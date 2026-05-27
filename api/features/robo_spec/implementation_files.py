"""Neo4j CRUD for :ImplementationFile nodes and [:IMPLEMENTED_IN] relationships.

Implements the source-mapping ontology described in
specs/029-robo-spec-skills/data-model.md §1.2 / §1.3.

Per research R5, source mapping is stored exclusively in the graph (no
workspace-local manifest), so this module is the *only* place that reads
or writes file-to-element links.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Literal

from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger

# Roles permitted on :ImplementationFile.role (data-model.md §1.2).
# Validated at the API layer; not enforced by Cypher.
ALLOWED_ROLES: tuple[str, ...] = (
    "primary",
    "interface-adapter",
    "infrastructure",
    "test",
    "other",
)

# Element labels that may carry [:IMPLEMENTED_IN] (data-model.md §1.3).
ELEMENT_LABELS: tuple[str, ...] = ("Aggregate", "Command", "Event", "ReadModel")


class InvalidPathError(ValueError):
    """Raised when a caller supplies a path that violates the contract.

    See data-model.md §1.2: paths must be workspace-relative POSIX, no
    absolute paths, no `..` segments. Validation happens here so the HTTP
    and MCP entry points share a single rule.
    """


class InvalidRoleError(ValueError):
    """Raised when ``role`` is not one of ALLOWED_ROLES."""


def _validate_path(path: str) -> str:
    """Reject absolute paths and any `..` segments; normalize to POSIX."""
    if not isinstance(path, str) or not path:
        raise InvalidPathError("path must be a non-empty string")
    if path.startswith("/") or path.startswith("\\"):
        raise InvalidPathError(f"path must be workspace-relative: {path!r}")
    # Normalize Windows-style separators to POSIX before splitting.
    posix = path.replace("\\", "/")
    parts = [p for p in posix.split("/") if p]
    if any(p == ".." for p in parts):
        raise InvalidPathError(f"path must not contain '..' segments: {path!r}")
    return "/".join(parts)


def _validate_role(role: str) -> str:
    if role not in ALLOWED_ROLES:
        raise InvalidRoleError(
            f"role must be one of {ALLOWED_ROLES!r}, got {role!r}"
        )
    return role


def register(
    *,
    project_id: str,
    element_id: str,
    files: Iterable[dict[str, str]],
    mode: Literal["replace", "merge"] = "merge",
) -> dict[str, Any]:
    """Create or update [:IMPLEMENTED_IN] links for one element.

    Args:
        project_id: Robo Architect project UUID. Persisted on the
            :ImplementationFile node.
        element_id: id of the Aggregate / Command / Event / ReadModel the
            files implement.
        files: iterable of ``{"path": "...", "role": "..."}`` entries.
        mode: "replace" clears existing [:IMPLEMENTED_IN] for this element
            before recreating; "merge" only adds new links (idempotent).

    Returns:
        ``{"elementId": str, "filesNow": int}`` per contract T6b.

    Raises:
        InvalidPathError: any path is absolute or contains ``..``.
        InvalidRoleError: any role is not in ALLOWED_ROLES.
    """
    # Validate all entries before touching the graph so a single bad
    # input fails the whole call cleanly (atomic from the caller's POV).
    normalized: list[dict[str, str]] = []
    for f in files:
        path = _validate_path(f.get("path", ""))
        role = _validate_role(f.get("role", ""))
        normalized.append({"path": path, "role": role})

    now_iso = datetime.now(timezone.utc).isoformat()

    label_match = "|".join(ELEMENT_LABELS)

    if mode not in ("replace", "merge"):
        raise ValueError(f"mode must be 'replace' or 'merge', got {mode!r}")

    # We use label filtering via ``WHERE any(lbl IN $element_labels WHERE
    # lbl IN labels(e))`` rather than Cypher 5's ``:A|B|C`` label-expression
    # syntax so this module stays compatible with both 4.x and 5.x Neo4j.
    clear_query = """
    MATCH (e { id: $element_id })-[r:IMPLEMENTED_IN]->()
    WHERE any(lbl IN $element_labels WHERE lbl IN labels(e))
    DELETE r
    """

    # The UNWIND lives inside a CALL subquery so the outer ``RETURN
    # count(r)`` always runs exactly once even when ``$files`` is empty
    # (the empty-files seed case used by /robo-plan's final step).
    upsert_query = """
    MATCH (e { id: $element_id })
    WHERE any(lbl IN $element_labels WHERE lbl IN labels(e))
    CALL {
        WITH e
        UNWIND $files as f
          MERGE (impl:ImplementationFile { projectId: $project_id, path: f.path })
          ON CREATE SET impl.id = randomUUID(),
                        impl.role = f.role,
                        impl.createdAt = $now,
                        impl.lastSeenAt = $now
          ON MATCH  SET impl.role = f.role,
                        impl.lastSeenAt = $now
          MERGE (e)-[:IMPLEMENTED_IN]->(impl)
          RETURN count(*) as merged
    }
    OPTIONAL MATCH (e)-[r:IMPLEMENTED_IN]->()
    RETURN count(r) as filesNow
    """

    with get_session() as session:
        if mode == "replace":
            session.run(
                clear_query,
                element_id=element_id,
                element_labels=list(ELEMENT_LABELS),
            )
        record = session.run(
            upsert_query,
            project_id=project_id,
            element_id=element_id,
            element_labels=list(ELEMENT_LABELS),
            files=normalized,
            now=now_iso,
        ).single()

    files_now = int((record or {}).get("filesNow") or 0)
    SmartLogger.log(
        "INFO",
        "ImplementationFile links registered.",
        category="robo_spec.implementation_files.register",
        params={
            "projectId": project_id,
            "elementId": element_id,
            "mode": mode,
            "filesGiven": len(normalized),
            "filesNow": files_now,
        },
    )
    return {"elementId": element_id, "filesNow": files_now}


def lookup_by_element(
    *,
    project_id: str,
    element_id: str,
) -> list[dict[str, Any]]:
    """Return every :ImplementationFile linked to ``element_id`` for this project."""
    query = """
    MATCH (e { id: $element_id })-[:IMPLEMENTED_IN]->(impl:ImplementationFile)
    WHERE impl.projectId = $project_id
    RETURN impl { .path, .role, .lastSeenAt } as file
    ORDER BY impl.role, impl.path
    """
    with get_session() as session:
        return [dict(r["file"]) for r in session.run(
            query, project_id=project_id, element_id=element_id,
        )]


def lookup_by_bc(
    *,
    project_id: str,
    bc_id: str,
) -> dict[str, list[dict[str, Any]]]:
    """Return all element→files mappings under a BC. Used by HTTP E6.

    Returns a map ``{element_id: [{path, role, lastSeenAt}, ...]}``. Elements
    with zero linked files are included with an empty list so the frontend
    can render the "not implemented yet" affordance up-front.
    """
    query = """
    MATCH (bc:BoundedContext { id: $bc_id })
    OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(agg:Aggregate)
    OPTIONAL MATCH (agg)-[:HAS_COMMAND]->(cmd:Command)
    OPTIONAL MATCH (cmd)-[:EMITS]->(evt:Event)
    OPTIONAL MATCH (bc)-[:HAS_READMODEL]->(rm:ReadModel)
    WITH collect(DISTINCT agg) + collect(DISTINCT cmd)
         + collect(DISTINCT evt) + collect(DISTINCT rm) as elements
    UNWIND elements as e
    WITH e WHERE e IS NOT NULL
    OPTIONAL MATCH (e)-[:IMPLEMENTED_IN]->(impl:ImplementationFile {projectId: $project_id})
    WITH e,
         collect({ path: impl.path, role: impl.role, lastSeenAt: impl.lastSeenAt }) as files
    RETURN
        e.id as elementId,
        head([lbl IN labels(e) WHERE lbl IN $element_labels]) as kind,
        e.name as name,
        [f IN files WHERE f.path IS NOT NULL] as files
    """
    out: dict[str, dict[str, Any]] = {}
    with get_session() as session:
        for r in session.run(
            query,
            bc_id=bc_id,
            project_id=project_id,
            element_labels=list(ELEMENT_LABELS),
        ):
            eid = r["elementId"]
            if not eid:
                continue
            out[eid] = {
                "kind": r["kind"],
                "name": r["name"],
                "files": [dict(f) for f in (r["files"] or [])],
            }
    return out
