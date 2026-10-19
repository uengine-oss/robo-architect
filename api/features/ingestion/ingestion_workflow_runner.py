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

from typing import AsyncGenerator, Optional

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
from api.features.ingestion.replacement import capture_before_replace, safe_counts
from api.features.ingestion import runs
from api.platform.observability.smart_logger import SmartLogger
from api.features.ingestion.workflow.utils.phase_logger import save as log_phase, save_summary as log_summary


# Event Storming 노드 라벨 (ingestion이 생성하는 것들만)
# FUNCTION, BusinessLogic, Actor, Table, Column 등 분석 그래프 노드는 제외
# Every event-storming node label. A fresh ingestion wipes all of these
# (single-model semantics) while leaving the analyzer code-analysis graph
# (FUNCTION / Rule / Table / Example …) and hybrid BPM nodes untouched.
# Keep in sync with ALL_CLEARED_LABELS in promote_to_es.py.
_ES_LABELS = [
    "UserStory", "BoundedContext", "Aggregate", "Command", "Event",
    "ReadModel", "Policy", "Property", "CQRSConfig", "CQRSOperation",
    "UI", "GWT", "Feature", "Invariant",
    # spec 025 의 사용자 여정. **빠져 있었다**(2026-10-07 측정).
    #
    # 적재는 교체다 — 그런데 이 둘이 목록에 없어서 재적재 때 살아남았다. 그리고
    # 여정의 걸음은 `(:JourneyStep)-[:SHOWS]->(:UI)` 로 화면을 가리키는데 **그 UI 는
    # 지워진다.** 즉 다시 적재할수록 **어디도 가리키지 않는 여정**이 쌓인다.
    # 목록 끝에 둔다 — 지우기는 `reversed()` 로 돌아 잎부터 떼기 때문이다.
    "Journey", "JourneyStep",
]


def clear_event_storming_nodes(client, session_id: str = "") -> None:
    """Delete all event storming nodes while preserving analyzer graph nodes."""
    with client.session() as s:
        # Count before
        counts = {}
        for label in _ES_LABELS:
            r = s.run(f"MATCH (n:{label}) RETURN count(n) AS c").single()
            if r and r["c"] > 0:
                counts[label] = r["c"]

        if not counts:
            SmartLogger.log(
                "INFO", "No previous event storming data to clear",
                category="ingestion.workflow.clear_previous",
                params={"session_id": session_id},
            )
            return

        # Delete in dependency order (leaf nodes first)
        for label in reversed(_ES_LABELS):
            s.run(f"MATCH (n:{label}) DETACH DELETE n")

        SmartLogger.log(
            "INFO",
            f"Cleared previous event storming data: {counts}",
            category="ingestion.workflow.clear_previous",
            params={"session_id": session_id, "deleted": counts},
        )


def tag_all_es_nodes(client, session_id: str) -> None:
    """Stamp every event-storming node with this run's `session_id`.

    Runs at the end of the workflow so the whole model — standard *and*
    hybrid paths — carries one unified `session_id`. The per-phase upserts
    only tag some labels (Feature/Invariant set it themselves; BC/UserStory/
    Command/Event/… don't), so this closing pass makes every node consistent.
    Safe because `clear_event_storming_nodes` wiped the graph at the start —
    everything present now belongs to this session.
    """
    if not session_id:
        return
    with client.session() as s:
        for label in _ES_LABELS:
            s.run(f"MATCH (n:{label}) SET n.session_id = $sid", sid=session_id)


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

    # ── 실패로 끝나도 **무엇이 빠졌는지** 싣는다 ──────────────────────────
    #
    # 완료 이벤트에만 붙이면, 정작 가장 아픈 때(중간에 죽은 때)에 화면이 오류 문구
    # 한 줄만 받는다. 2026-10-15 에 그랬다 — LLM 크레딧이 떨어져 ES 가 죽었는데
    # 그때까지 건너뛴 것들은 아무 데도 안 실렸다. 기록은 여기서 닫히므로 완료
    # 경로에서 다시 불러도 빈 값이 온다(한 번만 닫힌다).
    if getattr(ev, "phase", None) == IngestionPhase.ERROR:
        try:
            from api.features.ingestion.workflow import skip_ledger

            _skipped = skip_ledger.finish(session.id)
            if _skipped:
                _data = dict(getattr(ev, "data", None) or {})
                _data["skipped"] = _skipped
                try:
                    from dataclasses import replace as _replace, is_dataclass as _is_dc
                    ev = _replace(ev, data=_data) if _is_dc(ev) else ev
                    if not _is_dc(ev):
                        ev.data = _data
                except Exception:  # noqa: BLE001
                    try:
                        ev.data = _data
                    except Exception:  # noqa: BLE001
                        pass
        except Exception:  # noqa: BLE001 — 기록이 스트림을 막지 않는다
            pass

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
    # 적재 기록. 강제 종료되면 이 행만 남는다 — 아래 지우기 **직전에** 채운다.
    run_id: Optional[str] = None
    beater: Optional[runs.Heartbeat] = None

    client = get_neo4j_client()
    llm = get_llm()
    display_language = getattr(session, "display_language", "ko") or "ko"
    source_type = getattr(session, "source_type", "rfp") or "rfp"
    ctx = IngestionWorkflowContext(
        session=session, content=content, client=client, llm=llm,
        display_language=display_language, source_type=source_type,
    )

    try:
        # **빠지는 것을 여기서부터 센다.** 단계들이 남기는 skip/error 로그를 주워
        # 완료 이벤트의 `summary.skipped` 로 올린다 — 조용히 사라지지 않게
        # (ISS-28 · done12 §233). 기록이 실패해도 인제스천은 그대로 간다.
        try:
            from api.features.ingestion.workflow import skip_ledger

            skip_ledger.start(session.id)
        except Exception:  # noqa: BLE001
            pass

        SmartLogger.log(
            "INFO",
            "Ingestion workflow started (Event Modeling chain)",
            category="ingestion.workflow",
            params={"session_id": session.id, "content_length": len(content), "source_type": source_type},
        )

        # 0. 기존 이벤트스토밍 결과 삭제 (분석 그래프는 보존)
        #    지우기 **직전에** 현재 판을 산출물로 조립해 보관한다. 교체 자체는
        #    원래부터 이 자리에서 일어나고 있었다 — 없던 것은 되찾을 방법이다.
        try:
            # **지우기 전에** 돌고 있다는 사실을 Postgres 에 적는다 — 앱이 강제
            # 종료되면 그 행만 남아 다음 사람에게 무슨 일이 있었는지 말한다
            # (`runs.py`). 지워질 건수도 지우기 전에만 셀 수 있다.
            wiped = safe_counts()
            run_id = runs.start(None, session.id, uid=getattr(session, "uid", None),
                                kind="standard", counts=wiped)
            beater = runs.heartbeat(run_id)
            saved = capture_before_replace(reason="ingest", counts=wiped)
            runs.note(run_id, snapshots=[m.get("snapshotKey") for m in (saved or [])])
            clear_event_storming_nodes(client, session.id)
            yield ProgressEvent(
                phase=IngestionPhase.PARSING,
                message="이전 생성 결과 초기화 완료",
                progress=1,
                data={"type": "ClearAll", "cleared": True},
            )
        except Exception as e:
            SmartLogger.log(
                "WARN",
                f"Failed to clear previous event storming data: {e}",
                category="ingestion.workflow.clear_previous",
                params={"session_id": session.id, "error": str(e)},
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

        # Hybrid (Phase 5) post-workflow hook: tag ES nodes with session_id,
        # attach (BpmTask)-[:PROMOTED_TO]->(UserStory), detect cross-BC Policies.
        if source_type == "hybrid":
            from api.features.ingestion.hybrid.event_storming_bridge.promote_to_es import (
                hybrid_post_workflow_hook,
            )
            hsid = getattr(session, "hybrid_source_session_id", None)
            if hsid:
                async for ev in hybrid_post_workflow_hook(hsid):
                    yield ev

        # Unify session_id across every ES node this run produced (standard +
        # hybrid). Done last so post-hook nodes (cross-BC Policy, …) are covered.
        try:
            tag_all_es_nodes(client, session.id)
        except Exception as e:  # noqa: BLE001 — tagging is best-effort
            SmartLogger.log(
                "WARN",
                f"Failed to tag ES nodes with session_id: {e}",
                category="ingestion.workflow.tag_session",
                params={"session_id": session.id, "error": str(e)},
            )

        # 사후 검증·복구 — 인제스천 단계가 누락한 US→Command/ReadModel IMPLEMENTS
        # 링크를 기존 객체에 매핑해 보강(고아 US 검증 체크리스트). best-effort.
        try:
            from api.features.ingestion.workflow.post_coverage import reconcile_best_effort

            # reconcile_bc does synchronous LLM .invoke() — run off the event
            # loop so it can't freeze the server while OpenAI is slow.
            await asyncio.to_thread(reconcile_best_effort)
        except Exception as e:  # noqa: BLE001 — best-effort, never break ingestion
            SmartLogger.log(
                "WARN",
                f"Post-ingestion coverage step failed: {e}",
                category="ingestion.post_coverage",
                params={"session_id": session.id, "error": str(e)},
            )

        # Complete — 실제 Neo4j에 생성된 Policy 수 카운트
        events_from_us_count = len(getattr(ctx, "events_from_us", []) or [])
        events_from_cmd_count = sum(len(evts) for evts in ctx.events_by_agg.values())

        # ── 저장된 것을 **그래프에서** 센다 ───────────────────────────────
        #
        # 메모리 맥락으로 세면 두 가지가 틀린다.
        #   ① events 를 두 출처에서 더하게 된다 — `events_from_us`(만든 수)와
        #      `events_by_agg`(그것을 **그래프에서 다시 읽은** 것)는 같은 노드다.
        #      2026-10-15 실측: 64 + 46 = **110**, 그래프에는 **64**.
        #   ② 쓰기가 실패해도 메모리에는 남아 숫자가 줄지 않는다. 같은 세션에
        #      neo4j 오류 24건(pg_type 충돌·교착)이 났는데 화면은 초록이었다.
        #
        # 그래서 **보여 주는 수는 저장된 수**다. 만든 수는 `generated` 로 같이 보내고,
        # 둘이 다르면 `missing` 에 남긴다 — 조용히 사라지지 않게.
        _STORED_LABELS = {
            "user_stories": "UserStory",
            "bounded_contexts": "BoundedContext",
            "aggregates": "Aggregate",
            "commands": "Command",
            "events": "Event",
            "readmodels": "ReadModel",
            "uis": "UI",
            "policies": "Policy",
        }

        def _stored_counts() -> dict[str, int]:
            """세션에 실제로 남은 노드 수. 실패하면 빈 dict 를 준다."""
            out: dict[str, int] = {}
            try:
                with get_session() as _s:
                    for key, label in _STORED_LABELS.items():
                        row = _s.run(
                            f"MATCH (n:{label} {{session_id: $sid}}) RETURN count(n) AS cnt",
                            sid=session.id,
                        ).single()
                        out[key] = int(row["cnt"]) if row else 0
            except Exception as _e:  # noqa: BLE001 — 세기에 실패해도 완료는 막지 않는다
                SmartLogger.log(
                    "WARN",
                    f"Failed to count stored nodes: {_e}",
                    category="ingestion.workflow.stored_counts.error",
                    params={"session_id": session.id, "error": str(_e)},
                )
                return {}
            return out

        stored = _stored_counts()

        def _unused_inputs() -> dict[str, int]:
            """쓰이지 않은 **입력**. 만든 것이 아니라 **안 쓴 것**을 센다.

            2026-10-15 실측: 문서 조각 45개 중 12개(27%)가 어느 Task 에도 안 붙었고,
            용어 30개는 엣지가 0이었다. 적게 나온 것(=missing)과 **성격이 다르다** —
            이쪽은 "줬는데 안 썼다" 이고, 버린 것이 맞는지는 사람만 안다.
            """
            out: dict[str, int] = {}
            try:
                with get_session() as _s:
                    row = _s.run(
                        "MATCH (d:DocumentPassage {session_id: $sid}) "
                        "WHERE NOT ()-[:SOURCED_FROM]->(d) RETURN count(d) AS cnt",
                        sid=session.id,
                    ).single()
                    out["document_passages"] = int(row["cnt"]) if row else 0
                    row = _s.run(
                        "MATCH (g:GlossaryTerm {session_id: $sid}) "
                        "WHERE NOT (g)--() RETURN count(g) AS cnt",
                        sid=session.id,
                    ).single()
                    out["glossary_terms"] = int(row["cnt"]) if row else 0
            except Exception as _e:  # noqa: BLE001 — 세기에 실패해도 완료는 막지 않는다
                SmartLogger.log(
                    "WARN",
                    f"Failed to count unused inputs: {_e}",
                    category="ingestion.workflow.unused_inputs.error",
                    params={"session_id": session.id, "error": str(_e)},
                )
                return {}
            return {k: v for k, v in out.items() if v > 0}

        def _policy_prohibition_review() -> dict:
            """금지가 걸린 커맨드를 자동 실행하는 정책을 **세어서 보여 준다**.

            판정하지 않는다 — "모순이다" 라고 말하려면 금지의 조건과 트리거 사건이
            같은 것인지 알아야 하고, 그것은 낱말 맞추기로 되지 않는다. 대신
            **사람이 볼 목록**을 만든다. 2026-10-16 에 ⑤판 정책 하나가 원문이 두
            군데서 금지한 동작("급여 연계 전송 뒤 마감 해제")을 자동화하라고
            적었는데, 그때는 그 금지가 모델에 **아예 없어서** 비교할 것조차 없었다
            (done13 §253~§255). 지금은 있다.
            """
            import collections as _collections
            import re as _re

            # **두 말을 다 안다.** 선언문의 언어는 적재 때 고른 표시 언어를 따라간다 —
            # 한글로 돌리면 "…될 수 없다" 로 나오고, 영어 목록만 보면 금지가 0건이 된다
            # (2026-10-16 앱 실행에서 실제로 그랬다 · done13 §261).
            _BAN = (
                # 영어
                "cannot", "can not", "must not", "may not", "not allowed",
                "shall not", "only if", "only when", "only by", "only after",
                "never", "unless",
                # 한국어 — 업무 문서와 선언문이 실제로 쓰는 말만 넣는다
                "수 없", "하지 못", "못한다", "안 된다", "되어서는 안",
                "해서는 안", "금지", "불가", "허용되지 않", "허용하지 않",
                "만 할 수 있", "인 경우에만", "경우에만",
            )
            _STOP = {
                "the", "a", "an", "of", "for", "and", "or", "to", "in", "on",
                "be", "is", "are", "has", "have", "been", "not", "must", "may",
                "can", "cannot", "only", "if", "when", "that", "this", "it",
                "its", "by", "with", "at", "as", "from", "than", "more", "once",
                "same", "any", "all", "each", "should", "already", "after",
                "before",
            }

            def _stem(word: str) -> str:
                for suf in ("ted", "ting", "tion", "sion", "ses", "ed", "ing", "es", "s"):
                    if word.endswith(suf) and len(word) - len(suf) >= 4:
                        return word[: -len(suf)]
                return word

            def _camel(name: str) -> set:
                parts = _re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z]+|[a-z]+|\d+", name or "")
                return {_stem(p.lower()) for p in parts
                        if p.lower() not in _STOP and len(p) > 2}

            def _words(text: str) -> set:
                return {_stem(w) for w in _re.findall(r"[a-z]+", (text or "").lower())
                        if w not in _STOP and len(w) > 3}

            try:
                with get_session() as _s:
                    event_names = [r["n"] for r in _s.run(
                        "MATCH (e:Event) RETURN e.name AS n"
                    )]
                    rows = [dict(r) for r in _s.run(
                        "MATCH (e:Event)-[:TRIGGERS]->(p:Policy)-[:INVOKES]->(c:Command) "
                        "MATCH (i:Invariant)-[:VERIFIED_BY]->(c) "
                        "RETURN p.name AS policy, e.name AS trigger, "
                        "c.name AS command, i.declaration AS invariant"
                    )]
            except Exception as _e:  # noqa: BLE001 — 세기에 실패해도 완료는 막지 않는다
                SmartLogger.log(
                    "WARN",
                    f"Failed to review policies against invariants: {_e}",
                    category="ingestion.workflow.policy_review.error",
                    params={"session_id": session.id, "error": str(_e)},
                )
                return {}

            # 흔한 낱말은 아무 데서나 겹친다. 기준을 밖에서 정하지 않고 **여기서** 센다.
            freq = _collections.Counter()
            for name in event_names:
                for token in _camel(name):
                    freq[token] += 1
            threshold = max(3, int(len(event_names) * 0.15))
            common = {t for t, c in freq.items() if c >= threshold}

            banned = [r for r in rows
                      if any(b in (r.get("invariant") or "").lower() for b in _BAN)]
            narrow = []
            for r in banned:
                shared = sorted((_camel(r.get("trigger")) - common)
                                & _words(r.get("invariant")))
                if shared:
                    narrow.append({
                        "policy": r.get("policy"), "trigger": r.get("trigger"),
                        "command": r.get("command"),
                        "invariant": (r.get("invariant") or "")[:300],
                        "shared_terms": shared,
                    })
            narrow.sort(key=lambda d: (-len(d["shared_terms"]), d["policy"] or ""))

            # 좁힌 것이 비면 **넓은 것을 준다.**
            #
            # 2026-10-19 실측(done14 §283): 두 판 모두 `narrow` 가 비어서 화면에
            # **"정책 N개가 금지가 걸린 커맨드를 자동 실행합니다" 라는 개수만** 떴다.
            # 어느 정책인지는 화면에도 없고, 로그는 `look_first` 를 일부러 빼므로
            # **아무 데도 없었다.** "읽을 목록" 이라면서 목록이 없던 것이다.
            #
            # 좁히기(트리거 낱말과 금지 문장의 낱말이 겹치는 것)는 **순서를 정하는
            # 장치**지 걸러내는 장치가 아니다. 통과한 것이 없다고 해서 볼 것이 없는
            # 게 아니다 — 그날 뽑아 보니 4개 중 둘이 실제로 금지를 어기고 있었다.
            look_first = narrow[:12] or [
                {"policy": r.get("policy"), "trigger": r.get("trigger"),
                 "command": r.get("command"),
                 "invariant": (r.get("invariant") or "")[:300],
                 "shared_terms": []}
                for r in banned[:12]
            ]
            out = {
                "pairs": len(rows),
                "prohibitions": len(banned),
                "policies": len({r.get("policy") for r in banned}),
                "look_first": look_first,
                # 좁히기가 골라낸 수. 0 이면 위 목록은 **넓은 쪽**이다.
                "narrowed": len(narrow),
            }
            if banned:
                SmartLogger.log(
                    "WARN",
                    ("%d policy/invariant pairs carry a prohibition "
                     "(%d policies) — %d worth reading first")
                    % (len(banned), out["policies"], len(narrow)),
                    category="ingestion.workflow.policy_review",
                    params={"session_id": session.id,
                            # **이름을 남긴다.** 2026-10-19 까지 이 자리는 `look_first` 를
                            # 빼고 개수만 남겼다 — 그래서 모달을 닫으면 어느 정책이었는지
                            # 되찾을 길이 없었다(done14 §283). 선언문 전문은 길어서 빼고
                            # 정책·커맨드 이름만 남긴다. 그것만으로 그래프에서 찾을 수 있다.
                            "policy_names": sorted({r.get("policy") for r in banned
                                                    if r.get("policy")}),
                            **{k: v for k, v in out.items() if k != "look_first"}},
                )
            return out if banned else {}

        def _name_label_mismatch() -> dict:
            """서로 다른 Event 가 **같은 한국어 라벨**을 쓰는 것을 표시한다.

            하류가 **갈려 읽는다**: 정책 *이름*은 영어 Event 이름으로 만들고 정책
            *설명*은 `displayName` 을 쓴다. 사람은 한국어를 읽고 코드 생성은 영어를
            읽으므로 둘이 어긋나면 **산출물이 갈린다.** 2026-10-16 에 실제로
            `GrantAnnualLeaveOnEntitlementCalculated` 가 순환처럼 보였는데 라벨이
            어긋난 탓이었다 — 하마터면 **없는 결함을 보고할 뻔했다**(done13 §253).

            라벨이 겹치면 **한국어만 읽는 사람에게는 한 사건으로 보인다.** 정책
            설명도 같아지고, 리뷰가 둘을 못 가른다.

            **여기서 세는 것은 이 하나뿐이다.** "영어 뜻과 한국어 뜻이 다르다" 는
            더 넓은 질문인데, 재 보니 기계가 할 만한 일이 아니었다 — 낱말 사전을
            그 판의 데이터에서 배우게 해 봤더니 **1건을 맞히려고 7건을 울렸다**
            (`승인됨`과 `확인됨`의 `인됨` 처럼 조각이 충돌한다). 사전을 코드에
            박으면 이 검사가 **그 도메인 전용**이 된다. 그래서 그쪽은 제품이 아니라
            `2026-10-16/이름-라벨-대조.py` 에 두고 **사람이 읽는다**.

            판정하지 않는다 — 라벨이 더 정확한 경우도 있다. **사람이 볼 목록**이다.
            """
            import collections as _collections

            try:
                with get_session() as _s:
                    rows = [dict(r) for r in _s.run(
                        "MATCH (e:Event) WHERE e.displayName IS NOT NULL "
                        "RETURN e.name AS name, e.displayName AS label"
                    )]
            except Exception as _e:  # noqa: BLE001 — 세기에 실패해도 완료는 막지 않는다
                SmartLogger.log(
                    "WARN",
                    f"Failed to compare names against display labels: {_e}",
                    category="ingestion.workflow.name_label.error",
                    params={"session_id": session.id, "error": str(_e)},
                )
                return {}
            rows = [r for r in rows
                    if (r.get("name") or "").strip() and (r.get("label") or "").strip()]
            if len(rows) < 4:
                return {}

            by_label = _collections.defaultdict(set)
            for r in rows:
                by_label[r["label"].strip()].add(r["name"].strip())
            clashes = [{"label": k, "names": sorted(v)}
                       for k, v in by_label.items() if len(v) > 1]
            clashes.sort(key=lambda d: d["label"])
            if not clashes:
                return {}

            out = {
                "events": len(rows),
                "label_clashes": len(clashes),
                "events_affected": sum(len(c["names"]) for c in clashes),
                "look_first": clashes[:8],
            }
            SmartLogger.log(
                "WARN",
                ("%d display labels are each shared by more than one event "
                 "(%d events) — Korean readers cannot tell them apart")
                % (len(clashes), out["events_affected"]),
                category="ingestion.workflow.name_label",
                params={"session_id": session.id,
                        **{k: v for k, v in out.items() if k != "look_first"}},
            )
            return out

        review = _policy_prohibition_review()
        def _policy_wiring_review() -> dict:
            """정책의 **이름과 배선**이 어긋난 것, 그리고 **순환**을 표시한다.

            둘 다 그래프만 보면 되는 **객관**이다 — 낱말 사전도 언어도 도메인도
            필요 없다. 그래서 제품에서 센다(ISS-35 의 도메인 낱말 검사는 사전이
            필요해서 뺐다).

              ① **순환**  방아쇠 사건을 **그 정책이 부르는 커맨드가 낸다.**
                         `AnnualLeaveExpired → ExpireAnnualLeave → 다시
                         AnnualLeaveExpired` 는 설계가 아니라 제자리 돌기다
              ② **이름 ≠ 배선**  정책 이름의 `On<사건>` 과 실제 TRIGGERS 가 다르다.
                         정책 **이름**은 코드 생성이 읽고 사람은 **설명**을 읽으므로,
                         어긋나면 산출물이 갈린다(ISS-35 와 같은 부류)

            2026-10-16 실측(정책 5개): 순환 1 · 이름 ≠ 배선 3. 그 셋 중 둘은 이름이
            가리키는 사건이 **그래프에 아예 없었고**, 하나는 **라벨이 겹쳐 안 보이던**
            것이었다 — `…OnAttendanceClosingConfirmed` 인데 실제 방아쇠는
            `…Finalized` 이고 둘의 한국어 라벨이 같다. **결함 둘이 겹쳐 숨는다.**

            판정하지 않는다 — 순환이 맞는 설계인 경우도 드물게 있다. **사람이 볼
            목록**이다.
            """
            import re as _re

            def _said(policy: str) -> str | None:
                """정책 이름이 "어느 사건에 반응한다" 고 말하는지 읽는다.

                쓰이는 꼴 둘을 받는다 — `<동작>On<사건>` 과 `On<사건>Trigger<동작>`.
                못 읽으면 **None 을 돌려주고 세지 않는다** — 이름 짓는 규칙이
                바뀌면 조용히 틀린 판정을 내는 쪽이 더 나쁘다.
                """
                m = _re.search(r"On([A-Z][A-Za-z0-9]*?)(?:Trigger[A-Z][A-Za-z0-9]*)?$",
                               policy or "")
                return m.group(1) if m else None

            try:
                with get_session() as _s:
                    rows = [dict(r) for r in _s.run(
                        "MATCH (e:Event)-[:TRIGGERS]->(p:Policy)-[:INVOKES]->(c:Command) "
                        "RETURN p.name AS policy, e.name AS trigger, c.name AS command"
                    )]
                    loops = [dict(r) for r in _s.run(
                        "MATCH (e:Event)-[:TRIGGERS]->(p:Policy)-[:INVOKES]->"
                        "(c:Command)-[:EMITS]->(e2:Event) WHERE e.name = e2.name "
                        "RETURN p.name AS policy, e.name AS event, c.name AS command"
                    )]
                    known = {r["n"] for r in _s.run(
                        "MATCH (e:Event) RETURN e.name AS n") if r["n"]}
            except Exception as _e:  # noqa: BLE001 — 세기에 실패해도 완료는 막지 않는다
                SmartLogger.log(
                    "WARN",
                    f"Failed to review policy wiring: {_e}",
                    category="ingestion.workflow.policy_wiring.error",
                    params={"session_id": session.id, "error": str(_e)},
                )
                return {}
            if not rows:
                return {}

            mismatched, unreadable = [], 0
            for r in rows:
                said = _said(r.get("policy") or "")
                if said is None:
                    unreadable += 1
                    continue
                if said != (r.get("trigger") or ""):
                    mismatched.append({
                        "policy": r.get("policy"),
                        "name_says": said,
                        "actually": r.get("trigger"),
                        # **이름이 가리키는 사건이 아예 없으면** 더 센 신호다
                        "named_event_exists": said in known,
                    })
            mismatched.sort(key=lambda d: (d["named_event_exists"], d["policy"] or ""))

            out = {
                "policies": len(rows),
                "circular": len(loops),
                "name_mismatch": len(mismatched),
                "name_unreadable": unreadable,
                "circular_list": [
                    {k: v for k, v in d.items() if k in ("policy", "event", "command")}
                    for d in loops[:6]
                ],
                "look_first": mismatched[:6],
            }
            if loops or mismatched:
                SmartLogger.log(
                    "WARN",
                    ("%d policies: %d loop back to their own trigger, "
                     "%d carry a name that disagrees with the event wired to them")
                    % (len(rows), len(loops), len(mismatched)),
                    category="ingestion.workflow.policy_wiring",
                    params={"session_id": session.id,
                            **{k: v for k, v in out.items()
                               if k not in ("circular_list", "look_first")}},
                )
            return out if (loops or mismatched) else {}

        naming = _name_label_mismatch()
        wiring = _policy_wiring_review()

        unused = _unused_inputs()
        if unused:
            SmartLogger.log(
                "WARN",
                "Some inputs were never used",
                category="ingestion.workflow.unused_inputs",
                params={"session_id": session.id, "unused": unused},
            )

        # **무엇이** 빠졌나. 숫자(missing)는 개수만 말한다 — 이름과 단계는 여기서 온다.
        try:
            from api.features.ingestion.workflow import skip_ledger

            skipped = skip_ledger.finish(session.id)
        except Exception:  # noqa: BLE001 — 기록은 완료를 막지 않는다
            skipped = {}

        # 워크플로가 **만들었다고 믿는** 수. 진단용이고 화면의 주 숫자가 아니다.
        generated = {
            "user_stories": len(ctx.user_stories),
            "bounded_contexts": len(ctx.bounded_contexts),
            "aggregates": sum(len(aggs) for aggs in ctx.aggregates_by_bc.values()),
            "commands": sum(len(cmds) for cmds in ctx.commands_by_agg.values()),
            # ⚠ 더하지 않는다. 둘은 같은 노드를 가리킨다(위 ① 참고).
            "events": events_from_us_count,
            "readmodels": sum(len(rms) for rms in (getattr(ctx, "readmodels_by_bc", {}) or {}).values()),
            "uis": len(getattr(ctx, "uis", []) or []),
            "policies": len(ctx.policies),
        }

        # 만든 것보다 **적게 남은** 것만 적는다. 많이 남은 것은 다른 경로로 생긴 것이라
        # 손실이 아니다(2026-10-15 에 Command 가 그랬다 — 맥락 25, 그래프 26).
        missing = {
            k: generated[k] - stored[k]
            for k in generated
            if k in stored and stored[k] < generated[k]
        }
        if missing:
            SmartLogger.log(
                "WARN",
                "Some generated nodes are not in the graph",
                category="ingestion.workflow.stored_counts.missing",
                params={"session_id": session.id, "missing": missing,
                        "generated": generated, "stored": stored},
            )

        created_policy_count = stored.get("policies")
        if created_policy_count is None:
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
                    # **그래프에 남은 수**를 보여 준다. 못 셌을 때만 만든 수로 떨어진다.
                    "user_stories": stored.get("user_stories", generated["user_stories"]),
                    "bounded_contexts": stored.get("bounded_contexts", generated["bounded_contexts"]),
                    "aggregates": stored.get("aggregates", generated["aggregates"]),
                    "commands": stored.get("commands", generated["commands"]),
                    "events": stored.get("events", generated["events"]),
                    "readmodels": stored.get("readmodels", generated["readmodels"]),
                    "uis": stored.get("uis", generated["uis"]),
                    "policies": created_policy_count,
                    # 진단용 — 화면은 `missing` 이 있을 때만 쓴다.
                    "generated": generated,
                    "stored": stored,
                    "missing": missing,
                    "skipped": skipped,
                    "unused": unused,
                    # 금지가 걸린 커맨드를 자동 실행하는 정책 — **판정이 아니라 목록**이다
                    "review": review,
                    "naming": naming,
                    "wiring": wiring,
                    "events_from_us": events_from_us_count,
                    "events_reachable_from_commands": events_from_cmd_count,
                    # spec 025 — UI flow layer counters
                    "journeys_created": int(ui_flow_summary.get("journeys_created", 0)),
                    "next_ui_edges_created": int(ui_flow_summary.get("next_ui_edges_created", 0)),
                    "gateways_created": int(ui_flow_summary.get("gateways_created", 0)),
                    "ui_flow_warnings": dict(ui_flow_summary.get("warnings_by_code", {})),
                }
            },
        ))
        runs.finish(run_id, "complete")
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
        # 오류는 **중단이 아니다** — 화면이 이 자리에서 말을 한다.
        runs.finish(run_id, "error", str(e))
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
        # 박동을 먼저 세운다 — 스레드가 남으면 죽은 작업이 살아 있는 척한다.
        # 여기까지 와서 아직 `running` 이면 **사람이 멈춘 것**이다(취소·제너레이터
        # 닫힘). 강제 종료는 이 자리를 밟지 못한다 — 그 차이가 경고를 가른다.
        if beater is not None:
            beater.stop()
        runs.finish(run_id, "cancelled")
        # Spec 017: clear the workflow's session context so subsequent get_llm()
        # calls (e.g. /api/chat/modify) don't accidentally inherit this
        # workflow's token callback.
        try:
            reset_current_session(_session_token)
        except Exception:  # noqa: BLE001
            pass
