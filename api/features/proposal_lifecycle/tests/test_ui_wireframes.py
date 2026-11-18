"""D-5 ⑰ — Accept 뒤 프로포절이 만든 UI 에 와이어프레임을 붙이는 단추(백엔드).

생성기(LLM)는 가짜로 바꾼다. 세션은 두 질의만 흉내 낸다.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager

import pytest
from fastapi import HTTPException

from api.features.ai_design import html_template
from api.features.proposal_lifecycle.routes import proposals_ui_wireframes as uw

PID = "PRO-031"
ROWS = [
    {"id": "ui-a", "displayName": "환불 신청", "template": None},
    {"id": "ui-b", "displayName": "환불 내역", "template": "<div class=\"wf-root\">x</div>"},
    {"id": "ui-c", "displayName": "", "template": "  "},
]


class _Res:
    def __init__(self, rec=None, rows=None):
        self._rec, self._rows = rec, rows or []

    def single(self):
        return self._rec

    def data(self):
        return self._rows


class _Sess:
    def __init__(self, exists=True):
        self.exists = exists
        self.queries: list[tuple[str, dict]] = []

    @contextmanager
    def __call__(self, *a, **k):
        yield self

    def run(self, q, **p):
        self.queries.append((" ".join(q.split()), p))
        if "MATCH (p:Proposal" in q:
            return _Res({"id": PID} if self.exists else None)
        assert p.get("pid") == PID
        return _Res(rows=ROWS)


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    monkeypatch.setattr(uw.SmartLogger, "log", lambda *a, **k: None)


def _events(chunks: list[str]) -> list[tuple[str, dict]]:
    out = []
    for c in chunks:
        ev = c.split("\n")[0].removeprefix("event: ")
        data = json.loads(c.split("\n")[1].removeprefix("data: "))
        out.append((ev, data))
    return out


def test_list_marks_missing_wireframes_and_queries_by_proposal_source(monkeypatch):
    sess = _Sess()
    monkeypatch.setattr(uw, "get_session", sess)
    out = asyncio.run(uw.get_proposal_ui_wireframes(PID))
    assert out["total"] == 3 and out["missing"] == 2
    assert [u["hasWireframe"] for u in out["uis"]] == [False, True, False]
    assert out["uis"][2]["displayName"] == "ui-c"  # 이름이 없으면 id
    assert any("UI {proposalSource: $pid}" in q for q, _ in sess.queries)


def test_list_404_when_proposal_missing(monkeypatch):
    monkeypatch.setattr(uw, "get_session", _Sess(exists=False))
    with pytest.raises(HTTPException) as e:
        asyncio.run(uw.get_proposal_ui_wireframes(PID))
    assert e.value.status_code == 404


def test_stream_generates_only_missing_and_survives_one_failure():
    calls: list[str] = []

    async def fake_generate(ui_id, instruction, lang):
        calls.append(ui_id)
        if ui_id == "ui-c":
            raise RuntimeError("LLM 호출 실패: 시간 초과")
        return "<div class=\"wf-root\"></div>"

    uis = [{"id": r["id"], "displayName": r["displayName"] or r["id"],
            "hasWireframe": bool((r["template"] or "").strip())} for r in ROWS]

    async def go():
        return [c async for c in uw.stream_generate(PID, uis, generate=fake_generate)]

    ev = _events(asyncio.run(go()))
    assert calls == ["ui-a", "ui-c"]  # ui-b 는 이미 있다
    names = [e for e, _ in ev]
    assert names.count("ui_generated") == 1 and names.count("ui_failed") == 1
    failed = next(d for e, d in ev if e == "ui_failed")
    assert failed["uiId"] == "ui-c" and "시간 초과" in failed["lastErrorKr"]
    done = ev[-1]
    assert done[0] == "done"
    assert done[1]["summary"] == {"uisTotal": 2, "generated": 1, "failures": 1,
                                  "skippedExisting": 1, "status": "partially-succeeded"}
    # 소급 동기화와 같은 진행률 모양
    prog = [d for e, d in ev if e == "progress"]
    assert prog[0]["uisDone"] == 0 and prog[-1]["uisDone"] == 2 and prog[-1]["uisTotal"] == 2


def test_stream_regenerates_all_when_only_missing_false():
    calls: list[str] = []

    async def fake_generate(ui_id, instruction, lang):
        calls.append((ui_id, instruction, lang))

    uis = [{"id": "ui-b", "displayName": "x", "hasWireframe": True}]

    async def go():
        return [c async for c in uw.stream_generate(PID, uis, only_missing=False,
                                                     display_lang="en", generate=fake_generate)]

    asyncio.run(go())
    assert calls == [("ui-b", "", "en")]


def test_html_template_prompt_uses_name_description_bc():
    sys_p, user_p, name = html_template.build_prompts(
        {"name": "refund-form", "displayName": "환불 신청", "description": "주문 번호·금액 입력",
         "bcName": "결제", "attachedToType": "Command", "attachedToName": "RequestRefund"},
    )
    assert name == "환불 신청"
    assert "Screen: 환불 신청" in user_p and "Bounded Context: 결제" in user_p
    assert "Description: 주문 번호·금액 입력" in user_p and "Command RequestRefund" in user_p
    assert "Korean" in sys_p


def test_html_template_not_found(monkeypatch):
    monkeypatch.setattr(html_template, "_load_ui_context", lambda _id: None)
    with pytest.raises(html_template.UINodeNotFound):
        asyncio.run(html_template.generate_html_template("ui-x"))


def test_inspector_html_edit_route_delegates_to_shared_generator(monkeypatch):
    """인스펙터 단추(/api/ai-design/html-edit)도 같은 생성기를 쓴다 — 응답 계약은 그대로."""
    from api.features.ai_design import router as ai_router

    seen = []

    async def fake(ui_id, instruction, lang):
        seen.append((ui_id, instruction, lang))
        if ui_id == "missing":
            raise html_template.UINodeNotFound("UI node missing not found")
        if ui_id == "llm-down":
            raise html_template.TemplateGenerationError("LLM 호출 실패: x")
        return "<div class=\"wf-root\">ok</div>"

    monkeypatch.setattr(html_template, "generate_html_template", fake)

    class _Req:
        def __init__(self, body):
            self._body = body

        async def json(self):
            return self._body

    out = asyncio.run(ai_router.html_edit("ui-a", _Req({"instruction": " 버튼 추가 ", "display_language": "en"})))
    assert out == {"ok": True, "template": "<div class=\"wf-root\">ok</div>"}
    assert seen[-1] == ("ui-a", "버튼 추가", "en")
    for uid, code in (("missing", 404), ("llm-down", 502)):
        with pytest.raises(HTTPException) as e:
            asyncio.run(ai_router.html_edit(uid, _Req({})))
        assert e.value.status_code == code
