from __future__ import annotations

import importlib
import importlib.util
import os
import traceback
from pathlib import Path
from typing import Protocol


class _SmartLoggerLike(Protocol):
    @classmethod
    def log(
        cls,
        level: str,
        message: str,
        category: str | None = None,
        params: dict | None = None,
        max_inline_chars: int = 100,
    ) -> None: ...


def _safe_setdefault_env(key: str, value: str) -> None:
    # Don't override user-provided settings.
    if os.environ.get(key) is None:
        os.environ[key] = value


def _load_smart_logger_from_file(py_file: Path) -> type[_SmartLoggerLike]:
    spec = importlib.util.spec_from_file_location("private_smart_logger", str(py_file))
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to create import spec from file: {py_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[call-arg]
    cls = getattr(module, "SmartLogger", None)
    if cls is None:
        raise ImportError(f"`SmartLogger` not found in {py_file}")
    if not hasattr(cls, "log") or not callable(getattr(cls, "log")):
        raise TypeError(f"`SmartLogger.log` missing or not callable in {py_file}")
    return cls


def _load_smart_logger_from_module(module_path: str) -> type[_SmartLoggerLike]:
    module = importlib.import_module(module_path)
    cls = getattr(module, "SmartLogger", None)
    if cls is None:
        raise ImportError(f"`SmartLogger` not found in module: {module_path}")
    if not hasattr(cls, "log") or not callable(getattr(cls, "log")):
        raise TypeError(f"`SmartLogger.log` missing or not callable in {module_path}")
    return cls


def _resolve_impl() -> tuple[type[_SmartLoggerLike], str]:
    """
    Returns (SmartLoggerClass, source_description)
    """
    private = (os.getenv("PRIVATE_LOGGER_PATH") or "").strip()
    if private:
        # 1) Try file path
        p = Path(private)
        if p.exists() and p.is_file():
            return _load_smart_logger_from_file(p), f"PRIVATE_LOGGER_PATH(file)={p}"
        # 2) Try module import path
        return _load_smart_logger_from_module(private), f"PRIVATE_LOGGER_PATH(module)={private}"

    # Default: use project logger implementation from p_utils, but ensure it actually emits INFO logs.
    _safe_setdefault_env("SMART_LOGGER_MIN_LEVEL", "INFO")
    _safe_setdefault_env("SMART_LOGGER_INCLUDE_ALL_MIN_LEVEL", "ERROR")
    _safe_setdefault_env("SMART_LOGGER_CONSOLE_OUTPUT", "True")
    _safe_setdefault_env("SMART_LOGGER_FILE_OUTPUT", "False")
    _safe_setdefault_env("SMART_LOGGER_REMOVE_LOG_ON_CREATE", "False")

    class _FallbackLogger:
        @classmethod
        def log(
            cls,
            level: str,
            message: str,
            category: str | None = None,
            params: dict | None = None,
            max_inline_chars: int = 100,
        ) -> None:
            print(f"{level}: {message}")

    return _FallbackLogger, "fallback(print)"


_IMPL, _IMPL_SOURCE = _resolve_impl()


class SmartLogger:
    """
    Project-wide logger entry point.

    Always import and use this class:
        from api.smart_logger import SmartLogger
        SmartLogger.log("INFO", "message", category="...", params={...})
    """

    impl_source: str = _IMPL_SOURCE

    @classmethod
    def log(
        cls,
        level: str,
        message: str,
        category: str | None = None,
        params: dict | None = None,
        max_inline_chars: int = 100,
    ) -> None:
        try:
            _IMPL.log(level, message, category=category, params=params, max_inline_chars=max_inline_chars)
        except Exception:
            # Last-ditch fallback: keep the app running and still emit something.
            err = traceback.format_exc()
            cat = f"[{category}] " if category else ""
            print(f"{level}: {cat}{message}")
            print(f"LOGGER_ERROR: {err}")


