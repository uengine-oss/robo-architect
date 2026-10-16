# -*- coding: utf-8 -*-
"""한 세션에서 **무엇이 빠졌는지** 모은다 (Q2 · ISS-28).

## 왜 필요한가

Q1 이 "몇 개가 저장되지 않았다" 까지는 말하게 했다. 그런데 **무엇이** 빠졌는지는
여전히 로그를 열어야 알 수 있다. 2026-10-15 실측에서는 한 세션에 오류 24건
(`pg_type` 충돌 11 · 교착 13)이 나면서 Policy 2 · ReadModel 1 · UserStory↔BC 링크 3 ·
Command 속성 8 이 조용히 빠졌는데, 화면은 초록색 "생성 완료" 였다(done12 §233).

## 어떻게 모으나 — **단계 코드를 건드리지 않는다**

빠지는 자리는 이미 전부 `SmartLogger.log(...)` 를 지난다. 그래서 단계마다
수집 코드를 심지 않고 **로거에 관찰자를 하나 붙여** 지나가는 것을 줍는다.
단계가 늘어도 따라다닐 필요가 없고, 기존 호출부를 하나도 고치지 않는다.

주의 둘.

* **`SmartLogger.log` 의 분류기(`_should_log`)보다 앞에서 줍는다.** 기본 최소 수준이
  `ERROR` 라 WARNING 은 파일에 안 남는데, 우리가 세야 하는 것 중에는
  `commands.emits_zero_final` 같은 WARNING 이 있다.
* **관찰자가 던지면 로깅이 죽는다.** 전부 삼킨다 — 기록을 위해 본업을 막지 않는다.
"""

from __future__ import annotations

import threading
from typing import Any

# 한 세션이 남길 수 있는 최대 항목. 폭주하는 단계가 있어도 메모리를 먹지 않는다.
MAX_ENTRIES = 300

# 이 말들이 분류(category)에 있으면 "빠졌다" 로 본다.
#
# `timeout` 은 2026-10-15 실행에서 **놓쳐서** 더했다. 그날 ERROR 12건 중 5건이
# `ingestion.llm.ui_wireframe.timeout` · `…us_sequencing.timeout` ·
# `…extract_commands.timeout` 이었는데 표식에 없어 세지 못했다. 시간이 다 돼서
# 못 만든 것도 **빠진 것**이다 — 사람에게는 같은 손실이다.
_SKIP_MARKERS = (
    "skip", "error", "exception", "failed", "fail",
    "timeout", "zero_final", "orphan",
)

# params 에서 이름을 찾을 때 먼저 보는 열쇠들.
_NAME_KEYS = (
    "name", "readmodel_name", "policy_name", "command_name", "event_name",
    "aggregate_name", "bc_name", "user_story_id", "us_id", "id",
    "readmodel_index", "policy_index", "aggregate_index",
)

_lock = threading.Lock()
_ledgers: dict[str, "SkipLedger"] = {}
_installed = False


class SkipLedger:
    """한 세션의 누락 기록."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.entries: list[dict[str, Any]] = []
        self.dropped = 0

    def record(self, level: str, category: str, message: str, params: dict | None) -> None:
        if len(self.entries) >= MAX_ENTRIES:
            self.dropped += 1
            return
        self.entries.append({
            "level": level,
            "category": category,
            "phase": _phase_of(category),
            "name": _name_of(params, message),
            "reason": _reason_of(message),
        })

    def summary(self) -> dict[str, Any]:
        """화면과 기록에 실을 모양. 빈 세션이면 빈 dict 를 준다."""
        if not self.entries:
            return {}
        by_phase: dict[str, int] = {}
        for e in self.entries:
            by_phase[e["phase"]] = by_phase.get(e["phase"], 0) + 1
        return {
            "total": len(self.entries) + self.dropped,
            "by_phase": dict(sorted(by_phase.items(), key=lambda kv: -kv[1])),
            # 화면에는 앞의 것만 보인다. 전부는 로그에 있다.
            "items": self.entries[:20],
            "dropped": self.dropped,
        }


def _phase_of(category: str) -> str:
    """`ingestion.workflow.policies.skip` → `policies`.

    마지막 칸이 늘 `skip` 인 것은 아니다 — `bc.link_exception` 처럼 **표식이 칸 안에
    섞여** 있다. 그래서 같은지가 아니라 **들어 있는지**로 걸러야 한다.
    """
    parts = [p for p in (category or "").split(".") if p]
    for p in reversed(parts):
        if p in ("ingestion", "workflow", "neo4j"):
            continue
        if any(m in p for m in _SKIP_MARKERS):
            continue
        return p
    return category or "unknown"


def _name_of(params: Any, message: str) -> str:
    if isinstance(params, dict):
        for key in _NAME_KEYS:
            v = params.get(key)
            if v not in (None, "", []):
                return str(v)[:80]
    return (message or "").strip()[:80]


def _reason_of(message: str) -> str:
    """로그 문장에서 원인만 뽑는다. `{message: deadlock detected}` 꼴이 흔하다."""
    text = message or ""
    marker = "{message: "
    i = text.find(marker)
    if i >= 0:
        j = text.find("}", i)
        if j > i:
            return text[i + len(marker):j][:120]
    return text.strip()[:120]


def start(session_id: str) -> "SkipLedger":
    """세션 기록을 연다. 같은 세션을 다시 열면 **새로 시작**한다."""
    _install_observer()
    ledger = SkipLedger(session_id)
    with _lock:
        _ledgers[session_id] = ledger
    return ledger


def get(session_id: str) -> "SkipLedger | None":
    with _lock:
        return _ledgers.get(session_id)


def finish(session_id: str) -> dict[str, Any]:
    """기록을 닫고 요약을 돌려준다."""
    with _lock:
        ledger = _ledgers.pop(session_id, None)
    return ledger.summary() if ledger else {}


def _observe(level: str, message: str, category: str | None, params: Any) -> None:
    if not category or not str(category).startswith("ingestion."):
        return
    if str(level).upper() not in ("WARN", "WARNING", "ERROR", "CRITICAL"):
        return
    cat = str(category)
    if not any(m in cat for m in _SKIP_MARKERS):
        return
    sid = params.get("session_id") if isinstance(params, dict) else None
    with _lock:
        if sid and sid in _ledgers:
            targets = [_ledgers[sid]]
        else:
            # session_id 를 안 실어 보내는 호출부가 있다. 열려 있는 기록이
            # 하나뿐이면 그쪽으로 돌린다 — 둘 이상이면 **버린다**(섞으면 거짓이 된다).
            targets = list(_ledgers.values()) if len(_ledgers) == 1 else []
    for t in targets:
        t.record(str(level).upper(), cat, str(message), params if isinstance(params, dict) else None)


def _install_observer() -> None:
    global _installed
    if _installed:
        return
    try:
        from api.platform.observability.smart_logger import SmartLogger

        SmartLogger.add_observer(_observe)
        _installed = True
    except Exception:  # noqa: BLE001 — 기록은 본업을 막지 않는다
        _installed = False
