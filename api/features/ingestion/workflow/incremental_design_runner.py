"""Incremental design runner (034 — US7 설계 자동 반영).

기존 인제스천 워크플로의 **설계 단계를 선택된 User Story에 대해서만** 실행한다.
문서 업로드 대신 그래프의 기존 US·BC·Aggregate를 hydrate(resume 메커니즘)하고,
대상 US로 한정해 **워크플로 정순(이벤트 도출 → Aggregate → Command → ReadModel)** 으로
기존 phase 함수를 그대로 호출한다. 전체 워크플로와 달리 **그래프를 clear하지 않아**
기존 설계를 보존하며, 기존 BC/Aggregate는 MERGE 키로 재사용된다.

`/api/ingest/stream/{session_id}` SSE로 흘러나가므로 프런트는 기존 인제스천 진행 UI를
그대로 재사용한다.
"""

from __future__ import annotations

from typing import Any, AsyncGenerator

from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.ingestion_llm_runtime import (
    get_llm,
    reset_current_session,
    set_current_session,
)
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.features.ingestion.workflow.phases.aggregates import extract_aggregates_phase
from api.features.ingestion.workflow.phases.commands import extract_commands_phase
from api.features.ingestion.workflow.phases.events_from_user_stories import (
    extract_events_from_user_stories_phase,
)
from api.features.ingestion.workflow.phases.readmodels import extract_readmodels_phase
from api.platform.observability.smart_logger import SmartLogger


async def run_design_for_user_stories(
    session: Any, user_story_ids: list[str]
) -> AsyncGenerator[ProgressEvent, None]:
    """선택된 US에 대해 설계 단계(events→aggregate→command→readmodel)를 정순 실행."""
    # 런너 헬퍼는 지역 import로 (순환 방지).
    from api.features.ingestion.event_storming.neo4j_client import get_neo4j_client
    from api.features.ingestion.ingestion_workflow_runner import _augment_event, _run_phase

    _tok = set_current_session(session)
    client = get_neo4j_client()
    llm = get_llm()
    targets = {i for i in (user_story_ids or []) if i}
    ctx = IngestionWorkflowContext(
        session=session,
        content="",
        client=client,
        llm=llm,
        display_language=getattr(session, "display_language", "ko") or "ko",
        source_type=getattr(session, "source_type", "rfp") or "rfp",
    )
    try:
        yield _augment_event(session, ProgressEvent(
            phase=IngestionPhase.PARSING, message="기존 모델 로드 중…", progress=2,
            data={"type": "IncrementalDesign"},
        ))

        # 기존 US·BC·Aggregate 로드 (clear하지 않음 — 기존 설계 보존)
        ctx.sync_from_neo4j(up_to_phase="readmodels")

        # 대상 US로 한정
        ctx.user_stories = [us for us in (ctx.user_stories or []) if getattr(us, "id", None) in targets]
        if not ctx.user_stories:
            yield _augment_event(session, ProgressEvent(
                phase=IngestionPhase.COMPLETE, message="반영할 User Story가 없습니다.",
                progress=100, data={"summary": {"userStories": 0}},
            ))
            return

        # 대상 US가 속한 BC만 남기고(나머지 BC·Aggregate는 ctx에서 제거),
        # 남긴 BC의 userStoryIds도 대상으로 한정 → per-BC phase가 gap(delta)만 처리.
        target_bc_ids: set[str] = set()
        kept_bcs = []
        for bc in ctx.bounded_contexts or []:
            if not isinstance(bc, dict):
                continue
            ids = [i for i in (bc.get("userStoryIds") or bc.get("user_story_ids") or []) if i in targets]
            if not ids:
                continue  # 대상 US 없는 BC는 통째로 제외(재처리 방지)
            bc["user_story_ids"] = ids
            bc["userStoryIds"] = ids
            kept_bcs.append(bc)
            if bc.get("id"):
                target_bc_ids.add(bc["id"])
        ctx.bounded_contexts = kept_bcs
        # 대상 BC의 기존 Aggregate만 유지(Command가 붙을 수 있게), 나머지는 제거.
        ctx.aggregates_by_bc = {
            bc_id: aggs for bc_id, aggs in (ctx.aggregates_by_bc or {}).items() if bc_id in target_bc_ids
        }

        SmartLogger.log(
            "INFO",
            f"Incremental design for {len(ctx.user_stories)} US across {len(target_bc_ids)} BC.",
            category="ingestion.incremental_design",
            params={"session_id": session.id, "us": len(ctx.user_stories), "bcs": len(target_bc_ids)},
        )

        # 워크플로 정순: ① 이벤트 도출 → ② Aggregate → ③ Command → ④ ReadModel
        async for ev in _run_phase(session, ctx, extract_events_from_user_stories_phase(ctx), "events"):
            yield ev
        async for ev in _run_phase(session, ctx, extract_aggregates_phase(ctx), "commands"):
            yield ev
        async for ev in _run_phase(session, ctx, extract_commands_phase(ctx), "readmodels"):
            yield ev
        async for ev in _run_phase(session, ctx, extract_readmodels_phase(ctx), None):
            yield ev

        # 사후 커버리지 보강 (조회성 US → 기존 ReadModel 등)
        try:
            from api.features.ingestion.workflow.post_coverage import reconcile_best_effort

            reconcile_best_effort(list(target_bc_ids) or None)
        except Exception:  # noqa: BLE001 — best-effort
            pass

        # 완료 summary — 프런트 카운트 그리드가 읽는 snake_case 키로 실제 생성 수를
        # 그래프에서 집계(대상 BC 기준). 기존엔 {"userStories": N}만 보내 모달이 전부
        # 0으로 표시됐음.
        summary = {
            "user_stories": len(ctx.user_stories),
            "bounded_contexts": len(target_bc_ids),
            "aggregates": 0, "commands": 0, "events": 0, "read_models": 0,
            # reflect 단계는 정책/UI를 생성하지 않으므로 0으로 명시(undefined→빈칸 방지).
            "policies": 0, "uis": 0,
        }
        try:
            from api.platform.neo4j import get_session as _neo4j_session

            bcs = list(target_bc_ids)
            if bcs:
                with _neo4j_session() as _s:
                    rec = _s.run(
                        """
                        MATCH (bc:BoundedContext) WHERE bc.id IN $bcs
                        OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(agg:Aggregate)
                        OPTIONAL MATCH (agg)-[:HAS_COMMAND]->(cmd:Command)
                        OPTIONAL MATCH (cmd)-[:EMITS]->(evt:Event)
                        OPTIONAL MATCH (bc)-[:HAS_READMODEL]->(rm:ReadModel)
                        RETURN count(DISTINCT agg) AS aggs, count(DISTINCT cmd) AS cmds,
                               count(DISTINCT evt) AS evts, count(DISTINCT rm) AS rms
                        """,
                        bcs=bcs,
                    ).single()
                    if rec:
                        summary["aggregates"] = rec["aggs"]
                        summary["commands"] = rec["cmds"]
                        summary["events"] = rec["evts"]
                        summary["read_models"] = rec["rms"]
        except Exception:  # noqa: BLE001 — 카운트는 best-effort(표시용)
            pass

        yield _augment_event(session, ProgressEvent(
            phase=IngestionPhase.COMPLETE, message="✅ 설계 반영 완료!", progress=100,
            data={"summary": summary},
        ))
    except Exception as e:  # noqa: BLE001
        SmartLogger.log(
            "ERROR", f"Incremental design failed: {e}",
            category="ingestion.incremental_design", params={"session_id": session.id, "error": str(e)},
        )
        yield _augment_event(session, ProgressEvent(
            phase=IngestionPhase.ERROR, message=f"❌ 오류: {e}",
            progress=getattr(session, "progress", 0) or 0, data={"error": str(e)},
        ))
    finally:
        reset_current_session(_tok)
