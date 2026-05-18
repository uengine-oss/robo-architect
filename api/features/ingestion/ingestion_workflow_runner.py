"""
Ingestion Workflow Runner (streaming)

Business capability: convert uploaded requirements text into an Event Storming model in Neo4j,
emitting real-time progress events for the UI (SSE).

Event Modeling 기반 체인:
  1. Parsing
  2. UserStory 추출
  3. UserStory 시퀀스 할당
  4. Event 추출 (per UserStory)        ← Command 이전
  5. BoundedContext 식별
  6. Aggregate 추출
  7. Command 추출 (Event 역도출 포함)
  8. Command → 기존 Event EMITS 연결 (중복 Event 추출 없음)
  9. ReadModel 추출
  10. Properties 생성
  11. Property References
  12. Policy 식별
  13. GWT 생성
  14. UI Wireframe 생성
"""

from __future__ import annotations

from typing import AsyncGenerator

import asyncio
import time

from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.ingestion_llm_runtime import (
    get_llm,
    set_current_session,
    reset_current_session,
)
from api.features.ingestion.ingestion_sessions import IngestionSession, wait_if_paused
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.features.ingestion.workflow.phases.aggregates import extract_aggregates_phase
from api.features.ingestion.workflow.phases.bounded_contexts import identify_bounded_contexts_phase
from api.features.ingestion.workflow.phases.commands import extract_commands_phase
from api.features.ingestion.workflow.phases.events_from_user_stories import extract_events_from_user_stories_phase
from api.features.ingestion.workflow.phases.feature_grouping import feature_grouping_phase  # spec 026
from api.features.ingestion.workflow.phases.parsing import parsing_phase
from api.features.ingestion.workflow.phases.policies import identify_policies_phase
from api.features.ingestion.workflow.phases.properties import generate_properties_phase
from api.features.ingestion.workflow.phases.references import generate_property_references_phase
from api.features.ingestion.workflow.phases.readmodels import extract_readmodels_phase
from api.features.ingestion.workflow.phases.gwt import generate_gwt_phase
from api.features.ingestion.workflow.phases.extract_invariants import extract_invariants_phase  # spec 027
from api.features.ingestion.workflow.phases.ui_wireframes import generate_ui_wireframes_phase
from api.features.ingestion.workflow.phases.ui_flow_edges import generate_ui_flow_edges_phase  # spec 025
from api.features.ingestion.workflow.phases.user_stories import extract_user_stories_phase
from api.features.ingestion.workflow.phases.user_story_sequencing import assign_user_story_sequences_phase
from api.platform.env import IS_SKIP_UI_PHASE
from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger
from api.features.ingestion.workflow.utils.phase_logger import save as log_phase, save_summary as log_summary


async def _run_phase(session, ctx, phase_gen, pause_sync_target: str | None):
    """Run a single phase with cancel/pause handling. Yields ProgressEvents.

    Spec 017: every yielded event is augmented with the session's current
    `tokens` block + `suspendState` (so the floating panel updates live), and
    `session.current_phase` is tracked so the token callback can attribute
    each LLM call to the right phase. At phase exit, emit a `session_total`
    summary log for forensics (Constitution VII).
    """
    phase_start_total = int(getattr(session, "tokens_total", 0) or 0)
    phase_label_for_log = ""
    async for event in phase_gen:
        # Track phase for the token callback's per-phase aggregation.
        try:
            ev_phase = getattr(event, "phase", None)
            if ev_phase is not None:
                phase_value = getattr(ev_phase, "value", ev_phase)
                if phase_value:
                    session.current_phase = str(phase_value)
                    phase_label_for_log = session.current_phase
        except Exception:  # noqa: BLE001
            pass

        if getattr(session, "is_cancelled", False):
            # Suspend ack: flip to "suspended" before emitting the final event.
            session.suspend_state = "suspended"
            yield _augment_event(session, ProgressEvent(
                phase=IngestionPhase.ERROR,
                message="❌ 생성이 중단되었습니다",
                progress=getattr(session, "progress", 0) or 0,
                data={"error": "Cancelled by user", "cancelled": True},
            ))
            return
        if getattr(session, "is_paused", False) and session.status != IngestionPhase.PAUSED:
            yield _augment_event(session, ProgressEvent(
                phase=IngestionPhase.PAUSED,
                message="⏸️ 일시 정지됨 (채팅으로 일부를 수정한 후 재개하세요)",
                progress=getattr(session, "progress", 0) or 0,
                data={"isPaused": True},
            ))
            await wait_if_paused(session, ctx, pause_sync_target)
        yield _augment_event(session, event)

    # Spec 017 — phase-exit log: how many tokens this phase consumed.
    try:
        phase_end_total = int(getattr(session, "tokens_total", 0) or 0)
        phase_tokens = max(0, phase_end_total - phase_start_total)
        SmartLogger.log(
            "INFO",
            f"Phase {phase_label_for_log} tokens: {phase_tokens} (session total: {phase_end_total})",
            category="ingestion.tokens.session_total",
            params={
                "session_id": getattr(session, "id", None),
                "phase": phase_label_for_log,
                "phase_tokens": phase_tokens,
                "session_total": phase_end_total,
                "approximate": bool(getattr(session, "tokens_approximate", False)),
            },
        )
    except Exception:  # noqa: BLE001
        pass


def _augment_event(session: IngestionSession, ev: ProgressEvent) -> ProgressEvent:
    """Attach the session's token state + suspend_state to a ProgressEvent.

    Spec 017 SSE additions per contracts/sse-events.md:
    - `tokens.total` always (when any tally has happened)
    - `tokens.byPhase` only when at least one phase delta has changed since the
      last emit (sparse — saves SSE bytes for high-frequency events)
    - `tokens.approximate` and `tokens.lastCallTokens` always when present
    - `suspendState` always

    Mutates `session.last_progress_emit_at` and the per-phase emit snapshot
    used to compute the next byPhase delta.
    """
    # Compute byPhase delta vs. the last emitted snapshot.
    by_phase_now: dict[str, int] = dict(getattr(session, "tokens_by_phase", {}) or {})
    by_phase_last: dict[str, int] = getattr(session, "_tokens_by_phase_emit_snapshot", {}) or {}
    by_phase_delta: dict[str, int] = {
        k: v for k, v in by_phase_now.items()
        if v != by_phase_last.get(k)
    }
    if by_phase_delta:
        session._tokens_by_phase_emit_snapshot = dict(by_phase_now)

    tokens_block: dict | None = None
    if (
        getattr(session, "tokens_total", 0)
        or getattr(session, "tokens_approximate", False)
        or getattr(session, "tokens_last_call", None) is not None
    ):
        tokens_block = {
            "total": int(getattr(session, "tokens_total", 0) or 0),
            "approximate": bool(getattr(session, "tokens_approximate", False)),
        }
        last_call = getattr(session, "tokens_last_call", None)
        if last_call is not None:
            tokens_block["lastCallTokens"] = int(last_call)
        if by_phase_delta:
            tokens_block["byPhase"] = by_phase_delta

    suspend_state = getattr(session, "suspend_state", "running") or "running"

    # ProgressEvent fields are dataclass-style; we attach tokens / suspendState
    # via dataclasses.replace if those fields exist, else as attributes.
    try:
        from dataclasses import replace, is_dataclass
        if is_dataclass(ev):
            updates: dict = {}
            if hasattr(ev, "tokens"):
                updates["tokens"] = tokens_block
            if hasattr(ev, "suspendState"):
                updates["suspendState"] = suspend_state
            if updates:
                ev = replace(ev, **updates)
    except Exception:  # noqa: BLE001 — best-effort; never break the stream
        pass

    # Setattr fallback for non-dataclass / pydantic event types — frontend
    # only cares about these as JSON-serialized fields, so attribute storage
    # works for either model_dump or asdict serializers.
    try:
        if tokens_block is not None and getattr(ev, "tokens", None) != tokens_block:
            object.__setattr__(ev, "tokens", tokens_block) if False else setattr(ev, "tokens", tokens_block)
    except Exception:
        pass
    try:
        setattr(ev, "suspendState", suspend_state)
    except Exception:
        pass

    session.last_progress_emit_at = time.time()
    return ev


async def run_ingestion_workflow(session: IngestionSession, content: str) -> AsyncGenerator[ProgressEvent, None]:
    """
    Run the full ingestion workflow with streaming progress updates.

    Event Modeling chain:
      Parsing → UserStory → Sequencing → Event(per US) → BC → Aggregate → Command → EMITS 링크 → ReadModel → ...
    """
    from api.features.ingestion.event_storming.neo4j_client import get_neo4j_client

    # Spec 017: pin the active session so every nested get_llm() call inside
    # this workflow auto-attaches an IngestionTokenCallback. Reset in the
    # outer except/return paths below (this generator may exit at many points).
    _session_token = set_current_session(session)

    client = get_neo4j_client()
    llm = get_llm()
    display_language = getattr(session, "display_language", "ko") or "ko"
    source_type = getattr(session, "source_type", "rfp") or "rfp"
    ctx = IngestionWorkflowContext(
        session=session, content=content, client=client, llm=llm,
        display_language=display_language, source_type=source_type,
    )

    try:
        SmartLogger.log(
            "INFO",
            "Ingestion workflow started (Event Modeling chain)",
            category="ingestion.workflow",
            params={"session_id": session.id, "content_length": len(content), "source_type": source_type},
        )

        # 1. Parsing
        async for ev in _run_phase(session, ctx, parsing_phase(ctx), "user_stories"):
            if ev.phase == IngestionPhase.ERROR:
                yield ev; return
            yield ev

        # 2. UserStory 추출
        async for ev in _run_phase(session, ctx, extract_user_stories_phase(ctx), "user_stories"):
            if ev.phase == IngestionPhase.ERROR:
                yield ev; return
            yield ev
        log_phase(ctx, "01_user_stories")

        # 3. UserStory 시퀀스 할당
        async for ev in _run_phase(session, ctx, assign_user_story_sequences_phase(ctx), "events"):
            if ev.phase == IngestionPhase.ERROR:
                yield ev; return
            yield ev

        # 4. Event 추출 (per UserStory, Command 없이)
        async for ev in _run_phase(session, ctx, extract_events_from_user_stories_phase(ctx), "events"):
            if ev.phase == IngestionPhase.ERROR:
                yield ev; return
            yield ev
        log_phase(ctx, "02_events_from_us")

        # 5. BoundedContext 식별
        async for ev in _run_phase(session, ctx, identify_bounded_contexts_phase(ctx), "aggregates"):
            if ev.phase == IngestionPhase.ERROR:
                yield ev; return
            yield ev
        log_phase(ctx, "03_bounded_contexts")

        # 5b. Feature 묶음 (spec 026) — BC 분류 직후, Aggregate 추출 이전
        async for ev in _run_phase(session, ctx, feature_grouping_phase(ctx), "aggregates"):
            if ev.phase == IngestionPhase.ERROR:
                yield ev; return
            yield ev
        log_phase(ctx, "03b_feature_grouping")

        # 6. Aggregate 추출
        async for ev in _run_phase(session, ctx, extract_aggregates_phase(ctx), "commands"):
            if ev.phase == IngestionPhase.ERROR:
                yield ev; return
            yield ev
        log_phase(ctx, "04_aggregates")

        # 7. Command 추출 (emits_event_names로 EMITS 직접 연결 포함)
        async for ev in _run_phase(session, ctx, extract_commands_phase(ctx), "readmodels"):
            if ev.phase == IngestionPhase.ERROR:
                yield ev; return
            yield ev
        log_phase(ctx, "05_commands")

        # 8. ReadModel 추출
        async for ev in _run_phase(session, ctx, extract_readmodels_phase(ctx), "properties"):
            if ev.phase == IngestionPhase.ERROR:
                yield ev; return
            yield ev
        log_phase(ctx, "06_readmodels")

        # 10. Properties 생성
        async for ev in _run_phase(session, ctx, generate_properties_phase(ctx), "policies"):
            if ev.phase == IngestionPhase.ERROR:
                yield ev; return
            yield ev
        log_phase(ctx, "07_properties")

        # 11. Property References
        async for ev in _run_phase(session, ctx, generate_property_references_phase(ctx), "policies"):
            if ev.phase == IngestionPhase.ERROR:
                yield ev; return
            yield ev
        log_phase(ctx, "08_references")

        # 12. Policy 식별
        async for ev in _run_phase(session, ctx, identify_policies_phase(ctx), "policies"):
            if ev.phase == IngestionPhase.ERROR:
                yield ev; return
            yield ev
        log_phase(ctx, "09_policies")

        # 13. GWT 생성
        async for ev in _run_phase(session, ctx, generate_gwt_phase(ctx), None):
            if ev.phase == IngestionPhase.ERROR:
                yield ev; return
            yield ev
        log_phase(ctx, "10_gwt")

        # 13b. 어그리거트 인베리언트 추출 (spec 027) — GWT 생성 직후
        async for ev in _run_phase(session, ctx, extract_invariants_phase(ctx), None):
            if ev.phase == IngestionPhase.ERROR:
                yield ev; return
            yield ev
        log_phase(ctx, "10b_invariants")

        # 14. UI Wireframe 생성
        if IS_SKIP_UI_PHASE:
            if getattr(session, "is_paused", False) and session.status != IngestionPhase.PAUSED:
                yield _augment_event(session, ProgressEvent(
                    phase=IngestionPhase.PAUSED,
                    message="⏸️ 일시 정지됨",
                    progress=getattr(session, "progress", 0) or 0,
                    data={"isPaused": True},
                ))
                await wait_if_paused(session, ctx, None)
            yield _augment_event(session, ProgressEvent(
                phase=IngestionPhase.GENERATING_UI,
                message="UI 단계 생략됨 (IS_SKIP_UI_PHASE=true)",
                progress=92,
                data={"skipped": True},
            ))
        else:
            async for ev in _run_phase(session, ctx, generate_ui_wireframes_phase(ctx), None):
                if ev.phase == IngestionPhase.ERROR:
                    yield ev; return
                yield ev

        log_phase(ctx, "11_ui_wireframes")

        # 15. UI Flow Edges (spec 025) — only run if there are UIs to wire up
        if not IS_SKIP_UI_PHASE:
            async for ev in _run_phase(session, ctx, generate_ui_flow_edges_phase(ctx), None):
                if ev.phase == IngestionPhase.ERROR:
                    yield ev; return
                yield ev
            log_phase(ctx, "12_ui_flow_edges")

        log_summary(ctx)

        # Complete — 실제 Neo4j에 생성된 Policy 수 카운트
        events_from_us_count = len(getattr(ctx, "events_from_us", []) or [])
        events_from_cmd_count = sum(len(evts) for evts in ctx.events_by_agg.values())

        created_policy_count = 0
        try:
            with get_session() as _count_session:
                _pol_count = _count_session.run("MATCH (p:Policy) RETURN count(p) AS cnt").single()
                created_policy_count = _pol_count["cnt"] if _pol_count else 0
        except Exception:
            created_policy_count = len(ctx.policies)  # fallback

        # spec 025 — UI-flow counters (populated by generate_ui_flow_edges_phase)
        ui_flow_summary = getattr(ctx, "ui_flow_summary", None) or {}

        yield _augment_event(session, ProgressEvent(
            phase=IngestionPhase.COMPLETE,
            message="✅ 모델 생성 완료!",
            progress=100,
            data={
                "summary": {
                    "user_stories": len(ctx.user_stories),
                    "bounded_contexts": len(ctx.bounded_contexts),
                    "aggregates": sum(len(aggs) for aggs in ctx.aggregates_by_bc.values()),
                    "commands": sum(len(cmds) for cmds in ctx.commands_by_agg.values()),
                    "events": events_from_us_count + events_from_cmd_count,
                    "readmodels": sum(len(rms) for rms in (getattr(ctx, "readmodels_by_bc", {}) or {}).values()),
                    "uis": len(getattr(ctx, "uis", []) or []),
                    "policies": created_policy_count,
                    # spec 025 — UI flow layer counters
                    "journeys_created": int(ui_flow_summary.get("journeys_created", 0)),
                    "next_ui_edges_created": int(ui_flow_summary.get("next_ui_edges_created", 0)),
                    "gateways_created": int(ui_flow_summary.get("gateways_created", 0)),
                    "ui_flow_warnings": dict(ui_flow_summary.get("warnings_by_code", {})),
                }
            },
        ))
        SmartLogger.log(
            "INFO",
            "Ingestion workflow complete",
            category="ingestion.workflow",
            params={
                "session_id": session.id,
                "user_stories": len(ctx.user_stories),
                "bounded_contexts": len(ctx.bounded_contexts),
                "events_from_us": events_from_us_count,
                "events_from_cmd": events_from_cmd_count,
            },
        )

    except asyncio.CancelledError:
        # Spec 017 FR-005: cooperative suspend via session_call_slot. Normal
        # termination, not an error.
        SmartLogger.log(
            "INFO",
            "Ingestion suspended (cooperative cancel via session_call_slot)",
            category="ingestion.suspend.workflow",
            params={
                "session_id": session.id,
                "session_total_tokens": int(getattr(session, "tokens_total", 0) or 0),
            },
        )
        session.suspend_state = "suspended"
        yield _augment_event(session, ProgressEvent(
            phase=IngestionPhase.ERROR,
            message="❌ 생성이 중단되었습니다 (취소됨)",
            progress=getattr(session, "progress", 0) or 0,
            data={"error": "Cancelled by user", "cancelled": True},
        ))
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        SmartLogger.log(
            "ERROR",
            "Ingestion workflow failed",
            category="ingestion.workflow",
            params={
                "session_id": session.id,
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": error_trace,
            },
        )
        yield _augment_event(session, ProgressEvent(
            phase=IngestionPhase.ERROR,
            message=f"❌ 오류 발생: {str(e)}",
            progress=0,
            data={"error": str(e)},
        ))
    finally:
        # Spec 017: clear the workflow's session context so subsequent get_llm()
        # calls (e.g. /api/chat/modify) don't accidentally inherit this
        # workflow's token callback.
        try:
            reset_current_session(_session_token)
        except Exception:  # noqa: BLE001
            pass
