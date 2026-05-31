"""Recoverable deletion via snapshot DeletionRecord (034 — US delete + recovery).

Decision (user, 2026-05-31): option B — instead of an in-graph `:Archived`
tombstone (which would force a `NOT :Archived` filter onto every read query),
a deleted requirement subtree is serialized — node properties + every incident
relationship, with neighbours referenced by their natural `id` key — into a
single `:DeletionRecord` node, then the live nodes are `DETACH DELETE`d. The
live graph (and all existing tree / clarity / pending-design / ingestion
queries) stay untouched, and a batch can be restored faithfully later:
re-create the nodes by `id`, then re-MERGE each relationship to whichever
endpoints survive (neighbours deleted in the same batch are re-created too).

The snapshot is self-contained per batch, so restore never depends on the
current graph state beyond matching surviving neighbours by `id`.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from api.platform.observability.smart_logger import SmartLogger


# ── subtree collection ──────────────────────────────────────────────────────

def subtree_ids_for_epic(session, bc_id: str) -> list[str]:
    """Epic (BoundedContext) + its Features + their User Stories."""
    rec = session.run(
        """
        MATCH (bc:BoundedContext {id: $id})
        OPTIONAL MATCH (bc)-[:HAS_FEATURE]->(f:Feature)
        OPTIONAL MATCH (f)-[:HAS_USER_STORY]->(us:UserStory)
        WITH collect(DISTINCT bc.id) + collect(DISTINCT f.id)
           + collect(DISTINCT us.id) AS ids
        RETURN [x IN ids WHERE x IS NOT NULL] AS ids
        """,
        id=bc_id,
    ).single()
    return list(rec["ids"]) if rec and rec["ids"] else []


def subtree_ids_for_feature(session, feature_id: str, include_stories: bool) -> list[str]:
    """Feature, plus its User Stories when they are being deleted too."""
    if include_stories:
        rec = session.run(
            """
            MATCH (f:Feature {id: $id})
            OPTIONAL MATCH (f)-[:HAS_USER_STORY]->(us:UserStory)
            WITH collect(DISTINCT f.id) + collect(DISTINCT us.id) AS ids
            RETURN [x IN ids WHERE x IS NOT NULL] AS ids
            """,
            id=feature_id,
        ).single()
        return list(rec["ids"]) if rec and rec["ids"] else []
    return [feature_id]


def exclusive_design_ids(session, us_ids: list[str]) -> list[str]:
    """Design nodes the given User Stories implement that *no surviving* User
    Story also implements — the only design safe to remove when the
    requirement goes away. Shared design is preserved. Conservative: only
    nodes reached by a direct US-[:IMPLEMENTS]->design edge."""
    ids = [i for i in us_ids if i]
    if not ids:
        return []
    rec = session.run(
        """
        MATCH (us:UserStory)-[:IMPLEMENTS]->(d)
        WHERE us.id IN $ids AND d.id IS NOT NULL
        WITH DISTINCT d
        WHERE NOT EXISTS {
            MATCH (o:UserStory)-[:IMPLEMENTS]->(d)
            WHERE NOT o.id IN $ids
        }
        RETURN collect(d.id) AS ids
        """,
        ids=ids,
    ).single()
    return list(rec["ids"]) if rec and rec["ids"] else []


# ── snapshot capture ────────────────────────────────────────────────────────

def capture(
    session,
    node_ids: list[str],
    *,
    scope: str,
    root_label: str,
    root_name: str,
    actor: Optional[str] = None,
) -> Optional[str]:
    """Serialize the given nodes + their incident relationships into a
    DeletionRecord and return its batchId. Does NOT delete the live nodes —
    callers run their own (disposition-aware) deletion afterwards. Returns
    None when nothing matched (nothing to archive)."""
    ids = [i for i in dict.fromkeys(node_ids) if i]
    if not ids:
        return None

    nodes = session.run(
        """
        MATCH (n) WHERE n.id IN $ids
        RETURN collect({labels: labels(n), props: properties(n)}) AS nodes
        """,
        ids=ids,
    ).single()["nodes"]
    if not nodes:
        return None

    # Every relationship touching a snapshot node — neighbours referenced by id
    # so restore can re-link to survivors (or to same-batch re-created nodes).
    rels = session.run(
        """
        MATCH (a)-[r]-(b)
        WHERE a.id IN $ids AND startNode(r).id IS NOT NULL AND endNode(r).id IS NOT NULL
        WITH DISTINCT r, startNode(r) AS s, endNode(r) AS e
        RETURN collect({
            type: type(r), props: properties(r),
            startId: s.id, endId: e.id,
            startLabels: labels(s), endLabels: labels(e)
        }) AS rels
        """,
        ids=ids,
    ).single()["rels"]

    batch_id = str(uuid.uuid4())
    snapshot = json.dumps({"nodes": nodes, "rels": rels}, ensure_ascii=False, default=str)
    session.run(
        """
        CREATE (d:DeletionRecord {
            batchId: $batch_id, scope: $scope,
            rootLabel: $root_label, rootName: $root_name,
            actor: $actor, createdAt: $created_at, restored: false,
            nodeCount: $node_count, relCount: $rel_count, snapshot: $snapshot
        })
        """,
        batch_id=batch_id,
        scope=scope,
        root_label=root_label,
        root_name=root_name,
        actor=actor,
        created_at=datetime.now(timezone.utc).isoformat(),
        node_count=len(nodes),
        rel_count=len(rels),
        snapshot=snapshot,
    )
    SmartLogger.log(
        "INFO",
        "Deletion archived.",
        category="requirements.deletion.archive",
        params={"batch_id": batch_id, "scope": scope, "nodes": len(nodes), "rels": len(rels)},
    )
    return batch_id


def detach_delete(session, node_ids: list[str]) -> int:
    """DETACH DELETE the given live nodes; returns count removed."""
    ids = [i for i in dict.fromkeys(node_ids) if i]
    if not ids:
        return 0
    rec = session.run(
        "MATCH (n) WHERE n.id IN $ids DETACH DELETE n RETURN count(n) AS c",
        ids=ids,
    ).single()
    return int(rec["c"]) if rec else 0


# ── history + restore ───────────────────────────────────────────────────────

def list_records(session) -> list[dict]:
    rows = session.run(
        """
        MATCH (d:DeletionRecord)
        RETURN d.batchId AS batchId, d.scope AS scope, d.rootLabel AS rootLabel,
               d.rootName AS rootName, d.actor AS actor, d.createdAt AS createdAt,
               d.restored AS restored, d.nodeCount AS nodeCount, d.relCount AS relCount
        ORDER BY d.createdAt DESC
        """
    )
    return [dict(r) for r in rows]


def restore(session, batch_id: str) -> dict:
    """Re-create the snapshot nodes (MERGE by id) and re-link relationships to
    whichever endpoints exist now (survivors or same-batch re-creations)."""
    rec = session.run(
        "MATCH (d:DeletionRecord {batchId: $b}) RETURN d.snapshot AS snapshot, d.restored AS restored",
        b=batch_id,
    ).single()
    if not rec:
        return {"restored": False, "reason": "not_found"}
    if rec["restored"]:
        return {"restored": False, "reason": "already_restored"}

    snap = json.loads(rec["snapshot"])
    nodes, rels = snap.get("nodes", []), snap.get("rels", [])

    for n in nodes:
        labels = ":".join(_sanitize_label(l) for l in n["labels"])
        session.run(
            f"MERGE (n {{id: $id}}) SET n = $props SET n:{labels}",
            id=n["props"]["id"],
            props=n["props"],
        )

    relinked = 0
    for r in rels:
        res = session.run(
            f"""
            MATCH (a {{id: $s}}), (b {{id: $e}})
            MERGE (a)-[rel:`{_sanitize_rel(r['type'])}`]->(b)
            SET rel = $props
            RETURN count(rel) AS c
            """,
            s=r["startId"],
            e=r["endId"],
            props=r.get("props") or {},
        ).single()
        relinked += int(res["c"]) if res else 0

    session.run(
        "MATCH (d:DeletionRecord {batchId: $b}) SET d.restored = true, d.restoredAt = $ts",
        b=batch_id,
        ts=datetime.now(timezone.utc).isoformat(),
    )
    SmartLogger.log(
        "INFO",
        "Deletion restored.",
        category="requirements.deletion.restore",
        params={"batch_id": batch_id, "nodes": len(nodes), "relinked": relinked},
    )
    return {"restored": True, "nodeCount": len(nodes), "relinked": relinked}


def purge(session, batch_id: str) -> bool:
    """Permanently drop a DeletionRecord (no recovery afterward)."""
    rec = session.run(
        "MATCH (d:DeletionRecord {batchId: $b}) DELETE d RETURN count(d) AS c",
        b=batch_id,
    ).single()
    return bool(rec and rec["c"])


# Neo4j label/rel-type names come from our own graph, but sanitize defensively
# so a snapshot can never inject Cypher via a backtick-laden label.
def _sanitize_label(label: str) -> str:
    return "".join(ch for ch in str(label) if ch.isalnum() or ch == "_") or "Node"


def _sanitize_rel(rel: str) -> str:
    return "".join(ch for ch in str(rel) if ch.isalnum() or ch == "_") or "REL"
