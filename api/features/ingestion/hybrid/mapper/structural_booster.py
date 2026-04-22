"""Phase 3.3: structural signal booster.

Uses analyzer-graph context that's already loaded onto RuleContext:
- Actor alias: if a Task's BpmActor name appears in the Rule's FUNCTION performer
  list, add a small bonus.
- Sequence cluster: rules whose functions are performed by the same Actor and
  that match Tasks in the same BpmSequence get a small within-cluster bonus.

Side effect: returns a list of (rule_id, table_name, direction) triples so the
caller can persist `(Rule)-[:EVALUATES]->(Table)` edges. We don't write here
to keep this module pure.
"""

from __future__ import annotations

from api.features.ingestion.hybrid.contracts import (
    ActivityRuleMapping,
    BpmSkeleton,
    RuleContext,
)

_ACTOR_BONUS = 0.05
_CLUSTER_BONUS = 0.03
_SAME_CONTEXT_BONUS = 0.08  # Phase 2.5 — Task's majority BC == Rule.context_cluster
_MAX_SCORE = 0.99  # reserve 1.0 for manual / human-confirmed matches


def _infer_task_bc(
    task_id: str,
    matches: list["ActivityRuleMapping"],
    ctx_by_rule: dict[str, "RuleContext"],
) -> str | None:
    """A Task's inferred BC = the most frequent context_cluster among rules
    currently matched to it (lexical + embedding auto-matches together).

    Returns None if no matched rule has a context_cluster set.
    """
    counts: dict[str, int] = {}
    for m in matches:
        if m.task_id != task_id:
            continue
        ctx = ctx_by_rule.get(m.rule_id)
        if ctx and ctx.context_cluster:
            counts[ctx.context_cluster] = counts.get(ctx.context_cluster, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda kv: kv[1])[0]


def _actor_names_for_task(task, skeleton: BpmSkeleton) -> set[str]:
    by_id = {a.id: a.name for a in skeleton.actors}
    return {by_id.get(aid, "").strip().lower() for aid in (task.actor_ids or []) if by_id.get(aid)}


def boost(
    matches: list[ActivityRuleMapping],
    skeleton: BpmSkeleton,
    contexts: list[RuleContext],
) -> tuple[list[ActivityRuleMapping], list[tuple[str, str, str]]]:
    if not matches:
        return matches, []

    ctx_by_rule = {c.rule_id: c for c in contexts}
    tasks_by_id = {t.id: t for t in skeleton.tasks}
    # sequence_id for each task
    seq_of_task: dict[str, str] = {}
    for seq in skeleton.sequences:
        for tid in seq.task_ids:
            seq_of_task[tid] = seq.id

    # Cluster: {sequence_id: set[rule_id]} of matches in that sequence
    cluster: dict[str, set[str]] = {}
    for m in matches:
        sid = seq_of_task.get(m.task_id)
        if sid:
            cluster.setdefault(sid, set()).add(m.rule_id)

    # Phase 2.5 — compute each task's inferred BC from the current match pool.
    task_bc: dict[str, str | None] = {}
    for task_id in {m.task_id for m in matches}:
        task_bc[task_id] = _infer_task_bc(task_id, matches, ctx_by_rule)

    boosted: list[ActivityRuleMapping] = []
    table_edges: list[tuple[str, str, str]] = []
    seen_edges: set[tuple[str, str, str]] = set()

    for m in matches:
        ctx = ctx_by_rule.get(m.rule_id)
        if not ctx:
            boosted.append(m)
            continue
        task = tasks_by_id.get(m.task_id)
        if not task:
            boosted.append(m)
            continue

        score = m.score
        # Actor alias bonus
        task_actors = _actor_names_for_task(task, skeleton)
        ctx_actors = {a.strip().lower() for a in ctx.actors if a}
        if task_actors & ctx_actors:
            score += _ACTOR_BONUS
        # Sequence cluster bonus — if at least one other rule from the same
        # sequence is already matched, that Task likely belongs with them.
        sid = seq_of_task.get(m.task_id)
        if sid and len(cluster.get(sid, set())) >= 2:
            score += _CLUSTER_BONUS
        # Same-BC bonus — rule's context_cluster aligns with Task's majority BC.
        inferred = task_bc.get(m.task_id)
        if inferred and ctx.context_cluster and inferred == ctx.context_cluster:
            score += _SAME_CONTEXT_BONUS

        boosted.append(ActivityRuleMapping(
            task_id=m.task_id,
            rule_id=m.rule_id,
            score=min(score, _MAX_SCORE),
            method=m.method,
            reviewed=m.reviewed,
        ))

        for tbl in ctx.reads_tables:
            k = (ctx.rule_id, tbl, "READS")
            if k not in seen_edges:
                seen_edges.add(k)
                table_edges.append(k)
        for tbl in ctx.writes_tables:
            k = (ctx.rule_id, tbl, "WRITES")
            if k not in seen_edges:
                seen_edges.add(k)
                table_edges.append(k)

    return boosted, table_edges
