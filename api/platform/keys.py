from __future__ import annotations

import re


_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_MULTI_DASH = re.compile(r"-{2,}")


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


