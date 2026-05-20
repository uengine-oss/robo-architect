"""Neo4j graph operations for Aggregate Invariants (027).

Raw Cypher against the platform Neo4j session. Higher-level orchestration and
DTO assembly live in `invariants_service.py`.

Storage model
-------------
- `Invariant` node, `Aggregate-[:HAS_INVARIANT]->Invariant`.
- Detailed conditions reuse the existing single-`GWT`-node model
  (`/api/graph/gwt/upsert`): a shared condition is the Command's own
  `GWT {parentType:"Command"}` reached via `Invariant-[:VERIFIED_BY]->Command`;
  an invariant-owned condition is `GWT {parentType:"Invariant", parentId:<inv.id>}`
  reached via `Invariant-[:HAS_GWT]->GWT`.
"""

from __future__ import annotations

import json
from typing import Any

from api.platform.keys import invariant_key
from api.platform.neo4j import get_session

_INV_RETURN = "inv {.id, .key, .name, .declaration, .description, .source, .seq}"


# ── Aggregate lookup ─────────────────────────────────────────────────────


def get_aggregate(aggregate_id: str) -> dict[str, Any] | None:
    with get_session() as session:
        rec = session.run(
            "MATCH (agg:Aggregate {id: $id}) RETURN agg.id AS id, agg.key AS key, agg.name AS name",
            id=aggregate_id,
        ).single()
        return dict(rec) if rec else None


# ── List / read ──────────────────────────────────────────────────────────


def list_invariants(aggregate_id: str) -> list[dict[str, Any]]:
    """Summary rows for every Invariant of an Aggregate (ordered by seq)."""
    query = f"""
    MATCH (agg:Aggregate {{id: $aid}})-[:HAS_INVARIANT]->(inv:Invariant)
    OPTIONAL MATCH (inv)-[:VERIFIED_BY]->(c:Command)
    OPTIONAL MATCH (inv)-[:HAS_GWT]->(g:GWT)
    WITH inv, count(DISTINCT c) AS refCount, count(DISTINCT g) AS ownCount
    RETURN {_INV_RETURN} AS inv, refCount, ownCount
    ORDER BY coalesce(inv.seq, 0), inv.declaration
    """
    with get_session() as session:
        out: list[dict[str, Any]] = []
        for rec in session.run(query, aid=aggregate_id):
            inv = dict(rec["inv"])
            inv["referencedCommandCount"] = int(rec["refCount"] or 0)
            inv["isSpecified"] = (rec["refCount"] or 0) > 0 or (rec["ownCount"] or 0) > 0
            out.append(inv)
        return out


def get_invariant(invariant_id: str) -> dict[str, Any] | None:
    """Full detail for one Invariant: owning aggregate, references, own-GWT flag."""
    query = f"""
    MATCH (agg:Aggregate)-[:HAS_INVARIANT]->(inv:Invariant {{id: $id}})
    OPTIONAL MATCH (inv)-[:VERIFIED_BY]->(c:Command)
    OPTIONAL MATCH (c)-[:HAS_GWT]->(cg:GWT)
    WITH agg, inv,
         collect(DISTINCT CASE WHEN c IS NULL THEN NULL
            ELSE {{commandId: c.id, commandName: c.name, hasGwt: cg IS NOT NULL}} END) AS refs
    OPTIONAL MATCH (inv)-[:HAS_GWT]->(og:GWT)
    RETURN agg {{.id, .name}} AS agg, {_INV_RETURN} AS inv,
           refs, (og IS NOT NULL) AS hasOwnGwt
    """
    with get_session() as session:
        rec = session.run(query, id=invariant_id).single()
        if not rec:
            return None
        agg = dict(rec["agg"])
        inv = dict(rec["inv"])
        refs = [dict(r) for r in (rec["refs"] or []) if r]
        inv["aggregateId"] = agg.get("id")
        inv["aggregateName"] = agg.get("name") or ""
        inv["referencedConditions"] = refs
        inv["hasOwnGwt"] = bool(rec["hasOwnGwt"])
        inv["isSpecified"] = bool(refs) or inv["hasOwnGwt"]
        return inv


def find_invariant_id_by_key(key: str) -> str | None:
    with get_session() as session:
        rec = session.run(
            "MATCH (inv:Invariant {key: $key}) RETURN inv.id AS id", key=key
        ).single()
        return rec["id"] if rec else None


# ── Create / update / delete ─────────────────────────────────────────────


def create_invariant(
    *,
    aggregate_id: str,
    aggregate_key: str,
    declaration: str,
    name: str | None = None,
    description: str | None = None,
    source: str = "manual",
) -> tuple[dict[str, Any] | None, str | None]:
    """Create an Invariant under an Aggregate.

    Returns (invariant_dict, error). error is one of None / "duplicate".
    """
    key = invariant_key(aggregate_key, declaration)
    resolved_name = (name or declaration).strip()[:80] or "Invariant"
    with get_session() as session:
        existing = session.run(
            "MATCH (inv:Invariant {key: $key}) RETURN inv.id AS id", key=key
        ).single()
        if existing:
            return None, "duplicate"

        seq_rec = session.run(
            """
            MATCH (agg:Aggregate {id: $aid})-[:HAS_INVARIANT]->(inv:Invariant)
            RETURN coalesce(max(inv.seq), 0) AS maxSeq
            """,
            aid=aggregate_id,
        ).single()
        next_seq = int((seq_rec["maxSeq"] if seq_rec else 0) or 0) + 1

        rec = session.run(
            f"""
            MATCH (agg:Aggregate {{id: $aid}})
            MERGE (inv:Invariant {{key: $key}})
              ON CREATE SET inv.id = randomUUID(), inv.createdAt = datetime()
            SET inv.declaration = $declaration,
                inv.name = $name,
                inv.description = $description,
                inv.source = $source,
                inv.seq = $seq,
                inv.aggregateId = agg.id,
                inv.updatedAt = datetime()
            MERGE (agg)-[:HAS_INVARIANT]->(inv)
            RETURN {_INV_RETURN} AS inv
            """,
            aid=aggregate_id,
            key=key,
            declaration=declaration,
            name=resolved_name,
            description=description,
            source=source,
            seq=next_seq,
        ).single()
        return (dict(rec["inv"]) if rec else None), None


def update_invariant(invariant_id: str, fields: dict[str, Any]) -> bool:
    """Patch declaration/name/description. Returns False if not found."""
    sets = ["inv.updatedAt = datetime()"]
    params: dict[str, Any] = {"id": invariant_id}
    for col in ("declaration", "name", "description"):
        if col in fields and fields[col] is not None:
            sets.append(f"inv.{col} = ${col}")
            params[col] = fields[col]
    query = f"MATCH (inv:Invariant {{id: $id}}) SET {', '.join(sets)} RETURN inv.id AS id"
    with get_session() as session:
        rec = session.run(query, **params).single()
        return rec is not None


def delete_invariant(invariant_id: str) -> bool:
    """Delete an Invariant. Its own GWT bundle is removed; Command GWT reached
    via VERIFIED_BY is preserved (the edge is dropped by DETACH DELETE)."""
    with get_session() as session:
        exists = session.run(
            "MATCH (inv:Invariant {id: $id}) RETURN inv.id AS id", id=invariant_id
        ).single()
        if not exists:
            return False
        session.run(
            """
            MATCH (inv:Invariant {id: $id})
            OPTIONAL MATCH (inv)-[:HAS_GWT]->(og:GWT)
            DETACH DELETE og
            """,
            id=invariant_id,
        )
        session.run(
            "MATCH (inv:Invariant {id: $id}) DETACH DELETE inv", id=invariant_id
        )
        return True


# ── References (VERIFIED_BY — shared conditions) ─────────────────────────


def list_reference_candidates(invariant_id: str) -> list[dict[str, Any]] | None:
    """Commands of the invariant's Aggregate, with GWT + already-referenced flags.

    Returns None if the invariant does not exist.
    """
    with get_session() as session:
        if not session.run(
            "MATCH (inv:Invariant {id: $id}) RETURN inv.id AS id", id=invariant_id
        ).single():
            return None
        rows = session.run(
            """
            MATCH (agg:Aggregate)-[:HAS_INVARIANT]->(inv:Invariant {id: $id})
            MATCH (agg)-[:HAS_COMMAND]->(cmd:Command)
            OPTIONAL MATCH (cmd)-[:HAS_GWT]->(g:GWT)
            RETURN cmd.id AS commandId, cmd.name AS commandName,
                   (g IS NOT NULL) AS hasGwt,
                   EXISTS { (inv)-[:VERIFIED_BY]->(cmd) } AS alreadyReferenced
            ORDER BY cmd.name
            """,
            id=invariant_id,
        )
        return [dict(r) for r in rows]


def add_reference(invariant_id: str, command_id: str) -> str:
    """Add a VERIFIED_BY edge. Returns a status string:
    "ok" | "invariant_not_found" | "command_not_found" |
    "wrong_aggregate" | "already_referenced".
    """
    with get_session() as session:
        diag = session.run(
            """
            OPTIONAL MATCH (inv:Invariant {id: $iid})
            OPTIONAL MATCH (cmd:Command {id: $cid})
            OPTIONAL MATCH (agg:Aggregate)-[:HAS_INVARIANT]->(inv)
            RETURN inv IS NOT NULL AS invExists,
                   cmd IS NOT NULL AS cmdExists,
                   (inv IS NOT NULL AND cmd IS NOT NULL
                      AND EXISTS { (agg)-[:HAS_COMMAND]->(cmd) }) AS sameAgg,
                   (inv IS NOT NULL AND cmd IS NOT NULL
                      AND EXISTS { (inv)-[:VERIFIED_BY]->(cmd) }) AS already
            """,
            iid=invariant_id,
            cid=command_id,
        ).single()
        if not diag or not diag["invExists"]:
            return "invariant_not_found"
        if not diag["cmdExists"]:
            return "command_not_found"
        if not diag["sameAgg"]:
            return "wrong_aggregate"
        if diag["already"]:
            return "already_referenced"
        session.run(
            """
            MATCH (inv:Invariant {id: $iid})
            MATCH (cmd:Command {id: $cid})
            MERGE (inv)-[r:VERIFIED_BY]->(cmd)
              ON CREATE SET r.createdAt = datetime()
            """,
            iid=invariant_id,
            cid=command_id,
        )
        return "ok"


def remove_reference(invariant_id: str, command_id: str) -> bool:
    """Drop one VERIFIED_BY edge. The Command's GWT is never touched.
    Returns False when no such edge existed."""
    with get_session() as session:
        rec = session.run(
            """
            MATCH (inv:Invariant {id: $iid})-[r:VERIFIED_BY]->(cmd:Command {id: $cid})
            DELETE r
            RETURN count(r) AS removed
            """,
            iid=invariant_id,
            cid=command_id,
        ).single()
        return bool(rec and rec["removed"])


# ── Exception domain-object catalog on the Aggregate ─────────────────────
# Stored as a JSON-string property `Aggregate.exceptions`, sibling to the
# existing `enumerations` / `valueObjects` JSON properties.


def get_exceptions(aggregate_id: str) -> list[dict[str, Any]] | None:
    """Return the Aggregate's exception catalog. None when the Aggregate is unknown."""
    with get_session() as session:
        rec = session.run(
            "MATCH (agg:Aggregate {id: $id}) RETURN agg.exceptions AS exceptions",
            id=aggregate_id,
        ).single()
        if rec is None:
            return None
        raw = rec["exceptions"]
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return []
            return parsed if isinstance(parsed, list) else []
        return raw if isinstance(raw, list) else []


def put_exceptions(aggregate_id: str, exceptions: list[dict[str, Any]]) -> bool:
    """Replace the Aggregate's exception catalog. False when the Aggregate is unknown."""
    with get_session() as session:
        rec = session.run(
            """
            MATCH (agg:Aggregate {id: $id})
            SET agg.exceptions = $exceptions, agg.updatedAt = datetime()
            RETURN agg.id AS id
            """,
            id=aggregate_id,
            exceptions=json.dumps(exceptions),
        ).single()
        return rec is not None


# ── Lazy migration of legacy Aggregate.invariants text (R5) ──────────────


def migrate_legacy_invariants(aggregate_id: str) -> int:
    """Convert legacy `Aggregate.invariants` strings into first-class Invariant
    objects. Idempotent — guarded by `Aggregate.invariantsMigratedAt`.

    Returns the number of Invariant objects created (0 if already migrated).
    """
    with get_session() as session:
        rec = session.run(
            """
            MATCH (agg:Aggregate {id: $id})
            RETURN agg.key AS key, agg.invariants AS invariants,
                   agg.invariantsMigratedAt AS migratedAt
            """,
            id=aggregate_id,
        ).single()
        if not rec or rec["migratedAt"] is not None:
            return 0

        seen: set[str] = set()
        cleaned: list[str] = []
        for raw in rec["invariants"] or []:
            text = (str(raw) if raw is not None else "").strip()
            if text and text not in seen:
                seen.add(text)
                cleaned.append(text)

        for i, declaration in enumerate(cleaned, start=1):
            key = invariant_key(rec["key"], declaration)
            session.run(
                """
                MATCH (agg:Aggregate {id: $aid})
                MERGE (inv:Invariant {key: $key})
                  ON CREATE SET inv.id = randomUUID(), inv.createdAt = datetime()
                SET inv.declaration = $declaration,
                    inv.name = $name,
                    inv.source = 'migrated',
                    inv.seq = $seq,
                    inv.aggregateId = agg.id,
                    inv.updatedAt = datetime()
                MERGE (agg)-[:HAS_INVARIANT]->(inv)
                """,
                aid=aggregate_id,
                key=key,
                declaration=declaration,
                name=declaration[:80],
                seq=i,
            )

        # Stamp + clear the legacy list so it is no longer the source of truth.
        session.run(
            """
            MATCH (agg:Aggregate {id: $id})
            SET agg.invariantsMigratedAt = datetime(), agg.invariants = []
            """,
            id=aggregate_id,
        )
        return len(cleaned)
