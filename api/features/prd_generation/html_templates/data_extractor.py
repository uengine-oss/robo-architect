"""Deterministic graph → master-template context builder.

`build_base_context(bcs, manifest, project_name)` returns the full dict that
`document.html.j2` consumes for every `derived` section. LLM and hybrid
sections later overlay their results onto the same dict.
"""
from __future__ import annotations

import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

from api.features.ddd_spec.projection import (
    AggregateProjection,
    BoundedContextProjection,
    CommandProjection,
    PolicyProjection,
    UserStoryProjection,
)
from api.features.prd_generation.html_templates.schema import (
    ActorInfo,
    FunctionRow,
    GlossaryRow,
    MetaBlock,
    PolicyRow,
    ProcessRow,
    ProcessStep,
    StateTransitionRow,
    TemplateManifest,
    UseCaseRow,
)


# ----- generic helpers -----------------------------------------------------


_ROLE_RE = re.compile(r"As an?\s+([^,]+?)(?:,| I |\s*$)", re.IGNORECASE)


def _short_git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=Path(__file__).resolve().parents[4],
            check=False,
        )
        sha = (result.stdout or "").strip()
        return sha if result.returncode == 0 else ""
    except Exception:
        return ""


def _bc_token(bc: BoundedContextProjection) -> str:
    """A short uppercase token (e.g. ``MBR``) for IDs. Derived from slug."""
    slug = (bc.slug or bc.name or "BC").upper().replace("-", "_")
    parts = [p for p in slug.split("_") if p]
    if not parts:
        return "BC"
    # Use the first part, take up to 3 letters.
    head = parts[0][:3]
    return head or "BC"


def _agg_token(agg: AggregateProjection) -> str:
    s = (agg.slug or agg.name or "AGG").upper().replace("-", "_")
    parts = [p for p in s.split("_") if p]
    if not parts:
        return "AGG"
    return parts[0][:4]


def _persona_from_narrative(narrative: str) -> Optional[str]:
    m = _ROLE_RE.search(narrative or "")
    if not m:
        return None
    name = m.group(1).strip().strip("., ")
    return name or None


def _uniq_preserve(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        if it and it not in seen:
            out.append(it)
            seen.add(it)
    return out


# ----- section builders ----------------------------------------------------


def _build_meta(
    *,
    manifest: TemplateManifest,
    project_name: str,
    bcs: list[BoundedContextProjection],
) -> MetaBlock:
    prefix = manifest.metadata.doc_id_prefix
    # If there's exactly one BC, append its token. Otherwise just project-level.
    if len(bcs) == 1:
        doc_id = f"{prefix}-{_bc_token(bcs[0])}"
    else:
        doc_id = prefix
    title = f"{project_name} 정책서" if project_name else "정책서"
    if bcs:
        bc_names = "·".join(bc.name for bc in bcs[:3])
        if len(bcs) > 3:
            bc_names += " 외"
        eyebrow = f"{project_name} — {bc_names}".strip(" —")
    else:
        eyebrow = project_name or manifest.name

    return MetaBlock(
        doc_id=doc_id,
        version=manifest.version,
        author=manifest.metadata.author_default,
        generated_at=datetime.now().strftime("%Y-%m-%d"),
        git_sha=_short_git_sha(),
        project_name=project_name,
        title=title,
        eyebrow=eyebrow,
    )


def _build_scope(bcs: list[BoundedContextProjection]) -> str:
    if not bcs:
        return "(범위 정의 없음 — 이벤트 스토밍 그래프에 Bounded Context 가 적재되어 있지 않습니다.)"
    bc_phrase = ", ".join(f"<b>{bc.name}</b>" for bc in bcs)
    return (
        f"본 정책서는 현재 모델링된 {bc_phrase} 도메인의 처리 기준을 정의한다. "
        f"각 Bounded Context 의 유즈케이스 범위와 관련 액터, 프로세스, 기능, 정책을 정리한다."
    )


def _build_actors(bcs: list[BoundedContextProjection]) -> list[ActorInfo]:
    # Collect: personas from US narratives, then wireframe actors, then any
    # downstream BC names appearing in inbound flows (external systems).
    personas: list[tuple[str, str]] = []  # (name, source-hint)
    for bc in bcs:
        for us in bc.user_stories:
            name = _persona_from_narrative(us.narrative)
            if name:
                personas.append((name, "user_story"))
            for wf in us.wireframes:
                if wf.actor:
                    personas.append((wf.actor, "wireframe"))
        for flow in bc.inbound_flows:
            personas.append((flow.from_bc_name, "external"))
        for flow in bc.outbound_flows:
            personas.append((flow.to_bc_name, "external"))

    out: list[ActorInfo] = []
    seen: set[str] = set()
    for idx, (name, src) in enumerate(personas, start=1):
        if name in seen:
            continue
        seen.add(name)
        kind: Any = "external" if src == "external" else "primary"
        description = "외부 연동 시스템" if kind == "external" else "직접 업무를 수행하는 주체"
        out.append(
            ActorInfo(
                id=f"ACT-{idx:03d}",
                name=name,
                kind=kind,
                description=description,
            )
        )
    if not out:
        out.append(
            ActorInfo(
                id="ACT-001",
                name="고객",
                kind="primary",
                description="현재 그래프에 액터가 명시되지 않아 기본 액터로 표기한다.",
            )
        )
    return out


def _build_usecases(
    bcs: list[BoundedContextProjection], actors: list[ActorInfo]
) -> list[UseCaseRow]:
    actor_id_by_name = {a.name: a.id for a in actors}
    out: list[UseCaseRow] = []
    for bc in bcs:
        token = _bc_token(bc)
        for seq, us in enumerate(bc.user_stories, start=1):
            persona = _persona_from_narrative(us.narrative)
            actor_ids: list[str] = []
            if persona and persona in actor_id_by_name:
                actor_ids.append(actor_id_by_name[persona])
            for wf in us.wireframes:
                if wf.actor and wf.actor in actor_id_by_name:
                    aid = actor_id_by_name[wf.actor]
                    if aid not in actor_ids:
                        actor_ids.append(aid)
            preconditions: list[str] = []
            main_flow: list[str] = []
            for ac in us.acceptance_criteria:
                if ac.given:
                    preconditions.extend(ac.given)
                if ac.when:
                    main_flow.append(ac.when)
                if ac.then:
                    main_flow.extend(ac.then)
            out.append(
                UseCaseRow(
                    id=f"UC-{token}-{seq:03d}",
                    name=us.title or us.id,
                    actor_ids=actor_ids,
                    description=us.narrative or "",
                    preconditions=_uniq_preserve(preconditions),
                    main_flow=_uniq_preserve(main_flow),
                    bounded_context_slug=bc.slug,
                )
            )
    return out


_STATE_TYPE_RE = re.compile(r"(status|state|상태)", re.IGNORECASE)


def _state_attribute_for(agg: AggregateProjection) -> Optional[str]:
    """Pick an aggregate attribute that looks like a status field."""
    for attr in agg.attributes:
        if _STATE_TYPE_RE.search(attr.name) or _STATE_TYPE_RE.search(attr.type or ""):
            return attr.name
    return None


def _build_state_transitions(
    bcs: list[BoundedContextProjection],
) -> list[StateTransitionRow]:
    """Derive state transitions from Command → Event chains.

    Heuristic: when an aggregate has a status-like attribute, label the
    transition as ``initial → <event-derived state>``. Otherwise use the
    command name as the trigger and the event name as the target state.
    """
    rows: list[StateTransitionRow] = []
    for bc in bcs:
        for agg in bc.aggregates:
            state_attr = _state_attribute_for(agg)
            base_state = f"{agg.name}.{state_attr}" if state_attr else agg.name
            for cmd in agg.commands:
                if not cmd.events_emitted:
                    rows.append(
                        StateTransitionRow(
                            from_state=base_state,
                            event=cmd.name,
                            to_state=base_state,
                            trigger=cmd.description or "",
                        )
                    )
                    continue
                for ev in cmd.events_emitted:
                    rows.append(
                        StateTransitionRow(
                            from_state=base_state,
                            event=ev,
                            to_state=ev,
                            trigger=cmd.description or "",
                        )
                    )
    return rows


def _commands_index(bc: BoundedContextProjection) -> dict[str, tuple[AggregateProjection, CommandProjection]]:
    out: dict[str, tuple[AggregateProjection, CommandProjection]] = {}
    for agg in bc.aggregates:
        for cmd in agg.commands:
            out[cmd.id] = (agg, cmd)
            if cmd.name and cmd.name not in out:
                out[cmd.name] = (agg, cmd)
    return out


def _build_functions(bcs: list[BoundedContextProjection]) -> list[FunctionRow]:
    out: list[FunctionRow] = []
    for bc in bcs:
        bc_tok = _bc_token(bc)
        for agg in bc.aggregates:
            agg_tok = _agg_token(agg)
            for seq, cmd in enumerate(agg.commands, start=1):
                out.append(
                    FunctionRow(
                        id=f"FN-{bc_tok}-{agg_tok}-{seq:03d}",
                        name=cmd.name or cmd.id,
                        description=cmd.description or "",
                        bounded_context_slug=bc.slug,
                        aggregate_slug=agg.slug,
                        preconditions=list(cmd.preconditions),
                        postconditions=list(cmd.postconditions),
                        events_emitted=list(cmd.events_emitted),
                    )
                )
    return out


def _build_processes(
    bcs: list[BoundedContextProjection],
    functions: list[FunctionRow],
    actors: list[ActorInfo],
) -> list[ProcessRow]:
    actor_id_by_name = {a.name: a.id for a in actors}
    fn_by_name: dict[str, FunctionRow] = {f.name: f for f in functions}
    out: list[ProcessRow] = []
    for bc in bcs:
        bc_tok = _bc_token(bc)
        cmds_index = _commands_index(bc)
        for seq, us in enumerate(bc.user_stories, start=1):
            persona = _persona_from_narrative(us.narrative)
            actor_id = actor_id_by_name.get(persona) if persona else None
            steps: list[ProcessStep] = []
            if us.wireframes:
                # Wireframe-driven: each WF = one step. Try to map attached
                # Command to a function row.
                for sidx, wf in enumerate(us.wireframes, start=1):
                    function_id: Optional[str] = None
                    if wf.attached_to_type == "Command" and wf.attached_to_name:
                        fn = fn_by_name.get(wf.attached_to_name)
                        if fn:
                            function_id = fn.id
                    steps.append(
                        ProcessStep(
                            seq=sidx,
                            name=wf.name or wf.slug,
                            function_id=function_id,
                            wireframe_slug=wf.slug,
                            description=(
                                f"{wf.attached_to_type} `{wf.attached_to_name}` 와 연결" if wf.attached_to_name else ""
                            ),
                        )
                    )
            else:
                # No wireframes — emit one step per acceptance criterion (when clause).
                for sidx, ac in enumerate(us.acceptance_criteria, start=1):
                    if ac.when:
                        # Look up matching command by name match.
                        fn_id: Optional[str] = None
                        for cname, (_, cmd) in cmds_index.items():
                            if cname.lower() in ac.when.lower():
                                fn = fn_by_name.get(cmd.name)
                                if fn:
                                    fn_id = fn.id
                                break
                        steps.append(
                            ProcessStep(
                                seq=sidx,
                                name=ac.when,
                                function_id=fn_id,
                                description="; ".join(ac.then),
                            )
                        )
            out.append(
                ProcessRow(
                    id=f"PR-{bc_tok}-CS-{seq:03d}",
                    name=us.title or us.id,
                    bounded_context_slug=bc.slug,
                    actor_id=actor_id,
                    summary=us.narrative,
                    steps=steps,
                )
            )
    return out


def _build_policies(bcs: list[BoundedContextProjection]) -> list[PolicyRow]:
    out: list[PolicyRow] = []
    seen: set[tuple[str, str]] = set()
    for bc in bcs:
        bc_tok = _bc_token(bc)
        pidx = 1
        for agg in bc.aggregates:
            for pol in agg.policies:
                key = (bc.id, pol.id)
                if key in seen:
                    continue
                seen.add(key)
                out.append(
                    PolicyRow(
                        id=f"POL-{bc_tok}-{pidx:03d}",
                        name=pol.name or pol.id,
                        description=pol.description or "",
                        effect=pol.effect or "",
                        bounded_context_slug=bc.slug,
                        prose=pol.description or "",
                    )
                )
                pidx += 1
    return out


def _build_glossary(bcs: list[BoundedContextProjection]) -> list[GlossaryRow]:
    rows: list[GlossaryRow] = []
    seen: set[str] = set()
    for bc in bcs:
        for term in bc.key_terms:
            if term in seen:
                continue
            seen.add(term)
            rows.append(
                GlossaryRow(
                    term=term,
                    definition="",
                    bounded_context_slug=bc.slug,
                )
            )
        for agg in bc.aggregates:
            for attr in agg.attributes:
                if attr.name in seen:
                    continue
                seen.add(attr.name)
                rows.append(
                    GlossaryRow(
                        term=attr.name,
                        definition=attr.description or f"{agg.name} 의 {attr.mutability} 속성 ({attr.type})",
                        bounded_context_slug=bc.slug,
                    )
                )
            for me in agg.member_entities:
                if me.name in seen:
                    continue
                seen.add(me.name)
                rows.append(
                    GlossaryRow(
                        term=me.name,
                        definition=me.note or f"{agg.name} 의 {me.kind}",
                        bounded_context_slug=bc.slug,
                    )
                )
    return rows


# ----- public API ----------------------------------------------------------


def build_base_context(
    bcs: list[BoundedContextProjection],
    *,
    manifest: TemplateManifest,
    project_name: str = "",
) -> dict[str, Any]:
    """Build the deterministic context dict for `document.html.j2`.

    All keys are populated even when the graph is empty (defensive defaults
    so the master template never breaks rendering).
    """
    meta = _build_meta(manifest=manifest, project_name=project_name, bcs=bcs)
    actors = _build_actors(bcs)
    use_cases = _build_usecases(bcs, actors)
    state_transitions = _build_state_transitions(bcs)
    functions = _build_functions(bcs)
    processes = _build_processes(bcs, functions, actors)
    policies = _build_policies(bcs)
    glossary = _build_glossary(bcs)
    scope_text = _build_scope(bcs)

    return {
        "manifest": manifest,
        "meta": meta,
        "scope_text": scope_text,
        "principles": [],            # filled by LLM section
        "glossary": glossary,
        "actors": actors,
        "use_cases": use_cases,
        "state_transitions": state_transitions,
        "state_codes": [],           # state codes table; populated when status enums modeled
        "processes": processes,
        "functions": functions,
        "policies": policies,
        "bounded_contexts": bcs,
        "warnings": [],              # appended to as LLM sections run
    }
