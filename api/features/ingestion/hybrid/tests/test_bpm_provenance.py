"""BPMN 을 **누가 냈는지**가 노드에 남는가 (spec 058 §6 · T059/T060).

## 왜 필요했나

2026-09-17 에 facade 를 죽여 놓고 내장 추출기(native)가 task 7 · gateway 2 를
그럴듯하게 냈다. **결과물로는 진짜와 구분되지 않는다.** 진행 스트림에
`🔌 Phase 1 소스: …` 로 흘리긴 했지만 그건 지나가면 사라지고, 앱을 다시 열면
그 BPMN 을 누가 냈는지 알 길이 없었다.

2026-09-29 에 실제로 막혔다 — "pdf2bpmn 을 탔는지 폴백이었는지" 를 확인하려는데
`BpmProcess` 가 들고 있는 것이 id·session·index·name·source_pdf_name·bpmn_xml·
updated_at 뿐이었다. **확인할 방법 자체가 없었다.**

## 여기서 재는 것

  ① 출처를 주면 노드에 쓴다
  ② **주지 않으면 아무것도 쓰지 않는다** — 빈 값과 `native` 는 다르다(T060)
  ③ 재저장할 때 이미 있는 값을 `null` 로 덮지 않는다

②가 핵심이다. 빈 값을 `native` 로 읽으면 출처를 모르는 옛 노드가 전부
"폴백이었다" 로 집계된다. 그건 사실이 아니고, 그 집계를 근거로 서비스를
의심하게 된다.
"""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from api.features.ingestion.hybrid import contracts
from api.features.ingestion.hybrid.ontology import neo4j_ops


class _FakeSession:
    """`run` 으로 들어온 (쿼리, 파라미터) 를 모아 둔다."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def run(self, query: str, **params):
        self.calls.append((query, params))
        return _FakeResult()


class _FakeResult:
    def single(self):
        # process_index 계산용 count 질의에 답한다.
        return {"n": 0}

    def __iter__(self):
        return iter(())


@pytest.fixture()
def session(monkeypatch) -> _FakeSession:
    s = _FakeSession()

    @contextmanager
    def _get_session():
        yield s

    monkeypatch.setattr(neo4j_ops, "get_session", _get_session)
    return s


def _skeleton() -> contracts.BpmSkeleton:
    process = contracts.BpmProcess(
        id="proc_abc123",
        name="휴가신청 결재처리",
        session_id="sess-1",
    )
    return contracts.BpmSkeleton(
        process=process,
        actors=[],
        tasks=[],
        sequences=[],
        bpmn_xml="<definitions/>",
    )


def _process_merge(session: _FakeSession) -> tuple[str, dict]:
    """BpmProcess 를 MERGE 하는 호출을 찾아 돌려준다."""
    for query, params in session.calls:
        if "BpmProcess" in query and "MERGE" in query and params.get("id") == "proc_abc123":
            return query, params
    raise AssertionError(f"BpmProcess MERGE 를 찾지 못했다: {[q[:60] for q, _ in session.calls]}")


# ---------------------------------------------------------------------------
# ① 주면 쓴다
# ---------------------------------------------------------------------------

def test_facade_로_냈으면_그대로_남는다(session: _FakeSession) -> None:
    neo4j_ops.save_bpm_skeleton("sess-1", _skeleton(), generated_by="facade")
    query, params = _process_merge(session)
    assert "p.generatedBy = $generated_by" in query
    assert params["generated_by"] == "facade"
    assert params["generated_at"], "언제인지도 남아야 한다"
    # 폴백이 아니면 사유는 **빈 문자열이 아니라 없음**이다.
    assert params["fallback_reason"] is None


def test_폴백이면_사유까지_남는다(session: _FakeSession) -> None:
    reason = "facade 502 Bad Gateway; a2a All connection attempts failed"
    neo4j_ops.save_bpm_skeleton(
        "sess-1", _skeleton(), generated_by="native", fallback_reason=reason
    )
    _, params = _process_merge(session)
    assert params["generated_by"] == "native"
    assert params["fallback_reason"] == reason


@pytest.mark.parametrize("src", ["facade", "a2a", "native"])
def test_세_경로_모두_기록된다(session: _FakeSession, src: str) -> None:
    neo4j_ops.save_bpm_skeleton("sess-1", _skeleton(), generated_by=src)
    _, params = _process_merge(session)
    assert params["generated_by"] == src


# ---------------------------------------------------------------------------
# ② 모르면 쓰지 않는다 — 여기가 T060
# ---------------------------------------------------------------------------

def test_출처를_모르면_속성을_아예_안_쓴다(session: _FakeSession) -> None:
    """빈 값과 `native` 는 다르다.

    옛 노드는 출처가 없고, 그것은 "폴백이었다" 가 아니라 **"모른다"** 다.
    """
    neo4j_ops.save_bpm_skeleton("sess-1", _skeleton())
    query, params = _process_merge(session)
    assert "generatedBy" not in query, "모르는 것을 쓰면 '모른다'가 값이 되어버린다"
    assert "generated_by" not in params
    assert "generationFallbackReason" not in query


def test_빈_문자열도_모르는_것으로_본다(session: _FakeSession) -> None:
    neo4j_ops.save_bpm_skeleton("sess-1", _skeleton(), generated_by="")
    query, _ = _process_merge(session)
    assert "generatedBy" not in query


def test_사유만_있고_출처가_없으면_쓰지_않는다(session: _FakeSession) -> None:
    # 사유는 출처에 딸린 값이다. 출처 없이 사유만 남기면 읽는 쪽이 해석할 수 없다.
    neo4j_ops.save_bpm_skeleton("sess-1", _skeleton(), fallback_reason="뭔가 실패")
    query, _ = _process_merge(session)
    assert "generatedBy" not in query
    assert "generationFallbackReason" not in query


# ---------------------------------------------------------------------------
# ③ 재저장이 기존 값을 지우지 않는다
# ---------------------------------------------------------------------------

def test_출처_없이_다시_저장해도_기존_값을_덮지_않는다(session: _FakeSession) -> None:
    """같은 세션을 다시 저장하는 일은 흔하다(재탐색·백필).

    그때 `generatedBy=None` 을 파라미터로만 넘기면 `SET` 이 기존 값을 `null` 로
    덮는다 — 한 번 기록한 출처가 조용히 사라진다. 그래서 절 자체를 붙이지 않는다.
    """
    neo4j_ops.save_bpm_skeleton("sess-1", _skeleton())
    query, _ = _process_merge(session)
    assert "generatedBy" not in query
    # 나머지 속성은 그대로 갱신돼야 한다 — 출처가 없다고 저장을 건너뛰면 안 된다.
    assert "p.name = $name" in query
    assert "p.bpmn_xml = $xml" in query
