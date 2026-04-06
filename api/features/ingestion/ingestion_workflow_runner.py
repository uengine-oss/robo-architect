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

from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.ingestion_llm_runtime import get_llm
from api.features.ingestion.ingestion_sessions import IngestionSession, wait_if_paused
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.features.ingestion.workflow.phases.aggregates import extract_aggregates_phase
from api.features.ingestion.workflow.phases.bounded_contexts import identify_bounded_contexts_phase
from api.features.ingestion.workflow.phases.commands import extract_commands_phase
from api.features.ingestion.workflow.phases.events_from_user_stories import extract_events_from_user_stories_phase
from api.features.ingestion.workflow.phases.parsing import parsing_phase
from api.features.ingestion.workflow.phases.policies import identify_policies_phase
from api.features.ingestion.workflow.phases.properties import generate_properties_phase
from api.features.ingestion.workflow.phases.references import generate_property_references_phase
from api.features.ingestion.workflow.phases.readmodels import extract_readmodels_phase
from api.features.ingestion.workflow.phases.gwt import generate_gwt_phase
from api.features.ingestion.workflow.phases.ui_wireframes import generate_ui_wireframes_phase
from api.features.ingestion.workflow.phases.user_stories import extract_user_stories_phase
from api.features.ingestion.workflow.phases.user_story_sequencing import assign_user_story_sequences_phase
from api.platform.env import IS_SKIP_UI_PHASE
from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger
from api.features.ingestion.workflow.utils.phase_logger import save as log_phase, save_summary as log_summary


async def _run_phase(session, ctx, phase_gen, pause_sync_target: str | None):
    """Run a single phase with cancel/pause handling. Yields ProgressEvents."""
    async for event in phase_gen:
        if getattr(session, "is_cancelled", False):
            yield ProgressEvent(
                phase=IngestionPhase.ERROR,
                message="❌ 생성이 중단되었습니다",
                progress=getattr(session, "progress", 0) or 0,
                data={"error": "Cancelled by user", "cancelled": True},
            )
            return
        if getattr(session, "is_paused", False) and session.status != IngestionPhase.PAUSED:
            yield ProgressEvent(
                phase=IngestionPhase.PAUSED,
                message="⏸️ 일시 정지됨 (채팅으로 일부를 수정한 후 재개하세요)",
                progress=getattr(session, "progress", 0) or 0,
                data={"isPaused": True},
            )
            await wait_if_paused(session, ctx, pause_sync_target)
        yield event


async def run_ingestion_workflow(session: IngestionSession, content: str) -> AsyncGenerator[ProgressEvent, None]:
    """
    Run the full ingestion workflow with streaming progress updates.

    Event Modeling chain:
      Parsing → UserStory → Sequencing → Event(per US) → BC → Aggregate → Command → EMITS 링크 → ReadModel → ...
    """
    from api.features.ingestion.event_storming.neo4j_client import get_neo4j_client

    client = get_neo4j_client()
    llm = get_llm()
    display_language = getattr(session, "display_language", "ko") or "ko"
    source_type = getattr(session, "source_type", "rfp") or "rfp"
    ctx = IngestionWorkflowContext(
        session=session, content=content, client=client, llm=llm,
        display_language=display_language, source_type=source_type,
    )

    if source_type == "legacy_report":
        from api.features.ingestion.legacy_report.report_parser import parse_legacy_report
        ctx.source_report = parse_legacy_report(content)
    elif source_type == "analyzer_graph":
        from api.features.ingestion.analyzer_graph.graph_to_report import build_report_from_graph
        ctx.source_report = build_report_from_graph()

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

        # 14. UI Wireframe 생성
        if IS_SKIP_UI_PHASE:
            if getattr(session, "is_paused", False) and session.status != IngestionPhase.PAUSED:
                yield ProgressEvent(
                    phase=IngestionPhase.PAUSED,
                    message="⏸️ 일시 정지됨",
                    progress=getattr(session, "progress", 0) or 0,
                    data={"isPaused": True},
                )
                await wait_if_paused(session, ctx, None)
            yield ProgressEvent(
                phase=IngestionPhase.GENERATING_UI,
                message="UI 단계 생략됨 (IS_SKIP_UI_PHASE=true)",
                progress=92,
                data={"skipped": True},
            )
        else:
            async for ev in _run_phase(session, ctx, generate_ui_wireframes_phase(ctx), None):
                if ev.phase == IngestionPhase.ERROR:
                    yield ev; return
                yield ev

        log_phase(ctx, "11_ui_wireframes")
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

        yield ProgressEvent(
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
                }
            },
        )
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
        yield ProgressEvent(phase=IngestionPhase.ERROR, message=f"❌ 오류 발생: {str(e)}", progress=0, data={"error": str(e)})
