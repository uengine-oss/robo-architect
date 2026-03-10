from __future__ import annotations

from typing import Any


class PropertyOps:
    # =========================================================================
    # Property Operations (Phase 1: generation + FK hint)
    # =========================================================================

    def upsert_properties_bulk(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Bulk upsert Property nodes and attach them to their parent via HAS_PROPERTY.

        Idempotency key:
        - (parentType, parentId, name)

        Policy:
        - upsert-only (no deletes)
        - always overwrite on match (latest LLM result wins)
        - fkTargetHint is optional; if null it will be removed (Neo4j semantics)
        """
        rows = [r for r in (rows or []) if isinstance(r, dict)]
        if not rows:
            return {"upserted": 0}

        query = """
        UNWIND $rows as row
        WITH row
        WHERE row.parentType IN ['Aggregate','Command','Event','ReadModel']
          AND row.parentId IS NOT NULL AND trim(toString(row.parentId)) <> ''
          AND row.name IS NOT NULL AND trim(toString(row.name)) <> ''
          AND row.type IS NOT NULL AND trim(toString(row.type)) <> ''
        MERGE (p:Property {parentType: row.parentType, parentId: row.parentId, name: row.name})
        ON CREATE SET p.id = randomUUID(),
                      p.createdAt = datetime()
        SET p.type = row.type,
            p.description = coalesce(row.description, ''),
            p.displayName = coalesce(row.displayName, row.name),
            p.isKey = coalesce(row.isKey, false),
            p.isForeignKey = coalesce(row.isForeignKey, false),
            p.isRequired = coalesce(row.isRequired, false),
            p.parentType = row.parentType,
            p.parentId = row.parentId,
            p.fkTargetHint = row.fkTargetHint,
            p.updatedAt = datetime()
        WITH row, p
        MATCH (parent {id: row.parentId})
        WHERE row.parentType IN labels(parent)
        MERGE (parent)-[:HAS_PROPERTY]->(p)
        RETURN count(p) as upserted
        """

        with self.session() as session:
            rec = session.run(query, rows=rows).single()
            return {"upserted": int((rec or {}).get("upserted") or 0)}


