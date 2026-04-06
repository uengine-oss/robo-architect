"""Phase별 입출력 로깅 모듈.

각 Phase 완료 후 ctx에서 데이터를 읽어 JSON 파일로 저장한다.
기존 Phase 파일은 수정하지 않고, ingestion_workflow_runner.py에서만 호출.

저장 경로: logs/ingestion_runs/{session_id}/
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from api.platform.observability.smart_logger import SmartLogger


# ---------------------------------------------------------------------------
# 저장 경로
# ---------------------------------------------------------------------------

_LOG_BASE = Path(__file__).resolve().parents[4] / "logs" / "ingestion_runs"


def _get_run_dir(session_id: str) -> Path:
    run_dir = _LOG_BASE / session_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


# ---------------------------------------------------------------------------
# 안전한 직렬화 헬퍼
# ---------------------------------------------------------------------------

def _safe_attr(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _serialize_item(obj: Any, keys: list[str]) -> dict:
    return {k: _safe_attr(obj, k) for k in keys}


# ---------------------------------------------------------------------------
# Phase별 추출 함수
# ---------------------------------------------------------------------------

def _extract_user_stories(ctx: Any) -> dict:
    items = [
        _serialize_item(us, ["id", "role", "action", "benefit", "priority"])
        for us in (ctx.user_stories or [])
    ]
    return {
        "output_summary": {"count": len(items)},
        "items": items,
    }


def _extract_bounded_contexts(ctx: Any) -> dict:
    items = [
        _serialize_item(bc, ["id", "name", "description"])
        for bc in (ctx.bounded_contexts or [])
    ]
    return {
        "input_summary": {"user_stories_count": len(ctx.user_stories or [])},
        "output_summary": {"count": len(items)},
        "items": items,
    }


def _extract_aggregates(ctx: Any) -> dict:
    items = []
    for bc_id, aggs in (ctx.aggregates_by_bc or {}).items():
        for agg in aggs:
            item = _serialize_item(agg, ["id", "name", "rootEntity"])
            item["bc_id"] = bc_id
            items.append(item)
    return {
        "input_summary": {"bounded_contexts_count": len(ctx.bounded_contexts or [])},
        "output_summary": {"count": len(items)},
        "items": items,
    }


def _extract_commands(ctx: Any) -> dict:
    items = []
    for agg_id, cmds in (ctx.commands_by_agg or {}).items():
        for cmd in cmds:
            item = _serialize_item(cmd, ["id", "name", "actor", "category", "description"])
            item["aggregate_id"] = agg_id
            items.append(item)
    with_desc = sum(1 for i in items if i.get("description"))
    return {
        "input_summary": {
            "aggregates_count": sum(len(a) for a in (ctx.aggregates_by_bc or {}).values()),
        },
        "output_summary": {
            "count": len(items),
            "with_description": with_desc,
            "without_description": len(items) - with_desc,
        },
        "items": items,
    }


def _extract_events(ctx: Any) -> dict:
    items = []
    for agg_id, evts in (ctx.events_by_agg or {}).items():
        for evt in evts:
            item = _serialize_item(evt, ["id", "name", "version", "description"])
            item["aggregate_id"] = agg_id
            items.append(item)
    with_desc = sum(1 for i in items if i.get("description"))
    return {
        "input_summary": {
            "commands_count": sum(len(c) for c in (ctx.commands_by_agg or {}).values()),
        },
        "output_summary": {
            "count": len(items),
            "with_description": with_desc,
            "without_description": len(items) - with_desc,
        },
        "items": items,
    }


def _extract_readmodels(ctx: Any) -> dict:
    items = []
    for bc_id, rms in (ctx.readmodels_by_bc or {}).items():
        for rm in rms:
            item = _serialize_item(rm, ["id", "name", "description"])
            item["bc_id"] = bc_id
            items.append(item)
    return {
        "output_summary": {"count": len(items)},
        "items": items,
    }


def _extract_policies(ctx: Any) -> dict:
    items = [
        _serialize_item(pol, ["id", "name", "description"])
        for pol in (ctx.policies or [])
    ]
    return {
        "output_summary": {"count": len(items)},
        "items": items,
    }


def _extract_count_only(ctx: Any, phase: str) -> dict:
    """properties, references, gwt, ui 등 ctx에 별도 필드가 없는 Phase."""
    return {"output_summary": {"note": "See Neo4j for details"}}


# Phase 이름 → 추출 함수 매핑
_EXTRACTORS: dict[str, Any] = {
    "01_user_stories": _extract_user_stories,
    "02_bounded_contexts": _extract_bounded_contexts,
    "03_aggregates": _extract_aggregates,
    "04_commands": _extract_commands,
    "05_events": _extract_events,
    "06_readmodels": _extract_readmodels,
    "07_properties": _extract_count_only,
    "08_references": _extract_count_only,
    "09_policies": _extract_policies,
    "10_gwt": _extract_count_only,
    "11_ui_wireframes": _extract_count_only,
}


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------

def save(ctx: Any, phase_name: str) -> None:
    """Phase 완료 후 ctx에서 결과를 추출하여 JSON 파일로 저장.

    Args:
        ctx: IngestionWorkflowContext
        phase_name: "01_user_stories", "04_commands" 등
    """
    try:
        session_id = ctx.session.id if ctx.session else "unknown"
        extractor = _EXTRACTORS.get(phase_name, _extract_count_only)

        # count_only 함수는 (ctx, phase) 시그니처
        if extractor is _extract_count_only:
            data = extractor(ctx, phase_name)
        else:
            data = extractor(ctx)

        payload = {
            "phase": phase_name,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            **data,
        }

        run_dir = _get_run_dir(session_id)
        file_path = run_dir / f"{phase_name}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

        SmartLogger.log(
            "INFO",
            f"Phase log saved: {phase_name}",
            category=f"ingestion.phase_logger.{phase_name}",
            params={
                "session_id": session_id,
                "file": str(file_path),
                "output_summary": data.get("output_summary", {}),
            },
        )
    except Exception as e:
        SmartLogger.log(
            "ERROR",
            f"Phase log failed: {phase_name} — {e}",
            category="ingestion.phase_logger.error",
            params={"phase": phase_name, "error": str(e)},
        )


def save_summary(ctx: Any) -> None:
    """전체 워크플로우 완료 후 요약 파일 저장."""
    try:
        session_id = ctx.session.id if ctx.session else "unknown"
        summary = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "source_type": ctx.source_type,
            "totals": {
                "user_stories": len(ctx.user_stories or []),
                "bounded_contexts": len(ctx.bounded_contexts or []),
                "aggregates": sum(len(a) for a in (ctx.aggregates_by_bc or {}).values()),
                "commands": sum(len(c) for c in (ctx.commands_by_agg or {}).values()),
                "events": sum(len(e) for e in (ctx.events_by_agg or {}).values()),
                "readmodels": sum(len(r) for r in (ctx.readmodels_by_bc or {}).values()),
                "policies": len(ctx.policies or []),
                "uis": len(ctx.uis or []),
            },
        }

        run_dir = _get_run_dir(session_id)
        file_path = run_dir / "summary.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

    except Exception as e:
        SmartLogger.log(
            "ERROR",
            f"Summary log failed: {e}",
            category="ingestion.phase_logger.summary.error",
            params={"error": str(e)},
        )
