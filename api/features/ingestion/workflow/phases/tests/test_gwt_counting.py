"""GWT 요약 숫자가 **그래프와 맞는가**.

## 2026-09-29 실측에서 나온 것

인사관리(`prj_f6d8c556ad`) 승격을 완주시킨 뒤:

    요약 메시지   "GWT 생성 완료 (140개 구성요소)"
    그래프        GWT 29개 · 테스트케이스 124개

16 차이가 났다. **데이터가 사라진 것은 아니었다** — Command 29개를
`chunk_size=8, overlap_count=1` 로 쪼개면 5청크에 33회가 들어가고, 겹친 4개가
두 번 처리·두 번 세어진다. 저장은 `MERGE (gwt {parentType, parentId})` 라
한 노드로 합쳐지니 그래프는 29개가 맞다.

그런데 그 16을 쫓는 데 시간이 들었고, 그 사이 "GWT 가 유실된다" 를 의심했다.
그래서 두 가지를 잰다.

  ① 겹침이 없다          — 같은 Command 를 두 번 부르지 않는다(LLM 호출도 돈이다)
  ② 저장 못 하면 0 이다  — `_save_gwt` 가 부모를 못 찾았을 때 세지 않는다

②가 더 중요하다. 예전 `_save_gwt` 는 부모를 못 찾으면 "조용히 끝낸다" 고 적힌
자리에서 `None` 을 돌려줬고, 호출부는 그것과 무관하게 카운터를 올렸다. 즉
**아무것도 안 써도 요약은 정상으로 찍혔다.** 같은 파일의 `_GWT_RULE_UPSERT`
주석이 그 사고를 이미 한 번 적어 뒀다.
"""

from __future__ import annotations

import pytest

from api.features.ingestion.workflow.phases.gwt import _save_gwt
from api.features.ingestion.workflow.utils.chunking import split_list_with_overlap


# ---------------------------------------------------------------------------
# ① 청크가 같은 항목을 두 번 주지 않는다
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n", [1, 7, 8, 9, 16, 29, 30, 100])
def test_겹침_0이면_모든_항목이_정확히_한_번(n: int) -> None:
    chunks = split_list_with_overlap(list(range(n)), chunk_size=8, overlap_count=0)
    flat = [x for c in chunks for x in c]
    assert sorted(flat) == list(range(n)), "빠지거나 늘어난 항목이 있다"
    assert len(flat) == len(set(flat)), "같은 항목이 두 청크에 들어갔다"


def test_GWT_단계가_실제로_겹침_0으로_쪼갠다() -> None:
    """위 검사들은 `split_list_with_overlap` 만 본다 — **호출부는 안 본다.**

    값이 잘못 들어가는 자리는 호출부이므로 거기를 직접 확인한다. 소스를 읽는
    방식이 투박하지만, 이 한 줄이 조용히 되돌아가는 것이 실제로 있었던 일이다.
    """
    import inspect

    from api.features.ingestion.workflow.phases import gwt as gwt_module

    src = inspect.getsource(gwt_module.generate_gwt_phase)
    calls = [ln.strip() for ln in src.splitlines() if "split_list_with_overlap(" in ln]
    assert calls, "GWT 단계가 더 이상 이 함수로 쪼개지 않는다 — 이 검사를 고쳐라"
    for call in calls:
        assert "overlap_count=0" in call, (
            f"GWT 는 항목마다 독립으로 LLM 을 부르고 upsert 한다 — 겹치면 "
            f"한 번 더 부르고 앞의 것을 덮는다: {call}"
        )


def test_겹침_1이면_실제로_중복이_생긴다_회귀근거() -> None:
    """이 검사는 **옛 설정이 왜 틀렸는지**를 고정한다.

    누군가 `overlap_count` 를 되돌리면 위 검사가 깨진다. 그때 "원래 그런 건가"
    싶지 않도록, 겹침이 중복을 만든다는 사실을 여기 못박아 둔다.
    """
    chunks = split_list_with_overlap(list(range(29)), chunk_size=8, overlap_count=1)
    flat = [x for c in chunks for x in c]
    assert len(flat) == 33
    assert len(flat) - len(set(flat)) == 4, "29개·청크8·겹침1 이면 4개가 두 번 처리된다"


# ---------------------------------------------------------------------------
# ② 저장하지 못하면 세지 않는다
# ---------------------------------------------------------------------------

class _FakeResult:
    def __init__(self, record):
        self._record = record

    def single(self):
        return self._record


class _FakeSession:
    """`session.run` 만 흉내 낸다. 첫 호출이 upsert, 그 뒤가 참조 정리/연결."""

    def __init__(self, upsert_record):
        self._upsert_record = upsert_record
        self.queries: list[str] = []

    def run(self, query, **_kwargs):
        self.queries.append(query)
        # 첫 문장(upsert)만 레코드를 돌려준다.
        if len(self.queries) == 1:
            return _FakeResult(self._upsert_record)
        return _FakeResult(None)


def _save(session) -> bool:
    return _save_gwt(
        session,
        parent_type="Command",
        parent_id="cmd-1",
        given_ref_json=None,
        when_ref_json=None,
        then_ref_json=None,
        test_cases_json="[]",
        refs=[{"id": "evt-1", "type": "Event"}],
    )


def test_부모를_찾았으면_True_이고_참조까지_잇는다() -> None:
    session = _FakeSession({"id": "gwt-1"})
    assert _save(session) is True
    # upsert + refs clear + refs link = 3문장
    assert len(session.queries) == 3


def test_부모를_못_찾으면_False_이고_뒷문장을_실행하지_않는다() -> None:
    session = _FakeSession(None)
    assert _save(session) is False, "저장 못 했는데 True 를 주면 요약이 거짓말을 한다"
    assert len(session.queries) == 1, "부모가 없으면 참조를 손대면 안 된다"


def test_레코드가_있어도_id가_비면_저장_실패로_본다() -> None:
    # 실제로 겪는 모양: MATCH 는 됐지만 RETURN 이 빈 경우.
    session = _FakeSession({"id": None})
    assert _save(session) is False
    assert len(session.queries) == 1


def test_refs가_없으면_연결_문장을_건너뛴다() -> None:
    session = _FakeSession({"id": "gwt-1"})
    ok = _save_gwt(
        session,
        parent_type="Command",
        parent_id="cmd-1",
        given_ref_json=None,
        when_ref_json=None,
        then_ref_json=None,
        test_cases_json="[]",
        refs=[],
    )
    assert ok is True
    assert len(session.queries) == 2, "upsert + clear 까지만 돈다"


# ---------------------------------------------------------------------------
# ③ 저장 못 했으면 **말한다** (2026-10-06)
# ---------------------------------------------------------------------------
#
# ②는 "세지 않는다" 까지만 지켰다. 그런데 안 센 이유가 어디에도 남지 않으면,
# 나중에 "이 Command 는 왜 GWT 가 없나" 를 물을 때 **답할 방법이 없다** — 설계상
# 없는 것(Policy GWT 는 `if False:` 로 끈 상태다)과 사고로 없는 것이 같은 모양이
# 된다. 기준 그래프에서 Command 17 중 GWT 15 를 보고 실제로 그 질문을 했고,
# 둘이 비어 있던 이유를 **로그가 아니라 노드를 하나씩 뒤져서** 알아냈다
# (중복 승격된 Command 두 벌이었다).

def test_폴백이_아무것도_못_썼으면_로그로_말한다() -> None:
    """실패를 세지 않는 것만으로는 부족하다 — **이유가 남아야** 한다."""
    import inspect

    from api.features.ingestion.workflow.phases import gwt as gwt_module

    src = inspect.getsource(gwt_module._generate_gwt_for_command)
    assert "ingestion.workflow.gwt.fallback_empty" in src, \
        "폴백이 아무것도 안 썼을 때 말하지 않는다"
    assert "ingestion.workflow.gwt.fallback_error" in src, \
        "폴백 자체가 실패했을 때 말하지 않는다"


def test_폴백_경로에_조용한_반환이_없다() -> None:
    """`except Exception:` 다음에 바로 `return 0` 이 오면 사유가 사라진다."""
    import inspect
    import re

    from api.features.ingestion.workflow.phases import gwt as gwt_module

    src = inspect.getsource(gwt_module._generate_gwt_for_command)
    silent = re.search(r"except\s+Exception\s*:\s*\n\s*return\s+0", src)
    assert silent is None, "조용히 0 을 돌려주는 자리가 다시 생겼다"
