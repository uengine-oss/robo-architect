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

        query = """
        UNWIND $items as it
        MATCH (src:Property {id: it.srcId})
        WITH src, it
        CALL {
          WITH it
          OPTIONAL MATCH (pAgg:Aggregate {key: it.tgtKey}) WHERE it.tgtType = 'Aggregate'
          OPTIONAL MATCH (pCmd:Command {key: it.tgtKey}) WHERE it.tgtType = 'Command'
          OPTIONAL MATCH (pEvt:Event {key: it.tgtKey}) WHERE it.tgtType = 'Event'
          OPTIONAL MATCH (pRm:ReadModel {key: it.tgtKey}) WHERE it.tgtType = 'ReadModel'
          RETURN coalesce(pAgg, pCmd, pEvt, pRm) as parent
        }
        WITH src, it, parent
        OPTIONAL MATCH (tgt:Property {parentType: it.tgtType, parentId: parent.id, name: it.tgtProp})
        WITH src, it, parent, tgt,
             (parent IS NOT NULL) as parentFound,
             (tgt IS NOT NULL) as tgtFound,
             (coalesce(tgt.isKey, false) = true) as tgtIsKey
        FOREACH (_ IN CASE WHEN parentFound AND tgtFound AND tgtIsKey THEN [1] ELSE [] END |
          SET src.isForeignKey = true
          MERGE (src)-[:REFERENCES]->(tgt)
        )
        RETURN
          count(*) as scanned,
          sum(CASE WHEN parentFound THEN 1 ELSE 0 END) as parentFound,
          sum(CASE WHEN tgtFound THEN 1 ELSE 0 END) as tgtFound,
          sum(CASE WHEN parentFound AND tgtFound AND tgtIsKey THEN 1 ELSE 0 END) as created,
          sum(CASE WHEN NOT parentFound THEN 1 ELSE 0 END) as skipped_parent_missing,
          sum(CASE WHEN parentFound AND NOT tgtFound THEN 1 ELSE 0 END) as skipped_target_missing,
          sum(CASE WHEN parentFound AND tgtFound AND NOT tgtIsKey THEN 1 ELSE 0 END) as skipped_not_key
        """

        with self.session() as session:
            rec = session.run(query, items=items).single() or {}
            return {
                "scanned": int(rec.get("scanned") or 0),
                "parentFound": int(rec.get("parentFound") or 0),
                "tgtFound": int(rec.get("tgtFound") or 0),
                "created": int(rec.get("created") or 0),
                "skipped_parent_missing": int(rec.get("skipped_parent_missing") or 0),
                "skipped_target_missing": int(rec.get("skipped_target_missing") or 0),
                "skipped_not_key": int(rec.get("skipped_not_key") or 0),
            }


