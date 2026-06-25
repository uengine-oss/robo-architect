"""
robo-project-constitution 스킬 호출 (인터뷰 게이트 전용).

041 개정: Constitution 은 타깃 레포 파일이 아니라 **Neo4j 노드**(프로젝트 루트 싱글톤)에
저장된다. 이 러너는 *프로젝트 루트 헌장이 없을 때만* 인터뷰를 1회 수행해 루트 노드를 만든다.
보기/수정/BC 오버라이드는 Design 쪽(`api/features/constitution`)에서 처리한다 — 프로포절별
헌장은 절대 만들지 않는다.
"""

from __future__ import annotations

import json
from typing import AsyncGenerator, Optional

from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger
from api.platform.skill_runner import run_skill_lines, extract_json
from api.features.constitution.services import constitution_store as store

_SKILL_ROOT = "robo-proposals"
_SKILL_NAME = "robo-project-constitution"


# --- 호환 헬퍼: 다른 러너(plan/tasks/implement)가 호출한다. project_root 인자는 무시. ---

def read_constitution(project_root: Optional[str] = None) -> Optional[str]:
    """프로젝트 루트 헌장 본문(raw)을 그래프에서 읽는다. 없으면 None."""
    return store.project_constitution_raw()


def get_constitution_response(proposal_id: str) -> dict:
    """프로포절 인터뷰 게이트용 얇은 상태. 보기/수정 표면은 제공하지 않는다."""
    c = store.get_project_constitution()
    return {"exists": bool(c)}


def _load_proposal_ctx(proposal_id: str) -> Optional[dict]:
    with get_session() as session:
        rec = session.run(
            "MATCH (p:Proposal {id: $id}) RETURN p.originalPrompt AS prompt, "
            "p.strategicDiff AS sd",
            id=proposal_id,
        ).single()
    if not rec:
        return None

    def _parse(raw, default):
        try:
            return json.loads(raw) if raw else default
        except Exception:
            return default

    return {"prompt": rec["prompt"] or "", "strategic": _parse(rec.get("sd"), {})}


def _build_interview_prompt(proposal_id: str, ctx: dict) -> str:
    strat = ctx.get("strategic") or {}
    titles = []
    if isinstance(strat, dict):
        for key in ("epics", "features", "userStories"):
            for e in strat.get(key, []) or []:
                t = e.get("entityTitle") if isinstance(e, dict) else None
                if t:
                    titles.append(t)
    intent_summary = ", ".join(titles[:12]) or "(아직 없음)"
    return (
        f"Proposal ID: {proposal_id}\n"
        f"원본 프롬프트(자연어 요구사항): {ctx.get('prompt','')}\n\n"
        f"프로젝트 의도 요약: {intent_summary}\n\n"
        "프롬프트에 드러난 기술 선호는 미리 채운 제안으로, 비어 있는 영역은 의도 적합 추천으로 "
        "제시하라. 의존성 인지 최소 질문 원칙(모놀리스면 ingress/mesh/연동/서비스별환경 질문 생략)을 "
        "따르라. 확정되면 프로젝트 루트 헌장 본문(raw)과 fields 를 JSON 으로 출력하라."
    )


async def stream_constitution(proposal_id: str) -> AsyncGenerator[tuple[str, dict], None]:
    """프로젝트 루트 헌장이 없을 때만 인터뷰를 수행하고, done 시 루트 노드를 생성한다."""
    yield "phase", {"phase": "constitution_interview", "message": "프로젝트 헌장 인터뷰 중..."}

    ctx = _load_proposal_ctx(proposal_id)
    if not ctx:
        yield "error", {"code": "NOT_FOUND", "message": f"Proposal {proposal_id} not found"}
        return

    human_prompt = _build_interview_prompt(proposal_id, ctx)
    SmartLogger.log("INFO", f"constitution_interview_start: {proposal_id}",
                    category="proposal_lifecycle.constitution.start",
                    params={"proposalId": proposal_id})

    output_lines: list[str] = []
    suppress_log = False
    async for line in run_skill_lines(_SKILL_ROOT, _SKILL_NAME, human_prompt):
        if line.startswith("TOOL:"):
            continue
        output_lines.append(line)
        stripped = line.strip()
        if stripped.startswith("```") or (not suppress_log and stripped in ("{", "[")):
            suppress_log = True
            continue
        if not suppress_log:
            yield "log_line", {"text": line}

    data = extract_json("\n".join(output_lines))
    if not data or not isinstance(data, dict):
        yield "error", {"code": "CONSTITUTION_PARSE_FAILED", "message": "헌장 인터뷰 결과 파싱 실패"}
        return

    if data.get("action") == "question":
        yield "question", data.get("question", {})
        yield "done", {"proposalId": proposal_id, "pending": True}
        return

    raw_doc = data.get("raw") or ""
    fields = data.get("fields", {})
    # 프로젝트 루트 헌장 노드 생성/갱신(그래프가 원천). 프로포절 사본 아님.
    h = store.upsert_project_constitution(raw_doc, fields) if raw_doc else None

    yield "draft", {"raw": raw_doc}
    yield "done", {
        "proposalId": proposal_id,
        "raw": raw_doc,
        "fields": fields,
        "seededFrom": data.get("seededFrom", []),
        "recommendations": data.get("recommendations", []),
        "constitutionHash": h,
    }
    SmartLogger.log("INFO", f"constitution_interview_done: {proposal_id}",
                    category="proposal_lifecycle.constitution.done",
                    params={"proposalId": proposal_id, "hash": (h or "")[:8]})
