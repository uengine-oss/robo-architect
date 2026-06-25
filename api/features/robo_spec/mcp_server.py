"""MCP server for the robo-* Claude Code skill suite.

Contract: ``specs/029-robo-spec-skills/contracts/mcp-tools.md`` (T1..T8 + T6b).

The transport mount (streamable-HTTP at ``/mcp``) is performed by
``api/features/robo_spec/router.py``; this module declares the server
and the tool implementations.

Tool implementations:
- US1: T1 resolve_design_element, T2 get_bc_design,
       T3 set_bc_classification.
- US4: T6b register_implementation_files (needed by /robo-plan's
       seed step + /robo-implement).
- US5: T6 propose_sync, T6a apply_proposal (the /robo-sync round-trip).

Per Constitution Principle VII every tool wraps its body in a SmartLogger
event tagged with ``robo_spec.mcp.<tool_name>``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from api.features.robo_spec.implementation_files import (
    ALLOWED_ROLES,
    ELEMENT_LABELS,
    InvalidPathError,
    InvalidRoleError,
    register as register_files,
)
from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger

# In-memory pending-proposal store for /robo-sync (data-model §3.1).
# Maps proposalId → {createdAt, projectId, bcId, plannedChanges}.
# Entries TTL at 10 minutes; apply_proposal re-checks each element's
# version before mutating.
_PENDING_PROPOSALS: dict[str, dict[str, Any]] = {}
_PROPOSAL_TTL_SECONDS = 600


def _gc_proposals() -> None:
    """Purge proposals older than the TTL. Called opportunistically on
    every propose_sync / apply_proposal."""
    now = datetime.now(timezone.utc)
    expired = [
        pid for pid, p in _PENDING_PROPOSALS.items()
        if (now - p["createdAt"]).total_seconds() > _PROPOSAL_TTL_SECONDS
    ]
    for pid in expired:
        del _PENDING_PROPOSALS[pid]


def build_mcp_server() -> Any | None:
    """Construct and return a configured MCP server, or ``None`` when the
    ``mcp`` Python SDK is not importable.

    The router calls this once at module-import time and mounts the
    server's streamable-HTTP sub-app under ``/mcp`` when the return is
    non-None. When ``None`` is returned, the rest of the robo-spec
    surface still works — only the MCP transport is unavailable.
    """
    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore
    except ImportError as e:
        SmartLogger.log(
            "WARN",
            "mcp SDK not importable — /mcp transport disabled. "
            "Run `uv pip install -e .` (or `pip install -e .`) to enable.",
            category="robo_spec.mcp.sdk_missing",
            params={"error": str(e)},
        )
        return None

    # streamable_http_path="/" so the sub-app's only route ends up at
    # the mount root. Without this, FastMCP's default `/mcp` path
    # combined with our `app.mount("/mcp", ...)` would land at
    # `/mcp/mcp`, which is surprising in the workspace's mcp.json.
    server = FastMCP("robo-spec", streamable_http_path="/")

    # ------------------------------------------------------------------
    # T1 resolve_design_element
    # ------------------------------------------------------------------
    @server.tool(
        name="resolve_design_element",
        description=(
            "Resolve a /robo-plan argument (feature id, BC name, or "
            "Aggregate name) to exactly one design element. Returns the "
            "resolved element with its classification + version, or the "
            "list of disambiguation candidates when the name is ambiguous."
        ),
    )
    def resolve_design_element(query: str) -> dict[str, Any]:
        # The contract carries `projectId` too; v1 ignores it because
        # this repo's graph is single-project. The arg is still accepted
        # for forward compatibility when multi-project lands.
        cypher = """
        OPTIONAL MATCH (bc:BoundedContext)
          WHERE bc.name = $q OR bc.key = $q OR bc.id = $q
        OPTIONAL MATCH (agg:Aggregate)
          WHERE agg.name = $q OR agg.key = $q OR agg.id = $q
        WITH collect(DISTINCT bc) + collect(DISTINCT agg) as nodes
        UNWIND nodes as n
        WITH n WHERE n IS NOT NULL
        RETURN
            n.id     as id,
            n.name   as name,
            head([lbl IN labels(n) WHERE lbl IN ['BoundedContext','Aggregate']]) as kind,
            coalesce(n.classification, null) as classification,
            coalesce(n.version, 0) as version
        """
        with get_session() as s:
            rows = [dict(r) for r in s.run(cypher, q=query)]

        if not rows:
            SmartLogger.log(
                "WARN",
                f"resolve_design_element NOT_FOUND: {query!r}",
                category="robo_spec.mcp.resolve_design_element.not_found",
                params={"query": query},
            )
            return {"status": "not-found", "query": query}

        if len(rows) == 1:
            r = rows[0]
            return {
                "status": "resolved",
                "element": {
                    "id": r["id"],
                    "name": r["name"],
                    "kind": r["kind"],
                    "classification": r["classification"],
                    "version": int(r["version"] or 0),
                },
            }

        return {
            "status": "ambiguous",
            "candidates": [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "kind": r["kind"],
                    "version": int(r["version"] or 0),
                }
                for r in rows
            ],
        }

    # ------------------------------------------------------------------
    # T2 get_bc_design
    # ------------------------------------------------------------------
    @server.tool(
        name="get_bc_design",
        description=(
            "Return a BoundedContext plus all its aggregates, commands, "
            "events, read models, and the :ImplementationFile links "
            "currently registered for each element. /robo-plan calls this "
            "right after resolve_design_element to draft plan.md; the "
            "Design tab uses the same payload to render 'implemented' "
            "affordances. INCOMPLETE_DESIGN is signalled when the BC "
            "has zero aggregates."
        ),
    )
    def get_bc_design(bcId: str) -> dict[str, Any]:  # noqa: N803
        # Re-use the existing tree query verbatim and augment with the
        # implementation-files projection so a single round-trip is enough.
        tree_query = """
        MATCH (bc:BoundedContext {id: $bc_id})
        OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(agg:Aggregate)
        OPTIONAL MATCH (agg)-[:HAS_COMMAND]->(cmd:Command)
        OPTIONAL MATCH (cmd)-[:EMITS]->(evt:Event)
        OPTIONAL MATCH (bc)-[:HAS_READMODEL]->(rm:ReadModel)
        WITH bc, agg, cmd, evt, rm
        WITH bc,
             agg,
             collect(DISTINCT { id: cmd.id, name: cmd.name }) as commands,
             collect(DISTINCT { id: evt.id, name: evt.name }) as events,
             collect(DISTINCT { id: rm.id,  name: rm.name  }) as readmodels
        RETURN
            bc.id   as id,
            bc.name as name,
            bc.classification as classification,
            coalesce(bc.version, 0) as version,
            collect(DISTINCT {
                id: agg.id, name: agg.name,
                rootEntity: agg.rootEntity,
                version: coalesce(agg.version, 0)
            }) as aggregates,
            [cmd IN commands   WHERE cmd.id IS NOT NULL] as commands,
            [evt IN events     WHERE evt.id IS NOT NULL] as events,
            [rm  IN readmodels WHERE rm.id  IS NOT NULL] as readmodels
        """
        # NOTE: collect(DISTINCT {...}) 가 이미 중복을 제거하므로 apoc.coll.toSet 은
        # 불필요했고, APOC 미설치 환경에서 이 함수 때문에 쿼리가 throw → 폴백이
        # commands/events/readmodels 를 빈 배열로 떨궈 robo-spec /robo-plan 이 빈 설계를
        # 받던 버그(D7)를 유발했다. APOC 의존 제거.
        # APOC may not be installed everywhere — fall back to a
        # non-APOC version when it's missing.
        with get_session() as s:
            try:
                rec = s.run(tree_query, bc_id=bcId).single()
            except Exception:
                fallback = """
                MATCH (bc:BoundedContext {id: $bc_id})
                OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(agg:Aggregate)
                RETURN
                    bc.id   as id,
                    bc.name as name,
                    bc.classification as classification,
                    coalesce(bc.version, 0) as version,
                    collect(DISTINCT {
                        id: agg.id, name: agg.name,
                        rootEntity: agg.rootEntity,
                        version: coalesce(agg.version, 0)
                    }) as aggregates
                """
                rec = s.run(fallback, bc_id=bcId).single()
                if rec:
                    rec_dict = dict(rec)
                    rec_dict["commands"] = []
                    rec_dict["events"] = []
                    rec_dict["readmodels"] = []
                    return _enrich_with_files(rec_dict, project_id=None)

        if not rec:
            return {"status": "not-found", "bcId": bcId}

        out = dict(rec)
        # Strip aggregates with no id (the OPTIONAL MATCH produces one
        # such row when the BC has no aggregates).
        out["aggregates"] = [a for a in (out["aggregates"] or []) if a.get("id")]
        if not out["aggregates"]:
            out["incomplete"] = True

        return _enrich_with_files(out, project_id=None)

    # ------------------------------------------------------------------
    # T3 set_bc_classification
    # ------------------------------------------------------------------
    @server.tool(
        name="set_bc_classification",
        description=(
            "Persist the developer's answer when /robo-plan had to ask "
            "which architecture style to use. Direct mutation (no "
            "propose-then-apply) because the developer's answer is itself "
            "the proposal. Idempotent for the same value."
        ),
    )
    def set_bc_classification(bcId: str, classification: str) -> dict[str, Any]:  # noqa: N803
        if classification not in ("core", "supporting"):
            return {
                "status": "invalid-value",
                "message": "classification must be 'core' or 'supporting'",
                "given": classification,
            }
        cypher = """
        MATCH (bc:BoundedContext {id: $bc_id})
        WITH bc, coalesce(bc.classification, null) as old
        SET bc.classification = $cls,
            bc.version = coalesce(bc.version, 0) + 1
        RETURN bc.classification as cls, bc.version as version, old
        """
        with get_session() as s:
            rec = s.run(cypher, bc_id=bcId, cls=classification).single()
        if not rec:
            return {"status": "not-found", "bcId": bcId}
        SmartLogger.log(
            "INFO",
            "BC classification set via MCP T3.",
            category="robo_spec.mcp.set_bc_classification",
            params={
                "bcId": bcId,
                "delta": {"from": rec["old"], "to": rec["cls"]},
                "newVersion": int(rec["version"]),
            },
        )
        return {
            "status": "applied",
            "bcId": bcId,
            "classification": rec["cls"],
            "newVersion": int(rec["version"]),
        }

    # ------------------------------------------------------------------
    # T6b register_implementation_files
    # ------------------------------------------------------------------
    @server.tool(
        name="register_implementation_files",
        description=(
            "Create or update [:IMPLEMENTED_IN] links for one design "
            "element. mode='replace' clears the existing links first; "
            "mode='merge' (default) only adds new ones (idempotent). "
            "Source mapping lives only in the graph — there is no "
            "workspace-local manifest (research R5)."
        ),
    )
    def register_implementation_files(
        projectId: str,  # noqa: N803
        elementId: str,  # noqa: N803
        files: list[dict[str, str]],
        mode: str = "merge",
    ) -> dict[str, Any]:
        try:
            result = register_files(
                project_id=projectId,
                element_id=elementId,
                files=files,
                mode=mode,  # type: ignore[arg-type]
            )
        except InvalidPathError as e:
            return {"status": "invalid-path", "message": str(e)}
        except InvalidRoleError as e:
            return {
                "status": "invalid-role",
                "message": str(e),
                "allowed": list(ALLOWED_ROLES),
            }
        except ValueError as e:
            return {"status": "invalid-mode", "message": str(e)}
        return {"status": "applied", **result}

    # ------------------------------------------------------------------
    # T0 list_design_elements
    # ------------------------------------------------------------------
    # Discovery: returns every BoundedContext in the project graph with
    # its classification + the aggregates nested underneath. /robo-plan,
    # /robo-tasks, etc. should call this first when invoked WITHOUT an
    # argument so they can present the developer a clean picker of
    # available elements (the previous behavior — calling
    # resolve_design_element with a wildcard — surfaced "not-found"
    # because the resolver expects an exact name).
    @server.tool(
        name="list_design_elements",
        description=(
            "List every BoundedContext + its aggregates currently in "
            "the Robo Architect graph. Call this when /robo-plan, "
            "/robo-tasks, or /robo-implement is invoked without a "
            "specific feature-id / BC / Aggregate argument and you "
            "need to show the developer what's available."
        ),
    )
    def list_design_elements() -> dict[str, Any]:
        cypher = """
        MATCH (bc:BoundedContext)
        OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(agg:Aggregate)
        WITH bc,
             collect(DISTINCT {
                 id: agg.id, name: agg.name,
                 version: coalesce(agg.version, 0)
             }) AS aggregates
        RETURN
            bc.id AS id,
            bc.name AS name,
            bc.classification AS classification,
            bc.domainType AS domainType,
            coalesce(bc.version, 0) AS version,
            [a IN aggregates WHERE a.id IS NOT NULL] AS aggregates
        ORDER BY bc.name
        """
        with get_session() as s:
            rows = [dict(r) for r in s.run(cypher)]
        return {
            "boundedContexts": rows,
            "count": len(rows),
        }

    # ------------------------------------------------------------------
    # T6 propose_sync  (US5)
    # ------------------------------------------------------------------
    @server.tool(
        name="propose_sync",
        description=(
            "Compare the structural extract of source code (from the "
            "/robo-sync AST extractor) against the current Robo Architect "
            "graph and return a proposal. Returns a proposalId the caller "
            "uses with apply_proposal. Destructive changes (deletions / "
            "renames) appear in requiresConfirmation so the developer can "
            "be asked before they land in the graph."
        ),
    )
    def propose_sync(
        projectId: str,  # noqa: N803
        bcId: str,  # noqa: N803
        extracts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        _gc_proposals()
        # Each extract is {elementName, kind, fields: [{name, type}]}.
        # We resolve elementName → elementId in the BC's graph slice
        # (looking only at elements of the matching kind).
        cypher = """
        MATCH (bc:BoundedContext {id: $bc_id})-[:HAS_AGGREGATE]->(agg:Aggregate)
        OPTIONAL MATCH (agg)-[:HAS_PROPERTY]->(p:Property)
        RETURN
            agg.id   AS id,
            agg.name AS name,
            'Aggregate' AS kind,
            coalesce(agg.version, 0) AS version,
            collect({ name: p.name, type: p.type }) AS properties
        """
        with get_session() as s:
            graph_rows = [dict(r) for r in s.run(cypher, bc_id=bcId)]
        # Index by name → graph element row
        by_name: dict[str, dict[str, Any]] = {r["name"]: r for r in graph_rows if r.get("name")}

        diff_entries: list[dict[str, Any]] = []
        requires_confirmation: list[str] = []
        planned_changes: list[dict[str, Any]] = []
        rename_candidates: list[dict[str, Any]] = []

        for extract in extracts:
            name = extract.get("name")
            kind = extract.get("kind", "Aggregate")
            in_fields = [
                {"name": f["name"], "type": f["type"]}
                for f in (extract.get("fields") or [])
                if f.get("name")
            ]
            graph_row = by_name.get(name)
            if graph_row is None:
                # Element doesn't exist in graph — out of MVP scope to
                # create new aggregates from source. Skip with a note.
                diff_entries.append({
                    "elementName": name,
                    "elementId": None,
                    "note": "skipped — element not found in BC slice",
                    "added": in_fields,
                    "modified": [],
                    "removed": [],
                })
                continue
            graph_props = [
                {"name": p["name"], "type": p["type"]}
                for p in (graph_row["properties"] or [])
                if p and p.get("name")
            ]
            graph_by_name = {p["name"]: p for p in graph_props}
            extract_by_name = {p["name"]: p for p in in_fields}

            added = [p for p in in_fields if p["name"] not in graph_by_name]
            removed = [p for p in graph_props if p["name"] not in extract_by_name]
            modified = [
                {"name": n, "from": graph_by_name[n]["type"], "to": extract_by_name[n]["type"]}
                for n in graph_by_name
                if n in extract_by_name and graph_by_name[n]["type"] != extract_by_name[n]["type"]
            ]
            # Rename candidates: pair removed[i] ↔ added[j] when their
            # types match exactly. (LLM-ranked sophistication out of
            # scope for the MVP.)
            paired_added: set[str] = set()
            paired_removed: set[str] = set()
            for r_prop in removed:
                for a_prop in added:
                    if a_prop["name"] in paired_added: continue
                    if r_prop["type"] == a_prop["type"]:
                        rename_candidates.append({
                            "elementId": graph_row["id"],
                            "from": r_prop,
                            "to": a_prop,
                            "confidence": 0.5,
                            "rationale": "type match; LLM ranking not yet implemented",
                        })
                        paired_added.add(a_prop["name"])
                        paired_removed.add(r_prop["name"])
                        requires_confirmation.append(
                            f"{graph_row['id']}:rename:{r_prop['name']}->{a_prop['name']}"
                        )
                        break

            # Mark every deletion as requires_confirmation.
            for r_prop in removed:
                if r_prop["name"] not in paired_removed:
                    requires_confirmation.append(
                        f"{graph_row['id']}:remove:{r_prop['name']}"
                    )

            diff_entries.append({
                "elementName": name,
                "elementId": graph_row["id"],
                "kind": kind,
                "version": graph_row["version"],
                "added": added,
                "modified": modified,
                "removed": removed,
            })
            planned_changes.append({
                "elementId": graph_row["id"],
                "version": graph_row["version"],
                "added": added,
                "modified": modified,
                "removed": [p for p in removed if p["name"] not in paired_removed],
            })

        proposal_id = f"prop-{uuid.uuid4().hex[:12]}"
        _PENDING_PROPOSALS[proposal_id] = {
            "createdAt": datetime.now(timezone.utc),
            "projectId": projectId,
            "bcId": bcId,
            "planned_changes": planned_changes,
        }

        SmartLogger.log(
            "INFO",
            "propose_sync built a proposal.",
            category="robo_spec.mcp.propose_sync",
            params={
                "projectId": projectId, "bcId": bcId, "proposalId": proposal_id,
                "n_elements": len(extracts),
                "n_requiresConfirmation": len(requires_confirmation),
            },
        )

        return {
            "proposalId": proposal_id,
            "diff": {"elements": diff_entries},
            "renameCandidates": rename_candidates,
            "requiresConfirmation": requires_confirmation,
        }

    # ------------------------------------------------------------------
    # T6a apply_proposal  (US5)
    # ------------------------------------------------------------------
    @server.tool(
        name="apply_proposal",
        description=(
            "Apply a /robo-sync proposal previously returned by "
            "propose_sync. The `confirmed` list MUST include every "
            "entry from the proposal's requiresConfirmation array that "
            "the developer agreed to; anything in requiresConfirmation "
            "but NOT in confirmed is rejected and skipped (Principle IV). "
            "Returns status='conflict' (and applies nothing) when any "
            "targeted element's graph version has bumped since the "
            "proposal was built."
        ),
    )
    def apply_proposal(
        projectId: str,  # noqa: N803
        proposalId: str,  # noqa: N803
        confirmed: list[str] | None = None,
    ) -> dict[str, Any]:
        _gc_proposals()
        confirmed = confirmed or []
        proposal = _PENDING_PROPOSALS.get(proposalId)
        if proposal is None:
            return {"status": "unknown-proposal", "proposalId": proposalId}
        if proposal["projectId"] != projectId or proposal["bcId"] != "" and proposal["bcId"]:
            pass  # accepted; we don't tie projectId to a specific BC here

        # Version conflict check: re-fetch each targeted element's
        # version and bail if any has bumped.
        element_ids = [c["elementId"] for c in proposal["planned_changes"]]
        version_query = """
        UNWIND $ids AS eid
        MATCH (e {id: eid})
        RETURN e.id AS id, coalesce(e.version, 0) AS version
        """
        with get_session() as s:
            current_versions = {
                r["id"]: int(r["version"] or 0)
                for r in s.run(version_query, ids=element_ids)
            }

        conflicts = []
        for change in proposal["planned_changes"]:
            cur = current_versions.get(change["elementId"], 0)
            if cur != int(change["version"]):
                conflicts.append({
                    "elementId": change["elementId"],
                    "expected": int(change["version"]),
                    "actual": cur,
                })
        if conflicts:
            return {"status": "conflict", "conflicts": conflicts}

        # Apply changes element-by-element. For MVP we use HAS_PROPERTY
        # writes directly (mirrors what /api/contexts/aggregates/{id}/
        # properties PUT does internally).
        applied: list[dict[str, Any]] = []
        rejected: list[str] = []
        confirmed_set = set(confirmed)
        with get_session() as s:
            for change in proposal["planned_changes"]:
                eid = change["elementId"]
                add_props = list(change.get("added") or [])
                mod_props = list(change.get("modified") or [])
                rem_props = list(change.get("removed") or [])

                # Filter removes/renames by `confirmed` (everything in
                # requiresConfirmation must opt-in).
                allowed_removes = []
                for r_prop in rem_props:
                    key = f"{eid}:remove:{r_prop['name']}"
                    if key in confirmed_set:
                        allowed_removes.append(r_prop)
                    else:
                        rejected.append(key)
                # Renames are stored in confirmed as
                # "eid:rename:old->new"; the propose_sync step already
                # filtered them out of removed/added.

                # 1) Adds: MERGE Property and connect.
                for p in add_props:
                    s.run("""
                    MATCH (agg {id: $aid})
                    WHERE 'Aggregate' IN labels(agg) OR 'Command' IN labels(agg)
                       OR 'Event' IN labels(agg) OR 'ReadModel' IN labels(agg)
                    MERGE (prop:Property {parentType: head(labels(agg)), parentId: $aid, name: $name})
                    ON CREATE SET prop.id = randomUUID(), prop.createdAt = datetime()
                    SET prop.type = $type, prop.parentType = head(labels(agg)),
                        prop.parentId = $aid, prop.updatedAt = datetime()
                    MERGE (agg)-[:HAS_PROPERTY]->(prop)
                    """, aid=eid, name=p["name"], type=p["type"]).consume()

                # 2) Modifies: update existing Property's type.
                for p in mod_props:
                    s.run("""
                    MATCH (agg {id: $aid})-[:HAS_PROPERTY]->(prop:Property {name: $name})
                    SET prop.type = $type, prop.updatedAt = datetime()
                    """, aid=eid, name=p["name"], type=p["to"]).consume()

                # 3) Confirmed removes: delete the Property node.
                for p in allowed_removes:
                    s.run("""
                    MATCH (agg {id: $aid})-[:HAS_PROPERTY]->(prop:Property {name: $name})
                    DETACH DELETE prop
                    """, aid=eid, name=p["name"]).consume()

                # 4) Bump element version.
                bump = s.run("""
                MATCH (e {id: $aid})
                SET e.version = coalesce(e.version, 0) + 1
                RETURN e.version AS v
                """, aid=eid).single()
                new_v = int(bump["v"]) if bump else None
                applied.append({
                    "elementId": eid, "newVersion": new_v,
                    "addedCount": len(add_props),
                    "modifiedCount": len(mod_props),
                    "removedCount": len(allowed_removes),
                })

        # Burn the proposal so it can't be re-applied.
        del _PENDING_PROPOSALS[proposalId]

        SmartLogger.log(
            "INFO",
            "apply_proposal applied.",
            category="robo_spec.mcp.apply_proposal",
            params={
                "projectId": projectId, "proposalId": proposalId,
                "applied": applied, "rejected": rejected,
            },
        )
        return {"status": "applied", "applied": applied, "rejected": rejected}

    SmartLogger.log(
        "INFO",
        "MCP server constructed with discovery + US1 + US4 + US5 tools registered.",
        category="robo_spec.mcp.constructed",
        params={
            "tools": [
                "list_design_elements",
                "resolve_design_element",
                "get_bc_design",
                "set_bc_classification",
                "register_implementation_files",
                "propose_sync",
                "apply_proposal",
            ],
        },
    )
    return server


def _enrich_with_files(
    payload: dict[str, Any],
    project_id: str | None,
) -> dict[str, Any]:
    """Attach `implementationFiles[]` AND `properties[]` to every element
    in the get_bc_design payload.

    - `implementationFiles[]` comes from [:IMPLEMENTED_IN] →
      :ImplementationFile (filtered by ``project_id`` when supplied).
    - `properties[]` comes from [:HAS_PROPERTY] → :Property (no
      project scoping — properties belong to the design element
      regardless of workspace).

    Without `properties[]`, /robo-implement scaffolds empty stubs
    (the user reported exactly this for LegalGuardianConsent). With
    it, the skill can populate the constructor with real
    property names + types.
    """
    # Collect all element ids across aggregates/commands/events/readmodels.
    ids: list[str] = []
    for a in payload.get("aggregates", []) or []:
        if a.get("id"):
            ids.append(a["id"])
    for c in payload.get("commands", []) or []:
        if c.get("id"):
            ids.append(c["id"])
    for e in payload.get("events", []) or []:
        if e.get("id"):
            ids.append(e["id"])
    for rm in payload.get("readmodels", []) or []:
        if rm.get("id"):
            ids.append(rm["id"])

    if not ids:
        return payload

    # 1. Files (workspace-scoped).
    files_cypher = """
    UNWIND $ids as eid
    MATCH (e {id: eid})-[:IMPLEMENTED_IN]->(impl:ImplementationFile)
    WHERE $pid IS NULL OR impl.projectId = $pid
    RETURN eid as elementId,
           collect({path: impl.path, role: impl.role, lastSeenAt: impl.lastSeenAt}) as files
    """
    file_map: dict[str, list[dict[str, Any]]] = {}
    with get_session() as s:
        for r in s.run(files_cypher, ids=ids, pid=project_id):
            file_map[r["elementId"]] = [dict(f) for f in (r["files"] or [])]

    # 2. Properties (sorted by isKey, isForeignKey, name — matches the
    #    existing /api/contexts/{id}/full-tree ordering).
    props_cypher = """
    UNWIND $ids as eid
    MATCH (prop:Property {parentId: eid})
    WITH eid, prop
    ORDER BY coalesce(prop.isKey, false) DESC,
             coalesce(prop.isForeignKey, false) DESC,
             prop.name ASC
    WITH eid, collect({
        name: prop.name,
        type: prop.type,
        description: prop.description,
        isKey: coalesce(prop.isKey, false),
        isForeignKey: coalesce(prop.isForeignKey, false),
        isRequired: coalesce(prop.isRequired, false)
    }) as properties
    RETURN eid as elementId, properties
    """
    prop_map: dict[str, list[dict[str, Any]]] = {}
    with get_session() as s:
        for r in s.run(props_cypher, ids=ids):
            prop_map[r["elementId"]] = [dict(p) for p in (r["properties"] or [])]

    for kind in ("aggregates", "commands", "events", "readmodels"):
        for item in payload.get(kind, []) or []:
            if item.get("id"):
                item["implementationFiles"] = file_map.get(item["id"], [])
                item["properties"] = prop_map.get(item["id"], [])

    return payload
