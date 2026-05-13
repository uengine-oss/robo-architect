"""Read-only Neo4j projection of the event-storming graph.

This module never mutates the graph (FR-016). It deliberately does NOT
read ``UI.figmaFileKey`` / ``UI.figmaNodeId`` (FR-012) — wireframes are
rendered from ``UI.sceneGraph`` only, no Figma roundtrip.
"""
from __future__ import annotations

from typing import Any, Optional

from api.platform.neo4j import get_session

from api.features.ddd_spec.paths import derive_slug, unique_slug
from api.features.ddd_spec.projection import (
    AggregateAttribute,
    AggregateProjection,
    BoundedContextProjection,
    CommandProjection,
    CrossBcFlow,
    EventProjection,
    ExternalIntegrationProjection,
    GwtCriterion,
    MemberEntity,
    PolicyProjection,
    ReadModelProjection,
    StrategicClassification,
    UserStoryProjection,
    WireframeProjection,
)
from api.features.ddd_spec.wireframe_render import extract_viewport_class


# Fraction of known-viewport wireframes one class must cover for it to be
# called the project's "dominant" viewport. Below this, the agent has to
# ask the user which viewport drives the IA — that's the whole point of
# the check. 70% is a defensible default: it tolerates a couple of
# companion screens (admin panels, print views) without flipping the
# whole project to "mixed".
DOMINANT_VIEWPORT_THRESHOLD: float = 0.70


# --- low-level helpers ----------------------------------------------------


def _strip(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _list_of_str(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if v is not None and str(v).strip()]


def _identity_type_for(aggregate_name: str) -> str:
    """``Order`` → ``OrderId``; conservative default when not modeled."""
    base = "".join(part.capitalize() for part in aggregate_name.split())
    return (base or "Aggregate") + "Id"


def _mutability_default(prop: dict[str, Any]) -> str:
    if prop.get("isKey"):
        return "immutable after creation"
    return "mutable through commands only"


# --- repository façade ----------------------------------------------------


def _load_aggregate_attributes(session, aggregate_id: str) -> list[AggregateAttribute]:
    rows = session.run(
        """
        MATCH (a:Aggregate {id: $id})-[:HAS_PROPERTY]->(p:Property)
        RETURN p.name AS name, p.type AS type, p.description AS description,
               p.isKey AS isKey, p.isForeignKey AS isForeignKey,
               p.mutability AS mutability
        ORDER BY coalesce(p.isKey, false) DESC, p.name
        """,
        id=aggregate_id,
    )
    attrs: list[AggregateAttribute] = []
    for r in rows:
        mut = _strip(r.get("mutability")) or _mutability_default(dict(r))
        attrs.append(
            AggregateAttribute(
                name=r["name"] or "",
                type=_strip(r.get("type")) or "string",
                mutability=mut,
                description=_strip(r.get("description")),
            )
        )
    return attrs


def _load_gwt(session, parent_id: str, parent_type: str = "Command") -> list[GwtCriterion]:
    rows = session.run(
        """
        MATCH (p {id: $pid})
        OPTIONAL MATCH (p)-[:HAS_GIVEN]->(g:Given) WHERE g.parentType = $ptype
        WITH p, collect(DISTINCT g.description) AS gs_desc, collect(DISTINCT g.name) AS gs_name
        OPTIONAL MATCH (p)-[:HAS_WHEN]->(w:When) WHERE w.parentType = $ptype
        WITH p, gs_desc, gs_name, collect(DISTINCT coalesce(w.description, w.name))[0] AS w_text
        OPTIONAL MATCH (p)-[:HAS_THEN]->(t:Then) WHERE t.parentType = $ptype
        WITH p, gs_desc, gs_name, w_text,
             collect(DISTINCT coalesce(t.description, t.name)) AS ts_desc
        RETURN gs_desc, gs_name, w_text, ts_desc
        """,
        pid=parent_id,
        ptype=parent_type,
    )
    row = rows.single()
    if not row:
        return []
    givens = _list_of_str(row.get("gs_desc")) or _list_of_str(row.get("gs_name"))
    when = _strip(row.get("w_text")) or ""
    thens = _list_of_str(row.get("ts_desc"))
    if not (givens or when or thens):
        return []
    return [GwtCriterion(id=parent_id, given=givens, when=when, then=thens)]


def _load_commands(session, aggregate_id: str) -> list[CommandProjection]:
    rows = session.run(
        """
        MATCH (a:Aggregate {id: $id})-[:HAS_COMMAND]->(c:Command)
        OPTIONAL MATCH (c)-[:EMITS]->(e:Event)
        WITH c, collect(DISTINCT e.name) AS events
        RETURN c.id AS id, c.name AS name, c.description AS description,
               c.preconditions AS preconditions, c.postconditions AS postconditions,
               events AS events_emitted
        ORDER BY c.name
        """,
        id=aggregate_id,
    )
    commands: list[CommandProjection] = []
    for r in rows:
        cid = r["id"]
        commands.append(
            CommandProjection(
                id=cid,
                name=r.get("name") or cid,
                description=_strip(r.get("description")),
                preconditions=_list_of_str(r.get("preconditions")),
                postconditions=_list_of_str(r.get("postconditions")),
                events_emitted=_list_of_str(r.get("events_emitted")),
                gwt=_load_gwt(session, cid, "Command"),
            )
        )
    return commands


def _load_events(session, aggregate_id: str) -> list[EventProjection]:
    rows = session.run(
        """
        MATCH (a:Aggregate {id: $id})-[:HAS_COMMAND]->(:Command)-[:EMITS]->(e:Event)
        RETURN DISTINCT e.id AS id, e.name AS name, e.description AS description
        ORDER BY e.name
        """,
        id=aggregate_id,
    )
    return [
        EventProjection(
            id=r["id"], name=r.get("name") or r["id"], description=_strip(r.get("description"))
        )
        for r in rows
    ]


def _load_policies(session, aggregate_id: str) -> list[PolicyProjection]:
    rows = session.run(
        """
        MATCH (a:Aggregate {id: $id})-[:HAS_COMMAND]->(:Command)-[:EMITS]->(e:Event)
        OPTIONAL MATCH (e)-[:TRIGGERS]->(p:Policy)
        WITH DISTINCT p WHERE p IS NOT NULL
        RETURN p.id AS id, p.name AS name, p.description AS description,
               p.condition AS condition
        ORDER BY p.name
        """,
        id=aggregate_id,
    )
    out: list[PolicyProjection] = []
    for r in rows:
        out.append(
            PolicyProjection(
                id=r["id"],
                name=r.get("name") or r["id"],
                description=_strip(r.get("description")),
                effect=_strip(r.get("condition")),
            )
        )
    return out


def _load_read_models(session, bc_id: str) -> list[ReadModelProjection]:
    rows = session.run(
        """
        MATCH (bc:BoundedContext {id: $id})-[:HAS_READMODEL]->(rm:ReadModel)
        RETURN rm.id AS id, rm.name AS name, rm.description AS description
        ORDER BY rm.name
        """,
        id=bc_id,
    )
    return [
        ReadModelProjection(
            id=r["id"], name=r.get("name") or r["id"], description=_strip(r.get("description"))
        )
        for r in rows
    ]


def _load_member_entities(
    attrs: list[AggregateAttribute], aggregate_name: str
) -> list[MemberEntity]:
    """Heuristic — surface the identity VO and call out FK-type attrs.

    The graph doesn't model "owned entities" explicitly today, so the safest
    default is to emit the identity value object derived from the aggregate
    name. Renderers mark this section "(not modeled — confirm)" when empty.
    """
    members: list[MemberEntity] = []
    members.append(
        MemberEntity(
            name=_identity_type_for(aggregate_name),
            kind="identifier",
            note=f"value object — primary key of {aggregate_name}",
        )
    )
    return members


def _load_aggregates(session, bc_id: str) -> list[AggregateProjection]:
    rows = session.run(
        """
        MATCH (bc:BoundedContext {id: $id})-[:HAS_AGGREGATE]->(a:Aggregate)
        RETURN a.id AS id, a.name AS name, a.description AS description,
               a.rootEntity AS rootEntity, a.invariants AS invariants
        ORDER BY a.name
        """,
        id=bc_id,
    )
    taken: set[str] = set()
    aggregates: list[AggregateProjection] = []
    for r in rows:
        agg_id = r["id"]
        name = r.get("name") or agg_id
        slug = unique_slug(name, agg_id, taken)
        attrs = _load_aggregate_attributes(session, agg_id)
        aggregates.append(
            AggregateProjection(
                id=agg_id,
                name=name,
                slug=slug,
                description=_strip(r.get("description")),
                root_entity=_strip(r.get("rootEntity")) or name,
                member_entities=_load_member_entities(attrs, name),
                attributes=attrs,
                invariants=_list_of_str(r.get("invariants")),
                commands=_load_commands(session, agg_id),
                events=_load_events(session, agg_id),
                policies=_load_policies(session, agg_id),
                read_models=[],  # ReadModels are BC-scoped, surfaced separately below
                identity_type=_identity_type_for(name),
            )
        )
    return aggregates


def _load_user_stories(session, bc_id: str) -> list[UserStoryProjection]:
    rows = session.run(
        """
        MATCH (us:UserStory)-[:IMPLEMENTS]->(target)
        WHERE (target:BoundedContext AND target.id = $id)
           OR (target:Aggregate AND EXISTS {
                   MATCH (bc:BoundedContext {id: $id})-[:HAS_AGGREGATE]->(target)
               })
        OPTIONAL MATCH (us)-[:IMPLEMENTS]->(agg:Aggregate)
        RETURN DISTINCT us.id AS id, us.role AS role, us.action AS action,
               us.benefit AS benefit, us.priority AS priority,
               us.acceptanceCriteria AS criteria,
               head(collect(DISTINCT agg.id)) AS aggregate_id
        ORDER BY us.id
        """,
        id=bc_id,
    )
    stories: list[UserStoryProjection] = []
    for r in rows:
        us_id = r["id"]
        role = _strip(r.get("role"))
        action = _strip(r.get("action"))
        benefit = _strip(r.get("benefit"))
        narrative = (
            f"As a {role}, I want to {action}"
            + (f", so that {benefit}" if benefit else "")
            if role or action
            else (benefit or "")
        )
        priority = _strip(r.get("priority"))
        norm_priority = priority if priority in {"P1", "P2", "P3", "P4", "P5"} else None
        criteria_raw = _list_of_str(r.get("criteria"))
        ac: list[GwtCriterion] = []
        for idx, raw in enumerate(criteria_raw):
            # Best-effort parse: "Given X, When Y, Then Z".
            text = raw
            g_part = ""
            w_part = ""
            t_part = ""
            lower = text.lower()
            g_at = lower.find("given ")
            w_at = lower.find(" when ")
            t_at = lower.find(" then ")
            if w_at >= 0 and t_at > w_at:
                if g_at >= 0:
                    g_part = text[g_at + 6 : w_at].strip(" ,.")
                w_part = text[w_at + 6 : t_at].strip(" ,.")
                t_part = text[t_at + 6 :].strip(" ,.")
            else:
                # Treat as a bare obligation.
                t_part = text
            ac.append(
                GwtCriterion(
                    id=f"{us_id}-ac-{idx}",
                    given=[g_part] if g_part else [],
                    when=w_part,
                    then=[t_part] if t_part else [],
                )
            )

        wireframes = _load_wireframes_for_story(session, us_id)
        stories.append(
            UserStoryProjection(
                id=us_id,
                title=action.capitalize() if action else (us_id),
                narrative=narrative,
                priority=norm_priority,
                aggregate_id=_strip(r.get("aggregate_id")),
                acceptance_criteria=ac,
                wireframes=wireframes,
            )
        )
    return stories


def _load_wireframes_for_story(session, user_story_id: str) -> list[WireframeProjection]:
    rows = session.run(
        """
        MATCH (ui:UI)
        WHERE ui.userStoryId = $usid
        RETURN ui.id AS id, ui.name AS name, ui.template AS template,
               ui.sceneGraph AS sceneGraph,
               ui.attachedToType AS attachedToType,
               ui.attachedToName AS attachedToName,
               ui.actor AS actor
        ORDER BY ui.name
        """,
        usid=user_story_id,
    )
    taken: set[str] = set()
    out: list[WireframeProjection] = []
    for r in rows:
        ui_id = r["id"]
        name = r.get("name") or ui_id
        slug = unique_slug(name, ui_id, taken)
        scene_graph_json = _strip(r.get("sceneGraph"))
        out.append(
            WireframeProjection(
                ui_id=ui_id,
                name=name,
                slug=slug,
                scene_graph_json=scene_graph_json,
                template=_strip(r.get("template")),
                attached_to_type=r.get("attachedToType")
                if r.get("attachedToType") in {"Command", "ReadModel"}
                else None,
                attached_to_name=_strip(r.get("attachedToName")),
                actor=_strip(r.get("actor")),
                viewport_class=extract_viewport_class(scene_graph_json),
            )
        )
    return out


def _load_cross_flows_for_bc(
    session, bc_id: str
) -> tuple[list[CrossBcFlow], list[CrossBcFlow]]:
    """Return ``(inbound, outbound)`` cross-BC flows for this BC.

    Heuristic per research D6: derive flows from Event → Policy where the
    consuming Policy belongs to a different BC.
    """
    rows = session.run(
        """
        MATCH (bcU:BoundedContext)-[:HAS_AGGREGATE]->(:Aggregate)-[:HAS_COMMAND]->(:Command)-[:EMITS]->(e:Event)
        MATCH (e)-[:TRIGGERS]->(p:Policy)<-[:HAS_POLICY]-(bcD:BoundedContext)
        WHERE bcU.id <> bcD.id AND (bcU.id = $id OR bcD.id = $id)
        RETURN bcU.id AS from_id, bcU.name AS from_name,
               bcD.id AS to_id, bcD.name AS to_name,
               e.name AS message
        """,
        id=bc_id,
    )
    inbound: list[CrossBcFlow] = []
    outbound: list[CrossBcFlow] = []
    for r in rows:
        flow = CrossBcFlow(
            from_bc_id=r["from_id"],
            from_bc_name=r.get("from_name") or r["from_id"],
            to_bc_id=r["to_id"],
            to_bc_name=r.get("to_name") or r["to_id"],
            channel="Event bus",
            message=r.get("message") or "",
        )
        if flow.to_bc_id == bc_id:
            inbound.append(flow)
        elif flow.from_bc_id == bc_id:
            outbound.append(flow)
    return inbound, outbound


# --- public API -----------------------------------------------------------


def load_bounded_context(bc_id: str) -> Optional[BoundedContextProjection]:
    """Full projection for one Bounded Context, or ``None`` if not found."""
    with get_session() as session:
        bc_row = session.run(
            """
            MATCH (bc:BoundedContext {id: $id})
            RETURN bc.id AS id, bc.name AS name, bc.description AS description,
                   bc.purpose AS purpose, bc.domainType AS domainType,
                   bc.businessModel AS businessModel, bc.evolution AS evolution
            """,
            id=bc_id,
        ).single()
        if bc_row is None:
            return None

        name = bc_row.get("name") or bc_id
        slug = derive_slug(name, bc_id)
        strategic_fields = {
            "domain_type": _strip(bc_row.get("domainType")),
            "business_model": _strip(bc_row.get("businessModel")),
            "evolution": _strip(bc_row.get("evolution")),
        }
        strategic: Optional[StrategicClassification]
        if any(strategic_fields.values()):
            dt = strategic_fields["domain_type"]
            normalized_dt = dt if dt in {"Core", "Supporting", "Generic"} else None
            strategic = StrategicClassification(
                domain_type=normalized_dt,
                business_model=strategic_fields["business_model"],
                evolution=strategic_fields["evolution"],
            )
        else:
            strategic = None

        aggregates = _load_aggregates(session, bc_id)
        user_stories = _load_user_stories(session, bc_id)
        read_models = _load_read_models(session, bc_id)
        inbound, outbound = _load_cross_flows_for_bc(session, bc_id)

        # Surface BC-scoped ReadModels onto an "ambient" aggregate-less list
        # by attaching them to the first aggregate (if any) just for rendering
        # convenience. The renderer treats them as Domain-Term entries.
        if aggregates and read_models:
            aggregates[0] = aggregates[0].model_copy(update={"read_models": read_models})

        key_terms: list[str] = []
        for a in aggregates:
            key_terms.append(a.name)
            for m in a.member_entities:
                key_terms.append(m.name)
        # de-dup, preserve order
        seen: set[str] = set()
        deduped_terms: list[str] = []
        for t in key_terms:
            if t and t not in seen:
                deduped_terms.append(t)
                seen.add(t)

        return BoundedContextProjection(
            id=bc_id,
            name=name,
            slug=slug,
            description=_strip(bc_row.get("description")),
            purpose=_strip(bc_row.get("purpose")) or _strip(bc_row.get("description")),
            strategic=strategic,
            aggregates=aggregates,
            user_stories=user_stories,
            external_integrations=[],  # not modeled in the schema today (D6 footnote)
            inbound_flows=inbound,
            outbound_flows=outbound,
            key_terms=deduped_terms,
        )


def load_aggregate(aggregate_id: str) -> Optional[tuple[BoundedContextProjection, AggregateProjection]]:
    """Return the BC + Aggregate projection pair, or ``None`` if not found."""
    with get_session() as session:
        row = session.run(
            """
            MATCH (bc:BoundedContext)-[:HAS_AGGREGATE]->(a:Aggregate {id: $id})
            RETURN bc.id AS bc_id
            """,
            id=aggregate_id,
        ).single()
        if row is None:
            return None
    bc = load_bounded_context(row["bc_id"])
    if bc is None:
        return None
    for agg in bc.aggregates:
        if agg.id == aggregate_id:
            return bc, agg
    return None


def load_all_bounded_contexts() -> list[BoundedContextProjection]:
    """Every BC in the graph, ordered by name."""
    with get_session() as session:
        rows = session.run(
            "MATCH (bc:BoundedContext) RETURN bc.id AS id ORDER BY bc.name"
        )
        ids = [r["id"] for r in rows]
    out: list[BoundedContextProjection] = []
    for bc_id in ids:
        bc = load_bounded_context(bc_id)
        if bc is not None:
            out.append(bc)
    return out


def load_cross_bc_flows() -> list[CrossBcFlow]:
    """System-wide cross-BC flows derived from Event → Policy across BCs."""
    with get_session() as session:
        rows = session.run(
            """
            MATCH (bcU:BoundedContext)-[:HAS_AGGREGATE]->(:Aggregate)-[:HAS_COMMAND]->(:Command)-[:EMITS]->(e:Event)
            MATCH (e)-[:TRIGGERS]->(p:Policy)<-[:HAS_POLICY]-(bcD:BoundedContext)
            WHERE bcU.id <> bcD.id
            RETURN DISTINCT bcU.id AS from_id, bcU.name AS from_name,
                   bcD.id AS to_id, bcD.name AS to_name,
                   e.name AS message
            ORDER BY bcU.name, bcD.name
            """
        )
        return [
            CrossBcFlow(
                from_bc_id=r["from_id"],
                from_bc_name=r.get("from_name") or r["from_id"],
                to_bc_id=r["to_id"],
                to_bc_name=r.get("to_name") or r["to_id"],
                channel="Event bus",
                message=r.get("message") or "",
            )
            for r in rows
        ]


# --- Frontend composition (US5 / research D7+D8) --------------------------


def _node_key(bc_id: str, story_id: str, ui_id: str) -> str:
    """Canonical key for UI-flow DAG nodes."""
    return f"{bc_id}/{story_id}/{ui_id}"


def load_frontend_composition(
    framework: str,
    framework_conventions,
    bcs: list,
    flows: list,
):
    """Build the :class:`FrontendCompositionProjection` for the frontend renderer.

    Args:
        framework: the declared framework value (``vue`` / ``react`` /
            ``svelte`` / …) — echoed verbatim into ``framework.md``.
        framework_conventions: caller-resolved
            :class:`FrameworkConventions` for ``framework``, or ``None`` if
            the catalog doesn't recognise it (the renderer then emits
            ``frontend_framework_unsupported``). Passed in by the caller so
            ``ddd_spec`` stays decoupled from ``prd_generation``'s catalog
            (Principle V — cross-feature seam runs the other direction).
        bcs: pre-loaded :class:`BoundedContextProjection` list (from
            :func:`load_all_bounded_contexts`).
        flows: pre-loaded :class:`CrossBcFlow` list (from
            :func:`load_cross_bc_flows`).

    Returns a :class:`FrontendCompositionProjection` with menu, sequenced
    ``ui_flow``, ``unreferenced_uis`` (DAG islands), and any
    ``cycle_broken_edges`` recorded.
    """
    # Imported lazily to avoid hauling Pydantic models into modules that
    # only need the projection types.
    from api.features.ddd_spec.menu_builder import build_menu_hints
    from api.features.ddd_spec.projection import (
        FrontendCompositionProjection,
        TriggerOrigin,
        UIFlowEntry,
    )
    from api.features.ddd_spec.ui_flow_sequencer import (
        build_tiebreaker,
        sequence_topological,
    )

    conventions = framework_conventions

    # ---- Collect nodes + per-node metadata.
    bc_index: dict[str, int] = {}
    story_index: dict[str, tuple[int, Optional[str]]] = {}
    ui_index: dict[str, int] = {}
    bc_slug: dict[str, str] = {}
    bc_name: dict[str, str] = {}

    node_keys: list[str] = []
    node_meta: dict[str, dict] = {}  # node_key -> {bc_id, story_id, story_title, ui_id, ui_slug, bc_slug}

    for bidx, bc in enumerate(bcs):
        bc_index[bc.id] = bidx
        bc_slug[bc.id] = bc.slug
        bc_name[bc.id] = bc.name or bc.slug
        for sidx, story in enumerate(bc.user_stories):
            story_index[story.id] = (sidx, story.priority)
            for uidx, wf in enumerate(story.wireframes):
                ui_index[f"{story.id}/{wf.ui_id}"] = uidx
                key = _node_key(bc.id, story.id, wf.ui_id)
                node_keys.append(key)
                node_meta[key] = {
                    "bc_id": bc.id,
                    "bc_slug": bc.slug,
                    "story_id": story.id,
                    "story_title": story.title or story.id,
                    "ui_id": wf.ui_id,
                    "ui_slug": wf.slug,
                    "viewport_class": wf.viewport_class,
                }

    # ---- Build edges.
    # Tracks per-(src, dst) the trigger metadata so we can attach triggered_by
    # after the topological sort.
    edge_meta: dict[tuple[str, str], dict] = {}
    raw_edges: list[tuple[str, str]] = []

    # Intra-story edges: consecutive wireframes within one User Story.
    for bc in bcs:
        for story in bc.user_stories:
            for i in range(len(story.wireframes) - 1):
                src_wf = story.wireframes[i]
                dst_wf = story.wireframes[i + 1]
                src_key = _node_key(bc.id, story.id, src_wf.ui_id)
                dst_key = _node_key(bc.id, story.id, dst_wf.ui_id)
                raw_edges.append((src_key, dst_key))
                edge_meta.setdefault(
                    (src_key, dst_key),
                    {
                        "kind": "story_internal",
                        "from_user_story_id": story.id,
                    },
                )

    # Cross-BC edges. Per research D8 step 4, ideally each flow connects a
    # specific upstream UI (bound to a Command that emits the flow's event)
    # to a specific downstream UI (bound to the Command the downstream
    # Policy invokes). The current projection surfaces the upstream side
    # via ``CommandProjection.events_emitted``; the downstream Policy→
    # Command linkage is not yet projected, so v1 connects to the
    # downstream BC's first wireframe (by priority/insertion). Future
    # refinement is captured by the ``ui_flow_no_cross_bc_edges`` and
    # ``ui_unreferenced_flow`` warnings the renderer raises.
    bc_by_id = {bc.id: bc for bc in bcs}
    for flow in flows:
        upstream_bc = bc_by_id.get(flow.from_bc_id)
        downstream_bc = bc_by_id.get(flow.to_bc_id)
        if upstream_bc is None or downstream_bc is None or not flow.message:
            continue
        # Upstream UI candidate: a UI bound (Command attachment) to a
        # Command that emits the flow's event name.
        upstream_keys: list[str] = []
        for story in upstream_bc.user_stories:
            commands_by_name = {
                c.name: c
                for agg in upstream_bc.aggregates
                for c in agg.commands
            }
            for wf in story.wireframes:
                if wf.attached_to_type != "Command" or not wf.attached_to_name:
                    continue
                cmd = commands_by_name.get(wf.attached_to_name)
                if cmd is None:
                    continue
                if flow.message in cmd.events_emitted:
                    upstream_keys.append(_node_key(upstream_bc.id, story.id, wf.ui_id))
        # Fallback: the upstream BC's last User Story's last UI.
        if not upstream_keys and upstream_bc.user_stories:
            last_story = upstream_bc.user_stories[-1]
            if last_story.wireframes:
                last_wf = last_story.wireframes[-1]
                upstream_keys.append(
                    _node_key(upstream_bc.id, last_story.id, last_wf.ui_id)
                )
        # Downstream UI candidate (v1): downstream BC's first story / first
        # wireframe by graph insertion order — that's what users usually
        # land on after a cross-BC event.
        downstream_key: Optional[str] = None
        for story in downstream_bc.user_stories:
            if story.wireframes:
                downstream_key = _node_key(
                    downstream_bc.id, story.id, story.wireframes[0].ui_id
                )
                break
        if downstream_key is None:
            continue
        for upstream_key in upstream_keys:
            raw_edges.append((upstream_key, downstream_key))
            edge_meta.setdefault(
                (upstream_key, downstream_key),
                {
                    "kind": "event",
                    "event_name": flow.message,
                    "from_bounded_context_id": flow.from_bc_id,
                },
            )

    # ---- Sequence.
    tb = build_tiebreaker(bc_index, story_index, ui_index)
    ordered_keys, cycle_broken = sequence_topological(node_keys, raw_edges, tb)

    # Determine islands: nodes that participate in no surviving edge.
    surviving_edges = set(edge_meta.keys()) - set(cycle_broken)
    participating: set[str] = set()
    for src, dst in surviving_edges:
        participating.add(src)
        participating.add(dst)

    # Precompute incoming edges per node (for triggered_by lookup) — pick
    # the highest-precedence trigger: event > story_internal > entry_point.
    incoming: dict[str, list[dict]] = {k: [] for k in node_keys}
    for (src, dst) in surviving_edges:
        incoming[dst].append(edge_meta[(src, dst)])

    def _triggered_by(node_key: str) -> Optional[TriggerOrigin]:
        inc = incoming.get(node_key) or []
        # Prefer event triggers (cross-BC) over story_internal.
        for meta in inc:
            if meta["kind"] == "event":
                return TriggerOrigin(
                    kind="event",
                    event_name=meta.get("event_name"),
                    from_bounded_context_id=meta.get("from_bounded_context_id"),
                )
        for meta in inc:
            if meta["kind"] == "story_internal":
                return TriggerOrigin(
                    kind="story_internal",
                    from_user_story_id=meta.get("from_user_story_id"),
                )
        return None

    ui_flow: list[UIFlowEntry] = []
    unreferenced: list[UIFlowEntry] = []
    pos_counter = 0
    unref_counter = 0
    for key in ordered_keys:
        meta = node_meta[key]
        is_island = key not in participating
        if is_island:
            unref_counter += 1
            unreferenced.append(
                UIFlowEntry(
                    position=unref_counter,
                    bounded_context_id=meta["bc_id"],
                    bounded_context_slug=meta["bc_slug"],
                    user_story_id=meta["story_id"],
                    user_story_title=meta["story_title"],
                    wireframe_ui_id=meta["ui_id"],
                    wireframe_slug=meta["ui_slug"],
                    triggered_by=None,
                    is_unreferenced=True,
                    viewport_class=meta.get("viewport_class"),
                )
            )
            continue
        pos_counter += 1
        ui_flow.append(
            UIFlowEntry(
                position=pos_counter,
                bounded_context_id=meta["bc_id"],
                bounded_context_slug=meta["bc_slug"],
                user_story_id=meta["story_id"],
                user_story_title=meta["story_title"],
                wireframe_ui_id=meta["ui_id"],
                wireframe_slug=meta["ui_slug"],
                triggered_by=_triggered_by(key),
                is_unreferenced=False,
                viewport_class=meta.get("viewport_class"),
            )
        )

    # Viewport summary across all bound wireframes (ui_flow + unreferenced).
    # ``unknown`` collects entries whose scene graph was missing or
    # dimensionless so the agent sees that too (a project full of unknown
    # viewports gets no dominant — same shape as "mixed").
    summary: dict[str, int] = {"mobile": 0, "tablet": 0, "desktop": 0, "unknown": 0}
    for entry in (*ui_flow, *unreferenced):
        bucket = entry.viewport_class or "unknown"
        summary[bucket] = summary.get(bucket, 0) + 1
    known_total = summary["mobile"] + summary["tablet"] + summary["desktop"]
    dominant: Optional[str] = None
    if known_total > 0:
        for cls in ("mobile", "tablet", "desktop"):
            if summary[cls] / known_total >= DOMINANT_VIEWPORT_THRESHOLD:
                dominant = cls
                break

    return FrontendCompositionProjection(
        framework=framework,
        framework_conventions=conventions,
        bounded_contexts=bcs,
        # The "menu" field is a flat inventory of bound UIs (with
        # entry-point + unreferenced markers) ordered by UI-flow
        # position. The frontend-engineer agent designs the actual
        # menu IA from this inventory + ui_flow.md + the wider
        # event-modeling flow — we deliberately don't pre-decide
        # routes or groupings (research D7 revised).
        menu=build_menu_hints(bcs, ui_flow, unreferenced),
        ui_flow=ui_flow,
        unreferenced_uis=unreferenced,
        cycle_broken_edges=list(cycle_broken),
        viewport_summary=summary,
        dominant_viewport=dominant,
    )
