"""Feature node operations (026 — requirements-tab).

`Feature` is the grouping unit between BoundedContext(Epic) and UserStory.
This mixin provides MERGE-based upsert of Feature nodes plus the
`HAS_FEATURE` / `HAS_USER_STORY` relationship management used by both the
`feature_grouping` ingestion phase and the `/api/requirements` CRUD routes.

Non-clobber rule (data-model.md §1.5 / research R2): a `HAS_USER_STORY`
relationship with `source='manual'` is never overwritten by LLM
re-classification. Manual placement wins on re-ingest.
"""

from __future__ import annotations

from typing import Any

from api.platform.keys import feature_key as _feature_key


class FeatureOps:
    # =========================================================================
    # Feature upsert
    # =========================================================================

    def upsert_feature(
        self,
        *,
        bc_id: str,
        bc_key: str,
        name: str,
        description: str | None = None,
        source: str = "llm",
        sequence: int | None = None,
    ) -> dict[str, Any] | None:
        """MERGE a Feature node by its natural key and attach it to its BC.

        Returns the feature dict, or None if the BC does not exist.
        """
        key = _feature_key(bc_key, name)
        query = """
        MATCH (bc:BoundedContext {id: $bc_id})
        MERGE (f:Feature {key: $key})
          ON CREATE SET f.id = randomUUID(),
                        f.createdAt = datetime(),
                        f.source = $source
        SET f.name = $name,
            f.description = $description,
            f.boundedContextId = bc.id,
            f.sequence = $sequence,
            f.updatedAt = datetime()
        MERGE (bc)-[hf:HAS_FEATURE]->(f)
          ON CREATE SET hf.createdAt = datetime()
        RETURN f {.id, .key, .name, .description, .source, .boundedContextId} AS feature
        """
        with self.session() as session:
            rec = session.run(
                query,
                bc_id=bc_id,
                key=key,
                name=name,
                description=description,
                source=source,
                sequence=sequence,
            ).single()
            return dict(rec["feature"]) if rec else None

    def prune_orphan_features(self) -> int:
        """Delete Feature nodes not attached to any BoundedContext.

        Features MERGE on `bc_key + name` and are not session-scoped. A
        re-ingestion wipes the session's BoundedContexts; if a later run
        renames a BC, the old BC's features are left dangling (no
        `HAS_FEATURE` parent). Every feature-creation path attaches the
        node to its BC, so an unattached Feature is always stale — safe
        to remove. Run as housekeeping at the start of feature grouping.
        """
        query = """
        MATCH (f:Feature)
        WHERE NOT (:BoundedContext)-[:HAS_FEATURE]->(f)
        DETACH DELETE f
        RETURN count(f) AS pruned
        """
        with self.session() as session:
            rec = session.run(query).single()
            return int(rec["pruned"]) if rec else 0

    def link_user_story_to_feature(
        self,
        user_story_id: str,
        feature_id: str,
        *,
        source: str = "manual",
        confidence: float | None = None,
        respect_manual: bool = False,
    ) -> bool:
        """Attach a User Story to a Feature via HAS_USER_STORY.

        A User Story belongs to at most one Feature — any existing
        HAS_USER_STORY is detached first.

        When `respect_manual` is True (used by the ingestion phase), the link
        is skipped if the User Story already has a `source='manual'`
        HAS_USER_STORY relationship.
        """
        with self.session() as session:
            if respect_manual:
                guarded = session.run(
                    """
                    MATCH (us:UserStory {id: $us_id})<-[r:HAS_USER_STORY]-(:Feature)
                    WHERE r.source = 'manual'
                    RETURN count(r) AS c
                    """,
                    us_id=user_story_id,
                ).single()
                if guarded and guarded["c"] > 0:
                    return False

            rec = session.run(
                """
                MATCH (us:UserStory {id: $us_id})
                MATCH (f:Feature {id: $feature_id})
                OPTIONAL MATCH (us)<-[old:HAS_USER_STORY]-(:Feature)
                DELETE old
                MERGE (f)-[r:HAS_USER_STORY]->(us)
                  ON CREATE SET r.createdAt = datetime()
                SET r.source = $source, r.confidence = $confidence
                RETURN us.id AS us_id
                """,
                us_id=user_story_id,
                feature_id=feature_id,
                source=source,
                confidence=confidence,
            ).single()
            return rec is not None

    def detach_user_story_feature(self, user_story_id: str) -> None:
        """Remove any HAS_USER_STORY relationship for a User Story (unassign)."""
        with self.session() as session:
            session.run(
                """
                MATCH (:Feature)-[r:HAS_USER_STORY]->(us:UserStory {id: $us_id})
                DELETE r
                """,
                us_id=user_story_id,
            )

    # =========================================================================
    # Feature CRUD helpers
    # =========================================================================

    def get_feature(self, feature_id: str) -> dict[str, Any] | None:
        with self.session() as session:
            rec = session.run(
                """
                MATCH (f:Feature {id: $id})
                RETURN f {.id, .key, .name, .description, .source, .boundedContextId} AS feature
                """,
                id=feature_id,
            ).single()
            return dict(rec["feature"]) if rec else None

    def delete_feature(
        self, feature_id: str, *, disposition: str = "unassign"
    ) -> tuple[bool, list[str]]:
        """Delete a Feature node.

        disposition='unassign' — detach child User Stories (they survive,
        becoming unassigned). disposition='delete' — delete child User Stories
        and their relationships too.

        Returns (deleted, affected_user_story_ids).
        """
        with self.session() as session:
            exists = session.run(
                "MATCH (f:Feature {id: $id}) RETURN f.id AS id", id=feature_id
            ).single()
            if not exists:
                return False, []

            affected = [
                r["id"]
                for r in session.run(
                    """
                    MATCH (f:Feature {id: $id})-[:HAS_USER_STORY]->(us:UserStory)
                    RETURN us.id AS id
                    """,
                    id=feature_id,
                )
            ]

            if disposition == "delete":
                session.run(
                    """
                    MATCH (f:Feature {id: $id})-[:HAS_USER_STORY]->(us:UserStory)
                    DETACH DELETE us
                    """,
                    id=feature_id,
                )
            session.run(
                "MATCH (f:Feature {id: $id}) DETACH DELETE f", id=feature_id
            )
            return True, affected
