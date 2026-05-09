"""Phase 5 §5 — persist NamedSession + SessionDecomposition into Neo4j.

Two responsibilities, kept in one module so `promote_to_es` can call a single
function to land the entire model:

  1. Node MERGE (UserStory / BoundedContext / Aggregate / Command / Event /
     Policy / ReadModel) — every node carries `session_id` + `user_edited`
     respect (manual edits are not overwritten on re-run).
  2. Traceability edges (PRD §5.1) — PROMOTED_FROM, IMPLEMENTS, SOURCED_FROM,
     DERIVED_FROM, GROUNDED_IN, PRECONDITION_BY, READS_FROM, CROSSES,
     ATTACHED_TO, RAISED_IN, HAS_USERSTORY/AGGREGATE/POLICY/READMODEL,
     HAS_COMMAND, EMITS.

We MERGE rather than CREATE so reruns are idempotent. `user_edited=true` on a
node makes the SET a no-op, preserving manual canvas edits across re-promotions.

Cross-DB note: analyzer-side nodes (`Rule` / `Example` / `Table` / `FUNCTION` /
`Question`) live in the same Neo4j DB as the hybrid session (single-database
deployment, see PRD §1 infra fact), so all traceability edges resolve in one
session — no cross-DB join needed.
"""

from __future__ import annotations

from neo4j import Session

from api.features.ingestion.hybrid.event_storming_bridge.decomposer import (
    QuestionRef,
    SessionDecomposition,
)
from api.features.ingestion.hybrid.event_storming_bridge.naming import (
    BCAssignment,
    NamedSession,
)


# =============================================================================
# Node SET / MATCH templates — the "user_edited" guard centralizes manual-edit
# preservation. ON CREATE always populates initial fields; ON MATCH only writes
# the fields the user has not manually changed.
# =============================================================================


# Single MERGE pattern that respects user_edited. We split SET clauses into
# always (key, session_id) and conditional (everything LLM/decomposer-driven).
def _merge_user_story(
    s: Session, sid: str, us, bc_key: str, source: str,
    *, action: str = "", benefit: str = "",
) -> None:
    """Persist a UserStory. action/benefit come from the LLM naming layer
    (`UserStoryShape`); when the LLM step is skipped or fails, action falls
    back to the candidate's `name_seed` and benefit stays empty."""
    final_action = (action or us.name_seed or "")[:200]
    final_benefit = (benefit or "")[:200]
    s.run(
        """
        MERGE (n:UserStory {id: $id, session_id: $sid})
          ON CREATE SET
            n.role = $role,
            n.action = $action,
            n.benefit = $benefit,
            n.sequence = $sequence,
            n.task_id = $task_id,
            n.source = $source,
            n.bc_key = $bc_key,
            n.user_edited = false
          ON MATCH SET
            n.role = CASE WHEN coalesce(n.user_edited, false) THEN n.role ELSE $role END,
            n.action = CASE WHEN coalesce(n.user_edited, false) THEN n.action ELSE $action END,
            n.benefit = CASE WHEN coalesce(n.user_edited, false) THEN n.benefit ELSE $benefit END,
            n.sequence = CASE WHEN coalesce(n.user_edited, false) THEN n.sequence ELSE $sequence END,
            n.task_id = CASE WHEN coalesce(n.user_edited, false) THEN n.task_id ELSE $task_id END,
            n.source = CASE WHEN coalesce(n.user_edited, false) THEN n.source ELSE $source END,
            n.bc_key = CASE WHEN coalesce(n.user_edited, false) THEN n.bc_key ELSE $bc_key END
        """,
        id=us.id, sid=sid, role=us.role, action=final_action, benefit=final_benefit,
        sequence=us.sequence, task_id=us.task_id, source=source, bc_key=bc_key,
    )


def _merge_bc(s: Session, sid: str, bc: BCAssignment) -> None:
    s.run(
        """
        MERGE (n:BoundedContext {key: $key, session_id: $sid})
          ON CREATE SET
            n.id = $key,
            n.name = $name, n.displayName = $display_name,
            n.description = $description, n.rationale = $rationale,
            n.domainType = $domain_type, n.user_edited = false
          ON MATCH SET
            n.name = CASE WHEN coalesce(n.user_edited, false) THEN n.name ELSE $name END,
            n.displayName = CASE WHEN coalesce(n.user_edited, false) THEN n.displayName ELSE $display_name END,
            n.description = CASE WHEN coalesce(n.user_edited, false) THEN n.description ELSE $description END,
            n.rationale = CASE WHEN coalesce(n.user_edited, false) THEN n.rationale ELSE $rationale END,
            n.domainType = CASE WHEN coalesce(n.user_edited, false) THEN n.domainType ELSE $domain_type END
        """,
        key=bc.key, sid=sid, name=bc.name, display_name=bc.display_name,
        description=bc.description, rationale=bc.rationale, domain_type=bc.domain_type,
    )


def _merge_aggregate(s: Session, sid: str, key: str, name: str, display_name: str,
                     bc_key: str, root_table: str, member_functions: list[str]) -> None:
    s.run(
        """
        MERGE (n:Aggregate {key: $key, session_id: $sid})
          ON CREATE SET
            n.id = $key,
            n.name = $name, n.displayName = $display_name,
            n.rootTable = $root_table, n.bc_key = $bc_key,
            n.memberFunctions = $member_functions, n.user_edited = false
          ON MATCH SET
            n.name = CASE WHEN coalesce(n.user_edited, false) THEN n.name ELSE $name END,
            n.displayName = CASE WHEN coalesce(n.user_edited, false) THEN n.displayName ELSE $display_name END,
            n.rootTable = CASE WHEN coalesce(n.user_edited, false) THEN n.rootTable ELSE $root_table END,
            n.bc_key = CASE WHEN coalesce(n.user_edited, false) THEN n.bc_key ELSE $bc_key END,
            n.memberFunctions = CASE WHEN coalesce(n.user_edited, false) THEN n.memberFunctions ELSE $member_functions END
        """,
        key=key, sid=sid, name=name, display_name=display_name, bc_key=bc_key,
        root_table=root_table, member_functions=member_functions,
    )


def _merge_command(s: Session, sid: str, key: str, name: str, display_name: str,
                   aggregate_key: str, actor: str, branch_local_id: str | None) -> None:
    s.run(
        """
        MERGE (n:Command {key: $key, session_id: $sid})
          ON CREATE SET
            n.id = $key,
            n.name = $name, n.displayName = $display_name,
            n.aggregate_key = $aggregate_key, n.actor = $actor,
            n.branch_local_id = $branch_local_id, n.user_edited = false
          ON MATCH SET
            n.name = CASE WHEN coalesce(n.user_edited, false) THEN n.name ELSE $name END,
            n.displayName = CASE WHEN coalesce(n.user_edited, false) THEN n.displayName ELSE $display_name END,
            n.aggregate_key = CASE WHEN coalesce(n.user_edited, false) THEN n.aggregate_key ELSE $aggregate_key END,
            n.actor = CASE WHEN coalesce(n.user_edited, false) THEN n.actor ELSE $actor END,
            n.branch_local_id = CASE WHEN coalesce(n.user_edited, false) THEN n.branch_local_id ELSE $branch_local_id END
        """,
        key=key, sid=sid, name=name, display_name=display_name,
        aggregate_key=aggregate_key, actor=actor, branch_local_id=branch_local_id,
    )


def _merge_event(s: Session, sid: str, key: str, name: str, display_name: str,
                 aggregate_key: str, op: str, target_table: str,
                 sequence_within_command: str | None) -> None:
    s.run(
        """
        MERGE (n:Event {key: $key, session_id: $sid})
          ON CREATE SET
            n.id = $key,
            n.name = $name, n.displayName = $display_name,
            n.aggregate_key = $aggregate_key, n.writeOp = $op,
            n.targetTable = $target_table,
            n.sequenceWithinCommand = $sequence_within_command,
            n.user_edited = false
          ON MATCH SET
            n.name = CASE WHEN coalesce(n.user_edited, false) THEN n.name ELSE $name END,
            n.displayName = CASE WHEN coalesce(n.user_edited, false) THEN n.displayName ELSE $display_name END,
            n.aggregate_key = CASE WHEN coalesce(n.user_edited, false) THEN n.aggregate_key ELSE $aggregate_key END,
            n.writeOp = CASE WHEN coalesce(n.user_edited, false) THEN n.writeOp ELSE $op END,
            n.targetTable = CASE WHEN coalesce(n.user_edited, false) THEN n.targetTable ELSE $target_table END,
            n.sequenceWithinCommand = CASE WHEN coalesce(n.user_edited, false) THEN n.sequenceWithinCommand ELSE $sequence_within_command END
        """,
        key=key, sid=sid, name=name, display_name=display_name, op=op,
        aggregate_key=aggregate_key, target_table=target_table,
        sequence_within_command=sequence_within_command,
    )


def _merge_policy(s: Session, sid: str, key: str, name: str, description: str,
                  bc_key: str, kind: str) -> None:
    s.run(
        """
        MERGE (n:Policy {key: $key, session_id: $sid})
          ON CREATE SET
            n.id = $key,
            n.name = $name, n.displayName = $name,
            n.description = $description, n.bc_key = $bc_key, n.kind = $kind,
            n.user_edited = false
          ON MATCH SET
            n.name = CASE WHEN coalesce(n.user_edited, false) THEN n.name ELSE $name END,
            n.displayName = CASE WHEN coalesce(n.user_edited, false) THEN n.displayName ELSE $name END,
            n.description = CASE WHEN coalesce(n.user_edited, false) THEN n.description ELSE $description END,
            n.bc_key = CASE WHEN coalesce(n.user_edited, false) THEN n.bc_key ELSE $bc_key END,
            n.kind = CASE WHEN coalesce(n.user_edited, false) THEN n.kind ELSE $kind END
        """,
        key=key, sid=sid, name=name, description=description,
        bc_key=bc_key, kind=kind,
    )


def _merge_readmodel(s: Session, sid: str, key: str, name: str, display_name: str,
                     bc_key: str) -> None:
    s.run(
        """
        MERGE (n:ReadModel {key: $key, session_id: $sid})
          ON CREATE SET
            n.id = $key,
            n.name = $name, n.displayName = $display_name,
            n.bc_key = $bc_key, n.user_edited = false
          ON MATCH SET
            n.name = CASE WHEN coalesce(n.user_edited, false) THEN n.name ELSE $name END,
            n.displayName = CASE WHEN coalesce(n.user_edited, false) THEN n.displayName ELSE $display_name END,
            n.bc_key = CASE WHEN coalesce(n.user_edited, false) THEN n.bc_key ELSE $bc_key END
        """,
        key=key, sid=sid, name=name, display_name=display_name, bc_key=bc_key,
    )


# =============================================================================
# Public entry point
# =============================================================================


def save_named_session(
    session: Session,
    *,
    session_id: str,
    sd: SessionDecomposition,
    named: NamedSession,
) -> dict[str, int]:
    """Persist all nodes + traceability edges. Returns counts per kind."""
    counts: dict[str, int] = {
        "user_story": 0, "bounded_context": 0, "aggregate": 0, "command": 0,
        "event": 0, "policy": 0, "read_model": 0,
        "edge_promoted_from": 0, "edge_implements": 0, "edge_sourced_from": 0,
        "edge_derived_from": 0, "edge_grounded_in": 0, "edge_precondition_by": 0,
        "edge_emits": 0, "edge_has_command": 0, "edge_has_aggregate": 0,
        "edge_has_userstory": 0, "edge_has_policy": 0, "edge_has_readmodel": 0,
        "edge_attached_to": 0, "edge_raised_in": 0, "edge_reads_from": 0,
    }

    bc_of_us: dict[str, str] = {}
    for bc in named.bcs:
        for us_id in bc.user_story_ids:
            bc_of_us[us_id] = bc.key
    if named.bcs:
        primary = named.bcs[0].key
        for us in sd.user_stories:
            bc_of_us.setdefault(us.id, primary)

    # ----- 1. UserStory nodes + PROMOTED_FROM + SOURCED_FROM ----------------
    for us in sd.user_stories:
        bc_key = bc_of_us.get(us.id, named.bcs[0].key if named.bcs else "bc_default")
        shape = named.user_story_shapes.get(us.id)
        _merge_user_story(
            session, session_id, us, bc_key=bc_key, source=us.source,
            action=(shape.action if shape else ""),
            benefit=(shape.benefit if shape else ""),
        )
        counts["user_story"] += 1

        # PROMOTED_FROM (US → BpmTask)
        session.run(
            """
            MATCH (us:UserStory {id: $usid, session_id: $sid})
            MATCH (t:BpmTask {id: $tid, session_id: $sid})
            MERGE (us)-[r:PROMOTED_FROM]->(t)
              ON CREATE SET r.via = 'task', r.source = $src
              ON MATCH  SET r.source = $src
            """,
            usid=us.id, tid=us.task_id, sid=session_id, src=us.source,
        )
        counts["edge_promoted_from"] += 1

        # SOURCED_FROM (US → Rule) — analyzer Rule (no session_id) is referenced
        # by the same `id` we extracted from the Cypher query (rule_<sha1>).
        for rid in us.rule_ids:
            session.run(
                """
                MATCH (us:UserStory {id: $usid, session_id: $sid})
                MATCH (r:Rule {id: $rid, session_id: $sid})
                MERGE (us)-[:SOURCED_FROM]->(r)
                """,
                usid=us.id, rid=rid, sid=session_id,
            )
            counts["edge_sourced_from"] += 1

    # ----- 2. BoundedContext nodes + HAS_USERSTORY -------------------------
    for bc in named.bcs:
        _merge_bc(session, session_id, bc)
        counts["bounded_context"] += 1
        for us_id in bc.user_story_ids:
            # Two edges: HAS_USERSTORY (Phase 5 §5.1 spec) + reverse IMPLEMENTS
            # (legacy navigator/bigpicture_timeline/user_stories ops query the
            # reverse direction). Without the legacy edge the canvas shows
            # zero US under each BC even though grouping is correct.
            session.run(
                """
                MATCH (bc:BoundedContext {key: $bk, session_id: $sid})
                MATCH (us:UserStory {id: $usid, session_id: $sid})
                MERGE (bc)-[:HAS_USERSTORY]->(us)
                MERGE (us)-[:IMPLEMENTS]->(bc)
                """,
                bk=bc.key, usid=us_id, sid=session_id,
            )
            counts["edge_has_userstory"] += 1

    # ----- 3. Aggregate nodes + HAS_AGGREGATE / IMPLEMENTS / DERIVED_FROM /
    #          GROUNDED_IN / PROMOTED_FROM ----------------------------------
    agg_key_of_root: dict[str, str] = {}
    for agg in sd.aggregates:
        an = named.aggregate_names.get(agg.root_table)
        if not an:
            continue
        agg_key = f"agg_{agg.root_table}"
        agg_key_of_root[agg.root_table] = agg_key
        _merge_aggregate(
            session, session_id, key=agg_key, name=an.name, display_name=an.display_name,
            bc_key=an.bc_key, root_table=agg.root_table, member_functions=agg.member_functions,
        )
        counts["aggregate"] += 1

        # HAS_AGGREGATE
        session.run(
            """
            MATCH (bc:BoundedContext {key: $bk, session_id: $sid})
            MATCH (a:Aggregate {key: $ak, session_id: $sid})
            MERGE (bc)-[:HAS_AGGREGATE]->(a)
            """,
            bk=an.bc_key, ak=agg_key, sid=session_id,
        )
        counts["edge_has_aggregate"] += 1

        # IMPLEMENTS / PROMOTED_FROM (multi). Bidirectional IMPLEMENTS so legacy
        # navigator code (queries (US)-[:IMPLEMENTS]->(target)) and Phase 5
        # spec readers ((target)-[:IMPLEMENTS]->(US)) both resolve.
        for us_id in agg.user_story_ids:
            session.run(
                """
                MATCH (a:Aggregate {key: $ak, session_id: $sid})
                MATCH (us:UserStory {id: $usid, session_id: $sid})
                MERGE (a)-[:IMPLEMENTS]->(us)
                MERGE (us)-[:IMPLEMENTS]->(a)
                """,
                ak=agg_key, usid=us_id, sid=session_id,
            )
            counts["edge_implements"] += 1
        for tid in agg.contributing_task_ids:
            session.run(
                """
                MATCH (a:Aggregate {key: $ak, session_id: $sid})
                MATCH (t:BpmTask {id: $tid, session_id: $sid})
                MERGE (a)-[r:PROMOTED_FROM]->(t)
                  ON CREATE SET r.via = 'rules'
                """,
                ak=agg_key, tid=tid, sid=session_id,
            )
            counts["edge_promoted_from"] += 1

        # DERIVED_FROM (Aggregate → Rule, every member rule)
        for rid in agg.member_rule_ids:
            session.run(
                """
                MATCH (a:Aggregate {key: $ak, session_id: $sid})
                MATCH (r:Rule {id: $rid, session_id: $sid})
                MERGE (a)-[:DERIVED_FROM]->(r)
                """,
                ak=agg_key, rid=rid, sid=session_id,
            )
            counts["edge_derived_from"] += 1

        # GROUNDED_IN (Aggregate → Table) — analyzer Table has no session_id
        session.run(
            """
            MATCH (a:Aggregate {key: $ak, session_id: $sid})
            MATCH (t:Table {name: $tname})
            WHERE t.session_id IS NULL
            MERGE (a)-[:GROUNDED_IN]->(t)
            """,
            ak=agg_key, tname=agg.root_table, sid=session_id,
        )
        counts["edge_grounded_in"] += 1

    # ----- 4. Commands + HAS_COMMAND / IMPLEMENTS / PROMOTED_FROM /
    #          PRECONDITION_BY ----------------------------------------------
    for cmd in sd.commands:
        cn = named.command_names.get(cmd.id)
        if not cn:
            continue
        cmd_key = f"cmd_{cmd.id}"
        agg_key = agg_key_of_root.get(cmd.aggregate_root_table or "", "")
        # Validation-only tasks have a Command but no write-bearing rules → no
        # Aggregate to attach. Persist anyway with empty aggregate_key so the
        # node lives on the canvas; HAS_COMMAND edge skipped in that case.
        _merge_command(
            session, session_id, key=cmd_key, name=cn.name, display_name=cn.display_name,
            aggregate_key=agg_key, actor=cmd.actor, branch_local_id=cmd.branch_local_id,
        )
        counts["command"] += 1

        # HAS_COMMAND only when an Aggregate owns this Command.
        if agg_key:
            session.run(
                """
                MATCH (a:Aggregate {key: $ak, session_id: $sid})
                MATCH (c:Command {key: $ck, session_id: $sid})
                MERGE (a)-[:HAS_COMMAND]->(c)
                """,
                ak=agg_key, ck=cmd_key, sid=session_id,
            )
            counts["edge_has_command"] += 1

        # IMPLEMENTS (bidirectional — see Aggregate IMPLEMENTS comment) + PROMOTED_FROM
        session.run(
            """
            MATCH (c:Command {key: $ck, session_id: $sid})
            MATCH (us:UserStory {id: $usid, session_id: $sid})
            MERGE (c)-[:IMPLEMENTS]->(us)
            MERGE (us)-[:IMPLEMENTS]->(c)
            """,
            ck=cmd_key, usid=cmd.user_story_id, sid=session_id,
        )
        counts["edge_implements"] += 1
        session.run(
            """
            MATCH (c:Command {key: $ck, session_id: $sid})
            MATCH (t:BpmTask {id: $tid, session_id: $sid})
            MERGE (c)-[r:PROMOTED_FROM]->(t) ON CREATE SET r.via = 'task'
            """,
            ck=cmd_key, tid=cmd.task_id, sid=session_id,
        )
        counts["edge_promoted_from"] += 1

        # PRECONDITION_BY (Command → Rule for each guard)
        for rid in cmd.precondition_rule_ids:
            session.run(
                """
                MATCH (c:Command {key: $ck, session_id: $sid})
                MATCH (r:Rule {id: $rid, session_id: $sid})
                MERGE (c)-[:PRECONDITION_BY]->(r)
                """,
                ck=cmd_key, rid=rid, sid=session_id,
            )
            counts["edge_precondition_by"] += 1

    # ----- 5. Events + EMITS / IMPLEMENTS / PROMOTED_FROM / DERIVED_FROM ---
    for ev in sd.events:
        en = named.event_names.get(ev.id)
        if not en:
            continue
        ev_key = f"evt_{ev.id}"
        agg_key = agg_key_of_root.get(ev.aggregate_root_table, "")
        _merge_event(
            session, session_id, key=ev_key, name=en.name, display_name=en.display_name,
            aggregate_key=agg_key, op=ev.op, target_table=ev.target_table,
            sequence_within_command=ev.sequence_within_command,
        )
        counts["event"] += 1

        # EMITS — find the command that emits this rule
        emitting_cmd_key = _find_emitting_command_key(sd, ev.rule_id, ev.task_id)
        if emitting_cmd_key:
            session.run(
                """
                MATCH (c:Command {key: $ck, session_id: $sid})
                MATCH (e:Event {key: $ek, session_id: $sid})
                MERGE (c)-[:EMITS]->(e)
                """,
                ck=emitting_cmd_key, ek=ev_key, sid=session_id,
            )
            counts["edge_emits"] += 1

        # IMPLEMENTS (bidirectional) + PROMOTED_FROM + DERIVED_FROM (Example)
        session.run(
            """
            MATCH (e:Event {key: $ek, session_id: $sid})
            MATCH (us:UserStory {id: $usid, session_id: $sid})
            MERGE (e)-[:IMPLEMENTS]->(us)
            MERGE (us)-[:IMPLEMENTS]->(e)
            """,
            ek=ev_key, usid=ev.user_story_id, sid=session_id,
        )
        counts["edge_implements"] += 1
        session.run(
            """
            MATCH (e:Event {key: $ek, session_id: $sid})
            MATCH (t:BpmTask {id: $tid, session_id: $sid})
            MERGE (e)-[r:PROMOTED_FROM]->(t)
              ON CREATE SET r.via = 'aggregate_event', r.rule_id = $rid
            """,
            ek=ev_key, tid=ev.task_id, sid=session_id, rid=ev.rule_id,
        )
        counts["edge_promoted_from"] += 1
        if ev.derived_from_example_id:
            session.run(
                """
                MATCH (e:Event {key: $ek, session_id: $sid})
                MATCH (ex:Example {example_id: $exid})
                WHERE ex.session_id IS NULL
                MERGE (e)-[:DERIVED_FROM]->(ex)
                """,
                ek=ev_key, exid=ev.derived_from_example_id, sid=session_id,
            )
            counts["edge_derived_from"] += 1

    # ----- 6. Policies + HAS_POLICY / IMPLEMENTS / PROMOTED_FROM ----------
    for pol in sd.policies:
        pn = named.policy_names.get(pol.id)
        if not pn:
            continue
        pol_key = f"pol_{pol.id}"
        bc_key = bc_of_us.get(pol.user_story_id, named.bcs[0].key if named.bcs else "bc_default")
        kind = "cross_bc" if pol.coupled_domains else "per_fn"
        _merge_policy(
            session, session_id, key=pol_key, name=pn.name, description=pn.description,
            bc_key=bc_key, kind=kind,
        )
        counts["policy"] += 1
        session.run(
            """
            MATCH (bc:BoundedContext {key: $bk, session_id: $sid})
            MATCH (p:Policy {key: $pk, session_id: $sid})
            MERGE (bc)-[:HAS_POLICY]->(p)
            """,
            bk=bc_key, pk=pol_key, sid=session_id,
        )
        counts["edge_has_policy"] += 1
        session.run(
            """
            MATCH (p:Policy {key: $pk, session_id: $sid})
            MATCH (us:UserStory {id: $usid, session_id: $sid})
            MERGE (p)-[:IMPLEMENTS]->(us)
            MERGE (us)-[:IMPLEMENTS]->(p)
            """,
            pk=pol_key, usid=pol.user_story_id, sid=session_id,
        )
        counts["edge_implements"] += 1
        session.run(
            """
            MATCH (p:Policy {key: $pk, session_id: $sid})
            MATCH (t:BpmTask {id: $tid, session_id: $sid})
            MERGE (p)-[r:PROMOTED_FROM]->(t)
              ON CREATE SET r.via = 'coupled_domain'
            """,
            pk=pol_key, tid=pol.task_id, sid=session_id,
        )
        counts["edge_promoted_from"] += 1

    # ----- 7. ReadModels + HAS_READMODEL / IMPLEMENTS / PROMOTED_FROM ------
    for rm in sd.read_models:
        rmn = named.read_model_names.get(rm.id)
        if not rmn:
            continue
        rm_key = f"rm_{rm.id}"
        bc_key = bc_of_us.get(rm.user_story_id, named.bcs[0].key if named.bcs else "bc_default")
        _merge_readmodel(
            session, session_id, key=rm_key, name=rmn.name, display_name=rmn.display_name, bc_key=bc_key,
        )
        counts["read_model"] += 1
        session.run(
            """
            MATCH (bc:BoundedContext {key: $bk, session_id: $sid})
            MATCH (rm:ReadModel {key: $rk, session_id: $sid})
            MERGE (bc)-[:HAS_READMODEL]->(rm)
            """,
            bk=bc_key, rk=rm_key, sid=session_id,
        )
        counts["edge_has_readmodel"] += 1
        session.run(
            """
            MATCH (rm:ReadModel {key: $rk, session_id: $sid})
            MATCH (us:UserStory {id: $usid, session_id: $sid})
            MERGE (rm)-[:IMPLEMENTS]->(us)
            MERGE (us)-[:IMPLEMENTS]->(rm)
            """,
            rk=rm_key, usid=rm.user_story_id, sid=session_id,
        )
        counts["edge_implements"] += 1
        session.run(
            """
            MATCH (rm:ReadModel {key: $rk, session_id: $sid})
            MATCH (t:BpmTask {id: $tid, session_id: $sid})
            MERGE (rm)-[r:PROMOTED_FROM]->(t)
              ON CREATE SET r.via = 'task'
            """,
            rk=rm_key, tid=rm.task_id, sid=session_id,
        )
        counts["edge_promoted_from"] += 1

    # ----- 8. Question pass-through (ATTACHED_TO + RAISED_IN) -------------
    for q in sd.questions:
        # pick a "primary" BC — first one is fine; UI can re-attach via manual edit.
        bc_key = named.bcs[0].key if named.bcs else "bc_default"
        session.run(
            """
            MATCH (bc:BoundedContext {key: $bk, session_id: $sid})
            MATCH (q:Question {question_id: $qid})
            WHERE q.session_id IS NULL
            MERGE (q)-[:ATTACHED_TO]->(bc)
            """,
            bk=bc_key, qid=q.question_id, sid=session_id,
        )
        counts["edge_attached_to"] += 1
        session.run(
            """
            MATCH (q:Question {question_id: $qid})
            MATCH (f)
            WHERE coalesce(f.procedure_name, f.name) = $fn
            MERGE (q)-[:RAISED_IN]->(f)
            """,
            qid=q.question_id, fn=q.host_function,
        )
        counts["edge_raised_in"] += 1

    return counts


def _find_emitting_command_key(
    sd: SessionDecomposition, rule_id: str, task_id: str,
) -> str | None:
    """Locate the Command whose emit_rule_ids contains this rule, scoped to the task."""
    for cmd in sd.commands:
        if cmd.task_id != task_id:
            continue
        if rule_id in cmd.emit_rule_ids:
            return f"cmd_{cmd.id}"
    return None


# =============================================================================
# Wipe — used by re-run policy (PRD §6.3) before re-promoting.
# =============================================================================


# Labels wiped on re-promotion. Mirrors `promote_to_es.ALL_PROMOTED_LABELS`
# (kept in sync — that module re-exports the same logical set with a few extra
# future-compat entries). See ALL_PROMOTED_LABELS docstring for rationale.
_WIPE_LABELS = (
    "UserStory", "BoundedContext", "Aggregate", "Command", "Event",
    "Policy", "ReadModel", "CQRSConfig", "CQRSOperation",
    "UI", "GWT",
    "Property", "ValueObject", "Enumeration", "AggregateRoot", "TestCase",
)


def clear_promoted_nodes(
    session: Session, session_id: str, *, preserve_manual: bool = True,
) -> dict[str, int]:
    """Wipe ES nodes for this session. Manual-edited nodes preserved by default.

    CRITICAL — single-label only. See `_tag_orphan_promoted_nodes` docstring:
    the analyzer puts stereotype labels (Command / Query / Validation /
    Handler) on FUNCTION nodes as multi-labels. Without the
    `size(labels(n)) = 1` guard, a stray session_id on a multi-label FUNCTION
    (e.g. via a buggy tag pass) would cause this DETACH DELETE to wipe analyzer
    code nodes — destroying HAS_RULE / AFFECTS_TABLE chains the next promotion
    relies on. Phase 5/6 ES nodes are always single-label so this is safe.
    """
    counts: dict[str, int] = {}
    for label in _WIPE_LABELS:
        where = ["size(labels(n)) = 1"]
        if preserve_manual:
            where.append("coalesce(n.user_edited, false) = false")
        where_clause = " WHERE " + " AND ".join(where)
        cypher = (
            f"MATCH (n:{label} {{session_id: $sid}})"
            f"{where_clause} "
            "WITH n, count(n) AS c DETACH DELETE n RETURN c"
        )
        rec = session.run(cypher, sid=session_id).single()
        if rec and rec["c"]:
            counts[label] = int(rec["c"])
    return counts
