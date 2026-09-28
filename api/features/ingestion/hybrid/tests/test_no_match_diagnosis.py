"""매핑이 0으로 끝났을 때 **사람이 다음에 무엇을 할지** 고를 수 있는가.

## 여기서 재는 것

룰 매핑이 0이 되는 길은 여럿인데, 예전에는 화면에 **전부 같은 모양**("매핑 0")으로
보였다. 그래서 사용자가 할 수 있는 판단은 "기능이 고장났다" 뿐이었다.

2026-09-28 에 실제로 그렇게 보고됐다. 실측해 보니 기능은 멀쩡했고, 원인은 **문서와
코드의 도메인이 달랐던 것**이었다 — BPM 은 인사(휴가·근태), 분석 짝은 수납 코드
(청구번호·납부방법). 같은 기능을 짝이 맞는 프로젝트에서 돌리자 13개 태스크에서
32개 매핑이 나왔다.

그래서 세 경우가 **서로 다른 문장**으로 나오는지 잰다. 문장이 같으면 사용자는
여전히 구별할 수 없다.
"""

from api.features.ingestion.hybrid import explore_service as svc
from api.features.ingestion.hybrid.mapper import module_retriever as mr


def _diagnose(reason):
    mr._set_last_reason(reason)
    return svc._no_match_diagnosis()


def test_분석_짝이_없으면_그렇게_말한다():
    d = _diagnose(mr.REASON_NO_ANALYSIS_LINK)
    assert d["reason"] == mr.REASON_NO_ANALYSIS_LINK
    # 무엇을 해야 하는지가 있어야 한다 — "없습니다" 만으로는 아무도 못 고친다.
    assert "분석" in d["message"] and "지정" in d["message"]


def test_요약이_없으면_재분석을_가리킨다():
    d = _diagnose(mr.REASON_NO_SUMMARIES)
    assert d["reason"] == mr.REASON_NO_SUMMARIES
    assert "다시" in d["message"]


def test_문턱_미달이면_도메인_불일치를_의심하게_한다():
    d = _diagnose(None)
    assert d["reason"] == "no_module_above_threshold"
    # 이것이 실제로 보고된 경우다. "코드에 없다" 로 단정하지 않고 **짝을 확인하라**
    # 고 해야 한다 — 단정하면 사용자가 멀쩡한 코드를 의심한다.
    assert "확인" in d["message"]


def test_세_경우의_문장이_서로_다르다():
    msgs = {
        _diagnose(r)["message"]
        for r in (mr.REASON_NO_ANALYSIS_LINK, mr.REASON_NO_SUMMARIES, None)
    }
    assert len(msgs) == 3, "문장이 겹치면 사용자는 여전히 구별할 수 없다"


def test_이유는_코드와_문장을_함께_준다():
    """코드만 주면 화면이 문장을 또 만들어야 하고, 문장만 주면 분기할 수 없다."""
    for r in (mr.REASON_NO_ANALYSIS_LINK, mr.REASON_NO_SUMMARIES, None):
        d = _diagnose(r)
        assert set(d) == {"reason", "message"}
        assert d["reason"] and d["message"]


def test_이유는_탐색마다_비워진다():
    """안 비우면 **지난 탐색의 이유가 이번 결과에 붙는다.**

    캐시 적중으로 모듈 조회를 건너뛴 탐색이 특히 그렇다 — 그때는 아무도 값을
    덮어쓰지 않으므로, 직전에 "분석 짝 없음" 이었다면 그 문장이 그대로 남는다.
    """
    mr._set_last_reason(mr.REASON_NO_ANALYSIS_LINK)
    mr.reset_empty_reason()
    assert mr.last_empty_reason() is None
    assert svc._no_match_diagnosis()["reason"] == "no_module_above_threshold"
