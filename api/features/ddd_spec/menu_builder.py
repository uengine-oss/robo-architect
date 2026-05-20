"""Build the flat UI inventory for ``specs/frontend/menu-structure.md``.

The 2026-05-12 amendment treats ``menu-structure.md`` as a **guidance
document** for the frontend-engineer agent, NOT a finished menu
structure. We deliberately do not infer routes, group by BC, or invent
a navigation hierarchy here — that's the agent's job, informed by
the wider event-modeling flow captured in ``ui-flow.md``.

What we *do* produce: a flat inventory of every bound UI with enough
traceability for the agent to reason about it (owning BC, story,
binding, actor, entry-point status, unreferenced flag). The renderer
emits the inventory plus prose that tells the agent how to use it.
"""
from __future__ import annotations

from typing import Iterable

from api.features.ddd_spec.projection import (
    BoundedContextProjection,
    MenuEntry,
    UIFlowEntry,
)


def build_menu_hints(
    bcs: Iterable[BoundedContextProjection],
    ui_flow: list[UIFlowEntry],
    unreferenced: list[UIFlowEntry],
) -> list[MenuEntry]:
    """Return one :class:`MenuEntry` per bound UI, in UI-flow order.

    Ordering rule:
    - UIs that participate in the causal flow appear in the same order
      as ``ui_flow`` (so the agent reads them in user-journey order).
    - UIs that ended up as DAG islands (``unreferenced``) are appended
      at the tail with ``is_unreferenced=True``; the agent needs the
      user to confirm where to place them.

    Each entry's ``is_entry_point`` mirrors the UI-flow entry's
    ``triggered_by is None`` — those are the screens a user can land on
    directly, candidates for top-level navigation entries (the agent
    still decides).

    BC fields are filled for traceability so the agent can cite the
    owning BC in code comments / docstrings, but they are NOT a
    grouping directive.
    """
    bc_by_id: dict[str, BoundedContextProjection] = {bc.id: bc for bc in bcs}
    wireframe_by_key: dict[tuple[str, str, str], tuple] = {}
    for bc in bc_by_id.values():
        for story in bc.user_stories:
            for wf in story.wireframes:
                wireframe_by_key[(bc.id, story.id, wf.ui_id)] = (story, wf)

    hints: list[MenuEntry] = []
    seen: set[tuple[str, str, str]] = set()

    def _emit(entry: UIFlowEntry, *, unreferenced_flag: bool) -> None:
        key = (entry.bounded_context_id, entry.user_story_id, entry.wireframe_ui_id)
        if key in seen:
            return
        bc = bc_by_id.get(entry.bounded_context_id)
        story_wf = wireframe_by_key.get(key)
        if bc is None or story_wf is None:
            return
        story, wf = story_wf
        seen.add(key)
        hints.append(
            MenuEntry(
                bc_id=bc.id,
                bc_slug=bc.slug,
                bc_name=bc.name or bc.slug,
                user_story_id=story.id,
                user_story_title=story.title or story.id,
                wireframe_slug=wf.slug,
                wireframe_name=wf.name or wf.slug,
                actor=wf.actor,
                attached_to_type=wf.attached_to_type,
                attached_to_name=wf.attached_to_name,
                is_entry_point=(not unreferenced_flag) and (entry.triggered_by is None),
                is_unreferenced=unreferenced_flag,
                viewport_class=wf.viewport_class,
            )
        )

    for entry in ui_flow:
        _emit(entry, unreferenced_flag=False)
    for entry in unreferenced:
        _emit(entry, unreferenced_flag=True)
    return hints
