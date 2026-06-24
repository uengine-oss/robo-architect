"""
robo-proposal-tasks 스킬 호출 서비스.

Proposal의 Strategic/Tactical Diff → 구현 작업 목록(tasks)으로 분해한다.
구현(Claude Code 셀)이 아니라 **proposal 쪽에서 미리** 헤드리스 서브프로세스로
작업을 뽑아 스트리밍으로 보여주고(인텐트 분해와 동일한 방식), 그 결과를 Proposal에
저장한다. 구현 시작 시 implement_runner가 이 작업 목록을 speckit tasks 마크다운으로
렌더해 워크트리에 `PROPOSAL_<id>_TASKS.md`로 기록한다. (구현 탭 진행률 추적용)
"""

from __future__ import annotations

import json
from typing import AsyncGenerator

from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger
from api.platform.skill_runner import run_skill_lines, extract_json

_SKILL_ROOT = "robo-proposals"
_SKILL_NAME = "robo-proposal-tasks"


def _build_tasks_prompt(proposal_id: str, ctx: dict) -> str:
    # 041: Constitution + ImplementationPlan 을 함께 제시해, 작업 분해가 선언된
    # 아키텍처/원칙을 검토·준수하도록 한다(FR-015/FR-016).
    constitution = ctx.get("constitution") or "(Constitution 없음)"
    plan = ctx.get("implementationPlan") or "{}"
    return (
        f"Proposal ID: {proposal_id}\n"
        f"제목: {ctx.get('title') or proposal_id}\n"
        f"원본 프롬프트: {ctx.get('prompt') or ''}\n\n"
        f"Strategic Diff (JSON):\n{ctx.get('strategicDiff') or '{}'}\n\n"
        f"Tactical Diff (JSON):\n{ctx.get('tacticalDiff') or '[]'}\n\n"
        f"프로젝트 Constitution:\n{constitution}\n\n"
        f"Implementation Plan (아키텍처 결정/연동/개발환경, JSON):\n{plan}\n\n"
        "위 변경을 격리 워크트리에서 구현하기 위한 작업 목록(tasks)으로 분해해 JSON으로 출력하세요. "
        "작업은 Implementation Plan 의 아키텍처(서비스 경계·레포 매핑·연동/채널·서비스별 개발환경)와 "
        "일관되어야 하며, Constitution 결정과 충돌하는 작업이 있으면 명시적으로 표시하세요."
    )


def _get_context(proposal_id: str) -> dict | None:
    with get_session() as session:
        record = session.run(
            """
            MATCH (p:Proposal {id: $id})
            RETURN p.title AS title, p.originalPrompt AS prompt,
                   p.strategicDiff AS strategicDiff, p.tacticalDiff AS tacticalDiff,
                   p.implementationPlan AS implementationPlan, p.projectRoot AS projectRoot
            """,
            id=proposal_id,
        ).single()
    if not record:
        return None
    constitution = None
    try:
        from api.features.proposal_lifecycle.services.constitution_runner import read_constitution
        constitution = read_constitution(record.get("projectRoot"))
    except Exception:
        constitution = None
    return {
        "title": record.get("title"),
        "prompt": record.get("prompt") or "",
        "strategicDiff": record.get("strategicDiff") or "{}",
        "tacticalDiff": record.get("tacticalDiff") or "[]",
        "implementationPlan": record.get("implementationPlan") or "{}",
        "constitution": constitution,
    }


def _normalize_tasks(raw_tasks: list) -> list[dict]:
    """스킬 출력 tasks를 정규화하고 id를 보정한다."""
    tasks: list[dict] = []
    for i, t in enumerate(raw_tasks or []):
        if not isinstance(t, dict):
            continue
        text = (t.get("text") or "").strip()
        if not text:
            continue
        tasks.append({
            "id": t.get("id") or f"T{i + 1:03d}",
            "phase": (t.get("phase") or "Tasks").strip(),
            "text": text,
            "files": [f for f in (t.get("files") or []) if isinstance(f, str)],
            "parallel": bool(t.get("parallel", False)),
        })
    return tasks


def _save_tasks(proposal_id: str, tasks: list[dict]) -> None:
    with get_session() as session:
        session.run(
            "MATCH (p:Proposal {id: $id}) SET p.tasksJson = $tasks",
            id=proposal_id, tasks=json.dumps(tasks, ensure_ascii=False),
        )


def render_tasks_markdown(proposal_id: str, title: str | None, tasks: list[dict]) -> str:
    """저장된 작업 목록을 speckit tasks 형식 마크다운으로 렌더한다.

    구현 탭의 진행률 파서(tasks_progress.parse_tasks_markdown)가 읽는 포맷과 동일.
    """
    lines = [f"# Tasks: {title or proposal_id} ({proposal_id})", ""]
    lines.append("이 체크리스트는 Proposal 구현 진행 추적용입니다. 각 작업을 완료하면")
    lines.append("해당 항목을 `- [x]`로 바꾸고 워크트리에서 git commit 하세요.")
    lines.append("")
    current_phase: str | None = None
    for t in tasks:
        phase = t.get("phase") or "Tasks"
        if phase != current_phase:
            current_phase = phase
            heading = phase if phase.lower().startswith("phase") else f"## {phase}"
            lines.append("")
            lines.append(heading if heading.startswith("#") else f"## {phase}")
        marker = " [P]" if t.get("parallel") else ""
        files = f" ({', '.join(t['files'])})" if t.get("files") else ""
        lines.append(f"- [ ] {t['id']}{marker} {t['text']}{files}")
    lines.append("")
    return "\n".join(lines)


def load_tasks(proposal_id: str) -> dict:
    """저장된 작업 목록 + 렌더된 마크다운을 반환한다. (GET 라우트 / implement 기록용)"""
    with get_session() as session:
        record = session.run(
            "MATCH (p:Proposal {id: $id}) RETURN p.title AS title, p.tasksJson AS tasksJson",
            id=proposal_id,
        ).single()
    if not record:
        return {"exists": False, "tasks": [], "markdown": ""}
    try:
        tasks = json.loads(record.get("tasksJson") or "[]")
    except Exception:
        tasks = []
    if not tasks:
        return {"exists": False, "tasks": [], "markdown": ""}
    return {
        "exists": True,
        "tasks": tasks,
        "markdown": render_tasks_markdown(proposal_id, record.get("title"), tasks),
    }


async def stream_tasks(proposal_id: str) -> AsyncGenerator[tuple[str, dict], None]:
    """작업 분해 진행을 SSE로 yield한다: phase → log_line(narration) → tasks → done."""
    yield "phase", {"phase": "task_decomposition", "message": "구현 작업 분해 중..."}

    ctx = _get_context(proposal_id)
    if ctx is None:
        yield "error", {"code": "NOT_FOUND", "message": f"Proposal {proposal_id} not found"}
        return
    if (ctx.get("strategicDiff") in (None, "", "{}")) and (ctx.get("tacticalDiff") in (None, "", "[]")):
        yield "error", {"code": "NO_DIFF", "message": "분해할 Strategic/Tactical Diff가 없습니다. 먼저 인텐트 분해를 완료하세요."}
        return

    human_prompt = _build_tasks_prompt(proposal_id, ctx)

    output_lines: list[str] = []
    suppress_log = False
    async for line in run_skill_lines(_SKILL_ROOT, _SKILL_NAME, human_prompt):
        if line.startswith("TOOL:"):
            parts = line[5:].split(":", 1)
            yield "log_line", {"text": f"[tool] {parts[0].strip()} {parts[1].strip() if len(parts) > 1 else ''}"}
            continue
        output_lines.append(line)
        stripped = line.strip()
        if stripped.startswith("```") or (not suppress_log and stripped in ("{", "[")):
            suppress_log = True
            continue
        if not suppress_log:
            yield "log_line", {"text": line}

    raw = "\n".join(output_lines)
    if not raw.strip():
        yield "error", {"code": "TASKS_FAILED", "message": "작업 분해 실패"}
        return

    data = extract_json(raw)
    raw_tasks = data.get("tasks") if isinstance(data, dict) else (data if isinstance(data, list) else None)
    tasks = _normalize_tasks(raw_tasks or [])
    if not tasks:
        yield "error", {"code": "TASKS_PARSE_FAILED", "message": "작업 분해 결과 파싱 실패"}
        return

    _save_tasks(proposal_id, tasks)
    SmartLogger.log("INFO", f"tasks decomposed: {proposal_id} ({len(tasks)})",
                    category="proposal_lifecycle.tasks.done",
                    params={"proposalId": proposal_id, "count": len(tasks)})

    yield "tasks", {"tasks": tasks, "count": len(tasks)}
    yield "done", {"proposalId": proposal_id, "count": len(tasks)}
