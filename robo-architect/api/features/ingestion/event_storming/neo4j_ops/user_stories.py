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
        """Create a new user story."""
        query = """
        CREATE (us:UserStory {
            id: $id,
            role: $role,
            action: $action,
            benefit: $benefit,
            priority: $priority,
            status: $status,
            uiDescription: $ui_description
        })
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
            return dict(result.single()["user_story"])


