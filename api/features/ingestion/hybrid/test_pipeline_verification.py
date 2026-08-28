from __future__ import annotations

from api.features.ingestion.hybrid import pipeline_verification


class _Result:
    def __init__(self, value):
        self._value = value

    def single(self):
        return None if self._value is None else {"c": self._value}


class _Session:
    """각 지표가 독립 쿼리로 실행되므로, Cypher 본문을 보고 값을 돌려준다."""

    def __init__(self, values: dict):
        self.values = values

    def run(self, query, **params):
        q = " ".join(query.split())
        for pattern, value in self.values.items():
            if pattern in q:
                return _Result(value)
        return _Result(0)


class _Ctx:
    def __init__(self, s):
        self.s = s

    def __enter__(self):
        return self.s

    def __exit__(self, exc_type, exc, tb):
        return False


def _patch(monkeypatch, values):
    monkeypatch.setattr(pipeline_verification, "get_session", lambda: _Ctx(_Session(values)))


# 순서에 의존하지 않도록 각 쿼리를 특징짓는 문자열을 키로 쓴다.
_BPM = {
    "MATCH (p:BpmProcess": 2,
    "MATCH (t:BpmTask {session_id: $sid}) RETURN": 19,
    "MATCH (a:BpmActor": 4,
}
_ES = {
    "(n:UserStory": 19,
    "(n:BoundedContext": 3,
    "(n:Aggregate": 3,
    "(n:Command": 22,
    "(n:Event": 40,
    "(n:Policy": 18,
    "(n:ReadModel": 10,
}
_CHAIN = {
    "rel:PROMOTED_TO": 19,
    "rel:IMPLEMENTS": 19,
}


def test_document_path_ready_without_rule_mapping(monkeypatch):
    """문서 업로드 경로: 세션 Rule 이 없으면 Rule 매핑은 해당 사항 없음.

    Agentic Retrieval 은 사용자가 실행하는 지연 단계라, 실행하지 않아도
    파이프라인은 완주로 판정돼야 한다. 원문 근거는 Task->DocumentPassage 가
    담당한다.
    """
    _patch(monkeypatch, {
        **_BPM, **_ES, **_CHAIN,
        "(r:Rule {session_id: $sid})": 0,
        "rel:SOURCED_FROM]->(:DocumentPassage": 38,
        "[:SOURCED_FROM]->(:DocumentPassage": 19,
        "(p:DocumentPassage": 39,
    })
    out = pipeline_verification.verify_pipeline_status("a149dfd5")

    assert out["source_kind"] == "document"
    assert out["summary"]["mapping_applicable"] is False
    assert out["summary"]["mapping_ok"] is True
    assert out["summary"]["grounding_ok"] is True
    assert out["summary"]["prd_ready"] is True
    assert out["summary"]["pipeline_ready"] is True


def test_traceability_edges_always_reported(monkeypatch):
    """US->Rule 이 0 이어도 나머지 관계 건수가 사라지지 않아야 한다.

    이전 구현은 세 관계를 하나의 연쇄 MATCH 로 묶어, 중간의 SOURCED_FROM 이
    0 이면 traceability_edges 전체가 빈 dict 가 됐다.
    """
    _patch(monkeypatch, {
        **_BPM, **_ES, **_CHAIN,
        "(r:Rule {session_id: $sid})": 0,
        "rel:SOURCED_FROM]->(:Rule": 0,
        "rel:SOURCED_FROM]->(:DocumentPassage": 38,
    })
    edges = pipeline_verification.verify_pipeline_status("a149dfd5")["counts"]["traceability_edges"]

    assert edges["sourced_from"] == 0
    assert edges["promoted_to"] == 19
    assert edges["implements_bc"] == 19
    assert edges["task_passage"] == 38


def test_zero_readmodel_keeps_es_ok(monkeypatch):
    """ReadModel 0 건이 ES 승격 실패로 오판되지 않아야 한다."""
    _patch(monkeypatch, {
        **_BPM, **_ES, **_CHAIN,
        "(n:ReadModel": 0,
        "(r:Rule {session_id: $sid})": 0,
        "rel:SOURCED_FROM]->(:DocumentPassage": 38,
    })
    out = pipeline_verification.verify_pipeline_status("a149dfd5")

    assert out["counts"]["es"]["readmodels"] == 0
    assert out["summary"]["es_ok"] is True


def test_analyzer_path_requires_rule_mapping(monkeypatch):
    """analyzer 경로: 세션 Rule 이 있으면 매핑되지 않은 상태는 미완료다."""
    _patch(monkeypatch, {
        **_BPM, **_ES, **_CHAIN,
        "(r:Rule {session_id: $sid})": 145,
        "-[:REALIZED_BY]->": 0,
        "rel:SOURCED_FROM]->(:Rule": 0,
    })
    out = pipeline_verification.verify_pipeline_status("sid-analyzer")

    assert out["source_kind"] == "analyzer"
    assert out["summary"]["mapping_applicable"] is True
    assert out["summary"]["mapping_ok"] is False
    assert out["summary"]["grounding_ok"] is False
    assert out["summary"]["pipeline_ready"] is False
    assert out["counts"]["mapping"]["zero_rule_tasks"] == 19


def test_empty_session_not_ready(monkeypatch):
    _patch(monkeypatch, {})
    out = pipeline_verification.verify_pipeline_status("sid-empty")

    assert out["summary"]["pipeline_ready"] is False
    assert out["summary"]["bpm_ok"] is False
    assert out["summary"]["es_ok"] is False
    assert out["counts"]["traceability_edges"]["promoted_to"] == 0
