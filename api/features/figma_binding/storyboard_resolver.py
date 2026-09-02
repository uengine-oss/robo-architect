"""Resolve which storyboard a UI node belongs to.

A "storyboard" is the vertical slice rooted at one user-initiated entry
:Command (a Command not invoked by any :Policy). The resolver mirrors the
frontend's `_buildProcessChains` BFS but lives entirely in Cypher so we
don't import logic from `canvas_graph` (Constitution V — cross-feature
sharing happens "through Neo4j", not via Python imports).

See specs/016-figma-document-binding/research.md D9.
"""

from __future__ import annotations

from typing import Any

from api.platform.neo4j import get_session


# Maximum BFS depth. Long enough for realistic event-storming chains
# (Command→Event→Policy→Command×N→...→UI), short enough to bound runtime.
MAX_BFS_HOPS = 30

# Relationship types that participate in storyboard reachability.
# Includes both Event Modeling flow edges and structural edges that
# attach UI nodes (HAS_UI from BC, ATTACHED_TO from various sources).
_REL_TYPES = "EMITS|TRIGGERS|INVOKES|HAS_AGGREGATE|HAS_COMMAND|HAS_UI|ATTACHED_TO|REFERENCES|HAS_THEN|HAS_POLICY"


def list_entry_commands() -> list[dict[str, Any]]:
    """All :Command nodes that are NOT invoked by any :Policy.
    Ordered canonically (displayName ascending, id as tie-break).
    """
    with get_session() as session:
        records = session.run(
            """
            MATCH (c:Command)
            OPTIONAL MATCH (c)<-[pinv:INVOKES]-(:Policy)
            WITH c, count(pinv) AS invoked
            WHERE invoked = 0
            RETURN c.id AS id,
                   coalesce(c.displayName, c.name) AS displayName,
                   c.name AS name
            ORDER BY coalesce(c.displayName, c.name), c.id
            """
        ).data()
    return [dict(r) for r in records]


def resolve_storyboard_for_ui(
    ui_node_id: str, entry_commands: list[dict[str, Any]] | None = None
) -> str | None:
    """Return the entry Command's id whose storyboard contains the given UI,
    or None if no entry command reaches it.

    Tie-breaker (multiple reachable entry commands): canonical ordering above.

    `entry_commands` lets a caller resolving many UIs fetch the entry list once;
    omitted, it is fetched per call.

    Two statements, and that is the whole performance story. The original
    narrowed to entry commands with `WITH u, c, count(pinv) …` and *then*
    matched the variable-length path against `c` and `u`. Values that pass a
    `WITH` become jsonb, so re-opening them as pattern targets makes the
    expansion enumerate paths instead of walking the adjacency: measured 3.3s at
    depth 10, 19.3s at 12, and at the configured 30 it exhausted the server's
    temp space and died. Anchored on the UI alone the same reachability is
    immeasurable (0.00s) at depth 30, so the narrowing happens here instead.
    """
    if not ui_node_id:
        return None

    reachable_q = f"""
        MATCH (u:UI {{id: $uid}})-[:{_REL_TYPES}*1..{MAX_BFS_HOPS}]-(c:Command)
        RETURN DISTINCT c.id AS id
    """
    with get_session() as session:
        reachable = {r["id"] for r in session.run(reachable_q, uid=ui_node_id) if r["id"]}
    if not reachable:
        return None

    # `list_entry_commands` already returns the canonical order, so the first
    # match is the same one the old `ORDER BY … LIMIT 1` picked.
    for c in entry_commands if entry_commands is not None else list_entry_commands():
        if c["id"] in reachable:
            return c["id"]
    return None


def get_command_display_name(command_id: str) -> str | None:
    with get_session() as session:
        rec = session.run(
            """
            MATCH (c:Command {id: $cid})
            RETURN coalesce(c.displayName, c.name) AS displayName
            """,
            cid=command_id,
        ).single()
    if not rec:
        return None
    return rec["displayName"]


def get_step_count_for_storyboard(command_id: str) -> int:
    """Approximate step count = distinct nodes reachable from the entry command
    (capped). Used only for the storyboards list endpoint (display only).
    """
    cypher = f"""
        MATCH (c:Command {{id: $cid}})
        OPTIONAL MATCH (c)-[:{_REL_TYPES}*1..{MAX_BFS_HOPS}]-(n)
        RETURN count(DISTINCT n) AS stepCount
    """
    with get_session() as session:
        rec = session.run(cypher, cid=command_id).single()
    return int(rec["stepCount"]) if rec and rec["stepCount"] is not None else 0
