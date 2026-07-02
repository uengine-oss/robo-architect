from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger

SCHEMA_VERSION = 1
SKILL_VERSION = "robo-proposal-v1"
RESUME_WINDOW = 20


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(data: Any) -> str:
    return json.dumps(data if data is not None else {}, ensure_ascii=False)


def _parse(raw: Any, default: Any) -> Any:
    if raw is None:
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return default


def _next_sequence(proposal_id: str) -> int:
    with get_session() as session:
        rec = session.run(
            """
            MATCH (:Proposal {id:$proposalId})-[:HAS_INTERACTION]->(i:ProposalInteraction)
            RETURN coalesce(max(i.sequence), 0) AS seq
            """,
            proposalId=proposal_id,
        ).single()
    return int(rec.get("seq") or 0) + 1 if rec else 1


def record_interaction(
    proposal_id: str,
    *,
    phase: str,
    kind: str,
    status: str,
    payload: Any,
    artifact_ref: str | None = None,
) -> dict:
    interaction_id = f"PI-{uuid.uuid4().hex[:12]}"
    sequence = _next_sequence(proposal_id)
    created_at = _now()
    with get_session() as session:
        rec = session.run(
            """
            MATCH (p:Proposal {id:$proposalId})
            CREATE (i:ProposalInteraction {
              id:$id,
              proposalId:$proposalId,
              sequence:$sequence,
              phase:$phase,
              kind:$kind,
              status:$status,
              payload:$payload,
              artifactRef:$artifactRef,
              createdAt: datetime($createdAt),
              resolvedAt: null,
              skillVersion:$skillVersion,
              schemaVersion:$schemaVersion
            })
            MERGE (p)-[:HAS_INTERACTION]->(i)
            RETURN i {.*} AS interaction
            """,
            proposalId=proposal_id,
            id=interaction_id,
            sequence=sequence,
            phase=phase,
            kind=kind,
            status=status,
            payload=_json(payload),
            artifactRef=artifact_ref,
            createdAt=created_at,
            skillVersion=SKILL_VERSION,
            schemaVersion=SCHEMA_VERSION,
        ).single()
    if not rec:
        raise ValueError(f"Proposal {proposal_id} not found")
    interaction = _format_interaction(rec["interaction"])
    SmartLogger.log(
        "INFO",
        f"proposal interaction recorded: {proposal_id}/{kind}",
        category="proposal_lifecycle.interaction.recorded",
        params={"proposalId": proposal_id, "interactionId": interaction_id, "kind": kind, "status": status},
    )
    return interaction


def list_interactions(proposal_id: str, *, limit: int | None = None) -> list[dict]:
    limit_clause = "LIMIT $limit" if limit else ""
    params = {"proposalId": proposal_id}
    if limit:
        params["limit"] = limit
    with get_session() as session:
        rows = session.run(
            f"""
            MATCH (:Proposal {{id:$proposalId}})-[:HAS_INTERACTION]->(i:ProposalInteraction)
            RETURN i {{.*}} AS interaction
            ORDER BY i.sequence ASC
            {limit_clause}
            """,
            **params,
        )
        return [_format_interaction(r["interaction"]) for r in rows]


def get_interaction(interaction_id: str) -> dict | None:
    with get_session() as session:
        rec = session.run(
            "MATCH (i:ProposalInteraction {id:$id}) RETURN i {.*} AS interaction",
            id=interaction_id,
        ).single()
    return _format_interaction(rec["interaction"]) if rec else None


def recent_interactions(proposal_id: str, limit: int = RESUME_WINDOW) -> list[dict]:
    with get_session() as session:
        rows = session.run(
            """
            MATCH (:Proposal {id:$proposalId})-[:HAS_INTERACTION]->(i:ProposalInteraction)
            RETURN i {.*} AS interaction
            ORDER BY i.sequence DESC
            LIMIT $limit
            """,
            proposalId=proposal_id,
            limit=limit,
        )
        out = [_format_interaction(r["interaction"]) for r in rows]
    return list(reversed(out))


def pending_drafts(proposal_id: str) -> dict[str, Any]:
    with get_session() as session:
        rows = session.run(
            """
            MATCH (:Proposal {id:$proposalId})-[:HAS_INTERACTION]->(i:ProposalInteraction)
            WHERE i.kind = 'DRAFT' AND i.status = 'PENDING'
            RETURN i.phase AS phase, i.payload AS payload, i.createdAt AS createdAt
            ORDER BY i.sequence ASC
            """,
            proposalId=proposal_id,
        )
        drafts: dict[str, Any] = {}
        for row in rows:
            payload = _parse(row.get("payload"), {})
            artifact = payload.get("artifact") if isinstance(payload, dict) else payload
            if row.get("phase") and artifact is not None:
                drafts[row["phase"]] = artifact
        return drafts


def save_draft(proposal_id: str, phase: str, artifact: dict) -> dict:
    supersede_pending(proposal_id, kind="DRAFT", phase=phase)
    draft = record_interaction(
        proposal_id,
        phase=phase,
        kind="DRAFT",
        status="PENDING",
        payload={"artifact": artifact},
    )
    with get_session() as session:
        session.run(
            """
            MATCH (p:Proposal {id:$proposalId})
            SET p.pendingDraftId = $draftId,
                p.lifecycleStatus = 'READY_FOR_CONFIRM',
                p.currentPhase = $phase,
                p.resumeToken = $resumeToken,
                p.skillVersion = $skillVersion,
                p.schemaVersion = $schemaVersion
            """,
            proposalId=proposal_id,
            draftId=draft["id"],
            phase=phase,
            resumeToken=f"{proposal_id}:{draft['id']}",
            skillVersion=SKILL_VERSION,
            schemaVersion=SCHEMA_VERSION,
        )
    return draft


def confirm_draft(proposal_id: str, draft_id: str) -> dict | None:
    return _resolve(draft_id, "CONFIRMED")


def reject_draft(proposal_id: str, draft_id: str, reason: str | None = None) -> dict | None:
    interaction = _resolve(draft_id, "REJECTED", extra_payload={"reason": reason})
    if interaction:
        with get_session() as session:
            session.run(
                """
                MATCH (p:Proposal {id:$proposalId})
                SET p.pendingDraftId = null, p.lifecycleStatus = 'ACTIVE'
                """,
                proposalId=proposal_id,
            )
    return interaction


def record_question(proposal_id: str, phase: str, question: str, options: list[Any] | None = None) -> dict:
    supersede_pending(proposal_id, kind="QUESTION")
    interaction = record_interaction(
        proposal_id,
        phase=phase,
        kind="QUESTION",
        status="PENDING",
        payload={"question": question, "options": options or []},
    )
    with get_session() as session:
        session.run(
            """
            MATCH (p:Proposal {id:$proposalId})
            SET p.pendingQuestionId = $questionId,
                p.lifecycleStatus = 'WAITING_USER',
                p.currentPhase = $phase,
                p.resumeToken = $resumeToken,
                p.skillVersion = $skillVersion,
                p.schemaVersion = $schemaVersion
            """,
            proposalId=proposal_id,
            questionId=interaction["id"],
            phase=phase,
            resumeToken=f"{proposal_id}:{interaction['id']}",
            skillVersion=SKILL_VERSION,
            schemaVersion=SCHEMA_VERSION,
        )
    return interaction


def answer_question(proposal_id: str, question_id: str, answer: Any) -> dict:
    question = _resolve(question_id, "RESOLVED", extra_payload={"answer": answer})
    if question is None:
        raise ValueError(f"Question {question_id} not found")
    answer_interaction = record_interaction(
        proposal_id,
        phase=question.get("phase") or "UNKNOWN",
        kind="ANSWER",
        status="RESOLVED",
        payload={"questionId": question_id, "answer": answer},
        artifact_ref=question_id,
    )
    with get_session() as session:
        session.run(
            """
            MATCH (p:Proposal {id:$proposalId})
            SET p.pendingQuestionId = null,
                p.lifecycleStatus = 'ACTIVE',
                p.resumeToken = $resumeToken
            """,
            proposalId=proposal_id,
            resumeToken=f"{proposal_id}:{answer_interaction['id']}",
        )
    return {"question": question, "answer": answer_interaction}


def supersede_pending(proposal_id: str, *, kind: str, phase: str | None = None) -> int:
    phase_clause = "AND i.phase = $phase" if phase else ""
    params = {"proposalId": proposal_id, "kind": kind}
    if phase:
        params["phase"] = phase
    with get_session() as session:
        rec = session.run(
            f"""
            MATCH (:Proposal {{id:$proposalId}})-[:HAS_INTERACTION]->(i:ProposalInteraction)
            WHERE i.kind = $kind AND i.status = 'PENDING' {phase_clause}
            SET i.status = 'SUPERSEDED', i.resolvedAt = datetime($resolvedAt)
            RETURN count(i) AS count
            """,
            resolvedAt=_now(),
            **params,
        ).single()
    return int(rec.get("count") or 0) if rec else 0


def resume_context(proposal_id: str) -> dict:
    with get_session() as session:
        rec = session.run(
            """
            MATCH (p:Proposal {id:$proposalId})
            OPTIONAL MATCH (p)-[:HAS_INTERACTION]->(pending:ProposalInteraction)
            WHERE pending.id IN [p.pendingQuestionId, p.pendingDraftId]
            RETURN p {.*} AS proposal, collect(pending {.*}) AS pending
            """,
            proposalId=proposal_id,
        ).single()
    if not rec:
        raise ValueError(f"Proposal {proposal_id} not found")
    return {
        "proposal": _format_mapping(dict(rec["proposal"])),
        "pending": [_format_interaction(i) for i in (rec.get("pending") or []) if i],
        "recentInteractions": recent_interactions(proposal_id),
        "draftArtifacts": pending_drafts(proposal_id),
    }


def _resolve(
    interaction_id: str,
    status: str,
    *,
    extra_payload: dict | None = None,
) -> dict | None:
    with get_session() as session:
        rec = session.run(
            """
            MATCH (i:ProposalInteraction {id:$id})
            WITH i, i.payload AS oldPayload
            SET i.status = $status, i.resolvedAt = datetime($resolvedAt)
            RETURN i {.*} AS interaction, oldPayload AS oldPayload
            """,
            id=interaction_id,
            status=status,
            resolvedAt=_now(),
        ).single()
    if not rec:
        return None
    interaction = _format_interaction(rec["interaction"])
    if extra_payload:
        payload = dict(interaction.get("payload") or {})
        payload.update(extra_payload)
        with get_session() as session:
            session.run(
                "MATCH (i:ProposalInteraction {id:$id}) SET i.payload=$payload",
                id=interaction_id,
                payload=_json(payload),
            )
        interaction["payload"] = payload
    return interaction


def _format_interaction(raw: dict) -> dict:
    out = _format_mapping(dict(raw))
    out["payload"] = _parse(out.get("payload"), {})
    return out


def _format_mapping(raw: dict) -> dict:
    out = dict(raw)
    for key in ("createdAt", "resolvedAt"):
        value = out.get(key)
        if value is not None:
            try:
                out[key] = value.isoformat()
            except Exception:
                out[key] = str(value)
    return out
