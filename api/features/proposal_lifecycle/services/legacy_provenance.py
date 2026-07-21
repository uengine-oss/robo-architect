"""Proposal 단계별 레거시 검색 후보와 실제 상세 검토 기록(spec 053).

``skill_runner``의 typed tool event를 toolUseId로 짝지어 interleaving에도 안전하게 수집한다.
검색 결과와 ``node_detail`` 검토는 서로 다른 사실로 저장한다.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from api.platform.legacy_tool_events import decode_event, is_event
from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger


def _extract_saved_path(error_text: str) -> str:
    """CLI 초대형 결과 안내문에서 실제 저장 파일 경로를 문구 비의존으로 찾는다."""
    import re

    tail = error_text.split("saved to", 1)[1].lstrip(" :").strip()
    for match in re.finditer(r"\.(?:txt|json|jsonl|md)", tail):
        candidate = tail[:match.end()].strip()
        if Path(candidate).exists():
            return candidate
    match = re.match(r"(.+?\.(?:txt|json|jsonl|md))(?=[\s.\"<]|$)", tail)
    if match:
        return match.group(1).strip()
    for stop in ("\n", "</", " Use ", " use "):
        if stop in tail:
            tail = tail.split(stop, 1)[0]
    return tail.strip().rstrip(".")


def _unwrap_result_envelope(text: str) -> str:
    # 실스트림에는 envelope 이 중첩되어 도착할 수 있다(evlink P0 실측: PRO-005 실패
    # rawHead 가 1회 unwrap 후에도 `{"result":"{\"node\":…` 였음). 벗길 때마다 문자열이
    # 엄격히 짧아지므로 고정점 루프는 항상 종료한다.
    while True:
        try:
            outer = json.loads(text)
        except ValueError:
            return text
        if isinstance(outer, dict) and isinstance(outer.get("result"), str):
            text = outer["result"]
            continue
        return text


def _tool_payload(content: str) -> tuple[dict, str]:
    """도구 text 또는 CLI file fallback을 JSON으로 복원한다. 실패 원문 머리도 돌려준다."""
    # Claude stream-json의 MCP tool_result는 analyzer가 반환한 JSON 문자열을
    # ``{"result":"<json string>"}``으로 한 번 감싼다. 파일 fallback뿐 아니라
    # 일반 인라인 응답도 같은 envelope 계약이므로 파싱 전에 항상 해제한다.
    payload = _unwrap_result_envelope(content)
    if "saved to" in payload and not payload.lstrip().startswith("{"):
        try:
            path = _extract_saved_path(payload)
            raw = Path(path).read_text(encoding="utf-8")
            payload = _unwrap_result_envelope(raw)
        except OSError as exc:
            SmartLogger.log(
                "WARN", f"oversized result file read failed: {exc}",
                category="proposal_lifecycle.provenance.file_fallback_failed",
            )
    try:
        decoded = json.loads(payload)
    except ValueError:
        SmartLogger.log(
            "WARN", "legacy provenance result parse failed",
            category="proposal_lifecycle.provenance.parse_failed",
            params={"size": len(payload)},
        )
        return {}, payload[:200]
    return decoded if isinstance(decoded, dict) else {}, payload[:200]


def _compact_nodes(clusters: list) -> list[dict]:
    out: list[dict] = []
    for cluster in clusters or []:
        for node in cluster.get("nodes", []):
            out.append({
                "id": node.get("id", ""),
                "name": node.get("name", ""),
                "physicalName": node.get("physical_name", ""),
                "label": node.get("label", ""),
                "summary": (node.get("summary") or "")[:120],
                "relevance": node.get("relevance", 0),
                "rulesCount": len(node.get("rules") or []),
            })
    return out


# 원문 코드 저장 상한 — 임의 프로젝트의 초대형 함수가 Proposal property 를 비대하게
# 만들지 않도록 한다(UI 미리보기 용도로 충분한 크기). 초과분은 명시적으로 표시.
_CODE_TEXT_MAX = 20_000


def _compact_source(source: dict | None) -> dict:
    if not isinstance(source, dict):
        return {}
    out = dict(source)
    code = out.get("code_text")
    if isinstance(code, str) and len(code) > _CODE_TEXT_MAX:
        out["code_text"] = code[:_CODE_TEXT_MAX] + "\n… (truncated)"
        out["code_text_truncated"] = True
    return out


def _compact_inspection(node_id: str, data: dict, raw_head: str) -> dict:
    if data.get("error"):
        error = data["error"]
        return {
            "nodeId": node_id,
            "ok": False,
            "error": {
                "code": str(error.get("code") or "DETAIL_FAILED") if isinstance(error, dict)
                else "DETAIL_FAILED",
                "message": str(error.get("message") or "detail lookup failed")[:200]
                if isinstance(error, dict) else str(error)[:200],
            },
        }
    node = data.get("node") if isinstance(data.get("node"), dict) else None
    if node is None:
        return {
            "nodeId": node_id,
            "ok": False,
            "error": {"code": "RESULT_PARSE_FAILED", "message": "node detail payload missing node"},
            "rawHead": raw_head,
        }
    properties = node.get("properties") or {}
    columns = node.get("columns") or []
    return {
        "nodeId": node_id,
        "ok": True,
        "name": node.get("name", ""),
        "label": next((label for label in node.get("labels", []) if label != "EMBEDDED"), ""),
        "logicalName": properties.get("logical_name", ""),
        "summary": (properties.get("summary") or "")[:120],
        "source": _compact_source(node.get("source")),
        "columns": [{
            "name": column.get("name", ""),
            "logicalName": column.get("logical_name", ""),
        } for column in columns],
    }


class ProvenanceCollector:
    """한 stage의 typed MCP request/result를 toolUseId로 짝지어 누적한다."""

    def __init__(self) -> None:
        self.entries: list[dict] = []
        self._pending: dict[str, dict] = {}

    def feed(self, line: str) -> dict | None:
        event = decode_event(line)
        tool_use_id = str(event["toolUseId"])
        if event["phase"] == "request":
            if tool_use_id in self._pending:
                SmartLogger.log(
                    "WARN", "duplicate legacy tool use id",
                    category="proposal_lifecycle.provenance.duplicate_tool_id",
                    params={"toolUseId": tool_use_id},
                )
            self._pending[tool_use_id] = event
            return None

        request = self._pending.pop(tool_use_id, None)
        if request is None:
            request = {"kind": event["kind"], "input": {}}
            SmartLogger.log(
                "WARN", "unpaired legacy tool result",
                category="proposal_lifecycle.provenance.unpaired_result",
                params={"toolUseId": tool_use_id},
            )
        data, raw_head = _tool_payload(str(event.get("content") or ""))
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        tool_input = request.get("input") or {}

        if event["kind"] == "search":
            entry = {
                "query": str(tool_input.get("query") or ""),
                "searchedNodes": _compact_nodes(data.get("clusters") or []),
                "inspections": [],
                "at": now,
            }
            if tool_input.get("database"):
                entry["database"] = str(tool_input["database"])
            if data.get("error"):
                entry["error"] = data["error"]
            if not entry["searchedNodes"] and "error" not in entry:
                entry["rawHead"] = raw_head
            self.entries.append(entry)
            return {"kind": "search", "entry": entry}

        inspection = _compact_inspection(str(tool_input.get("node_id") or ""), data, raw_head)
        if not self.entries:
            self.entries.append({
                "query": "", "searchedNodes": [], "inspections": [], "at": now,
                "error": {"code": "DETAIL_WITHOUT_SEARCH", "message": "detail called before search"},
            })
        self.entries[-1]["inspections"].append(inspection)
        return {"kind": "detail", "inspection": inspection, "entry": self.entries[-1]}

    def save(self, proposal_id: str, stage: str) -> None:
        if not self.entries:
            return
        with get_session() as session:
            row = session.run(
                "MATCH (p:Proposal {id: $id}) RETURN p.legacyReferences AS refs", id=proposal_id,
            ).single()
            try:
                existing = json.loads((row or {}).get("refs") or "[]")
            except ValueError:
                existing = []
            existing.append({"version": 2, "stage": stage, "retrieves": self.entries})
            session.run(
                "MATCH (p:Proposal {id: $id}) SET p.legacyReferences = $refs",
                id=proposal_id,
                refs=json.dumps(existing, ensure_ascii=False),
            )
        SmartLogger.log(
            "INFO", f"legacy provenance saved: {proposal_id} {stage}",
            category="proposal_lifecycle.provenance.saved",
            params={
                "proposalId": proposal_id,
                "stage": stage,
                "retrieves": len(self.entries),
                "searched": sum(len(entry["searchedNodes"]) for entry in self.entries),
                "inspected": sum(len(entry["inspections"]) for entry in self.entries),
            },
        )


__all__ = ["ProvenanceCollector", "_extract_saved_path", "is_event"]
