"""인스펙터 저장 — 칸과 서버 허용 목록이 맞는지 · Property 대상을 옛 이름으로 찾는지 (2026-11-23).

현장(11-20): 수동으로 필드를 고쳐도 "Property 대상을 자동 보정할 수 없습니다". 로컬 점검에서
Command category · ReadModel actor/isMultipleResult 는 칸이 있는데 서버가 "field not allowed" 로
저장 전체를 거절했다.
"""
from __future__ import annotations

import re
from pathlib import Path

from api.features.model_modifier import model_change_application as m

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = ROOT / "frontend/src/features/canvas/ui/inspectors/nodeEditSchema.ts"


def _schema_keys() -> dict[str, set[str]]:
    """nodeEditSchema.ts 의 항목별 칸(key). CommonFields 는 name · displayName · description."""
    text = SCHEMA.read_text(encoding="utf-8")
    body = text[text.index("export const NodeEditSchemas"):]
    out: dict[str, set[str]] = {}
    cur = None
    for line in body.splitlines():
        mm = re.match(r"^  ([A-Za-z]+): \{", line)
        if mm:
            cur = mm.group(1)
            out[cur] = {"displayName", "description"} if "CommonFields" in body.split(f"  {cur}: {{", 1)[1].split("\n  }", 1)[0] else set()
            continue
        km = re.search(r"key: '([A-Za-z]+)'", line)
        if km and cur:
            out[cur].add(km.group(1))
    return out


def test_every_inspector_field_is_allowed_by_server():
    allowed = m._ALLOWED_UPDATE_FIELDS_BY_LABEL
    missing = {}
    for label, keys in _schema_keys().items():
        if label not in allowed:
            continue   # UserStory 등 이 경로로 저장하지 않는 항목
        lack = {k for k in keys if k != "name" and k not in allowed[label]}
        if lack:
            missing[label] = sorted(lack)
    assert missing == {}, f"인스펙터 칸인데 서버가 거절한다: {missing}"


def test_property_selector_prefers_old_name():
    upd = {"parentType": "Aggregate", "parentId": "agg1"}
    rename = {"action": "rename", "targetId": "prop-noid-2-a", "targetType": "Property",
              "targetName": "newName", "updates": {**upd, "oldName": "oldName"}}
    update = {"action": "update", "targetId": "prop-noid-2-a", "targetType": "Property",
              "targetName": "newName", "updates": {**upd, "type": "Long"}}
    batch = [rename, update]
    assert m._property_selector_names(rename, batch) == ["oldName"]
    assert m._property_selector_names(update, batch) == ["oldName", "newName"]
    update_with_own = {**update, "updates": {**upd, "oldName": "x"}}
    assert m._property_selector_names(update_with_own, [update_with_own]) == ["x", "newName"]
