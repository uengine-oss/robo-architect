"""Feature Grouping Phase (spec 026 — requirements-tab).

Runs right after Bounded Context classification. For each BC, groups its
User Stories into `Feature` clusters via the LLM, then persists `Feature`
nodes plus `HAS_FEATURE` / `HAS_USER_STORY` relationships.

Non-clobber: `HAS_USER_STORY` relationships with `source='manual'` are never
overwritten — the planner's drag-n-drop placement survives re-ingest
(research R2 / data-model §1.5).
"""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

from pydantic import BaseModel, Field

from langchain_core.messages import HumanMessage, SystemMessage

from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.platform.observability.smart_logger import SmartLogger

PHASE_START = 50
PHASE_END = 56

_SYSTEM_PROMPT = (
    "You are a product analyst. You group user stories into cohesive "
    "Features within a single Bounded Context. A Feature is a set of "
    "related user stories that together deliver one user-facing capability."
)


class _FeatureGroup(BaseModel):
    feature_name: str = Field(description="Short feature name (a user-facing capability)")
    feature_description: str = Field(default="", description="One-sentence description")
    user_story_indices: list[int] = Field(
        default_factory=list, description="1-based indices of user stories in this feature"
    )


class _FeatureGroupingResult(BaseModel):
    features: list[_FeatureGroup] = Field(default_factory=list)


def _build_prompt(bc_name: str, stories: list[dict]) -> str:
    lines = [
        f'Bounded Context: "{bc_name}"',
        "",
        "User stories in this Bounded Context:",
    ]
    for i, us in enumerate(stories, start=1):
        role = us.get("role") or ""
        action = us.get("action") or ""
        benefit = us.get("benefit") or ""
        lines.append(f'{i}. As a {role}, I want {action}, so that {benefit}')
    n = len(stories)
    target = max(2, round(n / 4)) if n > 5 else 1
    lines += [
        "",
        f"Group these {n} user stories into Features. Every user story index "
        "MUST appear in exactly one feature. A Feature is one user-facing "
        "capability — group by the capability the stories serve, not by how "
        "many there are.",
        "Sizing rules (hard constraints):",
        "- Aim for 3-6 stories per feature.",
        f"- With {n} stories, produce roughly {target} feature(s).",
        "- NEVER put more than 8 stories in one feature.",
        "- NEVER collapse everything into a single feature when stories span "
        "distinct capabilities — distinct capabilities must be separate Features.",
        "- Do not create one feature per story either.",
    ]
    return "\n".join(lines)


async def feature_grouping_phase(
    ctx: IngestionWorkflowContext,
) -> AsyncGenerator[ProgressEvent, None]:
    """Group each BC's user stories into Feature clusters and persist them."""
    client = ctx.client
    session_id = getattr(ctx.session, "id", None)

    yield ProgressEvent(
        phase=IngestionPhase.GROUPING_FEATURES,
        message="🧩 User Story를 Feature 단위로 묶는 중...",
        progress=PHASE_START,
    )

    # Housekeeping — re-ingestion wipes session-scoped BoundedContexts but
    # Feature nodes are not session-tagged. If a prior run's BC was renamed,
    # its features are left orphaned. Drop them before re-grouping.
    try:
        pruned = client.prune_orphan_features()
        if pruned:
            SmartLogger.log(
                "INFO",
                f"Pruned {pruned} orphan feature(s) before grouping",
                category="agent.requirements.feature_grouping.prune",
                params={"session_id": session_id, "pruned": pruned},
            )
    except Exception as exc:  # noqa: BLE001 — housekeeping is best-effort
        SmartLogger.log(
            "WARN",
            f"Orphan-feature prune failed (non-fatal): {exc}",
            category="agent.requirements.feature_grouping.prune.error",
            params={"session_id": session_id, "error": str(exc)},
        )

    # Collect (bc, [user stories]) pairs from Neo4j (US linked via IMPLEMENTS).
    with client.session() as session:
        bc_rows = list(
            session.run(
                """
                MATCH (us:UserStory)-[:IMPLEMENTS]->(bc:BoundedContext)
                WITH bc, collect(us {.id, .role, .action, .benefit}) AS stories
                RETURN bc.id AS bcId, bc.key AS bcKey, bc.name AS bcName, stories
                ORDER BY bc.name
                """
            )
        )

    total_bc = len(bc_rows)
    features_created = 0
    links_created = 0

    SmartLogger.log(
        "INFO",
        f"Feature grouping started: {total_bc} bounded contexts",
        category="agent.requirements.feature_grouping.start",
        params={"session_id": session_id, "bc_count": total_bc},
    )

    for idx, row in enumerate(bc_rows):
        bc_id = row["bcId"]
        bc_key = row["bcKey"]
        bc_name = row["bcName"] or ""
        stories = [dict(s) for s in (row["stories"] or [])]
        if not stories:
            continue

        progress = PHASE_START + int((PHASE_END - PHASE_START) * (idx / max(total_bc, 1)))
        yield ProgressEvent(
            phase=IngestionPhase.GROUPING_FEATURES,
            message=f"🧩 '{bc_name}' Feature 분류 중... ({idx + 1}/{total_bc})",
            progress=progress,
        )

        try:
            structured_llm = ctx.llm.with_structured_output(_FeatureGroupingResult)
            result: _FeatureGroupingResult = await asyncio.wait_for(
                asyncio.to_thread(
                    structured_llm.invoke,
                    [
                        SystemMessage(content=_SYSTEM_PROMPT),
                        HumanMessage(content=_build_prompt(bc_name, stories)),
                    ],
                ),
                timeout=180.0,
            )
            groups = result.features or []
        except Exception as exc:  # noqa: BLE001 — degrade to one feature per BC
            SmartLogger.log(
                "WARN",
                f"Feature grouping LLM failed for BC '{bc_name}': {exc}",
                category="agent.requirements.feature_grouping.error",
                params={"session_id": session_id, "bc_id": bc_id, "error": str(exc)},
            )
            groups = [
                _FeatureGroup(
                    feature_name=bc_name or "General",
                    feature_description="",
                    user_story_indices=list(range(1, len(stories) + 1)),
                )
            ]

        for seq, group in enumerate(groups, start=1):
            name = (group.feature_name or "").strip()
            if not name:
                continue
            feature = client.upsert_feature(
                bc_id=bc_id,
                bc_key=bc_key,
                name=name,
                description=group.feature_description or None,
                source="llm",
                sequence=seq,
                session_id=session_id,
            )
            if not feature:
                continue
            features_created += 1
            for one_based in group.user_story_indices or []:
                i = one_based - 1
                if 0 <= i < len(stories):
                    us_id = stories[i].get("id")
                    if us_id and client.link_user_story_to_feature(
                        us_id,
                        feature["id"],
                        source="llm",
                        confidence=0.8,
                        respect_manual=True,
                    ):
                        links_created += 1

    ctx.feature_grouping_summary = {
        "features_created": features_created,
        "user_story_links": links_created,
    }
    SmartLogger.log(
        "INFO",
        f"Feature grouping done: {features_created} features, {links_created} links",
        category="agent.requirements.feature_grouping.done",
        params={
            "session_id": session_id,
            "features_created": features_created,
            "user_story_links": links_created,
        },
    )

    yield ProgressEvent(
        phase=IngestionPhase.GROUPING_FEATURES,
        message=f"✅ Feature 분류 완료 ({features_created}개 Feature)",
        progress=PHASE_END,
        data={"features_created": features_created, "user_story_links": links_created},
    )
