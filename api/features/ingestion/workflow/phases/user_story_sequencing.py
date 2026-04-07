"""
Phase: User Story Sequencing

전체 UserStory 추출 완료 후, LLM에 비즈니스 흐름 순서를 할당 요청.
요약본(역할+행위)만 전달하여 토큰 절감.
대규모 입력 시 청킹 처리: 이전 청크의 sequence 매핑을 다음 청크에 전달하여 정합성 유지.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.features.ingestion.workflow.utils.chunking import (
    calculate_chunk_progress,
    should_chunk_list,
    split_list_with_overlap,
)
from api.features.ingestion.workflow.utils.user_story_format import format_us_text
from api.platform.observability.smart_logger import SmartLogger


SEQUENCE_SYSTEM_PROMPT = """You are a business process analyst. Your task is to assign a time-based sequence order to user stories based on the natural business flow."""

SEQUENCE_PROMPT = """Assign a sequence number to each user story based on when it would occur in the overall business flow timeline.

Rules:
- Start from 1 (earliest in the business journey)
- User stories that happen at the same logical step share the same number
- Consider the natural user journey: onboarding → authentication → browsing → selection → order → payment → fulfillment → review → support
- Registration/signup comes before login
- Login comes before authenticated actions
- Browsing/search comes before purchase
- Order comes before payment
- Payment comes before delivery/fulfillment
- Main flow comes before exception handling (refund, complaint, etc.)

User Stories:
{user_stories_text}
{already_sequenced_section}
Return ONLY a JSON object mapping user story IDs to sequence numbers.
Example: {{"US-001": 1, "US-002": 2, "US-003": 2, "US-004": 3}}"""

# Chunking constants
_CHUNK_MAX_ITEMS = 80
_CHUNK_SIZE = 60
_CHUNK_OVERLAP = 5
_ACCUMULATED_SEQ_DETAIL_LIMIT = 30  # Show detailed entries only for this many
_ACCUMULATED_SEQ_BUDGET_TOKENS = 4000  # Max token budget for accumulated context


def _us_to_text(us: Any) -> str:
    return format_us_text(us, include_benefit=False, bullet_prefix="- ")


def _format_accumulated_sequences(
    accumulated: dict[str, int],
    overlap_us_ids: set[str] | None = None,
) -> str:
    """Format already-assigned sequences for prompt injection.

    Strategy to prevent accumulated context overflow:
    1. Always show overlap US in detail (LLM needs these for continuity)
    2. For the rest, show a compact range summary instead of listing every entry
    3. Hard cap: if the text exceeds _ACCUMULATED_SEQ_BUDGET_TOKENS, truncate
    """
    if not accumulated:
        return ""

    overlap_ids = overlap_us_ids or set()

    # Separate overlap entries (always detailed) from the rest
    overlap_entries = {k: v for k, v in accumulated.items() if k in overlap_ids}
    non_overlap = {k: v for k, v in accumulated.items() if k not in overlap_ids}

    lines: list[str] = []

    # 1) Summary statistics (always compact)
    seq_values = sorted(set(accumulated.values()))
    min_seq, max_seq = seq_values[0], seq_values[-1]
    lines.append(
        f"Total: {len(accumulated)} stories sequenced, "
        f"sequence range: {min_seq}–{max_seq}"
    )

    # 2) Sequence distribution (compact — how many stories per sequence number)
    from collections import Counter
    seq_counts = Counter(accumulated.values())
    dist_parts = [f"seq {s}: {c} stories" for s, c in sorted(seq_counts.items())]
    # Show at most 20 sequence groups
    if len(dist_parts) > 20:
        dist_text = ", ".join(dist_parts[:20]) + f" ... +{len(dist_parts) - 20} more"
    else:
        dist_text = ", ".join(dist_parts)
    lines.append(f"Distribution: {dist_text}")

    # 3) Overlap entries in detail (critical for continuity)
    if overlap_entries:
        lines.append("")
        lines.append("Recent stories (for continuity):")
        for us_id, seq in sorted(overlap_entries.items(), key=lambda x: x[1]):
            lines.append(f"- [{us_id}]: {seq}")

    # 4) Sample of non-overlap entries (only if budget allows)
    remaining_budget = _ACCUMULATED_SEQ_DETAIL_LIMIT - len(overlap_entries)
    if remaining_budget > 0 and non_overlap:
        sample_items = sorted(non_overlap.items(), key=lambda x: x[1])
        sample = sample_items[:remaining_budget]
        if sample:
            lines.append("")
            lines.append("Sample of earlier assignments:")
            for us_id, seq in sample:
                lines.append(f"- [{us_id}]: {seq}")
            if len(non_overlap) > remaining_budget:
                lines.append(f"... and {len(non_overlap) - remaining_budget} more")

    body = "\n".join(lines)

    # Hard cap: truncate if exceeding token budget
    from api.features.ingestion.workflow.utils.chunking import estimate_tokens
    if estimate_tokens(body) > _ACCUMULATED_SEQ_BUDGET_TOKENS:
        # Keep only summary + overlap
        truncated_lines = lines[:3]  # summary + distribution
        if overlap_entries:
            truncated_lines.append("")
            truncated_lines.append("Recent stories (for continuity):")
            for us_id, seq in sorted(overlap_entries.items(), key=lambda x: x[1]):
                truncated_lines.append(f"- [{us_id}]: {seq}")
        truncated_lines.append(f"\n(Showing summary only — {len(non_overlap)} earlier entries omitted for context efficiency)")
        body = "\n".join(truncated_lines)

    return (
        "\n## ALREADY SEQUENCED (from previous chunks)\n"
        "The following stories have already been assigned sequences. "
        "Continue numbering consistently with these — use the same sequence numbers "
        "for stories at the same business flow stage, and extend the numbering naturally.\n"
        + body
        + "\n"
    )


async def assign_user_story_sequences_phase(
    ctx: IngestionWorkflowContext,
) -> AsyncGenerator[ProgressEvent, None]:
    """
    Phase: UserStory 추출 후 비즈니스 흐름 순서 할당.
    대규모 입력 시 청킹 처리하여 컨텍스트 오버플로우 방지.
    """
    yield ProgressEvent(
        phase=IngestionPhase.EXTRACTING_USER_STORIES,
        message="User Story 순서 할당 중...",
        progress=22,
    )

    user_stories = ctx.user_stories or []
    if not user_stories:
        return

    needs_chunking = should_chunk_list(
        user_stories, item_to_text=_us_to_text, max_items=_CHUNK_MAX_ITEMS
    )

    if needs_chunking:
        mapping = await _sequencing_chunked(ctx, user_stories)
    else:
        mapping = await _sequencing_single(ctx, user_stories)

    if not mapping:
        return

    # Apply sequences to user stories and update Neo4j
    updated = 0
    for us in user_stories:
        us_id = getattr(us, "id", "")
        seq = mapping.get(us_id)
        if seq is not None:
            us.sequence = int(seq)
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(
                        _update_us_sequence, ctx, us_id, int(seq)
                    ),
                    timeout=5.0,
                )
                updated += 1
            except Exception:
                pass

    SmartLogger.log(
        "INFO",
        f"User Story sequences assigned: {updated}/{len(user_stories)}",
        category="ingestion.workflow.us_sequencing.done",
        params={
            "session_id": ctx.session.id,
            "total": len(user_stories),
            "updated": updated,
            "max_sequence": max(mapping.values()) if mapping else 0,
        },
    )

    yield ProgressEvent(
        phase=IngestionPhase.EXTRACTING_USER_STORIES,
        message=f"User Story 순서 할당 완료: {updated}개",
        progress=24,
    )


async def _sequencing_single(
    ctx: IngestionWorkflowContext,
    user_stories: list[Any],
) -> dict[str, int]:
    """단일 LLM 호출로 전체 시퀀싱 (기존 로직)."""
    lines = [_us_to_text(us) for us in user_stories]
    user_stories_text = "\n".join(lines)

    prompt = SEQUENCE_PROMPT.format(
        user_stories_text=user_stories_text,
        already_sequenced_section="",
    )

    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(
                ctx.llm.invoke,
                [
                    SystemMessage(content=SEQUENCE_SYSTEM_PROMPT),
                    HumanMessage(content=prompt),
                ],
            ),
            timeout=120.0,
        )
        return _parse_sequence_response(response)
    except asyncio.TimeoutError:
        SmartLogger.log(
            "ERROR",
            "User Story sequencing timed out",
            category="ingestion.workflow.us_sequencing.timeout",
            params={"session_id": ctx.session.id},
        )
        return {}
    except Exception as e:
        SmartLogger.log(
            "ERROR",
            f"User Story sequencing failed: {e}",
            category="ingestion.workflow.us_sequencing.error",
            params={"session_id": ctx.session.id, "error": str(e)},
        )
        return {}


async def _sequencing_chunked(
    ctx: IngestionWorkflowContext,
    user_stories: list[Any],
) -> dict[str, int]:
    """청킹 기반 시퀀싱. 이전 청크 결과를 다음 청크에 전달."""
    chunks = split_list_with_overlap(
        user_stories, chunk_size=_CHUNK_SIZE, overlap_count=_CHUNK_OVERLAP
    )
    total_chunks = len(chunks)

    SmartLogger.log(
        "INFO",
        f"User Story sequencing: chunking into {total_chunks} chunks "
        f"({len(user_stories)} stories, chunk_size={_CHUNK_SIZE})",
        category="ingestion.workflow.us_sequencing.chunking",
        params={
            "session_id": ctx.session.id,
            "total_stories": len(user_stories),
            "total_chunks": total_chunks,
        },
    )

    accumulated_sequences: dict[str, int] = {}

    for chunk_idx, chunk_stories in enumerate(chunks):
        lines = [_us_to_text(us) for us in chunk_stories]
        user_stories_text = "\n".join(lines)

        # Identify overlap US IDs (stories in this chunk that were already sequenced)
        chunk_us_ids = {getattr(us, "id", "") for us in chunk_stories}
        overlap_ids = chunk_us_ids & set(accumulated_sequences.keys())

        already_sequenced_section = _format_accumulated_sequences(
            accumulated_sequences, overlap_us_ids=overlap_ids
        )

        prompt = SEQUENCE_PROMPT.format(
            user_stories_text=user_stories_text,
            already_sequenced_section=already_sequenced_section,
        )

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    ctx.llm.invoke,
                    [
                        SystemMessage(content=SEQUENCE_SYSTEM_PROMPT),
                        HumanMessage(content=prompt),
                    ],
                ),
                timeout=120.0,
            )

            chunk_mapping = _parse_sequence_response(response)

            # Merge: 이전 청크의 값을 우선 (overlap 충돌 시)
            for us_id, seq in chunk_mapping.items():
                if us_id not in accumulated_sequences:
                    accumulated_sequences[us_id] = seq

            SmartLogger.log(
                "INFO",
                f"Sequencing chunk {chunk_idx + 1}/{total_chunks}: "
                f"{len(chunk_mapping)} mapped, total accumulated: {len(accumulated_sequences)}",
                category="ingestion.workflow.us_sequencing.chunk_done",
                params={
                    "session_id": ctx.session.id,
                    "chunk_index": chunk_idx,
                    "chunk_mapped": len(chunk_mapping),
                    "accumulated_total": len(accumulated_sequences),
                },
            )

        except asyncio.TimeoutError:
            SmartLogger.log(
                "ERROR",
                f"User Story sequencing chunk {chunk_idx + 1}/{total_chunks} timed out",
                category="ingestion.workflow.us_sequencing.chunk_timeout",
                params={"session_id": ctx.session.id, "chunk_index": chunk_idx},
            )
        except Exception as e:
            SmartLogger.log(
                "ERROR",
                f"User Story sequencing chunk {chunk_idx + 1}/{total_chunks} failed: {e}",
                category="ingestion.workflow.us_sequencing.chunk_error",
                params={"session_id": ctx.session.id, "chunk_index": chunk_idx, "error": str(e)},
            )

    return accumulated_sequences


def _parse_sequence_response(response: Any) -> dict[str, int]:
    """LLM 응답에서 {us_id: sequence} 매핑 파싱."""
    content = response.content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    mapping = json.loads(content)
    return {k: int(v) for k, v in mapping.items()}


def _update_us_sequence(ctx: IngestionWorkflowContext, us_id: str, sequence: int) -> None:
    """Update sequence on UserStory node in Neo4j."""
    with ctx.client.session() as session:
        session.run(
            "MATCH (us:UserStory {id: $id}) SET us.sequence = $seq, us.updatedAt = datetime()",
            id=us_id,
            seq=sequence,
        )
