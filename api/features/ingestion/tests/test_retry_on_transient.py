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
