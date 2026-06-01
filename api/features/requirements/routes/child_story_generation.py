"""Child User Story auto-generation (034 — US5, in-process engine).

Given an Epic (BoundedContext) or Feature, ask the in-process LLM to propose
candidate User Stories. Proposals are returned for review (HITL) and persisted
only by the separate /child-stories/confirm endpoint. No new node types — the
confirm path reuses the same persistence as manual user-story authoring.

The "Claude IDE" engine variant (local claude + speckit) is a follow-up; this
module implements the in-process LLM engine, which needs no local install.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid

from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from starlette.requests import Request

from api.features.ingestion.event_storming.neo4j_client import get_neo4j_client
from api.features.ingestion.ingestion_llm_runtime import get_llm
from api.features.requirements.requirements_contracts import (
    ConfirmChildStoriesRequest,
    ConfirmChildStoriesResponse,
    GeneratedStory,
    GenerateChildStoriesResponse,
    LocalToolingStatus,
)
from api.features.requirements.tree_service import user_story_node_dto
from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


# ── Internal LLM output schema ───────────────────────────────────────────


class _LLMStories(BaseModel):
    stories: list[GeneratedStory] = Field(default_factory=list)


_SYSTEM_PROMPT = (
    "You are a senior product analyst decomposing requirements using DDD / "
    "Event Storming vocabulary. Given an Epic (a Bounded Context) or a Feature "
    "and its existing User Stories, propose 3–6 NEW, non-duplicate User Stories "
    "that belong in this scope. Each story has role / action / benefit "
    "(As a <role>, I want to <action>, so that <benefit>). Keep them concrete, "
    "atomic, and testable. Do NOT repeat any existing story. "
    "Write ALL text in the SAME natural language as the provided name and "
    "description (e.g. if they are Korean, answer in Korean)."
)


def _existing_stories_for_feature(feature_id: str) -> list[dict]:
    query = """
    MATCH (f:Feature {id: $id})-[:HAS_USER_STORY]->(us:UserStory)
    RETURN us.role AS role, us.action AS action, us.benefit AS benefit
    """
    with get_session() as session:
        return [dict(r) for r in session.run(query, id=feature_id)]


def _bc_name(bc_id: str) -> str | None:
    with get_session() as session:
        rec = session.run(
            "MATCH (bc:BoundedContext {id: $id}) RETURN bc.displayName AS dn, bc.name AS n",
            id=bc_id,
        ).single()
    if not rec:
        return None
    return rec["dn"] or rec["n"]


def _build_prompt(*, kind: str, name: str, description: str, parent: str | None, existing: list[dict]) -> str:
    lines = [f"{kind} 이름: {name}"]
    if description:
        lines.append(f"{kind} 설명: {description}")
    if parent:
        lines.append(f"상위 Epic(BoundedContext): {parent}")
    if existing:
        lines.append("\n기존 User Story (중복 금지):")
        for s in existing:
            lines.append(f"- As a {s.get('role','')}, I want to {s.get('action','')}, so that {s.get('benefit','')}")
    else:
        lines.append("\n기존 User Story: (없음)")
    lines.append("\n이 범위에 어울리는 새 User Story들을 제안하세요.")
    return "\n".join(lines)


def _parse_stories(raw: str) -> list[GeneratedStory]:
    """Parse a JSON object {stories:[...]} possibly wrapped in code fences."""
    txt = (raw or "").strip()
    if txt.startswith("```"):
        txt = txt.strip("`")
        nl = txt.find("\n")
        if nl != -1:
            txt = txt[nl + 1 :]
    data = json.loads(txt)
    return [
        GeneratedStory(role=s.get("role", ""), action=s.get("action", ""), benefit=s.get("benefit", ""))
        for s in (data.get("stories") or [])
        if (s.get("action") or "").strip()
    ]


def _generate_via_claude(prompt: str) -> list[GeneratedStory]:
    """Run the user's local `claude` CLI headlessly (US5 — claude-ide engine)."""
    full = (
        _SYSTEM_PROMPT
        + "\n\n"
        + prompt
        + '\n\nReturn ONLY a JSON object: {"stories":[{"role":"...","action":"...","benefit":"..."}]}. '
        + "No prose, no code fences."
    )
    proc = subprocess.run(
        ["claude", "--print", "--output-format", "json", full],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "claude failed")[:200])
    envelope = json.loads(proc.stdout)
    return _parse_stories(envelope.get("result", ""))


def _generate(
    name: str, description: str, kind: str, parent: str | None, existing: list[dict], engine: str = "in-process"
) -> list[GeneratedStory]:
    prompt = _build_prompt(kind=kind, name=name, description=description or "", parent=parent, existing=existing)
    # claude-ide 엔진: 로컬 claude로 생성, 실패 시 in-process로 폴백.
    if engine == "claude-ide":
        try:
            stories = _generate_via_claude(prompt)
            if stories:
                return stories
        except Exception as exc:  # noqa: BLE001
            SmartLogger.log(
                "WARN",
                "Claude IDE generation failed; falling back to in-process.",
                category="requirements.user_story.generate_children",
                params={"error": str(exc)},
            )
    try:
        structured = get_llm().with_structured_output(_LLMStories)
        result: _LLMStories = structured.invoke(
            [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
        return [s for s in (result.stories or []) if (s.action or "").strip()]
    except Exception as exc:  # noqa: BLE001 — degrade gracefully to manual fallback
        SmartLogger.log(
            "ERROR",
            "Child story generation failed.",
            category="requirements.user_story.generate_children",
            params={"error": str(exc)},
        )
        return []


@router.get("/local-tooling/status", response_model=LocalToolingStatus)
async def local_tooling_status() -> LocalToolingStatus:
    """로컬 Claude IDE + speckit 설치 상태 점검 (US5 claude-ide 엔진 사전 점검)."""
    claude = shutil.which("claude") is not None
    # speckit-specify may live in the user home (~/.claude/skills) or the
    # project (.claude/skills) — accept either.
    candidate_dirs = [
        os.path.expanduser("~/.claude/skills"),
        os.path.join(os.getcwd(), ".claude", "skills"),
    ]
    speckit = any(os.path.isdir(os.path.join(d, "speckit-specify")) for d in candidate_dirs)
    missing: list[str] = []
    if not claude:
        missing.append("claude")
    if not speckit:
        missing.append("speckit")
    hint = ""
    if missing:
        hint = (
            "‘Claude IDE’ 엔진을 쓰려면 로컬에 Claude Code(claude CLI)와 speckit 스킬이 "
            "필요합니다. https://claude.com/claude-code 에서 설치한 뒤 speckit 스킬을 추가하세요. "
            "설치 전까지는 ‘in-process LLM’ 엔진을 사용할 수 있습니다."
        )
    return LocalToolingStatus(
        claudeInstalled=claude, speckitInstalled=speckit, missing=missing, installHint=hint
    )


@router.post(
    "/generate-stories/{scope_type}/{scope_id}",
    response_model=GenerateChildStoriesResponse,
)
async def generate_child_stories(
    scope_type: str, scope_id: str, request: Request, engine: str = "in-process"
) -> GenerateChildStoriesResponse:
    """Propose child User Stories for an Epic ('epic') or Feature ('feature').

    `engine`: 'in-process' (backend LLM) or 'claude-ide' (local claude CLI,
    falls back to in-process on failure).
    """
    if scope_type not in ("epic", "feature"):
        raise HTTPException(status_code=422, detail="scope_type must be 'epic' or 'feature'")

    client = get_neo4j_client()

    if scope_type == "feature":
        feature = client.get_feature(scope_id)
        if not feature:
            raise HTTPException(status_code=404, detail=f"Feature {scope_id} not found")
        bc_id = feature.get("boundedContextId")
        proposals = _generate(
            name=feature.get("name") or "",
            description=feature.get("description") or "",
            kind="Feature",
            parent=_bc_name(bc_id) if bc_id else None,
            existing=_existing_stories_for_feature(scope_id),
            engine=engine,
        )
        out = GenerateChildStoriesResponse(
            scopeType="feature", scopeId=scope_id, boundedContextId=bc_id, featureId=scope_id, proposals=proposals
        )
    else:  # epic
        name = _bc_name(scope_id)
        if name is None:
            raise HTTPException(status_code=404, detail=f"Bounded context {scope_id} not found")
        existing = client.get_user_stories_by_bc(scope_id)
        with get_session() as session:
            desc_rec = session.run(
                "MATCH (bc:BoundedContext {id: $id}) RETURN bc.description AS d", id=scope_id
            ).single()
        proposals = _generate(
            name=name,
            description=(desc_rec["d"] if desc_rec else "") or "",
            kind="Epic",
            parent=None,
            existing=existing,
            engine=engine,
        )
        out = GenerateChildStoriesResponse(
            scopeType="epic", scopeId=scope_id, boundedContextId=scope_id, featureId=None, proposals=proposals
        )

    SmartLogger.log(
        "INFO",
        f"Generated {len(out.proposals)} child user stories.",
        category="requirements.user_story.generate_children",
        params={**http_context(request), "scope_type": scope_type, "scope_id": scope_id, "count": len(out.proposals)},
    )
    return out


@router.post(
    "/child-stories/confirm",
    response_model=ConfirmChildStoriesResponse,
    status_code=201,
)
async def confirm_child_stories(
    req: ConfirmChildStoriesRequest, request: Request
) -> ConfirmChildStoriesResponse:
    """Persist the user-selected generated stories under their BC (+Feature)."""
    client = get_neo4j_client()
    created = []
    for story in req.stories:
        if not (story.action or "").strip():
            continue
        us_id = str(uuid.uuid4())
        client.create_user_story(
            id=us_id,
            role=story.role or "사용자",
            action=story.action,
            benefit=story.benefit or "",
            priority="medium",
            status="draft",
        )
        if req.boundedContextId:
            client.link_user_story_to_bc(us_id, req.boundedContextId)
        if req.featureId:
            client.link_user_story_to_feature(us_id, req.featureId, source="manual")
        dto = user_story_node_dto(us_id)
        if dto:
            created.append(dto)

    SmartLogger.log(
        "INFO",
        f"Confirmed {len(created)} generated user stories.",
        category="requirements.user_story.confirm_children",
        params={**http_context(request), "feature_id": req.featureId, "bc_id": req.boundedContextId, "count": len(created)},
    )
    return ConfirmChildStoriesResponse(created=created)
