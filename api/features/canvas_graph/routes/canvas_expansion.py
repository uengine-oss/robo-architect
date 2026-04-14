from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from starlette.requests import Request

import httpx

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


def _parse_gwt_bundle(gwt_node: dict[str, Any] | None) -> dict[str, Any] | None:
    """
    Convert a single (GWT) node payload into the frontend-compatible shape:
    - gwtSets: array of rows (test cases)
    - each row: given/when/then objects (mapped refs fixed; fieldValues per test case)
    """
    if not gwt_node or not isinstance(gwt_node, dict) or not gwt_node.get("id"):
        return None

    given_ref = gwt_node.get("givenRef")
    when_ref = gwt_node.get("whenRef")
    then_ref = gwt_node.get("thenRef")
    test_cases = gwt_node.get("testCases")

    if isinstance(given_ref, str):
        try:
            given_ref = json.loads(given_ref)
        except Exception:
            given_ref = None
    if isinstance(when_ref, str):
        try:
            when_ref = json.loads(when_ref)
        except Exception:
            when_ref = None
    if isinstance(then_ref, str):
        try:
            then_ref = json.loads(then_ref)
        except Exception:
            then_ref = None
    if isinstance(test_cases, str):
        try:
            test_cases = json.loads(test_cases)
        except Exception:
            test_cases = []

    if not isinstance(test_cases, list):
        test_cases = []

    def _ref_to_part(ref: Any) -> dict[str, Any] | None:
        if not isinstance(ref, dict):
            return None
        rid = ref.get("referencedNodeId")
        rtype = ref.get("referencedNodeType")
        name = ref.get("name")
        if not rid or not rtype:
            return None
        return {
            "name": name or "",
            "referencedNodeId": rid,
            "referencedNodeType": rtype,
            "fieldValues": {},
        }

    given_part = _ref_to_part(given_ref)
    when_part = _ref_to_part(when_ref)
    then_part = _ref_to_part(then_ref)

    gwt_sets: list[dict[str, Any]] = []
    for idx, tc in enumerate(test_cases):
        tc = tc if isinstance(tc, dict) else {}
        scenario_desc = tc.get("scenarioDescription")
        # Store scenarioDescription in the first Given's description for backward compatibility
        given_with_desc = None
        if given_part:
            given_with_desc = {**given_part, "fieldValues": tc.get("givenFieldValues") or {}}
            if scenario_desc:
                # Prepend scenario description to given description
                existing_desc = given_part.get("description") or ""
                if existing_desc:
                    given_with_desc["description"] = f"{scenario_desc}\n\n{existing_desc}"
                else:
                    given_with_desc["description"] = scenario_desc
        
        gwt_sets.append(
            {
                "setIndex": idx,
                "scenarioDescription": scenario_desc,
                "given": given_with_desc,
                "when": {**when_part, "fieldValues": tc.get("whenFieldValues") or {}} if when_part else None,
                "then": {**then_part, "fieldValues": tc.get("thenFieldValues") or {}} if then_part else None,
            }
        )

    return {
        "gwtId": gwt_node.get("id"),
        "gwtSets": gwt_sets,
    }


def _fetch_properties_by_parent_id(session: Any, parent_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    """
    Fetch Property lists for parent node ids (Aggregate/Command/Event/ReadModel).
    Properties are sorted by:
      isKey desc -> isForeignKey desc -> name asc
    """
    parent_ids = [pid for pid in (parent_ids or []) if pid]
    if not parent_ids:
        return {}

    query = """
    UNWIND $parent_ids as pid
    MATCH (prop:Property {parentId: pid})
    WITH pid, prop
    ORDER BY coalesce(prop.isKey, false) DESC,
             coalesce(prop.isForeignKey, false) DESC,
             prop.name ASC
    WITH pid, collect(prop {
        .id, .name, .displayName, .type, .description,
        .isKey, .isForeignKey, .isRequired,
        .parentType, .parentId
    }) as properties
    RETURN pid as parentId, properties
    """
    result = session.run(query, parent_ids=parent_ids)
    out: dict[str, list[dict[str, Any]]] = {}
    for r in result:
        pid = r.get("parentId")
        props = r.get("properties") or []
        if pid:
            out[str(pid)] = [dict(p) for p in props if p and p.get("id")]
    return out


@router.put("/update-node/{node_id}")
async def update_node(node_id: str, request: Request) -> dict[str, Any]:
    """
    Update specific properties of a node (sceneGraph, template, etc.).
    Only allows safe fields to be updated.
    """
    body = await request.json()
    allowed_fields = {"sceneGraph", "template", "description", "name", "displayName"}
    updates = {k: v for k, v in body.items() if k in allowed_fields}

    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    with get_session() as session:
        set_clauses = ", ".join(f"n.{k} = ${k}" for k in updates)
        query = f"""
        MATCH (n {{id: $node_id}})
        SET {set_clauses}, n.updatedAt = datetime()
        RETURN n.id as id
        """
        params = {"node_id": node_id, **updates}
        result = session.run(query, **params).single()
        if not result:
            raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

    return {"ok": True, "nodeId": node_id, "updated": list(updates.keys())}


import os as _os

_WIREFRAME_SERVICE_URL = _os.getenv("WIREFRAME_SERVICE_URL", "http://localhost:7610")


@router.post("/export-fig/{node_id}")
async def export_fig(node_id: str) -> StreamingResponse:
    """
    Export a UI node's sceneGraph as a .fig file (with component assets).
    Proxies to the open-pencil wireframe service.
    """
    with get_session() as session:
        rec = session.run(
            "MATCH (n:UI {id: $id}) RETURN n.sceneGraph as sg, n.name as name, n.displayName as dn",
            id=node_id,
        ).single()
        if not rec:
            raise HTTPException(status_code=404, detail=f"UI node {node_id} not found")

    sg_str = rec.get("sg")
    if not sg_str:
        raise HTTPException(status_code=400, detail="No sceneGraph data on this UI node")

    try:
        scene_graph = json.loads(sg_str) if isinstance(sg_str, str) else sg_str
    except (json.JSONDecodeError, TypeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid sceneGraph JSON: {e}")

    ui_name = rec.get("dn") or rec.get("name") or "wireframe"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{_WIREFRAME_SERVICE_URL}/export-fig",
                json={"sceneGraph": scene_graph, "name": ui_name},
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Wireframe service error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Wireframe service unavailable: {e}")

    import io as _io

    safe_name = ui_name.replace('"', '').replace("'", "")[:50]
    return StreamingResponse(
        _io.BytesIO(resp.content),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.fig"'},
    )


@router.post("/generate-component-wireframe/{node_id}")
async def generate_component_wireframe(node_id: str, request: Request) -> dict[str, Any]:
    """
    Generate a wireframe using the .fig component library.
    1. Fetch UI node context (name, description, attached command/readmodel)
    2. Fetch component catalog from wireframe service
    3. Call LLM to select components
    4. Render via wireframe service → sceneGraph
    5. Save sceneGraph to the UI node
    """
    from api.platform import open_pencil_client
    from api.platform.llm import get_llm
    from langchain_core.messages import HumanMessage, SystemMessage

    # Check wireframe service availability
    if not open_pencil_client.is_available():
        raise HTTPException(status_code=503, detail="Wireframe service is not running")

    # Fetch UI node context from Neo4j
    with get_session() as session:
        rec = session.run(
            """
            MATCH (ui:UI {id: $id})
            OPTIONAL MATCH (ui)-[:ATTACHED_TO]->(target)
            OPTIONAL MATCH (bc:BoundedContext)-[:HAS_UI]->(ui)
            RETURN ui.name as name, ui.displayName as displayName,
                   ui.description as description,
                   ui.attachedToType as attachedToType,
                   ui.attachedToName as attachedToName,
                   labels(target)[0] as targetLabel,
                   target.name as targetName,
                   bc.name as bcName
            """,
            id=node_id,
        ).single()
        if not rec:
            raise HTTPException(status_code=404, detail=f"UI node {node_id} not found")

    ui_name = rec.get("displayName") or rec.get("name") or "Wireframe"
    ui_desc = rec.get("description") or ""
    attached_type = rec.get("attachedToType") or ""
    attached_name = rec.get("attachedToName") or rec.get("targetName") or ""
    bc_name = rec.get("bcName") or ""

    # Get component catalog
    catalog = open_pencil_client.get_component_catalog_for_prompt()
    if not catalog:
        raise HTTPException(status_code=503, detail="Component catalog not available")

    # Read optional body overrides
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    display_lang = body.get("display_language", "ko")

    lang_instruction = (
        "All visible text (overrides) MUST be written in Korean (한글)."
        if display_lang == "ko"
        else "All visible text (overrides) MUST be written in English."
    )

    # Build LLM prompt
    system_prompt = f"""You compose a mobile UI wireframe by selecting and arranging components from a design library.

Output rules (STRICT):
- Output ONLY valid JSON. No markdown fences, no explanatory text.
- The JSON must have a "components" array at the top level.
- Each element is an object with:
  - "component": the exact component name from the library
  - "overrides": (optional) object with text overrides

Example:
{{"components": [
  {{"component": "header-main", "overrides": {{"title": "화면 제목"}}}},
  {{"component": "input-search"}},
  {{"component": "com-card-product"}},
  {{"component": "btn-main-task-bottom", "overrides": {{"title": "확인"}}}}
]}}

{lang_instruction}

{catalog}
"""

    user_prompt = f"""Generate a wireframe for:
UI Name: {ui_name}
Bounded Context: {bc_name}
Attached To: {attached_type} {attached_name}
Description: {ui_desc}

Select appropriate components and arrange them top-to-bottom for a mobile screen."""

    # Call LLM
    llm = get_llm()
    try:
        resp = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])
        raw_text = resp.content if hasattr(resp, "content") else str(resp)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM call failed: {e}")

    # Parse LLM JSON and render via wireframe service
    import re as _re
    clean_text = raw_text.strip()
    # Strip markdown fences
    if clean_text.startswith("```"):
        clean_text = _re.sub(r"^```[a-zA-Z]*\n?", "", clean_text)
        clean_text = _re.sub(r"\n?```$", "", clean_text).strip()

    try:
        llm_data = json.loads(clean_text, strict=False)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"LLM output is not valid JSON: {e}. Raw: {clean_text[:300]}")

    components = llm_data.get("components")
    if not isinstance(components, list) or not components:
        raise HTTPException(status_code=500, detail=f"LLM output has no 'components' array. Keys: {list(llm_data.keys())}")

    scene_graph = open_pencil_client.render_wireframe(
        components=components, name=ui_name
    )
    if not scene_graph:
        raise HTTPException(
            status_code=502,
            detail=f"Wireframe service render failed. Components: {json.dumps(components[:3], ensure_ascii=False)}"
        )

    # Save sceneGraph to Neo4j
    sg_str = json.dumps(scene_graph, ensure_ascii=False)
    with get_session() as session:
        session.run(
            "MATCH (ui:UI {id: $id}) SET ui.sceneGraph = $sg, ui.updatedAt = datetime()",
            id=node_id,
            sg=sg_str,
        )

    return {
        "ok": True,
        "nodeId": node_id,
        "sceneGraph": sg_str,
        "uiName": ui_name,
    }


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
        main_node = _to_jsonable(dict(type_record["node"]))
        main_node["type"] = node_type
        # Parse enumerations and valueObjects for Aggregate nodes
        if node_type == "Aggregate":
            _parse_aggregate_fields(main_node)
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
                    agg = _to_jsonable(dict(record["agg"]))
                    agg["type"] = "Aggregate"
                    _parse_aggregate_fields(agg)
                    nodes.append(agg)
                    seen_ids.add(agg["id"])
                    if record["rel1"]["target"]:
                        relationships.append(_to_jsonable(dict(record["rel1"])))

                if record["cmd"] and record["cmd"]["id"] not in seen_ids:
                    cmd = _to_jsonable(dict(record["cmd"]))
                    cmd["type"] = "Command"
                    # Include parentId (Aggregate ID) for frontend layout (Aggregate height spans its Commands)
                    if record["agg"]:
                        cmd["parentId"] = record["agg"]["id"]
                    nodes.append(cmd)
                    seen_ids.add(cmd["id"])
                    if record["rel2"]["target"]:
                        relationships.append(_to_jsonable(dict(record["rel2"])))

                if record["evt"] and record["evt"]["id"] not in seen_ids:
                    evt = _to_jsonable(dict(record["evt"]))
                    evt["type"] = "Event"
                    nodes.append(evt)
                    seen_ids.add(evt["id"])
                    if record["rel3"]["target"]:
                        relationships.append(_to_jsonable(dict(record["rel3"])))

            pol_query = """
            MATCH (bc:BoundedContext {id: $node_id})-[:HAS_POLICY]->(pol:Policy)
            OPTIONAL MATCH (evt:Event)-[r:TRIGGERS]->(pol)
            OPTIONAL MATCH (pol)-[r2:INVOKES]->(cmd:Command)
            RETURN pol, evt.id as triggerEventId, cmd.id as invokeCommandId
            """
            pol_result = session.run(pol_query, node_id=node_id)
            for record in pol_result:
                if record["pol"] and record["pol"]["id"] not in seen_ids:
                    pol = _to_jsonable(dict(record["pol"]))
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
                    cmd = _to_jsonable(dict(record["cmd"]))
                    cmd["type"] = "Command"
                    # Include parentId (Aggregate ID) for frontend layout (Aggregate height spans its Commands)
                    cmd["parentId"] = node_id
                    nodes.append(cmd)
                    seen_ids.add(cmd["id"])
                    relationships.append({"source": node_id, "target": cmd["id"], "type": "HAS_COMMAND"})

                if record["evt"] and record["evt"]["id"] not in seen_ids:
                    evt = _to_jsonable(dict(record["evt"]))
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
                    evt = _to_jsonable(dict(record["evt"]))
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
                    pol = _to_jsonable(dict(record["pol"]))
                    pol["type"] = "Policy"
                    # Include invokeCommandId for frontend layout (place Policy left of Command)
                    if record["cmd"]:
                        pol["invokeCommandId"] = record["cmd"]["id"]
                    nodes.append(pol)
                    seen_ids.add(pol["id"])
                    relationships.append({"source": node_id, "target": pol["id"], "type": "TRIGGERS"})

                if record["cmd"] and record["cmd"]["id"] not in seen_ids:
                    cmd = _to_jsonable(dict(record["cmd"]))
                    cmd["type"] = "Command"
                    nodes.append(cmd)
                    seen_ids.add(cmd["id"])
                    relationships.append({"source": record["pol"]["id"], "target": cmd["id"], "type": "INVOKES"})

        elif node_type == "Policy":
            expand_query = """
            MATCH (pol:Policy {id: $node_id})
            OPTIONAL MATCH (evt:Event)-[:TRIGGERS]->(pol)
            OPTIONAL MATCH (pol)-[:INVOKES]->(cmd:Command)
            OPTIONAL MATCH (cmd)-[:EMITS]->(target_evt:Event)
            OPTIONAL MATCH (agg:Aggregate)-[:HAS_COMMAND]->(cmd)
            RETURN evt, cmd, target_evt, agg
            """
            expand_result = session.run(expand_query, node_id=node_id)
            seen_ids = {node_id}

            for record in expand_result:
                if record["evt"] and record["evt"]["id"] not in seen_ids:
                    evt = _to_jsonable(dict(record["evt"]))
                    evt["type"] = "Event"
                    nodes.append(evt)
                    seen_ids.add(evt["id"])
                    relationships.append({"source": evt["id"], "target": node_id, "type": "TRIGGERS"})

                if record["cmd"] and record["cmd"]["id"] not in seen_ids:
                    cmd = _to_jsonable(dict(record["cmd"]))
                    cmd["type"] = "Command"
                    nodes.append(cmd)
                    seen_ids.add(cmd["id"])
                    relationships.append({"source": node_id, "target": cmd["id"], "type": "INVOKES"})

                if record["target_evt"] and record["target_evt"]["id"] not in seen_ids:
                    target_evt = _to_jsonable(dict(record["target_evt"]))
                    target_evt["type"] = "Event"
                    nodes.append(target_evt)
                    seen_ids.add(target_evt["id"])
                    if record["cmd"]:
                        relationships.append({"source": record["cmd"]["id"], "target": target_evt["id"], "type": "EMITS"})

                if record["agg"] and record["agg"]["id"] not in seen_ids:
                    agg = _to_jsonable(dict(record["agg"]))
                    agg["type"] = "Aggregate"
                    nodes.append(agg)
                    seen_ids.add(agg["id"])
                    if record["cmd"]:
                        relationships.append({"source": agg["id"], "target": record["cmd"]["id"], "type": "HAS_COMMAND"})

        # Attach properties (do not display Property nodes on canvas; embed into parent nodes).
        parent_ids = [n.get("id") for n in nodes if n.get("type") in ("Aggregate", "Command", "Event", "ReadModel") and n.get("id")]
        prop_map = _fetch_properties_by_parent_id(session, parent_ids)
        for n in nodes:
            if n.get("type") in ("Aggregate", "Command", "Event", "ReadModel") and n.get("id"):
                n["properties"] = prop_map.get(n["id"], [])
        
        # Attach GWT for Command and Policy nodes
        # New structure: a single (GWT) bundle node per parent with testCases stored inside.
        cmd_policy_ids = [n.get("id") for n in nodes if n.get("type") in ("Command", "Policy") and n.get("id")]
        if cmd_policy_ids:
            gwt_query = """
            UNWIND $node_ids as node_id
            MATCH (parent {id: node_id})
            OPTIONAL MATCH (parent)-[:HAS_GWT]->(gwt:GWT)
            RETURN node_id,
                   gwt {.id, .givenRef, .whenRef, .thenRef, .testCases} as gwt
            """
            gwt_result = session.run(gwt_query, node_ids=cmd_policy_ids)
            
            gwt_map: dict[str, dict[str, Any]] = {}
            for record in gwt_result:
                nid = record.get("node_id")
                gwt_val = record.get("gwt")
                if nid and gwt_val and isinstance(gwt_val, dict) and gwt_val.get("id"):
                    gwt_map[str(nid)] = _to_jsonable(dict(gwt_val))
            
            for n in nodes:
                if n.get("type") in ("Command", "Policy") and n.get("id"):
                    nid = n["id"]
                    if nid in gwt_map:
                        parsed = _parse_gwt_bundle(gwt_map[nid])
                        if not parsed:
                            continue
                        n["gwtId"] = parsed.get("gwtId")
                        n["gwtSets"] = parsed.get("gwtSets") or []
                        if n["gwtSets"]:
                            first_set = n["gwtSets"][0]
                            if isinstance(first_set, dict):
                                if first_set.get("given"):
                                    n["given"] = first_set["given"]
                                if first_set.get("when"):
                                    n["when"] = first_set["when"]
                                if first_set.get("then"):
                                    n["then"] = first_set["then"]

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
        # Parse enumerations and valueObjects for Aggregate nodes
        if node_type == "Aggregate":
            _parse_aggregate_fields(main_node)

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
                    _parse_aggregate_fields(agg)
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
            RETURN rm
            """
            rm_result = session.run(rm_query, node_id=node_id)
            for record in rm_result:
                if record["rm"] and record["rm"]["id"] not in seen_ids:
                    rm = dict(record["rm"])
                    rm["type"] = "ReadModel"
                    rm["bcId"] = node_id
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

        # Attach properties (do not display Property nodes on canvas; embed into parent nodes).
        parent_ids = [n.get("id") for n in nodes if n.get("type") in ("Aggregate", "Command", "Event", "ReadModel") and n.get("id")]
        prop_map = _fetch_properties_by_parent_id(session, parent_ids)
        for n in nodes:
            if n.get("type") in ("Aggregate", "Command", "Event", "ReadModel") and n.get("id"):
                n["properties"] = prop_map.get(n["id"], [])
        
        # Attach GWT for Command and Policy nodes (bundle node)
        cmd_policy_ids = [n.get("id") for n in nodes if n.get("type") in ("Command", "Policy") and n.get("id")]
        if cmd_policy_ids:
            gwt_query = """
            UNWIND $node_ids as node_id
            MATCH (parent {id: node_id})
            OPTIONAL MATCH (parent)-[:HAS_GWT]->(gwt:GWT)
            RETURN node_id,
                   gwt {.id, .givenRef, .whenRef, .thenRef, .testCases} as gwt
            """
            gwt_result = session.run(gwt_query, node_ids=cmd_policy_ids)
            
            gwt_map: dict[str, dict[str, Any]] = {}
            for record in gwt_result:
                nid = record.get("node_id")
                gwt_val = record.get("gwt")
                if nid and gwt_val and isinstance(gwt_val, dict) and gwt_val.get("id"):
                    gwt_map[str(nid)] = _to_jsonable(dict(gwt_val))
            
            for n in nodes:
                if n.get("type") in ("Command", "Policy") and n.get("id"):
                    nid = n["id"]
                    if nid in gwt_map:
                        parsed = _parse_gwt_bundle(gwt_map[nid])
                        if not parsed:
                            continue
                        n["gwtId"] = parsed.get("gwtId")
                        n["gwtSets"] = parsed.get("gwtSets") or []
                        if n["gwtSets"]:
                            first_set = n["gwtSets"][0]
                            if isinstance(first_set, dict):
                                if first_set.get("given"):
                                    n["given"] = first_set["given"]
                                if first_set.get("when"):
                                    n["when"] = first_set["when"]
                                if first_set.get("then"):
                                    n["then"] = first_set["then"]

        payload = {
            "nodes": nodes,
            "relationships": _dedupe_relationships(relationships),
            "bcContext": {"id": bc["id"], "name": bc["name"], "description": bc.get("description")} if bc else None,
        }
        return _to_jsonable(payload)

