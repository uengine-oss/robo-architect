from __future__ import annotations

import json
from typing import Any

from api.platform.keys import aggregate_key


class AggregateOps:
    # =========================================================================
    # Aggregate Operations
    # =========================================================================

    def get_aggregates_by_bc(self, bc_id: str) -> list[dict[str, Any]]:
        """Fetch aggregates belonging to a bounded context."""
        query = """
        MATCH (bc:BoundedContext {id: $bc_id})-[:HAS_AGGREGATE]->(agg:Aggregate)
        OPTIONAL MATCH (agg)-[:HAS_COMMAND]->(cmd:Command)
        WITH agg, collect(DISTINCT cmd {.id, .name}) as commands
        RETURN {
            id: agg.id,
            name: agg.name,
            rootEntity: agg.rootEntity,
            invariants: agg.invariants,
            enumerations: agg.enumerations,
            valueObjects: agg.valueObjects,
            commands: commands
        } as aggregate
        ORDER BY aggregate.name
        """
        with self.session() as session:
            result = session.run(query, bc_id=bc_id)
            aggregates = []
            for record in result:
                agg_dict = dict(record["aggregate"])
                # Parse JSON strings back to lists
                if isinstance(agg_dict.get("enumerations"), str):
                    try:
                        agg_dict["enumerations"] = json.loads(agg_dict["enumerations"])
                    except (json.JSONDecodeError, TypeError):
                        agg_dict["enumerations"] = []
                elif agg_dict.get("enumerations") is None:
                    agg_dict["enumerations"] = []
                
                if isinstance(agg_dict.get("valueObjects"), str):
                    try:
                        agg_dict["valueObjects"] = json.loads(agg_dict["valueObjects"])
                    except (json.JSONDecodeError, TypeError):
                        agg_dict["valueObjects"] = []
                elif agg_dict.get("valueObjects") is None:
                    agg_dict["valueObjects"] = []
                
                aggregates.append(agg_dict)
            return aggregates

    def create_aggregate(
        self,
        *,
        name: str,
        bc_id: str,
        key: str | None = None,
        root_entity: str | None = None,
        invariants: list[str] | None = None,
        enumerations: list[dict[str, Any]] | None = None,
        value_objects: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Create a new aggregate and link it to a bounded context.

        IMPORTANT: One Aggregate belongs to exactly ONE Bounded Context.
        If an aggregate with the same key already exists and belongs to a different BC,
        this will raise an error.
        """
        with self.session() as session:
            bc_rec = session.run("MATCH (bc:BoundedContext {id: $id}) RETURN bc.key as key", id=bc_id).single()
            bc_key_value = (bc_rec or {}).get("key") or ""
            if not bc_key_value:
                raise ValueError(f"BoundedContext not found or missing key: {bc_id}")
            key = key or aggregate_key(bc_key_value, name)

            check_query = """
            OPTIONAL MATCH (existing:Aggregate {key: $key})<-[:HAS_AGGREGATE]-(otherBC:BoundedContext)
            WHERE otherBC.id <> $bc_id
            RETURN otherBC.id as existing_bc
            """
            record = session.run(check_query, key=key, bc_id=bc_id).single()
            if record and record["existing_bc"]:
                raise ValueError(
                    f"Aggregate {key} already belongs to BC {record['existing_bc']}. "
                    f"An Aggregate can only belong to ONE Bounded Context."
                )

        query = """
        MATCH (bc:BoundedContext {id: $bc_id})
        MERGE (agg:Aggregate {key: $key})
        ON CREATE SET agg.id = randomUUID(),
                      agg.createdAt = datetime()
        SET agg.key = $key,
            agg.name = $name,
            agg.rootEntity = $root_entity,
            agg.invariants = $invariants,
            agg.enumerations = $enumerations_json,
            agg.valueObjects = $value_objects_json,
            agg.updatedAt = datetime()
        WITH bc, agg
        MERGE (bc)-[:HAS_AGGREGATE {isPrimary: false}]->(agg)
        WITH agg
        RETURN {
            id: agg.id,
            key: agg.key,
            name: agg.name,
            rootEntity: agg.rootEntity,
            invariants: agg.invariants,
            enumerations: agg.enumerations,
            valueObjects: agg.valueObjects
        } as aggregate
        LIMIT 1
        """
        with self.session() as session:
            # Convert enumerations and value_objects to JSON-serializable format
            enum_list = []
            if enumerations:
                for enum in enumerations:
                    if isinstance(enum, dict):
                        enum_name = enum.get("name")
                        if enum_name:  # Only add if name exists
                            enum_list.append({
                                "name": str(enum_name),
                                "alias": enum.get("alias"),
                                "items": enum.get("items", [])
                            })
                    else:
                        # Handle Pydantic model
                        enum_name = getattr(enum, "name", None)
                        if enum_name:  # Only add if name exists
                            enum_list.append({
                                "name": str(enum_name),
                                "alias": getattr(enum, "alias", None),
                                "items": getattr(enum, "items", []) or []
                            })
            
            vo_list = []
            if value_objects:
                for vo in value_objects:
                    if isinstance(vo, dict):
                        vo_name = vo.get("name")
                        if vo_name:  # Only add if name exists
                            # Convert fields to dict format
                            fields_list = vo.get("fields", [])
                            fields_dicts = []
                            for field in fields_list:
                                if isinstance(field, dict):
                                    fields_dicts.append(field)
                                else:
                                    # Handle Pydantic ValueObjectField model
                                    fields_dicts.append({
                                        "name": getattr(field, "name", ""),
                                        "type": getattr(field, "type", "")
                                    })
                            vo_list.append({
                                "name": str(vo_name),
                                "alias": vo.get("alias"),
                                "referencedAggregateName": vo.get("referenced_aggregate_name"),
                                "referencedAggregateField": vo.get("referenced_aggregate_field"),
                                "fields": fields_dicts
                            })
                    else:
                        # Handle Pydantic model
                        vo_name = getattr(vo, "name", None)
                        if vo_name:  # Only add if name exists
                            # Convert fields to dict format
                            fields_list = getattr(vo, "fields", []) or []
                            fields_dicts = []
                            for field in fields_list:
                                if isinstance(field, dict):
                                    fields_dicts.append(field)
                                else:
                                    # Handle Pydantic ValueObjectField model
                                    fields_dicts.append({
                                        "name": getattr(field, "name", ""),
                                        "type": getattr(field, "type", "")
                                    })
                            vo_list.append({
                                "name": str(vo_name),
                                "alias": getattr(vo, "alias", None),
                                "referencedAggregateName": getattr(vo, "referenced_aggregate_name", None),
                                "referencedAggregateField": getattr(vo, "referenced_aggregate_field", None),
                                "fields": fields_dicts
                            })
            
            # Convert to JSON strings for Neo4j storage (Neo4j doesn't support nested maps in arrays)
            enumerations_json = json.dumps(enum_list) if enum_list else "[]"
            value_objects_json = json.dumps(vo_list) if vo_list else "[]"
            
            try:
                result = session.run(
                    query,
                    key=key,
                    name=name,
                    bc_id=bc_id,
                    root_entity=root_entity or name,
                    invariants=invariants or [],
                    enumerations_json=enumerations_json,
                    value_objects_json=value_objects_json,
                )
                records = list(result)
                if not records:
                    raise ValueError(f"Failed to create aggregate: {name}")
                record = records[0]
                agg_dict = dict(record["aggregate"])
                
                # Parse JSON strings back to lists for return value
                if isinstance(agg_dict.get("enumerations"), str):
                    agg_dict["enumerations"] = json.loads(agg_dict["enumerations"])
                if isinstance(agg_dict.get("valueObjects"), str):
                    agg_dict["valueObjects"] = json.loads(agg_dict["valueObjects"])
            except Exception as e:
                from api.platform.observability.smart_logger import SmartLogger
                SmartLogger.log(
                    "ERROR",
                    "Failed to execute aggregate creation query",
                    category="ingestion.neo4j.aggregates.create",
                    params={
                        "key": key,
                        "name": name,
                        "bc_id": bc_id,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
                raise
            # Ensure enumerations and valueObjects are always present (even if empty)
            if "enumerations" not in agg_dict:
                agg_dict["enumerations"] = []
            if "valueObjects" not in agg_dict:
                agg_dict["valueObjects"] = []
            return agg_dict

    def link_user_story_to_aggregate(self, user_story_id: str, aggregate_id: str, confidence: float = 0.9) -> bool:
        """Link a user story to an aggregate via IMPLEMENTS relationship."""
        query = """
        MATCH (us:UserStory {id: $user_story_id})
        MATCH (agg:Aggregate {id: $aggregate_id})
        MERGE (us)-[r:IMPLEMENTS]->(agg)
        SET r.confidence = $confidence,
            r.createdAt = datetime()
        RETURN us.id, agg.id
        """
        with self.session() as session:
            result = session.run(query, user_story_id=user_story_id, aggregate_id=aggregate_id, confidence=confidence)
            return result.single() is not None

    def link_user_story_to_command(self, user_story_id: str, command_id: str, confidence: float = 0.9) -> bool:
        """Link a user story to a command via IMPLEMENTS relationship."""
        query = """
        MATCH (us:UserStory {id: $user_story_id})
        MATCH (cmd:Command {id: $command_id})
        MERGE (us)-[r:IMPLEMENTS]->(cmd)
        SET r.confidence = $confidence,
            r.createdAt = datetime()
        RETURN us.id, cmd.id
        """
        with self.session() as session:
            result = session.run(query, user_story_id=user_story_id, command_id=command_id, confidence=confidence)
            return result.single() is not None

    def link_user_story_to_event(self, user_story_id: str, event_id: str, confidence: float = 0.9) -> bool:
        """Link a user story to an event via IMPLEMENTS relationship."""
        query = """
        MATCH (us:UserStory {id: $user_story_id})
        MATCH (evt:Event {id: $event_id})
        MERGE (us)-[r:IMPLEMENTS]->(evt)
        SET r.confidence = $confidence,
            r.createdAt = datetime()
        RETURN us.id, evt.id
        """
        with self.session() as session:
            result = session.run(query, user_story_id=user_story_id, event_id=event_id, confidence=confidence)
            return result.single() is not None

    def update_aggregate_enumerations_and_value_objects(
        self,
        aggregate_id: str,
        enumerations: list[dict[str, Any]] | None = None,
        value_objects: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Update enumerations and valueObjects for an existing aggregate."""
        query = """
        MATCH (agg:Aggregate {id: $aggregate_id})
        SET agg.enumerations = $enumerations_json,
            agg.valueObjects = $value_objects_json,
            agg.updatedAt = datetime()
        RETURN {
            id: agg.id,
            name: agg.name,
            rootEntity: agg.rootEntity,
            invariants: agg.invariants,
            enumerations: agg.enumerations,
            valueObjects: agg.valueObjects
        } as aggregate
        LIMIT 1
        """
        with self.session() as session:
            # Convert enumerations and value_objects to JSON-serializable format
            enum_list = []
            if enumerations:
                for enum in enumerations:
                    if isinstance(enum, dict):
                        enum_name = enum.get("name")
                        if enum_name:  # Only add if name exists
                            enum_list.append({
                                "name": str(enum_name),
                                "alias": enum.get("alias"),
                                "items": enum.get("items", [])
                            })
                    else:
                        # Handle Pydantic model
                        enum_name = getattr(enum, "name", None)
                        if enum_name:  # Only add if name exists
                            enum_list.append({
                                "name": str(enum_name),
                                "alias": getattr(enum, "alias", None),
                                "items": getattr(enum, "items", []) or []
                            })
            
            vo_list = []
            if value_objects:
                for vo in value_objects:
                    if isinstance(vo, dict):
                        vo_name = vo.get("name")
                        if vo_name:  # Only add if name exists
                            vo_list.append({
                                "name": str(vo_name),
                                "alias": vo.get("alias"),
                                "referencedAggregateName": vo.get("referenced_aggregate_name") or vo.get("referencedAggregateName"),
                                "referencedAggregateField": vo.get("referenced_aggregate_field") or vo.get("referencedAggregateField"),
                                "fields": vo.get("fields", [])
                            })
                    else:
                        # Handle Pydantic model
                        vo_name = getattr(vo, "name", None)
                        if vo_name:  # Only add if name exists
                            vo_list.append({
                                "name": str(vo_name),
                                "alias": getattr(vo, "alias", None),
                                "referencedAggregateName": getattr(vo, "referenced_aggregate_name", None) or getattr(vo, "referencedAggregateName", None),
                                "referencedAggregateField": getattr(vo, "referenced_aggregate_field", None) or getattr(vo, "referencedAggregateField", None),
                                "fields": getattr(vo, "fields", []) or []
                            })
            
            # Convert to JSON strings for Neo4j storage
            enumerations_json = json.dumps(enum_list) if enum_list else "[]"
            value_objects_json = json.dumps(vo_list) if vo_list else "[]"
            
            try:
                result = session.run(
                    query,
                    aggregate_id=aggregate_id,
                    enumerations_json=enumerations_json,
                    value_objects_json=value_objects_json,
                )
                record = result.single()
                if not record:
                    raise ValueError(f"Aggregate {aggregate_id} not found")
                agg_dict = dict(record["aggregate"])
                
                # Parse JSON strings back to lists for return value
                if isinstance(agg_dict.get("enumerations"), str):
                    agg_dict["enumerations"] = json.loads(agg_dict["enumerations"])
                if isinstance(agg_dict.get("valueObjects"), str):
                    agg_dict["valueObjects"] = json.loads(agg_dict["valueObjects"])
            except Exception as e:
                from api.platform.observability.smart_logger import SmartLogger
                SmartLogger.log(
                    "ERROR",
                    "Failed to update aggregate enumerations and value objects",
                    category="ingestion.neo4j.aggregates.update",
                    params={
                        "aggregate_id": aggregate_id,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
                raise
            
            # Ensure enumerations and valueObjects are always present (even if empty)
            if "enumerations" not in agg_dict:
                agg_dict["enumerations"] = []
            if "valueObjects" not in agg_dict:
                agg_dict["valueObjects"] = []
            return agg_dict


