from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter
from starlette.requests import Request

from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


def _parse_aggregate_fields(agg_dict: dict[str, Any]) -> None:
    """
    Parse JSON strings for enumerations and valueObjects in an Aggregate node dict.
    Modifies the dict in place.
    """
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


def _to_jsonable(value: Any, _seen: set[int] | None = None) -> Any:
    """
    Convert values returned from Neo4j (including neo4j.time.* temporals) into JSON-safe
    primitives.
    """
    # Fast path: JSON primitives
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if _seen is None:
        _seen = set()

    # Avoid potential recursion loops
    obj_id = id(value)
    if obj_id in _seen:
        return str(value)
    _seen.add(obj_id)

    # Containers
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v, _seen) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v, _seen) for v in value]

    # Python datetime-like
    try:
        import datetime as _dt
        if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
            return value.isoformat()
    except Exception:
        pass

    # Neo4j temporal types (neo4j.time.DateTime, Date, Time, Duration, etc.)
    iso_format = getattr(value, "iso_format", None)
    if callable(iso_format):
        try:
            return iso_format()
        except Exception:
            pass

    to_native = getattr(value, "to_native", None)
    if callable(to_native):
        try:
            native = to_native()
            iso = getattr(native, "isoformat", None)
            return iso() if callable(iso) else str(native)
        except Exception:
            pass

    # Fallback: stringify unknown values rather than failing serialization.
    return str(value)


def _dedupe_relationships(relationships: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique_rels: list[dict[str, Any]] = []
    seen_rels: set[tuple[str, str, str]] = set()
    for rel in relationships:
        if rel.get("source") and rel.get("target"):
            key = (rel["source"], rel["target"], rel["type"])
            if key not in seen_rels:
                seen_rels.add(key)
                unique_rels.append(rel)
    return unique_rels


@router.get("/event-triggers/{event_id}")
async def get_event_triggers(event_id: str, request: Request) -> dict[str, Any]:
    """
    Get all Policies triggered by an Event, along with their parent BCs and ALL related nodes.
    Used when double-clicking an Event on canvas to expand triggered policies.
    This fetches complete BCs with all their Aggregates, Commands, Events, and Policies.
    """
    # First, find all BCs that contain policies triggered by this event
    bc_query = """
    MATCH (evt:Event {id: $event_id})-[:TRIGGERS]->(pol:Policy)<-[:HAS_POLICY]-(bc:BoundedContext)
    RETURN DISTINCT bc.id as bcId
    """

    with get_session() as session:
        SmartLogger.log(
            "INFO",
            "Event triggers requested: expanding policies triggered by this event (incl. BC context).",
            category="api.graph.event_triggers.request",
            params={**http_context(request), "inputs": {"event_id": event_id}},
        )
        
        # Get all BC IDs
        bc_result = session.run(bc_query, event_id=event_id)
        bc_ids = [record["bcId"] for record in bc_result if record["bcId"]]
        
        if not bc_ids:
            return {"sourceEventId": event_id, "nodes": [], "relationships": []}
        
        nodes: list[dict[str, Any]] = []
        relationships: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        
        # For each BC, fetch ALL its contents (like expand-with-bc does)
        for bc_id in bc_ids:
            # Get BC node
            bc_node_query = """
            MATCH (bc:BoundedContext {id: $bc_id})
            RETURN bc
            """
            bc_node_result = session.run(bc_node_query, bc_id=bc_id)
            bc_record = bc_node_result.single()
            if bc_record and bc_record["bc"] and bc_record["bc"]["id"] not in seen_ids:
                bc = _to_jsonable(dict(bc_record["bc"]))
                bc["type"] = "BoundedContext"
                nodes.append(bc)
                seen_ids.add(bc["id"])
            
            # Get all Aggregates and their Commands/Events
            agg_query = """
            MATCH (bc:BoundedContext {id: $bc_id})-[:HAS_AGGREGATE]->(agg:Aggregate)
            OPTIONAL MATCH (agg)-[:HAS_COMMAND]->(cmd:Command)
            OPTIONAL MATCH (cmd)-[:EMITS]->(evt:Event)
            RETURN agg, cmd, evt
            """
            agg_result = session.run(agg_query, bc_id=bc_id)
            
            for record in agg_result:
                if record["agg"] and record["agg"]["id"] not in seen_ids:
                    agg = _to_jsonable(dict(record["agg"]))
                    agg["type"] = "Aggregate"
                    agg["bcId"] = bc_id
                    _parse_aggregate_fields(agg)
                    nodes.append(agg)
                    seen_ids.add(agg["id"])
                    relationships.append({"source": bc_id, "target": agg["id"], "type": "HAS_AGGREGATE"})
                
                if record["cmd"] and record["cmd"]["id"] not in seen_ids:
                    cmd = _to_jsonable(dict(record["cmd"]))
                    cmd["type"] = "Command"
                    cmd["bcId"] = bc_id
                    if record["agg"]:
                        cmd["parentId"] = record["agg"]["id"]
                    nodes.append(cmd)
                    seen_ids.add(cmd["id"])
                    if record["agg"]:
                        relationships.append({"source": record["agg"]["id"], "target": cmd["id"], "type": "HAS_COMMAND"})
                
                if record["evt"] and record["evt"]["id"] not in seen_ids:
                    evt = _to_jsonable(dict(record["evt"]))
                    evt["type"] = "Event"
                    evt["bcId"] = bc_id
                    nodes.append(evt)
                    seen_ids.add(evt["id"])
                    if record["cmd"]:
                        relationships.append({"source": record["cmd"]["id"], "target": evt["id"], "type": "EMITS"})
            
            # Get all Policies (including those triggered by the event)
            pol_query = """
            MATCH (bc:BoundedContext {id: $bc_id})-[:HAS_POLICY]->(pol:Policy)
            OPTIONAL MATCH (triggerEvt:Event)-[:TRIGGERS]->(pol)
            OPTIONAL MATCH (pol)-[:INVOKES]->(invokedCmd:Command)
            RETURN pol, triggerEvt.id as triggerEventId, invokedCmd.id as invokeCommandId
            """
            pol_result = session.run(pol_query, bc_id=bc_id)
            
            for record in pol_result:
                if record["pol"] and record["pol"]["id"] not in seen_ids:
                    pol = _to_jsonable(dict(record["pol"]))
                    pol["type"] = "Policy"
                    pol["bcId"] = bc_id
                    if record["invokeCommandId"]:
                        pol["invokeCommandId"] = record["invokeCommandId"]
                    nodes.append(pol)
                    seen_ids.add(pol["id"])
                    relationships.append({"source": bc_id, "target": pol["id"], "type": "HAS_POLICY"})
                    
                    # Add TRIGGERS relationship if this policy is triggered by the source event
                    if record["triggerEventId"] == event_id:
                        relationships.append({"source": event_id, "target": pol["id"], "type": "TRIGGERS"})
                    
                    # Add INVOKES relationship if policy invokes a command
                    if record["invokeCommandId"]:
                        relationships.append({"source": pol["id"], "target": record["invokeCommandId"], "type": "INVOKES"})
            
            # UI wireframes in this BC
            ui_query = """
            MATCH (bc:BoundedContext {id: $bc_id})-[:HAS_UI]->(ui:UI)
            RETURN ui
            """
            ui_result = session.run(ui_query, bc_id=bc_id)
            for record in ui_result:
                if record["ui"] and record["ui"]["id"] not in seen_ids:
                    ui = _to_jsonable(dict(record["ui"]))
                    ui["type"] = "UI"
                    ui["bcId"] = bc_id
                    nodes.append(ui)
                    seen_ids.add(ui["id"])
                    relationships.append({"source": bc_id, "target": ui["id"], "type": "HAS_UI"})
                    if ui.get("attachedToId"):
                        relationships.append({"source": ui["id"], "target": ui["attachedToId"], "type": "ATTACHED_TO"})
            
            # ReadModels in this BC
            rm_query = """
            MATCH (bc:BoundedContext {id: $bc_id})-[:HAS_READMODEL]->(rm:ReadModel)
            RETURN rm
            """
            rm_result = session.run(rm_query, bc_id=bc_id)
            for record in rm_result:
                if record["rm"] and record["rm"]["id"] not in seen_ids:
                    rm = _to_jsonable(dict(record["rm"]))
                    rm["type"] = "ReadModel"
                    rm["bcId"] = bc_id
                    nodes.append(rm)
                    seen_ids.add(rm["id"])
                    relationships.append({"source": bc_id, "target": rm["id"], "type": "HAS_READMODEL"})

        return {"sourceEventId": event_id, "nodes": nodes, "relationships": _dedupe_relationships(relationships)}


