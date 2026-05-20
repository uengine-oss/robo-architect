from __future__ import annotations

from typing import Any

from ._bulk_helper import (
    BulkResult,
    bulk_flush,
    reorder_to_input,
)


_USER_STORY_BULK_CYPHER = """
UNWIND $rows AS r
MERGE (us:UserStory {id: r.id})
  ON CREATE SET us.name = r.name,
                us.role = r.role,
                us.action = r.action,
                us.benefit = r.benefit,
                us.priority = r.priority,
                us.status = r.status,
                us.uiDescription = r.ui_description,
                us.displayName = r.display_name,
                us.sourceScreenName = r.source_screen_name,
                us.sourceUnitId = r.source_unit_id,
                us.sequence = r.sequence,
                us.acceptanceCriteria = r.acceptance_criteria,
                us.createdAt = datetime()
  ON MATCH SET us.name = CASE WHEN us.name IS NULL THEN r.name ELSE us.name END,
               us.role = CASE WHEN r.role IS NOT NULL AND r.role <> '' THEN r.role ELSE us.role END,
               us.action = CASE WHEN r.action IS NOT NULL AND r.action <> '' THEN r.action ELSE us.action END,
               us.benefit = CASE WHEN r.benefit IS NOT NULL AND r.benefit <> '' THEN r.benefit ELSE us.benefit END,
               us.priority = CASE WHEN r.priority IS NOT NULL AND r.priority <> '' THEN r.priority ELSE us.priority END,
               us.status = CASE WHEN r.status IS NOT NULL AND r.status <> '' THEN r.status ELSE us.status END,
               us.uiDescription = CASE WHEN r.ui_description IS NOT NULL AND r.ui_description <> '' THEN r.ui_description ELSE us.uiDescription END,
               us.displayName = CASE WHEN r.display_name IS NOT NULL AND r.display_name <> '' THEN r.display_name ELSE us.displayName END,
               us.sourceScreenName = CASE WHEN r.source_screen_name IS NOT NULL AND r.source_screen_name <> '' THEN r.source_screen_name ELSE us.sourceScreenName END,
               us.sourceUnitId = CASE WHEN r.source_unit_id IS NOT NULL AND r.source_unit_id <> '' THEN r.source_unit_id ELSE us.sourceUnitId END,
               us.sequence = CASE WHEN r.sequence IS NOT NULL THEN r.sequence ELSE us.sequence END,
               us.acceptanceCriteria = CASE
                   WHEN coalesce(us.criteriaUserEdited, false) THEN us.acceptanceCriteria
                   WHEN r.acceptance_criteria IS NOT NULL AND size(r.acceptance_criteria) > 0 THEN r.acceptance_criteria
                   ELSE us.acceptanceCriteria
               END,
               us.updatedAt = datetime()
RETURN us {.id, .name, .role, .action, .benefit, .priority, .status, .sequence,
           uiDescription: us.uiDescription, displayName: us.displayName,
           sourceScreenName: us.sourceScreenName, sourceUnitId: us.sourceUnitId,
           acceptanceCriteria: us.acceptanceCriteria,
           criteriaUserEdited: coalesce(us.criteriaUserEdited, false),
           criteriaEditedAt: us.criteriaEditedAt} AS result
"""


def _normalize_user_story_row(r: dict[str, Any]) -> dict[str, Any]:
    """Apply the same defaults as `create_user_story` so the Cypher SET
    clauses see consistent shapes."""
    role = r.get("role") or ""
    action = r.get("action") or ""
    name = r.get("name")
    if not name:
        name = f"{role}: {action[:60]}" if action else f"{role}: (no action)"
    return {
        "id": r["id"],
        "name": name,
        "role": role,
        "action": action,
        "benefit": r.get("benefit"),
        "priority": r.get("priority") or "medium",
        "status": r.get("status") or "draft",
        "ui_description": r.get("ui_description") or "",
        "display_name": r.get("display_name") or "",
        "source_screen_name": r.get("source_screen_name") or "",
        "source_unit_id": r.get("source_unit_id") or "",
        "sequence": r.get("sequence"),
        "acceptance_criteria": list(r.get("acceptance_criteria") or []),
    }


def _criteria_clean(values: Any) -> list[str]:
    """Strip empty-after-trim entries; cap is enforced at the API boundary."""
    if not values:
        return []
    cleaned: list[str] = []
    for v in values:
        if v is None:
            continue
        s = str(v).strip()
        if s:
            cleaned.append(s)
    return cleaned


class UserStoryOps:
    # =========================================================================
    # User Story Operations
    # =========================================================================

    def get_all_user_stories(self) -> list[dict[str, Any]]:
        """Fetch all user stories from Neo4j."""
        query = """
        MATCH (us:UserStory)
        OPTIONAL MATCH (us)-[:IMPLEMENTS]->(target)
        WITH us, collect(DISTINCT {type: labels(target)[0], name: target.name, id: target.id}) as implemented_in
        RETURN {
            id: us.id,
            role: us.role,
            action: us.action,
            benefit: us.benefit,
            priority: us.priority,
            status: us.status,
            uiDescription: us.uiDescription,
            displayName: us.displayName,
            sourceScreenName: us.sourceScreenName,
            implemented_in: implemented_in
        } as user_story
        ORDER BY user_story.id
        """
        with self.session() as session:
            result = session.run(query)
            return [dict(record["user_story"]) for record in result]

    def get_unprocessed_user_stories(self) -> list[dict[str, Any]]:
        """Fetch user stories not yet assigned to a Bounded Context."""
        query = """
        MATCH (us:UserStory)
        WHERE NOT (us)-[:IMPLEMENTS]->(:BoundedContext)
        RETURN {
            id: us.id,
            role: us.role,
            action: us.action,
            benefit: us.benefit,
            priority: us.priority,
            status: us.status,
            acceptanceCriteria: coalesce(us.acceptanceCriteria, []),
            criteriaUserEdited: coalesce(us.criteriaUserEdited, false)
        } as user_story
        ORDER BY us.priority DESC, us.id
        """
        with self.session() as session:
            result = session.run(query)
            return [dict(record["user_story"]) for record in result]

    def get_user_stories_by_bc(self, bc_id: str) -> list[dict[str, Any]]:
        """Fetch user stories assigned to a specific Bounded Context."""
        query = """
        MATCH (us:UserStory)-[:IMPLEMENTS]->(bc:BoundedContext {id: $bc_id})
        RETURN {
            id: us.id,
            role: us.role,
            action: us.action,
            benefit: us.benefit,
            priority: us.priority,
            status: us.status,
            acceptanceCriteria: coalesce(us.acceptanceCriteria, []),
            criteriaUserEdited: coalesce(us.criteriaUserEdited, false)
        } as user_story
        ORDER BY us.id
        """
        with self.session() as session:
            result = session.run(query, bc_id=bc_id)
            return [dict(record["user_story"]) for record in result]

    def create_user_story(
        self,
        id: str,
        role: str,
        action: str,
        benefit: str | None = None,
        priority: str = "medium",
        status: str = "draft",
        ui_description: str = "",
        display_name: str | None = None,
        source_screen_name: str | None = None,
        source_unit_id: str | None = None,
        sequence: int | None = None,
        acceptance_criteria: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new user story. Uses MERGE to prevent duplicates by id.

        ``acceptance_criteria``: optional list of strings persisted as
        ``acceptanceCriteria``. This path does NOT set ``criteriaUserEdited``
        (creation-time criteria are treated as freshly seeded; only
        post-creation manual edits via ``update_user_story`` constitute the
        "user has curated this" signal).
        """
        # name: "role: action (truncated)" 형태로 자동 생성
        name = f"{role}: {action[:60]}" if action else f"{role}: (no action)"
        criteria = _criteria_clean(acceptance_criteria) if acceptance_criteria is not None else None
        query = """
        MERGE (us:UserStory {id: $id})
        ON CREATE SET us.name = $name,
                      us.role = $role,
                      us.action = $action,
                      us.benefit = $benefit,
                      us.priority = $priority,
                      us.status = $status,
                      us.uiDescription = $ui_description,
                      us.displayName = $display_name,
                      us.sourceScreenName = $source_screen_name,
                      us.sourceUnitId = $source_unit_id,
                      us.sequence = $sequence,
                      us.acceptanceCriteria = CASE WHEN $acceptance_criteria IS NOT NULL THEN $acceptance_criteria ELSE [] END,
                      us.createdAt = datetime()
        ON MATCH SET us.name = CASE WHEN us.name IS NULL THEN $name ELSE us.name END,
                     us.role = CASE WHEN $role IS NOT NULL AND $role <> '' THEN $role ELSE us.role END,
                     us.action = CASE WHEN $action IS NOT NULL AND $action <> '' THEN $action ELSE us.action END,
                     us.benefit = CASE WHEN $benefit IS NOT NULL AND $benefit <> '' THEN $benefit ELSE us.benefit END,
                     us.priority = CASE WHEN $priority IS NOT NULL AND $priority <> '' THEN $priority ELSE us.priority END,
                     us.status = CASE WHEN $status IS NOT NULL AND $status <> '' THEN $status ELSE us.status END,
                     us.uiDescription = CASE WHEN $ui_description IS NOT NULL AND $ui_description <> '' THEN $ui_description ELSE us.uiDescription END,
                     us.displayName = CASE WHEN $display_name IS NOT NULL AND $display_name <> '' THEN $display_name ELSE us.displayName END,
                     us.sourceScreenName = CASE WHEN $source_screen_name IS NOT NULL AND $source_screen_name <> '' THEN $source_screen_name ELSE us.sourceScreenName END,
                     us.sourceUnitId = CASE WHEN $source_unit_id IS NOT NULL AND $source_unit_id <> '' THEN $source_unit_id ELSE us.sourceUnitId END,
                     us.sequence = CASE WHEN $sequence IS NOT NULL THEN $sequence ELSE us.sequence END,
                     us.acceptanceCriteria = CASE
                         WHEN $acceptance_criteria IS NOT NULL AND NOT coalesce(us.criteriaUserEdited, false) THEN $acceptance_criteria
                         ELSE us.acceptanceCriteria
                     END,
                     us.updatedAt = datetime()
        RETURN us {.id, .name, .role, .action, .benefit, .priority, .status, .sequence,
                   uiDescription: us.uiDescription, displayName: us.displayName,
                   sourceScreenName: us.sourceScreenName, sourceUnitId: us.sourceUnitId,
                   acceptanceCriteria: coalesce(us.acceptanceCriteria, []),
                   criteriaUserEdited: coalesce(us.criteriaUserEdited, false),
                   criteriaEditedAt: us.criteriaEditedAt} as user_story
        """
        with self.session() as session:
            result = session.run(
                query,
                id=id,
                name=name,
                role=role,
                action=action,
                benefit=benefit,
                priority=priority,
                status=status,
                ui_description=ui_description,
                display_name=display_name or "",
                source_screen_name=source_screen_name or "",
                source_unit_id=source_unit_id or "",
                sequence=sequence,
                acceptance_criteria=criteria,
            )
            record = result.single()
            if record is None:
                raise ValueError(f"create_user_story query returned no result for id={id}")
            user_story_dict = dict(record["user_story"])
            if not user_story_dict or not user_story_dict.get("id"):
                raise ValueError(f"create_user_story returned invalid result for id={id}: {user_story_dict}")
            return user_story_dict

    def update_user_story(
        self,
        user_story_id: str,
        *,
        role: str | None = None,
        action: str | None = None,
        benefit: str | None = None,
        priority: str | None = None,
        status: str | None = None,
        acceptance_criteria: list[str] | None = None,
        acceptance_criteria_present: bool = False,
    ) -> dict[str, Any] | None:
        """Partial-update a UserStory. Only fields whose argument is non-None
        are touched. ``acceptance_criteria_present`` distinguishes "criteria
        not in payload" from "criteria explicitly set to empty list" — when
        ``True``, ``criteriaUserEdited`` is flipped to true and
        ``criteriaEditedAt`` is set, even if the resulting list is empty.

        Returns ``None`` if the UserStory id is not found; callers should
        translate that to an HTTP 404.
        """
        criteria = _criteria_clean(acceptance_criteria) if acceptance_criteria_present else None
        query = """
        MATCH (us:UserStory {id: $user_story_id})
        SET us.role = CASE WHEN $role IS NOT NULL THEN $role ELSE us.role END,
            us.action = CASE WHEN $action IS NOT NULL THEN $action ELSE us.action END,
            us.benefit = CASE WHEN $benefit IS NOT NULL THEN $benefit ELSE us.benefit END,
            us.priority = CASE WHEN $priority IS NOT NULL THEN $priority ELSE us.priority END,
            us.status = CASE WHEN $status IS NOT NULL THEN $status ELSE us.status END,
            us.acceptanceCriteria = CASE WHEN $criteria_present THEN $criteria ELSE us.acceptanceCriteria END,
            us.criteriaUserEdited = CASE WHEN $criteria_present THEN true ELSE coalesce(us.criteriaUserEdited, false) END,
            us.criteriaEditedAt = CASE WHEN $criteria_present THEN datetime() ELSE us.criteriaEditedAt END,
            us.updatedAt = datetime()
        RETURN us {.id, .name, .role, .action, .benefit, .priority, .status, .sequence,
                   uiDescription: us.uiDescription, displayName: us.displayName,
                   sourceScreenName: us.sourceScreenName, sourceUnitId: us.sourceUnitId,
                   acceptanceCriteria: coalesce(us.acceptanceCriteria, []),
                   criteriaUserEdited: coalesce(us.criteriaUserEdited, false),
                   criteriaEditedAt: us.criteriaEditedAt} as user_story
        """
        with self.session() as session:
            result = session.run(
                query,
                user_story_id=user_story_id,
                role=role,
                action=action,
                benefit=benefit,
                priority=priority,
                status=status,
                criteria=criteria,
                criteria_present=acceptance_criteria_present,
            )
            record = result.single()
            if record is None:
                return None
            return dict(record["user_story"])
    
    def bulk_create_user_stories(
        self,
        rows: list[dict[str, Any]],
        *,
        session_id: str | None = None,
        phase: str | None = None,
    ) -> list[BulkResult]:
        """Persist user stories in batch — schema-equivalent to per-row
        `create_user_story` but using a single UNWIND transaction per chunk.

        Required input fields per row: `id`, `role`. Optional: `action`,
        `benefit`, `priority`, `status`, `ui_description`, `display_name`,
        `source_screen_name`, `source_unit_id`, `sequence`, `name`.
        """
        if not rows:
            return []
        normalized = [_normalize_user_story_row(r) for r in rows]
        results = bulk_flush(
            self.session,
            entity="user_story",
            rows=normalized,
            cypher=_USER_STORY_BULK_CYPHER,
            return_field="result",
            required_fields=["id", "role"],
            dedupe_key="id",
            session_id=session_id,
            phase=phase,
        )
        return reorder_to_input(rows, results, [])

    def bulk_set_user_story_sequence(
        self,
        rows: list[dict[str, Any]],
        *,
        session_id: str | None = None,
        phase: str | None = None,
    ) -> list[BulkResult]:
        """Batch-set `UserStory.sequence` from the user-story flow analysis.

        Required input fields per row: `us_id`, `sequence`.
        """
        if not rows:
            return []
        from ._bulk_helper import bulk_flush as _bulk_flush  # local re-import
        cypher = """
UNWIND $rows AS r
MATCH (us:UserStory {id: r.us_id})
SET us.sequence = r.sequence,
    us.updatedAt = datetime()
RETURN {us_id: us.id, sequence: us.sequence} AS result
"""
        return _bulk_flush(
            self.session,
            entity="user_story_sequence",
            rows=rows,
            cypher=cypher,
            return_field="result",
            required_fields=["us_id", "sequence"],
            dedupe_key=None,
            session_id=session_id,
            phase=phase,
        )

    def update_user_story_role_only(self, user_story_id: str, role: str) -> dict[str, Any]:
        """Update only the role field of an existing user story, preserving other fields."""
        query = """
        MATCH (us:UserStory {id: $user_story_id})
        SET us.role = $role,
            us.updatedAt = datetime()
        RETURN us {.id, .role, .action, .benefit, .priority, .status, uiDescription: us.uiDescription} as user_story
        """
        with self.session() as session:
            result = session.run(query, user_story_id=user_story_id, role=role)
            record = result.single()
            if not record:
                raise ValueError(f"User Story {user_story_id} not found")
            return dict(record["user_story"])


