"""Tests for the menu-hint inventory builder (T042, revised 2026-05-12).

After the user's feedback, ``menu-structure.md`` is no longer a
deterministic BC-grouped route tree — it is a flat inventory + guidance
document the frontend-engineer agent uses to design the menu IA from the
event-modeling flow. These tests verify the inventory shape, ordering,
and entry-point / unreferenced flagging.
"""
from __future__ import annotations

from api.features.ddd_spec.menu_builder import build_menu_hints
from api.features.ddd_spec.projection import (
    BoundedContextProjection,
    TriggerOrigin,
    UIFlowEntry,
    UserStoryProjection,
    WireframeProjection,
)


def _wf(ui_id: str, slug: str, *, name: str | None = None, actor: str | None = None,
        attached_to_type=None, attached_to_name: str | None = None) -> WireframeProjection:
    return WireframeProjection(
        ui_id=ui_id,
        name=name or slug,
        slug=slug,
        actor=actor,
        attached_to_type=attached_to_type,
        attached_to_name=attached_to_name,
    )


def _bc(id: str, name: str, slug: str, stories: list[UserStoryProjection]) -> BoundedContextProjection:
    return BoundedContextProjection(id=id, name=name, slug=slug, user_stories=stories)


def _flow(bc_id: str, bc_slug: str, story_id: str, ui_id: str,
          *, pos: int = 0, triggered_by: TriggerOrigin | None = None) -> UIFlowEntry:
    return UIFlowEntry(
        position=pos,
        bounded_context_id=bc_id,
        bounded_context_slug=bc_slug,
        user_story_id=story_id,
        user_story_title=story_id,
        wireframe_ui_id=ui_id,
        wireframe_slug=ui_id,
        triggered_by=triggered_by,
    )


def test_inventory_is_flat_no_grouping():
    """No bc_group / route discriminator — every entry is a bound UI."""
    bcs = [
        _bc("bcA", "Alpha", "alpha", [
            UserStoryProjection(id="US1", title="Story 1", priority="P1", wireframes=[_wf("u1", "screen1")]),
        ]),
        _bc("bcB", "Beta", "beta", [
            UserStoryProjection(id="US2", title="Story 2", priority="P1", wireframes=[_wf("u2", "screen2")]),
        ]),
    ]
    ui_flow = [
        _flow("bcA", "alpha", "US1", "u1"),
        _flow("bcB", "beta", "US2", "u2"),
    ]
    hints = build_menu_hints(bcs, ui_flow, [])
    assert len(hints) == 2
    # All hints are flat MenuEntry instances — no nested children, no
    # kind discriminator. Each one names a single wireframe.
    for h in hints:
        assert hasattr(h, "wireframe_slug")
        assert not hasattr(h, "kind")
        assert not hasattr(h, "children")
    assert {h.wireframe_slug for h in hints} == {"screen1", "screen2"}


def test_ordering_follows_ui_flow_not_bc_insertion():
    """The agent reads the inventory in user-journey order (the order
    the ``ui-flow`` sequencer produces), not in BC insertion order."""
    # Alphabetic BC insertion would put 'alpha' first, but ui_flow says
    # 'beta' is the entry point — the inventory must follow ui_flow.
    bcs = [
        _bc("bcA", "Alpha", "alpha", [
            UserStoryProjection(id="US1", title="A", priority="P1", wireframes=[_wf("u1", "a-screen")]),
        ]),
        _bc("bcB", "Beta", "beta", [
            UserStoryProjection(id="US2", title="B", priority="P1", wireframes=[_wf("u2", "b-screen")]),
        ]),
    ]
    ui_flow = [
        _flow("bcB", "beta", "US2", "u2"),  # downstream BC first per the sequencer
        _flow("bcA", "alpha", "US1", "u1"),
    ]
    hints = build_menu_hints(bcs, ui_flow, [])
    assert [h.wireframe_slug for h in hints] == ["b-screen", "a-screen"]


def test_entry_point_flagged_when_triggered_by_is_none():
    bcs = [
        _bc("bcA", "Alpha", "alpha", [
            UserStoryProjection(id="US1", title="A", priority="P1",
                                wireframes=[_wf("u1", "entry"), _wf("u2", "next")]),
        ]),
    ]
    ui_flow = [
        _flow("bcA", "alpha", "US1", "u1", triggered_by=None),
        _flow("bcA", "alpha", "US1", "u2",
              triggered_by=TriggerOrigin(kind="story_internal", from_user_story_id="US1")),
    ]
    hints = build_menu_hints(bcs, ui_flow, [])
    by_slug = {h.wireframe_slug: h for h in hints}
    assert by_slug["entry"].is_entry_point is True
    assert by_slug["entry"].is_unreferenced is False
    assert by_slug["next"].is_entry_point is False


def test_unreferenced_uis_appended_at_tail_with_flag():
    bcs = [
        _bc("bcA", "Alpha", "alpha", [
            UserStoryProjection(id="US1", title="A", priority="P1", wireframes=[_wf("u1", "main")]),
            UserStoryProjection(id="US2", title="Island", priority="P1", wireframes=[_wf("u9", "island")]),
        ]),
    ]
    ui_flow = [_flow("bcA", "alpha", "US1", "u1")]
    unreferenced = [_flow("bcA", "alpha", "US2", "u9")]
    hints = build_menu_hints(bcs, ui_flow, unreferenced)
    assert [h.wireframe_slug for h in hints] == ["main", "island"]
    assert hints[0].is_unreferenced is False
    assert hints[1].is_unreferenced is True
    # An unreferenced UI is never simultaneously an entry point in the
    # IA sense — the agent must confirm where to place it.
    assert hints[1].is_entry_point is False


def test_inventory_carries_traceability_fields():
    """Each hint must carry actor + binding + owning-BC fields so the
    agent can cite them in generated code (without using them for IA)."""
    bcs = [
        _bc("bcZ", "Zed", "zed", [
            UserStoryProjection(id="US-42", title="ship it", priority="P1", wireframes=[
                _wf("ui-99", "ship-it", actor="seller",
                    attached_to_type="Command", attached_to_name="ShipOrder"),
            ]),
        ]),
    ]
    ui_flow = [_flow("bcZ", "zed", "US-42", "ui-99")]
    [hint] = build_menu_hints(bcs, ui_flow, [])
    assert hint.bc_id == "bcZ"
    assert hint.bc_slug == "zed"
    assert hint.bc_name == "Zed"
    assert hint.user_story_id == "US-42"
    assert hint.user_story_title == "ship it"
    assert hint.wireframe_slug == "ship-it"
    assert hint.actor == "seller"
    assert hint.attached_to_type == "Command"
    assert hint.attached_to_name == "ShipOrder"


def test_empty_inputs_yield_empty_inventory():
    assert build_menu_hints([], [], []) == []


def test_duplicate_ui_in_ui_flow_emitted_once():
    """Defensive: the sequencer should not produce duplicates, but if it
    did we'd dedupe so the inventory stays meaningful."""
    bcs = [
        _bc("bcA", "Alpha", "alpha", [
            UserStoryProjection(id="US1", title="A", priority="P1", wireframes=[_wf("u1", "screen")]),
        ]),
    ]
    ui_flow = [
        _flow("bcA", "alpha", "US1", "u1"),
        _flow("bcA", "alpha", "US1", "u1"),  # accidental duplicate
    ]
    hints = build_menu_hints(bcs, ui_flow, [])
    assert len(hints) == 1
