"""Requirements tree aggregation (026 — requirements-tab).

Builds the Epic(BoundedContext) → Feature → UserStory → AcceptanceCriteria
4-level tree in a few graph queries, assembled in Python.

Bucketing (research R8):
- A User Story with a BC but no Feature → that Epic's `unassignedFeature`.
- A User Story with no BC at all → the top-level `unassigned` list.
"""

from __future__ import annotations

import json
from typing import Any

from api.platform.neo4j import get_session
from api.features.requirements.requirements_contracts import (
    AcceptanceCriterionDTO,
    EpicNodeDTO,
    FeatureNodeDTO,
    RequirementsTreeDTO,
    UserStoryNodeDTO,
)


def _load_json(raw: Any) -> Any:
    """GWT ref / testCase fields are persisted as JSON strings — tolerate
    dicts/lists (already decoded) and malformed values."""
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def _gwt_by_command() -> dict[str, list[AcceptanceCriterionDTO]]:
    """Acceptance criteria (Given/When/Then) keyed by Command id.

    Reads the single-`GWT`-node model: each Command has at most one `GWT`
    node (via `HAS_GWT`) carrying `givenRef`/`whenRef`/`thenRef` (the
    Given-When-Then skeleton — node references) and `testCases` (concrete
    acceptance scenarios). This is the one GWT model written by every code
    path (the `generate_gwt` ingestion phase, the interactive GWT editor,
    and the legacy event-storming persistence).
    """
    query = """
    MATCH (cmd:Command)-[:HAS_GWT]->(g:GWT)
    RETURN cmd.id AS cmdId,
           g.givenRef AS givenRef, g.whenRef AS whenRef,
           g.thenRef AS thenRef, g.testCases AS testCases
    """
    out: dict[str, list[AcceptanceCriterionDTO]] = {}
    with get_session() as session:
        for rec in session.run(query):
            cmd_id = rec["cmdId"]
            if not cmd_id:
                continue
            criteria: list[AcceptanceCriterionDTO] = []
            # Given-When-Then skeleton from the node references.
            for kind, raw in (
                ("given", rec["givenRef"]),
                ("when", rec["whenRef"]),
                ("then", rec["thenRef"]),
            ):
                ref = _load_json(raw)
                if isinstance(ref, dict):
                    label = (ref.get("name") or ref.get("exceptionName") or "").strip()
                    if label:
                        criteria.append(
                            AcceptanceCriterionDTO(kind=kind, name=label)  # type: ignore[arg-type]
                        )
            # Concrete acceptance scenarios.
            for tc in _load_json(rec["testCases"]) or []:
                if not isinstance(tc, dict):
                    continue
                desc = (tc.get("scenarioDescription") or "").strip()
                if desc:
                    criteria.append(AcceptanceCriterionDTO(kind="then", name=desc))
            if criteria:
                out[cmd_id] = criteria
    return out


def _user_story_dto(row: dict[str, Any], gwt: dict[str, list]) -> UserStoryNodeDTO:
    us = row["us"] or {}
    cmd_id = row.get("cmdId")
    return UserStoryNodeDTO(
        id=us.get("id"),
        role=us.get("role") or "",
        action=us.get("action") or "",
        benefit=us.get("benefit") or "",
        priority=us.get("priority") or "medium",
        status=us.get("status") or "draft",
        commandId=cmd_id,
        commandName=row.get("cmdName"),
        acceptanceCriteria=gwt.get(cmd_id, []) if cmd_id else [],
    )


def user_story_node_dto(user_story_id: str) -> UserStoryNodeDTO | None:
    """Build a single UserStoryNodeDTO (used by create/move responses)."""
    query = """
    MATCH (us:UserStory {id: $id})
    OPTIONAL MATCH (us)-[:IMPLEMENTS]->(cmd:Command)
    RETURN us {.id, .role, .action, .benefit, .priority, .status} AS us,
           cmd.id AS cmdId, cmd.name AS cmdName
    """
    with get_session() as session:
        rec = session.run(query, id=user_story_id).single()
    if not rec or not rec["us"]:
        return None
    gwt = _gwt_by_command()
    return _user_story_dto({"us": rec["us"], "cmdId": rec["cmdId"], "cmdName": rec["cmdName"]}, gwt)


def build_requirements_tree() -> RequirementsTreeDTO:
    """Assemble the full Epic→Feature→UserStory→AC tree."""
    gwt = _gwt_by_command()

    # All bounded contexts (epics) — shown even when they have no stories yet.
    with get_session() as session:
        bc_rows = list(
            session.run(
                "MATCH (bc:BoundedContext) RETURN bc.id AS id, bc.name AS name, bc.displayName AS displayName, bc.description AS description ORDER BY bc.name"
            )
        )
        feature_rows = list(
            session.run(
                """
                MATCH (bc:BoundedContext)-[:HAS_FEATURE]->(f:Feature)
                RETURN f.id AS id, f.name AS name, f.description AS description,
                       f.source AS source, bc.id AS bcId, f.sequence AS sequence
                ORDER BY f.sequence, f.name
                """
            )
        )
        us_rows = list(
            session.run(
                """
                MATCH (us:UserStory)
                OPTIONAL MATCH (us)-[:IMPLEMENTS]->(bc:BoundedContext)
                OPTIONAL MATCH (f:Feature)-[:HAS_USER_STORY]->(us)
                OPTIONAL MATCH (us)-[:IMPLEMENTS]->(cmd:Command)
                RETURN us {.id, .role, .action, .benefit, .priority, .status} AS us,
                       bc.id AS bcId,
                       f.id AS featureId,
                       cmd.id AS cmdId, cmd.name AS cmdName
                """
            )
        )

    # Index features by id and by BC.
    features: dict[str, FeatureNodeDTO] = {}
    features_by_bc: dict[str, list[str]] = {}
    for fr in feature_rows:
        fid = fr["id"]
        features[fid] = FeatureNodeDTO(
            id=fid,
            name=fr["name"] or "",
            description=fr.get("description"),
            source=fr.get("source") or "llm",
            boundedContextId=fr.get("bcId"),
        )
        features_by_bc.setdefault(fr["bcId"], []).append(fid)

    # Per-BC "unassigned feature" buckets and the global unassigned list.
    bc_unassigned: dict[str, list[UserStoryNodeDTO]] = {}
    global_unassigned: list[UserStoryNodeDTO] = []
    seen: set[str] = set()

    for row in us_rows:
        us = row["us"] or {}
        us_id = us.get("id")
        if not us_id or us_id in seen:
            continue
        seen.add(us_id)
        dto = _user_story_dto(row, gwt)
        feature_id = row.get("featureId")
        bc_id = row.get("bcId")
        if feature_id and feature_id in features:
            features[feature_id].userStories.append(dto)
        elif bc_id:
            bc_unassigned.setdefault(bc_id, []).append(dto)
        else:
            global_unassigned.append(dto)

    epics: list[EpicNodeDTO] = []
    for bc in bc_rows:
        bc_id = bc["id"]
        epic_features = [features[fid] for fid in features_by_bc.get(bc_id, [])]
        unassigned = bc_unassigned.get(bc_id)
        epics.append(
            EpicNodeDTO(
                id=bc_id,
                name=bc["name"] or "",
                displayName=bc["displayName"],
                description=bc.get("description"),
                features=epic_features,
                unassignedFeature=(
                    FeatureNodeDTO(
                        id=f"__unassigned__{bc_id}",
                        name="미분류",
                        source="manual",
                        userStories=unassigned,
                    )
                    if unassigned
                    else None
                ),
            )
        )

    return RequirementsTreeDTO(epics=epics, unassigned=global_unassigned)
