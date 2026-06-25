"""
Sandboxed filesystem helpers for the Claude Code IDE workspace.

Every filesystem-touching call from the workspace endpoints (`/tree`,
`/file` GET, `/file` PUT) MUST go through `resolve_under_root` first so the
sandbox check exists in exactly one place. See research D4 in
`specs/021-claude-code-ide-workspace/research.md`.
"""

from __future__ import annotations

import logging
import os
import secrets

from fastapi import HTTPException

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 2 * 1024 * 1024  # 2 MiB cap per FR-014
BINARY_SNIFF_BYTES = 8 * 1024


def resolve_under_root(root: str, path: str) -> str:
    """
    Sandbox check + path resolution.

    Computes the realpath of `os.path.join(root, path)` and verifies that
    the result is inside `realpath(root)`. Rejects absolute `path`, any
    `..` component, and any symlink target that escapes the root.

    Returns the resolved absolute path on success.
    Raises HTTPException(400) on sandbox violation, HTTPException(400)
    when `root` is not a directory.
    """
    if os.path.isabs(path):
        logger.warning(
            "claude_code.workspace.sandbox_violation",
            extra={"root": root, "path": path, "reason": "absolute_path"},
        )
        raise HTTPException(status_code=400, detail="path escapes project root")

    parts = path.replace("\\", "/").split("/") if path else []
    if any(p == ".." for p in parts):
        logger.warning(
            "claude_code.workspace.sandbox_violation",
            extra={"root": root, "path": path, "reason": "parent_component"},
        )
        raise HTTPException(status_code=400, detail="path escapes project root")

    real_root = os.path.realpath(os.path.expanduser(root))
    if not os.path.isdir(real_root):
        raise HTTPException(status_code=400, detail="root is not a directory")

    joined = os.path.join(real_root, path) if path else real_root
    resolved = os.path.realpath(joined)

    # Prefix check with separator to avoid /var/lib vs /var/library false positive.
    if resolved != real_root and not resolved.startswith(real_root + os.sep):
        logger.warning(
            "claude_code.workspace.sandbox_violation",
            extra={
                "root": root,
                "path": path,
                "resolved": resolved,
                "reason": "escapes_root",
            },
        )
        raise HTTPException(status_code=400, detail="path escapes project root")

    return resolved


def _is_binary(sample: bytes) -> bool:
    """Detect binary content: NUL byte or strict UTF-8 decode failure."""
    if b"\x00" in sample:
        return True
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def read_text_file(abs_path: str) -> tuple[str | None, int, int, bool]:
    """
    Read a file's content + metadata.

    Returns (content_or_None, size, mtime_ns, binary).
    Raises HTTPException(413) when file exceeds MAX_FILE_BYTES.
    Raises HTTPException(404) when the file does not exist.
    Raises HTTPException(403) on permission denied.
    """
    try:
        st = os.stat(abs_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail="file not found") from e
    except PermissionError as e:
        raise HTTPException(status_code=403, detail="permission denied") from e

    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail="not a file")

    if st.st_size > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail={"detail": "file too large to edit in browser", "size": st.st_size},
        )

    try:
        with open(abs_path, "rb") as f:
            sample = f.read(BINARY_SNIFF_BYTES)
            if _is_binary(sample):
                return (None, st.st_size, st.st_mtime_ns, True)
            # Not binary in the first 8 KB — read the rest and decode in full.
            rest = f.read()
    except PermissionError as e:
        raise HTTPException(status_code=403, detail="permission denied") from e

    try:
        text = (sample + rest).decode("utf-8")
    except UnicodeDecodeError:
        # Body had a non-UTF8 sequence past the sniff window; treat as binary.
        return (None, st.st_size, st.st_mtime_ns, True)

    return (text, st.st_size, st.st_mtime_ns, False)


def write_text_file_atomic(
    abs_path: str,
    content: str,
    expected_mtime_ns: int | None,
) -> tuple[int, int]:
    """
    Atomically write `content` to `abs_path` after an optimistic-concurrency
    check against `expected_mtime_ns`.

    - When `expected_mtime_ns is None`: the target file MUST NOT exist
      (otherwise raise HTTPException(400)).
    - When `expected_mtime_ns` is set: compare to the current
      `os.stat().st_mtime_ns`; on mismatch raise HTTPException(409) with
      `{current_mtime_ns, current_size}` in the detail body.

    Writes via `<basename>.tmp.<rand>` + fsync + atomic replace per
    contracts/rest-api.md.

    NOTE: the final step MUST be ``os.replace`` (not ``os.rename``). On POSIX
    ``os.rename`` atomically overwrites an existing destination, but on Windows
    it raises ``FileExistsError [WinError 183]`` when the destination already
    exists — so every save over an existing file failed there (the IDE surfaced
    it as "Failed to fetch"). ``os.replace`` overwrites atomically on both.

    Returns (new_size, new_mtime_ns).
    """
    parent = os.path.dirname(abs_path)
    if not os.path.isdir(parent):
        raise HTTPException(status_code=404, detail="parent directory not found")

    if expected_mtime_ns is None:
        if os.path.exists(abs_path):
            raise HTTPException(
                status_code=400,
                detail="expected_mtime_ns required for existing file",
            )
    else:
        try:
            st = os.stat(abs_path)
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail="file not found") from e
        except PermissionError as e:
            raise HTTPException(status_code=403, detail="permission denied") from e
        if st.st_mtime_ns != expected_mtime_ns:
            raise HTTPException(
                status_code=409,
                detail={
                    "detail": "file changed on disk since last read",
                    "current_mtime_ns": str(st.st_mtime_ns),
                    "current_size": st.st_size,
                },
            )

    payload = content.encode("utf-8")
    if len(payload) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail={"detail": "file too large to edit in browser", "size": len(payload)},
        )

    base = os.path.basename(abs_path)
    tmp_name = f"{base}.tmp.{secrets.token_hex(6)}"
    tmp_path = os.path.join(parent, tmp_name)

    # O_BINARY (Windows only; 0 elsewhere) is REQUIRED — without it Windows opens
    # the fd in text mode and translates every '\n' in `payload` into '\r\n' on
    # write, silently corrupting the editor's content (size grows, LF→CRLF) on
    # each save. We already hold UTF-8-encoded bytes, so the write must be raw.
    binary_flag = getattr(os, "O_BINARY", 0)
    try:
        fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | binary_flag, 0o644)
        try:
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp_path, abs_path)
    except PermissionError as e:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise HTTPException(status_code=403, detail="permission denied") from e
    except OSError:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    st = os.stat(abs_path)
    return (st.st_size, st.st_mtime_ns)


def delete_entry(abs_path: str) -> str:
    """Delete a file or directory at ``abs_path``.

    Returns the kind ("file" | "directory") that was deleted so the
    caller can echo it back to the UI.

    Refuses to delete the workspace root itself (caller should pass
    a non-empty `path`); refuses to follow a symlink target out of the
    sandbox (the caller has already passed the path through
    :func:`resolve_under_root` so the realpath is verified inside root).

    Raises HTTPException(404) when the path does not exist;
    HTTPException(403) on permission denied.
    """
    import shutil

    if not os.path.lexists(abs_path):
        raise HTTPException(status_code=404, detail="path not found")

    try:
        if os.path.islink(abs_path) or os.path.isfile(abs_path):
            os.remove(abs_path)
            return "file"
        if os.path.isdir(abs_path):
            shutil.rmtree(abs_path)
            return "directory"
    except PermissionError as e:
        raise HTTPException(status_code=403, detail="permission denied") from e
    except OSError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    raise HTTPException(status_code=400, detail="unsupported file type")


def move_entry(src_abs: str, dst_abs: str) -> str:
    """Move (rename) ``src_abs`` to ``dst_abs``.

    Both paths must have already been validated via :func:`resolve_under_root`.

    Returns the kind ("file" | "directory") that was moved.

    - Refuses to overwrite an existing destination (409).
    - Refuses when src == dst (400).
    - Refuses to move a directory into itself or a subpath of itself (400).
    - Parent directory of ``dst_abs`` must exist (404 otherwise).
    """
    if src_abs == dst_abs:
        raise HTTPException(status_code=400, detail="source and destination are identical")

    if not os.path.lexists(src_abs):
        raise HTTPException(status_code=404, detail="source not found")

    if os.path.lexists(dst_abs):
        raise HTTPException(status_code=409, detail="destination already exists")

    dst_parent = os.path.dirname(dst_abs)
    if not os.path.isdir(dst_parent):
        raise HTTPException(status_code=404, detail="destination parent not found")

    # Block moving a directory into itself or any descendant.
    if os.path.isdir(src_abs):
        src_with_sep = src_abs.rstrip(os.sep) + os.sep
        if dst_abs == src_abs or dst_abs.startswith(src_with_sep):
            raise HTTPException(
                status_code=400,
                detail="cannot move a directory into itself",
            )

    src_is_dir = os.path.isdir(src_abs) and not os.path.islink(src_abs)

    try:
        os.rename(src_abs, dst_abs)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail="permission denied") from e
    except OSError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return "directory" if src_is_dir else "file"


_HIDDEN_WHITELIST = {".claude", ".specify"}


def list_directory(abs_path: str) -> list[dict]:
    """
    List one level of children at `abs_path` per FR-016 filter rules.

    - Skip leading-`.` entries except `.claude` / `.specify`.
    - Skip `*.app` macOS bundles.
    - Sort directories first then files, case-insensitive within each group.

    Raises HTTPException(404) when the directory does not exist or is not
    a directory; HTTPException(403) on permission denied.
    """
    if not os.path.isdir(abs_path):
        raise HTTPException(status_code=404, detail="directory not found")

    try:
        entries = list(os.scandir(abs_path))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail="directory not found") from e
    except PermissionError as e:
        raise HTTPException(status_code=403, detail="permission denied") from e

    children: list[dict] = []
    for entry in entries:
        name = entry.name
        if name.startswith(".") and name not in _HIDDEN_WHITELIST:
            continue
        if name.endswith(".app"):
            continue
        try:
            is_dir = entry.is_dir()
        except OSError:
            continue
        children.append({"name": name, "type": "directory" if is_dir else "file"})

    # Directories first, then files; case-insensitive within each group.
    children.sort(key=lambda c: (c["type"] != "directory", c["name"].lower()))
    return children
