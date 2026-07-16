"""레거시 참조 프로버넌스 수집기 (spec 052).

skill_runner 가 robo-cluster(cluster_retrieve) 호출 시에만 흘리는 마커 라인을 소비해
"이 스테이지가 실제로 어떤 레거시 노드를 참조했나"를 **결정론 기록**으로 만든다
(LLM 재량 산문 인용과 무관 — 호출이 있었으면 무조건 기록, 없었으면 빈 배열).

마커 프로토콜(skill_runner 발신):
    LEGACYQ::{tool_input json — query, database?}
    LEGACYREF::<cluster_retrieve 결과 텍스트(JSON, 라인 평탄화됨)>

저장: Proposal 노드 속성 ``legacyReferences`` (JSON 문자열, 스테이지별 append) —
기존 clarificationLog/stageArtifacts 와 동일한 저장 관례.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger

MARK_QUERY = "LEGACYQ::"
MARK_RESULT = "LEGACYREF::"


def _extract_saved_path(error_text: str) -> str:
    """CLI 초대형-결과 안내문에서 저장 파일 경로 추출.

    안내문 문구가 CLI 버전마다 다르다(실측 3종 — "... Use the Read tool", "<persisted-output>
    ...</persisted-output>", "... Format: JSON with schema ..."). 문장 구조에 의존하면 새
    문구마다 깨지므로, 'saved to' 뒤에서 **확장자로 끝나는 최단 경로**만 정규식으로 집는다.
    마커 평탄화로 개행이 사라진 한 줄 텍스트에서도 동작해야 한다.

    ★평탄화 함정(2026-07-16 라이브 실측): 개행 제거로 경로와 다음 문장이 공백 없이 붙는다
    ("...toolu_x.txtUse the Read tool..."). 문자 경계로는 파일명 연속과 구분 불가이므로,
    확장자 경계 후보를 앞에서부터 **실존 파일 검사**로 확정한다(자기검증 — 문구 비의존).
    """
    import re

    tail = error_text.split("saved to", 1)[1].lstrip(" :").strip()
    for m in re.finditer(r"\.(?:txt|json|jsonl|md)", tail):
        cand = tail[:m.end()].strip()
        if Path(cand).exists():
            return cand
    m = re.match(r"(.+?\.(?:txt|json|jsonl|md))(?=[\s.\"<]|$)", tail)
    if m:
        return m.group(1).strip()
    for stop in ("\n", "</", " Use ", " use "):   # 확장자 없는 예외 경로 — 종전 규칙 폴백
        if stop in tail:
            tail = tail.split(stop, 1)[0]
    return tail.strip().rstrip(".")


def _unwrap_result_envelope(text: str) -> str:
    """CLI 저장 파일은 {"result": "<도구 텍스트>"} 로 한 겹 포장됨(실측) — 내용물만 꺼낸다.
    포장이 아니면(이미 도구 텍스트 그대로면) 원문 반환."""
    try:
        outer = json.loads(text)
    except ValueError:
        return text
    if isinstance(outer, dict) and isinstance(outer.get("result"), str):
        return outer["result"]
    return text


def is_marker(line: str) -> bool:
    return line.startswith(MARK_QUERY) or line.startswith(MARK_RESULT)


def _compact_nodes(clusters: list) -> list[dict]:
    """cluster_retrieve 응답 → 노드 요약(칩 팝오버가 쓰는 최소 필드만)."""
    out: list[dict] = []
    for c in clusters or []:
        for n in c.get("nodes", []):
            out.append({
                "id": n.get("id", ""),
                "name": n.get("name", ""),
                "label": n.get("label", ""),
                "summary": (n.get("summary") or "")[:120],
                "relevance": n.get("relevance", 0),
                "rulesCount": len(n.get("rules") or []),
            })
    return out


class ProvenanceCollector:
    """스테이지 1회 실행분의 (query → nodes) 쌍 누적. 스트림 순서상 Q 다음 REF 가 온다."""

    def __init__(self) -> None:
        self.entries: list[dict] = []
        self._pending_query: str = ""
        self._pending_database: str = ""

    def feed(self, line: str) -> dict | None:
        """마커 라인 1개 소비. 완결된 항목(REF 도착)이면 그 항목을 반환(SSE 표면화용)."""
        if line.startswith(MARK_QUERY):
            try:
                q = json.loads(line[len(MARK_QUERY):])
            except ValueError:
                q = {}
            self._pending_query = str(q.get("query", ""))
            self._pending_database = str(q.get("database") or "")
            return None
        if line.startswith(MARK_RESULT):
            payload = line[len(MARK_RESULT):]
            # 초대형 결과 폴백: CLI 가 한도 초과 시 내용을 파일로 치우고 경로만 준다 —
            # 프로버넌스는 그 파일을 직접 읽어 **전량** 기록한다(사용자 원칙: 다 반영).
            # 트리거를 포맷-불문으로: JSON 이 아닌데 'saved to' 안내가 있으면 파일 폴백.
            if "saved to" in payload and not payload.lstrip().startswith("{"):
                try:
                    saved = _extract_saved_path(payload)
                    raw = "".join(Path(saved).read_text(encoding="utf-8").splitlines())
                    # 저장 파일은 {"result": "<도구 텍스트>"} 포장(실측) — 내용물만.
                    payload = _unwrap_result_envelope(raw)
                except OSError as e:
                    SmartLogger.log("WARN", f"oversized result file read failed: {e}",
                                    category="proposal_lifecycle.provenance.file_fallback_failed")
            try:
                data = json.loads(payload)
            except ValueError:
                SmartLogger.log("WARN", "legacy provenance result parse failed",
                                category="proposal_lifecycle.provenance.parse_failed",
                                params={"size": len(payload)})
                data = {}
            entry = {
                "query": self._pending_query,
                "nodes": _compact_nodes(data.get("clusters") or []),
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            if self._pending_database:
                entry["database"] = self._pending_database
            if isinstance(data, dict) and data.get("error"):
                entry["error"] = str(data["error"])[:200]
            if not entry["nodes"] and "error" not in entry:
                # 0건의 이유를 감사 가능하게 — 정상 0(빈 clusters)인지 형태 이상인지 원문 머리 보존.
                entry["raw_head"] = payload[:200]
            self._pending_query = ""
            self.entries.append(entry)
            return entry
        return None

    def save(self, proposal_id: str, stage: str) -> None:
        """스테이지 기록 append — 호출 0회여도 빈 스테이지 항목을 남기지 않는다(노이즈 금지)."""
        if not self.entries:
            return
        with get_session() as session:
            row = session.run(
                "MATCH (p:Proposal {id: $id}) RETURN p.legacyReferences AS refs", id=proposal_id
            ).single()
            try:
                existing = json.loads((row or {}).get("refs") or "[]")
            except ValueError:
                existing = []
            existing.append({"stage": stage, "retrieves": self.entries})
            session.run(
                "MATCH (p:Proposal {id: $id}) SET p.legacyReferences = $refs",
                id=proposal_id, refs=json.dumps(existing, ensure_ascii=False),
            )
        SmartLogger.log("INFO", f"legacy provenance saved: {proposal_id} {stage}",
                        category="proposal_lifecycle.provenance.saved",
                        params={"proposalId": proposal_id, "stage": stage,
                                "retrieves": len(self.entries),
                                "nodes": sum(len(e["nodes"]) for e in self.entries)})
