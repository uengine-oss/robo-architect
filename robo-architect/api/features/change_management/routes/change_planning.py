from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from starlette.requests import Request

from api.features.change_management.change_api_contracts import ChangePlanRequest
from api.platform.observability.request_logging import http_context, summarize_for_log
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.post("/plan")
async def generate_change_plan(payload: ChangePlanRequest, request: Request) -> dict[str, Any]:
    """
    Generate a change plan using LangGraph-based workflow.

    Returns:
    - scope, scopeReasoning, keywords, relatedObjects, changes, summary
    """
    from api.features.change_management.planning_agent.change_graph import run_change_planning

    try:
        SmartLogger.log(
            "INFO",
            "Generate change plan called: capturing full router inputs for reproducibility.",
            category="change.plan.inputs",
            params={**http_context(request), "inputs": summarize_for_log(payload.model_dump(by_alias=True))},
        )
        SmartLogger.log(
            "INFO",
            "Generate change plan requested",
            category="change.plan",
            params={
                "userStoryId": payload.userStoryId,
                "impactedNodes": len(payload.impactedNodes),
                "hasFeedback": bool(payload.feedback),
                "hasPreviousPlan": bool(payload.previousPlan),
            },
        )
        result = run_change_planning(
            user_story_id=payload.userStoryId,
            original_user_story=payload.originalUserStory or {},
            edited_user_story=payload.editedUserStory,
            connected_objects=payload.impactedNodes,
            feedback=payload.feedback,
            previous_plan=payload.previousPlan,
        )
        SmartLogger.log(
            "INFO",
            "Generate change plan completed",
            category="change.plan",
            params={
                "userStoryId": payload.userStoryId,
                "scope": result.get("scope"),
                "changes": len(result.get("changes") or []),
                "relatedObjects": len(result.get("relatedObjects") or []),
            },
        )

        try:
            propagation = result.get("propagation") or {}
            SmartLogger.log(
                "INFO",
                "Propagation summary: verify iterative impact expansion (rounds/stopReason/confirmed/review) from logs alone.",
                category="change.plan.propagation.summary",
                params={
                    **http_context(request),
                    "userStoryId": payload.userStoryId,
                    "enabled": propagation.get("enabled"),
                    "rounds": propagation.get("rounds"),
                    "stopReason": propagation.get("stopReason"),
                    "confirmed_count": len(propagation.get("confirmed") or []),
                    "review_count": len(propagation.get("review") or []),
                },
            )
        except Exception:
            pass

        return result

    except Exception as e:
        import traceback

        SmartLogger.log(
            "ERROR",
            "Failed to generate change plan",
            category="change.plan",
            params={
                **http_context(request),
                "userStoryId": getattr(payload, "userStoryId", None),
                "error": str(e),
                "traceback": traceback.format_exc(),
            },
        )
        raise HTTPException(status_code=500, detail=f"Failed to generate change plan: {str(e)}")


