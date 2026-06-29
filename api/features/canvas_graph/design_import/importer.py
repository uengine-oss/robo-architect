"""Importer: normalized DesignModel → graph, reusing the proposal applier.

Builds a tactical-diff (the same shape `apply_tactical_diff` consumes) so the
imported model lands with exactly the relationships the Design-tab big-picture
query needs. `mode='replace'` wipes the existing event-storming model first
(single-model semantics); `mode='merge'` adds onto it.
"""
from __future__ import annotations

from typing import Any

from api.features.proposal_lifecycle.services.proposal_apply import apply_tactical_diff

IMPORT_SOURCE = "DESIGN-IMPORT"

# Mirrors ingestion_workflow_runner._ES_LABELS (single-model wipe scope).
_ES_LABELS = [
    "UserStory", "BoundedContext", "Aggregate", "Command", "Event",
    "ReadModel", "Policy", "Property", "CQRSConfig", "CQRSOperation",
    "UI", "GWT", "Feature", "Invariant",
]


def build_tactical_diff(model: dict) -> list[dict]:
    """DesignModel → tactical-diff items with tempIds + parent refs."""
    items: list[dict] = []
    for bc in model.get("boundedContexts", []):
        bc_temp = f"bc:{bc['name']}"
        items.append({
            "nodeLabel": "BoundedContext", "changeType": "CREATE",
            "nodeTitle": bc["name"], "tempId": bc_temp,
            "fields": {"displayName": bc.get("display") or bc["name"],
                       "description": bc.get("description") or ""},
        })
        for agg in bc.get("aggregates", []):
            items.append({
                "nodeLabel": "Aggregate", "changeType": "CREATE",
                "nodeTitle": agg["name"], "tempId": f"agg:{agg['name']}",
                "boundedContextId": bc_temp,
                "invariants": [{"declaration": d} for d in agg.get("invariants", [])],
            })
        for cmd in bc.get("commands", []):
            cmd_temp = f"cmd:{cmd['name']}"
            items.append({
                "nodeLabel": "Command", "changeType": "CREATE",
                "nodeTitle": cmd["name"], "tempId": cmd_temp,
                "aggregateId": f"agg:{cmd['aggregate']}" if cmd.get("aggregate") else None,
                "fields": {"actor": cmd.get("actor") or "system"},
            })
            for evt in cmd.get("emits", []):
                items.append({
                    "nodeLabel": "Event", "changeType": "CREATE",
                    "nodeTitle": evt["name"], "tempId": f"evt:{evt['name']}",
                    "commandId": cmd_temp,
                    "fields": {"displayName": evt.get("displayName") or evt["name"]},
                })
        for rm in bc.get("readModels", []):
            items.append({
                "nodeLabel": "ReadModel", "changeType": "CREATE",
                "nodeTitle": rm, "tempId": f"rm:{bc['name']}:{rm}",
                "boundedContextId": bc_temp,
            })
        for idx, pol in enumerate(bc.get("policies", [])):
            item: dict[str, Any] = {
                "nodeLabel": "Policy", "changeType": "CREATE",
                "nodeTitle": pol["name"], "tempId": f"pol:{bc['name']}:{idx}",
                "boundedContextId": bc_temp,
            }
            if pol.get("trigger"):
                item["triggerEventId"] = f"evt:{pol['trigger']}"
            if pol.get("invoke"):
                item["invokeCommandId"] = f"cmd:{pol['invoke']}"
            items.append(item)
    return items


def count_model(model: dict) -> dict:
    bcs = model.get("boundedContexts", [])
    agg = sum(len(b.get("aggregates", [])) for b in bcs)
    cmd = sum(len(b.get("commands", [])) for b in bcs)
    evt = sum(len(c.get("emits", [])) for b in bcs for c in b.get("commands", []))
    pol = sum(len(b.get("policies", [])) for b in bcs)
    rm = sum(len(b.get("readModels", [])) for b in bcs)
    inv = sum(len(a.get("invariants", [])) for b in bcs for a in b.get("aggregates", []))
    spine = sum(1 for b in bcs for p in b.get("policies", [])
                if p.get("trigger") and p.get("invoke"))
    return {"boundedContexts": len(bcs), "aggregates": agg, "commands": cmd,
            "events": evt, "policies": pol, "readModels": rm, "invariants": inv,
            "spine": spine}


def clear_event_storming(session) -> dict:
    counts: dict[str, int] = {}
    for label in _ES_LABELS:
        r = session.run(f"MATCH (n:{label}) RETURN count(n) AS c").single()
        if r and r["c"]:
            counts[label] = r["c"]
    for label in reversed(_ES_LABELS):
        session.run(f"MATCH (n:{label}) DETACH DELETE n")
    return counts


def import_model(session, model: dict, mode: str = "replace") -> dict:
    """Apply the DesignModel to the graph. Returns a result summary."""
    cleared: dict = {}
    if mode == "replace":
        cleared = clear_event_storming(session)
    tactical = build_tactical_diff(model)
    ref_map: dict = {}
    applied = apply_tactical_diff(session, IMPORT_SOURCE, tactical, ref_map)
    return {
        "mode": mode,
        "applied": applied,
        "cleared": cleared,
        "counts": count_model(model),
        "warnings": model.get("warnings", []),
    }
