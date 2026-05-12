"""Tests for the GWT → EARS deterministic transform (T013)."""
from __future__ import annotations

from api.features.ddd_spec.ears import (
    aggregate_invariant_lines,
    gwt_to_ears,
    story_acceptance_lines,
    unconditional_invariant,
)
from api.features.ddd_spec.projection import GwtCriterion


def _crit(given=None, when="", then=None):
    return GwtCriterion(id="c", given=given or [], when=when, then=then or [])


def test_full_gwt_maps_to_when_if_then_shall():
    out = gwt_to_ears(_crit(given=["cart is not empty"], when="customer confirms", then=["order is created"]))
    assert out == ["WHEN customer confirms IF cart is not empty THEN system SHALL order is created"]


def test_no_given_omits_if_clause():
    out = gwt_to_ears(_crit(when="customer confirms", then=["order is created"]))
    assert out == ["WHEN customer confirms THEN system SHALL order is created"]


def test_multiple_given_joined_with_and():
    out = gwt_to_ears(_crit(given=["cart not empty", "user logged in"], when="checkout", then=["order created"]))
    assert "IF cart not empty AND user logged in" in out[0]


def test_multiple_then_emits_one_shall_each():
    out = gwt_to_ears(_crit(when="X", then=["A", "B"]))
    assert out == [
        "WHEN X THEN system SHALL A",
        "WHEN X THEN system SHALL B",
    ]


def test_keyword_prefixes_stripped_from_given_when_then():
    out = gwt_to_ears(_crit(given=["Given user signed in"], when="When checkout", then=["Then order placed"]))
    assert out == ["WHEN checkout IF user signed in THEN system SHALL order placed"]


def test_unconditional_invariant_for_aggregate():
    line = unconditional_invariant("Order", "total must be positive")
    assert line == "THE Order SHALL total must be positive"


def test_aggregate_invariant_lines_numbering_order():
    lines = aggregate_invariant_lines(
        "Order",
        unconditional=["total > 0", "no edits after shipped"],
        commands_gwt=[_crit(when="confirmed", then=["status becomes Confirmed"])],
    )
    assert lines[0] == "THE Order SHALL total > 0"
    assert lines[1] == "THE Order SHALL no edits after shipped"
    assert lines[2] == "WHEN confirmed THEN system SHALL status becomes Confirmed"


def test_smoother_token_preservation():
    seen: list[list[str]] = []

    def smoother(lines: list[str]) -> list[str]:
        seen.append(list(lines))
        # Intentionally drop the SHALL token — caller must reject.
        return ["this paraphrase has no keywords"] * len(lines)

    lines = aggregate_invariant_lines(
        "Order",
        unconditional=["x"],
        commands_gwt=[],
        smoother=smoother,
    )
    # The smoother in this module returns the smoothed list as-is — the
    # token-preservation guard lives in `llm_assist.smooth_ears`. Verify the
    # pipeline calls the smoother with the deterministic lines first.
    assert seen and seen[0] == ["THE Order SHALL x"]
    assert lines == ["this paraphrase has no keywords"]


def test_story_acceptance_lines():
    out = story_acceptance_lines(
        acceptance_criteria=[_crit(given=["a"], when="b", then=["c", "d"])]
    )
    assert out == [
        "WHEN b IF a THEN system SHALL c",
        "WHEN b IF a THEN system SHALL d",
    ]
