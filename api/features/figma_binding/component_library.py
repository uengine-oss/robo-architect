"""Figma component library scanner + catalog formatter (spec 024).

Reads the bound Figma file, finds every COMPONENT / COMPONENT_SET node,
fetches a thumbnail per component, asks a vision LLM for a 1-sentence
description, and persists `:FigmaComponent` rows attached to the singleton
binding.

Also exposes `get_catalog_for_prompt()` which formats the persisted catalog
for injection into the ingestion phase's UI-wireframe LLM prompt
(see `api/features/ingestion/workflow/phases/ui_wireframes.py`).
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from api.platform.observability.smart_logger import SmartLogger

from . import component_vlm, repository


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─── In-process scan-lock ──────────────────────────────────────────────────
# A single bound file means a singleton binding, so we just guard with a
# module-level boolean. Concurrent callers see a 409 immediately.

_scan_in_flight: bool = False


def _claim_scan_slot() -> bool:
    global _scan_in_flight
    if _scan_in_flight:
        return False
    _scan_in_flight = True
    return True


def _release_scan_slot() -> None:
    global _scan_in_flight
    _scan_in_flight = False


# ─── Live progress state ───────────────────────────────────────────────────
# Single-binding ⇒ single progress slot. The SSE endpoint polls a version
# counter; the scan bumps it on every meaningful step (phase change, item
# completed). One asyncio.Event re-armed per bump notifies any waiters
# without per-subscriber queues.

_progress: dict[str, Any] = {
    "phase": "idle",          # idle | fetching | thumbnails | describing | persisting | done | error
    "total": 0,               # discovered component count (set after fetch)
    "described": 0,           # VLM completions so far
    "scanned": 0,             # DB upserts so far
    "lastItem": "",           # most recent component name
    "lastDescription": "",    # most recent VLM sentence (truncated)
    "error": None,            # error message when phase == "error"
    "result": None,           # final summary when phase == "done"
    "version": 0,             # monotonic — drives SSE wake-ups
    "startedAt": None,
}
_progress_event: asyncio.Event = asyncio.Event()


def _set_progress(**kwargs: Any) -> None:
    """Update the progress snapshot and wake any SSE subscribers.

    `version` is auto-incremented; callers pass real fields only.
    """
    _progress.update(kwargs)
    _progress["version"] = int(_progress.get("version", 0)) + 1
    # set→clear is cheap; subscribers that called `await event.wait()` will
    # immediately observe the set and proceed to read the snapshot.
    _progress_event.set()
    _progress_event.clear()


def get_progress_snapshot() -> dict[str, Any]:
    """Return a shallow copy of the current progress state. Public for router."""
    return dict(_progress)


async def wait_for_progress(last_version: int, timeout: float = 15.0) -> bool:
    """Block until `version > last_version` or timeout. Returns True if updated."""
    if _progress.get("version", 0) > last_version:
        return True
    try:
        await asyncio.wait_for(_progress_event.wait(), timeout=timeout)
        return True
    except asyncio.TimeoutError:
        return False


# ─── Public scan entrypoint ────────────────────────────────────────────────


async def scan_components(
    *, components: list[dict[str, Any]], actor: str
) -> dict[str, Any]:
    """Persist a plugin-pushed component scan and run VLM description.

    The Figma plugin walks ``figma.root.findAll(n => n.type === 'COMPONENT'
    || n.type === 'COMPONENT_SET')`` and ships each node with its rendered
    PNG (``node.exportAsync({format:'PNG'})``) as base64. We just decode +
    describe + persist — no Figma REST call, no API token.

    Each ``components`` item:
        {figmaNodeId, name, pageName, widthPx, heightPx, pngBase64}

    Raises HTTPException(404) when no active binding, (409) when a scan is
    already in flight.
    """
    binding = repository.get_active_binding()
    if not binding:
        raise HTTPException(
            status_code=404,
            detail={"error": "no_active_binding", "messageKr": "활성화된 Figma 바인딩이 없습니다"},
        )

    if not _claim_scan_slot():
        raise HTTPException(
            status_code=409,
            detail={"error": "scan_in_progress", "messageKr": "이미 컴포넌트 스캔이 진행 중입니다"},
        )

    started = time.monotonic()
    file_key = binding["figmaFileKey"]

    SmartLogger.log(
        "INFO",
        f"figma_binding.components.scan.start file_key={file_key} actor={actor} pushed={len(components)}",
        category="figma_binding.components.scan.start",
        params={"fileKey": file_key, "actor": actor, "pushed": len(components)},
    )

    _set_progress(
        phase="describing" if components else "persisting",
        total=len(components),
        described=0,
        scanned=0,
        lastItem="",
        lastDescription="",
        error=None,
        result=None,
        startedAt=_now_iso(),
    )

    try:
        # Plugin already supplied PNG bytes inline — build data URIs and let
        # the VLM describe them directly (no HTTP fetch).
        described: dict[str, str] = {}
        if components:
            name_by_id = {c["figmaNodeId"]: c.get("name", "") for c in components}

            def _on_vlm_each(nid: str, desc: str) -> None:
                described_count = int(_progress.get("described", 0)) + 1
                _set_progress(
                    phase="describing",
                    described=described_count,
                    lastItem=name_by_id.get(nid, nid),
                    lastDescription=(desc or "")[:140],
                )

            vlm_inputs: list[tuple[str, str, str]] = []
            for c in components:
                png = c.get("pngBase64") or ""
                if not png:
                    continue
                # The VLM helper detects data: URIs and skips its download path.
                vlm_inputs.append((
                    c["figmaNodeId"],
                    c.get("name", ""),
                    f"data:image/png;base64,{png}",
                ))
            if vlm_inputs:
                described = await component_vlm.describe_components(
                    vlm_inputs, on_each=_on_vlm_each
                )

        _set_progress(phase="persisting", scanned=0)
        existing = {c["figmaNodeId"]: c for c in repository.list_figma_components(file_key)}
        added = 0
        updated = 0
        vlm_described = 0
        vlm_failures = 0
        for comp in components:
            nid = comp["figmaNodeId"]
            desc = described.get(nid, "")
            if desc:
                vlm_described += 1
            else:
                vlm_failures += 1
            repository.upsert_figma_component(
                binding_file_key=file_key,
                figma_node_id=nid,
                name=comp.get("name", "") or nid,
                page_name=comp.get("pageName", "") or "",
                width_px=int(comp.get("widthPx", 0) or 0),
                height_px=int(comp.get("heightPx", 0) or 0),
                vlm_description=desc,
                figma_key=comp.get("figmaKey"),
                figma_node_last_modified=comp.get("figmaNodeLastModified"),
            )
            if nid in existing:
                updated += 1
            else:
                added += 1
            _set_progress(
                phase="persisting",
                scanned=added + updated,
                lastItem=comp.get("name", "") or nid,
            )

        kept_ids = [c["figmaNodeId"] for c in components]
        removed = repository.delete_stale_figma_components(file_key, kept_ids)

        component_count = repository.count_figma_components(file_key)
        duration_ms = int((time.monotonic() - started) * 1000)

        SmartLogger.log(
            "INFO",
            (
                f"figma_binding.components.scan.done file_key={file_key} "
                f"scanned={len(components)} added={added} updated={updated} "
                f"removed={removed} vlm_ok={vlm_described} vlm_fail={vlm_failures} "
                f"duration_ms={duration_ms}"
            ),
            category="figma_binding.components.scan.done",
            params={
                "fileKey": file_key,
                "scanned": len(components),
                "added": added,
                "updated": updated,
                "removed": removed,
                "vlmDescribed": vlm_described,
                "vlmFailures": vlm_failures,
                "componentCount": component_count,
                "durationMs": duration_ms,
            },
        )

        result = {
            "scanned": len(components),
            "added": added,
            "updated": updated,
            "removed": removed,
            "vlmDescribed": vlm_described,
            "vlmFailures": vlm_failures,
            "componentCount": component_count,
            "durationMs": duration_ms,
        }
        _set_progress(
            phase="done",
            scanned=len(components),
            described=vlm_described,
            total=len(components),
            result=result,
        )
        return result
    except HTTPException as e:
        _set_progress(phase="error", error=str(e.detail))
        raise
    except Exception as e:  # noqa: BLE001
        _set_progress(phase="error", error=str(e))
        raise
    finally:
        _release_scan_slot()


# ─── Catalog for ingestion-phase prompt injection ──────────────────────────


def get_catalog_for_prompt() -> str:
    """Return a human-readable catalog string for LLM injection.

    Empty string if no components are scanned for the active binding —
    caller should treat that as "fallback to generic Figma mode".
    """
    rows = repository.list_figma_components()
    if not rows:
        return ""

    by_page: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_page.setdefault(r.get("pageName") or "(unnamed page)", []).append(r)

    lines: list[str] = []
    lines.append("Available components (from the bound Figma design system):")
    lines.append(
        "When you reference one, use its exact `name` (case-insensitive)."
    )
    lines.append("")
    for page in sorted(by_page.keys()):
        lines.append(f"### Page: {page}")
        for r in sorted(by_page[page], key=lambda x: (x.get("name") or "").lower()):
            name = r.get("name") or ""
            desc = (r.get("vlmDescription") or "").strip() or "(no description)"
            w = r.get("widthPx") or 0
            h = r.get("heightPx") or 0
            lines.append(f"- {name} ({w}×{h}px): {desc}")
        lines.append("")
    return "\n".join(lines)


def list_components() -> list[dict[str, Any]]:
    """Public listing for the GET /components endpoint."""
    rows = repository.list_figma_components()
    out: list[dict[str, Any]] = []
    for r in rows:
        # Normalize Neo4j datetime to ISO string if needed.
        scanned = r.get("scannedAt")
        if scanned is not None and not isinstance(scanned, str):
            scanned = str(scanned)
        out.append(
            {
                "id": r.get("id"),
                "figmaNodeId": r.get("figmaNodeId"),
                "name": r.get("name"),
                "pageName": r.get("pageName"),
                "widthPx": r.get("widthPx"),
                "heightPx": r.get("heightPx"),
                "vlmDescription": r.get("vlmDescription") or "",
                "figmaKey": r.get("figmaKey"),
                "scannedAt": scanned,
            }
        )
    return out


def clear_components() -> int:
    """Hard-delete every :FigmaComponent for the active binding."""
    return repository.delete_figma_components()


def get_figma_node_id_by_name(name: str) -> str | None:
    """Resolve a component name → figmaNodeId for sceneGraph construction.

    Case-insensitive exact match first, then case-insensitive substring
    match (mirrors the plugin's componentCache lookup heuristic).
    """
    if not name:
        return None
    needle = name.strip().lower()
    if not needle:
        return None
    rows = repository.list_figma_components()
    if not rows:
        return None
    for r in rows:
        if (r.get("name") or "").strip().lower() == needle:
            return r.get("figmaNodeId")
    for r in rows:
        rn = (r.get("name") or "").strip().lower()
        if rn and (needle in rn or rn in needle):
            return r.get("figmaNodeId")
    return None


# Lookup table accessor used by callers that need many resolutions at once.
def build_name_to_node_index() -> dict[str, dict[str, Any]]:
    """{lowercased_name: {figmaNodeId, widthPx, heightPx}} for the active binding."""
    rows = repository.list_figma_components()
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        n = (r.get("name") or "").strip().lower()
        if not n:
            continue
        out[n] = {
            "figmaNodeId": r.get("figmaNodeId"),
            "name": r.get("name"),
            "widthPx": r.get("widthPx") or 0,
            "heightPx": r.get("heightPx") or 0,
        }
    return out


# ─── 024: JSX → sceneGraph integration ────────────────────────────────────


INSTANCE_MARKER_PREFIX = "$INSTANCE:"


def build_jsx_agent_extra_context(catalog_for_prompt: str | None = None) -> str:
    """Build the `extra_context` blob to pass to ai_design.run_render_agent
    so the LLM knows which components it may instantiate and the marker
    convention (a leaf <Frame name="$INSTANCE:Name|k=v|..." w={w} h={h} />).
    """
    catalog = catalog_for_prompt if catalog_for_prompt is not None else get_catalog_for_prompt()
    if not catalog:
        return ""
    return (
        "## Bound Figma design-system components (use these when one clearly fits)\n\n"
        f"{catalog}\n"
        "## How to USE a catalog component in your JSX\n\n"
        "Emit a LEAF <Frame> with a special name prefix `$INSTANCE:` followed by the exact catalog name.\n"
        "Add text overrides after a `|` separator, k=v pairs. Example:\n\n"
        "```\n"
        '<Frame name="$INSTANCE:input-search|placeholder=상품을 검색하세요" w="fill" h={48} />\n'
        '<Frame name="$INSTANCE:btn-main-task|text=장바구니에 추가|label=장바구니에 추가" w="fill" h={56} />\n'
        "```\n\n"
        "Rules:\n"
        "- Marker frames must be LEAVES (no children) — the plugin instantiates the real component there.\n"
        "- Use the exact catalog name (case-insensitive). Wrong names render as empty placeholders.\n"
        "- **IMPORTANT — INSTANCE sizing**: the W×H numbers in the catalog above are the\n"
        "  Figma DOCUMENTATION PAGE bbox of the COMPONENT_SET (which stacks all variants\n"
        "  vertically and is therefore many times larger than a real instance). When you\n"
        "  emit the marker, DO NOT echo those numbers. Use realistic INSTANCE sizes:\n"
        "  - input fields: `w=\"fill\"` `h={48}`\n"
        "  - primary buttons (btn-main-*): `w=\"fill\"` `h={56}`\n"
        "  - small/icon buttons: `w={48}` `h={48}` (or close)\n"
        "  - cards (com-card-*): `w=\"fill\"` and a height proportional to content — start with `h={88}` for a product row, `h={160}` for a thumbnail card.\n"
        "  - thumbnails (thumb-*): roughly the catalog's reported W but `h` close to W.\n"
        "  - top bars / headers: `w=\"fill\"` `h={56}` to `h={72}`.\n"
        "  - tab bars / footers: `w=\"fill\"` `h={56}`.\n"
        "- **Override keys** — common ones the plugin recognises out of the box:\n"
        "  `text`, `label`, `title`, `placeholder` (fallback to first TEXT child).\n"
        "  Use Korean values when the screen is Korean.\n"
        "  Example: a primary CTA → `|label=장바구니에 추가|text=장바구니에 추가`\n"
        "  (pass both keys; the plugin tries variant-property names + direct text-node names).\n"
        "- For UI that has NO suitable catalog entry (dynamic lists, status banners, custom layouts), use regular <Frame>/<Text>/<Rectangle>/<Icon> elements as the JSX guide says.\n"
        "- Prefer catalog instances for: top bars, primary buttons, inputs/search fields, badges/chips, list rows, when a fitting catalog entry exists.\n"
    )


def retype_instance_markers(
    scene_graph: dict[str, Any] | None,
    name_index: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """In-place post-process: convert FRAME nodes named '$INSTANCE:Name|k=v|…'
    into proper INSTANCE leaves the Figma plugin can instantiate.

    Returns the (mutated) sceneGraph and a counts dict:
        {"retyped": int, "instance_names": [str], "unresolved": [str]}
    """
    if not scene_graph or not isinstance(scene_graph, dict):
        return scene_graph, {"retyped": 0, "instance_names": [], "unresolved": []}
    if name_index is None:
        name_index = build_name_to_node_index()

    nodes = scene_graph.get("nodes")
    if not isinstance(nodes, dict):
        return scene_graph, {"retyped": 0, "instance_names": [], "unresolved": []}

    retyped = 0
    instance_names: list[str] = []
    unresolved: list[str] = []

    for nid, n in nodes.items():
        if not isinstance(n, dict):
            continue
        name = n.get("name") or ""
        if not isinstance(name, str) or not name.startswith(INSTANCE_MARKER_PREFIX):
            continue

        rest = name[len(INSTANCE_MARKER_PREFIX):].strip()
        # Parse "Name|k=v|k=v"
        parts = [p for p in rest.split("|") if p]
        comp_name = parts[0].strip() if parts else ""
        overrides: dict[str, str] = {}
        for kv in parts[1:]:
            if "=" in kv:
                k, _, v = kv.partition("=")
                k = k.strip()
                v = v.strip()
                if k:
                    overrides[k] = v

        if not comp_name:
            unresolved.append(name)
            continue

        # Resolve against the catalog index (lowercased exact, then substring).
        key = comp_name.lower()
        entry = name_index.get(key)
        if not entry:
            for k, v in name_index.items():
                if k and (key in k or k in key):
                    entry = v
                    break
        if not entry:
            unresolved.append(comp_name)
            continue

        # Retype the node to INSTANCE; clean name; set componentId + overrides;
        # clear children (plugin doesn't recurse into INSTANCE).
        n["type"] = "INSTANCE"
        n["name"] = entry.get("name") or comp_name
        n["componentId"] = entry.get("figmaNodeId") or ""
        # Merge with any existing overrides on the node.
        existing = n.get("overrides") if isinstance(n.get("overrides"), dict) else {}
        n["overrides"] = {**existing, **overrides}
        n["childIds"] = []
        retyped += 1
        instance_names.append(n["name"])

    return scene_graph, {
        "retyped": retyped,
        "instance_names": instance_names,
        "unresolved": unresolved,
    }
