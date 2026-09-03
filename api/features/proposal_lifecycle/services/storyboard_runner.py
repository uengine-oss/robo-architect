"""
056 — Proposal 초안 스토리보드.

Intent 단계가 끝나 Strategic Diff + journeys 가 저장되는 즉시, 각 저니 step 을
open-pencil 와이어프레임(sceneGraph)으로 렌더해 `p.storyboard` 에 저장한다.
설계·디자인 정합이 끝나기 전에 초안 수준의 화면 흐름을 바로 보여 주는 것이 목적이다.

- 렌더는 `ai_design.wireframe_agent.run_render_agent` (JSX → open-pencil Yoga
  레이아웃 → SerializedSceneGraph) 를 재사용한다.
- 저니가 없으면 UserStory 목록에서 순차 흐름을 합성한다.
- 진행 상태는 in-memory job + Neo4j `p.storyboard` 양쪽에 기록되므로 새로고침
  후에도 부분 결과를 볼 수 있다.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any

from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger

STORYBOARD_MAX_STEPS = 12
_RENDER_CONCURRENCY = 2

_jobs: dict[str, dict[str, Any]] = {}


# ─── Screen plan (journeys → steps) ───────────────────────────────────────


def _slug(text: str, fallback: str) -> str:
    s = re.sub(r"[^0-9A-Za-z가-힣]+", "-", (text or "").strip()).strip("-").lower()
    return s or fallback


def _story_text(us: dict[str, Any]) -> str:
    """UserStory 엔트리(strategicDiff.userStories[i])를 한 줄 설명으로."""
    fields = us.get("fields") if isinstance(us.get("fields"), dict) else {}

    def _f(key: str) -> str:
        v = fields.get(key)
        if isinstance(v, dict):
            v = v.get("after", v.get("value"))
        if v is None:
            v = us.get(key)
        return str(v).strip() if v else ""

    role, action, benefit = _f("role"), _f("action"), _f("benefit")
    title = us.get("entityTitle") or us.get("storyTitle") or us.get("title") or ""
    parts = []
    if title:
        parts.append(str(title))
    if role or action:
        parts.append(f"{role} 로서 {action}".strip())
    if benefit:
        parts.append(f"→ {benefit}")
    acc = _f("acceptanceCriteria") or _f("acceptance")
    if acc:
        parts.append(f"인수조건: {acc[:300]}")
    return " / ".join(p for p in parts if p)


def _index_user_stories(strategic_diff: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(strategic_diff, dict):
        return []
    us = strategic_diff.get("userStories")
    return [u for u in us if isinstance(u, dict)] if isinstance(us, list) else []


def _match_story(step: dict[str, Any], stories: list[dict[str, Any]]) -> dict[str, Any] | None:
    refs: list[str] = []
    for key in ("userStoryRef", "userStoryId", "storyRef", "ref"):
        v = step.get(key)
        if isinstance(v, str):
            refs.append(v)
    for key in ("userStoryRefs", "refs"):
        v = step.get(key)
        if isinstance(v, list):
            refs.extend(str(x) for x in v)
    for us in stories:
        ids = {str(us.get("tempId") or ""), str(us.get("entityId") or ""), str(us.get("id") or "")}
        if refs and ids & set(refs):
            return us
    # 이름 토큰 겹침으로 최선 매칭
    name = (step.get("name") or step.get("title") or "").lower()
    tokens = {t for t in re.split(r"[\s/·,.-]+", name) if len(t) >= 2}
    best, best_score = None, 0
    for us in stories:
        text = (_story_text(us) or "").lower()
        score = sum(1 for t in tokens if t in text)
        if score > best_score:
            best, best_score = us, score
    return best if best_score > 0 else None


def build_screen_plan(
    strategic_diff: dict[str, Any] | None,
    journeys: list[dict[str, Any]] | None,
    original_prompt: str = "",
) -> list[dict[str, Any]]:
    """journeys(+strategicDiff) → 렌더 계획.

    Returns [{id, name, description, steps:[{id, name, kind, next, description}]}]
    screen step 만 렌더 대상이며 gateway 는 흐름 표시용으로만 남긴다.
    """
    stories = _index_user_stories(strategic_diff)
    plan: list[dict[str, Any]] = []
    budget = STORYBOARD_MAX_STEPS

    for ji, j in enumerate(journeys or []):
        if not isinstance(j, dict):
            continue
        jname = j.get("name") or j.get("title") or f"Journey {ji + 1}"
        jdesc = j.get("description") or ""
        jid = j.get("tempId") or j.get("id") or _slug(jname, f"jny-{ji + 1}")
        steps_out: list[dict[str, Any]] = []
        raw_steps = j.get("steps") if isinstance(j.get("steps"), list) else []
        for si, st in enumerate(raw_steps):
            if not isinstance(st, dict):
                continue
            sname = st.get("name") or st.get("title") or st.get("ref") or f"Step {si + 1}"
            sid = st.get("tempId") or st.get("id") or _slug(sname, f"st-{si + 1}")
            kind = st.get("kind") or "screen"
            nxt = st.get("next") if isinstance(st.get("next"), list) else []
            us = _match_story(st, stories)
            desc_parts = [f"저니: {jname}" + (f" — {jdesc}" if jdesc else ""), f"화면: {sname}"]
            if st.get("description"):
                desc_parts.append(str(st["description"]))
            if st.get("condition"):
                desc_parts.append(f"분기 조건: {st['condition']}")
            if us:
                desc_parts.append(f"관련 유저스토리: {_story_text(us)}")
            if original_prompt:
                desc_parts.append(f"요구사항 원문(참고): {original_prompt[:400]}")
            steps_out.append({
                "id": str(sid),
                "name": str(sname),
                "kind": kind,
                "next": [str(n) for n in nxt],
                "description": "\n".join(desc_parts),
                "userStoryId": (us.get("tempId") or us.get("entityId")) if us else None,
            })
        if steps_out:
            plan.append({"id": str(jid), "name": str(jname), "description": str(jdesc), "steps": steps_out})

    if not plan and stories:
        # 저니가 없으면 유저스토리 순서대로 한 흐름을 합성한다.
        steps_out = []
        for i, us in enumerate(stories[:budget]):
            title = us.get("entityTitle") or us.get("storyTitle") or us.get("title") or f"화면 {i + 1}"
            sid = _slug(str(us.get("tempId") or title), f"st-{i + 1}")
            steps_out.append({
                "id": sid,
                "name": str(title),
                "kind": "screen",
                "next": [],
                "description": "\n".join([
                    f"화면: {title}",
                    f"관련 유저스토리: {_story_text(us)}",
                    f"요구사항 원문(참고): {original_prompt[:400]}" if original_prompt else "",
                ]).strip(),
                "userStoryId": us.get("tempId") or us.get("entityId"),
            })
        for a, b in zip(steps_out, steps_out[1:]):
            a["next"] = [b["id"]]
        plan.append({"id": "jny-user-stories", "name": "유저스토리 흐름", "description": "저니 미정의 — 유저스토리 순서로 합성", "steps": steps_out})

    # 전체 예산 제한 (screen step 기준)
    count = 0
    for j in plan:
        kept = []
        for st in j["steps"]:
            if st["kind"] == "screen":
                if count >= budget:
                    continue
                count += 1
            kept.append(st)
        j["steps"] = kept
    return [j for j in plan if j["steps"]]


# ─── Neo4j I/O ────────────────────────────────────────────────────────────


def _load_proposal(proposal_id: str) -> dict[str, Any] | None:
    with get_session() as session:
        rec = session.run(
            "MATCH (p:Proposal {id: $id}) RETURN p.originalPrompt AS prompt, p.strategicDiff AS sd, "
            "p.journeys AS jny, p.storyboard AS sb",
            id=proposal_id,
        ).single()
    if not rec:
        return None

    def _parse(raw, default):
        try:
            return json.loads(raw) if isinstance(raw, str) and raw else (raw or default)
        except Exception:
            return default

    return {
        "prompt": rec.get("prompt") or "",
        "strategic": _parse(rec.get("sd"), {}),
        "journeys": _parse(rec.get("jny"), []),
        "storyboard": _parse(rec.get("sb"), None),
    }


def load_storyboard(proposal_id: str) -> dict[str, Any] | None:
    row = _load_proposal(proposal_id)
    if row is None:
        return None
    sb = row.get("storyboard")
    job = _jobs.get(proposal_id)
    if job and isinstance(sb, dict):
        sb = {**sb, "status": job.get("status", sb.get("status")), "done": job.get("done", sb.get("done"))}
    return sb


def _save_storyboard(proposal_id: str, storyboard: dict[str, Any]) -> None:
    with get_session() as session:
        session.run(
            "MATCH (p:Proposal {id: $id}) SET p.storyboard = $sb",
            id=proposal_id, sb=json.dumps(storyboard, ensure_ascii=False),
        )


def strip_scenes(storyboard: dict[str, Any] | None) -> dict[str, Any] | None:
    """목록/폴링용 경량 버전 — sceneGraph 제거."""
    if not isinstance(storyboard, dict):
        return storyboard
    out = {**storyboard, "journeys": []}
    for j in storyboard.get("journeys") or []:
        steps = []
        for st in j.get("steps") or []:
            steps.append({k: v for k, v in st.items() if k != "sceneGraph"} | {"hasScene": bool(st.get("sceneGraph"))})
        out["journeys"].append({**j, "steps": steps})
    return out


# ─── Rendering ────────────────────────────────────────────────────────────


def _root_frame_id(scene_graph: dict[str, Any]) -> str | None:
    nodes = scene_graph.get("nodes") if isinstance(scene_graph, dict) else None
    if not isinstance(nodes, dict):
        return None
    for nid, n in nodes.items():
        if not isinstance(n, dict) or n.get("type") != "FRAME":
            continue
        parent = nodes.get(n.get("parentId") or "")
        if isinstance(parent, dict) and parent.get("type") == "CANVAS":
            return nid
    for nid, n in nodes.items():
        if isinstance(n, dict) and n.get("type") == "FRAME":
            return nid
    return None


def _catalog_context() -> str:
    """open-pencil 컴포넌트 라이브러리가 살아 있으면 네이티브 <Instance> 지침을 붙인다."""
    from api.features.ai_design.wireframe_agent import native_component_context

    return native_component_context()


async def _render_step(step: dict[str, Any], journey: dict[str, Any], extra_context: str) -> dict[str, Any]:
    from api.features.ai_design.wireframe_agent import run_render_agent

    scene, summary = await run_render_agent(
        name=step["name"],
        description=step.get("description", ""),
        bc_name=journey.get("name", ""),
        bc_description=journey.get("description", ""),
        extra_context=extra_context,
    )
    if not scene:
        return {**step, "status": "failed", "error": "render returned no sceneGraph", "sceneGraph": None, "frameId": None}
    return {**step, "status": "done", "error": None, "sceneGraph": scene, "frameId": _root_frame_id(scene), "summary": summary}


def is_running(proposal_id: str) -> bool:
    return _jobs.get(proposal_id, {}).get("status") == "running"


async def run_storyboard(proposal_id: str, *, force: bool = False) -> dict[str, Any] | None:
    """Proposal 의 저니를 스토리보드로 렌더해 저장한다. 완료된 storyboard 를 반환."""
    if is_running(proposal_id):
        return load_storyboard(proposal_id)

    row = _load_proposal(proposal_id)
    if row is None:
        return None
    existing = row.get("storyboard")
    if existing and not force and existing.get("status") == "completed":
        return existing

    plan = build_screen_plan(row["strategic"], row["journeys"], row["prompt"])
    now = datetime.now(timezone.utc).isoformat()
    total = sum(1 for j in plan for st in j["steps"] if st["kind"] == "screen")
    storyboard: dict[str, Any] = {
        "status": "running" if total else "empty",
        "generatedAt": now,
        "total": total,
        "done": 0,
        "journeys": [
            {**j, "steps": [{**st, "status": "pending" if st["kind"] == "screen" else "skipped",
                             "sceneGraph": None, "frameId": None, "error": None} for st in j["steps"]]}
            for j in plan
        ],
    }
    _save_storyboard(proposal_id, storyboard)
    if not total:
        _jobs.pop(proposal_id, None)
        return storyboard

    _jobs[proposal_id] = {"status": "running", "done": 0, "total": total}
    SmartLogger.log("INFO", f"storyboard start {proposal_id}: {total} screens",
                    category="proposal_lifecycle.storyboard.start",
                    params={"proposalId": proposal_id, "total": total})

    extra_context = await asyncio.to_thread(_catalog_context)
    sem = asyncio.Semaphore(_RENDER_CONCURRENCY)
    lock = asyncio.Lock()

    async def _one(ji: int, si: int) -> None:
        journey = storyboard["journeys"][ji]
        step = journey["steps"][si]
        async with sem:
            try:
                result = await _render_step(step, journey, extra_context)
            except Exception as e:  # noqa: BLE001
                result = {**step, "status": "failed", "error": str(e)[:300], "sceneGraph": None, "frameId": None}
        async with lock:
            journey["steps"][si] = result
            storyboard["done"] += 1
            _jobs[proposal_id]["done"] = storyboard["done"]
            try:
                await asyncio.to_thread(_save_storyboard, proposal_id, storyboard)
            except Exception as e:  # noqa: BLE001
                SmartLogger.log("WARN", f"storyboard save failed {proposal_id}: {e}",
                                category="proposal_lifecycle.storyboard.save_failed")

    tasks = [
        _one(ji, si)
        for ji, j in enumerate(storyboard["journeys"])
        for si, st in enumerate(j["steps"])
        if st["kind"] == "screen"
    ]
    try:
        await asyncio.gather(*tasks)
        failed = sum(1 for j in storyboard["journeys"] for st in j["steps"] if st.get("status") == "failed")
        storyboard["status"] = "completed" if failed < total else "failed"
        storyboard["failed"] = failed
    except Exception as e:  # noqa: BLE001
        storyboard["status"] = "failed"
        storyboard["error"] = str(e)[:300]
    finally:
        _jobs.pop(proposal_id, None)
        _save_storyboard(proposal_id, storyboard)

    SmartLogger.log("INFO", f"storyboard done {proposal_id}: status={storyboard['status']}",
                    category="proposal_lifecycle.storyboard.done",
                    params={"proposalId": proposal_id, "status": storyboard["status"], "done": storyboard["done"]})
    return storyboard


def schedule_storyboard(proposal_id: str, *, force: bool = False) -> bool:
    """이벤트 루프가 있으면 백그라운드 태스크로 스토리보드 생성을 건다."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return False
    if is_running(proposal_id):
        return True
    loop.create_task(run_storyboard(proposal_id, force=force))
    return True


def update_step_scene(proposal_id: str, step_id: str, scene_graph: dict[str, Any]) -> dict[str, Any] | None:
    """FrameEditor 에서 편집한 sceneGraph 를 해당 step 에 반영."""
    row = _load_proposal(proposal_id)
    if row is None or not isinstance(row.get("storyboard"), dict):
        return None
    sb = row["storyboard"]
    hit = False
    for j in sb.get("journeys") or []:
        for st in j.get("steps") or []:
            if st.get("id") == step_id:
                st["sceneGraph"] = scene_graph
                st["frameId"] = _root_frame_id(scene_graph)
                st["status"] = "done"
                st["error"] = None
                st["editedAt"] = datetime.now(timezone.utc).isoformat()
                hit = True
    if not hit:
        return None
    _save_storyboard(proposal_id, sb)
    return sb
