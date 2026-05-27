"""Tests for generate_bc_spec_files threshold-gated split (oversized BC fix).

The split decision is driven by a single line-count threshold so the test
fixtures can be tiny — we override the env knob per test rather than
constructing thousand-line BCs.
"""
from __future__ import annotations

import pytest

from api.features.prd_generation.prd_api_contracts import (
    AIAssistant,
    DeploymentStyle,
    Framework,
    Language,
    SpecFormat,
    TechStackConfig,
)
from api.features.prd_generation.prd_artifact_generation import (
    _events_emitted_by,
    generate_bc_spec,
    generate_bc_spec_files,
)


def _cfg() -> TechStackConfig:
    return TechStackConfig(
        project_name="demo",
        language=Language.JAVA,
        framework=Framework.SPRING_BOOT,
        ai_assistant=AIAssistant.CLAUDE,
        spec_format=SpecFormat.PRD,
        include_frontend=False,
        frontend_framework=None,
        deployment=DeploymentStyle.MODULAR_MONOLITH,
    )


def _cmd(name: str) -> dict:
    return {
        "id": f"cmd-{name}",
        "name": name,
        "displayName": name,
        "actor": "system",
        "category": "Update",
        "inputSchema": "{}",
        "description": f"{name} description",
        "properties": [{"id": "p1", "name": "p1", "type": "String"}],
        "sourceRules": [],
    }


def _evt(name: str, emitting_cmd: str) -> dict:
    return {
        "id": f"evt-{name}",
        "name": name,
        "displayName": name,
        "version": "1",
        "schema": "{}",
        "description": f"{name} happened",
        "properties": [{"id": "p1", "name": "p1", "type": "String"}],
        "sourceRules": [],
        "sourceExamples": [],
        "emittingCommandId": f"cmd-{emitting_cmd}",
        "emittingCommandName": emitting_cmd,
    }


def _agg(name: str, cmd_names: list[str]) -> dict:
    commands = [_cmd(c) for c in cmd_names]
    # 2 events per command keeps the fixture compact but exercises
    # emitting-command linkage on the split path.
    events = []
    for c in cmd_names:
        events.append(_evt(f"{c}Started", c))
        events.append(_evt(f"{c}Completed", c))
    return {
        "id": f"agg-{name}",
        "name": name,
        "displayName": name,
        "rootEntity": name,
        "invariants": [],
        "enumerations": [],
        "valueObjects": [],
        "properties": [],
        "sourceRules": [],
        "commands": commands,
        "events": events,
    }


def _bc(name: str, aggregates: list[dict]) -> dict:
    return {
        "id": f"bc-{name}",
        "name": name,
        "displayName": name,
        "description": f"{name} BC",
        "aggregates": aggregates,
        "readmodels": [],
        "policies": [],
        "uis": [],
        "gwts": [],
        "questions": [],
        "userStories": [],
    }


def test_small_bc_emits_single_index_file(monkeypatch):
    """Small BCs still live under their own folder — same shape as split
    BCs — so consumers can rely on ``specs/{bc}/index.md`` always existing.
    """
    monkeypatch.setenv("BC_SPEC_SPLIT_LINE_THRESHOLD", "10000")
    bc = _bc("Tiny", [_agg("OnlyAgg", ["DoOne"])])
    files = generate_bc_spec_files(bc, _cfg())
    assert list(files.keys()) == ["specs/tiny/index.md"]


def test_oversized_multi_aggregate_splits_per_aggregate(monkeypatch):
    # Force the threshold low so the split branch fires with tiny fixtures.
    monkeypatch.setenv("BC_SPEC_SPLIT_LINE_THRESHOLD", "40")
    bc = _bc(
        "Shop",
        [
            _agg("Order", ["Place", "Cancel"]),
            _agg("Inventory", ["Reserve", "Release"]),
        ],
    )
    files = generate_bc_spec_files(bc, _cfg())
    assert "specs/shop/index.md" in files
    assert "specs/shop/order.md" in files
    assert "specs/shop/inventory.md" in files
    # Per-aggregate file should contain only its own aggregate.
    order = files["specs/shop/order.md"]
    assert "### Order" in order
    assert "### Inventory" not in order
    # Index should table-link to both aggregates.
    idx = files["specs/shop/index.md"]
    assert "## Aggregates (per-file)" in idx
    assert "[`Order`](order.md)" in idx
    assert "[`Inventory`](inventory.md)" in idx


def test_oversized_single_aggregate_splits_per_command(monkeypatch):
    monkeypatch.setenv("BC_SPEC_SPLIT_LINE_THRESHOLD", "40")
    bc = _bc("Billing", [_agg("Invoice", ["Issue", "Settle", "Refund"])])
    files = generate_bc_spec_files(bc, _cfg())
    assert "specs/billing/index.md" in files
    assert "specs/billing/invoice/cmds/issue.md" in files
    assert "specs/billing/invoice/cmds/settle.md" in files
    assert "specs/billing/invoice/cmds/refund.md" in files
    # Per-command file should carry its emitted events (and no other cmd's).
    issue = files["specs/billing/invoice/cmds/issue.md"]
    assert "`Issue`" in issue
    assert "`Settle`" not in issue
    assert "IssueStarted" in issue
    assert "IssueCompleted" in issue
    assert "SettleStarted" not in issue
    # Index lists all commands with link targets.
    idx = files["specs/billing/index.md"]
    assert "## Commands (per-file)" in idx
    assert "[`Issue`](invoice/cmds/issue.md)" in idx
    assert "[`Refund`](invoice/cmds/refund.md)" in idx


def test_events_without_emitting_command_land_in_index(monkeypatch):
    """Defensive: orphan events (no emittingCommand*) must not be silently
    dropped during a per-command split."""
    monkeypatch.setenv("BC_SPEC_SPLIT_LINE_THRESHOLD", "40")
    agg = _agg("Invoice", ["Issue", "Settle"])
    agg["events"].append({
        "id": "evt-orphan",
        "name": "OrphanRecorded",
        "displayName": "OrphanRecorded",
        "version": "1",
        "properties": [],
        "sourceRules": [],
        "sourceExamples": [],
        # Intentionally missing emittingCommand* keys.
    })
    bc = _bc("Billing", [agg])
    files = generate_bc_spec_files(bc, _cfg())
    idx = files["specs/billing/index.md"]
    assert "OrphanRecorded" in idx
    # And the per-cmd files must not have absorbed it.
    issue = files["specs/billing/invoice/cmds/issue.md"]
    assert "OrphanRecorded" not in issue


def test_oversized_single_agg_single_cmd_stays_monolith(monkeypatch):
    """No useful split granularity → fall back to the monolith path."""
    monkeypatch.setenv("BC_SPEC_SPLIT_LINE_THRESHOLD", "10")
    bc = _bc("Lonely", [_agg("Only", ["DoIt"])])
    files = generate_bc_spec_files(bc, _cfg())
    assert list(files.keys()) == ["specs/lonely/index.md"]


def test_threshold_env_invalid_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("BC_SPEC_SPLIT_LINE_THRESHOLD", "not-a-number")
    bc = _bc("Tiny", [_agg("OnlyAgg", ["DoOne"])])
    # Should not raise; default (800) keeps tiny BC as a single index file.
    files = generate_bc_spec_files(bc, _cfg())
    assert list(files.keys()) == ["specs/tiny/index.md"]


def test_events_emitted_by_matches_by_id_or_name():
    agg = {
        "events": [
            {"id": "e1", "emittingCommandId": "c1", "emittingCommandName": "Cmd1"},
            {"id": "e2", "emittingCommandId": "c2", "emittingCommandName": "Cmd2"},
            {"id": "e3", "emittingCommandId": None, "emittingCommandName": "Cmd1"},
        ]
    }
    by_id = _events_emitted_by(agg, "c1", None)
    assert {e["id"] for e in by_id} == {"e1"}
    by_name = _events_emitted_by(agg, None, "Cmd1")
    assert {e["id"] for e in by_name} == {"e1", "e3"}


def test_monolith_render_unchanged_for_small_bc():
    """When no split fires the index content must exactly equal what
    generate_bc_spec produced (only the path changed)."""
    bc = _bc("Tiny", [_agg("OnlyAgg", ["DoOne"])])
    cfg = _cfg()
    files = generate_bc_spec_files(bc, cfg)
    assert files["specs/tiny/index.md"] == generate_bc_spec(bc, cfg)


def _ui(name: str, kind: str, target: str) -> dict:
    """Convenience: build a UI dict that mirrors what fetch_bc_data emits."""
    return {
        "id": f"ui-{name}",
        "name": name,
        "description": f"{name} wireframe",
        "template": "<html><body><h1>placeholder</h1></body></html>",
        "attachedToId": target,
        "attachedToType": kind,
        "attachedToName": target,
    }


def test_command_attached_uis_follow_their_command_on_command_split(monkeypatch):
    monkeypatch.setenv("BC_SPEC_SPLIT_LINE_THRESHOLD", "40")
    bc = _bc("Billing", [_agg("Invoice", ["Issue", "Settle"])])
    bc["uis"] = [
        _ui("IssueForm", "Command", "Issue"),
        _ui("SettleScreen", "Command", "Settle"),
        _ui("OrphanWidget", "ReadModel", "InvoiceList"),
    ]
    files = generate_bc_spec_files(bc, _cfg())
    issue = files["specs/billing/invoice/cmds/issue.md"]
    settle = files["specs/billing/invoice/cmds/settle.md"]
    idx = files["specs/billing/index.md"]
    # Command-attached UIs travel with their command, not the index.
    assert "IssueForm" in issue and "IssueForm" not in settle and "IssueForm" not in idx
    assert "SettleScreen" in settle and "SettleScreen" not in issue and "SettleScreen" not in idx
    # Non-command UIs stay in the index.
    assert "OrphanWidget" in idx
    # Index command table surfaces the UI count column.
    assert "| UIs |" in idx


def test_command_attached_uis_follow_aggregate_on_aggregate_split(monkeypatch):
    monkeypatch.setenv("BC_SPEC_SPLIT_LINE_THRESHOLD", "40")
    bc = _bc(
        "Shop",
        [
            _agg("Order", ["Place", "Cancel"]),
            _agg("Inventory", ["Reserve", "Release"]),
        ],
    )
    bc["uis"] = [
        _ui("PlaceOrderForm", "Command", "Place"),
        _ui("CancelOrderForm", "Command", "Cancel"),
        _ui("ReserveScreen", "Command", "Reserve"),
        _ui("FreestandingWidget", "ReadModel", "ItemList"),
    ]
    files = generate_bc_spec_files(bc, _cfg())
    order = files["specs/shop/order.md"]
    inventory = files["specs/shop/inventory.md"]
    idx = files["specs/shop/index.md"]
    # UIs attached to commands owned by the aggregate ride along.
    assert "PlaceOrderForm" in order
    assert "CancelOrderForm" in order
    assert "ReserveScreen" in inventory
    # And don't leak into the other aggregate or into the index.
    assert "PlaceOrderForm" not in inventory
    assert "PlaceOrderForm" not in idx
    assert "ReserveScreen" not in order
    assert "ReserveScreen" not in idx
    # Non-command-attached UI lands in the index.
    assert "FreestandingWidget" in idx
