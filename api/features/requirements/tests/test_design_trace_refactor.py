"""Regression test for the `_expand_trace` extraction (spec 039 T002-T004).

The User-Story design-trace and the BPM-task design-trace now share
`_expand_trace`. This pins the extracted helper's behaviour on a fake session so
the refactor can't silently change the trace shape both routes depend on.
"""

from __future__ import annotations

from api.features.requirements.routes import design_trace


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def single(self):
        return self._rows[0] if self._rows else None

    def __iter__(self):
        return iter(self._rows)


class _Session:
    """Scripts a tiny graph: Command cmd1 owned by agg1, screen ui1 attached,
    emitting evt1 which triggers pol1 invoking cmd2 (terminal)."""

    def run(self, query, **params):
        cid = params.get("cmd_id")
        if "RETURN cmd {.*} AS cmd" in query:  # seed root command
            return _Result([{"cmd": {"id": params["id"], "name": params["id"]}}])
        if "HAS_COMMAND]->(cmd:Command {id: $cmd_id})" in query:
            if cid == "cmd1":
                return _Result([{"agg": {"id": "agg1", "name": "Agg"}}])
            return _Result([])
        if "(ui:UI)-[:ATTACHED_TO]->(cmd:Command {id: $cmd_id})" in query:
            if cid == "cmd1":
                return _Result([{"ui": {"id": "ui1", "name": "Screen"}}])
            return _Result([])
        if "[:EMITS]->(evt:Event)" in query:
            if cid == "cmd1":
                return _Result([{
                    "evt": {"id": "evt1", "name": "Evt"},
                    "pol": {"id": "pol1", "name": "Pol"},
                    "next": {"id": "cmd2", "name": "Cmd2"},
                }])
            return _Result([])
        if "HAS_PROPERTY" in query:
            return _Result([])
        return _Result([])


def test_expand_trace_shapes_full_chain():
    nodes, rels = design_trace._expand_trace(_Session(), ["cmd1"], depth=2)

    assert set(nodes.keys()) == {"cmd1", "agg1", "ui1", "evt1", "pol1", "cmd2"}
    assert nodes["cmd1"]["type"] == "Command"
    assert nodes["agg1"]["type"] == "Aggregate"
    assert nodes["ui1"]["type"] == "UI"
    assert nodes["evt1"]["type"] == "Event"
    assert nodes["pol1"]["type"] == "Policy"

    rel_set = {(r["source"], r["target"], r["type"]) for r in rels}
    assert ("agg1", "cmd1", "HAS_COMMAND") in rel_set
    assert ("ui1", "cmd1", "ATTACHED_TO") in rel_set
    assert ("cmd1", "evt1", "EMITS") in rel_set
    assert ("evt1", "pol1", "TRIGGERS") in rel_set
    assert ("pol1", "cmd2", "INVOKES") in rel_set


def test_expand_trace_unknown_root_yields_empty():
    class _Empty:
        def run(self, query, **params):
            return _Result([])

    nodes, rels = design_trace._expand_trace(_Empty(), ["ghost"], depth=2)
    assert nodes == {}
    assert rels == []


def test_expand_trace_depth_one_stops_before_next_command():
    # depth=1 expands cmd1's neighbours but does not expand cmd2 further.
    nodes, _ = design_trace._expand_trace(_Session(), ["cmd1"], depth=1)
    # cmd2 is discovered as a node (via INVOKES) but not itself expanded.
    assert "cmd2" in nodes
