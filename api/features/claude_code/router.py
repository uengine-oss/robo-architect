"""
Claude Code Terminal WebSocket endpoint + project setup.

Spawns a PTY session running `claude` CLI and bridges it
to the browser via WebSocket (JSON messages for input/resize,
raw text for output).
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import signal
import struct
import zipfile

import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from api.features.claude_code.workspace_fs import (
    list_directory,
    read_text_file,
    resolve_under_root,
    write_text_file_atomic,
)
from api.features.claude_code.workspace_schemas import (
    FileResponse as WorkspaceFileResponse,
)
from api.features.claude_code.workspace_schemas import (
    FileWriteRequest,
    FileWriteResponse,
    TreeChild,
    TreeResponse,
)
from api.features.prd_generation.prd_api_contracts import PRDGenerationRequest

router = APIRouter(prefix="/api/claude-code", tags=["claude-code"])

logger = logging.getLogger(__name__)

IS_UNIX_PTY_SUPPORTED = os.name == "posix"

if IS_UNIX_PTY_SUPPORTED:
    import fcntl
    import pty
    import termios


# ─── Directory browsing ───


@router.get("/browse-directory")
async def browse_directory(path: str = "~"):
    """
    List directories under the given path for the folder picker UI.
    Returns the resolved absolute path and its subdirectories.
    """
    resolved = os.path.expanduser(path)
    resolved = os.path.abspath(resolved)

    if not os.path.isdir(resolved):
        # Try parent if path doesn't exist yet
        parent = os.path.dirname(resolved)
        if os.path.isdir(parent):
            resolved = parent
        else:
            resolved = os.path.expanduser("~")

    dirs = []
    try:
        for entry in sorted(os.scandir(resolved), key=lambda e: e.name.lower()):
            if entry.is_dir() and not entry.name.startswith(".") and not entry.name.endswith(".app"):
                dirs.append(entry.name)
    except PermissionError:
        pass

    # Also provide parent path for navigation
    parent = os.path.dirname(resolved) if resolved != "/" else None

    return {
        "current_path": resolved,
        "parent_path": parent,
        "directories": dirs,
    }


# ─── IDE workspace: file tree + read/write (feature 021) ───


@router.get("/tree", response_model=TreeResponse)
async def workspace_tree(root: str, path: str = ""):
    """List one level of children at `root + path` for the IDE workspace tree."""
    resolved = resolve_under_root(root, path)
    children = list_directory(resolved)
    if path == "":
        logger.info(
            "claude_code.workspace.tree_root_listed",
            extra={"root": root, "child_count": len(children)},
        )
    return TreeResponse(
        root=os.path.realpath(os.path.expanduser(root)),
        path=path,
        children=[TreeChild(**c) for c in children],
    )


@router.get("/file", response_model=WorkspaceFileResponse)
async def workspace_read_file(root: str, path: str):
    """Read a single file's content + metadata for the IDE workspace editor."""
    resolved = resolve_under_root(root, path)
    content, size, mtime_ns, binary = read_text_file(resolved)
    return WorkspaceFileResponse(
        path=path,
        size=size,
        mtime_ns=str(mtime_ns),
        binary=binary,
        content=content,
        encoding="utf-8",
    )


@router.put("/file", response_model=FileWriteResponse)
async def workspace_write_file(req: FileWriteRequest):
    """Save a file's contents with optimistic-concurrency check via mtime_ns."""
    resolved = resolve_under_root(req.root, req.path)
    expected = int(req.expected_mtime_ns) if req.expected_mtime_ns else None
    new_size, new_mtime_ns = write_text_file_atomic(resolved, req.content, expected)
    return FileWriteResponse(
        path=req.path,
        size=new_size,
        mtime_ns=str(new_mtime_ns),
    )


# ─── Project setup (extract PRD to target directory) ───


class SetupProjectRequest(BaseModel):
    """Extract generated PRD files to a target directory for Claude Code."""
    project_path: str
    prd_request: PRDGenerationRequest


@router.post("/setup-project")
async def setup_project(request: SetupProjectRequest):
    """
    Generate PRD files and extract them to the specified project directory.
    Returns the resolved absolute path.

    Uses the shared :func:`api.features.prd_generation.routes.prd_export.build_prd_zip`
    helper so the on-disk artifact set produced here is **bit-identical**
    to the one ``/api/prd/download`` ships — no per-BC agent files, no
    ``Frontend-PRD.md``, no ``.scene.json`` sidecars, role-based agents
    + ``/generate-frontend`` command emitted when applicable, and the
    PRD↔CLAUDE / PRD↔.cursorrules disjointness lint enforced (hard
    abort on violation).
    """
    from fastapi import HTTPException

    from api.features.prd_generation.prd_model_data import get_bcs_from_nodes
    from api.features.prd_generation.prd_split_lint import PrdSplitLintError
    from api.features.prd_generation.routes.prd_export import (
        _require_frontend_framework,
        build_prd_zip,
    )

    # Enforce FR-020 — when include_frontend=true, frontend_framework
    # MUST be set. Same contract as /api/prd/{generate,download}.
    _require_frontend_framework(request.prd_request.tech_stack)

    # Resolve and validate path
    project_path = os.path.expanduser(request.project_path)
    project_path = os.path.abspath(project_path)

    # Create directory if it doesn't exist
    os.makedirs(project_path, exist_ok=True)

    bcs = get_bcs_from_nodes(None)
    if not bcs:
        raise HTTPException(status_code=404, detail="No Bounded Contexts found")

    config = request.prd_request.tech_stack

    # Build ZIP in memory via the shared helper.
    zip_buffer = io.BytesIO()
    try:
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            build_prd_zip(zf, bcs, config)
    except PrdSplitLintError as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": e.code,
                "file": e.offending_file,
                "substring": e.offending_substring,
                "offset": e.offset,
                "message": str(e),
            },
        )

    # Remove legacy files that older setup-project runs may have left
    # in this working copy but that the current contract no longer
    # emits (per-BC agents, Frontend-PRD.md, scene-graph JSON sidecars).
    # Without this, a re-run would leave stale files alongside the new
    # role-based agents — exactly the duplication users reported.
    deprecated_removed = _cleanup_deprecated_local_paths(project_path, bcs, config)

    # Extract ZIP to target directory
    zip_buffer.seek(0)
    extracted_files = []
    with zipfile.ZipFile(zip_buffer, "r") as zf:
        for member in zf.namelist():
            target = os.path.join(project_path, member)
            target_dir = os.path.dirname(target)
            os.makedirs(target_dir, exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(zf.read(member).decode("utf-8"))
            extracted_files.append(member)

    return {
        "success": True,
        "project_path": project_path,
        "files_extracted": extracted_files,
        "deprecated_removed": deprecated_removed,
    }


def _cleanup_deprecated_local_paths(project_path: str, bcs: list, config) -> list[str]:
    """Remove files that older setup-project runs wrote to disk but that
    the current contract no longer emits. Returns the list of removed
    paths (relative to ``project_path``).

    Targets:
    - ``.claude/agents/<bc_name>_agent.md`` (one per BC the user has now)
      — FR-023 / US7: per-BC agents are replaced by two role-based agents.
    - ``Frontend-PRD.md`` — 2026-05-12 amendment: the frontend
      perspective lives in ``specs/frontend/*`` instead.
    - ``specs/**/*.scene.json`` — 2026-05-12 amendment: scene-graph
      sidecars are no longer emitted; the SVG is the only visual asset.

    Scope is intentionally narrow: we only delete files whose paths
    match exactly the patterns the *old* contract emitted, never
    arbitrary user content.
    """
    from api.features.prd_generation.prd_api_contracts import AIAssistant

    removed: list[str] = []

    # Per-BC agent files — only delete those whose slug matches a BC
    # currently in the graph (a hand-renamed agent file stays put).
    if config.ai_assistant == AIAssistant.CLAUDE:
        agents_dir = os.path.join(project_path, ".claude", "agents")
        if os.path.isdir(agents_dir):
            for bc in bcs:
                bc_name_slug = (
                    (bc.get("name", "unknown") or "unknown").lower().replace(" ", "_")
                )
                stale = os.path.join(agents_dir, f"{bc_name_slug}_agent.md")
                if os.path.isfile(stale):
                    try:
                        os.remove(stale)
                        removed.append(os.path.relpath(stale, project_path))
                    except OSError:
                        pass

    # Frontend-PRD.md (top level only — never recursive, to avoid
    # touching unrelated trees the user may have created).
    fpath = os.path.join(project_path, "Frontend-PRD.md")
    if os.path.isfile(fpath):
        try:
            os.remove(fpath)
            removed.append("Frontend-PRD.md")
        except OSError:
            pass

    # scene-graph JSON sidecars under specs/.
    specs_root = os.path.join(project_path, "specs")
    if os.path.isdir(specs_root):
        for root, _dirs, files in os.walk(specs_root):
            for fname in files:
                if fname.endswith(".scene.json"):
                    p = os.path.join(root, fname)
                    try:
                        os.remove(p)
                        removed.append(os.path.relpath(p, project_path))
                    except OSError:
                        pass

    return sorted(removed)


# ─── PTY Terminal WebSocket ───


def _set_pty_size(fd: int, rows: int, cols: int) -> None:
    """Send TIOCSWINSZ ioctl to resize the PTY."""
    if not IS_UNIX_PTY_SUPPORTED:
        raise RuntimeError("PTY terminal is only supported on POSIX hosts.")
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


@router.websocket("/terminal")
async def terminal_ws(
    websocket: WebSocket,
    workdir: str = Query(default=""),
):
    """
    WebSocket ↔ PTY bridge.

    Query params:
      workdir — working directory for the claude CLI session.

    Client messages (JSON):
      {"type": "input", "data": "<keystrokes>"}
      {"type": "resize", "cols": 80, "rows": 24}

    Server messages: raw terminal output bytes (text frames).
    """
    if not IS_UNIX_PTY_SUPPORTED:
        await websocket.accept()
        await websocket.send_json(
            {
                "type": "error",
                "message": "Claude Code terminal is only supported on POSIX hosts.",
            }
        )
        await websocket.close(code=1011)
        return

    await websocket.accept()

    # Resolve working directory
    cwd = None
    if workdir:
        resolved = os.path.expanduser(workdir)
        resolved = os.path.abspath(resolved)
        if os.path.isdir(resolved):
            cwd = resolved

    # Spawn PTY with claude CLI
    master_fd, slave_fd = pty.openpty()

    env = os.environ.copy()
    env["TERM"] = "xterm-256color"
    env["COLORTERM"] = "truecolor"

    pid = os.fork()
    if pid == 0:
        # ─── Child process ───
        os.close(master_fd)
        os.setsid()

        # Change to requested working directory
        if cwd:
            os.chdir(cwd)

        # Make the slave the controlling terminal
        fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)

        os.dup2(slave_fd, 0)
        os.dup2(slave_fd, 1)
        os.dup2(slave_fd, 2)
        if slave_fd > 2:
            os.close(slave_fd)

        try:
            os.execvpe("claude", ["claude"], env)
        except OSError:
            # claude CLI not found — fallback to shell
            shell = os.environ.get("SHELL", "/bin/zsh")
            os.execvpe(shell, [shell], env)

    # ─── Parent process ───
    os.close(slave_fd)

    # Make master_fd non-blocking for async reads
    flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
    fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    async def _read_pty():
        """Read PTY output and forward to WebSocket.

        Buffers partial UTF-8 sequences and batches output to reduce
        the number of WebSocket messages and xterm.js render cycles.
        """
        leftover = b""
        try:
            while True:
                await asyncio.sleep(0.02)
                try:
                    chunks = []
                    # Drain all available data from the PTY
                    while True:
                        try:
                            data = os.read(master_fd, 16384)
                            if not data:
                                # EOF — send remaining and exit
                                if leftover or chunks:
                                    combined = leftover + b"".join(chunks)
                                    await websocket.send_text(
                                        combined.decode("utf-8", errors="replace")
                                    )
                                return
                            chunks.append(data)
                        except BlockingIOError:
                            break
                        except OSError as e:
                            if e.errno == 5:  # EIO — child exited
                                if leftover or chunks:
                                    combined = leftover + b"".join(chunks)
                                    await websocket.send_text(
                                        combined.decode("utf-8", errors="replace")
                                    )
                                return
                            raise

                    if not chunks:
                        continue

                    combined = leftover + b"".join(chunks)
                    leftover = b""

                    # Find the last valid UTF-8 boundary to avoid splitting
                    # multi-byte characters (e.g. Korean, emoji, CJK).
                    # Walk back from the end to find a safe cut point.
                    end = len(combined)
                    # Check up to 4 bytes back (max UTF-8 char length)
                    for i in range(min(4, end)):
                        byte = combined[end - 1 - i]
                        if byte < 0x80:
                            # ASCII — safe boundary right after this byte
                            break
                        elif byte >= 0xC0:
                            # Start of a multi-byte sequence
                            expected_len = (
                                2 if byte < 0xE0 else 3 if byte < 0xF0 else 4
                            )
                            available = i + 1
                            if available < expected_len:
                                # Incomplete sequence — keep it for next round
                                leftover = combined[end - available :]
                                combined = combined[: end - available]
                            break

                    if combined:
                        await websocket.send_text(
                            combined.decode("utf-8", errors="replace")
                        )

                except OSError:
                    await asyncio.sleep(0.05)
                except WebSocketDisconnect:
                    break
        except Exception:
            pass

    read_task = asyncio.create_task(_read_pty())

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)

            if msg.get("type") == "input":
                data = msg.get("data", "")
                os.write(master_fd, data.encode("utf-8"))

            elif msg.get("type") == "resize":
                cols = msg.get("cols", 80)
                rows = msg.get("rows", 24)
                _set_pty_size(master_fd, rows, cols)
                try:
                    os.kill(pid, signal.SIGWINCH)
                except ProcessLookupError:
                    pass

    except (WebSocketDisconnect, Exception):
        pass
    finally:
        read_task.cancel()
        try:
            os.close(master_fd)
        except OSError:
            pass
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            pass
