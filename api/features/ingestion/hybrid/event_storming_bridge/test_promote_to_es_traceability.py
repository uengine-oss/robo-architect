from __future__ import annotations

from api.features.ingestion.hybrid.event_storming_bridge import promote_to_es


def test_attach_analyzer_traceability_counts_include_fallback(monkeypatch):
    class _Rec:
        def __init__(self, c: int):
            self._c = c

        def __getitem__(self, key):
            if key == "c":
                return self._c
            raise KeyError(key)

    class _Session:
        def __init__(self):
            self.queries: list[str] = []

        def run(self, query, **params):
            self.queries.append(query)
            # 1st run: sourced_from, 2nd run: direct question attach, 3rd run: fallback
            idx = len(self.queries)
            if idx == 1:
                return type("_R", (), {"single": lambda _s: _Rec(50)})()
            if idx == 2:
                return type("_R", (), {"single": lambda _s: _Rec(1)})()
            return type("_R", (), {"single": lambda _s: _Rec(3)})()

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
    fallback_query = sess.queries[2]
    assert "WITH bc ORDER BY bc.key LIMIT 1" in fallback_query
    assert "MATCH (q:QUESTION)" in fallback_query
