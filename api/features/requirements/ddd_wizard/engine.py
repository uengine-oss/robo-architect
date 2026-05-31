"""마법사 단계 엔진 — 단계 산출물(마크다운 + 그래프 변경안) 생성 (035 — US1/US2/US4).

신규 생성기가 아니라 단계 진행·HITL 제안 생성기다. in-process는 get_llm,
claude-ide는 로컬 claude CLI(child_story_generation 패턴, 실패 시 in-process 폴백).
LLM/키가 없어도 답변 기반의 결정적 폴백 제안을 만들어 마법사가 끊기지 않게 한다.
"""

from __future__ import annotations

import json
import uuid

from api.features.requirements.ddd_wizard.step_prompts import STEP_QUESTIONS
from api.features.requirements.requirements_contracts import (
    GraphChangePreview,
    WizardProposal,
)
from api.platform.observability.smart_logger import SmartLogger

_SYSTEM = (
    "You are a DDD facilitator running the ddd-crew 8-step modelling process. "
    "Given a step and the user's answers/document, produce (1) a concise Korean "
    "markdown artifact for that step, and (2) a list of proposed graph changes. "
    "Graph mapping: Epic=BoundedContext, Feature=Feature, UserStory=UserStory, "
    "domain events=Event, aggregates=Aggregate. Only propose changes that map to "
    "these existing node types — never invent node labels. Return ONLY JSON: "
    '{"artifact":"<markdown>","changes":[{"action":"create|update","targetType":'
    '"BoundedContext|UserStory|Event|Aggregate","label":"...","after":{...}}]}.'
)


def _user_prompt(step_key: str, answers: dict, document: str | None) -> str:
    qs = STEP_QUESTIONS.get(step_key, [])
    lines = [f"단계: {step_key}", "질문:"]
    lines += [f"- {q}" for q in qs]
    if answers:
        lines.append("\n사용자 답변:")
        for k, v in answers.items():
            lines.append(f"- {k}: {v}")
    if document:
        lines.append(f"\n붙여넣은 문서:\n{document[:4000]}")
    lines.append("\n이 단계의 산출물과 그래프 변경안을 만들어 주세요.")
    return "\n".join(lines)


def _parse(raw: str) -> tuple[str, list[dict]]:
    txt = (raw or "").strip()
    if txt.startswith("```"):
        txt = txt.strip("`")
        nl = txt.find("\n")
        if nl != -1:
            txt = txt[nl + 1 :]
    data = json.loads(txt)
    return data.get("artifact", ""), list(data.get("changes") or [])


def _via_claude(step_key: str, answers: dict, document: str | None) -> tuple[str, list[dict]]:
    import subprocess

    full = _SYSTEM + "\n\n" + _user_prompt(step_key, answers, document)
    proc = subprocess.run(
        ["claude", "--print", "--output-format", "json", full],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "claude failed")[:200])
    envelope = json.loads(proc.stdout)
    return _parse(envelope.get("result", ""))


def _fallback(step_key: str, answers: dict, document: str | None) -> tuple[str, list[dict]]:
    """LLM 불가 시 답변을 그대로 정리한 결정적 산출물."""
    qs = STEP_QUESTIONS.get(step_key, [])
    body = [f"# {step_key} 산출물 (초안)", ""]
    for q in qs:
        body.append(f"- **{q}**")
    if answers:
        body.append("\n## 답변 요약")
        for k, v in answers.items():
            body.append(f"- {k}: {v}")
    if document:
        body.append("\n## 입력 문서 발췌")
        body.append(document[:1000])
    changes: list[dict] = []
    # decompose 단계: 답변에서 서브도메인 이름이 오면 BC create 제안.
    if step_key == "decompose":
        for name in (answers.get("subdomains") or "").split(","):
            name = name.strip()
            if name:
                changes.append(
                    {"action": "create", "targetType": "BoundedContext",
                     "label": f"BoundedContext '{name}' 생성", "after": {"name": name}}
                )
    return "\n".join(body), changes


def generate_step(
    step_key: str, answers: dict, document: str | None, *, engine: str = "in-process"
) -> WizardProposal:
    """단계 산출물 + 그래프 변경안을 만든다."""
    artifact, changes = "", []
    if engine == "claude-ide":
        try:
            artifact, changes = _via_claude(step_key, answers, document)
        except Exception as exc:  # noqa: BLE001
            SmartLogger.log(
                "WARN", "Claude IDE step generation failed; falling back.",
                category="requirements.ddd_wizard.generate",
                params={"error": str(exc), "step": step_key},
            )
    if not artifact:
        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            from api.features.ingestion.ingestion_llm_runtime import get_llm

            resp = get_llm().invoke(
                [SystemMessage(content=_SYSTEM),
                 HumanMessage(content=_user_prompt(step_key, answers, document))]
            )
            artifact, changes = _parse(getattr(resp, "content", "") or "")
        except Exception as exc:  # noqa: BLE001 — degrade to deterministic fallback
            SmartLogger.log(
                "WARN", "In-process step generation failed; using deterministic fallback.",
                category="requirements.ddd_wizard.generate",
                params={"error": str(exc), "step": step_key},
            )
            artifact, changes = _fallback(step_key, answers, document)

    previews = [
        GraphChangePreview(
            changeId=str(uuid.uuid4()),
            action=(c.get("action") or "create"),
            targetType=(c.get("targetType") or "BoundedContext"),
            targetId=c.get("targetId"),
            label=c.get("label") or "",
            before=c.get("before") or {},
            after=c.get("after") or {},
        )
        for c in changes
    ]
    return WizardProposal(stepKey=step_key, artifactMarkdown=artifact, graphChanges=previews)
