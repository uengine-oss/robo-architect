from __future__ import annotations

from api.features.ingestion.hybrid.event_storming_bridge import promote_to_es


def test_attach_analyzer_traceability_counts_include_fallback(monkeypatch):
    """폴백은 BC 를 먼저 고른 뒤 그 id 로 붙인다.

    `WITH bc … LIMIT 1` 뒤에 다시 MATCH 를 두면 쓰기 앞의 마지막 읽기 절이
    WITH 가 아니게 되므로, BC 선택을 별도 읽기 질의로 분리했다. LIMIT 이
    BC 선택에만 걸린다는 원래 의도는 그대로다.
    """

    class _Rec(dict):
        pass

    class _Session:
        def __init__(self):
            self.queries: list[str] = []

        def run(self, query, **params):
            self.queries.append(query)
            # 1) sourced_from  2) 직접 attach  3) 첫 BC 선택  4) 폴백 attach
            idx = len(self.queries)
            rec = {1: _Rec(c=50), 2: _Rec(c=1), 3: _Rec(id="bc-1")}.get(idx, _Rec(c=3))
            return type("_R", (), {"single": lambda _s, r=rec: r})()

    class _Ctx:
        def __init__(self, s):
            self.s = s

        def __enter__(self):
            return self.s

        def __exit__(self, exc_type, exc, tb):
            return False

    sess = _Session()
    monkeypatch.setattr(promote_to_es, "get_session", lambda: _Ctx(sess))

    counts = promote_to_es._attach_analyzer_traceability("sid-1")

    assert counts["sourced_from"] == 50
    assert counts["attached_to"] == 4

    bc_pick, fallback = sess.queries[2], sess.queries[3]
    assert "ORDER BY bc.key LIMIT 1" in bc_pick
    assert "MERGE" not in bc_pick          # BC 선택은 읽기 전용이다
    assert "MATCH (q:QUESTION)" in fallback
    assert "$bid" in fallback              # 고른 BC 를 파라미터로 받는다
