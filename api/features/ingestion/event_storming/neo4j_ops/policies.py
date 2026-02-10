from __future__ import annotations

from typing import Any

from api.platform.keys import policy_key


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
    ) -> dict[str, Any]:
        """Create a policy with TRIGGERS and INVOKES relationships."""
        import time
        print(f"[NEO4J] create_policy START: {name} (bc_id={bc_id}, trigger_event_id={trigger_event_id}, invoke_command_id={invoke_command_id})", flush=True)
        start_time = time.time()
        MAX_TIMEOUT = 10.0  # 10초 최대 대기 시간
        
        try:
            print(f"[NEO4J] create_policy: Opening session for {name}", flush=True)
            with self.session() as session:
                print(f"[NEO4J] create_policy: Session opened, fetching BC key for {bc_id}", flush=True)
                elapsed = time.time() - start_time
                if elapsed > MAX_TIMEOUT:
                    raise TimeoutError(f"BC key lookup timeout for {bc_id} (elapsed: {elapsed:.2f}s)")
                
                print(f"[NEO4J] create_policy: Running BC key query for {bc_id}", flush=True)
                bc_query_start = time.time()
                bc_rec = session.run("MATCH (bc:BoundedContext {id: $id}) RETURN bc.key as key", id=bc_id).single()
                bc_query_elapsed = time.time() - bc_query_start
                print(f"[NEO4J] create_policy: BC key query completed in {bc_query_elapsed:.2f}s for {bc_id}", flush=True)
                
                elapsed = time.time() - start_time
                if elapsed > MAX_TIMEOUT:
                    raise TimeoutError(f"BC key lookup timeout for {bc_id} (elapsed: {elapsed:.2f}s)")
                
                bc_key_value = (bc_rec or {}).get("key") or ""
                if not bc_key_value:
                    print(f"[NEO4J] create_policy ERROR: BoundedContext not found or missing key: {bc_id}", flush=True)
                    raise ValueError(f"BoundedContext not found or missing key: {bc_id}")
                key = key or policy_key(bc_key_value, name)
                print(f"[NEO4J] create_policy: BC key resolved: {bc_key_value}, policy key: {key}", flush=True)

                print(f"[NEO4J] create_policy: Creating policy node for {name}", flush=True)
                query = """
                MATCH (bc:BoundedContext {id: $bc_id})
                MATCH (evt:Event {id: $trigger_event_id})
                MATCH (cmd:Command {id: $invoke_command_id})
                MERGE (pol:Policy {key: $key})
                ON CREATE SET pol.id = randomUUID(),
                              pol.createdAt = datetime()
                SET pol.key = $key,
                    pol.name = $name,
                    pol.description = $description,
                    pol.updatedAt = datetime()
                MERGE (bc)-[:HAS_POLICY]->(pol)
                MERGE (evt)-[:TRIGGERS {priority: 1, isEnabled: true}]->(pol)
                MERGE (pol)-[:INVOKES {isAsync: true}]->(cmd)
                RETURN pol {.id, .key, .name, .description} as policy
                """
                elapsed = time.time() - start_time
                if elapsed > MAX_TIMEOUT:
                    raise TimeoutError(f"Policy creation query timeout for {name} (elapsed: {elapsed:.2f}s)")
                
                print(f"[NEO4J] create_policy: Running MERGE query for {name}", flush=True)
                merge_query_start = time.time()
                result = session.run(
                    query,
                    key=key,
                    name=name,
                    bc_id=bc_id,
                    trigger_event_id=trigger_event_id,
                    invoke_command_id=invoke_command_id,
                    description=description,
                )
                merge_query_elapsed = time.time() - merge_query_start
                print(f"[NEO4J] create_policy: MERGE query completed in {merge_query_elapsed:.2f}s for {name}", flush=True)
                
                elapsed = time.time() - start_time
                if elapsed > MAX_TIMEOUT:
                    raise TimeoutError(f"Policy creation query timeout for {name} (elapsed: {elapsed:.2f}s)")
                
                print(f"[NEO4J] create_policy: Fetching result for {name}", flush=True)
                result_start = time.time()
                single_result = result.single()
                result_elapsed = time.time() - result_start
                print(f"[NEO4J] create_policy: Result fetched in {result_elapsed:.2f}s for {name}", flush=True)
                
                if not single_result:
                    print(f"[NEO4J] create_policy ERROR: No result returned for {name}", flush=True)
                    raise ValueError(f"No result returned from policy creation query for {name}")
                
                policy_dict = dict(single_result["policy"])
                elapsed = time.time() - start_time
                print(f"[NEO4J] create_policy SUCCESS: {name}, id: {policy_dict.get('id')}, total elapsed: {elapsed:.2f}s", flush=True)
                return policy_dict
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[NEO4J] create_policy ERROR: {name} failed after {elapsed:.2f}s: {type(e).__name__}: {e}", flush=True)
            import traceback
            print(f"[NEO4J] create_policy ERROR: Traceback:\n{traceback.format_exc()}", flush=True)
            raise

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


