"""ReadModel UI 분류 헬퍼 (spec 042 — US3).

`ui_wireframes.py`의 ReadModel UI 생성을 "ReadModel당 무조건 1 UI" → **3분류**로 바꾼다
(하이브리드 인제스천 한정). Command UI는 기존대로 "사람-조작(=policy-invoked 아님) command마다"
로 두므로(= task당 1~N UI 자연 허용) 여기서 다루지 않는다.

ReadModel 3분류:
  - `screen` — 사람이 보는 화면. 조회/검색 화면뿐 아니라 **업무 처리의 결과 화면**
               (이벤트 모델링의 …→ReadModel→UI 결과 뷰)도 포함 → **자체 UI 생성**
  - `inline` — 자체 화면이 아니라 다른 화면에 데이터로만 박힘 → 소비 화면에 role:'display' 부착
  - `system` — 시스템 내부에서만 소비(사람에게 안 보임) → UI 없음(레인의 FEEDS로만)

설계 원칙: LLM 판정은 `llm_invoke` 주입 가능(테스트 스텁). 신규 Neo4j 라벨/관계 0 —
`attach_*`는 기존 `ATTACHED_TO`에 `role` 속성만 추가.
"""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable, Optional

from pydantic import BaseModel


class ReadModelVerdict(BaseModel):
    # 'screen' | 'inline' | 'system'
    kind: str = "screen"
    rationale: str = ""


def _get(obj: Any, key: str, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


LlmInvoke = Callable[[str, str], Awaitable[str]]  # (system, user) -> raw text


async def _default_llm_invoke(system: str, user: str) -> str:
    from api.features.ai_design.wireframe_agent import invoke_sync_llm_with_backoff
    from api.platform.llm_messages import build_system_message
    from api.platform.env import get_llm_provider_model
    from langchain_core.messages import HumanMessage

    model = get_llm_provider_model()
    resp = await invoke_sync_llm_with_backoff(
        model, [build_system_message(system), HumanMessage(content=user)]
    )
    return getattr(resp, "content", str(resp))


def _parse_json(raw: str) -> dict:
    raw = (raw or "").strip()
    if "```" in raw:
        raw = raw.split("```")[1].lstrip("json").strip() if raw.count("```") >= 2 else raw
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        raw = raw[start : end + 1]
    try:
        return json.loads(raw)
    except Exception:
        return {}


_RM_SYS = (
    "너는 CQRS ReadModel(조회 결과)의 화면 설계자다. 이 조회 결과가 사용자에게 어떻게 "
    "나타나는지 셋 중 하나로 판정한다:\n"
    "- screen: 사람이 보는 '화면'이다. 조회/검색 화면(검색·목록·대시보드)뿐 아니라, "
    "업무 처리의 **결과 화면**(처리 결과·확인·상세를 사용자에게 보여주는 화면)도 screen이다.\n"
    "- inline: 자체 화면이 아니라 다른 화면 안에 작은 데이터(배지·요약)로만 박힌다.\n"
    "- system: 시스템 내부에서만 쓰이고 사람 화면엔 전혀 안 나타난다.\n"
    "결과/상세/상태를 사용자가 본다면 기본적으로 screen으로 본다.\n"
    'JSON만 출력: {"kind": "screen|inline|system", "rationale": "..."}'
)

_VALID_KINDS = ("screen", "inline", "system")


async def classify_readmodel(
    rm: Any, *, llm_invoke: Optional[LlmInvoke] = None
) -> ReadModelVerdict:
    """ReadModel을 screen / inline / system 으로 판정. 실패·불확실 시 보수적으로 'screen'
    (사용자가 보는 결과 화면을 누락하지 않도록 — 이벤트 모델링의 ReadModel→UI 결과 뷰)."""
    invoke = llm_invoke or _default_llm_invoke
    try:
        name = _get(rm, "name", "")
        desc = _get(rm, "description", "")
        queries = _get(rm, "query_keys", []) or []
        user = f"readmodel: {name}\ndesc: {desc}\nqueries: {queries}"
        data = _parse_json(await invoke(_RM_SYS, user))
        kind = str(data.get("kind", "")).strip()
        if kind not in _VALID_KINDS:
            kind = "screen"
        return ReadModelVerdict(kind=kind, rationale=str(data.get("rationale", "")))
    except Exception:
        return ReadModelVerdict(kind="screen", rationale="fallback: own result screen")


def attach_readmodel_display(session, ui_id: str, rm_id: str) -> None:
    """소비 화면(UI)에 ReadModel을 표시 데이터로 연결: (:UI)-[:ATTACHED_TO {role:'display'}]->(:ReadModel).
    신규 관계 아님 — 기존 ATTACHED_TO에 role 속성."""
    session.run(
        """
        MATCH (u:UI {id: $uid}), (rm:ReadModel {id: $rid})
        MERGE (u)-[r:ATTACHED_TO]->(rm)
        SET r.role = 'display'
        """,
        uid=ui_id,
        rid=rm_id,
    )


def attach_display_readmodels(session, session_id: str, rm_ids: list[str]) -> int:
    """'displayed' ReadModel들을 그 결과를 *생산하는* command의 화면(UI)에 role:'display'로 부착
    (UI 생성 후 1회). 경로(`PROMOTED_TO` 비의존 — 그 브리지는 후처리 훅에서 ui_wireframes
    단계 *이후*에 생기므로 여기서 쓰면 안 됨):
      ReadModel -HAS_CQRS->CQRSConfig-HAS_OPERATION->CQRSOperation-TRIGGERED_BY->Event
        <-EMITS- Command <-ATTACHED_TO- (u:UI)
    = 그 ReadModel을 만드는 Event를 발생시킨 Command의 화면. 소비 화면을 못 찾으면 부착 안 함
    (레인의 FEEDS로만 표시). 신규 라벨/관계 0 — 기존 ATTACHED_TO에 role 속성."""
    attached = 0
    for rid in rm_ids or []:
        rec = session.run(
            """
            MATCH (rm:ReadModel {id: $rid})-[:HAS_CQRS]->(:CQRSConfig)
                  -[:HAS_OPERATION]->(:CQRSOperation)-[:TRIGGERED_BY]->(:Event)
                  <-[:EMITS]-(:Command)<-[a:ATTACHED_TO]-(u:UI)
            WHERE a.role IS NULL OR a.role <> 'display'
            RETURN u.id AS uid LIMIT 1
            """,
            rid=rid,
        ).single()
        if rec and rec["uid"]:
            attach_readmodel_display(session, rec["uid"], rid)
            attached += 1
    return attached
