"""D-5 ⑰ — 프로포절이 만든 UI 에 와이어프레임을 붙인다(Accept 뒤, **단추로**).

Accept 는 `(:UI {proposalSource: <pid>})` 를 만들지만 `template` 은 스킬 계약에서 선택이라
대개 비어 있다 → 캔버스 UINode 가 "No wireframe" 을 찍는다. 그리고 생성기를 부르는 곳이
프로포절 경로에 없었다.

새 생성기를 짜지 않는다 — 인스펙터와 같은 `ai_design.html_template.generate_html_template`
를 UI 마다 돌린다. LLM 호출이 UI 수만큼 들므로 **자동이 아니라 단추**다.
진행률 이벤트는 Figma 소급 동기화(spec 020) 스트림과 **같은 이름·모양**을 쓴다
(`progress` · `ui_generated` · `ui_failed` · `done`) — 프런트가 같은 방식으로 읽는다.
중지 = 클라이언트가 EventSource 를 닫는다(진행 중인 한 건은 끝까지 가고, 다음 건은 안 간다).
"""

from __future__ import annotations

import json
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


def list_proposal_uis(proposal_id: str) -> list[dict[str, Any]] | None:
    """이 프로포절이 만든 UI 목록. Proposal 이 없으면 None."""
    with get_session() as session:
        exists = session.run(
            "MATCH (p:Proposal {id: $id}) RETURN p.id AS id", id=proposal_id,
        ).single()
        if not exists:
            return None
        rows = session.run(
            """
            MATCH (u:UI {proposalSource: $pid})
            RETURN u.id AS id,
                   coalesce(u.displayName, u.name, '') AS displayName,
                   u.template AS template
            ORDER BY coalesce(u.displayName, u.name), u.id
            """,
            pid=proposal_id,
        ).data()
    out = []
    for r in rows:
        tpl = r.get("template")
        out.append({
            "id": r.get("id"),
            "displayName": r.get("displayName") or r.get("id"),
            "hasWireframe": bool(isinstance(tpl, str) and tpl.strip()),
        })
    return out


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def stream_generate(proposal_id: str, uis: list[dict[str, Any]], *,
                          only_missing: bool = True, display_lang: str = "ko",
                          generate=None) -> AsyncGenerator[str, None]:
    """UI 마다 생성기를 차례로 돌리며 SSE 문자열을 낸다. 한 건 실패가 나머지를 막지 않는다."""
    if generate is None:
        from api.features.ai_design.html_template import generate_html_template as generate

    targets = [u for u in uis if not (only_missing and u.get("hasWireframe"))]
    summary = {"uisTotal": len(targets), "generated": 0, "failures": 0, "skippedExisting": len(uis) - len(targets)}
    yield _sse("progress", {"proposalId": proposal_id, "uisDone": 0, "uisTotal": len(targets), "currentTarget": None})

    for i, ui in enumerate(targets):
        yield _sse("progress", {"proposalId": proposal_id, "uisDone": i, "uisTotal": len(targets),
                                "currentTarget": ui["displayName"]})
        try:
            await generate(ui["id"], "", display_lang)
            summary["generated"] += 1
            yield _sse("ui_generated", {"proposalId": proposal_id, "uiId": ui["id"],
                                        "displayName": ui["displayName"]})
        except Exception as e:  # noqa: BLE001 — 한 건 실패는 기록하고 다음으로
            summary["failures"] += 1
            SmartLogger.log("WARNING", f"proposal ui wireframe failed: {ui['id']} {e}",
                            category="proposal_lifecycle.ui_wireframes.ui_failed",
                            params={"proposalId": proposal_id, "uiId": ui["id"]})
            yield _sse("ui_failed", {"proposalId": proposal_id, "uiId": ui["id"],
                                     "displayName": ui["displayName"], "lastErrorKr": str(e)})

    yield _sse("progress", {"proposalId": proposal_id, "uisDone": len(targets), "uisTotal": len(targets),
                            "currentTarget": None})
    summary["status"] = "partially-succeeded" if summary["failures"] else "succeeded"
    SmartLogger.log("INFO", f"proposal ui wireframes done: {proposal_id}",
                    category="proposal_lifecycle.ui_wireframes.done",
                    params={"proposalId": proposal_id, **summary})
    yield _sse("done", {"proposalId": proposal_id, "summary": summary})


@router.get("/{proposal_id}/ui-wireframes")
async def get_proposal_ui_wireframes(proposal_id: str):
    """이 프로포절이 만든 UI 와 와이어프레임 유무 — Accept 요약의 "UI N건" 단추가 쓴다."""
    uis = list_proposal_uis(proposal_id)
    if uis is None:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")
    return {
        "proposalId": proposal_id,
        "total": len(uis),
        "missing": sum(1 for u in uis if not u["hasWireframe"]),
        "uis": uis,
    }


@router.get("/stream/{proposal_id}/ui-wireframes")
async def stream_proposal_ui_wireframes(
    proposal_id: str,
    onlyMissing: bool = Query(True),
    lang: str = Query("ko"),
):
    """UI 와이어프레임 일괄 생성 SSE. `onlyMissing=false` 면 이미 있는 것도 다시 만든다."""
    uis = list_proposal_uis(proposal_id)
    if uis is None:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")
    return StreamingResponse(
        stream_generate(proposal_id, uis, only_missing=onlyMissing, display_lang=lang),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
