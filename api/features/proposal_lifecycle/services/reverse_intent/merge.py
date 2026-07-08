"""merge — 그룹별 StrategicDiff 를 합치며 중복 제거.

Aggregate 정체성 = 테이블이므로 그룹 간 겹침은 원칙상 없음. 상위 엔티티(BC/Feature/UserStory)는
제목 기준으로 dedup(다른 그룹이 같은 BC 를 낸 경우 통합). PoC 이식.
"""
from __future__ import annotations

_KEYS = ("epics", "features", "userStories", "processes")


def _strategic_of(data) -> dict:
    if not isinstance(data, dict):
        return {}
    if "strategicDiff" in data and isinstance(data["strategicDiff"], dict):
        return data["strategicDiff"]
    return data  # 이미 strategicDiff 형태일 수 있음


def merge_strategic_diffs(results: list[dict]) -> dict:
    """results: [{"table":.., "data": intent결과 dict|None}] → 합쳐진 strategicDiff."""
    combined: dict[str, list] = {k: [] for k in _KEYS}
    seen: dict[str, dict[str, int]] = {k: {} for k in _KEYS}  # title -> combined index

    for res in results:
        sd = _strategic_of(res.get("data"))
        table = res.get("table")
        for key in _KEYS:
            for entry in (sd.get(key) or []):
                if not isinstance(entry, dict):
                    continue
                title = (entry.get("entityTitle") or entry.get("name") or "").strip().lower()
                if title and title in seen[key]:
                    combined[key][seen[key][title]].setdefault("_sourceTables", [])
                    if table and table not in combined[key][seen[key][title]]["_sourceTables"]:
                        combined[key][seen[key][title]]["_sourceTables"].append(table)
                    continue
                e = dict(entry)
                e["_sourceTables"] = [table] if table else []
                if title:
                    seen[key][title] = len(combined[key])
                combined[key].append(e)
    combined["version"] = 1
    return combined


def count_summary(merged: dict) -> dict:
    return {k: len(merged.get(k, [])) for k in _KEYS}
