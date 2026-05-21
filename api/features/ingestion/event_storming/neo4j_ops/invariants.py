"""Invariant node operations (027 — aggregate-invariants).

Used by the `extract_invariants` ingestion phase to persist LLM-extracted
invariants idempotently. Re-ingesting the same requirement `MERGE`s on the
natural key, so no duplicate Invariant is created (spec FR-022).

The interactive `/api/invariants` CRUD routes use their own `get_session()`
helper (`api/features/invariants/neo4j_ops.py`) — this mixin is the
ingestion-pipeline counterpart, mounted on `Neo4jClient`.
"""

from __future__ import annotations

from typing import Any

from api.platform.keys import invariant_key as _invariant_key


class InvariantOps:
    def upsert_invariant(
        self,
        *,
        aggregate_id: str,
        aggregate_key: str,
        declaration: str,
        name: str | None = None,
        source: str = "ingested",
        seq: int | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any] | None:
        """MERGE an Invariant by its natural key and attach it to its Aggregate.

        `source` and `session_id` are only set on create, so a re-ingest never
        clobbers an invariant a planner has since edited. An ingestion-created
        invariant carries the run's `session_id` (joins the session-scoped
        wipe on re-ingestion); a manually-created invariant has none and
        survives re-ingestion.
        """
        key = _invariant_key(aggregate_key, declaration)
        query = """
        MATCH (agg:Aggregate {id: $aid})
        MERGE (inv:Invariant {key: $key})
          ON CREATE SET inv.id = randomUUID(),
                        inv.createdAt = datetime(),
                        inv.source = $source,
                        inv.session_id = $session_id
        SET inv.declaration = $declaration,
            inv.name = $name,
            inv.aggregateId = agg.id,
            inv.seq = coalesce(inv.seq, $seq),
            inv.updatedAt = datetime()
        MERGE (agg)-[:HAS_INVARIANT]->(inv)
        RETURN inv {.id, .key, .name, .declaration, .source, .seq} AS invariant
        """
        with self.session() as session:
            rec = session.run(
                query,
                aid=aggregate_id,
                key=key,
                declaration=declaration,
                name=(name or declaration)[:80],
                source=source,
                seq=seq,
                session_id=session_id,
            ).single()
            return dict(rec["invariant"]) if rec else None

    def link_invariant_verified_by(self, invariant_id: str, command_id: str) -> bool:
        """Attach a VERIFIED_BY edge — only when the Command belongs to the same
        Aggregate as the Invariant. Returns False otherwise."""
        query = """
        MATCH (agg:Aggregate)-[:HAS_INVARIANT]->(inv:Invariant {id: $iid})
        MATCH (agg)-[:HAS_COMMAND]->(cmd:Command {id: $cid})
        MERGE (inv)-[r:VERIFIED_BY]->(cmd)
          ON CREATE SET r.createdAt = datetime()
        RETURN inv.id AS id
        """
        with self.session() as session:
            return session.run(query, iid=invariant_id, cid=command_id).single() is not None

    def prune_orphan_invariants(self) -> int:
        """Delete Invariant nodes not attached to any Aggregate.

        Invariants are MERGEd on `aggregate_key + declaration` and are not
        session-scoped. When a re-ingestion wipes the session's Aggregates and
        the model re-extraction renames an aggregate, the old aggregate's
        invariants are left dangling (no `HAS_INVARIANT` parent). Every
        invariant-creation path attaches the node to its Aggregate, so an
        unattached Invariant is always stale — safe to remove. Run as
        housekeeping at the start of the extract-invariants phase.
        """
        query = """
        MATCH (inv:Invariant)
        WHERE NOT (:Aggregate)-[:HAS_INVARIANT]->(inv)
        DETACH DELETE inv
        RETURN count(inv) AS pruned
        """
        with self.session() as session:
            rec = session.run(query).single()
            return int(rec["pruned"]) if rec else 0
