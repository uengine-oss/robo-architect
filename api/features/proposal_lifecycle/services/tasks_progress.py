"""
Proposal 구현 진행 추적 — 워크트리의 `PROPOSAL_<id>_TASKS.md`(speckit tasks 형식)를
읽어 체크박스 진행률을 산출한다. 셀(claude)이 작업을 완료할 때마다 `- [ ]`를
`- [x]`로 바꾸므로, 이 파일만 폴링하면 구현 진행 상황을 알 수 있다. (구현 탭 표시용)

헤드리스 완료 신호가 없는 인터랙티브 셀 구현(FR-007)에서, 파일 기반 진행 추적이
"멈췄는지/진행 중인지"를 가늠하는 가장 단순하고 안정적인 신호다.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

# `- [ ] ...`, `- [x] ...`, `* [X] ...` (선행 공백 허용 = 중첩 항목)
_CHECKBOX = re.compile(r"^\s*[-*]\s*\[([ xX])\]\s*(.+?)\s*$")
# 마크다운 헤더(섹션) — 가장 가까운 헤더를 항목의 phase로 본다.
_HEADER = re.compile(r"^\s*(#{1,6})\s+(.+?)\s*$")
# robo-tasks 마커: 진행률 표시에는 불필요하므로 텍스트에서 제거한다.
_ROBO_MARKER = re.compile(r"\s*<!--\s*@robo\b.*?-->\s*$")


def tasks_filename(proposal_id: str) -> str:
    return f"PROPOSAL_{proposal_id}_TASKS.md"


def parse_tasks_markdown(text: str) -> dict:
    """speckit tasks 마크다운에서 체크박스 진행률을 파싱한다."""
    items: list[dict] = []
    section: str | None = None
    for line in text.splitlines():
        h = _HEADER.match(line)
        if h:
            section = h.group(2).strip()
            continue
        m = _CHECKBOX.match(line)
        if m:
            done = m.group(1).lower() == "x"
            label = _ROBO_MARKER.sub("", m.group(2)).strip()
            items.append({"text": label, "done": done, "section": section})

    total = len(items)
    done = sum(1 for i in items if i["done"])

    # 섹션별 집계 (등장 순서 유지)
    sections: list[dict] = []
    index: dict[str, dict] = {}
    for it in items:
        key = it["section"] or "기타"
        bucket = index.get(key)
        if bucket is None:
            bucket = {"title": key, "total": 0, "done": 0}
            index[key] = bucket
            sections.append(bucket)
        bucket["total"] += 1
        if it["done"]:
            bucket["done"] += 1

    return {
        "exists": True,
        "total": total,
        "done": done,
        "percent": round(done * 100 / total) if total else 0,
        "items": items,
        "sections": sections,
    }


def read_progress(worktree_path: str | None, proposal_id: str) -> dict:
    """워크트리의 tasks 체크리스트를 읽어 진행률 + 갱신 시각(정체 판단용)을 반환한다."""
    empty = {
        "exists": False, "total": 0, "done": 0, "percent": 0,
        "items": [], "sections": [], "updatedAt": None, "secondsSinceUpdate": None,
        "file": tasks_filename(proposal_id),
    }
    if not worktree_path:
        return empty
    path = Path(worktree_path) / tasks_filename(proposal_id)
    if not path.is_file():
        return empty
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        stat = path.stat()
    except OSError:
        return empty

    result = parse_tasks_markdown(text)
    result["updatedAt"] = stat.st_mtime
    result["secondsSinceUpdate"] = max(0.0, time.time() - stat.st_mtime)
    result["file"] = tasks_filename(proposal_id)
    return result
