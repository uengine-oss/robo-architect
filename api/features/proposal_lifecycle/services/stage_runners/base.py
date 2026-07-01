"""042 — 스테이지 스킬 실행 공통 베이스.

plan_runner.stream_plan 의 스트리밍/파싱 패턴을 재사용한다(Principle III/X):
스킬을 PTY 로 실행 → narration 라인은 `log_line` SSE 로 흘리고, 코드블록/JSON 은 억제,
종료 시 stdout 전체에서 JSON 을 추출해 반환한다. 백엔드는 파서일 뿐(Principle X).
"""

from __future__ import annotations

from typing import AsyncGenerator, Callable, Optional

from api.features.proposal_lifecycle.services.proposal_ai_validation import (
    validate_stage_artifact,
    violation_summary,
)
from api.platform.observability.smart_logger import SmartLogger
from api.platform.skill_runner import extract_json, run_skill_lines

_SKILL_ROOT = "robo-proposals"


async def stream_skill_json(
    skill_name: str,
    human_prompt: str,
    parse_error_code: str,
) -> AsyncGenerator[tuple[str, object], None]:
    """스킬을 스트리밍 실행한다.

    yield 형식:
      ("log_line", {"text": ...})    — narration 한 줄(실시간)
      ("json", <dict|list>)          — 최종 파싱된 JSON
      ("error", {code, message})     — 파싱 실패/스킬 오류
    """
    output_lines: list[str] = []
    suppress_log = False
    saw_error = False

    async for line in run_skill_lines(_SKILL_ROOT, skill_name, human_prompt):
        if line == "PHASE:error":
            saw_error = True
            continue
        if line.startswith("TOOL:"):
            # claude 호출(툴 사용) 로그를 그대로 보여준다(intent_runner 와 동일 패턴).
            parts = line[5:].split(":", 1)
            tool = parts[0].strip()
            path = parts[1].strip() if len(parts) > 1 else ""
            yield "log_line", {"text": f"[tool] {tool} {path}".rstrip()}
            continue
        output_lines.append(line)
        stripped = line.strip()
        if stripped.startswith("```") or (not suppress_log and stripped in ("{", "[")):
            suppress_log = True
            continue
        if not suppress_log:
            yield "log_line", {"text": line}

    if saw_error and not output_lines:
        yield "error", {"code": parse_error_code, "message": f"{skill_name} 스킬 실행 실패"}
        return

    data = extract_json("\n".join(output_lines))
    if data is None:
        SmartLogger.log("WARN", f"stage skill parse failed: {skill_name}",
                        category="proposal_lifecycle.staged.parse_fail",
                        params={"skill": skill_name})
        yield "error", {"code": parse_error_code, "message": f"{skill_name} 결과 파싱 실패"}
        return

    yield "json", data


def domain_node_lines(limit: int = 120) -> str:
    """현재 도메인 노드 목록을 프롬프트용 텍스트로(임팩트/참조용)."""
    from api.platform.neo4j_helpers import load_domain_nodes
    nodes = load_domain_nodes() or []
    return "\n".join(
        f"- id: {n['id']}, type: {n.get('label','')}, name: {n.get('name','')}"
        for n in nodes[:limit]
    ) or "(없음)"


async def execute_stage(
    proposal_id: str,
    stage: str,
    skill_name: str,
    prompt: str,
    *,
    artifact_key: str,
    parse_error_code: str,
    validators: Optional[list[tuple[Callable[[dict], bool], str]]] = None,
    detect_conflicts: bool = False,
) -> AsyncGenerator[tuple[str, object], None]:
    """스테이지 1개를 실행하는 공통 루틴.

    yield: phase / log_line / artifact / conflicts(선택) / done / error.
    - validators: (check(artifact)->bool, warning_msg) 목록 — 실패 시 artifact['_warnings'] 에 누적(차단 아님).
    - detect_conflicts: True 면 strategic_memory.detect_conflicts 로 메모리 충돌을 산출해 conflicts SSE.
    """
    from api.features.proposal_lifecycle.services import staged_runner

    yield "phase", {"phase": stage.lower(), "message": f"{stage} 단계 분석 중..."}
    staged_runner.log_stage(proposal_id, stage, "start")

    artifact = None
    async for ev, data in stream_skill_json(skill_name, prompt, parse_error_code):
        if ev == "json":
            artifact = data.get(artifact_key, data) if isinstance(data, dict) else data
        elif ev == "error":
            yield "error", data
            return
        else:
            yield ev, data

    if not isinstance(artifact, dict):
        yield "error", {"code": parse_error_code, "message": f"{stage} 산출물 형식 오류"}
        return

    artifact["stage"] = stage
    warnings = []
    validation = validate_stage_artifact(stage, artifact)
    if validation.violations:
        SmartLogger.log(
            "WARN",
            f"stage artifact contract invalid: {stage}",
            category="proposal_lifecycle.staged.artifact_invalid",
            params={
                "proposalId": proposal_id,
                "stage": stage,
                "skillName": skill_name,
                "violationSummary": violation_summary(validation.violations),
                "violations": validation.violations,
            },
            max_inline_chars=0,
        )
        yield "error", {
            "code": f"{stage}_ARTIFACT_INVALID",
            "message": f"{stage} 산출물이 필수 계약을 만족하지 않아 저장하지 않았습니다.",
            "violationSummary": violation_summary(validation.violations),
            "violations": validation.violations[:8],
        }
        return
    warnings.extend(v.get("message", v.get("code", "")) for v in validation.warnings)
    for check, msg in (validators or []):
        try:
            if not check(artifact):
                warnings.append(msg)
        except Exception:
            warnings.append(msg)
    if warnings:
        artifact["_warnings"] = warnings

    if detect_conflicts:
        from api.features.proposal_lifecycle.services import strategic_memory
        conflicts = strategic_memory.detect_conflicts(proposal_id, stage, artifact)
        if conflicts:
            yield "conflicts", {"conflicts": conflicts}

    yield "artifact", {"stage": stage, "artifact": artifact}
    nxt = staged_runner.next_stage_after(
        (staged_runner.load_state(proposal_id) or {}).get("stagePlan"), stage)
    yield "done", {"stage": stage, "nextStage": nxt}
