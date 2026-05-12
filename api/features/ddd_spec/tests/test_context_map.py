"""Tests for the Context-Map relationship-pattern heuristics (T024)."""
from __future__ import annotations

from dataclasses import dataclass, field

from api.features.ddd_spec.projection import (
    BoundedContextProjection,
    CrossBcFlow,
    ExternalIntegrationProjection,
)
from api.features.ddd_spec.renderers import context_map


@dataclass
class _Ctx:
    warnings: list = field(default_factory=list)

    def warn(self, code, message, target=None):
        self.warnings.append((code, target or {}))


def _bc(bc_id, name, *, externals=None):
    return BoundedContextProjection(
        id=bc_id,
        name=name,
        slug=name.lower().replace(" ", "-"),
        external_integrations=externals or [],
    )


def _flow(u, d, message="X", pattern=None):
    return CrossBcFlow(
        from_bc_id=u.id,
        from_bc_name=u.name,
        to_bc_id=d.id,
        to_bc_name=d.name,
        message=message,
        recorded_pattern=pattern,
    )


def test_default_customer_supplier_for_simple_event_flow():
    ctx = _Ctx()
    a = _bc("a", "A")
    b = _bc("b", "B")
    edges = context_map.build_edges(ctx, [a, b], [_flow(a, b)])
    assert edges[0]["pattern"] == "Customer-Supplier"
    assert edges[0]["pattern_inferred"]
    assert ("relationship_pattern_inferred", {"from_bc_id": "a", "to_bc_id": "b"}) in ctx.warnings


def test_conformist_acl_when_downstream_has_external_integration():
    ctx = _Ctx()
    a = _bc("a", "A")
    b = _bc(
        "b",
        "B",
        externals=[
            ExternalIntegrationProjection(
                id="x",
                external_system_name="Stripe",
                slug="stripe",
                direction="outbound",
            )
        ],
    )
    edges = context_map.build_edges(ctx, [a, b], [_flow(a, b)])
    assert "Conformist" in edges[0]["pattern"]
    assert "Anti-Corruption Layer" in edges[0]["pattern"]


def test_published_language_for_high_fanout():
    ctx = _Ctx()
    pub = _bc("pub", "Publisher")
    consumers = [_bc(f"c{i}", f"C{i}") for i in range(3)]
    flows = [_flow(pub, c) for c in consumers]
    edges = context_map.build_edges(ctx, [pub] + consumers, flows)
    for e in edges:
        assert e["pattern"] == "Open Host Service + Published Language"


def test_recorded_pattern_used_without_inference_warning():
    ctx = _Ctx()
    a = _bc("a", "A")
    b = _bc("b", "B")
    edges = context_map.build_edges(ctx, [a, b], [_flow(a, b, pattern="Shared Kernel")])
    assert edges[0]["pattern"] == "Shared Kernel"
    assert not edges[0]["pattern_inferred"]
    assert not ctx.warnings


def test_acl_spec_file_link_for_downstream_with_external():
    ctx = _Ctx()
    a = _bc("a", "A")
    b = _bc(
        "b",
        "B",
        externals=[
            ExternalIntegrationProjection(
                id="x",
                external_system_name="Stripe",
                slug="stripe",
                direction="outbound",
            )
        ],
    )
    edges = context_map.build_edges(ctx, [a, b], [_flow(a, b)])
    assert edges[0]["spec_file"].endswith("acl-stripe.md")
