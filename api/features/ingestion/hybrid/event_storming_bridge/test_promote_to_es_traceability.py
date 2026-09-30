# -*- coding: utf-8 -*-
"""승격이 붙이는 **출처 엣지**를 잰다.

두 가지다.

  ① 폴백은 BC 를 먼저 고른 뒤 그 id 로 붙인다 — `WITH bc … LIMIT 1` 뒤에 다시
     MATCH 를 두면 쓰기 앞의 마지막 읽기 절이 WITH 가 아니게 되므로 BC 선택을
     별도 읽기 질의로 분리했다. LIMIT 이 BC 선택에만 걸린다는 의도는 그대로다.

  ② **전술 요소도 출처를 받는다** (2026-09-30). 그 전에는 UserStory 만 룰까지
     닿았고 Command·Aggregate·Event·Policy·ReadModel 은 노드에 아무것도 없었다.

### 질의를 순서 번호로 찾지 않는다

예전 이 검사는 `sess.queries[2]`, `[3]` 으로 질의를 집었다. ②를 넣자 질의가 여섯
늘어 **번호가 밀려 깨졌다** — 잡은 것은 결함이 아니라 순서였다. 그래서 내용으로
찾는다. 순서가 바뀌어도, 사이에 질의가 끼어도 재려는 것을 그대로 잰다.
"""

from __future__ import annotations

import pytest

from api.features.ingestion.hybrid.event_storming_bridge import promote_to_es


class _Rec(dict):
    pass


class _Session:
    """질의를 모으고, **내용에 따라** 그럴듯한 값을 돌려준다."""

    def __init__(self) -> None:
        self.queries: list[str] = []

    def run(self, query: str, **params):
        self.queries.append(query)
        if "ORDER BY bc.key LIMIT 1" in query:
            rec = _Rec(id="bc-1")
        elif "MERGE (us)-[rel:SOURCED_FROM]" in query:
            rec = _Rec(c=50)
        elif "MERGE (x)-[rel:SOURCED_FROM]" in query:
            rec = _Rec(c=7)          # 요소 종류마다 7건
        elif "$bid" in query:
            rec = _Rec(c=3)          # 폴백 attach
        else:
            rec = _Rec(c=1)          # 직접 attach
        return type("_R", (), {"single": lambda _s, r=rec: r})()


class _Ctx:
    def __init__(self, s):
        self.s = s

    def __enter__(self):
        return self.s

    def __exit__(self, exc_type, exc, tb):
        return False


@pytest.fixture
def run(monkeypatch: pytest.MonkeyPatch):
    sess = _Session()
    monkeypatch.setattr(promote_to_es, "get_session", lambda: _Ctx(sess))
    counts = promote_to_es._attach_analyzer_traceability("sid-1")
    return sess, counts


def _find(sess: _Session, needle: str) -> str:
    hits = [q for q in sess.queries if needle in q]
    assert hits, f"{needle!r} 를 담은 질의가 없다"
    return hits[0]


def test_폴백은_BC_를_먼저_고르고_id_로_붙인다(run):
    sess, counts = run
    assert counts["attached_to"] == 4

    bc_pick = _find(sess, "ORDER BY bc.key LIMIT 1")
    assert "MERGE" not in bc_pick, "BC 선택은 읽기 전용이다"
    fallback = _find(sess, "$bid")
    assert "MATCH (q:QUESTION)" in fallback


def test_전술_요소에도_출처를_붙인다(run):
    """UserStory 만 닿던 것을 다섯 종류로 넓혔다."""
    sess, _ = run
    element = [q for q in sess.queries if "MERGE (x)-[rel:SOURCED_FROM]" in q]
    labels = {lab for q in element for lab in
              ("Command", "Aggregate", "ReadModel", "Event", "Policy") if f"x:{lab} " in q}
    assert labels == {"Command", "Aggregate", "ReadModel", "Event", "Policy"}, (
        f"출처를 못 받는 요소가 있다: {labels}"
    )


def test_합성_Policy_는_트리거_Event_로도_닿는다(run):
    """BC 간 합성 Policy 는 US 가 직접 가리키지 않는다 — 실측 12/18 vs 18/18."""
    sess, _ = run
    triggered = [q for q in sess.queries
                 if "TRIGGERS]->(x:Policy" in q and "HAS_EVENT" in q]
    assert triggered, "트리거 Event 경유 경로가 없다 — Policy 6개가 출처를 못 받는다"


def test_primary_는_덮이지_않는다(run):
    """요소 하나에 task 여러 개가 모인다 — 그냥 SET 하면 마지막 task 가 이긴다."""
    sess, _ = run
    element = [q for q in sess.queries if "MERGE (x)-[rel:SOURCED_FROM]" in q]
    assert element, "요소 출처 질의가 아예 없다 — 이 검사가 헛돈다"
    for q in element:
        assert "CASE WHEN rel.evidence_role = 'primary'" in q, (
            "primary 를 지키지 않는다 — supporting 으로 뒤집힌다"
        )
        assert "coalesce(rel.via_task_id, t.id)" in q, "via_task_id 를 덮어쓴다"


def test_합계와_종류별_수를_같이_센다(run):
    sess, counts = run
    # UserStory 50 + 요소 질의 6개 × 7 = 92
    assert counts["sourced_from"] == 50 + 7 * 6
    for key in ("command", "aggregate", "readmodel", "event", "policy"):
        assert counts[f"sourced_from_{key}"] > 0, f"{key} 수를 안 센다"
    # Policy 는 길이 둘이라 합쳐진다.
    assert counts["sourced_from_policy"] == 14
