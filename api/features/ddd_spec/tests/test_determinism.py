"""Byte-stable regeneration with ``smooth_ears=false`` (T038 / SC-005).

Running the BC pipeline twice against the same projection must produce
``.md`` files identical except for the ``Generated:`` timestamp line.
"""
from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch

import pytest

from api.features.ddd_spec import paths as paths_mod
from api.features.ddd_spec import repository, service
from api.features.ddd_spec.projection import (
    AggregateAttribute,
    AggregateProjection,
    BoundedContextProjection,
    CommandProjection,
    EventProjection,
    GwtCriterion,
    MemberEntity,
    UserStoryProjection,
)
from api.features.ddd_spec.schemas import GenerateBoundedContextRequest


_GENERATED_LINE = re.compile(r"^.*Generated: .*$", re.MULTILINE)


def _strip_timestamp(text: str) -> str:
    return _GENERATED_LINE.sub("Generated: <ts>", text)


@pytest.fixture()
def specs_root(tmp_path, monkeypatch):
    monkeypatch.setattr(paths_mod, "BASE_DIR", tmp_path)
    monkeypatch.setattr(paths_mod, "SPECS_DIR", tmp_path / "specs")
    monkeypatch.setattr(paths_mod, "BC_ROOT", tmp_path / "specs" / "bounded-contexts")
    monkeypatch.setattr(paths_mod, "LOCK_PATH", tmp_path / "specs" / "bounded-contexts" / ".ddd-spec.lock")
    (tmp_path / "specs" / "bounded-contexts").mkdir(parents=True)
    return tmp_path


def _fixture_bc() -> BoundedContextProjection:
    return BoundedContextProjection(
        id="bc-1",
        name="Order",
        slug="order",
        description="Customer orders",
        purpose="Manage orders",
        aggregates=[
            AggregateProjection(
                id="agg-1",
                name="Order",
                slug="order",
                description="Order aggregate",
                root_entity="Order",
                member_entities=[MemberEntity(name="OrderId", kind="identifier")],
                attributes=[AggregateAttribute(name="id", type="OrderId", mutability="immutable")],
                invariants=["total must be positive"],
                commands=[
                    CommandProjection(
                        id="cmd-1",
                        name="Confirm",
                        events_emitted=["OrderConfirmed"],
                        gwt=[
                            GwtCriterion(
                                id="g",
                                given=["valid cart"],
                                when="confirmed",
                                then=["status becomes Confirmed"],
                            )
                        ],
                    )
                ],
                events=[EventProjection(id="evt", name="OrderConfirmed")],
                identity_type="OrderId",
            )
        ],
        user_stories=[
            UserStoryProjection(
                id="US-1",
                title="Confirm order",
                narrative="As a customer I want to confirm",
                aggregate_id="agg-1",
                acceptance_criteria=[
                    GwtCriterion(
                        id="ac",
                        given=["cart not empty"],
                        when="customer confirms",
                        then=["order is created"],
                    )
                ],
            )
        ],
    )


def test_two_runs_with_smooth_ears_false_are_byte_identical(specs_root):
    bc = _fixture_bc()
    req = GenerateBoundedContextRequest(
        bounded_context_id=bc.id, overwrite=True, smooth_ears=False, render_svg=False,
        aliases_to_avoid="omit",
    )
    with patch.object(repository, "load_bounded_context", return_value=bc):
        service.generate_bounded_context(req)
        snapshot_1 = {
            p.relative_to(specs_root).as_posix(): _strip_timestamp(p.read_text())
            for p in (specs_root / "specs" / "bounded-contexts").rglob("*.md")
        }
        service.generate_bounded_context(req)
        snapshot_2 = {
            p.relative_to(specs_root).as_posix(): _strip_timestamp(p.read_text())
            for p in (specs_root / "specs" / "bounded-contexts").rglob("*.md")
        }
    assert snapshot_1 == snapshot_2
