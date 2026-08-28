from __future__ import annotations

from api.platform.neo4j import get_session


def _scalar(s, cypher: str, sid: str) -> int:
    """단일 집계값(`c`)을 반환하는 Cypher 를 실행한다.

    각 지표를 독립 쿼리로 분리하기 위한 헬퍼. 이전 구현은 여러 MATCH 를
    `WITH` 로 엮어 하나의 쿼리로 처리했는데, 중간 MATCH 가 0건이면 그 뒤
    행이 통째로 사라져 나머지 지표까지 `None` 이 됐다. 그 결과 "0건" 과
    "측정 실패" 를 구분할 수 없었고, ReadModel 이 없는 세션이 `es_ok=false`
    로, Rule 매핑을 하지 않은 문서 세션이 `traceability_edges={}` 로
    보고됐다. 지표 하나당 쿼리 하나면 항상 0 이상의 실수가 나온다.
    """
    rec = s.run(cypher, sid=sid).single()
    if not rec or rec["c"] is None:
        return 0
    return int(rec["c"])


def verify_pipeline_status(session_id: str) -> dict:
    """Return end-to-end readiness for
    BPM 생성 > Rule 매핑 > ES 승격 > PRD 생성.

    소스 경로에 따라 판정 기준이 달라진다.

    - analyzer 경로: 세션에 Rule 이 있고, `(BpmTask)-[:REALIZED_BY]->(Rule)`
      매핑과 그로부터 파생되는 `(UserStory)-[:SOURCED_FROM]->(Rule)` 이
      원문 근거가 된다.
    - 문서 업로드 경로: 세션에 Rule 이 생성되지 않는다. 원문 근거는
      `(BpmTask)-[:SOURCED_FROM]->(DocumentPassage)` 가 담당하며, Rule 매핑은
      애초에 해당 사항이 없다. 또한 Rule 매핑(Agentic Retrieval)은 비용
      최적화를 위해 사용자가 명시적으로 실행하는 지연 단계이므로(hybrid
      workflow runner Phase 3 참조) 파이프라인 완주 여부의 필수 조건이
      아니다.
    """

    with get_session() as s:
        processes = _scalar(s, "MATCH (p:BpmProcess {session_id: $sid}) RETURN count(p) AS c", session_id)
        tasks = _scalar(s, "MATCH (t:BpmTask {session_id: $sid}) RETURN count(t) AS c", session_id)
        actors = _scalar(s, "MATCH (a:BpmActor {session_id: $sid}) RETURN count(a) AS c", session_id)

        rules_in_session = _scalar(s, "MATCH (r:Rule {session_id: $sid}) RETURN count(r) AS c", session_id)
        mapped_tasks = _scalar(
            s,
            "MATCH (t:BpmTask {session_id: $sid})-[:REALIZED_BY]->(:Rule {session_id: $sid}) "
            "RETURN count(DISTINCT t) AS c",
            session_id,
        )

        es_counts = {
            "user_stories": _scalar(s, "MATCH (n:UserStory {session_id: $sid}) RETURN count(n) AS c", session_id),
            "bounded_contexts": _scalar(s, "MATCH (n:BoundedContext {session_id: $sid}) RETURN count(n) AS c", session_id),
            "aggregates": _scalar(s, "MATCH (n:Aggregate {session_id: $sid}) RETURN count(n) AS c", session_id),
            "commands": _scalar(s, "MATCH (n:Command {session_id: $sid}) RETURN count(n) AS c", session_id),
            "events": _scalar(s, "MATCH (n:Event {session_id: $sid}) RETURN count(n) AS c", session_id),
            "policies": _scalar(s, "MATCH (n:Policy {session_id: $sid}) RETURN count(n) AS c", session_id),
            "readmodels": _scalar(s, "MATCH (n:ReadModel {session_id: $sid}) RETURN count(n) AS c", session_id),
        }

        promoted_to = _scalar(
            s,
            "MATCH (:BpmTask {session_id: $sid})-[rel:PROMOTED_TO]->(:UserStory {session_id: $sid}) "
            "RETURN count(rel) AS c",
            session_id,
        )
        sourced_from = _scalar(
            s,
            "MATCH (:UserStory {session_id: $sid})-[rel:SOURCED_FROM]->(:Rule {session_id: $sid}) "
            "RETURN count(rel) AS c",
            session_id,
        )
        implements_bc = _scalar(
            s,
            "MATCH (:UserStory {session_id: $sid})-[rel:IMPLEMENTS]->(:BoundedContext {session_id: $sid}) "
            "RETURN count(rel) AS c",
            session_id,
        )
        task_passages = _scalar(
            s,
            "MATCH (:BpmTask {session_id: $sid})-[rel:SOURCED_FROM]->(:DocumentPassage {session_id: $sid}) "
            "RETURN count(rel) AS c",
            session_id,
        )
        grounded_tasks = _scalar(
            s,
            "MATCH (t:BpmTask {session_id: $sid})-[:SOURCED_FROM]->(:DocumentPassage {session_id: $sid}) "
            "RETURN count(DISTINCT t) AS c",
            session_id,
        )
        passages = _scalar(s, "MATCH (p:DocumentPassage {session_id: $sid}) RETURN count(p) AS c", session_id)

        total_questions = _scalar(s, "MATCH (q:QUESTION) WHERE q.session_id IS NULL RETURN count(q) AS c", session_id)
        attached_questions = _scalar(
            s,
            "MATCH (q:QUESTION) WHERE q.session_id IS NULL "
            "MATCH (q)-[:ATTACHED_TO]->(:BoundedContext {session_id: $sid}) "
            "RETURN count(DISTINCT q) AS c",
            session_id,
        )

    # 세션에 Rule 이 없으면 문서 업로드 경로 — Rule 매핑은 해당 사항 없음.
    source_kind = "analyzer" if rules_in_session > 0 else "document"
    mapping_applicable = rules_in_session > 0

    bpm_ok = processes > 0 and tasks > 0
    es_ok = (
        es_counts["user_stories"] > 0
        and es_counts["bounded_contexts"] > 0
        and es_counts["aggregates"] > 0
        and es_counts["commands"] > 0
    )
    mapping_ok = (mapped_tasks > 0) if mapping_applicable else True
    # 원문 근거: analyzer 는 US→Rule, 문서 경로는 Task→DocumentPassage.
    grounding_ok = sourced_from > 0 if mapping_applicable else task_passages > 0
    prd_ready = es_ok and promoted_to > 0 and implements_bc > 0

    return {
        "session_id": session_id,
        "source_kind": source_kind,
        "summary": {
            "pipeline_ready": bool(bpm_ok and mapping_ok and es_ok and prd_ready),
            "bpm_ok": bpm_ok,
            "mapping_ok": mapping_ok,
            "mapping_applicable": mapping_applicable,
            "es_ok": es_ok,
            "grounding_ok": grounding_ok,
            "prd_ready": prd_ready,
        },
        "counts": {
            "bpm": {"processes": processes, "tasks": tasks, "actors": actors},
            "mapping": {
                "total_tasks": tasks,
                "mapped_tasks": mapped_tasks,
                "zero_rule_tasks": max(tasks - mapped_tasks, 0),
                "session_rules": rules_in_session,
            },
            "es": es_counts,
            "traceability_edges": {
                "promoted_to": promoted_to,
                "sourced_from": sourced_from,
                "implements_bc": implements_bc,
                "task_passage": task_passages,
            },
            "grounding": {
                "passages": passages,
                "grounded_tasks": grounded_tasks,
                "ungrounded_tasks": max(tasks - grounded_tasks, 0),
            },
            "question_attach": {
                "total_questions": total_questions,
                "attached_questions": attached_questions,
            },
        },
        "notes": [
            "BPM: BpmProcess/BpmTask 존재 여부",
            "Rule mapping: BpmTask-REALIZED_BY coverage (문서 업로드 경로는 해당 없음 — 사용자가 실행하는 지연 단계)",
            "ES promotion: UserStory/BC/Aggregate/Command 존재 여부",
            "Grounding: analyzer 는 US->Rule(SOURCED_FROM), 문서 경로는 BpmTask->DocumentPassage",
            "PRD readiness: PROMOTED_TO + IMPLEMENTS(US->BC) 체인",
        ],
    }
