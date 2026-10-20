# -*- coding: utf-8 -*-
"""일시적인 그래프 오류를 다시 해 보는 장치 (§300).

2026-10-20 실측: 정책을 동시에 만드는 150밀리초 안에 14건이 터졌다 —
교착 8(`TransientError`) · `pg_type` 중복키 6(`ClientError`).
드라이버는 **앞의 것만** 재시도한다. 뒤의 것을 이름으로 집어 같이 다시 한다.

⚠ 여기서 재는 것은 **가름이 맞는가**다 — 아무 `ClientError` 나 다시 하면
같은 실패를 반복하며 시간만 쓴다.
"""

import pytest

from api.features.ingestion.event_storming.neo4j_client import (
    is_retryable_graph_error,
    retry_on_transient,
    retry_stats_reset,
    retry_stats_snapshot,
)


class _TransientError(Exception):
    """드라이버의 `neo4j.exceptions.TransientError` 를 이름으로 흉내 낸다."""


class _ClientError(Exception):
    pass


class Test무엇을_다시_하나:
    def test_교착은_다시_한다(self):
        assert is_retryable_graph_error(_TransientError("deadlock detected"))

    def test_pg_type_중복키는_다시_한다(self):
        e = _ClientError(
            '{neo4j_code: Neo.ClientError.Statement.ArgumentError} '
            '{message: duplicate key value violates unique constraint '
            '"pg_type_typname_nsp_index"}'
        )
        assert is_retryable_graph_error(e)

    def test_그_밖의_ClientError_는_다시_안_한다(self):
        """질의가 틀린 것은 다시 해도 같은 실패다."""
        assert not is_retryable_graph_error(
            _ClientError("{message: unexpected character '#' at offset 169}"))
        assert not is_retryable_graph_error(
            _ClientError('invalid input syntax for type bigint: "HR_APPROVAL_HISTORY"'))

    def test_보통_예외는_다시_안_한다(self):
        assert not is_retryable_graph_error(ValueError("nope"))


class Test다시_하기:
    def test_두_번째에_통과하면_그_값을_준다(self):
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 2:
                raise _TransientError("deadlock detected")
            return "ok"

        assert retry_on_transient(flaky, base_delay=0.0) == "ok"
        assert calls["n"] == 2

    def test_끝까지_안_되면_마지막_오류를_올린다(self):
        calls = {"n": 0}

        def always():
            calls["n"] += 1
            raise _TransientError("deadlock detected")

        with pytest.raises(_TransientError):
            retry_on_transient(always, attempts=3, base_delay=0.0)
        assert calls["n"] == 3

    def test_다시_안_할_오류는_곧바로_올린다(self):
        calls = {"n": 0}

        def bad():
            calls["n"] += 1
            raise _ClientError("syntax error")

        with pytest.raises(_ClientError):
            retry_on_transient(bad, attempts=4, base_delay=0.0)
        assert calls["n"] == 1, "다시 하면 안 되는 것을 다시 했다"

    def test_한_번에_되면_한_번만_부른다(self):
        calls = {"n": 0}

        def fine():
            calls["n"] += 1
            return 42

        assert retry_on_transient(fine) == 42
        assert calls["n"] == 1


class Test몇_번_다시_했나:
    """**성공한 재시도는 아무것도 안 남긴다.** 그래서 센다(§301).

    2026-10-20 적재에서 오류가 0 으로 나왔는데, 그게 **재시도가 삼켜서인지
    애초에 안 난 것인지** 가를 수가 없었다(정책이 4개라 부딪힐 일이 적었다).
    로그로는 안 된다 — 이 저장소는 파일 최소 수준이 ERROR 다.
    """

    def test_안_부딪히면_비어_있다(self):
        retry_stats_reset()
        retry_on_transient(lambda: "ok")
        assert retry_stats_snapshot() == {}, "돌진이 없었는데 숫자가 생겼다"

    def test_삼킨_만큼_센다(self):
        retry_stats_reset()
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise _TransientError("deadlock detected")
            return "ok"

        assert retry_on_transient(flaky, base_delay=0.0) == "ok"
        assert retry_stats_snapshot() == {"deadlock": 2}

    def test_종류를_갈라_센다(self):
        retry_stats_reset()
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 2:
                raise _ClientError(
                    'duplicate key value violates unique constraint '
                    '"pg_type_typname_nsp_index"')
            return "ok"

        retry_on_transient(flaky, base_delay=0.0)
        assert retry_stats_snapshot() == {"pg_type": 1}

    def test_끝까지_안_되면_포기한_것도_센다(self):
        retry_stats_reset()

        def always():
            raise _TransientError("deadlock detected")

        with pytest.raises(_TransientError):
            retry_on_transient(always, attempts=3, base_delay=0.0)
        snap = retry_stats_snapshot()
        assert snap["deadlock"] == 2, "두 번 다시 했다"
        assert snap["gave_up.deadlock"] == 1, "포기한 것이 안 세어졌다"

    def test_부른다고_세지_않는다(self):
        """다시 할 수 없는 오류는 숫자에 안 들어간다."""
        retry_stats_reset()
        with pytest.raises(_ClientError):
            retry_on_transient(lambda: (_ for _ in ()).throw(_ClientError("syntax")),
                               base_delay=0.0)
        assert retry_stats_snapshot() == {}
