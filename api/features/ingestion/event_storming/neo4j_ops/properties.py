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

        # 부모 라벨을 붙이지 않는 `MATCH (parent {id: …})` 와
        # `row.parentType IN labels(parent)` 는 백엔드 의존이 크다.
        # parentType 을 이미 알고 있으므로 타입별로 나눠 라벨을 명시한다.
        _PARENT_LABELS = ("Aggregate", "Command", "Event", "ReadModel")

        def _valid(r: dict[str, Any]) -> bool:
            if r.get("parentType") not in _PARENT_LABELS:
                return False
            for k in ("parentId", "name", "type"):
                v = r.get(k)
                if v is None or not str(v).strip():
                    return False
            return True

        valid_rows = [r for r in rows if _valid(r)]
        if not valid_rows:
            return {"upserted": 0}

        upsert_query = """
        UNWIND $rows as row
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
        RETURN count(p) as upserted
        """

        with self.session() as session:
            rec = session.run(upsert_query, rows=valid_rows).single()
            upserted = int((rec or {}).get("upserted") or 0)

            for label in _PARENT_LABELS:
                subset = [r for r in valid_rows if r.get("parentType") == label]
                if not subset:
                    continue
                session.run(
                    f"""
                    UNWIND $rows as row
                    MATCH (parent:{label} {{id: row.parentId}})
                    MATCH (p:Property {{parentType: row.parentType,
                                        parentId: row.parentId, name: row.name}})
                    MERGE (parent)-[:HAS_PROPERTY]->(p)
                    """,
                    rows=subset,
                )
            return {"upserted": upserted}


