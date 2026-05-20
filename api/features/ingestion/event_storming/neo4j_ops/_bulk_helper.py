"""Shared infrastructure for bulk-create / bulk-link helpers in this package.

Every entity-specific `bulk_create_<entity>(rows)` helper composes the
primitives here:
    1. validate_required(rows, required_fields) — splits into (valid, errors)
    2. dedupe_by_key(rows, key_field)             — within-batch dedup + warn
    3. chunked(rows, INGESTION_BATCH_SIZE)         — iterator of sub-lists
    4. run_chunk(session, cypher, rows, return)    — one UNWIND transaction
    5. with_retry(fn)                              — one retry on transient err
    6. emit_flush_log(...) / maybe_snapshot(...)   — observability + debug
    7. reorder_to_input(...)                        — preserve 1:1 input order

The result of every helper is a `list[BulkResult]` mirroring `rows` 1:1, so
callers can `zip(rows, results, strict=True)` and react per-row.

Design notes (spec 018 § Decisions):
- Sequential chunking, not parallel — Neo4j locks serialize anyway.
- Pre-flush validation in Python; chunks only see clean rows.
- Per-row error capture; chunk-level rollback only on Neo4j-level failure.
- One SmartLogger event per helper call; per-row debug log lines on errors.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Iterator
from datetime import datetime, timezone
from typing import Any, TypedDict

from api.platform.env import (
    get_ingestion_batch_size,
    get_ingestion_snapshot_debug,
)
from api.platform.observability.smart_logger import SmartLogger


class BulkResult(TypedDict, total=False):
    ok: bool
    id: str | None
    key: str | None
    error: str | None
    error_field: str | None


# ─── Chunking ────────────────────────────────────────────────────────────


def chunked(rows: list[dict[str, Any]], size: int | None = None) -> Iterator[list[dict[str, Any]]]:
    """Yield rows in chunks of `size` (default `INGESTION_BATCH_SIZE` env)."""
    n = size if size is not None else get_ingestion_batch_size()
    if n <= 0:
        n = 1
    for i in range(0, len(rows), n):
        yield rows[i : i + n]


# ─── Validation ──────────────────────────────────────────────────────────


def validate_required(
    rows: list[dict[str, Any]],
    required: list[str],
) -> tuple[list[dict[str, Any]], list[BulkResult]]:
    """Split `rows` into (valid, error_results).

    A row is invalid if any required field is missing, None, or an empty
    string. Each invalid row contributes one BulkResult with `error_field`
    naming the first missing field.
    """
    valid: list[dict[str, Any]] = []
    errors: list[BulkResult] = []
    for row in rows:
        missing = next((f for f in required if not row.get(f)), None)
        if missing:
            errors.append(
                {
                    "ok": False,
                    "error": f"missing required field: {missing}",
                    "error_field": missing,
                    "id": row.get("id"),
                }
            )
        else:
            valid.append(row)
    return valid, errors


def dedupe_by_key(
    rows: list[dict[str, Any]],
    key_field: str,
    *,
    entity: str = "row",
) -> list[dict[str, Any]]:
    """Drop duplicates within a single batch by `key_field`. First occurrence
    wins. Logs a warning per duplicate so LLM-output anomalies are visible.
    """
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    dup_count = 0
    for row in rows:
        k = row.get(key_field)
        if k is None:
            out.append(row)
            continue
        if k in seen:
            dup_count += 1
            continue
        seen.add(k)
        out.append(row)
    if dup_count > 0:
        SmartLogger.log(
            "WARN",
            f"ingestion.batch.duplicate_key entity={entity} duplicates={dup_count}",
            category="ingestion.batch.duplicate_key",
            params={"entity": entity, "duplicates": dup_count, "keyField": key_field},
        )
    return out


# ─── Cypher execution ────────────────────────────────────────────────────


def run_chunk(
    session: Any,
    cypher: str,
    rows: list[dict[str, Any]],
    *,
    return_field: str = "result",
) -> list[dict[str, Any]]:
    """Run one `UNWIND $rows AS r ...` transaction and return the per-row
    Cypher RETURN value, in input order.

    Neo4j preserves UNWIND iteration order; the result rows come back 1:1.
    Raises on Neo4j-level errors (caller's `with_retry` decides retry).
    """
    if not rows:
        return []
    cursor = session.run(cypher, rows=rows)
    out: list[dict[str, Any]] = []
    for record in cursor:
        v = record.get(return_field) if record else None
        out.append(dict(v) if v else {})
    return out


def with_retry(fn: Callable[[], Any], *, retries: int = 1, backoff_s: float = 1.0) -> Any:
    """Retry `fn` once on transient Neo4j errors (timeout / unavailability /
    deadlock). Re-raises after the last attempt so the caller can convert
    chunk-level failure into per-row error results.
    """
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — driver's transient classes vary across versions
            name = type(exc).__name__
            transient = name in {
                "TransientError",
                "ServiceUnavailable",
                "SessionExpired",
                "WriteServiceUnavailable",
                "DatabaseError",
                "ClientError",  # some deadlocks surface here in older drivers
            } and any(
                hint in str(exc)
                for hint in ("DeadlockDetected", "Transaction", "timeout", "unavailable")
            )
            if attempt < retries and transient:
                SmartLogger.log(
                    "WARN",
                    f"ingestion.batch.chunk_retry attempt={attempt + 1} err={name}: {exc}",
                    category="ingestion.batch.chunk_retry",
                    params={"attempt": attempt + 1, "errorType": name, "error": str(exc)},
                )
                time.sleep(backoff_s)
                last_exc = exc
                continue
            raise
    if last_exc is not None:
        raise last_exc
    return None


# ─── Observability ───────────────────────────────────────────────────────


def emit_flush_log(
    entity: str,
    *,
    count: int,
    duration_ms: float,
    chunks: int,
    errors: int,
    session_id: str | None = None,
    phase: str | None = None,
) -> None:
    """Emit one SmartLogger event per `bulk_create_<entity>` call.

    Per-row error log lines are emitted separately at DEBUG by the caller
    (so production INFO logs stay quiet for the common no-error path).
    """
    SmartLogger.log(
        "INFO",
        f"ingestion.batch.{entity}.flush count={count} duration_ms={duration_ms:.1f} chunks={chunks} errors={errors}",
        category=f"ingestion.batch.{entity}.flush",
        params={
            "entity": entity,
            "count": count,
            "durationMs": round(duration_ms, 2),
            "chunks": chunks,
            "errorRows": errors,
            "sessionId": session_id,
            "phase": phase,
        },
    )


def maybe_snapshot(
    *,
    session_id: str | None,
    phase: str | None,
    entity: str,
    rows: list[dict[str, Any]],
) -> None:
    """When `INGESTION_SNAPSHOT_DEBUG=1`, write rows to
    `logs/ingestion-snapshots/<session_id>/<phase>.<entity>.json`. Best-effort.
    """
    if not get_ingestion_snapshot_debug():
        return
    if not session_id or not phase:
        return
    try:
        outdir = os.path.join("logs", "ingestion-snapshots", str(session_id))
        os.makedirs(outdir, exist_ok=True)
        path = os.path.join(outdir, f"{phase}.{entity}.json")
        payload = {
            "session_id": session_id,
            "phase": phase,
            "entity_type": entity,
            "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "rows": rows,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as exc:  # noqa: BLE001 — snapshot is best-effort
        SmartLogger.log(
            "WARN",
            f"ingestion.batch.snapshot_failed entity={entity} err={exc}",
            category="ingestion.batch.snapshot_failed",
            params={"entity": entity, "error": str(exc)},
        )


# ─── Result reassembly ───────────────────────────────────────────────────


def reorder_to_input(
    input_rows: list[dict[str, Any]],
    success_results: list[BulkResult],
    error_results: list[BulkResult],
    *,
    match_field: str | None = None,
) -> list[BulkResult]:
    """Rebuild a 1:1 result list aligned with `input_rows`.

    `success_results` are the per-row outcomes for rows that survived
    validation, in the same order as the validated subset. `error_results`
    are the validation rejects, with `id` (or another `match_field`) keyed
    back to inputs.

    Fast path when both lists came from a single straight-through pass:
    success_results length + error_results length == len(input_rows). We
    interleave them based on which rows were rejected by validation, in
    order of appearance.
    """
    # Use `id` if available; else `match_field`; else fall back to positional
    # (which works because validate_required preserves order).
    err_by_pos: dict[int, BulkResult] = {}
    if not error_results:
        return list(success_results)

    # Index errors back to original positions by walking input_rows in order
    # and matching each error against the next input row that has the same
    # rejected required field.
    err_iter = iter(error_results)
    success_iter = iter(success_results)
    field_for_match = match_field or "id"
    out: list[BulkResult] = []
    pending_err: BulkResult | None = next(err_iter, None)
    for row in input_rows:
        if pending_err is not None:
            err_id = pending_err.get("id") if pending_err.get("id") is not None else None
            row_id = row.get(field_for_match)
            # Match either by id (when present) or by position (fall-through).
            if err_id is not None and err_id == row_id:
                out.append(pending_err)
                pending_err = next(err_iter, None)
                continue
            if err_id is None:
                # Position-based match: this error belongs to the next input
                # row whose required field is missing — i.e. matches `row`
                # if `row` truly fails the same required-field check.
                missing = pending_err.get("error_field")
                if missing and not row.get(missing):
                    out.append(pending_err)
                    pending_err = next(err_iter, None)
                    continue
        # Otherwise consume one success row.
        nxt = next(success_iter, None)
        out.append(nxt if nxt is not None else {"ok": False, "error": "unaligned"})
    # Drain any leftover errors (shouldn't happen in normal flows).
    if pending_err is not None:
        out.append(pending_err)
    for extra in err_iter:
        out.append(extra)
    return out


# ─── Bulk-flush orchestrator (used by every entity helper) ───────────────


def bulk_flush(
    session_factory: Callable[[], Any],
    *,
    entity: str,
    rows: list[dict[str, Any]],
    cypher: str,
    return_field: str,
    required_fields: list[str],
    dedupe_key: str | None = None,
    session_id: str | None = None,
    phase: str | None = None,
) -> list[BulkResult]:
    """One-shot orchestrator: validate → dedupe → chunked flush → reassemble.

    Most entity-specific `bulk_create_<entity>` helpers can call straight
    through to this function, providing only the entity-specific bits
    (cypher, required fields, dedupe key). Helpers that need extra steps
    (e.g., key derivation via `event_key()`, two-pass relationship handling)
    do those steps before/after this call.
    """
    if not rows:
        return []

    started = time.perf_counter()
    valid, errors = validate_required(rows, required_fields)
    if dedupe_key:
        valid = dedupe_by_key(valid, dedupe_key, entity=entity)

    maybe_snapshot(session_id=session_id, phase=phase, entity=entity, rows=valid)

    success: list[BulkResult] = []
    chunk_count = 0
    chunk_failures = 0
    for chunk in chunked(valid):
        chunk_count += 1
        try:
            with session_factory() as session:
                rs = with_retry(lambda s=session, c=chunk: run_chunk(s, cypher, c, return_field=return_field))
            for row, r in zip(chunk, rs, strict=False):
                if not r:
                    success.append({"ok": False, "error": "no result row"})
                else:
                    success.append({"ok": True, **r})
        except Exception as exc:  # noqa: BLE001
            chunk_failures += 1
            SmartLogger.log(
                "ERROR",
                f"ingestion.batch.{entity}.chunk_failed err={exc}",
                category=f"ingestion.batch.{entity}.chunk_failed",
                params={"entity": entity, "error": str(exc), "chunkSize": len(chunk)},
            )
            for _row in chunk:
                success.append({"ok": False, "error": str(exc)})

    duration_ms = (time.perf_counter() - started) * 1000.0
    out = reorder_to_input(rows, success, errors)
    error_count = sum(1 for r in out if not r.get("ok"))
    emit_flush_log(
        entity,
        count=len(rows),
        duration_ms=duration_ms,
        chunks=chunk_count,
        errors=error_count,
        session_id=session_id,
        phase=phase,
    )
    return out
