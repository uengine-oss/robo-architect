"""선점 수명의 **계약**만 잰다 — 붙는 것은 화면 검사와 verify 스크립트가 잰다.

여기 있는 것은 전부 "되돌아가면 조용히 깨지는" 자리다. 실제 동작은
`scripts/verify_collab_lock_lifetime.py` 와
`frontend/tests/collab-lock-lifetime.spec.ts` 가 그래프·화면까지 보고 잰다.
"""
from __future__ import annotations

from api.features.collab import store


def test_고정_ttl_이_없다():
    """시계로 재는 길이 남아 있으면 안 된다.

    전에는 `LOCK_TTL_SECONDS = 60` 이 있었고, 그 60초를 갱신하는 것이 SSE
    스트림뿐이라 **스트림이 끊기는 순간 편집 중인 사람의 잠금이 풀렸다.**
    """
    assert not hasattr(store, "LOCK_TTL_SECONDS")
    assert hasattr(store, "LOCK_ABSENT_GRACE_SECONDS")


def test_유예가_접속_ttl_보다_길다():
    """같거나 짧으면 접속자 목록이 깜빡이는 순간에 잠금이 걷힌다."""
    assert store.LOCK_ABSENT_GRACE_SECONDS > store.PRESENCE_TTL_SECONDS


def test_생사_판정이_세션을_본다():
    """잠금은 사람이 아니라 **창**에 묶인다.

    사람에만 묶으면, 창을 둘 열어 둔 사람이 편집하던 창을 닫아도 다른 창이
    살아 있다는 이유로 잠금이 남는다 — 아무도 열고 있지 않은 요소가 잠긴다.
    """
    sql = store._HOLDER_PRESENT
    assert "app_collab_sessions" in sql
    assert "s.session = l.session" in sql
    # 세션이 없는 옛 행·스크립트는 사람 기준으로 본다. 이 갈래를 빼면
    # 잠금을 안 거치는 쓰기가 영구 잠금이 된다.
    assert "l.session IS NULL" in sql


def test_정리_실패는_0건과_구별된다():
    """`sweep_absent_locks` 는 못 했을 때 -1 을 준다.

    0 으로 주면 "치울 게 없었다"와 "치우려다 실패했다"가 같은 값이 된다.
    실제로 이 함수가 처음 판에서 정확히 그렇게 틀렸다 — 파라미터 타입 오류를
    `except` 가 먹고 0 을 냈고, 검사는 "정리가 아무것도 안 했다"로 읽었다.
    """
    assert store.sweep_absent_locks("이름이 틀린 graph!!") == -1
