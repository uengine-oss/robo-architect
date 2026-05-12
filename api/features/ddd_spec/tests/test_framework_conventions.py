"""Tests for the frontend framework convention catalog (T043)."""
from __future__ import annotations

import pytest

from api.features.prd_generation.prd_api_contracts import FrontendFramework
from api.features.prd_generation.prd_tech_stack_catalog import (
    FRAMEWORK_CONVENTIONS,
    get_framework_conventions,
)


def test_vue_react_svelte_all_resolve():
    for fw in (FrontendFramework.VUE, FrontendFramework.REACT, FrontendFramework.SVELTE):
        c = get_framework_conventions(fw)
        assert c is not None
        assert c.framework == fw.value
        assert c.component_file_shape
        assert c.state_default
        assert c.routing_default
        assert c.styling_default


def test_none_input_returns_none():
    assert get_framework_conventions(None) is None


def test_catalog_keys_are_frontend_framework_enum_members():
    for k in FRAMEWORK_CONVENTIONS.keys():
        assert isinstance(k, FrontendFramework)


def test_each_convention_value_strings_are_nonempty():
    for fw, conv in FRAMEWORK_CONVENTIONS.items():
        for attr in ("component_file_shape", "state_default", "routing_default", "styling_default"):
            v = getattr(conv, attr)
            assert isinstance(v, str) and v.strip(), f"{fw.value}.{attr} empty"


def test_conventions_distinguish_frameworks():
    """No two frameworks should share an identical conventions bundle —
    they exist precisely to differ."""
    bundles = [
        (k.value, (c.component_file_shape, c.state_default, c.routing_default, c.styling_default))
        for k, c in FRAMEWORK_CONVENTIONS.items()
    ]
    tuples_seen = set()
    for fw, t in bundles:
        assert t not in tuples_seen, f"Framework {fw} duplicates another's conventions"
        tuples_seen.add(t)
