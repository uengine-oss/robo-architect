"""Read-time non-retryable classifier for Figma sync failures (spec 020).

Pure function over (failure record, current binding, neo4j_view, in-flight set).
Keeps the failure store on `:UI {figmaSync*}` minimal — retryability is recomputed
on every History tab read so stale "non-retryable" classifications cannot exist.

Five non-retryable reasons (research D5):
  - 이전 바인딩            : failure's bindingFileKey ≠ current binding's
  - 대상 UI 가 삭제됨      : :UI no longer exists in graph
  - 대상 스토리보드가 보관됨 : owning storyboard's mapping is archived
  - 바인딩 해제됨          : binding.status == 'disconnected' (or no binding)
  - Figma 파일에 접근할 수 없음 : binding.status == 'unreachable'
"""

from __future__ import annotations

from typing import Any, TypedDict


class _NeoView(TypedDict, total=False):
    """Pre-fetched view of the graph state needed by the classifier.

    Caller (service.list_failures) batches a single Cypher round-trip to
    populate this for ALL failure rows at once.
    """

    ui_present: dict[str, bool]
    storyboard_archived: dict[str, bool]


def classify(
    *,
    failure: dict[str, Any],
    current_binding: dict[str, Any] | None,
    neo4j_view: _NeoView,
    in_flight: set[str],
) -> dict[str, Any]:
    """Return `{retryability, nonRetryableReason}` for one failure row.

    `failure` keys: uiId, figmaSyncBindingFileKey (optional, may be None).
    `current_binding` keys: figmaFileKey, status. None when no active binding.
    """
    ui_id = failure.get("uiId")

    if ui_id and ui_id in in_flight:
        return {"retryability": "in-flight", "nonRetryableReason": None}

    if not current_binding or current_binding.get("status") == "disconnected":
        return {"retryability": "non-retryable", "nonRetryableReason": "바인딩 해제됨"}

    if current_binding.get("status") == "unreachable":
        return {
            "retryability": "non-retryable",
            "nonRetryableReason": "Figma 파일에 접근할 수 없음",
        }

    # ":UI 가 더 이상 존재하지 않음"
    ui_present_map = neo4j_view.get("ui_present") or {}
    if ui_id and ui_id in ui_present_map and not ui_present_map[ui_id]:
        return {"retryability": "non-retryable", "nonRetryableReason": "대상 UI 가 삭제됨"}

    # "이전 바인딩": file key recorded on the :UI doesn't match the active binding's
    failure_key = failure.get("figmaSyncBindingFileKey")
    current_key = current_binding.get("figmaFileKey")
    if failure_key and current_key and failure_key != current_key:
        return {"retryability": "non-retryable", "nonRetryableReason": "이전 바인딩"}

    # "대상 스토리보드가 보관됨": owning storyboard archived
    sb_archived_map = neo4j_view.get("storyboard_archived") or {}
    if ui_id and ui_id in sb_archived_map and sb_archived_map[ui_id]:
        return {
            "retryability": "non-retryable",
            "nonRetryableReason": "대상 스토리보드가 보관됨",
        }

    return {"retryability": "retryable", "nonRetryableReason": None}
