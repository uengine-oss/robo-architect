from __future__ import annotations

from typing import Any

from api.platform.keys import policy_key

from ._bulk_helper import (
    BulkResult,
    bulk_flush,
    reorder_to_input,
    validate_required,
)


_POLICY_BULK_CYPHER = """
UNWIND $rows AS r
MATCH (bc:BoundedContext {id: r.bc_id})
MATCH (evt:Event {id: r.trigger_event_id})
MATCH (cmd:Command {id: r.invoke_command_id})
MERGE (pol:Policy {key: r.key})
  ON CREATE SET pol.id = randomUUID(),
                pol.createdAt = datetime()
SET pol.key = r.key,
    pol.name = r.name,
    pol.displayName = r.display_name,
    pol.description = r.description,
    pol.updatedAt = datetime()
MERGE (bc)-[:HAS_POLICY]->(pol)
MERGE (evt)-[:TRIGGERS {priority: 1, isEnabled: true}]->(pol)
MERGE (pol)-[:INVOKES {isAsync: true}]->(cmd)
RETURN pol {.id, .key, .name, .displayName, .description} AS result
"""


class PolicyOps:
    # =========================================================================
    # Policy Operations
    # =========================================================================

    def create_policy(
        self,
        *,
        name: str,
        bc_id: str,
        trigger_event_id: str,
        invoke_command_id: str,
        key: str | None = None,
        description: str | None = None,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a policy with TRIGGERS and INVOKES relationships."""
        import time
        start_time = time.time()
        MAX_TIMEOUT = 10.0  # 10초 최대 대기 시간
        
        try:
            with self.session() as session:
                elapsed = time.time() - start_time
                if elapsed > MAX_TIMEOUT:
                    raise TimeoutError(f"BC key lookup timeout for {bc_id} (elapsed: {elapsed:.2f}s)")
                
                bc_rec = session.run("MATCH (bc:BoundedContext {id: $id}) RETURN bc.key as key", id=bc_id).single()
                
                elapsed = time.time() - start_time
                if elapsed > MAX_TIMEOUT:
                    raise TimeoutError(f"BC key lookup timeout for {bc_id} (elapsed: {elapsed:.2f}s)")
                
                bc_key_value = (bc_rec or {}).get("key") or ""
                if not bc_key_value:
                    print(f"[NEO4J] create_policy ERROR: BoundedContext not found or missing key: {bc_id}", flush=True)
                    raise ValueError(f"BoundedContext not found or missing key: {bc_id}")
                key = key or policy_key(bc_key_value, name)
                display_name = display_name or name
                query = """
                MATCH (bc:BoundedContext {id: $bc_id})
                MATCH (evt:Event {id: $trigger_event_id})
                MATCH (cmd:Command {id: $invoke_command_id})
                MERGE (pol:Policy {key: $key})
                ON CREATE SET pol.id = randomUUID(),
                              pol.createdAt = datetime()
                SET pol.key = $key,
                    pol.name = $name,
                    pol.displayName = $display_name,
                    pol.description = $description,
                    pol.updatedAt = datetime()
                MERGE (bc)-[:HAS_POLICY]->(pol)
                MERGE (evt)-[:TRIGGERS {priority: 1, isEnabled: true}]->(pol)
                MERGE (pol)-[:INVOKES {isAsync: true}]->(cmd)
                RETURN pol {.id, .key, .name, .displayName, .description} as policy
                """
                elapsed = time.time() - start_time
                if elapsed > MAX_TIMEOUT:
                    raise TimeoutError(f"Policy creation query timeout for {name} (elapsed: {elapsed:.2f}s)")
                
                result = session.run(
                    query,
                    key=key,
                    name=name,
                    display_name=display_name,
                    bc_id=bc_id,
                    trigger_event_id=trigger_event_id,
                    invoke_command_id=invoke_command_id,
                    description=description,
                )
                
                elapsed = time.time() - start_time
                if elapsed > MAX_TIMEOUT:
                    raise TimeoutError(f"Policy creation query timeout for {name} (elapsed: {elapsed:.2f}s)")
                
                single_result = result.single()
                
                if not single_result:
                    print(f"[NEO4J] create_policy ERROR: No result returned for {name}", flush=True)
                    raise ValueError(f"No result returned from policy creation query for {name}")
                
                policy_dict = dict(single_result["policy"])
                return policy_dict
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[NEO4J] create_policy ERROR: {name} failed after {elapsed:.2f}s: {type(e).__name__}: {e}", flush=True)
            import traceback
            print(f"[NEO4J] create_policy ERROR: Traceback:\n{traceback.format_exc()}", flush=True)
            raise

    def bulk_create_policies(
        self,
        rows: list[dict[str, Any]],
        *,
        session_id: str | None = None,
        phase: str | None = None,
    ) -> list[BulkResult]:
        """Persist policies in batch — schema-equivalent to `create_policy`.

        Required: `name`, `bc_id`, `trigger_event_id`, `invoke_command_id`.
        Optional: `key`, `display_name`, `description`.

        Rows whose trigger event or invoke command do not match an existing
        node will produce no result row from the inner MATCH; the helper
        marks those as `{ok: False, error: "missing trigger/invoke target"}`.
        """
        if not rows:
            return []

        valid, errors = validate_required(
            rows, ["name", "bc_id", "trigger_event_id", "invoke_command_id"]
        )

        # Look up bc.key once per distinct bc_id.
        bc_ids = sorted({r["bc_id"] for r in valid})
        bc_key_map: dict[str, str] = {}
        if bc_ids:
            with self.session() as session:
                cur = session.run(
                    "MATCH (bc:BoundedContext) WHERE bc.id IN $ids RETURN bc.id AS id, bc.key AS key",
                    ids=bc_ids,
                )
                for rec in cur:
                    if rec and rec.get("id") and rec.get("key"):
                        bc_key_map[rec["id"]] = rec["key"]

        prepared: list[dict[str, Any]] = []
        bc_missing: list[BulkResult] = []
        for r in valid:
            bc_key_value = bc_key_map.get(r["bc_id"])
            if not bc_key_value:
                bc_missing.append(
                    {
                        "ok": False,
                        "error": f"BoundedContext not found: {r['bc_id']}",
                        "error_field": "bc_id",
                        "id": r.get("id"),
                    }
                )
                continue
            key = r.get("key") or policy_key(bc_key_value, r["name"])
            prepared.append(
                {
                    "key": key,
                    "name": r["name"],
                    "bc_id": r["bc_id"],
                    "trigger_event_id": r["trigger_event_id"],
                    "invoke_command_id": r["invoke_command_id"],
                    "display_name": r.get("display_name") or r["name"],
                    "description": r.get("description"),
                }
            )

        results = bulk_flush(
            self.session,
            entity="policy",
            rows=prepared,
            cypher=_POLICY_BULK_CYPHER,
            return_field="result",
            required_fields=["bc_id", "trigger_event_id", "invoke_command_id"],
            dedupe_key="key",
            session_id=session_id,
            phase=phase,
        )

        all_errors = list(bc_missing) + list(errors)
        return reorder_to_input(rows, results, all_errors)

    def link_user_story_to_policy(
        self, user_story_id: str, policy_id: str, confidence: float = 0.9
    ) -> bool:
        """Link a user story to a policy via IMPLEMENTS relationship."""
        import time
        start_time = time.time()
        MAX_TIMEOUT = 5.0  # 5초 최대 대기 시간
        
        query = """
        MATCH (us:UserStory {id: $user_story_id})
        MATCH (pol:Policy {id: $policy_id})
        MERGE (us)-[r:IMPLEMENTS]->(pol)
        SET r.confidence = $confidence,
            r.createdAt = datetime()
        RETURN us.id, pol.id
        """
        with self.session() as session:
            elapsed = time.time() - start_time
            if elapsed > MAX_TIMEOUT:
                raise TimeoutError(f"User story link timeout for {user_story_id} -> {policy_id} (elapsed: {elapsed:.2f}s)")
            
            result = session.run(
                query,
                user_story_id=user_story_id,
                policy_id=policy_id,
                confidence=confidence,
            )
            elapsed = time.time() - start_time
            if elapsed > MAX_TIMEOUT:
                raise TimeoutError(f"User story link timeout for {user_story_id} -> {policy_id} (elapsed: {elapsed:.2f}s)")
            return result.single() is not None


