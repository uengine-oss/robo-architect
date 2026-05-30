"""LLM section runners for the HTML policy-document orchestrator.

Each runner takes the deterministic base context (built by
`data_extractor.build_base_context`) plus the loaded manifest, calls the
configured LLM via `api.platform.llm.get_llm`, and merges results back
into the context dict. Any failure is caught and recorded as a warning —
the build always succeeds with safe fallbacks.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from api.features.prd_generation.html_templates.schema import (
    SectionSpec,
    TemplateManifest,
)


logger = logging.getLogger(__name__)


def _prompt_env(template_dir: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(template_dir)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        autoescape=False,
    )


def _render_prompt(template_dir: Path, prompt_rel_path: str, ctx: dict[str, Any]) -> str:
    env = _prompt_env(template_dir)
    template = env.get_template(prompt_rel_path)
    return template.render(**ctx)


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.+?)```", re.DOTALL)


def _extract_json(raw: str) -> Any:
    """Best-effort: strip code fences and parse JSON. Returns `None` on failure."""
    if not raw:
        return None
    text = raw.strip()
    m = _JSON_FENCE_RE.search(text)
    if m:
        text = m.group(1).strip()
    # Some models still wrap with leading prose — find the first `[` or `{`.
    for opener, closer in (("[", "]"), ("{", "}")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start >= 0 and end > start:
            candidate = text[start : end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _invoke_llm(prompt: str) -> str:
    """Lazy import + invoke. Raises on failure — caller catches."""
    from langchain_core.messages import HumanMessage

    from api.platform.llm import get_llm
    from api.platform.llm_messages import build_system_message

    llm = get_llm()
    response = llm.invoke(
        [
            build_system_message("You output structured JSON only. No prose outside JSON."),
            HumanMessage(content=prompt),
        ]
    )
    return getattr(response, "content", "") or ""


# ----- section runners ----------------------------------------------------


def _run_design_principles(
    template_dir: Path, section: SectionSpec, ctx: dict[str, Any]
) -> None:
    if not section.prompt:
        return
    prompt = _render_prompt(template_dir, section.prompt, ctx)
    raw = _invoke_llm(prompt)
    parsed = _extract_json(raw)
    if not isinstance(parsed, list):
        raise ValueError(f"design_principles: expected list, got {type(parsed).__name__}")
    cleaned: list[dict[str, str]] = []
    for entry in parsed[:10]:
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("title") or "").strip()
        body = str(entry.get("body") or "").strip()
        if not body:
            continue
        cleaned.append({"title": title, "body": body})
    if cleaned:
        ctx["principles"] = cleaned


def _run_state_transitions(
    template_dir: Path, section: SectionSpec, ctx: dict[str, Any]
) -> None:
    if not section.prompt:
        return
    rows = ctx.get("state_transitions") or []
    if not rows:
        return
    prompt = _render_prompt(template_dir, section.prompt, ctx)
    raw = _invoke_llm(prompt)
    parsed = _extract_json(raw)
    if not isinstance(parsed, list):
        raise ValueError(f"state_transitions: expected list, got {type(parsed).__name__}")
    for idx, row in enumerate(rows):
        if idx >= len(parsed):
            break
        entry = parsed[idx]
        if isinstance(entry, dict):
            trig = str(entry.get("trigger") or "").strip()
            if trig:
                row.trigger = trig


def _run_policy_prose(
    template_dir: Path, section: SectionSpec, ctx: dict[str, Any]
) -> None:
    if not section.prompt:
        return
    policies = ctx.get("policies") or []
    if not policies:
        return
    prompt = _render_prompt(template_dir, section.prompt, ctx)
    raw = _invoke_llm(prompt)
    parsed = _extract_json(raw)
    if not isinstance(parsed, list):
        raise ValueError(f"policy_prose: expected list, got {type(parsed).__name__}")
    for idx, pol in enumerate(policies):
        if idx >= len(parsed):
            break
        entry = parsed[idx]
        if isinstance(entry, dict):
            prose = str(entry.get("prose") or "").strip()
            if prose:
                pol.prose = prose


_RUNNERS = {
    "overview.principles": _run_design_principles,
    "usecase.state_table": _run_state_transitions,
    "policy.detail": _run_policy_prose,
}


def run_section(
    *,
    section: SectionSpec,
    manifest: TemplateManifest,
    template_dir: Path,
    ctx: dict[str, Any],
) -> None:
    """Dispatch an `llm`/`hybrid` section by id. Failures degrade to warnings."""
    if section.kind == "derived":
        return
    runner = _RUNNERS.get(section.id)
    if runner is None:
        return
    try:
        runner(template_dir, section, ctx)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("LLM section %s failed: %s", section.id, exc)
        ctx.setdefault("warnings", []).append(
            f"섹션 '{section.id}' 자동 합성 실패: {type(exc).__name__} — 폴백 텍스트로 표시됨"
        )
