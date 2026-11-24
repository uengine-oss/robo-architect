"""graph_subgraph — 어느 저장소에서나 받는 모양으로만 묻는지 · 합칠 때 중복이 없는지 (2026-11-24)."""

from api.platform import graph_subgraph as g


class _Rec(dict):
    def __getitem__(self, k):
        return dict.__getitem__(self, k)


class FakeSession:
    def __init__(self, answers):
        self.answers = answers
        self.queries = []

    def run(self, q, **params):
        self.queries.append(q)
        for key, rows in self.answers:
            if key in q:
                return [_Rec(r) for r in rows]
        return []


def test_never_uses_functions_the_store_lacks():
    s = FakeSession([])
    g.k_hop_nodes(s, ["a"], ["HAS_X"], 2)
    g.relationships_among(s, ["a", "b"], ["HAS_X"], with_properties=True)
    g.relationships_touching(s, ["a"])
    text = " ".join(s.queries)
    for bad in ("startNode(", "endNode(", "relationships(", "nodes(", "reduce("):
        assert bad not in text


def test_touching_merges_both_directions_once():
    rel = {"type": "HAS_X", "props": {}, "startId": "a", "endId": "b", "startLabels": [], "endLabels": []}
    s = FakeSession([("WHERE s.id IN", [{"rel": rel}]), ("WHERE e.id IN", [{"rel": rel}])])
    assert g.relationships_touching(s, ["a", "b"]) == [rel]


def test_rel_types_are_sanitised():
    s = FakeSession([])
    g.relationships_among(s, ["a"], ["HAS_X", "BAD]->(x) DETACH DELETE x //"])
    assert "DELETE" not in s.queries[0] and "[r:HAS_X]" in s.queries[0]
