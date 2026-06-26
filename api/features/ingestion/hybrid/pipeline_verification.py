from __future__ import annotations

from api.platform.neo4j import get_session


def verify_pipeline_status(session_id: str) -> dict:
    """Return end-to-end readiness for
    BPM 생성 > Rule 매핑 > ES 승격 > PRD 생성.
    """

    with get_session() as s:
        bpm = s.run(
            """
            MATCH (p:BpmProcess {session_id: $sid})
            WITH count(p) AS processes
            MATCH (t:BpmTask {session_id: $sid})
            WITH processes, count(t) AS tasks
            MATCH (a:BpmActor {session_id: $sid})
            RETURN processes, tasks, count(a) AS actors
            """,
            sid=session_id,
        ).single()

        mapping = s.run(
            """
            MATCH (t:BpmTask {session_id: $sid})
            OPTIONAL MATCH (t)-[:REALIZED_BY]->(r:Rule {session_id: $sid})
            WITH t, count(r) AS rc
            RETURN count(*) AS total_tasks,
                   count(CASE WHEN rc > 0 THEN 1 END) AS mapped_tasks,
                   count(CASE WHEN rc = 0 THEN 1 END) AS zero_rule_tasks
            """,
            sid=session_id,
        ).single()

        es = s.run(
            """
            MATCH (us:UserStory {session_id: $sid})
            WITH count(us) AS user_stories
            MATCH (bc:BoundedContext {session_id: $sid})
            WITH user_stories, count(bc) AS bounded_contexts
            MATCH (agg:Aggregate {session_id: $sid})
            WITH user_stories, bounded_contexts, count(agg) AS aggregates
            MATCH (cmd:Command {session_id: $sid})
            WITH user_stories, bounded_contexts, aggregates, count(cmd) AS commands
            MATCH (evt:Event {session_id: $sid})
            WITH user_stories, bounded_contexts, aggregates, commands, count(evt) AS events
            MATCH (pol:Policy {session_id: $sid})
            WITH user_stories, bounded_contexts, aggregates, commands, events, count(pol) AS policies
            MATCH (rm:ReadModel {session_id: $sid})
            RETURN user_stories, bounded_contexts, aggregates, commands, events, policies, count(rm) AS readmodels
            """,
            sid=session_id,
        ).single()

        edges = s.run(
            """
            MATCH (t:BpmTask {session_id: $sid})-[pt:PROMOTED_TO]->(us:UserStory {session_id: $sid})
            WITH count(pt) AS promoted_to
            MATCH (us:UserStory {session_id: $sid})-[sf:SOURCED_FROM]->(:Rule {session_id: $sid})
            WITH promoted_to, count(sf) AS sourced_from
            MATCH (us2:UserStory {session_id: $sid})-[imp:IMPLEMENTS]->(:BoundedContext {session_id: $sid})
            RETURN promoted_to, sourced_from, count(imp) AS implements_bc
            """,
            sid=session_id,
        ).single()

        question = s.run(
            """
            MATCH (q:QUESTION) WHERE q.session_id IS NULL
            OPTIONAL MATCH (q)-[:ATTACHED_TO]->(bc:BoundedContext {session_id: $sid})
            RETURN count(DISTINCT q) AS total_questions,
                   count(DISTINCT CASE WHEN bc IS NOT NULL THEN q END) AS attached_questions
            """,
            sid=session_id,
        ).single()

    bpm_ok = bool(bpm and bpm["processes"] > 0 and bpm["tasks"] > 0)
    mapping_ok = bool(mapping and mapping["mapped_tasks"] > 0)
    es_ok = bool(es and es["user_stories"] > 0 and es["bounded_contexts"] > 0 and es["aggregates"] > 0 and es["commands"] > 0)
    prd_ready = bool(es_ok and edges and edges["promoted_to"] > 0 and edges["implements_bc"] > 0)

    return {
        "session_id": session_id,
        "summary": {
            "pipeline_ready": bool(bpm_ok and mapping_ok and es_ok and prd_ready),
            "bpm_ok": bpm_ok,
            "mapping_ok": mapping_ok,
            "es_ok": es_ok,
            "prd_ready": prd_ready,
        },
        "counts": {
            "bpm": dict(bpm) if bpm else {},
            "mapping": dict(mapping) if mapping else {},
            "es": dict(es) if es else {},
            "traceability_edges": dict(edges) if edges else {},
            "question_attach": dict(question) if question else {},
        },
        "notes": [
            "BPM: BpmProcess/BpmTask 존재 여부",
            "Rule mapping: BpmTask-REALIZED_BY coverage",
            "ES promotion: UserStory/BC/Aggregate/Command 존재 여부",
            "PRD readiness: PROMOTED_TO + IMPLEMENTS(US->BC) 체인",
        ],
    }
