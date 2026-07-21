"""043 — ODA 표준 모드 오케스트레이터.

robo-proposal-oda 스킬(extends oda-specify/oda-plan)을 ODA 지식 베이스를 근거로 실행해
intent(표준 정합성 + 전략 diff + 1차 적합성)와 plan(전술 diff + 표준 산출물 + 최종 게이트)을
산출하고, 표준 strategicDiff/tacticalDiff 로 수렴시켜 다운스트림을 무분기로 유지한다(FR-013).

스킬=에이전트, 백엔드=시퀀서/파서/게이트(Principle X). SSE 진행(Principle III).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import AsyncGenerator, Optional

from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger
from api.platform.skill_runner import run_skill_lines, extract_json
from api.features.proposal_lifecycle.services import oda_conformance

_SKILL_ROOT = "robo-proposals"
_SKILL_NAME = "robo-proposal-oda"

# oda-specify/oda-plan 스킬과 동일한 해석 규칙(oda-knowledge-map §0).
_FALLBACK_ROOT = "/Users/uengine/oda-canvas"


def resolve_knowledge_root() -> Optional[str]:
    """ODA 표준 지식 루트를 해석한다(FR-014). 없으면 None — 호출자가 사용 불가 처리.

    1) $ODA_KNOWLEDGE_ROOT  2) cwd 에서 walk-up 하며 sid/ + repo/usecase-library/ 동시 보유
    디렉터리  3) /Users/uengine/oda-canvas. 첫 유효 경로에서 멈춘다.
    """
    def _valid(root: Path) -> bool:
        return (root / "sid").is_dir() and (root / "repo" / "usecase-library").is_dir()

    env = os.environ.get("ODA_KNOWLEDGE_ROOT")
    if env and _valid(Path(env)):
        return str(Path(env))

    cur = Path.cwd()
    for cand in [cur, *cur.parents]:
        if _valid(cand):
            return str(cand)

    fb = Path(_FALLBACK_ROOT)
    if _valid(fb):
        return str(fb)
    return None


# --- 파서(테스트 대상) ------------------------------------------------------

def parse_intent_result(data: dict) -> dict:
    """스킬 intent 결과 → {alignment, conformance, strategicDiff, journeys}.

    conformance.gateResult 는 스킬 값을 신뢰하지 않고 violations 로부터 재계산한다(차단 권위는
    백엔드, FR-006).
    """
    alignment = data.get("alignment") or {}
    conformance = dict(data.get("conformance") or {})
    conformance["gateResult"] = oda_conformance.evaluate_gate(conformance)["result"]
    return {
        "alignment": alignment,
        "conformance": conformance,
        "strategicDiff": data.get("strategicDiff") or {},
        "journeys": data.get("journeys") or [],
    }


def parse_plan_result(data: dict) -> dict:
    """스킬 plan 결과 → {conformance, tacticalDiff, artifacts}."""
    conformance = dict(data.get("conformance") or {})
    conformance["gateResult"] = oda_conformance.evaluate_gate(conformance)["result"]
    return {
        "conformance": conformance,
        "tacticalDiff": data.get("tacticalDiff") or [],
        "artifacts": data.get("artifacts") or {},
    }


# --- 입력 로드 / 결과 저장 --------------------------------------------------

def _load_prompt(proposal_id: str) -> Optional[str]:
    with get_session() as session:
        rec = session.run(
            "MATCH (p:Proposal {id:$id}) RETURN p.originalPrompt AS prompt",
            id=proposal_id,
        ).single()
    return None if rec is None else (rec.get("prompt") or "")


def _save_intent(proposal_id: str, parsed: dict) -> None:
    sd = parsed["strategicDiff"]
    if isinstance(sd, dict):
        sd["version"] = sd.get("version", 1) or 1
    # evlink SPEC2 T3-1: ODA 저장도 요소별 legacyRefs 관문을 지난다.
    from api.features.proposal_lifecycle.services.legacy_element_refs import enforce_proposal_refs
    enforce_proposal_refs(proposal_id, strategic_diff=sd)
    auto_title = None
    us = sd.get("userStories", []) if isinstance(sd, dict) else []
    if us:
        auto_title = us[0].get("entityTitle") or us[0].get("storyTitle")
    sets = ["p.strategicDiff=$sd", "p.journeys=$journeys",
            "p.odaAlignment=$align", "p.odaConformance=$conf"]
    params = {
        "id": proposal_id,
        "sd": json.dumps(sd, ensure_ascii=False),
        "journeys": json.dumps(parsed["journeys"], ensure_ascii=False),
        "align": json.dumps(parsed["alignment"], ensure_ascii=False),
        "conf": json.dumps(parsed["conformance"], ensure_ascii=False),
    }
    if auto_title:
        sets.append("p.title=$title")
        params["title"] = auto_title
    with get_session() as session:
        session.run(f"MATCH (p:Proposal {{id:$id}}) SET {', '.join(sets)}", **params)


def _save_plan(proposal_id: str, parsed: dict) -> None:
    # evlink SPEC2 T3-1: tactical 확정도 legacyRefs 관문을 지난다.
    from api.features.proposal_lifecycle.services.legacy_element_refs import enforce_proposal_refs
    enforce_proposal_refs(proposal_id, tactical_diff=parsed.get("tacticalDiff"))
    with get_session() as session:
        session.run(
            "MATCH (p:Proposal {id:$id}) SET p.tacticalDiff=$td, "
            "p.odaArtifacts=$arts, p.odaConformance=$conf",
            id=proposal_id,
            td=json.dumps(parsed["tacticalDiff"], ensure_ascii=False),
            arts=json.dumps(parsed["artifacts"], ensure_ascii=False),
            conf=json.dumps(parsed["conformance"], ensure_ascii=False),
        )


def _build_prompt(proposal_id: str, prompt: str, phase: str) -> str:
    return (
        f"Proposal ID: {proposal_id}\n"
        f"Phase: {phase}\n"
        f"원본 프롬프트: {prompt}\n\n"
        f"위 요청을 ODA/TM Forum 표준 지식 베이스에 근거해 '{phase}' 단계로 처리하고, "
        "SKILL.md 의 출력 계약(JSON)대로 결과를 출력하세요."
    )


async def _stream(proposal_id: str, phase: str, save_fn, parse_fn,
                  result_event: str) -> AsyncGenerator[tuple[str, dict], None]:
    yield "phase", {"phase": f"oda_{phase}", "message": f"ODA 표준 {phase} 진행 중..."}

    root = resolve_knowledge_root()
    if not root:
        yield "error", {"code": "ODA_KB_NOT_FOUND",
                        "message": "ODA 표준 지식 베이스를 찾을 수 없습니다 ($ODA_KNOWLEDGE_ROOT)."}
        return

    prompt = _load_prompt(proposal_id)
    if prompt is None:
        yield "error", {"code": "NOT_FOUND", "message": f"Proposal {proposal_id} not found"}
        return

    human_prompt = _build_prompt(proposal_id, prompt, phase)
    output_lines: list[str] = []
    suppress = False
    async for line in run_skill_lines(_SKILL_ROOT, _SKILL_NAME, human_prompt, add_dirs=[root]):
        if line.startswith("TOOL:"):
            parts = line[5:].split(":", 1)
            yield "tool_use", {"tool": parts[0].strip(),
                               "path": parts[1].strip() if len(parts) > 1 else ""}
            continue
        output_lines.append(line)
        stripped = line.strip()
        if stripped.startswith("```") or (not suppress and stripped in ("{", "[")):
            suppress = True
            continue
        if not suppress:
            yield "log_line", {"text": line}

    raw = "\n".join(output_lines)
    data = extract_json(raw)
    if not data or not isinstance(data, dict):
        yield "error", {"code": "ODA_PARSE_FAILED", "message": f"ODA {phase} 결과 파싱 실패"}
        return

    parsed = parse_fn(data)
    save_fn(proposal_id, parsed)

    gate = oda_conformance.evaluate_gate(parsed["conformance"])
    yield result_event, {"alignment": parsed.get("alignment"),
                         "conformance": parsed["conformance"],
                         "gate": gate}
    yield "done", {"proposalId": proposal_id, "phase": phase,
                   "gateResult": gate["result"], "blocking": gate["blocking"]}


def stream_oda_intent(proposal_id: str):
    return _stream(proposal_id, "intent", _save_intent, parse_intent_result, "oda_intent")


def stream_oda_plan(proposal_id: str):
    return _stream(proposal_id, "plan", _save_plan, parse_plan_result, "oda_plan")
