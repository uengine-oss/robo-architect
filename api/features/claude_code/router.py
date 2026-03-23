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

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from api.features.prd_generation.prd_api_contracts import PRDGenerationRequest

router = APIRouter(prefix="/api/claude-code", tags=["claude-code"])

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
    """
    from api.features.prd_generation.prd_api_contracts import AIAssistant
    from api.features.prd_generation.prd_artifact_generation import (
        generate_agent_config,
        generate_bc_spec,
        generate_claude_md,
        generate_claude_skill_ddd_principles,
        generate_claude_skill_eventstorming_implementation,
        generate_claude_skill_frontend,
        generate_claude_skill_gwt_test_generation,
        generate_claude_skill_tech_stack,
        generate_cursor_tech_stack_rule,
        generate_cursor_rules,
        generate_docker_compose,
        generate_dockerfile,
        generate_ddd_principles_rule,
        generate_eventstorming_implementation_rule,
        generate_gwt_test_generation_rule,
        generate_frontend_cursor_rule,
        generate_frontend_prd,
        generate_main_prd,
        generate_readme,
    )
    from api.features.prd_generation.prd_model_data import get_bcs_from_nodes

    # Resolve and validate path
    project_path = os.path.expanduser(request.project_path)
    project_path = os.path.abspath(project_path)

    # Create directory if it doesn't exist
    os.makedirs(project_path, exist_ok=True)

    bcs = get_bcs_from_nodes(None)
    if not bcs:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No Bounded Contexts found")

    config = request.prd_request.tech_stack

    # Build ZIP in memory (reuse existing logic)
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        if config.ai_assistant == AIAssistant.CLAUDE:
            zf.writestr("CLAUDE.md", generate_claude_md(bcs, config))
            zf.writestr(".claude/skills/ddd-principles.md", generate_claude_skill_ddd_principles(config))
            zf.writestr(".claude/skills/eventstorming-implementation.md", generate_claude_skill_eventstorming_implementation(config))
            zf.writestr(".claude/skills/gwt-test-generation.md", generate_claude_skill_gwt_test_generation(config))
            zf.writestr(f".claude/skills/{config.framework.value}.md", generate_claude_skill_tech_stack(config))
            if config.include_frontend and config.frontend_framework:
                frontend_skill = generate_claude_skill_frontend(config)
                if frontend_skill:
                    zf.writestr(f".claude/skills/{config.frontend_framework.value}.md", frontend_skill)
                frontend_prd = generate_frontend_prd(bcs, config)
                if frontend_prd:
                    zf.writestr("Frontend-PRD.md", frontend_prd)

        zf.writestr("PRD.md", generate_main_prd(bcs, config))
        zf.writestr(".cursorrules", generate_cursor_rules(config))

        if config.ai_assistant == AIAssistant.CURSOR:
            zf.writestr(".cursor/rules/ddd-principles.mdc", generate_ddd_principles_rule(config))
            zf.writestr(".cursor/rules/eventstorming-implementation.mdc", generate_eventstorming_implementation_rule(config))
            zf.writestr(".cursor/rules/gwt-test-generation.mdc", generate_gwt_test_generation_rule(config))
            zf.writestr(f".cursor/rules/{config.framework.value}.mdc", generate_cursor_tech_stack_rule(config))
            if config.include_frontend and config.frontend_framework:
                frontend_rule = generate_frontend_cursor_rule(config)
                if frontend_rule:
                    zf.writestr(f".cursor/rules/{config.frontend_framework.value}.mdc", frontend_rule)
                frontend_prd = generate_frontend_prd(bcs, config)
                if frontend_prd:
                    zf.writestr("Frontend-PRD.md", frontend_prd)

        for bc in bcs:
            bc_name = (bc.get("name", "unknown") or "unknown").lower().replace(" ", "_")
            zf.writestr(f"specs/{bc_name}_spec.md", generate_bc_spec(bc, config))
            if config.ai_assistant == AIAssistant.CLAUDE:
                zf.writestr(f".claude/agents/{bc_name}_agent.md", generate_agent_config(bc, config))

        if config.include_docker:
            zf.writestr("docker-compose.yml", generate_docker_compose(config))
            zf.writestr("Dockerfile", generate_dockerfile(config))

        zf.writestr("README.md", generate_readme(bcs, config))

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
    }


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
