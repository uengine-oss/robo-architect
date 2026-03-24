"""
Figma UI Nodes -> User Stories

Business capability: transform Figma storyboard node data into a structured user story list.
The LLM analyzes UI element hierarchy (frames, buttons, inputs, text) to infer user stories.
Supports chunking by screen (top-level FRAME) for large storyboards.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Callable

from langchain_core.messages import HumanMessage, SystemMessage

from api.features.ingestion.ingestion_contracts import GeneratedUserStory, UserStoryList
from api.features.ingestion.ingestion_llm_runtime import get_llm
from api.platform.env import (
    AI_AUDIT_LOG_ENABLED,
    AI_AUDIT_LOG_FULL_OUTPUT,
    AI_AUDIT_LOG_FULL_PROMPT,
    get_llm_provider_model,
)
from api.platform.observability.request_logging import summarize_for_log
from api.platform.observability.smart_logger import SmartLogger


# Max screens per chunk (balance between context size and granularity)
MAX_SCREENS_PER_CHUNK = 5
# Max concurrent LLM calls for chunks
MAX_CONCURRENT_CHUNKS = 3


FIGMA_SYSTEM_PROMPT = """당신은 도메인 주도 설계(DDD) 전문가이자 UX 분석 전문가입니다.
Figma에서 추출된 UI 화면 구성요소 데이터를 분석하여 User Story를 추출하는 작업을 수행합니다.

**입력 데이터 형식:**
- 각 요소는 type(FRAME, TEXT, RECTANGLE, ELLIPSE 등), name(컴포넌트 이름), text(텍스트 내용), 크기, 부모-자식 관계 정보를 포함합니다.
- FRAME은 화면이나 컴포넌트 그룹을 나타냅니다.
- TEXT는 라벨, 버튼 텍스트, 제목 등 사용자에게 보여지는 텍스트입니다.
- 부모 ID가 없는 최상위 FRAME은 개별 화면(페이지)을 나타냅니다.

**분석 원칙:**
1. 각 화면의 구성요소(버튼, 입력 필드, 테이블, 네비게이션 등)를 분석하여 사용자가 수행할 수 있는 기능을 추론하세요.
2. 버튼 텍스트("로그인", "저장", "삭제", "검색" 등)에서 주요 액션을 식별하세요.
3. 입력 필드와 폼에서 데이터 입력/수정 기능을 식별하세요.
4. 테이블/리스트에서 조회/목록 기능을 식별하세요.
5. 네비게이션 구조에서 화면 간 이동과 메뉴 구조를 파악하세요.
6. 화면 이름(FRAME name)에서 비즈니스 도메인 맥락을 파악하세요.

**CRITICAL 원칙 (절대 준수):**
1. 각 기능을 반드시 개별 User Story로 변환하세요.
2. UI에서 관찰되는 모든 사용자 인터랙션을 User Story로 만드세요.
3. 추측은 UI 요소에 근거해야 합니다 - 화면에 없는 기능을 만들어내지 마세요.
4. role은 UI 맥락에서 추론하되, 구체적인 역할명을 사용하세요.
"""

FIGMA_EXTRACT_PROMPT = """분석할 Figma UI 화면 구성요소:

{figma_data}

---

위 Figma UI 요소 데이터를 분석하여 User Story 목록을 추출하세요.

지침:
1. 각 화면(최상위 FRAME)별로 어떤 기능이 있는지 분석
2. 버튼, 입력 필드, 테이블 등 인터랙티브 요소에서 기능 추론
3. "As a [role], I want to [action], so that [benefit]" 형식 사용
4. 역할(role)은 UI 맥락에서 구체적으로 추론 (예: customer, admin, manager 등)
5. 액션(action)은 명확한 동사로 시작
6. ui_description은 해당 화면의 UI 구성을 1문장으로 요약
7. ★ source_screen_name은 해당 User Story가 파생된 Figma 화면 이름(## 화면: 뒤의 이름)을 정확히 기입하세요. 하나의 US는 반드시 하나의 화면에 매핑되어야 합니다.

User Story ID는 US-001, US-002 형식으로 순차적으로 부여하세요.

★ 완전성 원칙: 화면에서 식별 가능한 모든 사용자 기능을 빠짐없이 추출하세요.
"""


# ---------------------------------------------------------------------------
# Node summarization
# ---------------------------------------------------------------------------

def _build_node_maps(nodes: list[dict]) -> tuple[dict[str | None, list[dict]], list[dict]]:
    """Build parent→children map and identify top-level frames."""
    children_map: dict[str | None, list[dict]] = {}
    for node in nodes:
        pid = node.get("parentId")
        children_map.setdefault(pid, []).append(node)

    top_frames = [n for n in nodes if n.get("type") == "FRAME" and not n.get("parentId")]
    if not top_frames:
        top_frames = [n for n in nodes if n.get("type") == "FRAME"]
    return children_map, top_frames


def _describe_node(node: dict, children_map: dict, depth: int = 0) -> list[str]:
    """Recursively describe a node and its children."""
    lines: list[str] = []
    indent = "  " * depth
    ntype = node.get("type", "UNKNOWN")
    name = node.get("name", "")
    text = node.get("text", "")
    w = node.get("width", 0)
    h = node.get("height", 0)
    visible = node.get("visible", True)

    if not visible:
        return lines

    desc_parts = [f"{indent}- [{ntype}]"]
    if name:
        desc_parts.append(f'"{name}"')
    if text and text != name:
        desc_parts.append(f'(텍스트: "{text}")')
    if w and h:
        desc_parts.append(f"({int(w)}x{int(h)})")
    lines.append(" ".join(desc_parts))

    nid = node.get("id")
    if nid and nid in children_map:
        for child in children_map[nid]:
            lines.extend(_describe_node(child, children_map, depth + 1))
    return lines


def _summarize_screens(frames: list[dict], children_map: dict) -> str:
    """Summarize a set of screens (top-level frames) and their children."""
    lines: list[str] = []
    for frame in frames:
        lines.append(f"\n## 화면: {frame.get('name', '(이름 없음)')}")
        lines.extend(_describe_node(frame, children_map, 0))
    return "\n".join(lines)


def _summarize_figma_nodes(nodes: list[dict]) -> str:
    """Summarize all Figma nodes into a readable text format for the LLM."""
    children_map, top_frames = _build_node_maps(nodes)
    if top_frames:
        return _summarize_screens(top_frames, children_map)
    # Fallback: no frames, list everything
    lines = ["\n## UI 요소 목록:"]
    for node in nodes:
        lines.extend(_describe_node(node, {}, 0))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Chunking by screen
# ---------------------------------------------------------------------------

def _chunk_screens(top_frames: list[dict], max_per_chunk: int = MAX_SCREENS_PER_CHUNK) -> list[list[dict]]:
    """Split top-level frames into chunks of max_per_chunk screens each."""
    chunks: list[list[dict]] = []
    for i in range(0, len(top_frames), max_per_chunk):
        chunks.append(top_frames[i : i + max_per_chunk])
    return chunks


# ---------------------------------------------------------------------------
# Single-chunk extraction
# ---------------------------------------------------------------------------

def _extract_from_summary(figma_summary: str, chunk_label: str = "") -> list[GeneratedUserStory]:
    """Run LLM extraction on a single figma summary text."""
    llm = get_llm(max_tokens=32768)
    structured_llm = llm.with_structured_output(UserStoryList)

    prompt = FIGMA_EXTRACT_PROMPT.format(figma_data=figma_summary)

    provider, model = get_llm_provider_model()
    label = f" ({chunk_label})" if chunk_label else ""
    if AI_AUDIT_LOG_ENABLED:
        SmartLogger.log(
            "INFO",
            f"Ingestion: extract user stories from Figma{label} - LLM invoke starting.",
            category="ingestion.llm.user_stories.figma.start",
            params={
                "llm": {"provider": provider, "model": model},
                "chunk_label": chunk_label,
                "summary_length": len(figma_summary),
                "prompt": prompt if AI_AUDIT_LOG_FULL_PROMPT else summarize_for_log(prompt),
            },
        )

    t_llm0 = time.perf_counter()
    response = structured_llm.invoke([
        SystemMessage(content=FIGMA_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])
    llm_ms = int((time.perf_counter() - t_llm0) * 1000)

    stories = getattr(response, "user_stories", []) or []
    if AI_AUDIT_LOG_ENABLED:
        SmartLogger.log(
            "INFO",
            f"Ingestion: extract user stories from Figma{label} - LLM invoke completed.",
            category="ingestion.llm.user_stories.figma.done",
            params={
                "llm": {"provider": provider, "model": model},
                "llm_ms": llm_ms,
                "chunk_label": chunk_label,
                "user_story_count": len(stories),
            },
        )

    fixed: list[GeneratedUserStory] = []
    for s in stories:
        sid = getattr(s, "id", "") or ""
        role = (getattr(s, "role", "") or "").strip()
        action = (getattr(s, "action", "") or "").strip()
        if not action:
            continue
        if not role:
            role = "user"
        fixed.append(
            GeneratedUserStory(
                id=sid,
                role=role,
                action=action,
                benefit=getattr(s, "benefit", "") or "",
                priority=getattr(s, "priority", "medium") or "medium",
                ui_description=getattr(s, "ui_description", "") or "",
                displayName=getattr(s, "displayName", None),
                source_screen_name=getattr(s, "source_screen_name", None),
            )
        )
    return fixed


# ---------------------------------------------------------------------------
# Public API (sync – called via asyncio.to_thread from workflow phase)
# ---------------------------------------------------------------------------

def extract_user_stories_from_figma(figma_nodes_json: str) -> list[GeneratedUserStory]:
    """
    Extract user stories from Figma node data using LLM.
    Single-shot for small storyboards (≤ MAX_SCREENS_PER_CHUNK screens).
    """
    nodes = json.loads(figma_nodes_json)
    figma_summary = _summarize_figma_nodes(nodes)
    return _extract_from_summary(figma_summary)


def extract_user_stories_from_figma_chunk(
    nodes: list[dict],
    screen_chunk: list[dict],
    children_map: dict,
    chunk_idx: int,
    total_chunks: int,
) -> list[GeneratedUserStory]:
    """
    Extract user stories from a single chunk of screens.
    Called from the async phase via asyncio.to_thread.
    """
    summary = _summarize_screens(screen_chunk, children_map)
    screen_names = [f.get("name", "?") for f in screen_chunk]
    label = f"chunk {chunk_idx + 1}/{total_chunks}: {', '.join(screen_names)}"
    print(f"[FIGMA CHUNK] Processing {label} ({len(summary)} chars)")
    return _extract_from_summary(summary, chunk_label=label)


def parse_and_chunk_figma_nodes(figma_nodes_json: str) -> tuple[list[dict], dict, list[list[dict]]]:
    """
    Parse figma nodes JSON and split into screen chunks.
    Returns (all_nodes, children_map, screen_chunks).
    """
    nodes = json.loads(figma_nodes_json)
    children_map, top_frames = _build_node_maps(nodes)

    if len(top_frames) <= MAX_SCREENS_PER_CHUNK:
        # No chunking needed
        return nodes, children_map, [top_frames]

    chunks = _chunk_screens(top_frames)
    print(
        f"[FIGMA CHUNK] {len(top_frames)} screens → {len(chunks)} chunks "
        f"(max {MAX_SCREENS_PER_CHUNK} screens/chunk)"
    )
    return nodes, children_map, chunks
