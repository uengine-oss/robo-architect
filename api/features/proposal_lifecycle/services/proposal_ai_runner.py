"""Common Claude Code skill execution with validation and retry feedback."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from typing import Any

from api.features.proposal_lifecycle.services.proposal_ai_validation import (
    ValidationResult,
    format_validation_feedback,
    validation_error_payload,
    violation_summary,
)
from api.platform.observability.smart_logger import SmartLogger
from api.platform.skill_runner import extract_json, run_skill_lines, run_skill_once

_SKILL_ROOT = "robo-proposals"


PromptBuilder = Callable[[str | None], str]
Validator = Callable[[Any], ValidationResult]


async def stream_validated_skill_json(
    *,
    skill_name: str,
    prompt_builder: PromptBuilder,
    validator: Validator,
    proposal_id: str,
    scenario: str | None = None,
    stage: str | None = None,
    max_retries: int = 0,
    parse_error_code: str = "AI_PARSE_FAILED",
    validation_error_code: str = "AI_CONTRACT_INVALID",
) -> AsyncGenerator[tuple[str, object], None]:
    """Stream a skill and retry invalid outputs before yielding a result."""
    feedback: str | None = None
    last_violations: list[dict] = []

    for attempt_index in range(max_retries + 1):
        attempt = attempt_index + 1
        SmartLogger.log(
            "INFO",
            f"proposal ai attempt: {skill_name}",
            category="proposal_lifecycle.ai.attempt",
            params=_log_params(proposal_id, skill_name, scenario, stage, attempt),
        )
        if feedback:
            yield "log_line", {"text": "[검증] 이전 산출물 계약 위반을 수정하도록 validator feedback을 포함해 재시도합니다."}

        raw_lines: list[str] = []
        suppress_log = False
        async for line in run_skill_lines(_SKILL_ROOT, skill_name, prompt_builder(feedback)):
            if line.startswith("TOOL:"):
                parts = line[5:].split(":", 1)
                tool = parts[0].strip()
                path = parts[1].strip() if len(parts) > 1 else ""
                yield "log_line", {"text": f"[tool] {tool} {path}".rstrip()}
                continue
            if line == "PHASE:error":
                last_violations = [_violation("skill", "execution_failed", f"{skill_name} execution failed")]
                break

            raw_lines.append(line)
            stripped = line.strip()
            if stripped.startswith("```") or (not suppress_log and stripped in ("{", "[")):
                suppress_log = True
                continue
            if not suppress_log:
                yield "log_line", {"text": line}

        result = _parse_and_validate("\n".join(raw_lines), validator, parse_error_code)
        if result.valid:
            SmartLogger.log(
                "INFO",
                f"proposal ai valid: {skill_name}",
                category="proposal_lifecycle.ai.valid",
                params=_log_params(proposal_id, skill_name, scenario, stage, attempt),
            )
            yield "result", result.normalized_output
            return

        last_violations = result.violations
        _log_invalid(proposal_id, skill_name, scenario, stage, attempt, result.violations)
        feedback = format_validation_feedback(result.violations)

    yield "error", validation_error_payload(
        validation_error_code,
        "생성된 AI 산출물이 계약을 만족하지 않아 저장하지 않았습니다.",
        last_violations,
    )


async def run_validated_skill_once(
    *,
    skill_name: str,
    prompt_builder: PromptBuilder,
    validator: Validator,
    proposal_id: str,
    scenario: str | None = None,
    stage: str | None = None,
    max_retries: int = 0,
    parse_error_code: str = "AI_PARSE_FAILED",
    validation_error_code: str = "AI_CONTRACT_INVALID",
    timeout: int = 600,
) -> ValidationResult:
    """Run a non-streaming skill with the same validation/retry policy."""
    feedback: str | None = None
    last_result = ValidationResult(
        False,
        violations=[_violation("result", "not_run", "Skill did not run")],
    )

    for attempt_index in range(max_retries + 1):
        attempt = attempt_index + 1
        SmartLogger.log(
            "INFO",
            f"proposal ai attempt: {skill_name}",
            category="proposal_lifecycle.ai.attempt",
            params=_log_params(proposal_id, skill_name, scenario, stage, attempt),
        )
        raw = await run_skill_once(
            _SKILL_ROOT,
            skill_name,
            prompt_builder(feedback),
            timeout=timeout,
        )
        if not raw:
            last_result = ValidationResult(
                False,
                violations=[_violation("skill", "empty_output", f"{skill_name} returned no output")],
            )
        else:
            last_result = _parse_and_validate(raw, validator, parse_error_code)

        if last_result.valid:
            SmartLogger.log(
                "INFO",
                f"proposal ai valid: {skill_name}",
                category="proposal_lifecycle.ai.valid",
                params=_log_params(proposal_id, skill_name, scenario, stage, attempt),
            )
            return last_result

        _log_invalid(proposal_id, skill_name, scenario, stage, attempt, last_result.violations)
        feedback = format_validation_feedback(last_result.violations)

    SmartLogger.log(
        "ERROR",
        f"proposal ai final invalid: {skill_name}",
        category="proposal_lifecycle.ai.final_invalid",
        params={
            **_log_params(proposal_id, skill_name, scenario, stage, max_retries + 1),
            "errorCode": validation_error_code,
            "violations": last_result.violations,
        },
        max_inline_chars=0,
    )
    return last_result


def error_payload_from_result(code: str, result: ValidationResult) -> dict:
    return validation_error_payload(
        code,
        "생성된 AI 산출물이 계약을 만족하지 않아 저장하지 않았습니다.",
        result.violations,
    )


def _parse_and_validate(raw: str, validator: Validator, parse_error_code: str) -> ValidationResult:
    data = extract_json(raw)
    if data is None:
        return ValidationResult(
            False,
            violations=[_violation("result", parse_error_code, "AI output did not contain valid JSON")],
        )
    return validator(data)


def _log_invalid(
    proposal_id: str,
    skill_name: str,
    scenario: str | None,
    stage: str | None,
    attempt: int,
    violations: list[dict],
) -> None:
    SmartLogger.log(
        "WARN",
        f"proposal ai contract invalid: {skill_name}",
        category="proposal_lifecycle.ai.contract_invalid",
        params={
            **_log_params(proposal_id, skill_name, scenario, stage, attempt),
            "violationSummary": violation_summary(violations),
            "violations": violations,
        },
        max_inline_chars=0,
    )


def _log_params(
    proposal_id: str,
    skill_name: str,
    scenario: str | None,
    stage: str | None,
    attempt: int,
) -> dict:
    return {
        "proposalId": proposal_id,
        "skillName": skill_name,
        "scenario": scenario,
        "stage": stage,
        "attempt": attempt,
    }


def _violation(path: str, code: str, message: str) -> dict:
    return {"path": path, "code": code, "message": message, "severity": "blocking"}
