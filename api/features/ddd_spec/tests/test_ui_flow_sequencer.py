"""Tests for the UI-flow topological sort (T041, research D8)."""
from __future__ import annotations

import random

from api.features.ddd_spec.ui_flow_sequencer import (
    _priority_index,
    build_tiebreaker,
    sequence_topological,
)


def _tb_minimal(node_keys: list[str]):
    """Tiebreaker that uses the lexical key — fine for tests where the node
    name encodes the desired order."""
    return lambda k: (k,)


def test_causal_chain_upstream_before_downstream():
    nodes = ["bcA/US1/ui1", "bcB/US2/ui1"]
    edges = [("bcA/US1/ui1", "bcB/US2/ui1")]
    ordered, broken = sequence_topological(nodes, edges, _tb_minimal(nodes))
    assert ordered == ["bcA/US1/ui1", "bcB/US2/ui1"]
    assert broken == []


def test_cycle_breaks_back_edge_with_largest_tiebreaker():
    nodes = ["a", "b", "c"]
    # a -> b, b -> c, c -> a forms a 3-node cycle. The algorithm breaks
    # the edge whose destination has the max tiebreaker — 'c' — and whose
    # source is the largest among 'c's incoming edges — 'b'. So (b, c) is
    # removed; remaining edges are a->b and c->a, whose topological order
    # is c → a → b.
    edges = [("a", "b"), ("b", "c"), ("c", "a")]
    ordered, broken = sequence_topological(nodes, edges, _tb_minimal(nodes))
    assert set(ordered) == {"a", "b", "c"}
    assert broken == [("b", "c")]
    # Surviving edges must be respected.
    surviving = [e for e in edges if e not in broken]
    for src, dst in surviving:
        assert ordered.index(src) < ordered.index(dst)


def test_single_bc_no_edges_falls_back_to_tiebreaker_order():
    nodes = ["bcX/US1/ui1", "bcX/US2/ui1", "bcX/US3/ui1"]
    ordered, broken = sequence_topological(nodes, [], _tb_minimal(nodes))
    assert ordered == ["bcX/US1/ui1", "bcX/US2/ui1", "bcX/US3/ui1"]
    assert broken == []


def test_island_node_still_emitted():
    nodes = ["a", "b", "c"]  # 'c' is an island
    edges = [("a", "b")]
    ordered, broken = sequence_topological(nodes, edges, _tb_minimal(nodes))
    assert set(ordered) == {"a", "b", "c"}
    assert ordered.index("a") < ordered.index("b")
    assert broken == []


def test_determinism_under_input_shuffle():
    """SC-010: same logical input → same byte-stable ordering."""
    nodes = [f"bc{i % 3}/US{i}/ui1" for i in range(12)]
    edges = [
        (nodes[0], nodes[5]),
        (nodes[1], nodes[6]),
        (nodes[2], nodes[7]),
    ]
    baseline, _ = sequence_topological(nodes, edges, _tb_minimal(nodes))
    rng = random.Random(42)
    for _ in range(20):
        shuffled_nodes = list(nodes)
        rng.shuffle(shuffled_nodes)
        shuffled_edges = list(edges)
        rng.shuffle(shuffled_edges)
        out, _ = sequence_topological(
            shuffled_nodes, shuffled_edges, _tb_minimal(nodes)
        )
        assert out == baseline


def test_priority_index_orders_correctly():
    assert _priority_index("P1") < _priority_index("P3")
    assert _priority_index("P3") < _priority_index(None)
    assert _priority_index("") == _priority_index(None)


def test_build_tiebreaker_uses_full_key_tuple():
    bc_index = {"bcA": 0, "bcB": 1}
    story_index = {"US1": (0, "P1"), "US2": (1, "P2"), "US3": (0, None)}
    ui_index = {"US1/u1": 0, "US2/u1": 0, "US3/u1": 0}
    tb = build_tiebreaker(bc_index, story_index, ui_index)
    # bcA's P1 story sorts ahead of bcB's P2 story.
    assert tb("bcA/US1/u1") < tb("bcB/US2/u1")
    # Within bcA: P1 (US1) before priority-less (US3).
    assert tb("bcA/US1/u1") < tb("bcA/US3/u1")
