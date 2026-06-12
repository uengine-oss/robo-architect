"""
Cross-platform PTY backend for the Claude Code terminal.

The WebSocket bridge in :mod:`router` must never branch on the host OS.
This module hides that difference behind a single :func:`spawn_pty`
factory plus a small :class:`PtyProcess` protocol. Two concrete backends
implement the same byte-oriented, non-blocking contract:

  * **PosixPtyBackend** — ``fork`` + ``pty.openpty`` + ``execvpe`` (Linux / macOS).
  * **WindowsPtyBackend** — Windows ConPTY via the ``pywinpty`` wheel.

Shared contract (identical on both platforms)::

    proc.pid                          -> int
    proc.read_nonblocking(max_bytes)  -> bytes   # b"" when idle; raises EOFError on child exit
    proc.write(data: bytes)           -> None
    proc.set_size(rows, cols)         -> None
    proc.is_alive()                   -> bool
    proc.terminate()                  -> None

Because every method speaks **bytes** and never blocks, the session
registry, scrollback ring buffer, UTF-8-safe split and re-attach logic in
:mod:`router` work unchanged regardless of backend.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Protocol, runtime_checkable

IS_WINDOWS = os.name == "nt"
IS_POSIX = os.name == "posix"

# Mirrors the set the legacy router enforced before passing through to
# claude's --permission-mode flag.
ALLOWED_PERMISSION_MODES = {
    "acceptEdits", "auto", "bypassPermissions",
    "default", "dontAsk", "plan",
}

if IS_POSIX:
    import errno
    import fcntl
    import pty
    import signal
    import struct
    import termios


def build_claude_argv(permission_mode: str) -> list[str]:
    """The argv used to launch the interactive ``claude`` CLI session."""
    argv = ["claude"]
    if permission_mode in ALLOWED_PERMISSION_MODES:
        argv += ["--permission-mode", permission_mode]
    return argv


@runtime_checkable
class PtyProcess(Protocol):
    """The OS-neutral surface the terminal bridge talks to."""

    @property
    def pid(self) -> int: ...

    def read_nonblocking(self, max_bytes: int = 16384) -> bytes:
        """Return whatever output is available right now (``b""`` if none).

        Raises :class:`EOFError` once the child has exited and its output
        is fully drained.
        """
        ...

    def write(self, data: bytes) -> None: ...

    def set_size(self, rows: int, cols: int) -> None: ...

    def is_alive(self) -> bool: ...

    def terminate(self) -> None: ...


def pty_supported() -> bool:
    """Whether an interactive PTY can be opened on this host.

    POSIX always can. Windows can iff the ``pywinpty`` wheel imports
    (it ships prebuilt, so this is true on a normal ``pip install``).
    """
    if IS_POSIX:
        return True
    if IS_WINDOWS:
        try:
            import winpty  # noqa: F401  (probe only)

            return True
        except Exception:
            return False
    return False


def unsupported_reason() -> str:
    """Human-readable explanation when :func:`pty_supported` is False."""
    if IS_WINDOWS:
        return (
            "Claude Code terminal requires the 'pywinpty' package on Windows. "
            "Install it with: pip install pywinpty"
        )
    return f"Claude Code terminal is not supported on this host (os.name={os.name!r})."


def spawn_pty(
    cwd: str | None,
    permission_mode: str,
    *,
    argv: list[str] | None = None,
) -> PtyProcess:
    """Spawn an interactive PTY running ``claude`` (or a custom ``argv``).

    ``argv`` defaults to :func:`build_claude_argv`; tests/evidence scripts
    pass an explicit argv (e.g. ``["claude", "--version"]``) to exercise
    the same spawn path deterministically.
    """
    resolved_argv = list(argv) if argv is not None else build_claude_argv(permission_mode)
    if IS_WINDOWS:
        return _WindowsPtyProcess(resolved_argv, cwd)
    return _PosixPtyProcess(resolved_argv, cwd)


# ─────────────────────────── POSIX backend ───────────────────────────


class _PosixPtyProcess:
    """fork + openpty + execvpe. Equivalent to the legacy ``_spawn_pty``."""

    def __init__(self, argv: list[str], cwd: str | None):
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
            try:
                os.execvpe(argv[0], argv, env)
            except OSError:
                shell = os.environ.get("SHELL", "/bin/zsh")
                os.execvpe(shell, [shell], env)

        # ─── Parent ───
        os.close(slave_fd)
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        self._pid = pid
        self._fd = master_fd

    @property
    def pid(self) -> int:
        return self._pid

    def read_nonblocking(self, max_bytes: int = 16384) -> bytes:
        try:
            data = os.read(self._fd, max_bytes)
        except BlockingIOError:
            return b""
        except OSError as e:
            if e.errno == errno.EIO:  # EIO — child exited
                raise EOFError from e
            raise
        if not data:
            raise EOFError
        return data

    def write(self, data: bytes) -> None:
        os.write(self._fd, data)

    def set_size(self, rows: int, cols: int) -> None:
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(self._fd, termios.TIOCSWINSZ, winsize)
        try:
            os.kill(self._pid, signal.SIGWINCH)
        except (OSError, ProcessLookupError):
            pass

    def is_alive(self) -> bool:
        try:
            wpid, _ = os.waitpid(self._pid, os.WNOHANG)
        except ChildProcessError:
            return False
        return wpid == 0

    def terminate(self) -> None:
        try:
            os.close(self._fd)
        except OSError:
            pass
        try:
            os.kill(self._pid, signal.SIGTERM)
        except (OSError, ProcessLookupError):
            pass
        try:
            os.waitpid(self._pid, os.WNOHANG)
        except ChildProcessError:
            pass


# ────────────────────────── Windows backend ──────────────────────────


class _WindowsPtyProcess:
    """Windows ConPTY via pywinpty's low-level :class:`winpty.PTY`.

    pywinpty's ``read`` returns *str* (ConPTY hands us UTF-8 text); we
    re-encode to bytes so the byte-oriented session pipeline in
    :mod:`router` (ring buffer + :func:`_utf8_safe_split`) is identical
    across platforms. ``read(blocking=False)`` returns ``""`` when idle,
    so the existing 20 ms polling loop applies unchanged.
    """

    def __init__(self, argv: list[str], cwd: str | None, rows: int = 24, cols: int = 80):
        from winpty import PTY

        # Resolve the executable. claude installs as a real claude.exe on
        # Windows; shutil.which finds it on PATH. If it can't be resolved,
        # fall back to the system shell so the user still gets a usable
        # terminal instead of a hard spawn failure.
        exe = argv[0]
        resolved = exe if os.path.isabs(exe) and os.path.exists(exe) else shutil.which(exe)
        if resolved:
            appname = resolved
            cmdline = subprocess.list2cmdline(argv[1:]) if len(argv) > 1 else ""
        else:
            appname = os.environ.get("COMSPEC", "cmd.exe")
            cmdline = ""

        self._pty = PTY(cols, rows)
        # cwd="" / None → inherit the server's cwd. env=None → inherit the
        # parent environment (ConPTY renders VT natively, so no TERM needed).
        ok = self._pty.spawn(
            appname,
            cmdline=(cmdline or None),
            cwd=(cwd or None),
        )
        if not ok:
            raise RuntimeError(f"ConPTY failed to spawn {appname!r}")
        self._pid = self._pty.pid

    @property
    def pid(self) -> int:
        return self._pid

    def read_nonblocking(self, max_bytes: int = 16384) -> bytes:
        try:
            chunk = self._pty.read(False)  # blocking=False → "" when idle
        except Exception as e:
            # pywinpty raises WinptyError once the pipe is gone.
            raise EOFError from e
        if chunk:
            return chunk.encode("utf-8", errors="replace")
        # No data: distinguish "idle" from "child exited and drained".
        if not self._pty.isalive():
            raise EOFError
        return b""

    def write(self, data: bytes) -> None:
        self._pty.write(data.decode("utf-8", errors="replace"))

    def set_size(self, rows: int, cols: int) -> None:
        try:
            self._pty.set_size(cols, rows)  # pywinpty order is (cols, rows)
        except Exception:
            pass

    def is_alive(self) -> bool:
        try:
            return bool(self._pty.isalive())
        except Exception:
            return False

    def terminate(self) -> None:
        pid = self._pid
        try:
            self._pty.cancel_io()
        except Exception:
            pass
        # On Windows os.kill(pid, SIGTERM) maps to TerminateProcess — kills
        # the claude child even though the low-level PTY has no kill().
        try:
            import signal as _signal

            os.kill(pid, _signal.SIGTERM)
        except (OSError, ProcessLookupError, ValueError):
            pass
        # Dropping the PTY closes the ConPTY device + reaps the agent.
        self._pty = None
