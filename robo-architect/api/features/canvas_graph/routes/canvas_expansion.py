from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
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


def _to_jsonable(value: Any, _seen: set[int] | None = None) -> Any:
    """
    Convert values returned from Neo4j (including neo4j.time.* temporals) into JSON-safe
    primitives. This is intentionally local and only used by the expand-with-bc endpoint
    to keep scope minimal.
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
        import datetime as _dt  # local import to avoid widening module imports unnecessarily

        if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
            return value.isoformat()
    except Exception:
        # If datetime isn't usable for any reason, continue with other strategies.
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


@router.get("/expand/{node_id}")
async def expand_node(node_id: str, request: Request) -> dict[str, Any]:
    """
    Expand a node to get its connected nodes based on type.
    - BoundedContext → All Aggregates + Policies
    - Aggregate → All Commands + Events
    - Command → Events it emits
    - Event → Policies it triggers
    - Policy → Commands it invokes
    """

    type_query = """
    MATCH (n {id: $node_id})
    RETURN labels(n)[0] as nodeType, n as node
    """

    with get_session() as session:
        SmartLogger.log(
            "INFO",
            "Expand requested: expanding connected nodes by node type.",
            category="api.graph.expand.request",
            params={**http_context(request), "inputs": {"node_id": node_id}},
        )
        type_result = session.run(type_query, node_id=node_id)
        type_record = type_result.single()

        if not type_record:
            SmartLogger.log(
                "WARNING",
                "Expand aborted: node_id not found.",
                category="api.graph.expand.not_found",
                params={**http_context(request), "inputs": {"node_id": node_id}},
            )
            raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

        node_type = type_record["nodeType"]
        main_node = dict(type_record["node"])
        main_node["type"] = node_type
        SmartLogger.log(
            "INFO",
            "Expand node type resolved: determining expansion strategy.",
            category="api.graph.expand.node_type",
            params={**http_context(request), "inputs": {"node_id": node_id}, "nodeType": node_type},
        )

        nodes = [main_node]
        relationships: list[dict[str, Any]] = []

        if node_type == "BoundedContext":
            agg_query = """
            MATCH (bc:BoundedContext {id: $node_id})-[r:HAS_AGGREGATE]->(agg:Aggregate)
            OPTIONAL MATCH (agg)-[r2:HAS_COMMAND]->(cmd:Command)
            OPTIONAL MATCH (cmd)-[r3:EMITS]->(evt:Event)
            RETURN agg, cmd, evt,
                   {source: bc.id, target: agg.id, type: 'HAS_AGGREGATE'} as rel1,
                   {source: agg.id, target: cmd.id, type: 'HAS_COMMAND'} as rel2,
                   {source: cmd.id, target: evt.id, type: 'EMITS'} as rel3
            """
            agg_result = session.run(agg_query, node_id=node_id)
            seen_ids = {node_id}

            for record in agg_result:
                if record["agg"] and record["agg"]["id"] not in seen_ids:
                    agg = dict(record["agg"])
                    agg["type"] = "Aggregate"
                    nodes.append(agg)
                    seen_ids.add(agg["id"])
                    if record["rel1"]["target"]:
                        relationships.append(dict(record["rel1"]))

                if record["cmd"] and record["cmd"]["id"] not in seen_ids:
                    cmd = dict(record["cmd"])
                    cmd["type"] = "Command"
                    # Include parentId (Aggregate ID) for frontend layout (Aggregate height spans its Commands)
                    if record["agg"]:
                        cmd["parentId"] = record["agg"]["id"]
                    nodes.append(cmd)
                    seen_ids.add(cmd["id"])
                    if record["rel2"]["target"]:
                        relationships.append(dict(record["rel2"]))

                if record["evt"] and record["evt"]["id"] not in seen_ids:
                    evt = dict(record["evt"])
                    evt["type"] = "Event"
                    nodes.append(evt)
                    seen_ids.add(evt["id"])
                    if record["rel3"]["target"]:
                        relationships.append(dict(record["rel3"]))

            pol_query = """
            MATCH (bc:BoundedContext {id: $node_id})-[:HAS_POLICY]->(pol:Policy)
            OPTIONAL MATCH (evt:Event)-[r:TRIGGERS]->(pol)
            OPTIONAL MATCH (pol)-[r2:INVOKES]->(cmd:Command)
            RETURN pol, evt.id as triggerEventId, cmd.id as invokeCommandId
            """
            pol_result = session.run(pol_query, node_id=node_id)
            for record in pol_result:
                if record["pol"] and record["pol"]["id"] not in seen_ids:
                    pol = dict(record["pol"])
                    pol["type"] = "Policy"
                    # Include invokeCommandId for frontend layout (place Policy left of Command)
                    if record["invokeCommandId"]:
                        pol["invokeCommandId"] = record["invokeCommandId"]
                    nodes.append(pol)
                    seen_ids.add(pol["id"])

                    if record["triggerEventId"]:
                        relationships.append({"source": record["triggerEventId"], "target": pol["id"], "type": "TRIGGERS"})
                    if record["invokeCommandId"]:
                        relationships.append({"source": pol["id"], "target": record["invokeCommandId"], "type": "INVOKES"})

        elif node_type == "Aggregate":
            expand_query = """
            MATCH (agg:Aggregate {id: $node_id})-[:HAS_COMMAND]->(cmd:Command)
            OPTIONAL MATCH (cmd)-[:EMITS]->(evt:Event)
            RETURN cmd, evt
            """
            expand_result = session.run(expand_query, node_id=node_id)
            seen_ids = {node_id}

            for record in expand_result:
                if record["cmd"] and record["cmd"]["id"] not in seen_ids:
                    cmd = dict(record["cmd"])
                    cmd["type"] = "Command"
                    # Include parentId (Aggregate ID) for frontend layout (Aggregate height spans its Commands)
                    cmd["parentId"] = node_id
                    nodes.append(cmd)
                    seen_ids.add(cmd["id"])
                    relationships.append({"source": node_id, "target": cmd["id"], "type": "HAS_COMMAND"})

                if record["evt"] and record["evt"]["id"] not in seen_ids:
                    evt = dict(record["evt"])
                    evt["type"] = "Event"
                    nodes.append(evt)
                    seen_ids.add(evt["id"])
                    relationships.append({"source": record["cmd"]["id"], "target": evt["id"], "type": "EMITS"})

        elif node_type == "Command":
            expand_query = """
            MATCH (cmd:Command {id: $node_id})-[:EMITS]->(evt:Event)
            RETURN evt
            """
            expand_result = session.run(expand_query, node_id=node_id)

            for record in expand_result:
                if record["evt"]:
                    evt = dict(record["evt"])
                    evt["type"] = "Event"
                    nodes.append(evt)
                    relationships.append({"source": node_id, "target": evt["id"], "type": "EMITS"})

        elif node_type == "Event":
            expand_query = """
            MATCH (evt:Event {id: $node_id})-[:TRIGGERS]->(pol:Policy)
            OPTIONAL MATCH (pol)-[:INVOKES]->(cmd:Command)
            RETURN pol, cmd
            """
            expand_result = session.run(expand_query, node_id=node_id)
            seen_ids = {node_id}

            for record in expand_result:
                if record["pol"] and record["pol"]["id"] not in seen_ids:
                    pol = dict(record["pol"])
                    pol["type"] = "Policy"
                    # Include invokeCommandId for frontend layout (place Policy left of Command)
                    if record["cmd"]:
                        pol["invokeCommandId"] = record["cmd"]["id"]
                    nodes.append(pol)
                    seen_ids.add(pol["id"])
                    relationships.append({"source": node_id, "target": pol["id"], "type": "TRIGGERS"})

                if record["cmd"] and record["cmd"]["id"] not in seen_ids:
                    cmd = dict(record["cmd"])
                    cmd["type"] = "Command"
                    nodes.append(cmd)
                    seen_ids.add(cmd["id"])
                    relationships.append({"source": record["pol"]["id"], "target": cmd["id"], "type": "INVOKES"})

        elif node_type == "Policy":
            expand_query = """
            MATCH (pol:Policy {id: $node_id})-[:INVOKES]->(cmd:Command)
            RETURN cmd
            """
            expand_result = session.run(expand_query, node_id=node_id)

            for record in expand_result:
                if record["cmd"]:
                    cmd = dict(record["cmd"])
                    cmd["type"] = "Command"
                    nodes.append(cmd)
                    relationships.append({"source": node_id, "target": cmd["id"], "type": "INVOKES"})

        return {"nodes": nodes, "relationships": _dedupe_relationships(relationships)}


@router.get("/node-context/{node_id}")
async def get_node_context(node_id: str, request: Request) -> dict[str, Any]:
    """
    Get the BoundedContext that contains a given node.
    Returns BC info so nodes can be properly grouped.
    """
    query = """
    MATCH (n {id: $node_id})
    OPTIONAL MATCH (bc:BoundedContext)-[:HAS_AGGREGATE|HAS_POLICY*1..2]->(n)
    OPTIONAL MATCH (bc2:BoundedContext)-[:HAS_AGGREGATE]->(agg:Aggregate)-[:HAS_COMMAND]->(n)
    OPTIONAL MATCH (bc3:BoundedContext)-[:HAS_AGGREGATE]->(agg2:Aggregate)-[:HAS_COMMAND]->(cmd:Command)-[:EMITS]->(n)
    OPTIONAL MATCH (bc4:BoundedContext)-[:HAS_UI]->(n)
    OPTIONAL MATCH (bc5:BoundedContext)-[:HAS_READMODEL]->(n)
    WITH n, coalesce(bc, bc2, bc3, bc4, bc5) as context
    RETURN {
        nodeId: n.id,
        nodeType: labels(n)[0],
        bcId: context.id,
        bcName: context.name,
        bcDescription: context.description
    } as result
    """

    with get_session() as session:
        SmartLogger.log(
            "INFO",
            "Node context requested: resolving parent BC for node.",
            category="api.graph.node_context.request",
            params={**http_context(request), "inputs": {"node_id": node_id}},
        )
        result = session.run(query, node_id=node_id)
        record = result.single()

        if not record:
            SmartLogger.log(
                "WARNING",
                "Node context not found: node_id missing or BC could not be resolved.",
                category="api.graph.node_context.not_found",
                params={**http_context(request), "inputs": {"node_id": node_id}},
            )
            return {"nodeId": node_id, "bcId": None}

        payload = dict(record["result"])
        SmartLogger.log(
            "INFO",
            "Node context returned.",
            category="api.graph.node_context.done",
            params={**http_context(request), "result": payload},
        )
        return payload


@router.get("/expand-with-bc/{node_id}")
async def expand_node_with_bc(node_id: str, request: Request) -> dict[str, Any]:
    """
    Expand a node and include its parent BoundedContext.
    This ensures nodes are always displayed within their BC container.
    """
    context_query = """
    MATCH (n {id: $node_id})
    WITH n, labels(n)[0] as nodeType

    // Find parent BC based on node type
    OPTIONAL MATCH (bc1:BoundedContext {id: $node_id})
    OPTIONAL MATCH (bc2:BoundedContext)-[:HAS_AGGREGATE]->(n)
    OPTIONAL MATCH (bc3:BoundedContext)-[:HAS_AGGREGATE]->(agg:Aggregate)-[:HAS_COMMAND]->(n)
    OPTIONAL MATCH (bc4:BoundedContext)-[:HAS_AGGREGATE]->(agg2:Aggregate)-[:HAS_COMMAND]->(cmd:Command)-[:EMITS]->(n)
    OPTIONAL MATCH (bc5:BoundedContext)-[:HAS_POLICY]->(n)
    OPTIONAL MATCH (bc6:BoundedContext)-[:HAS_UI]->(n)
    OPTIONAL MATCH (bc7:BoundedContext)-[:HAS_READMODEL]->(n)

    WITH n, nodeType, coalesce(bc1, bc2, bc3, bc4, bc5, bc6, bc7) as bc
    RETURN n, nodeType, bc
    """

    with get_session() as session:
        SmartLogger.log(
            "INFO",
            "Expand-with-BC requested: expanding node and including its parent BC for grouping.",
            category="api.graph.expand_with_bc.request",
            params={**http_context(request), "inputs": {"node_id": node_id}},
        )
        ctx_result = session.run(context_query, node_id=node_id)
        ctx_record = ctx_result.single()

        if not ctx_record:
            SmartLogger.log(
                "WARNING",
                "Expand-with-BC aborted: node_id not found.",
                category="api.graph.expand_with_bc.not_found",
                params={**http_context(request), "inputs": {"node_id": node_id}},
            )
            raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

        node_type = ctx_record["nodeType"]
        bc = ctx_record["bc"]
        main_node = dict(ctx_record["n"])
        main_node["type"] = node_type

        nodes: list[dict[str, Any]] = []
        relationships: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        if bc:
            bc_node = dict(bc)
            bc_node["type"] = "BoundedContext"
            nodes.append(bc_node)
            seen_ids.add(bc["id"])
            main_node["bcId"] = bc["id"]

        nodes.append(main_node)
        seen_ids.add(node_id)

        if node_type == "BoundedContext":
            expand_query = """
            MATCH (bc:BoundedContext {id: $node_id})-[:HAS_AGGREGATE]->(agg:Aggregate)
            OPTIONAL MATCH (agg)-[:HAS_COMMAND]->(cmd:Command)
            OPTIONAL MATCH (cmd)-[:EMITS]->(evt:Event)
            RETURN agg, cmd, evt
            """
            expand_result = session.run(expand_query, node_id=node_id)

            for record in expand_result:
                if record["agg"] and record["agg"]["id"] not in seen_ids:
                    agg = dict(record["agg"])
                    agg["type"] = "Aggregate"
                    agg["bcId"] = node_id
                    nodes.append(agg)
                    seen_ids.add(agg["id"])
                    relationships.append({"source": node_id, "target": agg["id"], "type": "HAS_AGGREGATE"})

                if record["cmd"] and record["cmd"]["id"] not in seen_ids:
                    cmd = dict(record["cmd"])
                    cmd["type"] = "Command"
                    cmd["bcId"] = node_id
                    # Include parentId (Aggregate ID) for frontend layout (Aggregate height spans its Commands)
                    if record["agg"]:
                        cmd["parentId"] = record["agg"]["id"]
                    nodes.append(cmd)
                    seen_ids.add(cmd["id"])
                    if record["agg"]:
                        relationships.append({"source": record["agg"]["id"], "target": cmd["id"], "type": "HAS_COMMAND"})

                if record["evt"] and record["evt"]["id"] not in seen_ids:
                    evt = dict(record["evt"])
                    evt["type"] = "Event"
                    evt["bcId"] = node_id
                    nodes.append(evt)
                    seen_ids.add(evt["id"])
                    if record["cmd"]:
                        relationships.append({"source": record["cmd"]["id"], "target": evt["id"], "type": "EMITS"})

            pol_query = """
            MATCH (bc:BoundedContext {id: $node_id})-[:HAS_POLICY]->(pol:Policy)
            OPTIONAL MATCH (evt:Event)-[:TRIGGERS]->(pol)
            OPTIONAL MATCH (pol)-[:INVOKES]->(cmd:Command)
            RETURN pol, evt.id as triggerEventId, cmd.id as invokeCommandId
            """
            pol_result = session.run(pol_query, node_id=node_id)

            for record in pol_result:
                if record["pol"] and record["pol"]["id"] not in seen_ids:
                    pol = dict(record["pol"])
                    pol["type"] = "Policy"
                    pol["bcId"] = node_id
                    # Include invokeCommandId for frontend layout (place Policy left of Command)
                    if record["invokeCommandId"]:
                        pol["invokeCommandId"] = record["invokeCommandId"]
                    nodes.append(pol)
                    seen_ids.add(pol["id"])

                    if record["triggerEventId"]:
                        relationships.append({"source": record["triggerEventId"], "target": pol["id"], "type": "TRIGGERS"})
                    if record["invokeCommandId"]:
                        relationships.append({"source": pol["id"], "target": record["invokeCommandId"], "type": "INVOKES"})

            # UI wireframes in this BC
            ui_query = """
            MATCH (bc:BoundedContext {id: $node_id})-[:HAS_UI]->(ui:UI)
            RETURN ui
            """
            ui_result = session.run(ui_query, node_id=node_id)
            for record in ui_result:
                if record["ui"] and record["ui"]["id"] not in seen_ids:
                    ui = dict(record["ui"])
                    ui["type"] = "UI"
                    ui["bcId"] = node_id
                    nodes.append(ui)
                    seen_ids.add(ui["id"])
                    relationships.append({"source": node_id, "target": ui["id"], "type": "HAS_UI"})
                    if ui.get("attachedToId"):
                        relationships.append({"source": ui["id"], "target": ui["attachedToId"], "type": "ATTACHED_TO"})

            # ReadModels in this BC
            rm_query = """
            MATCH (bc:BoundedContext {id: $node_id})-[:HAS_READMODEL]->(rm:ReadModel)
            OPTIONAL MATCH (rm)-[:HAS_PROPERTY]->(prop:Property)
            WITH rm, collect(prop {.id, .name, .type, .description, .isRequired}) as properties
            RETURN rm, properties
            """
            rm_result = session.run(rm_query, node_id=node_id)
            for record in rm_result:
                if record["rm"] and record["rm"]["id"] not in seen_ids:
                    rm = dict(record["rm"])
                    rm["type"] = "ReadModel"
                    rm["bcId"] = node_id
                    # Filter null properties
                    rm["properties"] = [p for p in (record["properties"] or []) if p and p.get("id")]
                    nodes.append(rm)
                    seen_ids.add(rm["id"])
                    relationships.append({"source": node_id, "target": rm["id"], "type": "HAS_READMODEL"})

        elif node_type == "Aggregate":
            bc_id = bc["id"] if bc else None
            expand_query = """
            MATCH (agg:Aggregate {id: $node_id})-[:HAS_COMMAND]->(cmd:Command)
            OPTIONAL MATCH (cmd)-[:EMITS]->(evt:Event)
            RETURN cmd, evt
            """
            expand_result = session.run(expand_query, node_id=node_id)

            for record in expand_result:
                if record["cmd"] and record["cmd"]["id"] not in seen_ids:
                    cmd = dict(record["cmd"])
                    cmd["type"] = "Command"
                    cmd["bcId"] = bc_id
                    nodes.append(cmd)
                    seen_ids.add(cmd["id"])
                    relationships.append({"source": node_id, "target": cmd["id"], "type": "HAS_COMMAND"})

                if record["evt"] and record["evt"]["id"] not in seen_ids:
                    evt = dict(record["evt"])
                    evt["type"] = "Event"
                    evt["bcId"] = bc_id
                    nodes.append(evt)
                    seen_ids.add(evt["id"])
                    relationships.append({"source": record["cmd"]["id"], "target": evt["id"], "type": "EMITS"})

            if bc_id:
                pol_query = """
                MATCH (bc:BoundedContext {id: $bc_id})-[:HAS_POLICY]->(pol:Policy)
                OPTIONAL MATCH (evt:Event)-[:TRIGGERS]->(pol)
                OPTIONAL MATCH (pol)-[:INVOKES]->(cmd:Command)
                RETURN pol, evt.id as triggerEventId, cmd.id as invokeCommandId
                """
                pol_result = session.run(pol_query, bc_id=bc_id)

                for record in pol_result:
                    if record["pol"] and record["pol"]["id"] not in seen_ids:
                        pol = dict(record["pol"])
                        pol["type"] = "Policy"
                        pol["bcId"] = bc_id
                        pol["triggerEventId"] = record["triggerEventId"]
                        pol["invokeCommandId"] = record["invokeCommandId"]
                        nodes.append(pol)
                        seen_ids.add(pol["id"])

                        if record["triggerEventId"]:
                            relationships.append({"source": record["triggerEventId"], "target": pol["id"], "type": "TRIGGERS"})
                        if record["invokeCommandId"]:
                            relationships.append({"source": pol["id"], "target": record["invokeCommandId"], "type": "INVOKES"})

        elif node_type == "Command":
            bc_id = bc["id"] if bc else None
            expand_query = """
            MATCH (cmd:Command {id: $node_id})-[:EMITS]->(evt:Event)
            RETURN evt
            """
            expand_result = session.run(expand_query, node_id=node_id)

            for record in expand_result:
                if record["evt"]:
                    evt = dict(record["evt"])
                    evt["type"] = "Event"
                    evt["bcId"] = bc_id
                    nodes.append(evt)
                    relationships.append({"source": node_id, "target": evt["id"], "type": "EMITS"})

        elif node_type == "Event":
            bc_id = bc["id"] if bc else None
            expand_query = """
            MATCH (evt:Event {id: $node_id})-[:TRIGGERS]->(pol:Policy)
            OPTIONAL MATCH (pol)-[:INVOKES]->(cmd:Command)
            OPTIONAL MATCH (polBc:BoundedContext)-[:HAS_POLICY]->(pol)
            RETURN pol, cmd, polBc
            """
            expand_result = session.run(expand_query, node_id=node_id)

            for record in expand_result:
                pol_bc_id = record["polBc"]["id"] if record["polBc"] else bc_id

                if record["pol"] and record["pol"]["id"] not in seen_ids:
                    pol = dict(record["pol"])
                    pol["type"] = "Policy"
                    pol["bcId"] = pol_bc_id
                    # Include invokeCommandId for frontend layout (place Policy left of Command)
                    if record["cmd"]:
                        pol["invokeCommandId"] = record["cmd"]["id"]
                    nodes.append(pol)
                    seen_ids.add(pol["id"])
                    relationships.append({"source": node_id, "target": pol["id"], "type": "TRIGGERS"})

                if record["cmd"] and record["cmd"]["id"] not in seen_ids:
                    cmd = dict(record["cmd"])
                    cmd["type"] = "Command"
                    cmd["bcId"] = pol_bc_id
                    nodes.append(cmd)
                    seen_ids.add(cmd["id"])
                    relationships.append({"source": record["pol"]["id"], "target": cmd["id"], "type": "INVOKES"})

        elif node_type == "Policy":
            bc_id = bc["id"] if bc else None
            expand_query = """
            MATCH (pol:Policy {id: $node_id})-[:INVOKES]->(cmd:Command)
            RETURN cmd
            """
            expand_result = session.run(expand_query, node_id=node_id)

            for record in expand_result:
                if record["cmd"]:
                    cmd = dict(record["cmd"])
                    cmd["type"] = "Command"
                    cmd["bcId"] = bc_id
                    nodes.append(cmd)
                    relationships.append({"source": node_id, "target": cmd["id"], "type": "INVOKES"})

        payload = {
            "nodes": nodes,
            "relationships": _dedupe_relationships(relationships),
            "bcContext": {"id": bc["id"], "name": bc["name"], "description": bc.get("description")} if bc else None,
        }
        return _to_jsonable(payload)

