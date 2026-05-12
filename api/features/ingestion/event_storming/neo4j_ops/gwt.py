from __future__ import annotations

import json
from typing import Any

from ._bulk_helper import (
    BulkResult,
    bulk_flush,
    reorder_to_input,
)


def _make_gwt_bulk_cypher(
    *, label: str, var: str, parent_rel: str, default_ref_type: str | None
) -> str:
    """Build the per-kind UNWIND template — `:Given`/`:When`/`:Then` differ
    only in label, return-var name, parent-rel name, and default ref type."""
    ref_type_default = (
        f"coalesce(r.referenced_node_type, '{default_ref_type}')"
        if default_ref_type
        else "r.referenced_node_type"
    )
    return f"""
UNWIND $rows AS r
MATCH (parent {{id: r.parent_id}})
WHERE r.parent_type IN labels(parent)
MERGE ({var}:{label} {{parentType: r.parent_type, parentId: r.parent_id, key: r.key}})
  ON CREATE SET {var}.id = randomUUID(),
                {var}.createdAt = datetime()
SET {var}.key = r.key,
    {var}.name = r.name,
    {var}.description = r.description,
    {var}.referencedNodeId = r.referenced_node_id,
    {var}.referencedNodeType = {ref_type_default},
    {var}.parentType = r.parent_type,
    {var}.parentId = r.parent_id,
    {var}.fieldValues = r.field_values_json,
    {var}.updatedAt = datetime()
MERGE (parent)-[:{parent_rel}]->({var})
WITH {var}, r
CALL {{
  WITH {var}, r
  MATCH (ref {{id: r.referenced_node_id}})
  WHERE r.referenced_node_id IS NOT NULL AND r.referenced_node_type IS NOT NULL
    AND r.referenced_node_type IN labels(ref)
  MERGE ({var})-[:REFERENCES]->(ref)
  RETURN count(*) AS _
}}
RETURN {var} {{.id, .key, .name, .description, .referencedNodeId, .referencedNodeType, .fieldValues}} AS result
"""


_GIVEN_BULK_CYPHER = _make_gwt_bulk_cypher(
    label="Given", var="g", parent_rel="HAS_GIVEN", default_ref_type=None
)
_WHEN_BULK_CYPHER = _make_gwt_bulk_cypher(
    label="When", var="w", parent_rel="HAS_WHEN", default_ref_type="Aggregate"
)
_THEN_BULK_CYPHER = _make_gwt_bulk_cypher(
    label="Then", var="t", parent_rel="HAS_THEN", default_ref_type="Event"
)


def _normalize_gwt_row(r: dict[str, Any], *, kind: str) -> dict[str, Any]:
    """Apply per-row defaults (auto-derived `key`, JSON-encoded `field_values`)."""
    parent_id = r["parent_id"]
    key = r.get("key") or f"{kind}.{parent_id}"
    field_values = r.get("field_values")
    field_values_json = json.dumps(field_values) if field_values else None
    return {
        "key": key,
        "parent_type": r["parent_type"],
        "parent_id": parent_id,
        "name": r.get("name"),
        "description": r.get("description"),
        "referenced_node_id": r.get("referenced_node_id"),
        "referenced_node_type": r.get("referenced_node_type"),
        "field_values_json": field_values_json,
    }


class GWTOps:
    # =========================================================================
    # Given/When/Then Operations
    # =========================================================================

    def create_given(
        self,
        *,
        parent_type: str,  # "Command" or "Policy"
        parent_id: str,
        name: str,
        key: str | None = None,
        description: str | None = None,
        referenced_node_id: str | None = None,
        referenced_node_type: str | None = None,
        field_values: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Create a Given node and link it to Command/Policy via HAS_GIVEN."""
        key = key or f"given.{parent_id}"
        query = """
        MATCH (parent {id: $parent_id})
        WHERE $parent_type IN labels(parent)
        MERGE (g:Given {parentType: $parent_type, parentId: $parent_id, key: $key})
        ON CREATE SET g.id = randomUUID(),
                      g.createdAt = datetime()
        SET g.key = $key,
            g.name = $name,
            g.description = $description,
            g.referencedNodeId = $referenced_node_id,
            g.referencedNodeType = $referenced_node_type,
            g.parentType = $parent_type,
            g.parentId = $parent_id,
            g.fieldValues = $field_values_json,
            g.updatedAt = datetime()
        MERGE (parent)-[:HAS_GIVEN]->(g)
        WITH g, $referenced_node_id as ref_id, $referenced_node_type as ref_type
        WHERE ref_id IS NOT NULL AND ref_type IS NOT NULL
        MATCH (ref {id: ref_id})
        WHERE ref_type IN labels(ref)
        MERGE (g)-[:REFERENCES]->(ref)
        RETURN g {.id, .key, .name, .description, .referencedNodeId, .referencedNodeType, .fieldValues} as given
        """
        field_values_json = json.dumps(field_values) if field_values else None
        with self.session() as session:
            result = session.run(
                query,
                parent_type=parent_type,
                parent_id=parent_id,
                key=key,
                name=name,
                description=description,
                referenced_node_id=referenced_node_id,
                referenced_node_type=referenced_node_type,
                field_values_json=field_values_json,
            )
            given = dict(result.single()["given"])
            # Parse fieldValues JSON string back to dict
            if given.get("fieldValues") and isinstance(given["fieldValues"], str):
                given["fieldValues"] = json.loads(given["fieldValues"])
            return given

    def create_when(
        self,
        *,
        parent_type: str,  # "Command" or "Policy"
        parent_id: str,
        name: str,
        key: str | None = None,
        description: str | None = None,
        referenced_node_id: str | None = None,
        referenced_node_type: str = "Aggregate",
        field_values: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Create a When node and link it to Command/Policy via HAS_WHEN."""
        key = key or f"when.{parent_id}"
        query = """
        MATCH (parent {id: $parent_id})
        WHERE $parent_type IN labels(parent)
        MERGE (w:When {parentType: $parent_type, parentId: $parent_id, key: $key})
        ON CREATE SET w.id = randomUUID(),
                      w.createdAt = datetime()
        SET w.key = $key,
            w.name = $name,
            w.description = $description,
            w.referencedNodeId = $referenced_node_id,
            w.referencedNodeType = $referenced_node_type,
            w.parentType = $parent_type,
            w.parentId = $parent_id,
            w.fieldValues = $field_values_json,
            w.updatedAt = datetime()
        MERGE (parent)-[:HAS_WHEN]->(w)
        WITH w, $referenced_node_id as ref_id, $referenced_node_type as ref_type
        WHERE ref_id IS NOT NULL AND ref_type IS NOT NULL
        MATCH (ref {id: ref_id})
        WHERE ref_type IN labels(ref)
        MERGE (w)-[:REFERENCES]->(ref)
        RETURN w {.id, .key, .name, .description, .referencedNodeId, .referencedNodeType, .fieldValues} as when
        """
        field_values_json = json.dumps(field_values) if field_values else None
        with self.session() as session:
            result = session.run(
                query,
                parent_type=parent_type,
                parent_id=parent_id,
                key=key,
                name=name,
                description=description,
                referenced_node_id=referenced_node_id,
                referenced_node_type=referenced_node_type,
                field_values_json=field_values_json,
            )
            when = dict(result.single()["when"])
            # Parse fieldValues JSON string back to dict
            if when.get("fieldValues") and isinstance(when["fieldValues"], str):
                when["fieldValues"] = json.loads(when["fieldValues"])
            return when

    def create_then(
        self,
        *,
        parent_type: str,  # "Command" or "Policy"
        parent_id: str,
        name: str,
        key: str | None = None,
        description: str | None = None,
        referenced_node_id: str | None = None,
        referenced_node_type: str = "Event",
        field_values: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Create a Then node and link it to Command/Policy via HAS_THEN."""
        key = key or f"then.{parent_id}"
        query = """
        MATCH (parent {id: $parent_id})
        WHERE $parent_type IN labels(parent)
        MERGE (t:Then {parentType: $parent_type, parentId: $parent_id, key: $key})
        ON CREATE SET t.id = randomUUID(),
                      t.createdAt = datetime()
        SET t.key = $key,
            t.name = $name,
            t.description = $description,
            t.referencedNodeId = $referenced_node_id,
            t.referencedNodeType = $referenced_node_type,
            t.parentType = $parent_type,
            t.parentId = $parent_id,
            t.fieldValues = $field_values_json,
            t.updatedAt = datetime()
        MERGE (parent)-[:HAS_THEN]->(t)
        WITH t, $referenced_node_id as ref_id, $referenced_node_type as ref_type
        WHERE ref_id IS NOT NULL AND ref_type IS NOT NULL
        MATCH (ref {id: ref_id})
        WHERE ref_type IN labels(ref)
        MERGE (t)-[:REFERENCES]->(ref)
        RETURN t {.id, .key, .name, .description, .referencedNodeId, .referencedNodeType, .fieldValues} as then
        """
        field_values_json = json.dumps(field_values) if field_values else None
        with self.session() as session:
            result = session.run(
                query,
                parent_type=parent_type,
                parent_id=parent_id,
                key=key,
                name=name,
                description=description,
                referenced_node_id=referenced_node_id,
                referenced_node_type=referenced_node_type,
                field_values_json=field_values_json,
            )
            then = dict(result.single()["then"])
            # Parse fieldValues JSON string back to dict
            if then.get("fieldValues") and isinstance(then["fieldValues"], str):
                then["fieldValues"] = json.loads(then["fieldValues"])
            return then

    def _bulk_create_gwt_kind(
        self,
        rows: list[dict[str, Any]],
        *,
        kind: str,  # "given" | "when" | "then"
        cypher: str,
        entity: str,  # observability label
        session_id: str | None,
        phase: str | None,
    ) -> list[BulkResult]:
        """Shared body for the three Given/When/Then bulk helpers."""
        if not rows:
            return []
        normalized = [_normalize_gwt_row(r, kind=kind) for r in rows]
        results = bulk_flush(
            self.session,
            entity=entity,
            rows=normalized,
            cypher=cypher,
            return_field="result",
            required_fields=["parent_type", "parent_id"],
            dedupe_key=None,
            session_id=session_id,
            phase=phase,
        )
        # Parse fieldValues JSON back to dict on the way out (matches per-row).
        for r in results:
            fv = r.get("fieldValues") if isinstance(r, dict) else None
            if isinstance(fv, str):
                try:
                    r["fieldValues"] = json.loads(fv)
                except Exception:  # noqa: BLE001
                    pass
        return reorder_to_input(rows, results, [])

    def bulk_create_givens(
        self,
        rows: list[dict[str, Any]],
        *,
        session_id: str | None = None,
        phase: str | None = None,
    ) -> list[BulkResult]:
        """Bulk variant of `create_given`. Required: `parent_type`, `parent_id`."""
        return self._bulk_create_gwt_kind(
            rows,
            kind="given",
            cypher=_GIVEN_BULK_CYPHER,
            entity="given",
            session_id=session_id,
            phase=phase,
        )

    def bulk_create_whens(
        self,
        rows: list[dict[str, Any]],
        *,
        session_id: str | None = None,
        phase: str | None = None,
    ) -> list[BulkResult]:
        """Bulk variant of `create_when`. Required: `parent_type`, `parent_id`."""
        return self._bulk_create_gwt_kind(
            rows,
            kind="when",
            cypher=_WHEN_BULK_CYPHER,
            entity="when",
            session_id=session_id,
            phase=phase,
        )

    def bulk_create_thens(
        self,
        rows: list[dict[str, Any]],
        *,
        session_id: str | None = None,
        phase: str | None = None,
    ) -> list[BulkResult]:
        """Bulk variant of `create_then`. Required: `parent_type`, `parent_id`."""
        return self._bulk_create_gwt_kind(
            rows,
            kind="then",
            cypher=_THEN_BULK_CYPHER,
            entity="then",
            session_id=session_id,
            phase=phase,
        )
