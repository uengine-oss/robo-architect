# -*- coding: utf-8 -*-
"""탐색 시점의 분석 출처가 다음 프로젝트 분석 뒤에도 남는다."""

from contextlib import contextmanager

from api.features.ingestion.hybrid.contracts import RuleContext, RuleDTO
from api.features.ingestion.hybrid.mapper import rule_context
from api.features.ingestion.hybrid.ontology import neo4j_ops


class _Record(dict):
    pass


class _AnalyzerSession:
    def __init__(self, records):
        self.records = records
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def run(self, query, **params):
        self.params = params
        return self.records


class _WriteSession:
    def __init__(self):
        self.calls = []

    def run(self, query, **params):
        self.calls.append((query, params))


def test_live_graph_is_joined_by_routine_id_not_same_name(monkeypatch):
    live = _AnalyzerSession([_Record(
        rule_id="r1", summary="요약", actors=[], reads_tables=["EMP"],
        writes_tables=["LEAVE"], callers=[], callees=[],
        parent_module="m", parent_package="p",
    )])
    monkeypatch.setattr(rule_context, "analyzer_session", lambda: live)
    rule = RuleDTO(
        id="r1", given="g", when="w", then="t",
        source_function="applyLeave", source_module="routine-immutable-id",
    )

    out = rule_context.build_rule_contexts([rule])

    assert live.params["sources"] == [{
        "rule_id": "r1", "function_name": "applyLeave",
        "routine_id": "routine-immutable-id",
    }]
    assert out[0].reads_tables == ["EMP"]
    assert "f._id = source.routine_id" in rule_context._FN_LOOKUP_QUERY


def test_missing_live_graph_keeps_rule_snapshot(monkeypatch):
    monkeypatch.setattr(rule_context, "analyzer_session", lambda: _AnalyzerSession([]))
    rule = RuleDTO(
        id="r1", given="g", when="w", then="t", source_function="gone",
        source_module="gone-id", source_summary="saved summary",
        reads_tables=["EMP"], writes_tables=["LEAVE"],
    )

    out = rule_context.build_rule_contexts([rule])[0]

    assert out.function_summary == "saved summary"
    assert out.reads_tables == ["EMP"]
    assert out.writes_tables == ["LEAVE"]


def test_exploration_persists_rule_properties_and_table_edges(monkeypatch):
    writer = _WriteSession()

    @contextmanager
    def session():
        yield writer

    monkeypatch.setattr(neo4j_ops, "get_session", session)
    ctx = RuleContext(
        rule_id="r1", given="g", when="w", then="t",
        function_summary="요약", reads_tables=["EMP"],
        writes_tables=["EMP", "LEAVE"],
    )

    neo4j_ops.save_rule_contexts("s1", [ctx])

    assert writer.calls[0][1]["reads"] == ["EMP"]
    assert writer.calls[0][1]["writes"] == ["EMP", "LEAVE"]
    edge_params = [params for query, params in writer.calls[1:]]
    assert {(p["name"], p["direction"]) for p in edge_params} == {
        ("EMP", "READS"), ("EMP", "WRITES"), ("LEAVE", "WRITES"),
    }
    assert all(p["sid"] == "s1" for p in edge_params)
