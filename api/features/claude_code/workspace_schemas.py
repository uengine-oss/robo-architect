"""
Pydantic models for the Claude Code IDE workspace endpoints.

Shapes for `GET /tree`, `GET /file`, and `PUT /file`. See
`specs/021-claude-code-ide-workspace/data-model.md` for field semantics.

Note: `mtime_ns` is serialized as a JSON string at the boundary because
nanosecond mtime exceeds JS Number safe-integer range. The frontend echoes
it verbatim on PUT; only this module's helpers ever do `int(...)` on it.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class TreeChild(BaseModel):
    name: str
    type: Literal["file", "directory"]


class TreeResponse(BaseModel):
    root: str
    path: str
    children: list[TreeChild]


class FileResponse(BaseModel):
    path: str
    size: int
    # Serialized as a string to preserve nanosecond precision across JS Number.
    mtime_ns: str
    binary: bool
    content: Optional[str] = None
    encoding: Literal["utf-8"] = "utf-8"


class FileWriteRequest(BaseModel):
    root: str
    path: str
    content: str
    # String at the JSON boundary; convert to int inside the endpoint handler
    # before passing to write_text_file_atomic. None means "creating new file".
    expected_mtime_ns: Optional[str] = Field(
        default=None,
        description="Required for existing files; None creates a new file.",
    )


class FileWriteResponse(BaseModel):
    path: str
    size: int
    mtime_ns: str
