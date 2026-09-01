from __future__ import annotations

from api.features.ingestion.hybrid.event_storming_bridge import promote_to_es


def test_attach_analyzer_traceability_creates_source_links(monkeypatch):
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
            return type("_R", (), {"single": lambda _s: _Rec(50)})()

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

    assert counts == {"sourced_from": 50}
    assert len(sess.queries) == 1
    assert "SOURCED_FROM" in sess.queries[0]
