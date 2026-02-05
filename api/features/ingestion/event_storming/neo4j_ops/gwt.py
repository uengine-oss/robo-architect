from __future__ import annotations

import json
from typing import Any


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
