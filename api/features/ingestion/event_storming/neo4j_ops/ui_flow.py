"""
UI Flow Operations (spec 025 v3 — Journey / JourneyStep node model).

Persists and reads the user-journey graph layer:
  - `:Journey`         — a purpose-driven user journey (first-class node)
  - `:JourneyStep`     — a journey-local step; kind 'screen' (SHOWS a shared
                         `:UI`) or 'gateway' (a branch diamond)
  - `(:BoundedContext)-[:HAS_JOURNEY]->(:Journey)`
  - `(:Journey)-[:HAS_STEP]->(:JourneyStep)`
  - `(:JourneyStep)-[:SHOWS]->(:UI)`            (screen steps only)
  - `(:JourneyStep)-[:NEXT {condition}]->(:JourneyStep)`   (the flow — edges,
    so branching is expressible)

The same screen reused across journeys is a distinct `:JourneyStep` in each
journey, all pointing at the one shared `:UI`.

`read_ui_flow_for_bcs` projects this node model back into the legacy
`{gateways, edges}` shape the event-modeling canvas already consumes, so the
storage refactor does not ripple into the frontend.
"""

from __future__ import annotations

from typing import Any


_JOURNEY_MERGE = """
MATCH (bc:BoundedContext {id: $bc_id})
MERGE (j:Journey {key: $journey_key})
  ON CREATE SET j.id = $journey_id, j.createdAt = datetime()
SET j.journeyId = $journey_slug,
    j.name = $name,
    j.description = $description,
    j.boundedContextId = $bc_id,
    j.source = $source,
    j.updatedAt = datetime()
MERGE (bc)-[:HAS_JOURNEY]->(j)
RETURN j.id AS id
"""

# Wipe a journey's existing steps before recreating — the journey node keeps
# its stable id; steps/edges are fully re-derived each run.
_WIPE_STEPS = """
MATCH (j:Journey {id: $journey_id})-[:HAS_STEP]->(st:JourneyStep)
DETACH DELETE st
"""

_STEP_UNWIND = """
MATCH (j:Journey {id: $journey_id})
UNWIND $steps AS st
MERGE (s:JourneyStep {key: st.key})
  ON CREATE SET s.id = st.id, s.createdAt = datetime()
SET s.kind = st.kind,
    s.label = st.label,
    s.sequence = st.sequence,
    s.journeyId = $journey_slug,
    s.source = $source,
    s.updatedAt = datetime()
MERGE (j)-[:HAS_STEP]->(s)
"""

_SHOWS_UNWIND = """
UNWIND $links AS l
MATCH (s:JourneyStep {id: l.step_id})
MATCH (u:UI {id: l.ui_id})
MERGE (s)-[:SHOWS]->(u)
"""

_NEXT_UNWIND = """
UNWIND $edges AS e
MATCH (a:JourneyStep {id: e.source_step_id})
MATCH (b:JourneyStep {id: e.target_step_id})
MERGE (a)-[r:NEXT {id: e.id}]->(b)
  ON CREATE SET r.createdAt = datetime()
SET r.condition = coalesce(e.condition, ''),
    r.documentExcerpt = coalesce(e.document_excerpt, ''),
    r.source = coalesce(e.source, 'llm'),
    r.updatedAt = datetime()
"""


class UIFlowOps:
    """Mixin on `Neo4jClient` — see `neo4j_client.py`."""

    # ─── Write ───────────────────────────────────────────────────────────

    def upsert_journey_graph(self, journey: dict[str, Any]) -> str | None:
        """
        Idempotently persist one journey's full graph.

        `journey` shape:
          {
            "journey_node_id", "journey_key", "journey_slug",
            "name", "description", "bounded_context_id", "source",
            "steps": [{id, key, kind, label, ui_id?, sequence}, ...],
            "next":  [{id, source_step_id, target_step_id, condition,
                       document_excerpt, source}, ...],
          }

        The journey node keeps its stable id across runs; its steps + edges
        are wiped and re-created so a re-derive cleanly reflects new output.
        Returns the journey node id.
        """
        steps = journey.get("steps") or []
        edges = journey.get("next") or []
        screen_links = [
            {"step_id": s["id"], "ui_id": s["ui_id"]}
            for s in steps
            if s.get("kind") == "screen" and s.get("ui_id")
        ]
        with self.session() as session:
            rec = session.run(
                _JOURNEY_MERGE,
                bc_id=journey["bounded_context_id"],
                journey_key=journey["journey_key"],
                journey_id=journey["journey_node_id"],
                journey_slug=journey["journey_slug"],
                name=journey["name"],
                description=journey.get("description") or "",
                source=journey.get("source") or "llm",
            ).single()
            if not rec:
                return None
            jid = rec["id"]

            session.run(_WIPE_STEPS, journey_id=jid).consume()
            if steps:
                session.run(
                    _STEP_UNWIND,
                    journey_id=jid,
                    journey_slug=journey["journey_slug"],
                    source=journey.get("source") or "llm",
                    steps=steps,
                ).consume()
            if screen_links:
                session.run(_SHOWS_UNWIND, links=screen_links).consume()
            if edges:
                session.run(_NEXT_UNWIND, edges=edges).consume()
            return jid

    def delete_llm_journeys_not_in(self, keep_ids: set[str], bc_ids: list[str]) -> int:
        """Delete `source='llm'` journeys (and their steps) in the given BCs
        whose id is not in `keep_ids`. Manual journeys are never touched."""
        if not bc_ids:
            return 0
        cypher = """
        MATCH (bc:BoundedContext)-[:HAS_JOURNEY]->(j:Journey {source: 'llm'})
        WHERE bc.id IN $bc_ids AND NOT j.id IN $keep_ids
        OPTIONAL MATCH (j)-[:HAS_STEP]->(st:JourneyStep)
        DETACH DELETE st, j
        RETURN count(DISTINCT j) AS deleted
        """
        with self.session() as session:
            rec = session.run(cypher, bc_ids=bc_ids, keep_ids=list(keep_ids)).single()
            return int((rec or {}).get("deleted", 0))

    # ─── Read (projected to the legacy canvas shape) ─────────────────────

    def read_ui_flow_for_bcs(self, bc_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        """
        Read the journey graph for the given BCs and PROJECT it into the
        `{gateways, edges}` shape the event-modeling canvas consumes:
          - gateway-kind JourneySteps → `gateways`
          - `:NEXT` edges → `edges`, with screen-step endpoints resolved to
            their `:UI` (kind 'ui') and gateway steps kept as kind 'gateway'.
        """
        if not bc_ids:
            return {"gateways": [], "edges": []}
        with self.session() as session:
            gw_cur = session.run(
                """
                MATCH (bc:BoundedContext)-[:HAS_JOURNEY]->(j:Journey)
                WHERE bc.id IN $bc_ids
                MATCH (j)-[:HAS_STEP]->(g:JourneyStep {kind: 'gateway'})
                RETURN g.id AS id, g.key AS key, g.label AS label,
                       'exclusive' AS kind,
                       j.boundedContextId AS bounded_context_id,
                       coalesce(g.source, 'llm') AS source,
                       coalesce(j.journeyId, '') AS journey_id,
                       coalesce(j.name, '') AS journey_name,
                       toString(g.createdAt) AS created_at,
                       toString(g.updatedAt) AS updated_at
                ORDER BY g.createdAt
                """,
                bc_ids=bc_ids,
            )
            gateways = [dict(rec) for rec in gw_cur]

            edge_cur = session.run(
                """
                MATCH (bc:BoundedContext)-[:HAS_JOURNEY]->(j:Journey)
                WHERE bc.id IN $bc_ids
                MATCH (j)-[:HAS_STEP]->(s1:JourneyStep)-[n:NEXT]->(s2:JourneyStep)
                MATCH (j)-[:HAS_STEP]->(s2)
                OPTIONAL MATCH (s1)-[:SHOWS]->(u1:UI)
                OPTIONAL MATCH (s2)-[:SHOWS]->(u2:UI)
                RETURN n.id AS id,
                       s1.kind AS s1_kind, s1.id AS s1_id, u1.id AS u1_id,
                       s2.kind AS s2_kind, s2.id AS s2_id, u2.id AS u2_id,
                       coalesce(n.condition, '') AS condition,
                       coalesce(n.source, 'llm') AS source,
                       coalesce(n.documentExcerpt, '') AS document_excerpt,
                       coalesce(j.journeyId, '') AS journey_id,
                       coalesce(j.name, '') AS journey_name,
                       toString(n.createdAt) AS created_at,
                       toString(n.updatedAt) AS updated_at
                ORDER BY n.createdAt
                """,
                bc_ids=bc_ids,
            )
            edges: list[dict[str, Any]] = []
            for rec in edge_cur:
                r = dict(rec)
                if r["s1_kind"] == "gateway":
                    src_id, src_kind = r["s1_id"], "gateway"
                else:
                    src_id, src_kind = r["u1_id"], "ui"
                if r["s2_kind"] == "gateway":
                    tgt_id, tgt_kind = r["s2_id"], "gateway"
                else:
                    tgt_id, tgt_kind = r["u2_id"], "ui"
                # A screen step with no SHOWS link cannot be drawn — skip.
                if not src_id or not tgt_id:
                    continue
                edges.append(
                    {
                        "id": r["id"],
                        "source_id": src_id,
                        "source_kind": src_kind,
                        "target_id": tgt_id,
                        "target_kind": tgt_kind,
                        "condition": r["condition"],
                        "source": r["source"],
                        "document_excerpt": r["document_excerpt"],
                        "journey_id": r["journey_id"],
                        "journey_name": r["journey_name"],
                        "created_at": r["created_at"],
                        "updated_at": r["updated_at"],
                    }
                )

            return {"gateways": gateways, "edges": edges}
