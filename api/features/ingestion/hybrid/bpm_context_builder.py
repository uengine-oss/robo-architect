"""Hybrid BPM → grouped LLM contexts.

Same shape as `analyzer_graph.graph_context_builder.build_grouped_unit_contexts()`:
returns `[(group_name, [unit_id, ...], context_text), ...]` so the existing
ingestion `user_stories` phase can consume it via the same code path.

Grouping strategy: **one BpmTask = one group**. Within each Task we cluster
the realized Rules by `source_function`, then apply the dedup rules:
  1. DF cutoff — drop functions mapped to >50% of all tasks (entry/main noise)
  2. Top-1 attribution — for surviving fns, keep only the Task with the highest
     sum of REALIZED_BY confidences

This way each LLM call is scoped to a single business activity (Task), and the
LLM is guided to produce one UserStory per fn cluster within that Task.
"""

from __future__ import annotations

import os
from collections import defaultdict

from api.platform.neo4j import get_session


_FN_DF_THRESHOLD = float(os.getenv("HYBRID_ES_FN_DF_THRESHOLD", "0.5"))


def _fetch_bpm_data(session_id: str) -> dict:
    """Read tasks, actors, rules, REALIZED_BY links and ExternalTable edges in one go."""
    with get_session() as s:
        tasks = []
        for r in s.run(
            "MATCH (t:BpmTask {session_id: $sid}) "
            "OPTIONAL MATCH (a:BpmActor {session_id: $sid})-[:PERFORMS]->(t) "
            "RETURN t, collect(DISTINCT a.name) AS actor_names "
            "ORDER BY t.sequence_index",
            sid=session_id,
        ):
            t = dict(r["t"])
            t["actor_names"] = [n for n in (r["actor_names"] or []) if n]
            tasks.append(t)

        rules = {}
        for r in s.run(
            "MATCH (rule:Rule {session_id: $sid}) RETURN rule",
            sid=session_id,
        ):
            rd = dict(r["rule"])
            rules[rd["id"]] = rd

        # (task_id, rule_id, confidence)
        links = []
        for r in s.run(
            "MATCH (t:BpmTask {session_id: $sid})-[link:REALIZED_BY]->"
            "(rule:Rule {session_id: $sid}) "
            "RETURN t.id AS tid, rule.id AS rid, link.confidence AS conf",
            sid=session_id,
        ):
            links.append((r["tid"], r["rid"], float(r["conf"] or 0.0)))

        # rule_id → READS / WRITES tables
        reads = defaultdict(list)
        writes = defaultdict(list)
        for r in s.run(
            "MATCH (rule:Rule {session_id: $sid})-[rel:EVALUATES]->"
            "(tbl:ExternalTable {session_id: $sid}) "
            "RETURN rule.id AS rid, tbl.name AS tname, rel.direction AS dir",
            sid=session_id,
        ):
            (writes if r["dir"] == "WRITES" else reads)[r["rid"]].append(r["tname"])

    return {
        "tasks": tasks, "rules": rules, "links": links,
        "reads": dict(reads), "writes": dict(writes),
    }


def _dedup_task_fn_mapping(
    total_tasks: int,
    rules: dict[str, dict],
    links: list[tuple[str, str, float]],
) -> tuple[dict[str, dict[str, list[str]]], set[str]]:
    """Apply DF cutoff + Top-1 attribution. Returns (pruned, dropped_fns).
    pruned = {task_id: {fn: [rule_id, ...]}}.
    """
    raw: dict[str, dict[str, list[tuple[str, float]]]] = defaultdict(lambda: defaultdict(list))
    fn_tasks: dict[str, set[str]] = defaultdict(set)
    for tid, rid, conf in links:
        rule = rules.get(rid)
        if not rule or not rule.get("source_function"):
            continue
        fn = rule["source_function"]
        raw[tid][fn].append((rid, conf))
        fn_tasks[fn].add(tid)

    dropped = {fn for fn, ts in fn_tasks.items() if len(ts) / max(1, total_tasks) > _FN_DF_THRESHOLD}

    fn_score_by_task: dict[str, dict[str, float]] = defaultdict(dict)
    for tid, fns in raw.items():
        for fn, items in fns.items():
            if fn in dropped:
                continue
            fn_score_by_task[fn][tid] = sum(c for _, c in items)
    fn_winner = {
        fn: max(scores.items(), key=lambda kv: (kv[1], kv[0]))[0]
        for fn, scores in fn_score_by_task.items() if scores
    }

    pruned: dict[str, dict[str, list[str]]] = defaultdict(dict)
    for tid, fns in raw.items():
        for fn, items in fns.items():
            if fn in dropped or fn_winner.get(fn) != tid:
                continue
            pruned[tid][fn] = [rid for rid, _ in items]
    return pruned, dropped


def _format_task_context(
    task: dict,
    fn_to_rules: dict[str, list[str]],
    rules_by_id: dict[str, dict],
    reads_by_rule: dict[str, list[str]],
    writes_by_rule: dict[str, list[str]],
) -> str:
    """Build the per-Task LLM context — Task header + per-fn BL groups + guidelines."""
    lines: list[str] = [
        f"# Task: {task['name']} (sequence_index={task.get('sequence_index') or 0})",
    ]
    if task.get("description"):
        lines.append(f"Description: {task['description']}")
    if task.get("actor_names"):
        lines.append(f"Actor: {', '.join(task['actor_names'])}")
    if task.get("source_section") or task.get("source_page"):
        src_bits = []
        if task.get("source_section"):
            src_bits.append(task["source_section"])
        if task.get("source_page"):
            src_bits.append(f"p.{task['source_page']}")
        lines.append(f"Source: {' / '.join(src_bits)}")
    if task.get("conditions"):
        lines.append("Conditions (문서+코드 결합):")
        for c in (task["conditions"] or [])[:6]:
            lines.append(f"  - {c}")
    lines.append("")

    if not fn_to_rules:
        lines.append("(매핑된 코드 Rule 없음 — 문서 description 만으로 1개 US 도출)")
    else:
        # Render each fn cluster as a BL block (analogous to analyzer_graph format).
        bl_seq = 0
        for fn in sorted(fn_to_rules.keys()):
            rids = fn_to_rules[fn]
            tables_seen: set[str] = set()
            for rid in rids:
                tables_seen.update(writes_by_rule.get(rid, []))
            tables_str = f" (WRITES {', '.join(sorted(tables_seen))})" if tables_seen else ""
            lines.append(f"## fn: {fn} ({len(rids)} BLs){tables_str}")
            for rid in rids:
                bl_seq += 1
                rule = rules_by_id.get(rid, {})
                title = (rule.get("when") or rule.get("then") or "")[:80]
                lines.append(f"  - BL[{bl_seq}]: {title}")
                if rule.get("given"):
                    lines.append(f"    Given: {rule['given']}")
                if rule.get("when"):
                    lines.append(f"    When : {rule['when']}")
                if rule.get("then"):
                    lines.append(f"    Then : {rule['then']}")
            lines.append("")

    lines.extend([
        "### GUIDELINES (hybrid mode):",
        "- 위 Task 안의 각 fn 묶음 마다 1개 UserStory 를 만드세요 — fn 은 코드 응집 단위입니다.",
        "- 매핑된 Rule 이 없으면 description 으로 1개만 만드세요.",
        "- role 은 위 Actor 그대로 사용 (없으면 'system').",
        "- displayName 은 한국어 (예: '입력값 검증 — 입력 파라미터 유효성').",
        "- ui_description 은 해당 기능의 최소 화면을 1문장으로 요약.",
        "- source_bl 필드는 비워두세요 (hybrid 는 후처리로 채웁니다).",
        "- 코드 식별자(camelCase)를 그대로 노출하지 말고 도메인 용어로 풀어쓰세요.",
    ])
    return "\n".join(lines)


def build_grouped_unit_contexts_from_bpm(
    session_id: str,
) -> list[tuple[str, list[str], str]]:
    """Hybrid analogue of `build_grouped_unit_contexts()`.

    Returns: [(group_name, [task_id], context_text), ...]
    Each group = one BpmTask. Tasks with zero post-dedup rules also yield a
    group (document-only US).
    """
    data = _fetch_bpm_data(session_id)
    tasks = data["tasks"]
    if not tasks:
        return []

    pruned, _dropped = _dedup_task_fn_mapping(
        total_tasks=len(tasks), rules=data["rules"], links=data["links"],
    )

    out: list[tuple[str, list[str], str]] = []
    for task in tasks:
        tid = task["id"]
        fn_to_rules = pruned.get(tid, {})
        ctx = _format_task_context(
            task=task, fn_to_rules=fn_to_rules,
            rules_by_id=data["rules"],
            reads_by_rule=data["reads"], writes_by_rule=data["writes"],
        )
        out.append((task["name"], [tid], ctx))
    return out


def fetch_task_metadata_for_bpm(session_id: str) -> dict[str, dict]:
    """Helper for downstream cross-BC policy detection: task_id → {name, next_ids, actor_names}."""
    out: dict[str, dict] = {}
    with get_session() as s:
        for r in s.run(
            "MATCH (t:BpmTask {session_id: $sid}) "
            "OPTIONAL MATCH (t)-[:NEXT]->(n:BpmTask {session_id: $sid}) "
            "OPTIONAL MATCH (a:BpmActor {session_id: $sid})-[:PERFORMS]->(t) "
            "RETURN t.id AS tid, t.name AS name, t.sequence_index AS seq, "
            "       collect(DISTINCT n.id) AS next_ids, "
            "       collect(DISTINCT a.name) AS actors",
            sid=session_id,
        ):
            out[r["tid"]] = {
                "name": r["name"], "sequence_index": r["seq"],
                "next_ids": [n for n in (r["next_ids"] or []) if n],
                "actor_names": [a for a in (r["actors"] or []) if a],
            }
    return out
