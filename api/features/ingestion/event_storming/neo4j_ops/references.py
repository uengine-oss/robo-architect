from __future__ import annotations

from typing import Any


class ReferenceOps:
    # =========================================================================
    # REFERENCES Operations (Phase 2)
    # =========================================================================

    def fetch_fk_hint_sources(self) -> list[dict[str, Any]]:
        """
        Fetch candidate source properties for REFERENCES creation.

        Criteria (Phase 2):
        - src.isForeignKey = true
        - src.fkTargetHint is not null/empty
        """
        query = """
        MATCH (src:Property)
        WHERE coalesce(src.isForeignKey, false) = true
          AND src.fkTargetHint IS NOT NULL
          AND trim(toString(src.fkTargetHint)) <> ''
        RETURN src.id as id, src.fkTargetHint as fkTargetHint
        ORDER BY src.id
        """
        with self.session() as session:
            result = session.run(query)
            out: list[dict[str, Any]] = []
            for r in result:
                if not r:
                    continue
                sid = r.get("id")
                hint = r.get("fkTargetHint")
                if sid and hint:
                    out.append({"id": str(sid), "fkTargetHint": str(hint)})
            return out

    def create_references_from_hints(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Create REFERENCES relationships for parsed hint items.

        Each item must include:
        - srcId
        - tgtType (Aggregate|Command|Event|ReadModel)
        - tgtKey (natural key)
        - tgtProp (property name, typically 'id')

        Invariant:
        - Target Property must have isKey=true; otherwise skipped.
        """
        items = [it for it in (items or []) if isinstance(it, dict)]
        if not items:
            return {
                "scanned": 0,
                "parentFound": 0,
                "tgtFound": 0,
                "created": 0,
                "skipped_parent_missing": 0,
                "skipped_target_missing": 0,
                "skipped_not_key": 0,
            }

        # `CALL { … }` 서브쿼리와 조건부 `FOREACH` 쓰기는 백엔드 의존이 크다.
        # tgtType 이 대상 라벨을 정해주므로 타입별로 읽어 판정한 뒤,
        # 자격을 갖춘 것만 한 번에 쓴다.
        _TGT_LABELS = ("Aggregate", "Command", "Event", "ReadModel")

        stats = {
            "scanned": 0,
            "parentFound": 0,
            "tgtFound": 0,
            "created": 0,
            "skipped_parent_missing": 0,
            "skipped_target_missing": 0,
            "skipped_not_key": 0,
        }
        to_link: list[dict[str, Any]] = []

        with self.session() as session:
            for label in _TGT_LABELS:
                subset = [it for it in items if it.get("tgtType") == label]
                if not subset:
                    continue
                rows = session.run(
                    f"""
                    UNWIND $items AS it
                    MATCH (src:Property {{id: it.srcId}})
                    OPTIONAL MATCH (parent:{label} {{key: it.tgtKey}})
                    OPTIONAL MATCH (tgt:Property {{parentType: it.tgtType,
                                                   parentId: parent.id,
                                                   name: it.tgtProp}})
                    RETURN it.srcId AS srcId, parent.id AS parentId,
                           tgt.id AS tgtId, coalesce(tgt.isKey, false) AS tgtIsKey
                    """,
                    items=subset,
                )
                for row in rows:
                    stats["scanned"] += 1
                    parent_found = row["parentId"] is not None
                    tgt_found = row["tgtId"] is not None
                    if parent_found:
                        stats["parentFound"] += 1
                    if tgt_found:
                        stats["tgtFound"] += 1
                    if not parent_found:
                        stats["skipped_parent_missing"] += 1
                    elif not tgt_found:
                        stats["skipped_target_missing"] += 1
                    elif not bool(row["tgtIsKey"]):
                        stats["skipped_not_key"] += 1
                    else:
                        stats["created"] += 1
                        to_link.append({"srcId": row["srcId"], "tgtId": row["tgtId"]})

            # 대상 라벨이 넷 중 하나가 아니면 부모를 찾을 수 없다 — 원래 질의와
            # 같게 scanned 에 넣고 parent 미발견으로 센다.
            other = [it for it in items if it.get("tgtType") not in _TGT_LABELS]
            stats["scanned"] += len(other)
            stats["skipped_parent_missing"] += len(other)

            if to_link:
                session.run(
                    """
                    UNWIND $rows AS row
                    MATCH (src:Property {id: row.srcId})
                    MATCH (tgt:Property {id: row.tgtId})
                    SET src.isForeignKey = true
                    MERGE (src)-[:REFERENCES]->(tgt)
                    """,
                    rows=to_link,
                )

        return stats


