from __future__ import annotations

from typing import Any


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
        RETURN us {.id, .role, .action, .benefit, .priority, .status} as user_story
        ORDER BY us.priority DESC, us.id
        """
        with self.session() as session:
            result = session.run(query)
            return [dict(record["user_story"]) for record in result]

    def get_user_stories_by_bc(self, bc_id: str) -> list[dict[str, Any]]:
        """Fetch user stories assigned to a specific Bounded Context."""
        query = """
        MATCH (us:UserStory)-[:IMPLEMENTS]->(bc:BoundedContext {id: $bc_id})
        RETURN us {.id, .role, .action, .benefit, .priority, .status} as user_story
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
    ) -> dict[str, Any]:
        """Create a new user story. Uses MERGE to prevent duplicates by id."""
        query = """
        MERGE (us:UserStory {id: $id})
        ON CREATE SET us.role = $role,
                      us.action = $action,
                      us.benefit = $benefit,
                      us.priority = $priority,
                      us.status = $status,
                      us.uiDescription = $ui_description,
                      us.createdAt = datetime()
        ON MATCH SET us.role = CASE WHEN $role IS NOT NULL AND $role <> '' THEN $role ELSE us.role END,
                     us.action = CASE WHEN $action IS NOT NULL AND $action <> '' THEN $action ELSE us.action END,
                     us.benefit = CASE WHEN $benefit IS NOT NULL AND $benefit <> '' THEN $benefit ELSE us.benefit END,
                     us.priority = CASE WHEN $priority IS NOT NULL AND $priority <> '' THEN $priority ELSE us.priority END,
                     us.status = CASE WHEN $status IS NOT NULL AND $status <> '' THEN $status ELSE us.status END,
                     us.uiDescription = CASE WHEN $ui_description IS NOT NULL AND $ui_description <> '' THEN $ui_description ELSE us.uiDescription END,
                     us.updatedAt = datetime()
        RETURN us {.id, .role, .action, .benefit, .priority, .status, uiDescription: us.uiDescription} as user_story
        """
        with self.session() as session:
            result = session.run(
                query,
                id=id,
                role=role,
                action=action,
                benefit=benefit,
                priority=priority,
                status=status,
                ui_description=ui_description,
            )
            record = result.single()
            if record is None:
                raise ValueError(f"create_user_story query returned no result for id={id}")
            user_story_dict = dict(record["user_story"])
            if not user_story_dict or not user_story_dict.get("id"):
                raise ValueError(f"create_user_story returned invalid result for id={id}: {user_story_dict}")
            return user_story_dict
    
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


