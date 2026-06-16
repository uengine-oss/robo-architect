"""Design-trace route (026 — requirements-tab).

Given a User Story, returns the design trajectory starting from the Command
it implements: command → aggregate → event → policy → command → aggregate,
expanded up to a bounded depth. Output shape matches the Design tab's
`expand-with-bc` endpoint (`{nodes, relationships}`) so the frontend can
reuse its Vue Flow rendering.
"""

from __future__ import annotations

from fastapi import APIRouter
from starlette.requests import Request

from api.features.requirements.requirements_contracts import DesignTraceResponse
from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


def _scalar(value):
    """Make a Neo4j value JSON-safe — Neo4j DateTime etc. become strings."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_scalar(v) for v in value]
    if isinstance(value, dict):
        return {k: _scalar(v) for k, v in value.items()}
    return str(value)


# Canvas-relevant scalar fields the Design-tab node components read. Heavy /
# structured fields (valueObjects, enumerations, schema, sceneGraph, …) are
# deliberately excluded — the trace canvas is a brief overview, and dumping a
# 30-entry valueObjects list renders an unbounded, broken sticker.
_NODE_FIELDS = (
    "name", "displayName", "key", "actor", "rootEntity", "description", "version",
)


def _node(rec_node: dict, node_type: str) -> dict:
    """Project a Neo4j node to a compact, JSON-safe canvas node.

    Only the canvas-relevant scalar fields are kept so the Design-tab node
    components render identically but stay compact. `properties` is filled in
    later by `_attach_properties`.
    """
    src = dict(rec_node)
    d: dict = {"id": src.get("id"), "type": node_type, "properties": []}
    for k in _NODE_FIELDS:
        v = src.get(k)
        if v is not None:
            d[k] = _scalar(v)
    if not d.get("name"):
        d["name"] = d.get("id")
    return d


def _attach_properties(session, nodes: dict[str, dict]) -> None:
    """Attach each node's HAS_PROPERTY fields so canvas stickers show them."""
    if not nodes:
        return
    for rec in session.run(
        """
        MATCH (n)-[:HAS_PROPERTY]->(p:Property)
        WHERE n.id IN $ids
        RETURN n.id AS nid, collect(p {.*}) AS props
        """,
        ids=list(nodes.keys()),
    ):
        node = nodes.get(rec["nid"])
        if node is not None:
            node["properties"] = [
                {k: _scalar(v) for k, v in dict(p).items()} for p in rec["props"]
            ]


def _expand_trace(
    session, root_command_ids: list[str], depth: int,
    extra_rm_ids: list[str] | None = None,
) -> tuple[dict[str, dict], list[dict]]:
    """Expand the command→aggregate/ui/event/policy design trace.

    Shared by the User-Story design-trace (one root Command) and the BPM-task
    design-trace (all Commands promoted from the task). Seeds the given root
    Commands, then walks Aggregate(HAS_COMMAND) / UI(ATTACHED_TO) /
    Command-EMITS-Event-TRIGGERS-Policy-INVOKES-Command up to `depth` hops, and
    attaches HAS_PROPERTY fields. Read-only.

    Returns (nodes, relationships): nodes is {id: node_dict}; relationships is a
    list of {source, target, type}.
    """
    nodes: dict[str, dict] = {}
    rels: list[dict] = []
    rel_seen: set[tuple] = set()

    def add_rel(src: str, tgt: str, rtype: str) -> None:
        k = (src, tgt, rtype)
        if k not in rel_seen:
            rel_seen.add(k)
            rels.append({"source": src, "target": tgt, "type": rtype})

    # Seed root Command nodes (skip ids that don't resolve to a Command).
    for cid in root_command_ids:
        rec = session.run(
            "MATCH (cmd:Command {id: $id}) RETURN cmd {.*} AS cmd", id=cid
        ).single()
        if rec and rec["cmd"] and rec["cmd"].get("id"):
            nodes.setdefault(rec["cmd"]["id"], _node(rec["cmd"], "Command"))

    # 조회성 US 등 command가 없는 경우, US가 IMPLEMENTS하는 ReadModel을 직접 시드해
    # 결과 UI(아래 ATTACHED_TO 섹션)와 함께 궤적에 표시되게 한다(읽기측 설계 가시화).
    for rid in extra_rm_ids or []:
        rec = session.run(
            "MATCH (rm:ReadModel {id: $id}) RETURN rm {.*} AS rm", id=rid
        ).single()
        if rec and rec["rm"] and rec["rm"].get("id"):
            nodes.setdefault(rec["rm"]["id"], _node(rec["rm"], "ReadModel"))

    frontier: list[str] = [cid for cid in root_command_ids if cid in nodes]
    for _ in range(depth):
        next_frontier: list[str] = []
        for cmd_id in frontier:
            # Aggregate that owns the command.
            for rec in session.run(
                """
                MATCH (agg:Aggregate)-[:HAS_COMMAND]->(cmd:Command {id: $cmd_id})
                RETURN agg {.*} AS agg
                """,
                cmd_id=cmd_id,
            ):
                agg = rec["agg"]
                if not agg or not agg.get("id"):
                    continue
                nodes.setdefault(agg["id"], _node(agg, "Aggregate"))
                add_rel(agg["id"], cmd_id, "HAS_COMMAND")

            # UI wireframes attached to the command — so the planner can
            # see how the requirement connects through to the screen.
            for rec in session.run(
                """
                MATCH (ui:UI)-[:ATTACHED_TO]->(cmd:Command {id: $cmd_id})
                RETURN ui {.*} AS ui
                """,
                cmd_id=cmd_id,
            ):
                ui = rec["ui"]
                if ui and ui.get("id"):
                    nodes.setdefault(ui["id"], _node(ui, "UI"))
                    add_rel(ui["id"], cmd_id, "ATTACHED_TO")

            # Events emitted, policies triggered, commands invoked.
            for rec in session.run(
                """
                MATCH (cmd:Command {id: $cmd_id})-[:EMITS]->(evt:Event)
                OPTIONAL MATCH (evt)-[:TRIGGERS]->(pol:Policy)
                OPTIONAL MATCH (pol)-[:INVOKES]->(next:Command)
                RETURN evt {.*} AS evt, pol {.*} AS pol, next {.*} AS next
                """,
                cmd_id=cmd_id,
            ):
                evt = rec["evt"]
                if evt and evt.get("id"):
                    nodes.setdefault(evt["id"], _node(evt, "Event"))
                    add_rel(cmd_id, evt["id"], "EMITS")
                pol = rec["pol"]
                if evt and evt.get("id") and pol and pol.get("id"):
                    nodes.setdefault(pol["id"], _node(pol, "Policy"))
                    add_rel(evt["id"], pol["id"], "TRIGGERS")
                nxt = rec["next"]
                if pol and pol.get("id") and nxt and nxt.get("id"):
                    if nxt["id"] not in nodes:
                        nodes[nxt["id"]] = _node(nxt, "Command")
                        next_frontier.append(nxt["id"])
                    add_rel(pol["id"], nxt["id"], "INVOKES")
        frontier = next_frontier
        if not frontier:
            break

    # ReadModels fed by the Events in the trace (CQRS read side) — so the
    # event-modeling lane (042) can show UI→Command→Event→ReadModel. The CQRS
    # chain is Event <-[:TRIGGERED_BY]- CQRSOperation <-[:HAS_OPERATION]-
    # CQRSConfig <-[:HAS_CQRS]- ReadModel. Additive: existing callers gain a few
    # ReadModel nodes; absence of the chain simply yields none.
    event_ids = [nid for nid, n in nodes.items() if n.get("type") == "Event"]
    if event_ids:
        for rec in session.run(
            """
            MATCH (rm:ReadModel)-[:HAS_CQRS]->(:CQRSConfig)
                  -[:HAS_OPERATION]->(:CQRSOperation)-[:TRIGGERED_BY]->(evt:Event)
            WHERE evt.id IN $eids
            RETURN rm {.*} AS rm, evt.id AS eid
            """,
            eids=event_ids,
        ):
            rm = rec["rm"]
            if rm and rm.get("id"):
                nodes.setdefault(rm["id"], _node(rm, "ReadModel"))
                add_rel(rec["eid"], rm["id"], "FEEDS")

    # ReadModel의 결과 화면(042): (:UI)-[:ATTACHED_TO]->(:ReadModel). 이벤트 모델링의
    # …→ReadModel→UI(결과) 끝단을 레인에 표시. role='display'(inline)도 포함해 끌어온다.
    rm_ids = [nid for nid, n in nodes.items() if n.get("type") == "ReadModel"]
    if rm_ids:
        for rec in session.run(
            """
            MATCH (ui:UI)-[a:ATTACHED_TO]->(rm:ReadModel)
            WHERE rm.id IN $rids
            RETURN ui {.*} AS ui, rm.id AS rid, a.role AS role
            """,
            rids=rm_ids,
        ):
            ui = rec["ui"]
            if ui and ui.get("id"):
                nodes.setdefault(ui["id"], _node(ui, "UI"))
                # 결과 UI는 ReadModel 다음(오른쪽)에 오므로 rm→ui 방향으로 잇는다.
                add_rel(rec["rid"], ui["id"], "DISPLAYED_ON" if rec["role"] == "display" else "RESULT_UI")

    # Attach properties so the canvas stickers render them (like Design tab).
    _attach_properties(session, nodes)
    return nodes, rels


@router.get("/user-story/{user_story_id}/design-trace", response_model=DesignTraceResponse)
async def get_design_trace(
    user_story_id: str, request: Request, depth: int = 2
) -> DesignTraceResponse:
    """Load the policy→command→event design trace for a User Story."""
    SmartLogger.log(
        "INFO",
        "Design trace requested.",
        category="requirements.design_trace.request",
        params={**http_context(request), "user_story_id": user_story_id, "depth": depth},
    )

    depth = max(1, min(depth, 5))

    with get_session() as session:
        root = session.run(
            """
            MATCH (us:UserStory {id: $id}) RETURN us.id AS id
            """,
            id=user_story_id,
        ).single()
        if not root:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail=f"User story {user_story_id} not found")

        root_cmd = session.run(
            """
            MATCH (us:UserStory {id: $id})-[:IMPLEMENTS]->(cmd:Command)
            RETURN cmd {.*} AS cmd LIMIT 1
            """,
            id=user_story_id,
        ).single()

        if not root_cmd or not root_cmd["cmd"]:
            # command가 없는 조회성(읽기측) US — US가 IMPLEMENTS하는 ReadModel을
            # 루트로 궤적을 구성한다(CQRS 읽기측: …→Event→ReadModel→결과UI).
            rm_rows = session.run(
                """
                MATCH (us:UserStory {id: $id})-[:IMPLEMENTS]->(rm:ReadModel)
                OPTIONAL MATCH (rm)-[:HAS_CQRS]->(:CQRSConfig)
                      -[:HAS_OPERATION]->(:CQRSOperation)-[:TRIGGERED_BY]->(:Event)<-[:EMITS]-(cmd:Command)
                RETURN collect(DISTINCT rm.id) AS rm_ids, collect(DISTINCT cmd.id) AS cmd_ids
                """,
                id=user_story_id,
            ).single()
            rm_ids = [x for x in (rm_rows["rm_ids"] if rm_rows else []) if x]
            feed_cmd_ids = [x for x in (rm_rows["cmd_ids"] if rm_rows else []) if x]
            if not rm_ids:
                SmartLogger.log(
                    "INFO",
                    "Design trace empty: user story has no implemented Command or ReadModel.",
                    category="requirements.design_trace.empty",
                    params={**http_context(request), "user_story_id": user_story_id},
                )
                return DesignTraceResponse(rootCommandId=None, nodes=[], relationships=[], empty=True)
            # 먹이는 command가 있으면 그걸 루트로 전체 레인을, 없으면 ReadModel만 시드.
            nodes, rels = _expand_trace(session, feed_cmd_ids, depth, extra_rm_ids=rm_ids)
            return DesignTraceResponse(
                rootCommandId=(feed_cmd_ids[0] if feed_cmd_ids else None),
                nodes=list(nodes.values()),
                relationships=rels,
                empty=not nodes,
            )

        root_id = root_cmd["cmd"]["id"]
        nodes, rels = _expand_trace(session, [root_id], depth)

    SmartLogger.log(
        "INFO",
        "Design trace built.",
        category="requirements.design_trace.done",
        params={
            **http_context(request),
            "user_story_id": user_story_id,
            "nodes": len(nodes),
            "relationships": len(rels),
        },
    )
    return DesignTraceResponse(
        rootCommandId=root_id,
        nodes=list(nodes.values()),
        relationships=rels,
        empty=False,
    )
