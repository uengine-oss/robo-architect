"""Requirements tree aggregation (026 — requirements-tab).

Builds the Epic(BoundedContext) → Feature → UserStory → AcceptanceCriteria
4-level tree in a few graph queries, assembled in Python.

Bucketing (research R8):
- A User Story with a BC but no Feature → that Epic's `unassignedFeature`.
- A User Story with no BC at all → the top-level `unassigned` list.
"""

from __future__ import annotations

from typing import Any

from api.platform.neo4j import get_session
from api.features.requirements.requirements_contracts import (
    AcceptanceCriterionDTO,
    EpicNodeDTO,
    FeatureNodeDTO,
    RequirementsTreeDTO,
    UserStoryNodeDTO,
)


def _gwt_by_command() -> dict[str, list[AcceptanceCriterionDTO]]:
    """Acceptance criteria (Given/When/Then) keyed by Command id."""
    query = """
    MATCH (cmd:Command)
    OPTIONAL MATCH (cmd)-[:HAS_GIVEN]->(g:Given)
    OPTIONAL MATCH (cmd)-[:HAS_WHEN]->(w:When)
    OPTIONAL MATCH (cmd)-[:HAS_THEN]->(t:Then)
    RETURN cmd.id AS cmdId,
           g {.name, .description} AS given,
           w {.name, .description} AS when,
           t {.name, .description} AS then
    """
    out: dict[str, list[AcceptanceCriterionDTO]] = {}
    with get_session() as session:
        for rec in session.run(query):
            cmd_id = rec["cmdId"]
            criteria: list[AcceptanceCriterionDTO] = []
            for kind, payload in (
                ("given", rec["given"]),
                ("when", rec["when"]),
                ("then", rec["then"]),
            ):
                if payload and payload.get("name"):
                    criteria.append(
                        AcceptanceCriterionDTO(
                            kind=kind,  # type: ignore[arg-type]
                            name=payload.get("name") or "",
                            description=payload.get("description"),
                        )
                    )
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
                "MATCH (bc:BoundedContext) RETURN bc.id AS id, bc.name AS name ORDER BY bc.name"
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
