from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from starlette.requests import Request

from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


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
    Get all Policies triggered by an Event, along with their parent BCs and related nodes.
    Used when double-clicking an Event on canvas to expand triggered policies.
    """
    query = """
    MATCH (evt:Event {id: $event_id})-[:TRIGGERS]->(pol:Policy)<-[:HAS_POLICY]-(bc:BoundedContext)
    OPTIONAL MATCH (pol)-[:INVOKES]->(cmd:Command)<-[:HAS_COMMAND]-(agg:Aggregate)<-[:HAS_AGGREGATE]-(bc)
    OPTIONAL MATCH (cmd)-[:EMITS]->(resultEvt:Event)
    RETURN DISTINCT bc, pol, cmd, agg, resultEvt
    """

    with get_session() as session:
        SmartLogger.log(
            "INFO",
            "Event triggers requested: expanding policies triggered by this event (incl. BC context).",
            category="api.graph.event_triggers.request",
            params={**http_context(request), "inputs": {"event_id": event_id}},
        )
        result = session.run(query, event_id=event_id)

        nodes: list[dict[str, Any]] = []
        relationships: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for record in result:
            if record["bc"] and record["bc"]["id"] not in seen_ids:
                bc = dict(record["bc"])
                bc["type"] = "BoundedContext"
                nodes.append(bc)
                seen_ids.add(bc["id"])

            bc_id = record["bc"]["id"] if record["bc"] else None

            if record["agg"] and record["agg"]["id"] not in seen_ids:
                agg = dict(record["agg"])
                agg["type"] = "Aggregate"
                agg["bcId"] = bc_id
                nodes.append(agg)
                seen_ids.add(agg["id"])

            if record["pol"] and record["pol"]["id"] not in seen_ids:
                pol = dict(record["pol"])
                pol["type"] = "Policy"
                pol["bcId"] = bc_id
                nodes.append(pol)
                seen_ids.add(pol["id"])
                relationships.append({"source": event_id, "target": pol["id"], "type": "TRIGGERS"})

            if record["cmd"] and record["cmd"]["id"] not in seen_ids:
                cmd = dict(record["cmd"])
                cmd["type"] = "Command"
                cmd["bcId"] = bc_id
                nodes.append(cmd)
                seen_ids.add(cmd["id"])

                if record["pol"]:
                    relationships.append({"source": record["pol"]["id"], "target": cmd["id"], "type": "INVOKES"})
                if record["agg"]:
                    relationships.append({"source": record["agg"]["id"], "target": cmd["id"], "type": "HAS_COMMAND"})

            if record["resultEvt"] and record["resultEvt"]["id"] not in seen_ids:
                evt = dict(record["resultEvt"])
                evt["type"] = "Event"
                evt["bcId"] = bc_id
                nodes.append(evt)
                seen_ids.add(evt["id"])

                if record["cmd"]:
                    relationships.append({"source": record["cmd"]["id"], "target": evt["id"], "type": "EMITS"})

        return {"sourceEventId": event_id, "nodes": nodes, "relationships": _dedupe_relationships(relationships)}


