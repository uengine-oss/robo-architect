"""Renderer section-mapping tests (T035).

These tests drive each renderer end-to-end with fixture projections and
inspect the produced markdown for the expected section anchors and the
"(not modeled — confirm)"/"Open Decisions" degraded-path branches.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from api.features.ddd_spec import paths as paths_mod
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
from api.features.ddd_spec.service import jinja_env
from api.features.ddd_spec.renderers import (
    aggregate_spec,
    bc_canvas,
    domain_terms,
    requirements_md,
)


@dataclass
class _Ctx:
    created: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def warn(self, code, message, target=None):
        self.warnings.append(code)

    def record_created(self, info):
        self.created.append(info)

    def record_skipped(self, info):
        self.skipped.append(info)

    def log(self, *a, **kw):
        pass


@pytest.fixture()
def specs_root(tmp_path, monkeypatch):
    monkeypatch.setattr(paths_mod, "BASE_DIR", tmp_path)
    monkeypatch.setattr(paths_mod, "SPECS_DIR", tmp_path / "specs")
    monkeypatch.setattr(paths_mod, "BC_ROOT", tmp_path / "specs" / "bounded-contexts")
    (tmp_path / "specs" / "bounded-contexts").mkdir(parents=True)
    return tmp_path


@pytest.fixture()
def bc():
    return BoundedContextProjection(
        id="bc-1",
        name="Order",
        slug="order",
        description="Customer orders",
        purpose=None,
        strategic=None,
        aggregates=[
            AggregateProjection(
                id="agg-1",
                name="Order",
                slug="order",
                description="Order aggregate",
                root_entity="Order",
                member_entities=[MemberEntity(name="OrderId", kind="identifier")],
                attributes=[
                    AggregateAttribute(name="id", type="OrderId", mutability="immutable")
                ],
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
                    ),
                    CommandProjection(id="cmd-2", name="Cancel", gwt=[]),
                ],
                events=[EventProjection(id="evt", name="OrderConfirmed")],
                identity_type="OrderId",
            )
        ],
        user_stories=[
            UserStoryProjection(
                id="US-1",
                title="Confirm order",
                narrative="As a customer I want to confirm my order",
                aggregate_id="agg-1",
                acceptance_criteria=[
                    GwtCriterion(
                        id="ac-1",
                        given=["cart not empty"],
                        when="customer confirms",
                        then=["order is created"],
                    )
                ],
            )
        ],
    )


def test_bc_canvas_warns_on_missing_purpose_and_classification(specs_root, bc):
    ctx = _Ctx()
    info = bc_canvas.render(ctx, jinja_env(), bc, generated_at="2026-01-01T00:00:00Z")
    assert info is not None
    body = Path(specs_root / info.path).read_text()
    assert "Purpose" in body and "_(not modeled — confirm)_" in body
    assert "Strategic Classification" in body and "_(not classified — confirm)_" in body
    assert "bc_purpose_missing" in ctx.warnings
    assert "bc_not_classified" in ctx.warnings


def test_aggregate_spec_has_all_sections_and_flags_gwt_less_command(specs_root, bc):
    ctx = _Ctx()
    agg = bc.aggregates[0]
    info = aggregate_spec.render(
        ctx,
        jinja_env(),
        bc,
        agg,
        generated_at="2026-01-01T00:00:00Z",
        smoother=None,
        overwrite=True,
    )
    assert info is not None
    body = Path(specs_root / info.path).read_text()
    for section in (
        "## Description",
        "## Aggregate Root",
        "## Member Entities & Value Objects",
        "## Properties",
        "## Enforced Invariants",
        "## Corrective Policies",
        "## Commands",
        "## Domain Events Emitted",
        "## Repository Interface",
        "## Open Decisions",
    ):
        assert section in body, f"missing section: {section}"
    assert "THE Order SHALL total must be positive" in body
    assert "WHEN confirmed IF valid cart THEN system SHALL status becomes Confirmed" in body
    # GWT-less Cancel command → Open Decisions branch.
    assert "Command `Cancel` has no GWT modeled" in body
    assert "command_missing_gwt" in ctx.warnings


def test_domain_terms_has_term_blocks(specs_root, bc):
    ctx = _Ctx()
    req = GenerateBoundedContextRequest(bounded_context_id="bc-1", aliases_to_avoid="omit")
    info = domain_terms.render(ctx, jinja_env(), bc, req, "2026-01-01T00:00:00Z")
    assert info is not None
    body = Path(specs_root / info.path).read_text()
    assert "## Term: `Order`" in body
    assert "## Term: `Confirm`" in body
    assert "## Term: `OrderConfirmed`" in body


def test_requirements_md_renders_ears_acceptance(specs_root, bc):
    ctx = _Ctx()
    req = GenerateBoundedContextRequest(bounded_context_id="bc-1", render_svg=False)
    info = requirements_md.render(ctx, jinja_env(), bc, req, generated_at="2026-01-01T00:00:00Z")
    assert info is not None
    body = Path(specs_root / info.path).read_text()
    assert "## Aggregate: Order" in body
    assert "### Confirm order" in body
    assert "WHEN customer confirms IF cart not empty THEN system SHALL order is created" in body
