from __future__ import annotations

import re
import uuid


_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_MULTI_DASH = re.compile(r"-{2,}")

# Project-stable namespace for deterministic uuid5() ids on UI-flow artifacts (spec 025).
# Generated once; do not change — changing this would re-id every existing edge on re-ingest.
_UI_FLOW_NS = uuid.UUID("6f1a3b78-2c4d-5e69-8f01-9b2d3c4e5f60")


def slugify(value: str) -> str:
    """
    Make a stable, URL-ish slug used for natural keys.

    - lower-case
    - non [a-z0-9] => '-'
    - collapse duplicate '-'
    - strip leading/trailing '-'
    """
    s = (value or "").strip().lower()
    if not s:
        return "unnamed"
    s = _NON_ALNUM.sub("-", s)
    s = _MULTI_DASH.sub("-", s).strip("-")
    return s or "unnamed"


def bc_key(name: str) -> str:
    return slugify(name)


def aggregate_key(bc_key_value: str, aggregate_name: str) -> str:
    return f"{slugify(bc_key_value)}.{slugify(aggregate_name)}"


def command_key(aggregate_key_value: str, command_name: str) -> str:
    return f"{aggregate_key_value}.{slugify(command_name)}"


def event_key(command_key_value: str, event_name: str, version: str) -> str:
    v = (version or "").strip() or "1.0.0"
    return f"{command_key_value}.{slugify(event_name)}@{v}"


def readmodel_key(bc_key_value: str, readmodel_name: str) -> str:
    return f"{slugify(bc_key_value)}.{slugify(readmodel_name)}"


def policy_key(target_bc_key_value: str, policy_name: str) -> str:
    return f"{slugify(target_bc_key_value)}.{slugify(policy_name)}"


def ui_key(attached_to_type: str, attached_to_id: str) -> str:
    t = slugify(attached_to_type or "target")
    return f"ui.{t}.{attached_to_id}"


def feature_key(bc_key_value: str, feature_name: str) -> str:
    """Natural key for a :Feature node, scoped to its owning BC (026)."""
    return f"{slugify(bc_key_value)}.feature.{slugify(feature_name)}"


def _short_hash(value: str) -> str:
    """Stable 12-hex BLAKE2 digest — keeps non-ASCII (Korean) labels distinct
    where `slugify` alone would collapse them all to "unnamed"."""
    import hashlib

    return hashlib.blake2b((value or "").strip().lower().encode("utf-8"), digest_size=6).hexdigest()


def invariant_key(aggregate_key_value: str, declaration: str) -> str:
    """Natural key for an :Invariant node, scoped to its owning Aggregate (027).

    The declaration is a free-form sentence (often Korean) on which `slugify`
    alone collapses to "unnamed", so a short content hash is appended to keep
    distinct invariants distinct while staying idempotent on re-ingest.
    """
    return (
        f"{aggregate_key_value}.invariant."
        f"{slugify(declaration)}-{_short_hash(declaration)}"
    )


# ── spec 025 v3 — Journey / JourneyStep node model ──────────────────────
#
# A user journey is a first-class :Journey node owning ordered :JourneyStep
# nodes. A step is either a 'screen' (SHOWS a shared :UI) or a 'gateway'
# (a branch diamond). Steps are connected by :NEXT edges (which carry the
# branch condition) — the flow stays edge-based so branching is expressible.


def journey_slug(journey_name: str) -> str:
    """Stable slug for a user journey — used for grouping/filtering on the
    frontend and as part of node keys."""
    return f"{slugify(journey_name)}-{_short_hash(journey_name)}"


def journey_key(bc_key_value: str, journey_name: str) -> str:
    """Natural key for a :Journey node, scoped to its owning BC."""
    return f"{slugify(bc_key_value)}.journey.{journey_slug(journey_name)}"


def journey_node_id(journey_key_value: str) -> str:
    """Deterministic UUID5 for a :Journey given its natural key."""
    return str(uuid.uuid5(_UI_FLOW_NS, journey_key_value))


def journey_step_key(journey_key_value: str, kind: str, ref: str) -> str:
    """Natural key for a :JourneyStep within a journey.

    `ref` is the UI id for a 'screen' step (one step per (journey, screen)),
    or the label for a 'gateway' step.
    """
    k = (kind or "screen").strip().lower()
    if k == "gateway":
        ref_part = f"{slugify(ref)}-{_short_hash(ref)}"
    else:
        ref_part = slugify(ref) or _short_hash(ref)
    return f"{journey_key_value}.step.{k}.{ref_part}"


def journey_step_id(step_key_value: str) -> str:
    """Deterministic UUID5 for a :JourneyStep given its natural key."""
    return str(uuid.uuid5(_UI_FLOW_NS, step_key_value))


def next_step_id(src_step_key: str, tgt_step_key: str, condition: str) -> str:
    """Deterministic UUID5 for a :NEXT edge between two journey steps."""
    payload = f"{src_step_key}->{tgt_step_key}#{slugify(condition or '')}"
    return str(uuid.uuid5(_UI_FLOW_NS, payload))


