"""Slug derivation, output-path resolution, atomic-create with file lock,
stale-asset detection. Per research D5.

All write targets are asserted under ``specs/`` via ``os.path.realpath``
before any file handle opens; anything outside is a hard error
(``path_escape``).
"""
from __future__ import annotations

import contextlib
import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import Iterator

try:
    import fcntl  # POSIX
    _HAS_FCNTL = True
except ImportError:  # Windows has no fcntl; fall back to msvcrt byte-range locks
    fcntl = None  # type: ignore[assignment]
    _HAS_FCNTL = False
    import msvcrt

from slugify import slugify


# Project layout anchors.
# ``BASE_DIR`` is the repo root (../../../.. from this file).
BASE_DIR: Path = Path(__file__).resolve().parents[3]
SPECS_DIR: Path = BASE_DIR / "specs"
BC_ROOT: Path = SPECS_DIR / "bounded-contexts"
LOCK_PATH: Path = BC_ROOT / ".ddd-spec.lock"


class PathEscapeError(Exception):
    """A computed write path resolved outside ``specs/``."""


def _normalized_slug(name: str) -> str:
    """python-slugify wrapper with the project-wide options."""
    return slugify(
        name or "",
        lowercase=True,
        separator="-",
        max_length=40,
        word_boundary=True,
    )


def _hash_suffix(source_id: str) -> str:
    return hashlib.sha1(source_id.encode("utf-8")).hexdigest()[:6]


def derive_slug(name: str, source_id: str) -> str:
    """ASCII-safe slug from ``name``; fall back to a 6-char hash of
    ``source_id`` when slugify produces an empty result.
    """
    base = _normalized_slug(name)
    if base:
        return base
    return _hash_suffix(source_id or name or "x")


def unique_slug(name: str, source_id: str, taken: set[str]) -> str:
    """Like :func:`derive_slug`, but suffix-hashes on collision within ``taken``.
    Mutates ``taken`` to include the returned slug.
    """
    candidate = derive_slug(name, source_id)
    if candidate in taken:
        candidate = f"{candidate}-{_hash_suffix(source_id)}"
    taken.add(candidate)
    return candidate


def assert_under_specs(path: os.PathLike[str] | str) -> Path:
    """Resolve ``path`` and assert it lives under ``realpath(specs/)``."""
    target = Path(os.path.realpath(str(path)))
    base = Path(os.path.realpath(str(SPECS_DIR)))
    try:
        target.relative_to(base)
    except ValueError as e:
        raise PathEscapeError(
            f"Refusing to write outside specs/: {target} (base={base})"
        ) from e
    return target


def bc_dir(bc_slug: str) -> Path:
    """The folder for one BC's artifacts."""
    return assert_under_specs(BC_ROOT / bc_slug)


def aggregates_dir(bc_slug: str) -> Path:
    return assert_under_specs(BC_ROOT / bc_slug / "aggregates")


def assets_dir(bc_slug: str) -> Path:
    return assert_under_specs(BC_ROOT / bc_slug / "requirements.assets")


def context_map_path() -> Path:
    return assert_under_specs(SPECS_DIR / "context-map.md")


def frontend_dir() -> Path:
    """``specs/frontend/`` — the sibling of ``specs/bounded-contexts/`` that
    holds the frontend perspective artifacts (US5).

    Sandboxed by :func:`assert_under_specs`; same atomic-write + lock
    machinery applies.
    """
    return assert_under_specs(SPECS_DIR / "frontend")


# --- atomic write --------------------------------------------------------


def atomic_write_text(target: Path, text: str, *, overwrite: bool) -> bool:
    """Write ``text`` to ``target`` via tempfile+os.replace.

    Returns True if the file was written, False if it pre-existed and
    ``overwrite=False`` (caller records as skipped).
    """
    assert_under_specs(target)
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists() and not overwrite:
        return False

    fd, tmp_path = tempfile.mkstemp(
        prefix=target.name + ".", suffix=".tmp", dir=str(target.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp_path, target)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_path)
    return True


def atomic_write_bytes(target: Path, data: bytes, *, overwrite: bool) -> bool:
    assert_under_specs(target)
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists() and not overwrite:
        return False

    fd, tmp_path = tempfile.mkstemp(
        prefix=target.name + ".", suffix=".tmp", dir=str(target.parent)
    )
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp_path, target)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_path)
    return True


# --- locking --------------------------------------------------------------


@contextlib.contextmanager
def ddd_spec_lock() -> Iterator[None]:
    """Process-level fcntl.flock on ``specs/bounded-contexts/.ddd-spec.lock``.

    Raises ``BlockingIOError`` if held elsewhere — callers map this to a
    409 ``lock_busy`` response.
    """
    BC_ROOT.mkdir(parents=True, exist_ok=True)
    LOCK_PATH.touch(exist_ok=True)
    if _HAS_FCNTL:
        with open(LOCK_PATH, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                with contextlib.suppress(Exception):
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    else:
        # Windows: emulate a non-blocking exclusive lock with msvcrt.
        # msvcrt.locking needs at least one byte in the file to lock.
        with open(LOCK_PATH, "a+b") as f:
            if os.fstat(f.fileno()).st_size == 0:
                f.write(b"\0")
                f.flush()
            f.seek(0)
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as e:
                # Match the POSIX LOCK_NB contract callers map to 409 lock_busy.
                raise BlockingIOError(str(e)) from e
            try:
                yield
            finally:
                with contextlib.suppress(Exception):
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)


# --- staging --------------------------------------------------------------


@contextlib.contextmanager
def staging_dir(prefix: str = "ddd-spec-stage-") -> Iterator[Path]:
    """Temporary directory under the system tempdir, removed on exit."""
    path = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        yield path
    finally:
        with contextlib.suppress(FileNotFoundError):
            shutil.rmtree(path)


# --- stale-asset detection -----------------------------------------------


def detect_stale_assets(bc_slug: str, referenced_asset_paths: set[Path]) -> list[Path]:
    """Files under ``requirements.assets/`` that are not referenced by the
    freshly-rendered ``requirements.md`` (reported, not deleted).
    """
    folder = assets_dir(bc_slug)
    if not folder.exists():
        return []
    referenced = {p.resolve() for p in referenced_asset_paths}
    stale: list[Path] = []
    for entry in folder.iterdir():
        if entry.is_file() and entry.resolve() not in referenced:
            stale.append(entry)
    stale.sort()
    return stale
