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
    ) -> dict[str, Any] | None:
        """MERGE an Invariant by its natural key and attach it to its Aggregate.

        `source` is only set on create, so a re-ingest never clobbers an
        invariant a planner has since edited.
        """
        key = _invariant_key(aggregate_key, declaration)
        query = """
        MATCH (agg:Aggregate {id: $aid})
        MERGE (inv:Invariant {key: $key})
          ON CREATE SET inv.id = randomUUID(),
                        inv.createdAt = datetime(),
                        inv.source = $source
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
