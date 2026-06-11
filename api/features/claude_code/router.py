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
import time
import zipfile
from typing import Any

import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from api.features.claude_code.workspace_fs import (
    delete_entry,
    list_directory,
    move_entry,
    read_text_file,
    resolve_under_root,
    write_text_file_atomic,
)
from api.features.claude_code.workspace_schemas import (
    FileResponse as WorkspaceFileResponse,
)
from api.features.claude_code.workspace_schemas import (
    DeleteRequest,
    DeleteResponse,
    FileWriteRequest,
    FileWriteResponse,
    MoveRequest,
    MoveResponse,
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


@router.delete("/file", response_model=DeleteResponse)
async def workspace_delete_entry(req: DeleteRequest):
    """Delete a file or directory inside the workspace.

    Refuses to delete the workspace root (path must be non-empty).
    Directory deletion is recursive (``shutil.rmtree``).
    """
    from fastapi import HTTPException

    if not req.path:
        raise HTTPException(status_code=400, detail="path is required (cannot delete root)")
    resolved = resolve_under_root(req.root, req.path)
    deleted_type = delete_entry(resolved)
    logger.info(
        "claude_code.workspace.entry_deleted",
        extra={"root": req.root, "path": req.path, "kind": deleted_type},
    )
    return DeleteResponse(path=req.path, deleted_type=deleted_type)


@router.post("/move", response_model=MoveResponse)
async def workspace_move_entry(req: MoveRequest):
    """Move or rename a file/directory inside the workspace.

    Both ``from_path`` and ``to_path`` are sandbox-checked. Refuses to
    overwrite an existing destination (409) or move a directory into
    itself (400).
    """
    from fastapi import HTTPException

    if not req.from_path or not req.to_path:
        raise HTTPException(status_code=400, detail="from_path and to_path are required")
    src = resolve_under_root(req.root, req.from_path)
    dst = resolve_under_root(req.root, req.to_path)
    moved_type = move_entry(src, dst)
    logger.info(
        "claude_code.workspace.entry_moved",
        extra={
            "root": req.root,
            "from_path": req.from_path,
            "to_path": req.to_path,
            "kind": moved_type,
        },
    )
    return MoveResponse(
        from_path=req.from_path,
        to_path=req.to_path,
        moved_type=moved_type,
    )


# ─── Project setup (extract PRD to target directory) ───


class SetupProjectRequest(BaseModel):
    """Extract generated PRD files to a target directory for Claude Code.

    ``output_mode`` (feature 029) controls which structure is laid down:

    - ``"robo-spec"`` (default, recommended): skip the legacy PRD pipeline
      entirely; only install the verbatim robo-spec skill set + speckit
      inheritance chain + ``.mcp.json`` + ``.claude/robo-project.json``.
      The user generates ``plan.md`` / ``tasks.md`` / source on demand in
      Claude Code via ``/robo-plan``, ``/robo-tasks``, ``/robo-implement``.
    - ``"prd"``: pre-029 behavior — generate the full PRD ZIP
      (PRD.md, specs/, .cursor/rules/, agents/, ...) AND ALSO install the
      robo-spec skills on top. ``prd_request.tech_stack`` is required.
    """
    project_path: str
    prd_request: PRDGenerationRequest
    output_mode: str = "robo-spec"


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

    # Resolve and validate path (shared by both output modes).
    project_path = os.path.expanduser(request.project_path)
    project_path = os.path.abspath(project_path)
    os.makedirs(project_path, exist_ok=True)

    # ------------------------------------------------------------------
    # Robo-Spec Skills mode (feature 029, default): skip the heavy PRD
    # pipeline entirely. The user produces plan/tasks/source on demand
    # in Claude Code via /robo-plan, /robo-tasks, /robo-implement.
    # ------------------------------------------------------------------
    if request.output_mode == "robo-spec":
        # We still need at least one BC in the graph so the user has
        # something to /robo-plan against. (The check exists in the
        # legacy path too; surfaced here as 404 with a clear message.)
        bcs = get_bcs_from_nodes(None)
        if not bcs:
            raise HTTPException(status_code=404, detail="No Bounded Contexts found")

        robo_install = _install_robo_spec(project_path)
        return {
            "success": True,
            "project_path": project_path,
            "files_extracted": [],
            "deprecated_removed": [],
            "output_mode": "robo-spec",
            **robo_install,
        }

    # ------------------------------------------------------------------
    # Legacy PRD mode (pre-029): generate the full PRD ZIP + robo-spec.
    # ------------------------------------------------------------------
    # Enforce FR-020 — when include_frontend=true, frontend_framework
    # MUST be set. Same contract as /api/prd/{generate,download}.
    _require_frontend_framework(request.prd_request.tech_stack)

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

    # ------------------------------------------------------------------
    # Robo-Spec verbatim install (feature 029 — E1 extension, T013)
    # ------------------------------------------------------------------
    # Per FR-012: files under <repo>/skills/robo-spec/ MUST be
    # copied byte-for-byte (no Jinja, no template substitution) into
    # <workspace>/.claude/skills/. The project-specific config files
    # (.claude/robo-project.json and .claude/mcp.json) are generated
    # alongside the copy because they carry per-project URLs — they're
    # explicitly NOT under skills/ so FR-012's "byte-identical for
    # skills/" guarantee stands (data-model.md §2.5 + SC-006).
    robo_install = _install_robo_spec(project_path)

    return {
        "success": True,
        "project_path": project_path,
        "files_extracted": extracted_files,
        "deprecated_removed": deprecated_removed,
        **robo_install,
    }


def _install_robo_spec(project_path: str) -> dict[str, Any]:
    """Copy <repo>/skills/robo-spec/ verbatim into the workspace,
    then write the per-project config files. Returns a fragment merged
    into the setup-project response (see schemas.RoboSpecInstallSummary).

    Idempotent: re-running on a workspace that already has the install
    overwrites the skill files (FR-012 — they're derivable from the
    skills/robo-spec source) and refreshes mcp.json's URL. The project_id in
    robo-project.json is NEVER mutated on re-run — a different id
    incoming when an existing id is present surfaces as HTTP 409.

    The project_id at v1 is the workspace's resolved absolute path
    hashed to a UUID — a stable per-host identifier that does not require
    a server-side project registry. When a real Robo Architect project
    UUID becomes available (e.g., via a future request field), the
    derivation can be replaced without changing the on-disk shape.
    """
    import hashlib
    import shutil
    import uuid
    from fastapi import HTTPException

    repo_root = _resolve_repo_root()
    src_skills = os.path.join(repo_root, "skills", "robo-spec")
    if not os.path.isdir(src_skills):
        # Packaging bug, not a user error — surface explicitly.
        raise HTTPException(
            status_code=500,
            detail=f"skills/robo-spec/ not found at {src_skills}",
        )

    dest_claude = os.path.join(project_path, ".claude")
    dest_skills = os.path.join(dest_claude, "skills")
    os.makedirs(dest_claude, exist_ok=True)

    # Verbatim copy of the robo-* skill tree. dirs_exist_ok=True lets
    # re-runs overwrite cleanly.
    shutil.copytree(src_skills, dest_skills, dirs_exist_ok=True)

    # Inheritance dependency (research R11): the robo-{plan,tasks,implement}
    # skills explicitly delegate to their `speckit-*` counterparts at runtime
    # ("read .claude/skills/speckit-plan/SKILL.md first"). For that read to
    # succeed in the target workspace we MUST ship the matching speckit
    # SKILL.md files alongside. We copy them from this repo's own speckit
    # install — the version we pin against in the robo-* frontmatter
    # (`requires-speckit`) is whatever this repo has on disk.
    #
    # Only the three skills the robo-* overrides extend are shipped. Other
    # speckit-* skills (constitution, clarify, taskstoissues, git helpers)
    # are not part of the inheritance chain and are intentionally omitted.
    speckit_src_root = os.path.join(repo_root, ".claude", "skills")
    for speckit_name in ("speckit-plan", "speckit-tasks", "speckit-implement"):
        speckit_src = os.path.join(speckit_src_root, speckit_name)
        if not os.path.isdir(speckit_src):
            # Treat as a packaging error rather than continuing silently —
            # without speckit-plan/SKILL.md in the workspace, /robo-plan's
            # inheritance step would dead-end at runtime.
            raise HTTPException(
                status_code=500,
                detail=(
                    f"upstream {speckit_name}/ not found at {speckit_src} — "
                    "robo-* skills depend on these via the inheritance "
                    "pattern (research R11)."
                ),
            )
        shutil.copytree(
            speckit_src,
            os.path.join(dest_skills, speckit_name),
            dirs_exist_ok=True,
        )

    # Derive a stable project_id from the workspace path. Hash → UUIDv5-like
    # 32-hex string, prefixed with `ws-` so it's visually distinguishable
    # from a real Robo Architect project UUID when both appear in logs.
    derived_project_id = "ws-" + hashlib.sha256(
        project_path.encode("utf-8")
    ).hexdigest()[:32]

    backend_url = os.environ.get("ROBO_SPEC_BACKEND_URL", "http://localhost:8000")
    mcp_endpoint = backend_url.rstrip("/") + "/mcp"

    robo_project_json_path = os.path.join(dest_claude, "robo-project.json")
    if os.path.isfile(robo_project_json_path):
        try:
            with open(robo_project_json_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            existing_pid = existing.get("projectId")
        except (OSError, json.JSONDecodeError):
            existing_pid = None
        if existing_pid and existing_pid != derived_project_id:
            # Per E1: re-running on a workspace that already has a
            # different projectId is a conflict — protects the developer
            # against accidentally re-linking the wrong project.
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "PROJECT_ID_MISMATCH",
                    "existing": existing_pid,
                    "incoming": derived_project_id,
                    "hint": (
                        "Delete .claude/robo-project.json (and review what "
                        "was previously linked) before re-running setup-project."
                    ),
                },
            )

    robo_project_doc = {
        "projectId": derived_project_id,
        "backendUrl": backend_url,
        "mcpEndpoint": mcp_endpoint,
        "createdAt": (existing.get("createdAt")  # type: ignore[has-type]
                      if os.path.isfile(robo_project_json_path)
                      else _now_iso()),
    }
    with open(robo_project_json_path, "w", encoding="utf-8") as f:
        json.dump(robo_project_doc, f, indent=2)

    # .mcp.json — Claude Code reads this to discover project-scoped MCP
    # servers. MUST live at the project root (NOT under .claude/) — that
    # is the discovery path Claude Code's MCP loader looks at; an
    # otherwise-correct file under .claude/ is silently ignored.
    # The URL carries a trailing slash so Claude's HTTP client doesn't
    # hit FastAPI's 307 redirect from `/mcp` → `/mcp/`.
    mcp_endpoint_with_slash = (
        mcp_endpoint if mcp_endpoint.endswith("/") else mcp_endpoint + "/"
    )
    mcp_json_path = os.path.join(project_path, ".mcp.json")
    mcp_json_doc = {
        "mcpServers": {
            "robo-spec": {
                "type": "http",
                "url": mcp_endpoint_with_slash,
            }
        }
    }
    with open(mcp_json_path, "w", encoding="utf-8") as f:
        json.dump(mcp_json_doc, f, indent=2)

    # Checksum of the freshly-copied skills/ subtree — SC-006 verifies
    # byte-identical install by comparing this to a digest of the source.
    checksum = _sha256_directory(dest_skills)

    return {
        "roboSpecInstalled": True,
        "roboSpecChecksum": f"sha256:{checksum}",
        "roboProjectId": derived_project_id,
    }


def _resolve_repo_root() -> str:
    """Find the repo root by walking up until we find both `api/` and
    `skills/`. This avoids hard-coding ``__file__`` parents which
    breaks when the package is editable-installed elsewhere.
    """
    here = os.path.abspath(os.path.dirname(__file__))
    while True:
        if (
            os.path.isdir(os.path.join(here, "api"))
            and os.path.isdir(os.path.join(here, "skills"))
        ):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            # Reached filesystem root — fall back to the four-parent
            # default (matches the current repo layout).
            return os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "..")
            )
        here = parent


def _sha256_directory(path: str) -> str:
    """Stable sha256 of a directory tree's file contents. Sorts walk
    output deterministically so the digest is reproducible.
    """
    import hashlib

    h = hashlib.sha256()
    for root, dirs, files in os.walk(path):
        dirs.sort()
        for fname in sorted(files):
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, path).replace(os.sep, "/")
            h.update(rel.encode("utf-8"))
            h.update(b"\x00")
            with open(full, "rb") as f:
                h.update(f.read())
            h.update(b"\x00")
    return h.hexdigest()


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


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


# ─── PTY session registry (survives ws disconnect / browser refresh) ───
# Each session keeps a `claude` PTY alive INDEPENDENT of any single WebSocket so a
# page reload (or tab switch) can re-attach — replaying scrollback — instead of
# killing claude. Sessions are keyed by a stable client-supplied session_id
# (a proposal worktree path, 'main', or 'shell-<ts>'); the same id reconnecting
# re-attaches to the same live claude process.

_SESSION_TTL_SECONDS = 30 * 60      # reap sessions detached longer than this
_SESSION_MAX = 16                   # hard cap on concurrent live sessions
_RING_BYTES = 256 * 1024            # per-session scrollback replay buffer


class _PtySession:
    def __init__(self, session_id: str, pid: int, master_fd: int, cwd: str | None):
        self.id = session_id
        self.pid = pid
        self.master_fd = master_fd
        self.cwd = cwd
        self.buffer = bytearray()       # bounded scrollback (raw bytes)
        self.ws: WebSocket | None = None  # currently-attached WebSocket
        self.lock = asyncio.Lock()
        self.reader_task: asyncio.Task | None = None
        self.alive = True
        self.rows = 24
        self.cols = 80
        self.detached_at = time.monotonic()


_sessions: dict[str, _PtySession] = {}


def _append_ring(sess: _PtySession, data: bytes) -> None:
    sess.buffer.extend(data)
    if len(sess.buffer) > _RING_BYTES:
        del sess.buffer[: len(sess.buffer) - _RING_BYTES]


def _utf8_safe_split(combined: bytes) -> tuple[bytes, bytes]:
    """Split off a trailing incomplete multibyte UTF-8 sequence → (emit, leftover)."""
    end = len(combined)
    for i in range(min(4, end)):
        byte = combined[end - 1 - i]
        if byte < 0x80:
            break
        if byte >= 0xC0:
            expected = 2 if byte < 0xE0 else 3 if byte < 0xF0 else 4
            if i + 1 < expected:
                return combined[: end - (i + 1)], combined[end - (i + 1):]
            break
    return combined, b""


def _kill_pty(sess: _PtySession) -> None:
    try:
        os.close(sess.master_fd)
    except OSError:
        pass
    try:
        os.kill(sess.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        os.waitpid(sess.pid, os.WNOHANG)
    except ChildProcessError:
        pass


async def _destroy_session(session_id: str) -> bool:
    """Explicitly terminate a session (× button / reap)."""
    sess = _sessions.pop(session_id, None)
    if not sess:
        return False
    sess.alive = False
    if sess.reader_task and not sess.reader_task.done():
        sess.reader_task.cancel()
    _kill_pty(sess)
    return True


def _reap_stale_sessions() -> None:
    now = time.monotonic()
    for sid, sess in list(_sessions.items()):
        if sess.ws is None and (now - sess.detached_at) > _SESSION_TTL_SECONDS:
            asyncio.create_task(_destroy_session(sid))


async def _session_reader(sess: _PtySession) -> None:
    """Persistent PTY reader — runs for the session's whole lifetime (not a single
    ws). Appends output to the scrollback ring and forwards live to the attached ws."""
    leftover = b""
    while sess.alive:
        await asyncio.sleep(0.02)
        chunks: list[bytes] = []
        try:
            while True:
                try:
                    data = os.read(sess.master_fd, 16384)
                    if not data:
                        sess.alive = False
                        break
                    chunks.append(data)
                except BlockingIOError:
                    break
                except OSError as e:
                    if e.errno == 5:  # EIO — child exited
                        sess.alive = False
                    break
        except Exception:
            pass

        if chunks:
            combined = leftover + b"".join(chunks)
            emit, leftover = _utf8_safe_split(combined)
            if emit:
                async with sess.lock:
                    _append_ring(sess, emit)
                    ws = sess.ws
                if ws is not None:
                    try:
                        await ws.send_text(emit.decode("utf-8", errors="replace"))
                    except Exception:
                        pass
        if not sess.alive:
            break

    # claude exited — notify any attached ws and unregister (best-effort).
    async with sess.lock:
        ws = sess.ws
    if ws is not None:
        try:
            await ws.send_text("\r\n\x1b[33m[세션 종료됨 — claude 프로세스가 끝났습니다]\x1b[0m\r\n")
        except Exception:
            pass
    if _sessions.get(sess.id) is sess:
        _sessions.pop(sess.id, None)
    _kill_pty(sess)


def _spawn_pty(cwd: str | None, permission_mode: str) -> tuple[int, int]:
    """Fork a `claude` PTY. Returns (pid, master_fd) with master_fd non-blocking."""
    master_fd, slave_fd = pty.openpty()

    env = os.environ.copy()
    env["TERM"] = "xterm-256color"
    env["COLORTERM"] = "truecolor"

    pid = os.fork()
    if pid == 0:
        # ─── Child ───
        os.close(master_fd)
        os.setsid()
        if cwd:
            try:
                os.chdir(cwd)
            except OSError:
                pass
        fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)
        os.dup2(slave_fd, 0)
        os.dup2(slave_fd, 1)
        os.dup2(slave_fd, 2)
        if slave_fd > 2:
            os.close(slave_fd)
        ALLOWED_PERMISSION_MODES = {
            "acceptEdits", "auto", "bypassPermissions",
            "default", "dontAsk", "plan",
        }
        claude_argv = ["claude"]
        if permission_mode in ALLOWED_PERMISSION_MODES:
            claude_argv += ["--permission-mode", permission_mode]
        try:
            os.execvpe("claude", claude_argv, env)
        except OSError:
            shell = os.environ.get("SHELL", "/bin/zsh")
            os.execvpe(shell, [shell], env)

    # ─── Parent ───
    os.close(slave_fd)
    flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
    fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    return pid, master_fd


@router.delete("/terminal/session")
async def close_terminal_session(session_id: str = Query(...)):
    """Explicitly terminate a PTY session (frontend × close button)."""
    closed = await _destroy_session(session_id)
    return {"closed": closed}


@router.get("/global-skills/status")
async def global_skills_status():
    """홈(``~/.claude/skills/``)에 이 저장소의 스킬이 설치돼 있는지 점검한다.

    Code 탭 진입 시 프론트가 호출한다. 같은 서버 세션에서 이미 설치 확인/완료된
    경우 ``verified=True`` 로 빠르게 응답해 재점검·재프롬프트를 막는다.
    """
    from api.platform import global_skills

    return global_skills.status()


@router.post("/global-skills/install")
async def global_skills_install():
    """이 저장소의 스킬을 ``~/.claude/skills/`` 에 평탄 구조로 설치한다."""
    from api.platform import global_skills

    return global_skills.install()


@router.websocket("/terminal")
async def terminal_ws(
    websocket: WebSocket,
    workdir: str = Query(default=""),
    permission_mode: str = Query(default=""),
    session_id: str = Query(default=""),
):
    """
    WebSocket ↔ PTY bridge.

    Query params:
      workdir — working directory for the claude CLI session.
      permission_mode — optional pass-through to claude's
        ``--permission-mode`` flag (e.g. ``acceptEdits``,
        ``bypassPermissions``, ``plan``). Leave blank to use claude's
        default interactive prompting. Robo-spec e2e tests pass
        ``bypassPermissions`` so the MCP tool calls (set_bc_classification,
        register_implementation_files, …) don't pause on a permission
        prompt under each invocation; for human use the default is
        recommended.
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
    _reap_stale_sessions()

    # Resolve working directory (only used when creating a fresh session).
    cwd = None
    if workdir:
        resolved = os.path.abspath(os.path.expanduser(workdir))
        if os.path.isdir(resolved):
            cwd = resolved

    # Stable session key — survives reload so the same id re-attaches to the
    # same live claude. Fall back to workdir, then an ephemeral per-socket id.
    sid = session_id or workdir or f"ephemeral-{id(websocket)}"

    sess = _sessions.get(sid)
    if sess is not None and sess.alive:
        # ── Re-attach: replay scrollback, then become the live sink ──
        async with sess.lock:
            old = sess.ws
            sess.ws = None
            snapshot = bytes(sess.buffer)
        if old is not None:
            try:
                await old.close()
            except Exception:
                pass
        async with sess.lock:
            try:
                if snapshot:
                    await websocket.send_text(snapshot.decode("utf-8", errors="replace"))
            except Exception:
                pass
            sess.ws = websocket
            sess.detached_at = time.monotonic()
    else:
        # ── New session ──
        if len(_sessions) >= _SESSION_MAX:
            _reap_stale_sessions()
            if len(_sessions) >= _SESSION_MAX:
                try:
                    await websocket.send_text(
                        "\r\n\x1b[31m[세션 한도 초과 — 사용하지 않는 셀(×)을 닫고 다시 시도하세요]\x1b[0m\r\n"
                    )
                    await websocket.close(code=1011)
                except Exception:
                    pass
                return
        pid, master_fd = _spawn_pty(cwd, permission_mode)
        sess = _PtySession(sid, pid, master_fd, cwd)
        sess.ws = websocket
        _sessions[sid] = sess
        sess.reader_task = asyncio.create_task(_session_reader(sess))

    # ── Input / resize loop (the reader task handles output) ──
    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            mtype = msg.get("type")

            if mtype == "input":
                try:
                    os.write(sess.master_fd, msg.get("data", "").encode("utf-8"))
                except OSError:
                    pass

            elif mtype == "resize":
                sess.cols = msg.get("cols", 80)
                sess.rows = msg.get("rows", 24)
                try:
                    _set_pty_size(sess.master_fd, sess.rows, sess.cols)
                    os.kill(sess.pid, signal.SIGWINCH)
                except (OSError, ProcessLookupError):
                    pass

            elif mtype == "close":
                # Explicit terminate (× close button) — kill the PTY.
                await _destroy_session(sid)
                break

    except (WebSocketDisconnect, Exception):
        pass
    finally:
        # Detach but KEEP the session alive so a reload/tab-switch can re-attach.
        # (Explicit close already destroyed it above; reap handles stale ones.)
        if sess is not None and sess.ws is websocket:
            sess.ws = None
            sess.detached_at = time.monotonic()
