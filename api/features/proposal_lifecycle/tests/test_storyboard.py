"""056 — Proposal 초안 스토리보드 단위 테스트 (Neo4j/LLM 없이)."""

from __future__ import annotations

import asyncio

import pytest

from api.features.proposal_lifecycle.services import storyboard_runner as sr


STRATEGIC = {
    "version": 1,
    "userStories": [
        {"op": "CREATE", "entityType": "userStory", "tempId": "US-browse", "entityTitle": "메뉴 조회",
         "fields": {"role": {"after": "고객"}, "action": {"after": "메뉴를 조회한다"}, "benefit": {"after": "원하는 음식을 고른다"}}},
        {"op": "CREATE", "entityType": "userStory", "tempId": "US-order", "entityTitle": "주문 생성",
         "fields": {"role": {"after": "고객"}, "action": {"after": "장바구니를 주문한다"}}},
    ],
}
JOURNEYS = [
    {"tempId": "JNY-order", "name": "음식 주문 여정", "description": "메뉴 조회부터 주문 확정까지",
     "steps": [
         {"tempId": "ST-browse", "name": "메뉴 조회", "kind": "screen", "readModelRef": "RM-menu", "userStoryRef": "US-browse", "next": ["ST-gw"]},
         {"tempId": "ST-gw", "name": "장바구니 비었나?", "kind": "gateway", "condition": "장바구니 수량 > 0", "next": ["ST-order"]},
         {"tempId": "ST-order", "name": "주문 생성", "kind": "screen", "commandRef": "CMD-place", "next": []},
     ]},
]


def test_build_screen_plan_uses_journeys_and_matches_stories():
    plan = sr.build_screen_plan(STRATEGIC, JOURNEYS, "배달앱 주문 기능")
    assert len(plan) == 1
    j = plan[0]
    assert j["id"] == "JNY-order" and j["name"] == "음식 주문 여정"
    kinds = [s["kind"] for s in j["steps"]]
    assert kinds == ["screen", "gateway", "screen"]
    browse = j["steps"][0]
    assert browse["userStoryId"] == "US-browse"            # explicit ref
    assert "메뉴를 조회한다" in browse["description"]
    assert browse["next"] == ["ST-gw"]
    order = j["steps"][2]
    assert order["userStoryId"] == "US-order"              # matched by name tokens
    assert "요구사항 원문" in order["description"]


def test_build_screen_plan_falls_back_to_user_stories():
    plan = sr.build_screen_plan(STRATEGIC, [], "prompt")
    assert len(plan) == 1 and plan[0]["id"] == "jny-user-stories"
    steps = plan[0]["steps"]
    assert [s["name"] for s in steps] == ["메뉴 조회", "주문 생성"]
    assert steps[0]["next"] == [steps[1]["id"]] and steps[1]["next"] == []


def test_build_screen_plan_respects_budget(monkeypatch):
    monkeypatch.setattr(sr, "STORYBOARD_MAX_STEPS", 1)
    plan = sr.build_screen_plan(STRATEGIC, JOURNEYS, "")
    screens = [s for s in plan[0]["steps"] if s["kind"] == "screen"]
    assert len(screens) == 1


def test_root_frame_id_prefers_canvas_child():
    scene = {"nodes": {
        "doc": {"type": "DOCUMENT", "parentId": None},
        "pg": {"type": "CANVAS", "parentId": "doc"},
        "f1": {"type": "FRAME", "parentId": "pg"},
        "f2": {"type": "FRAME", "parentId": "f1"},
    }}
    assert sr._root_frame_id(scene) == "f1"
    assert sr._root_frame_id({"nodes": {"x": {"type": "FRAME", "parentId": "nope"}}}) == "x"
    assert sr._root_frame_id({}) is None


def test_strip_scenes_drops_scene_graph_but_flags_presence():
    sb = {"status": "completed", "journeys": [{"id": "j", "steps": [
        {"id": "a", "sceneGraph": {"nodes": {}}, "status": "done"},
        {"id": "b", "sceneGraph": None, "status": "failed"},
    ]}]}
    light = sr.strip_scenes(sb)
    steps = light["journeys"][0]["steps"]
    assert "sceneGraph" not in steps[0] and steps[0]["hasScene"] is True
    assert steps[1]["hasScene"] is False
    # original untouched
    assert sb["journeys"][0]["steps"][0]["sceneGraph"] == {"nodes": {}}


def test_run_storyboard_renders_each_screen_and_persists(monkeypatch):
    saved: list[dict] = []
    monkeypatch.setattr(sr, "_load_proposal", lambda pid: {
        "prompt": "배달앱", "strategic": STRATEGIC, "journeys": JOURNEYS, "storyboard": None})
    monkeypatch.setattr(sr, "_save_storyboard", lambda pid, sb: saved.append({"status": sb["status"], "done": sb["done"]}))
    monkeypatch.setattr(sr, "_catalog_context", lambda: "")

    async def fake_render(*, name, description, bc_name, bc_description, extra_context, on_event=None):
        if name == "주문 생성":
            return None, None
        return {"nodes": {"pg": {"type": "CANVAS", "parentId": "doc"}, "f": {"type": "FRAME", "parentId": "pg"}}}, "ok"

    import api.features.ai_design.wireframe_agent as wa
    monkeypatch.setattr(wa, "run_render_agent", fake_render)

    sb = asyncio.run(sr.run_storyboard("PRO-TEST", force=True))
    assert sb["status"] == "completed" and sb["total"] == 2 and sb["done"] == 2 and sb["failed"] == 1
    steps = {s["id"]: s for s in sb["journeys"][0]["steps"]}
    assert steps["ST-browse"]["status"] == "done" and steps["ST-browse"]["frameId"] == "f"
    assert steps["ST-order"]["status"] == "failed"
    assert steps["ST-gw"]["status"] == "skipped"
    assert saved[0]["status"] == "running" and saved[-1]["status"] == "completed"
    assert not sr.is_running("PRO-TEST")


def test_run_storyboard_returns_existing_unless_forced(monkeypatch):
    existing = {"status": "completed", "journeys": []}
    monkeypatch.setattr(sr, "_load_proposal", lambda pid: {"prompt": "", "strategic": {}, "journeys": [], "storyboard": existing})
    assert asyncio.run(sr.run_storyboard("PRO-X")) is existing


def test_update_step_scene(monkeypatch):
    store = {"storyboard": {"status": "completed", "journeys": [{"id": "j", "steps": [{"id": "a", "sceneGraph": None, "status": "failed"}]}]}}
    monkeypatch.setattr(sr, "_load_proposal", lambda pid: {"prompt": "", "strategic": {}, "journeys": [], **store})
    monkeypatch.setattr(sr, "_save_storyboard", lambda pid, sb: store.__setitem__("storyboard", sb))
    scene = {"nodes": {"pg": {"type": "CANVAS", "parentId": None}, "f": {"type": "FRAME", "parentId": "pg"}}}
    sb = sr.update_step_scene("P", "a", scene)
    st = sb["journeys"][0]["steps"][0]
    assert st["status"] == "done" and st["frameId"] == "f" and st["sceneGraph"] is scene
    assert sr.update_step_scene("P", "missing", scene) is None


def test_native_instance_context_mentions_instance_syntax():
    from api.features.figma_binding import component_library as cl

    ctx = cl.build_jsx_agent_extra_context("## btn-main\n- Type: COMPONENT", native_instances=True)
    assert "<Instance" in ctx and "$INSTANCE:" not in ctx
    legacy = cl.build_jsx_agent_extra_context("## btn-main")
    assert "$INSTANCE:" in legacy
    assert cl.build_jsx_agent_extra_context("", native_instances=True) == ""
