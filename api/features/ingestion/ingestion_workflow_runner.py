"""
Ingestion Workflow Runner (streaming)

Business capability: convert uploaded requirements text into an Event Storming model in Neo4j,
emitting real-time progress events for the UI (SSE).
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
from api.features.ingestion.workflow.phases.events import extract_events_phase
from api.features.ingestion.workflow.phases.parsing import parsing_phase
from api.features.ingestion.workflow.phases.policies import identify_policies_phase
from api.features.ingestion.workflow.phases.properties import generate_properties_phase
from api.features.ingestion.workflow.phases.references import generate_property_references_phase
from api.features.ingestion.workflow.phases.readmodels import extract_readmodels_phase
from api.features.ingestion.workflow.phases.gwt import generate_gwt_phase
from api.features.ingestion.workflow.phases.ui_wireframes import generate_ui_wireframes_phase
from api.features.ingestion.workflow.phases.user_stories import extract_user_stories_phase
from api.platform.env import IS_SKIP_UI_PHASE
from api.platform.observability.smart_logger import SmartLogger


async def run_ingestion_workflow(session: IngestionSession, content: str) -> AsyncGenerator[ProgressEvent, None]:
    """
    Run the full ingestion workflow with streaming progress updates.
    """
    from api.features.ingestion.event_storming.neo4j_client import get_neo4j_client

    client = get_neo4j_client()
    llm = get_llm()
    ctx = IngestionWorkflowContext(session=session, content=content, client=client, llm=llm)

    try:
        SmartLogger.log(
            "INFO",
            "Ingestion workflow started",
            category="ingestion.workflow",
            params={"session_id": session.id, "content_length": len(content)},
        )

        async for event in parsing_phase(ctx):
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
                await wait_if_paused(session)
            yield event

        async for event in extract_user_stories_phase(ctx):
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
                await wait_if_paused(session)
            yield event

        async for event in identify_bounded_contexts_phase(ctx):
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
                await wait_if_paused(session)
            yield event

        async for event in extract_aggregates_phase(ctx):
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
                await wait_if_paused(session)
            yield event

        async for event in extract_commands_phase(ctx):
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
                await wait_if_paused(session)
            yield event

        async for event in extract_events_phase(ctx):
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
                await wait_if_paused(session)
            yield event

        async for event in extract_readmodels_phase(ctx):
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
                await wait_if_paused(session)
            yield event

        async for event in generate_properties_phase(ctx):
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
                await wait_if_paused(session)
            yield event

        async for event in generate_property_references_phase(ctx):
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
                await wait_if_paused(session)
            yield event

        # Policy phase MUST run before UI phase so we can exclude policy-invoked commands from UI generation
        async for event in identify_policies_phase(ctx):
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
                await wait_if_paused(session)
            yield event

        # Generate GWT (Given/When/Then) for Commands and Policies
        async for event in generate_gwt_phase(ctx):
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
                await wait_if_paused(session)
            yield event

        if IS_SKIP_UI_PHASE:
            if getattr(session, "is_paused", False) and session.status != IngestionPhase.PAUSED:
                yield ProgressEvent(
                    phase=IngestionPhase.PAUSED,
                    message="⏸️ 일시 정지됨 (채팅으로 일부를 수정한 후 재개하세요)",
                    progress=getattr(session, "progress", 0) or 0,
                    data={"isPaused": True},
                )
                await wait_if_paused(session)

            yield ProgressEvent(
                phase=IngestionPhase.GENERATING_UI,
                message="UI 단계 생략됨 (IS_SKIP_UI_PHASE=true)",
                progress=92,
                data={"skipped": True},
            )
        else:
            async for event in generate_ui_wireframes_phase(ctx):
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
                    await wait_if_paused(session)
                yield event

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
                    "readmodels": sum(len(rms) for rms in (getattr(ctx, "readmodels_by_bc", {}) or {}).values()),
                    "uis": len(getattr(ctx, "uis", []) or []),
                    "events": sum(len(evts) for evts in ctx.events_by_agg.values()),
                    "policies": len(ctx.policies),
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
                "aggregates": sum(len(aggs) for aggs in ctx.aggregates_by_bc.values()),
                "commands": sum(len(cmds) for cmds in ctx.commands_by_agg.values()),
                "readmodels": sum(len(rms) for rms in (getattr(ctx, "readmodels_by_bc", {}) or {}).values()),
                "events": sum(len(evts) for evts in ctx.events_by_agg.values()),
                "policies": len(ctx.policies),
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


