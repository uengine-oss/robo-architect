from __future__ import annotations

import json
from typing import Any


def _get(obj: Any, attr: str) -> Any:
    """Attribute access that works on both objects and plain dicts."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(attr)
    return getattr(obj, attr, None)


def _ref_json(obj: Any) -> str | None:
    """Pack a legacy given/when/then component into the single-`GWT`-node
    ``_GWTRef`` shape (``referencedNodeId`` / ``referencedNodeType`` /
    ``name``). Returns None when there is nothing referenceable."""
    if obj is None:
        return None
    name = (_get(obj, "name") or _get(obj, "description") or "").strip()
    ref_id = _get(obj, "referencedNodeId")
    ref_type = _get(obj, "referencedNodeType")
    if not (name or ref_id):
        return None
    return json.dumps(
        {"referencedNodeId": ref_id, "referencedNodeType": ref_type, "name": name or None}
    )


def _field_values(obj: Any) -> dict[str, Any]:
    fv = _get(obj, "fieldValues")
    return fv if isinstance(fv, dict) else {}


class GWTOps:
    """GWT persistence — the single-`GWT`-node model (``HAS_GWT``).

    One ``GWT`` node per parent (Command/Policy/Invariant) carries the
    Given-When-Then skeleton as ``givenRef`` / ``whenRef`` / ``thenRef`` plus
    a ``testCases`` bundle. This is the same shape written by the
    ``generate_gwt`` ingestion phase and the interactive GWT editor
    (``POST /api/graph/gwt/upsert``), so every reader sees one model.
    """

    def upsert_gwt(
        self,
        *,
        parent_type: str,
        parent_id: str,
        given: Any = None,
        when: Any = None,
        then: Any = None,
    ) -> bool:
        """MERGE the parent's single ``GWT`` node from given/when/then
        component objects (or dicts).

        Idempotent — re-runs update the same node, and slots may be filled
        across calls (a Command's ``then`` is only known after its events
        exist, so ``given``/``when`` are written first). Returns True on
        success.
        """
        if not parent_id:
            return False

        given_ref = _ref_json(given)
        when_ref = _ref_json(when)
        then_ref = _ref_json(then)
        if given_ref is None and when_ref is None and then_ref is None:
            return False

        # Fold any field-value maps into a single test case.
        gfv, wfv, tfv = _field_values(given), _field_values(when), _field_values(then)
        test_cases: list[dict[str, Any]] = []
        if gfv or wfv or tfv:
            test_cases.append(
                {
                    "scenarioDescription": (
                        _get(given, "description")
                        or _get(when, "description")
                        or "Ingested scenario"
                    ),
                    "givenFieldValues": gfv,
                    "whenFieldValues": wfv,
                    "thenFieldValues": tfv,
                }
            )

        # `coalesce` keeps a slot already written by an earlier call.
        query = """
        MATCH (parent {id: $parent_id})
        WHERE $parent_type IN labels(parent)
        MERGE (gwt:GWT {parentType: $parent_type, parentId: $parent_id})
          ON CREATE SET gwt.id = randomUUID(),
                        gwt.createdAt = datetime(),
                        gwt.testCases = '[]'
        SET gwt.updatedAt = datetime(),
            gwt.givenRef = coalesce($given_ref, gwt.givenRef),
            gwt.whenRef  = coalesce($when_ref, gwt.whenRef),
            gwt.thenRef  = coalesce($then_ref, gwt.thenRef),
            gwt.testCases = CASE WHEN $test_cases = '[]'
                                 THEN coalesce(gwt.testCases, '[]')
                                 ELSE $test_cases END
        MERGE (parent)-[:HAS_GWT]->(gwt)
        RETURN gwt.id AS id
        """
        with self.session() as session:
            rec = session.run(
                query,
                parent_type=parent_type,
                parent_id=parent_id,
                given_ref=given_ref,
                when_ref=when_ref,
                then_ref=then_ref,
                test_cases=json.dumps(test_cases),
            ).single()
            return rec is not None
