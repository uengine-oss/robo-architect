from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from starlette.requests import Request

from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter(tags=["readmodel-cqrs"])


class CQRSOperationCreate(BaseModel):
    operation_type: str  # "INSERT", "UPDATE", "DELETE"
    trigger_event_id: str


class CQRSMappingCreate(BaseModel):
    target_property_id: str
    source_property_id: Optional[str] = None
    source_type: str = "event"  # "event" or "value"
    static_value: Optional[str] = None


class CQRSWhereCreate(BaseModel):
    target_property_id: str
    source_event_field_id: str
    operator: str = "="


@router.get("/api/readmodel/{readmodel_id}/cqrs")
async def get_cqrs_config(readmodel_id: str, request: Request) -> dict[str, Any]:
    """
    Get the full CQRS configuration for a ReadModel.
    Includes operations, mappings, and where conditions (when present).
    """
    query = """
    MATCH (rm:ReadModel {id: $readmodel_id})
    OPTIONAL MATCH (rm)-[:HAS_CQRS]->(cqrs:CQRSConfig)
    OPTIONAL MATCH (cqrs)-[:HAS_OPERATION]->(op:CQRSOperation)
    OPTIONAL MATCH (op)-[:TRIGGERED_BY]->(evt:Event)
    OPTIONAL MATCH (op)-[:HAS_MAPPING]->(m:CQRSMapping)
    OPTIONAL MATCH (m)-[:SOURCE]->(srcProp:Property)
    OPTIONAL MATCH (m)-[:TARGET]->(tgtProp:Property)
    OPTIONAL MATCH (op)-[:HAS_WHERE]->(w:CQRSWhere)
    OPTIONAL MATCH (w)-[:TARGET]->(whereTgtProp:Property)
    OPTIONAL MATCH (w)-[:SOURCE_EVENT_FIELD]->(whereSrcProp:Property)
    WITH cqrs, op, evt,
         collect(DISTINCT {
             id: m.id,
             sourceType: m.sourceType,
             staticValue: m.staticValue,
             sourcePropertyId: srcProp.id,
             sourcePropertyName: srcProp.name,
             targetPropertyId: tgtProp.id,
             targetPropertyName: tgtProp.name
         }) as mappings,
         collect(DISTINCT {
             id: w.id,
             operator: w.operator,
             targetPropertyId: whereTgtProp.id,
             targetPropertyName: whereTgtProp.name,
             sourceEventFieldId: whereSrcProp.id,
             sourceEventFieldName: whereSrcProp.name
         }) as whereConditions
    WITH cqrs, collect(DISTINCT {
        id: op.id,
        operationType: op.operationType,
        triggerEventId: evt.id,
        triggerEventName: evt.name,
        mappings: mappings,
        whereConditions: whereConditions
    }) as operations
    RETURN {
        id: cqrs.id,
        readmodelId: coalesce(cqrs.readmodelId, $readmodel_id),
        operations: operations
    } as config
    """

    SmartLogger.log(
        "INFO",
        "CQRS config requested.",
        category="api.readmodel.cqrs.get.request",
        params={**http_context(request), "inputs": {"readmodel_id": readmodel_id}},
    )

    with get_session() as session:
        # Ensure readmodel exists; if not, return 404 (matches UI expectation)
        exists = session.run("MATCH (rm:ReadModel {id: $id}) RETURN rm.id as id", id=readmodel_id).single()
        if not exists:
            raise HTTPException(status_code=404, detail=f"ReadModel {readmodel_id} not found")

        record = session.run(query, readmodel_id=readmodel_id).single()
        if not record or not record.get("config") or record["config"].get("id") is None:
            return {"id": None, "readmodelId": readmodel_id, "operations": []}

        config = dict(record["config"])
        ops = [op for op in (config.get("operations") or []) if op and op.get("id") is not None]
        for op in ops:
            op["mappings"] = [m for m in (op.get("mappings") or []) if m and m.get("id") is not None]
            op["whereConditions"] = [w for w in (op.get("whereConditions") or []) if w and w.get("id") is not None]
        config["operations"] = ops
        return config


@router.post("/api/readmodel/{readmodel_id}/cqrs")
async def create_cqrs_config(readmodel_id: str, request: Request) -> dict[str, Any]:
    """Create a CQRSConfig node and link it to the ReadModel (idempotent)."""
    cqrs_id = f"CQRS-{readmodel_id}"
    query = """
    MATCH (rm:ReadModel {id: $readmodel_id})
    MERGE (cqrs:CQRSConfig {id: $cqrs_id})
    SET cqrs.readmodelId = $readmodel_id
    MERGE (rm)-[:HAS_CQRS]->(cqrs)
    RETURN cqrs {.id, .readmodelId} as config
    """
    SmartLogger.log(
        "INFO",
        "CQRS config create requested.",
        category="api.readmodel.cqrs.create.request",
        params={**http_context(request), "inputs": {"readmodel_id": readmodel_id}},
    )
    with get_session() as session:
        record = session.run(query, readmodel_id=readmodel_id, cqrs_id=cqrs_id).single()
        if not record:
            raise HTTPException(status_code=404, detail=f"ReadModel {readmodel_id} not found")
        return dict(record["config"])


@router.delete("/api/readmodel/{readmodel_id}/cqrs")
async def delete_cqrs_config(readmodel_id: str, request: Request) -> dict[str, Any]:
    """Delete CQRSConfig and all operations/mappings/where conditions under it."""
    query = """
    MATCH (rm:ReadModel {id: $readmodel_id})-[:HAS_CQRS]->(cqrs:CQRSConfig)
    OPTIONAL MATCH (cqrs)-[:HAS_OPERATION]->(op:CQRSOperation)
    OPTIONAL MATCH (op)-[:HAS_MAPPING]->(m:CQRSMapping)
    OPTIONAL MATCH (op)-[:HAS_WHERE]->(w:CQRSWhere)
    DETACH DELETE cqrs, op, m, w
    RETURN count(cqrs) as deleted
    """
    SmartLogger.log(
        "INFO",
        "CQRS config delete requested.",
        category="api.readmodel.cqrs.delete.request",
        params={**http_context(request), "inputs": {"readmodel_id": readmodel_id}},
    )
    with get_session() as session:
        record = session.run(query, readmodel_id=readmodel_id).single()
        return {"success": bool(record and record["deleted"] > 0), "readmodelId": readmodel_id}


@router.get("/api/readmodel/{readmodel_id}/cqrs/events")
async def get_events_for_cqrs(readmodel_id: str, request: Request) -> list[dict[str, Any]]:
    """
    Get available events (with their properties) for CQRS trigger/mapping UI.
    """
    query = """
    MATCH (bc:BoundedContext)-[:HAS_AGGREGATE]->(agg:Aggregate)-[:HAS_COMMAND]->(cmd:Command)-[:EMITS]->(evt:Event)
    OPTIONAL MATCH (evt)-[:HAS_PROPERTY]->(prop:Property)
    WITH bc, evt, collect(DISTINCT prop {.id, .name, .type}) as properties
    RETURN {
        id: evt.id,
        name: evt.name,
        bcId: bc.id,
        bcName: bc.name,
        properties: properties
    } as event
    ORDER BY bc.name, evt.name
    """
    SmartLogger.log(
        "INFO",
        "CQRS events requested.",
        category="api.readmodel.cqrs.events.request",
        params={**http_context(request), "inputs": {"readmodel_id": readmodel_id}},
    )
    with get_session() as session:
        result = session.run(query)
        return [dict(r["event"]) for r in result]


@router.get("/api/readmodel/{readmodel_id}/properties")
async def get_readmodel_properties(readmodel_id: str, request: Request) -> list[dict[str, Any]]:
    """Get ReadModel properties for CQRS mapping UI."""
    query = """
    MATCH (rm:ReadModel {id: $readmodel_id})-[:HAS_PROPERTY]->(prop:Property)
    RETURN prop {.id, .name, .type, .isRequired} as property
    ORDER BY prop.name
    """
    SmartLogger.log(
        "INFO",
        "ReadModel properties requested.",
        category="api.readmodel.properties.request",
        params={**http_context(request), "inputs": {"readmodel_id": readmodel_id}},
    )
    with get_session() as session:
        result = session.run(query, readmodel_id=readmodel_id)
        return [dict(r["property"]) for r in result]


@router.post("/api/readmodel/{readmodel_id}/cqrs/operations")
async def create_cqrs_operation(readmodel_id: str, operation: CQRSOperationCreate, request: Request) -> dict[str, Any]:
    """Create a CQRS operation (ensures CQRSConfig exists)."""
    SmartLogger.log(
        "INFO",
        "CQRS operation create requested.",
        category="api.cqrs.operation.create.request",
        params={
            **http_context(request),
            "inputs": {"readmodel_id": readmodel_id, "operation_type": operation.operation_type, "trigger_event_id": operation.trigger_event_id},
        },
    )

    cqrs_id = f"CQRS-{readmodel_id}"
    op_id = f"CQRS-OP-{readmodel_id.replace('RM-', '')}-{operation.operation_type}-{operation.trigger_event_id.replace('EVT-', '')}"
    query = """
    MATCH (rm:ReadModel {id: $readmodel_id})
    MERGE (cqrs:CQRSConfig {id: $cqrs_id})
    SET cqrs.readmodelId = $readmodel_id
    MERGE (rm)-[:HAS_CQRS]->(cqrs)
    WITH cqrs
    MATCH (evt:Event {id: $trigger_event_id})
    MERGE (op:CQRSOperation {id: $op_id})
    SET op.operationType = $operation_type,
        op.cqrsConfigId = $cqrs_id,
        op.triggerEventId = $trigger_event_id
    MERGE (cqrs)-[:HAS_OPERATION]->(op)
    MERGE (op)-[:TRIGGERED_BY]->(evt)
    RETURN op {.id, .operationType, .cqrsConfigId, .triggerEventId} as operation
    """
    with get_session() as session:
        record = session.run(
            query,
            readmodel_id=readmodel_id,
            cqrs_id=cqrs_id,
            op_id=op_id,
            operation_type=operation.operation_type,
            trigger_event_id=operation.trigger_event_id,
        ).single()
        if not record:
            raise HTTPException(status_code=404, detail=f"ReadModel {readmodel_id} not found")
        return dict(record["operation"])


@router.delete("/api/cqrs/operation/{operation_id}")
async def delete_cqrs_operation(operation_id: str, request: Request) -> dict[str, Any]:
    query = """
    MATCH (op:CQRSOperation {id: $operation_id})
    OPTIONAL MATCH (op)-[:HAS_MAPPING]->(m:CQRSMapping)
    OPTIONAL MATCH (op)-[:HAS_WHERE]->(w:CQRSWhere)
    DETACH DELETE op, m, w
    RETURN count(op) as deleted
    """
    SmartLogger.log(
        "INFO",
        "CQRS operation delete requested.",
        category="api.cqrs.operation.delete.request",
        params={**http_context(request), "inputs": {"operation_id": operation_id}},
    )
    with get_session() as session:
        record = session.run(query, operation_id=operation_id).single()
        return {"success": bool(record and record["deleted"] > 0), "operationId": operation_id}


@router.post("/api/cqrs/operation/{operation_id}/mappings")
async def create_cqrs_mapping(operation_id: str, mapping: CQRSMappingCreate, request: Request) -> dict[str, Any]:
    SmartLogger.log(
        "INFO",
        "CQRS mapping create requested.",
        category="api.cqrs.mapping.create.request",
        params={**http_context(request), "inputs": {"operation_id": operation_id, "source_type": mapping.source_type}},
    )
    import uuid

    mapping_id = f"CQRS-MAP-{uuid.uuid4().hex[:8]}"

    if mapping.source_type == "event" and mapping.source_property_id:
        query = """
        MATCH (op:CQRSOperation {id: $operation_id})
        MATCH (srcProp:Property {id: $source_property_id})
        MATCH (tgtProp:Property {id: $target_property_id})
        MERGE (m:CQRSMapping {id: $mapping_id})
        SET m.operationId = $operation_id,
            m.sourceType = $source_type,
            m.staticValue = null
        MERGE (op)-[:HAS_MAPPING]->(m)
        MERGE (m)-[:SOURCE]->(srcProp)
        MERGE (m)-[:TARGET]->(tgtProp)
        RETURN m {.id, .operationId, .sourceType} as mapping
        """
        params = {
            "operation_id": operation_id,
            "mapping_id": mapping_id,
            "source_property_id": mapping.source_property_id,
            "target_property_id": mapping.target_property_id,
            "source_type": mapping.source_type,
        }
    else:
        query = """
        MATCH (op:CQRSOperation {id: $operation_id})
        MATCH (tgtProp:Property {id: $target_property_id})
        MERGE (m:CQRSMapping {id: $mapping_id})
        SET m.operationId = $operation_id,
            m.sourceType = $source_type,
            m.staticValue = $static_value
        MERGE (op)-[:HAS_MAPPING]->(m)
        MERGE (m)-[:TARGET]->(tgtProp)
        RETURN m {.id, .operationId, .sourceType, .staticValue} as mapping
        """
        params = {
            "operation_id": operation_id,
            "mapping_id": mapping_id,
            "target_property_id": mapping.target_property_id,
            "source_type": mapping.source_type,
            "static_value": mapping.static_value,
        }

    with get_session() as session:
        record = session.run(query, **params).single()
        if not record:
            raise HTTPException(status_code=404, detail="Operation or property not found")
        return dict(record["mapping"])


@router.delete("/api/cqrs/mapping/{mapping_id}")
async def delete_cqrs_mapping(mapping_id: str, request: Request) -> dict[str, Any]:
    query = """
    MATCH (m:CQRSMapping {id: $mapping_id})
    DETACH DELETE m
    RETURN count(m) as deleted
    """
    SmartLogger.log(
        "INFO",
        "CQRS mapping delete requested.",
        category="api.cqrs.mapping.delete.request",
        params={**http_context(request), "inputs": {"mapping_id": mapping_id}},
    )
    with get_session() as session:
        record = session.run(query, mapping_id=mapping_id).single()
        return {"success": bool(record and record["deleted"] > 0), "mappingId": mapping_id}


@router.post("/api/cqrs/operation/{operation_id}/where")
async def create_cqrs_where(operation_id: str, where: CQRSWhereCreate, request: Request) -> dict[str, Any]:
    import uuid

    where_id = f"CQRS-WHERE-{uuid.uuid4().hex[:8]}"
    query = """
    MATCH (op:CQRSOperation {id: $operation_id})
    MATCH (tgtProp:Property {id: $target_property_id})
    MATCH (srcProp:Property {id: $source_event_field_id})
    MERGE (w:CQRSWhere {id: $where_id})
    SET w.operationId = $operation_id,
        w.operator = $operator
    MERGE (op)-[:HAS_WHERE]->(w)
    MERGE (w)-[:TARGET]->(tgtProp)
    MERGE (w)-[:SOURCE_EVENT_FIELD]->(srcProp)
    RETURN w {.id, .operationId, .operator} as whereCondition
    """
    SmartLogger.log(
        "INFO",
        "CQRS where create requested.",
        category="api.cqrs.where.create.request",
        params={**http_context(request), "inputs": {"operation_id": operation_id}},
    )
    with get_session() as session:
        record = session.run(
            query,
            operation_id=operation_id,
            where_id=where_id,
            target_property_id=where.target_property_id,
            source_event_field_id=where.source_event_field_id,
            operator=where.operator,
        ).single()
        if not record:
            raise HTTPException(status_code=404, detail="Operation or property not found")
        return dict(record["whereCondition"])


@router.delete("/api/cqrs/where/{where_id}")
async def delete_cqrs_where(where_id: str, request: Request) -> dict[str, Any]:
    query = """
    MATCH (w:CQRSWhere {id: $where_id})
    DETACH DELETE w
    RETURN count(w) as deleted
    """
    SmartLogger.log(
        "INFO",
        "CQRS where delete requested.",
        category="api.cqrs.where.delete.request",
        params={**http_context(request), "inputs": {"where_id": where_id}},
    )
    with get_session() as session:
        record = session.run(query, where_id=where_id).single()
        return {"success": bool(record and record["deleted"] > 0), "whereId": where_id}


