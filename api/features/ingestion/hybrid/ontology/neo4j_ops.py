"""Neo4j write operations for the hybrid ontology."""

from __future__ import annotations

from api.features.ingestion.hybrid.contracts import (
    ActivityRuleMapping,
    BpmActor,
    BpmProcess,
    BpmSequenceDTO,
    BpmSkeleton,
    BpmTaskDTO,
    DocumentPassage,
    GlossaryTerm,
    RuleDTO,
    TaskPassageLink,
)
from api.features.ingestion.hybrid.ontology.schema import (
    ALL_HYBRID_LABELS,
    L_ACTIVITY_MAPPING,
    L_BPM_ACTOR,
    L_BPM_PROCESS,
    L_BPM_SEQUENCE,
    L_BPM_TASK,
    L_BPMN_EVENT,
    L_BPMN_GATEWAY,
    L_BPMN_PROCESS,
    L_DOCUMENT_PASSAGE,
    L_EXTERNAL_TABLE,
    L_GLOSSARY_TERM,
    L_HYBRID_SESSION,
    L_RULE,
    R_CONTAINS,
    R_EVALUATES,
    R_HAS_ACTOR,
    R_HAS_TASK,
    R_IMPLEMENTED_BY,
    R_NEXT,
    R_PERFORMS,
    R_REALIZED_BY,
    R_SOURCED_FROM,
)
from api.platform.neo4j import ANALYZER_NEO4J_DATABASE, get_session


def clear_hybrid_nodes(session_id: str) -> dict[str, int]:
    """Clear hybrid-owned nodes for a given ingestion session. Leaves analyzer/event storming alone."""
    counts: dict[str, int] = {}
    with get_session() as s:
        for label in ALL_HYBRID_LABELS:
            r = s.run(
                f"MATCH (n:{label} {{session_id: $sid}}) WITH n, count(n) AS c DETACH DELETE n RETURN c",
                sid=session_id,
            ).single()
            if r and r["c"]:
                counts[label] = r["c"]
    return counts


def clear_all_hybrid_workspace() -> dict[str, int]:
    """Wipe every hybrid-owned node across all sessions. Analyzer/event-storming labels are
    NOT touched — safe to call even when analyzer and hybrid share the same Neo4j database.
    """
    counts: dict[str, int] = {}
    with get_session() as s:
        for label in ALL_HYBRID_LABELS:
            r = s.run(
                f"MATCH (n:{label}) WITH n, count(n) AS c DETACH DELETE n RETURN c"
            ).single()
            if r and r["c"]:
                counts[label] = r["c"]
    return counts


def save_bpm_processes(session_id: str, processes: list[BpmProcess]) -> None:
    """Persist BpmProcess identity nodes. Idempotent on (id, session_id).

    Does NOT create HAS_TASK / HAS_ACTOR edges — those are wired by
    `save_bpm_skeleton` which knows each skeleton's task/actor ids.
    """
    if not processes:
        return
    with get_session() as s:
        for p in processes:
            s.run(
                f"MERGE (p:{L_BPM_PROCESS} {{id: $id, session_id: $sid}}) "
                "SET p.name = $name, p.domain_keywords = $keywords, "
                "    p.source_pdf_name = $pdf_name, p.updated_at = datetime()",
                id=p.id, sid=session_id, name=p.name,
                keywords=list(p.domain_keywords or []),
                pdf_name=p.source_pdf_name,
            )


def save_bpm_skeleton(session_id: str, skeleton: BpmSkeleton) -> None:
    """Persist actors, tasks, sequences, and NEXT relations to Neo4j.
    Also writes a :HybridSession marker node holding the bpmn_xml so the
    frontend can rehydrate the canvas without relying on localStorage.

    If `skeleton.process` is set, each Actor/Task node is stamped with the
    `process_id` property and connected via (BpmProcess)-[:HAS_TASK]/[:HAS_ACTOR].
    """
    process = skeleton.process
    pid = process.id if process else None
    with get_session() as s:
        s.run(
            f"MERGE (h:{L_HYBRID_SESSION} {{id: $sid, session_id: $sid}}) "
            "SET h.bpmn_xml = $xml, h.updated_at = datetime()",
            sid=session_id, xml=skeleton.bpmn_xml or "",
        )
        if process is not None:
            s.run(
                f"MERGE (p:{L_BPM_PROCESS} {{id: $id, session_id: $sid}}) "
                "SET p.name = $name, p.description = $desc, "
                "    p.domain_keywords = $keywords, "
                "    p.source_pdf_name = $pdf_name, p.bpmn_xml = $xml, "
                "    p.updated_at = datetime()",
                id=process.id, sid=session_id, name=process.name,
                desc=process.description,
                keywords=list(process.domain_keywords or []),
                pdf_name=process.source_pdf_name,
                xml=skeleton.bpmn_xml or "",
            )
        for actor in skeleton.actors:
            s.run(
                f"MERGE (a:{L_BPM_ACTOR} {{id: $id, session_id: $sid}}) "
                "SET a.name = $name, a.description = $description, a.process_id = $pid",
                id=actor.id, sid=session_id, name=actor.name,
                description=actor.description, pid=pid,
            )
            if pid:
                s.run(
                    f"MATCH (p:{L_BPM_PROCESS} {{id: $pid, session_id: $sid}}), "
                    f"(a:{L_BPM_ACTOR} {{id: $aid, session_id: $sid}}) "
                    f"MERGE (p)-[:{R_HAS_ACTOR}]->(a)",
                    pid=pid, aid=actor.id, sid=session_id,
                )
        for task in skeleton.tasks:
            s.run(
                f"MERGE (t:{L_BPM_TASK} {{id: $id, session_id: $sid}}) "
                "SET t.name = $name, t.description = $description, "
                "    t.sequence_index = $seq, t.source_page = $page, "
                "    t.source_section = $section, t.process_id = $pid",
                id=task.id, sid=session_id, name=task.name, description=task.description,
                seq=task.sequence_index, page=task.source_page,
                section=task.source_section, pid=pid,
            )
            if pid:
                s.run(
                    f"MATCH (p:{L_BPM_PROCESS} {{id: $pid, session_id: $sid}}), "
                    f"(t:{L_BPM_TASK} {{id: $tid, session_id: $sid}}) "
                    f"MERGE (p)-[:{R_HAS_TASK}]->(t)",
                    pid=pid, tid=task.id, sid=session_id,
                )
            for actor_id in task.actor_ids:
                s.run(
                    f"MATCH (a:{L_BPM_ACTOR} {{id: $aid, session_id: $sid}}), "
                    f"(t:{L_BPM_TASK} {{id: $tid, session_id: $sid}}) "
                    f"MERGE (a)-[:{R_PERFORMS}]->(t)",
                    aid=actor_id, tid=task.id, sid=session_id,
                )
        for seq in skeleton.sequences:
            s.run(
                f"MERGE (q:{L_BPM_SEQUENCE} {{id: $id, session_id: $sid}}) "
                "SET q.name = $name, q.process_id = $pid",
                id=seq.id, sid=session_id, name=seq.name, pid=pid,
            )
            # CONTAINS edges
            for tid in seq.task_ids:
                s.run(
                    f"MATCH (q:{L_BPM_SEQUENCE} {{id: $qid, session_id: $sid}}), "
                    f"(t:{L_BPM_TASK} {{id: $tid, session_id: $sid}}) "
                    f"MERGE (q)-[:{R_CONTAINS}]->(t)",
                    qid=seq.id, tid=tid, sid=session_id,
                )
            # NEXT chain
            for i in range(len(seq.task_ids) - 1):
                s.run(
                    f"MATCH (a:{L_BPM_TASK} {{id: $a, session_id: $sid}}), "
                    f"(b:{L_BPM_TASK} {{id: $b, session_id: $sid}}) "
                    f"MERGE (a)-[:{R_NEXT}]->(b)",
                    a=seq.task_ids[i], b=seq.task_ids[i + 1], sid=session_id,
                )


def link_process_module(
    session_id: str, process_id: str, module_fqn: str,
    confidence: float = 1.0, method: str = "agent_step1",
) -> None:
    """Persist §2.F — (BpmProcess)-[:IMPLEMENTED_BY]->(MODULE) across DBs.

    MODULE lives in the analyzer DB, so we can't create a real Neo4j edge.
    Instead we append to three parallel lists on BpmProcess:
      `implemented_by` (fqn), `implemented_by_confidence`, `implemented_by_method`.
    `replace_process_modules` below atomically rewrites all three from scratch —
    use that when recomputing Step 1 for a process.
    """
    if not (process_id and module_fqn):
        return
    with get_session() as s:
        # Dedup by fqn — if already present, overwrite its parallel entries.
        s.run(
            f"""
            MATCH (p:{L_BPM_PROCESS} {{id: $pid, session_id: $sid}})
            WITH p,
                 coalesce(p.implemented_by, []) AS fqns,
                 coalesce(p.implemented_by_confidence, []) AS confs,
                 coalesce(p.implemented_by_method, []) AS methods
            WITH p, fqns, confs, methods,
                 [i IN range(0, size(fqns) - 1) WHERE fqns[i] <> $fqn] AS keep_idx
            WITH p,
                 [i IN keep_idx | fqns[i]]    AS fqns_filtered,
                 [i IN keep_idx | confs[i]]   AS confs_filtered,
                 [i IN keep_idx | methods[i]] AS methods_filtered
            SET p.implemented_by            = fqns_filtered + [$fqn],
                p.implemented_by_confidence = confs_filtered + [$conf],
                p.implemented_by_method     = methods_filtered + [$method]
            """,
            pid=process_id, sid=session_id, fqn=module_fqn,
            conf=float(confidence), method=method,
        )


def replace_process_modules(
    session_id: str, process_id: str,
    entries: list[tuple[str, float, str]],
) -> None:
    """Atomically rewrite the IMPLEMENTED_BY list on a process. Each entry is
    (module_fqn, confidence, method). Use when Step 1 recomputes from scratch."""
    if not process_id:
        return
    fqns = [e[0] for e in entries]
    confs = [float(e[1]) for e in entries]
    methods = [e[2] for e in entries]
    with get_session() as s:
        s.run(
            f"MATCH (p:{L_BPM_PROCESS} {{id: $pid, session_id: $sid}}) "
            "SET p.implemented_by = $fqns, "
            "    p.implemented_by_confidence = $confs, "
            "    p.implemented_by_method = $methods",
            pid=process_id, sid=session_id,
            fqns=fqns, confs=confs, methods=methods,
        )


def fetch_processes_for_session(session_id: str) -> list[dict]:
    """Return every BpmProcess for a session with its task/actor ids."""
    with get_session() as s:
        rows = list(s.run(
            f"""
            MATCH (p:{L_BPM_PROCESS} {{session_id: $sid}})
            OPTIONAL MATCH (p)-[:{R_HAS_TASK}]->(t:{L_BPM_TASK} {{session_id: $sid}})
            WITH p, collect(DISTINCT t.id) AS task_ids
            OPTIONAL MATCH (p)-[:{R_HAS_ACTOR}]->(a:{L_BPM_ACTOR} {{session_id: $sid}})
            RETURN p, task_ids, collect(DISTINCT a.id) AS actor_ids
            ORDER BY p.name
            """,
            sid=session_id,
        ))
    result: list[dict] = []
    for r in rows:
        pd = {k: v for k, v in dict(r["p"]).items() if k != "session_id"}
        pd["task_ids"] = [t for t in (r["task_ids"] or []) if t]
        pd["actor_ids"] = [a for a in (r["actor_ids"] or []) if a]
        result.append(pd)
    return result


def save_rules(session_id: str, rules: list[RuleDTO]) -> None:
    """Persist Rule nodes keyed by (id, session_id). No task linkage — that's Phase 3."""
    if not rules:
        return
    with get_session() as s:
        for rule in rules:
            s.run(
                f"MERGE (r:{L_RULE} {{id: $id, session_id: $sid}}) "
                "SET r.given = $given, r.`when` = $when, r.`then` = $then, "
                "    r.source_function = $sf, r.source_module = $sm, r.confidence = $conf, "
                "    r.title = $title, r.context_cluster = $ctx, "
                "    r.es_role = $es_role, r.es_role_confidence = $es_role_conf",
                id=rule.id, sid=session_id,
                given=rule.given, when=rule.when, then=rule.then,
                sf=rule.source_function, sm=rule.source_module, conf=rule.confidence,
                title=rule.title, ctx=rule.context_cluster,
                es_role=rule.es_role, es_role_conf=rule.es_role_confidence,
            )


def update_rule_es_roles(session_id: str, role_map: dict[str, tuple[str, float]]) -> int:
    """Phase 2.6 — write back `es_role` + `es_role_confidence` on existing Rule nodes."""
    if not role_map:
        return 0
    updated = 0
    with get_session() as s:
        for rule_id, (role, conf) in role_map.items():
            if not role:
                continue
            rec = s.run(
                f"MATCH (r:{L_RULE} {{id: $rid, session_id: $sid}}) "
                "SET r.es_role = $role, r.es_role_confidence = $conf "
                "RETURN r.id AS id",
                rid=rule_id, sid=session_id, role=role, conf=float(conf),
            ).single()
            if rec:
                updated += 1
    return updated


def update_rule_context_clusters(session_id: str, rule_cluster_map: dict[str, str]) -> int:
    """Phase 2.5 — write back `context_cluster` onto existing Rule nodes.

    Returns number of rules updated. Idempotent (MERGE-compatible — only SET).
    """
    if not rule_cluster_map:
        return 0
    updated = 0
    with get_session() as s:
        for rule_id, cluster in rule_cluster_map.items():
            if not cluster:
                continue
            rec = s.run(
                f"MATCH (r:{L_RULE} {{id: $rid, session_id: $sid}}) "
                "SET r.context_cluster = $ctx "
                "RETURN r.id AS id",
                rid=rule_id, sid=session_id, ctx=cluster,
            ).single()
            if rec:
                updated += 1
    return updated


def fetch_rules(session_id: str) -> list[dict]:
    """Read back Rule nodes for a session (debug / downstream consumers)."""
    with get_session() as s:
        return [
            dict(rec["r"])
            for rec in s.run(
                f"MATCH (r:{L_RULE} {{session_id: $sid}}) RETURN r ORDER BY r.source_function, r.id",
                sid=session_id,
            )
        ]


def save_session_bpmn_xml(session_id: str, bpmn_xml: str) -> None:
    """Update the HybridSession marker's bpmn_xml. Used after Phase 1 has decided
    the final XML (A2A response or native build fallback)."""
    if not bpmn_xml:
        return
    with get_session() as s:
        s.run(
            f"MERGE (h:{L_HYBRID_SESSION} {{id: $sid, session_id: $sid}}) "
            "SET h.bpmn_xml = $xml, h.updated_at = datetime()",
            sid=session_id, xml=bpmn_xml,
        )


def relabel_pdf2bpmn_nodes(session_id: str) -> dict[str, int]:
    """Rename pdf2bpmn extractor's side-effect nodes to `Bpmn*` labels and tag
    them with our session_id. Resolves the `:Event` label clash with the
    event_storming pipeline (PRD §4.5.6 #1).

    pdf2bpmn 만의 고유 프로퍼티로 식별 — event_storming 의 :Event / :Process 노드
    (key/id/displayName 사용) 와 혼동되지 않는다.
    """
    counts: dict[str, int] = {}
    rules = [
        # (source_label, target_label, distinguishing_property)
        ("Event", L_BPMN_EVENT, "event_type"),
        ("Gateway", L_BPMN_GATEWAY, "gateway_type"),
        ("Process", L_BPMN_PROCESS, "proc_id"),
    ]
    with get_session() as s:
        for src, tgt, prop in rules:
            rec = s.run(
                f"MATCH (n:{src}) WHERE n.{prop} IS NOT NULL AND n.session_id IS NULL "
                f"SET n:{tgt}, n.session_id = $sid "
                f"REMOVE n:{src} "
                "RETURN count(n) AS c",
                sid=session_id,
            ).single()
            if rec and rec["c"]:
                counts[tgt] = int(rec["c"])
    return counts


def save_glossary(session_id: str, terms: list[GlossaryTerm]) -> None:
    if not terms:
        return
    with get_session() as s:
        for term in terms:
            s.run(
                f"MERGE (g:{L_GLOSSARY_TERM} {{term: $term, session_id: $sid}}) "
                "SET g.aliases = $aliases, g.code_candidates = $candidates, g.source = $source",
                term=term.term, sid=session_id,
                aliases=term.aliases, candidates=term.code_candidates, source=term.source,
            )


def save_mappings(
    session_id: str,
    mappings: list[ActivityRuleMapping],
    table_edges: list[tuple[str, str, str]] | None = None,
    review_mappings: list[ActivityRuleMapping] | None = None,
) -> None:
    """Persist Task↔Rule mappings + audit trail + Rule→Table EVALUATES.

    - `mappings` (auto-accepted): creates both REALIZED_BY edge AND ActivityMapping node.
    - `review_mappings` (review queue): creates ONLY ActivityMapping node, no edge.
      Snapshot endpoint filters AMs without a REALIZED_BY edge to surface the
      review queue. Accept/reject endpoints rely on the AM node existing.
    """
    if not mappings and not table_edges and not review_mappings:
        return
    with get_session() as s:
        for m in mappings or []:
            s.run(
                f"MATCH (t:{L_BPM_TASK} {{id: $tid, session_id: $sid}}), "
                f"(r:{L_RULE} {{id: $rid, session_id: $sid}}) "
                f"MERGE (t)-[rel:{R_REALIZED_BY}]->(r) "
                "SET rel.confidence = $score, rel.method = $method, rel.reviewed = $reviewed, "
                "    rel.rationale = $rationale, rel.evidence_refs = $evidence_refs, "
                "    rel.evidence_path = $evidence_path, rel.agent_verdict = $agent_verdict",
                tid=m.task_id, rid=m.rule_id, sid=session_id,
                score=m.score, method=m.method, reviewed=m.reviewed,
                rationale=m.rationale, evidence_refs=list(m.evidence_refs or []),
                evidence_path=list(m.evidence_path or []),
                agent_verdict=m.agent_verdict,
            )
            amid = f"am_{m.task_id}_{m.rule_id}"
            s.run(
                f"MERGE (am:{L_ACTIVITY_MAPPING} {{id: $id, session_id: $sid}}) "
                "SET am.task_id = $tid, am.rule_id = $rid, am.score = $score, "
                "    am.method = $method, am.reviewed = $reviewed, "
                "    am.rationale = $rationale",
                id=amid, sid=session_id, tid=m.task_id, rid=m.rule_id,
                score=m.score, method=m.method, reviewed=m.reviewed,
                rationale=m.rationale,
            )
        # Review queue — persist AM node only, no REALIZED_BY edge. This lets
        # users accept/reject from the UI using the (sid, tid, rid) key the
        # router expects. Without this, the accept endpoint returns 404.
        for m in review_mappings or []:
            amid = f"am_{m.task_id}_{m.rule_id}"
            s.run(
                f"MERGE (am:{L_ACTIVITY_MAPPING} {{id: $id, session_id: $sid}}) "
                "SET am.task_id = $tid, am.rule_id = $rid, am.score = $score, "
                "    am.method = $method, am.reviewed = false",
                id=amid, sid=session_id, tid=m.task_id, rid=m.rule_id,
                score=m.score, method=m.method,
            )
        for rule_id, table_name, direction in (table_edges or []):
            s.run(
                f"MERGE (tbl:{L_EXTERNAL_TABLE} {{name: $name, session_id: $sid}}) "
                f"WITH tbl MATCH (r:{L_RULE} {{id: $rid, session_id: $sid}}) "
                f"MERGE (r)-[rel:{R_EVALUATES}]->(tbl) "
                "SET rel.direction = $direction",
                name=table_name, sid=session_id, rid=rule_id, direction=direction,
            )


def delete_task_rule_mapping(session_id: str, task_id: str, rule_id: str) -> None:
    """Remove a single (Task, Rule) mapping — REALIZED_BY edge + ActivityMapping
    node. Used by the arbitration loop to undo losing claims that were saved
    optimistically during per-process partial persist (§8.7 UX).
    """
    if not (session_id and task_id and rule_id):
        return
    with get_session() as s:
        s.run(
            f"MATCH (t:{L_BPM_TASK} {{id: $tid, session_id: $sid}})"
            f"-[rel:{R_REALIZED_BY}]->(r:{L_RULE} {{id: $rid, session_id: $sid}}) "
            "DELETE rel",
            tid=task_id, rid=rule_id, sid=session_id,
        )
        s.run(
            f"MATCH (am:{L_ACTIVITY_MAPPING} "
            "{session_id: $sid, task_id: $tid, rule_id: $rid}) "
            "DETACH DELETE am",
            sid=session_id, tid=task_id, rid=rule_id,
        )


def save_passages(session_id: str, passages: list[DocumentPassage]) -> None:
    if not passages:
        return
    with get_session() as s:
        for p in passages:
            s.run(
                f"MERGE (d:{L_DOCUMENT_PASSAGE} {{id: $id, session_id: $sid}}) "
                "SET d.heading = $heading, d.text = $text, d.page = $page, "
                "    d.char_start = $cs, d.char_end = $ce, d.chunk_method = $method",
                id=p.id, sid=session_id, heading=p.heading, text=p.text,
                page=p.page, cs=p.char_start, ce=p.char_end, method=p.chunk_method,
            )


def save_task_passage_links(session_id: str, links: list[TaskPassageLink]) -> None:
    if not links:
        return
    with get_session() as s:
        for link in links:
            s.run(
                f"MATCH (t:{L_BPM_TASK} {{id: $tid, session_id: $sid}}), "
                f"(d:{L_DOCUMENT_PASSAGE} {{id: $pid, session_id: $sid}}) "
                f"MERGE (t)-[rel:{R_SOURCED_FROM}]->(d) "
                "SET rel.score = $score, rel.rank = $rank, rel.low_confidence = $lowc",
                tid=link.task_id, pid=link.passage_id, sid=session_id,
                score=link.score, rank=link.rank, lowc=link.low_confidence,
            )


def accept_review_mapping(session_id: str, task_id: str, rule_id: str) -> dict:
    """Promote a review-queue ActivityMapping into a REALIZED_BY edge."""
    with get_session() as s:
        rec = s.run(
            f"MATCH (am:{L_ACTIVITY_MAPPING} {{session_id: $sid, task_id: $tid, rule_id: $rid}}) "
            "SET am.reviewed = true RETURN am.score AS score, am.method AS method",
            sid=session_id, tid=task_id, rid=rule_id,
        ).single()
        if not rec:
            return {"ok": False, "error": "ActivityMapping not found"}
        score = rec["score"]
        method = rec["method"]
        s.run(
            f"MATCH (t:{L_BPM_TASK} {{id: $tid, session_id: $sid}}), "
            f"(r:{L_RULE} {{id: $rid, session_id: $sid}}) "
            f"MERGE (t)-[rel:{R_REALIZED_BY}]->(r) "
            "SET rel.confidence = $score, rel.method = $method, rel.reviewed = true",
            tid=task_id, rid=rule_id, sid=session_id, score=score, method=method,
        )
    return {"ok": True, "score": score, "method": method}


def reject_review_mapping(session_id: str, task_id: str, rule_id: str) -> dict:
    """Remove a review-queue ActivityMapping so it won't be offered again."""
    with get_session() as s:
        before = s.run(
            f"MATCH (am:{L_ACTIVITY_MAPPING} {{session_id: $sid, task_id: $tid, rule_id: $rid}}) "
            "RETURN count(am) AS c",
            sid=session_id, tid=task_id, rid=rule_id,
        ).single()
        s.run(
            f"MATCH (am:{L_ACTIVITY_MAPPING} {{session_id: $sid, task_id: $tid, rule_id: $rid}}) "
            "DETACH DELETE am",
            sid=session_id, tid=task_id, rid=rule_id,
        )
    return {"ok": True, "deleted": int(before["c"]) if before else 0}


# -----------------------------------------------------------------------------
# BL (Rule) manual control — §8.2.4 operations for user-driven reassignment.
# All three operations are idempotent (MERGE on write, optional DELETE on remove).
# -----------------------------------------------------------------------------

def unassign_rule_from_task(session_id: str, rule_id: str, task_id: str) -> dict:
    """Detach a Rule from a Task. Removes both the REALIZED_BY edge and the
    ActivityMapping audit node so the rule no longer shows up under the task
    and isn't kept in the review queue either.
    """
    with get_session() as s:
        before = s.run(
            f"MATCH (t:{L_BPM_TASK} {{id: $tid, session_id: $sid}})"
            f"-[rel:{R_REALIZED_BY}]->(r:{L_RULE} {{id: $rid, session_id: $sid}}) "
            "RETURN count(rel) AS c",
            sid=session_id, tid=task_id, rid=rule_id,
        ).single()
        s.run(
            f"MATCH (t:{L_BPM_TASK} {{id: $tid, session_id: $sid}})"
            f"-[rel:{R_REALIZED_BY}]->(r:{L_RULE} {{id: $rid, session_id: $sid}}) "
            "DELETE rel",
            sid=session_id, tid=task_id, rid=rule_id,
        )
        s.run(
            f"MATCH (am:{L_ACTIVITY_MAPPING} {{session_id: $sid, task_id: $tid, rule_id: $rid}}) "
            "DETACH DELETE am",
            sid=session_id, tid=task_id, rid=rule_id,
        )
    return {"ok": True, "edges_removed": int(before["c"]) if before else 0}


def assign_rule_to_task(
    session_id: str, rule_id: str, task_id: str, confidence: float = 1.0,
) -> dict:
    """Manually attach a Rule to a Task. method='manual', reviewed=true, confidence=1.0
    by default (user-confirmed). No-ops if both nodes don't exist."""
    with get_session() as s:
        # Validate both sides exist to give a clean error rather than silently MERGEing.
        ok = s.run(
            f"MATCH (t:{L_BPM_TASK} {{id: $tid, session_id: $sid}}), "
            f"(r:{L_RULE} {{id: $rid, session_id: $sid}}) RETURN count(t) AS tc, count(r) AS rc",
            sid=session_id, tid=task_id, rid=rule_id,
        ).single()
        if not ok or ok["tc"] == 0 or ok["rc"] == 0:
            return {"ok": False, "error": "Task or Rule not found in this session"}
        s.run(
            f"MATCH (t:{L_BPM_TASK} {{id: $tid, session_id: $sid}}), "
            f"(r:{L_RULE} {{id: $rid, session_id: $sid}}) "
            f"MERGE (t)-[rel:{R_REALIZED_BY}]->(r) "
            "SET rel.confidence = $conf, rel.method = 'manual', rel.reviewed = true",
            sid=session_id, tid=task_id, rid=rule_id, conf=float(confidence),
        )
        amid = f"am_{task_id}_{rule_id}"
        s.run(
            f"MERGE (am:{L_ACTIVITY_MAPPING} {{id: $id, session_id: $sid}}) "
            "SET am.task_id = $tid, am.rule_id = $rid, am.score = $conf, "
            "    am.method = 'manual', am.reviewed = true",
            id=amid, sid=session_id, tid=task_id, rid=rule_id, conf=float(confidence),
        )
    return {"ok": True, "method": "manual", "confidence": float(confidence)}


def move_rule_between_tasks(
    session_id: str, rule_id: str, from_task_id: str, to_task_id: str,
) -> dict:
    """Atomically move a Rule from one Task to another (unassign + assign)."""
    if from_task_id == to_task_id:
        return {"ok": False, "error": "from_task_id and to_task_id are the same"}
    off = unassign_rule_from_task(session_id, rule_id, from_task_id)
    on = assign_rule_to_task(session_id, rule_id, to_task_id)
    if not on.get("ok"):
        return {"ok": False, "error": on.get("error", "assign failed"), "rolled_back_from": off}
    return {"ok": True, "from_task": from_task_id, "to_task": to_task_id, "edges_removed": off.get("edges_removed", 0)}


# Roles collapsed from 6 → 5 on 2026-04-20 (invariant + decision merged into
# `aggregate`). Legacy values are tolerated on read but rewritten to `aggregate`
# when encountered during normal mutation paths (best-effort migration).
_VALID_ES_ROLES = {"aggregate", "validation", "policy", "query", "external"}
_LEGACY_ROLE_MAP = {"invariant": "aggregate", "decision": "aggregate"}


def update_rule_es_role_manual(session_id: str, rule_id: str, es_role: str) -> dict:
    """User-driven es_role override. Bumps confidence to 1.0 to signal manual.
    Returns 400-style error if the role isn't one of the supported 5 (legacy
    values invariant/decision are accepted and silently mapped to aggregate)."""
    role = (es_role or "").strip().lower()
    role = _LEGACY_ROLE_MAP.get(role, role)
    if role not in _VALID_ES_ROLES:
        return {"ok": False, "error": f"invalid es_role '{es_role}'; must be one of {sorted(_VALID_ES_ROLES)}"}
    with get_session() as s:
        rec = s.run(
            f"MATCH (r:{L_RULE} {{id: $rid, session_id: $sid}}) "
            "SET r.es_role = $role, r.es_role_confidence = 1.0 "
            "RETURN r.id AS id",
            sid=session_id, rid=rule_id, role=role,
        ).single()
        if not rec:
            return {"ok": False, "error": "Rule not found in this session"}
    return {"ok": True, "rule_id": rule_id, "es_role": role, "es_role_confidence": 1.0}


def save_task_conditions(session_id: str, conditions_by_task: dict[str, list[str]]) -> None:
    if not conditions_by_task:
        return
    with get_session() as s:
        for task_id, conds in conditions_by_task.items():
            if not conds:
                continue
            s.run(
                f"MATCH (t:{L_BPM_TASK} {{id: $tid, session_id: $sid}}) SET t.conditions = $conds",
                tid=task_id, sid=session_id, conds=conds,
            )


def _to_jsonable(v):
    """Coerce values returned by the Neo4j driver into JSON-serialisable forms.

    Neo4j ships its own temporal types (`neo4j.time.DateTime`, `Date`, `Time`,
    `Duration`) which Pydantic can't serialize by default. We stringify them via
    their `iso_format()` method; everything else passes through unchanged.
    Containers (list/tuple/dict) are walked recursively.
    """
    try:
        from neo4j.time import Date, DateTime, Duration, Time
    except Exception:  # pragma: no cover — driver always available in practice
        Date = DateTime = Duration = Time = ()  # type: ignore
    if isinstance(v, (Date, DateTime, Time)):
        return v.iso_format()
    if isinstance(v, Duration):
        return str(v)
    if isinstance(v, dict):
        return {k: _to_jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_to_jsonable(x) for x in v]
    return v


def fetch_session_snapshot(session_id: str) -> dict:
    """Return everything a cold-loading frontend needs to rehydrate hybrid state.

    Shape mirrors the SSE payload contract: Task objects already include
    `rules[]`, `functions[]`, `document_passages[]`, `conditions[]` populated.
    """
    def _strip(n: dict, drop=("session_id",)) -> dict:
        out = {}
        for k, v in dict(n).items():
            if k in drop:
                continue
            out[k] = _to_jsonable(v)
        return out

    with get_session() as s:
        # Session marker (bpmn_xml)
        session_rec = s.run(
            f"MATCH (h:{L_HYBRID_SESSION} {{session_id: $sid}}) RETURN h",
            sid=session_id,
        ).single()
        bpmn_xml = dict(session_rec["h"]).get("bpmn_xml") if session_rec else None

        # Actors
        actors = [_strip(r["a"]) for r in s.run(
            f"MATCH (a:{L_BPM_ACTOR} {{session_id: $sid}}) RETURN a ORDER BY a.name",
            sid=session_id,
        )]

        # Tasks with enriched sub-collections
        task_rows = list(s.run(
            f"""
            MATCH (t:{L_BPM_TASK} {{session_id: $sid}})
            OPTIONAL MATCH (a:{L_BPM_ACTOR} {{session_id: $sid}})-[:{R_PERFORMS}]->(t)
            WITH t, collect(DISTINCT a.id) AS actor_ids
            RETURN t, actor_ids
            ORDER BY t.sequence_index
            """,
            sid=session_id,
        ))

        # Rules flat list (for lookup + front display)
        rule_rows = list(s.run(
            f"MATCH (r:{L_RULE} {{session_id: $sid}}) RETURN r ORDER BY r.source_function, r.id",
            sid=session_id,
        ))
        rules_by_id: dict[str, dict] = {}
        rules_list: list[dict] = []
        for rr in rule_rows:
            rd = _strip(rr["r"])
            rules_by_id[rd["id"]] = rd
            rules_list.append(rd)

        # Task → Rule mappings (auto-accepted only — REALIZED_BY edges)
        task_rule_rows = list(s.run(
            f"""
            MATCH (t:{L_BPM_TASK} {{session_id: $sid}})-[link:{R_REALIZED_BY}]->(r:{L_RULE} {{session_id: $sid}})
            RETURN t.id AS task_id, r.id AS rule_id,
                   link.confidence AS confidence, link.method AS method, link.reviewed AS reviewed,
                   link.rationale AS rationale, link.evidence_refs AS evidence_refs,
                   link.evidence_path AS evidence_path, link.agent_verdict AS agent_verdict
            """,
            sid=session_id,
        ))
        rules_by_task: dict[str, list[dict]] = {}
        functions_by_task: dict[str, dict[str, dict]] = {}
        referenced_fn_names: set[str] = set()
        for row in task_rule_rows:
            rdto = rules_by_id.get(row["rule_id"])
            if not rdto:
                continue
            entry = {
                **rdto,
                "confidence": row["confidence"],
                "match_method": row["method"],
                "rationale": row.get("rationale"),
                "evidence_refs": row.get("evidence_refs") or [],
                "evidence_path": row.get("evidence_path") or [],
                "agent_verdict": row.get("agent_verdict"),
            }
            rules_by_task.setdefault(row["task_id"], []).append(entry)
            if rdto.get("source_function"):
                key = f"{rdto.get('source_module') or ''}.{rdto['source_function']}"
                fns = functions_by_task.setdefault(row["task_id"], {})
                fns.setdefault(key, {
                    "id": key,
                    "name": rdto["source_function"],
                    "module": rdto.get("source_module"),
                    "confidence": row["confidence"],
                })
                referenced_fn_names.add(rdto["source_function"])

        # Cross-DB: pull FUNCTION.summary from the analyzer DB so the Inspector's
        # "Mapped Functions" section shows the same summary that was available
        # at ingestion time. Without this, refresh hydration drops summary and
        # functions render as name-only.
        summary_by_fn: dict[str, str | None] = {}
        if referenced_fn_names:
            try:
                with get_session(database=ANALYZER_NEO4J_DATABASE) as asess:
                    for arec in asess.run(
                        # De-dup per fn name at the Cypher level — a fn may have
                        # multiple matching nodes (e.g. also labelled :Query).
                        # Take the first non-null summary per name.
                        """
                        UNWIND $fn_names AS fn
                        OPTIONAL MATCH (f) WHERE coalesce(f.procedure_name, f.name) = fn
                        WITH fn, collect(f.summary) AS summaries
                        RETURN fn,
                               head([s IN summaries WHERE s IS NOT NULL AND s <> '']) AS summary
                        """,
                        fn_names=sorted(referenced_fn_names),
                    ):
                        summary_by_fn[arec["fn"]] = arec.get("summary")
            except Exception:
                # Best-effort — analyzer DB may be unreachable. UI still renders
                # without summary in that case, matching prior behavior.
                summary_by_fn = {}
        if summary_by_fn:
            for fns in functions_by_task.values():
                for fn_entry in fns.values():
                    if fn_entry.get("name") in summary_by_fn:
                        fn_entry["summary"] = summary_by_fn[fn_entry["name"]]

        # Task → DocumentPassage links
        passage_rows = list(s.run(
            f"""
            MATCH (t:{L_BPM_TASK} {{session_id: $sid}})-[link:{R_SOURCED_FROM}]->(p:{L_DOCUMENT_PASSAGE} {{session_id: $sid}})
            RETURN t.id AS task_id, p, link.score AS score, link.rank AS rank, link.low_confidence AS low_confidence
            ORDER BY t.id, link.rank
            """,
            sid=session_id,
        ))
        passages_by_task: dict[str, list[dict]] = {}
        for row in passage_rows:
            p = _strip(row["p"])
            p["score"] = row["score"]
            p["rank"] = row["rank"]
            p["low_confidence"] = row["low_confidence"]
            passages_by_task.setdefault(row["task_id"], []).append(p)

        # Compose tasks
        tasks: list[dict] = []
        for rr in task_rows:
            td = _strip(rr["t"])
            td["actor_ids"] = [aid for aid in (rr["actor_ids"] or []) if aid]
            td["rules"] = rules_by_task.get(td["id"], [])
            td["functions"] = list(functions_by_task.get(td["id"], {}).values())
            td["document_passages"] = passages_by_task.get(td["id"], [])
            td["conditions"] = td.get("conditions") or []
            tasks.append(td)

        # Sequences
        sequences = []
        for sr in s.run(
            f"""
            MATCH (q:{L_BPM_SEQUENCE} {{session_id: $sid}})
            OPTIONAL MATCH (q)-[:{R_CONTAINS}]->(t:{L_BPM_TASK})
            WITH q, collect(t.id) AS task_ids
            RETURN q, task_ids
            """,
            sid=session_id,
        ):
            seq = _strip(sr["q"])
            seq["task_ids"] = [tid for tid in (sr["task_ids"] or []) if tid]
            sequences.append(seq)

        # Processes (§2.A) — top-level BpmProcess with its HAS_TASK/HAS_ACTOR children.
        # Loaded via the same session so snapshot + cold-reload frontend see processes.
        process_rows = list(s.run(
            f"""
            MATCH (p:{L_BPM_PROCESS} {{session_id: $sid}})
            OPTIONAL MATCH (p)-[:{R_HAS_TASK}]->(t:{L_BPM_TASK} {{session_id: $sid}})
            WITH p, collect(DISTINCT t.id) AS task_ids
            OPTIONAL MATCH (p)-[:{R_HAS_ACTOR}]->(a:{L_BPM_ACTOR} {{session_id: $sid}})
            RETURN p, task_ids, collect(DISTINCT a.id) AS actor_ids
            ORDER BY p.name
            """,
            sid=session_id,
        ))
        processes = []
        for row in process_rows:
            pd = _strip(row["p"])
            pd["task_ids"] = [x for x in (row["task_ids"] or []) if x]
            pd["actor_ids"] = [x for x in (row["actor_ids"] or []) if x]
            # bpmn_xml is already included by _strip since we set it as a node prop.
            processes.append(pd)

        # Lazy backfill: older sessions saved per-process data but no
        # `bpmn_xml` property on BpmProcess. Rebuild on demand from the
        # actors/tasks/sequences already in the graph so the frontend's
        # double-click/drag can render the process without a re-ingestion.
        from api.features.ingestion.hybrid.contracts import (
            BpmActor as _Actor,
            BpmSequenceDTO as _Seq,
            BpmSkeleton as _Skel,
            BpmTaskDTO as _Task,
        )
        from api.features.ingestion.hybrid.document_to_bpm.bpmn_builder import (
            build_bpmn_xml as _build_bpmn_xml,
        )
        # We'll need actors/tasks lookup maps — but they're built below.
        # Defer actual regeneration until after the task/actor lists are composed
        # (see end of the `with` block below).
        _processes_needing_xml = [
            p for p in processes if not p.get("bpmn_xml")
        ]

        # Glossary
        glossary = [_strip(r["g"]) for r in s.run(
            f"MATCH (g:{L_GLOSSARY_TERM} {{session_id: $sid}}) RETURN g ORDER BY g.term",
            sid=session_id,
        )]

        # Review queue — ActivityMappings without a corresponding REALIZED_BY edge.
        # These are θ_review-band matches: the pipeline saw a plausible Task↔Rule
        # link but lacked confidence to auto-commit, so it parked the suggestion
        # here for the user to accept/reject.
        review_queue = []
        for row in s.run(
            f"""
            MATCH (am:{L_ACTIVITY_MAPPING} {{session_id: $sid}})
            OPTIONAL MATCH (t:{L_BPM_TASK} {{id: am.task_id, session_id: $sid}})-[r:{R_REALIZED_BY}]->(:{L_RULE} {{id: am.rule_id, session_id: $sid}})
            WITH am WHERE r IS NULL
            RETURN am
            """,
            sid=session_id,
        ):
            amd = _strip(row["am"])
            review_queue.append({
                "task_id": amd.get("task_id"),
                "rule_id": amd.get("rule_id"),
                "score": amd.get("score"),
                "method": amd.get("method"),
                "reviewed": amd.get("reviewed", False),
            })

        # Unassigned rules — Rules with no REALIZED_BY edge on ANY task in this
        # session. Distinct from review queue: review items carry a suggested
        # task_id (the pipeline thought about it), while unassigned rules have
        # no suggestion at all. Both are surfaced together in the Inspector's
        # unified "Unassigned / Review" pool so the user has a single place
        # to see every rule not yet committed to a Task.
        rules_with_edges = set()
        for row in s.run(
            f"""
            MATCH (:{L_BPM_TASK} {{session_id: $sid}})-[:{R_REALIZED_BY}]->(r:{L_RULE} {{session_id: $sid}})
            RETURN DISTINCT r.id AS rid
            """,
            sid=session_id,
        ):
            rules_with_edges.add(row["rid"])
        unassigned_rule_ids = [rid for rid in rules_by_id if rid not in rules_with_edges]

    # If HybridSession didn't store bpmn_xml (old session or A2A-empty case),
    # reconstruct from the actor/task/sequence graph so the frontend canvas
    # can still render on cold load.
    if not bpmn_xml and actors and tasks:
        try:
            from api.features.ingestion.hybrid.document_to_bpm.bpmn_builder import build_bpmn_xml
            skeleton = BpmSkeleton(
                actors=[BpmActor(**{k: a.get(k) for k in ("id", "name", "description") if k in a}) for a in actors],
                tasks=[BpmTaskDTO(
                    id=t["id"], name=t.get("name", ""),
                    description=t.get("description"),
                    sequence_index=t.get("sequence_index", 0),
                    actor_ids=t.get("actor_ids") or [],
                    source_page=t.get("source_page"),
                    source_section=t.get("source_section"),
                ) for t in tasks],
                sequences=[BpmSequenceDTO(
                    id=s.get("id", "seq_tmp"),
                    name=s.get("name", "Main"),
                    task_ids=s.get("task_ids") or [],
                ) for s in sequences],
            )
            bpmn_xml = build_bpmn_xml(skeleton)
            # Persist the rebuilt XML so future fetches hit it directly
            save_session_bpmn_xml(session_id, bpmn_xml)
        except Exception:
            pass  # best-effort

    promoted = _fetch_promotion_summary(session_id)

    # Lazy backfill: if we have tasks but no processes (older session, or
    # native extractor with no process identity), synthesize one default
    # process so the frontend always has a Process root for the tree.
    if tasks and not processes:
        default_pid = f"proc_legacy_{session_id[:8]}"
        processes = [{
            "id": default_pid,
            "name": session_id[:8],
            "domain_keywords": [],
            "source_pdf_name": None,
            "task_ids": [t["id"] for t in tasks],
            "actor_ids": [a["id"] for a in actors],
        }]

    # Per-process bpmn_xml lazy regeneration — for processes whose XML was
    # never persisted (pre-feature-flag ingestion), reconstruct from the
    # actors/tasks/sequences we already fetched. Persist back so subsequent
    # fetches are cheap.
    if _processes_needing_xml:
        actors_by_id = {a["id"]: a for a in actors}
        tasks_by_id = {t["id"]: t for t in tasks}
        sequences_by_pid: dict[str, list] = {}
        for seq in sequences:
            sequences_by_pid.setdefault(seq.get("process_id") or "", []).append(seq)

        for p in _processes_needing_xml:
            pid = p["id"]
            p_actors = [actors_by_id[aid] for aid in (p.get("actor_ids") or []) if aid in actors_by_id]
            p_tasks = [tasks_by_id[tid] for tid in (p.get("task_ids") or []) if tid in tasks_by_id]
            if not p_tasks:
                continue
            p_seqs = sequences_by_pid.get(pid) or []
            try:
                skel = _Skel(
                    actors=[_Actor(id=a["id"], name=a.get("name", ""),
                                   description=a.get("description"))
                            for a in p_actors],
                    tasks=[_Task(
                        id=t["id"], name=t.get("name", ""),
                        description=t.get("description"),
                        sequence_index=t.get("sequence_index", 0),
                        actor_ids=t.get("actor_ids") or [],
                        source_page=t.get("source_page"),
                        source_section=t.get("source_section"),
                    ) for t in p_tasks],
                    sequences=[_Seq(
                        id=s.get("id", f"seq_{pid}"),
                        name=s.get("name", "Main"),
                        task_ids=s.get("task_ids") or [],
                    ) for s in p_seqs] or [_Seq(
                        id=f"seq_{pid}", name="Main",
                        task_ids=[t["id"] for t in p_tasks],
                    )],
                )
                xml = _build_bpmn_xml(skel)
                p["bpmn_xml"] = xml
                # Persist so next call is cheap.
                with get_session() as s2:
                    s2.run(
                        f"MATCH (p:{L_BPM_PROCESS} {{id: $id, session_id: $sid}}) "
                        "SET p.bpmn_xml = $xml",
                        id=pid, sid=session_id, xml=xml,
                    )
            except Exception:
                pass  # best-effort — leave bpmn_xml empty for this process

    return {
        "session_id": session_id,
        "bpmn_xml": bpmn_xml,
        "processes": processes,
        "actors": actors,
        "tasks": tasks,
        "sequences": sequences,
        "rules": rules_list,
        "glossary": glossary,
        "review_queue": review_queue,
        "unassigned_rule_ids": unassigned_rule_ids,
        "promoted": promoted,
    }


def _fetch_promotion_summary(session_id: str) -> dict:
    """Counts of Phase 5 nodes for this session. Zero-counts dict if not promoted."""
    summary = {
        "user_stories": 0, "events": 0, "bounded_contexts": 0,
        "aggregates": 0, "commands": 0, "readmodels": 0, "policies": 0,
        "policies_cross_bc": 0,
    }
    label_to_key = {
        "UserStory": "user_stories",
        "Event": "events",
        "BoundedContext": "bounded_contexts",
        "Aggregate": "aggregates",
        "Command": "commands",
        "ReadModel": "readmodels",
        "Policy": "policies",
    }
    with get_session() as s:
        for label, key in label_to_key.items():
            r = s.run(
                f"MATCH (n:{label} {{session_id: $sid}}) RETURN count(n) AS c",
                sid=session_id,
            ).single()
            if r:
                summary[key] = int(r["c"])
        r = s.run(
            "MATCH (p:Policy {session_id: $sid}) WHERE p.kind = 'cross_bc' "
            "RETURN count(p) AS c",
            sid=session_id,
        ).single()
        if r:
            summary["policies_cross_bc"] = int(r["c"])
    return summary


def debug_session_snapshot(session_id: str) -> dict:
    """Return counts + small samples of each hybrid label for a session (diagnostic)."""
    snapshot: dict = {"session_id": session_id, "counts": {}, "samples": {}}
    labels = [
        L_BPM_PROCESS, L_BPM_ACTOR, L_BPM_TASK, L_BPM_SEQUENCE, L_RULE,
        L_GLOSSARY_TERM, L_DOCUMENT_PASSAGE, L_ACTIVITY_MAPPING, L_EXTERNAL_TABLE,
    ]
    with get_session() as s:
        for label in labels:
            rec = s.run(
                f"MATCH (n:{label} {{session_id: $sid}}) RETURN count(n) AS c",
                sid=session_id,
            ).single()
            snapshot["counts"][label] = int(rec["c"]) if rec else 0
        for label in labels:
            rows = s.run(
                f"MATCH (n:{label} {{session_id: $sid}}) RETURN n LIMIT 3",
                sid=session_id,
            )
            snapshot["samples"][label] = [dict(r["n"]) for r in rows]
        # Relationship counts for the key edges
        rel_counts: dict[str, int] = {}
        for rel in (R_PERFORMS, R_NEXT, R_CONTAINS, R_REALIZED_BY, R_EVALUATES, R_SOURCED_FROM, R_HAS_TASK, R_HAS_ACTOR):
            rec = s.run(
                f"MATCH (a {{session_id: $sid}})-[r:{rel}]->(b {{session_id: $sid}}) RETURN count(r) AS c",
                sid=session_id,
            ).single()
            rel_counts[rel] = int(rec["c"]) if rec else 0
        snapshot["relationships"] = rel_counts
    return snapshot


def fetch_bpm_skeleton_cytoscape(session_id: str) -> dict:
    """Read BpmTask graph for rendering (cytoscape-compatible element list)."""
    nodes: list[dict] = []
    edges: list[dict] = []
    with get_session() as s:
        for rec in s.run(
            f"MATCH (n) WHERE n.session_id = $sid AND "
            f"(n:{L_BPM_TASK} OR n:{L_BPM_ACTOR} OR n:{L_BPM_SEQUENCE}) "
            "RETURN n, labels(n) AS labels",
            sid=session_id,
        ):
            n = rec["n"]
            nodes.append({
                "data": {
                    "id": n["id"],
                    "label": n.get("name", ""),
                    "type": rec["labels"][0],
                    "description": n.get("description"),
                    "sequence_index": n.get("sequence_index"),
                }
            })
        for rec in s.run(
            "MATCH (a)-[r]->(b) WHERE a.session_id = $sid AND b.session_id = $sid "
            "RETURN a.id AS src, b.id AS dst, type(r) AS rel",
            sid=session_id,
        ):
            edges.append({
                "data": {
                    "id": f"{rec['src']}->{rec['dst']}:{rec['rel']}",
                    "source": rec["src"],
                    "target": rec["dst"],
                    "label": rec["rel"],
                }
            })
    return {"nodes": nodes, "edges": edges}
