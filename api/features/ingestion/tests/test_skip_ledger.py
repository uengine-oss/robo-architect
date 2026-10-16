# -*- coding: utf-8 -*-
"""빠진 것이 **결과에 실리는지** 본다 (Q2 · ISS-28).

2026-10-15 실측: 한 세션에 neo4j 오류 24건이 났는데 화면은 초록색 "생성 완료" 였고,
무엇이 빠졌는지는 로그를 열어야 알 수 있었다(done12 §233). 여기서 검증하는 것은
**단계 코드를 고치지 않고도** 그 사실이 올라오는가다.
"""

from api.features.ingestion.workflow import skip_ledger
from api.platform.observability.smart_logger import SmartLogger


def _reset() -> None:
    SmartLogger.remove_observer(skip_ledger._observe)
    skip_ledger._installed = False
    skip_ledger._ledgers.clear()


def test_skip_logs_are_collected_without_touching_phases():
    _reset()
    skip_ledger.start("sess-1")

    # 단계들이 실제로 남기는 모양 그대로.
    SmartLogger.log(
        "ERROR",
        "Policy creation failed: {message: deadlock detected}",
        category="ingestion.workflow.policies.skip",
        params={"session_id": "sess-1", "policy_index": 2},
    )
    SmartLogger.log(
        "WARNING",
        "ReadModel create skipped",
        category="ingestion.neo4j.readmodel.skip",
        params={"session_id": "sess-1", "readmodel_name": "PaymentInstitutionInfoCollection"},
    )
    SmartLogger.log(
        "ERROR",
        "Exception linking User Story US-003 to BC Leave: {message: duplicate key value}",
        category="ingestion.workflow.bc.link_exception",
        params={"session_id": "sess-1", "user_story_id": "US-003"},
    )

    out = skip_ledger.finish("sess-1")
    assert out["total"] == 3
    # 분류에서 **단계 이름**이 나온다 — 화면이 "어디서" 를 말할 수 있다.
    assert out["by_phase"] == {"policies": 1, "readmodel": 1, "bc": 1}
    names = {i["name"] for i in out["items"]}
    assert "PaymentInstitutionInfoCollection" in names
    assert "US-003" in names
    # 원인이 한 줄로 남는다.
    assert any(i["reason"] == "deadlock detected" for i in out["items"])


def test_normal_logs_are_not_collected():
    _reset()
    skip_ledger.start("sess-2")

    SmartLogger.log("INFO", "Events from User Stories: 64 events created",
                    category="ingestion.workflow.events_from_us.done",
                    params={"session_id": "sess-2"})
    # 경고지만 **빠진 것이 아니다** — 분류에 표식이 없다.
    SmartLogger.log("WARNING", "tokens high",
                    category="ingestion.tokens.session_total",
                    params={"session_id": "sess-2"})

    assert skip_ledger.finish("sess-2") == {}


def test_other_sessions_do_not_leak_in():
    _reset()
    skip_ledger.start("sess-A")
    skip_ledger.start("sess-B")

    SmartLogger.log("ERROR", "boom", category="ingestion.workflow.policies.skip",
                    params={"session_id": "sess-B", "name": "P1"})
    # 세션을 안 실어 보내는 호출부. **둘 이상 열려 있으면 버린다** — 섞으면 거짓이 된다.
    SmartLogger.log("ERROR", "boom2", category="ingestion.workflow.policies.skip", params={})

    a = skip_ledger.finish("sess-A")
    b = skip_ledger.finish("sess-B")
    assert a == {}
    assert b["total"] == 1
    assert b["items"][0]["name"] == "P1"


def test_cap_keeps_memory_bounded():
    _reset()
    skip_ledger.start("sess-3")
    for i in range(skip_ledger.MAX_ENTRIES + 25):
        SmartLogger.log("ERROR", f"x{i}", category="ingestion.workflow.aggregates.skip",
                        params={"session_id": "sess-3"})
    out = skip_ledger.finish("sess-3")
    assert len(out["items"]) == 20                     # 화면에 실리는 것은 앞쪽만
    assert out["dropped"] == 25
    assert out["total"] == skip_ledger.MAX_ENTRIES + 25


def test_observer_never_breaks_logging():
    _reset()
    skip_ledger.start("sess-4")

    def _boom(*_a, **_k):
        raise RuntimeError("관찰자가 터져도 로깅은 산다")

    SmartLogger.add_observer(_boom)
    try:
        SmartLogger.log("ERROR", "still logs", category="ingestion.workflow.policies.skip",
                        params={"session_id": "sess-4"})
    finally:
        SmartLogger.remove_observer(_boom)

    assert skip_ledger.finish("sess-4")["total"] == 1
