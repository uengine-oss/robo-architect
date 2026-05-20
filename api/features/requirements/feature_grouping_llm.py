"""Natural-language requirement decomposition (026 — requirements-tab).

Backs `POST /api/requirements/user-story/propose`. Decomposes free-form text
into proposed User Stories and suggests a Bounded Context + Feature for each.
This step never mutates the graph — it only proposes (Constitution IV / R4).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from langchain_core.messages import HumanMessage, SystemMessage

from api.features.ingestion.ingestion_llm_runtime import get_llm
from api.features.requirements.requirements_contracts import (
    GenerationWarning,
    ProposedUserStory,
)
from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger

_SYSTEM_PROMPT = (
    "You are a requirements analyst. You convert free-form product notes into "
    "well-formed user stories (role / action / benefit) and classify each into "
    "the most fitting Bounded Context and Feature from the provided lists. "
    "If the input is too vague to form a user story, mark it unclear."
)


class _LLMProposal(BaseModel):
    role: str = ""
    action: str = ""
    benefit: str = ""
    bounded_context_name: str = Field(default="", description="Exact name from the BC list, or empty")
    feature_name: str = Field(default="", description="Exact name from the Feature list, or a new feature name")
    confidence: float = 0.5
    unclear: bool = False


class _LLMDecomposition(BaseModel):
    proposals: list[_LLMProposal] = Field(default_factory=list)


def _existing_context() -> tuple[list[dict], list[dict]]:
    with get_session() as session:
        bcs = [
            {"id": r["id"], "name": r["name"]}
            for r in session.run("MATCH (bc:BoundedContext) RETURN bc.id AS id, bc.name AS name")
        ]
        features = [
            {"id": r["id"], "name": r["name"], "bcId": r["bcId"]}
            for r in session.run(
                """
                MATCH (bc:BoundedContext)-[:HAS_FEATURE]->(f:Feature)
                RETURN f.id AS id, f.name AS name, bc.id AS bcId
                """
            )
        ]
    return bcs, features


def decompose_requirement(
    text: str, target_bc_id: Optional[str] = None
) -> tuple[list[ProposedUserStory], list[GenerationWarning]]:
    """Decompose NL text into proposed user stories. No graph mutation."""
    warnings: list[GenerationWarning] = []
    bcs, features = _existing_context()
    bc_by_name = {b["name"].strip().lower(): b for b in bcs}
    feature_by_name = {f["name"].strip().lower(): f for f in features}

    bc_list = "\n".join(f'- {b["name"]}' for b in bcs) or "(none)"
    feature_list = "\n".join(f'- {f["name"]}' for f in features) or "(none)"
    prompt = (
        f"Existing Bounded Contexts:\n{bc_list}\n\n"
        f"Existing Features:\n{feature_list}\n\n"
        f"Requirement text:\n{text}\n\n"
        "Decompose into one or more user stories."
    )

    try:
        structured = get_llm().with_structured_output(_LLMDecomposition)
        result: _LLMDecomposition = structured.invoke(
            [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
        llm_proposals = result.proposals or []
    except Exception as exc:  # noqa: BLE001
        SmartLogger.log(
            "WARN",
            f"Requirement decomposition LLM failed: {exc}",
            category="requirements.user_story.propose_error",
            params={"error": str(exc)},
        )
        return [], [GenerationWarning(code="requirement_unclear", message="요구사항 분해에 실패했습니다. 직접 입력해 주세요.")]

    proposals: list[ProposedUserStory] = []
    for lp in llm_proposals:
        if lp.unclear or not lp.action:
            warnings.append(
                GenerationWarning(
                    code="requirement_unclear",
                    message=f"입력이 모호하여 User Story로 분해하기 어렵습니다: \"{lp.action or text[:40]}\"",
                )
            )

        # Resolve BC: explicit target wins, else LLM name match.
        bc_id = target_bc_id
        if not bc_id and lp.bounded_context_name:
            match = bc_by_name.get(lp.bounded_context_name.strip().lower())
            bc_id = match["id"] if match else None
        if not bc_id:
            warnings.append(
                GenerationWarning(code="bc_unresolved", message="Bounded Context 자동 분류 실패 — 미분류로 둡니다.")
            )

        # Resolve Feature within the chosen BC.
        feature_id = None
        feature_name = lp.feature_name or None
        if lp.feature_name:
            fmatch = feature_by_name.get(lp.feature_name.strip().lower())
            if fmatch and (bc_id is None or fmatch["bcId"] == bc_id):
                feature_id = fmatch["id"]
        if lp.feature_name and not feature_id:
            warnings.append(
                GenerationWarning(
                    code="feature_unresolved",
                    message=f"'{lp.feature_name}' Feature가 없어 새로 만들거나 미분류로 둡니다.",
                )
            )

        proposals.append(
            ProposedUserStory(
                role=lp.role,
                action=lp.action,
                benefit=lp.benefit,
                suggestedBoundedContextId=bc_id,
                suggestedFeatureId=feature_id,
                suggestedFeatureName=feature_name,
                confidence=lp.confidence,
                unclear=bool(lp.unclear or not lp.action),
            )
        )

    return proposals, warnings
