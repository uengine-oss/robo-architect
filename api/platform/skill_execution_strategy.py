"""Execution strategies for proposal skills.

The default strategy remains the locally authenticated Claude CLI.  The
OpenAI-compatible strategy is intentionally implemented here (instead of
pretending that an OpenAI endpoint speaks the Anthropic CLI protocol) and
provides the small filesystem/shell tool surface used by robo skills.
"""

from __future__ import annotations

import asyncio
import fnmatch
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncGenerator, Awaitable, Callable

from openai import AsyncOpenAI


ToolReporter = Callable[[str], Awaitable[None]]


@dataclass(frozen=True)
class OpenAICompatibleSettings:
    api_key: str
    base_url: str
    model: str
    max_turns: int = 40

    @classmethod
    def from_env(cls) -> "OpenAICompatibleSettings":
        api_key = os.getenv("SKILL_RUNNER_API_KEY", "").strip()
        base_url = os.getenv("SKILL_RUNNER_BASE_URL", "").strip().rstrip("/")
        model = os.getenv("SKILL_RUNNER_MODEL", "").strip()
        missing = [name for name, value in (
            ("SKILL_RUNNER_API_KEY", api_key),
            ("SKILL_RUNNER_BASE_URL", base_url),
            ("SKILL_RUNNER_MODEL", model),
        ) if not value]
        if missing:
            raise RuntimeError(
                "openai_compatible 스킬 실행 설정이 비었습니다: " + ", ".join(missing)
            )
        return cls(
            api_key=api_key,
            base_url=base_url,
            model=model,
            max_turns=max(1, int(os.getenv("SKILL_RUNNER_MAX_TURNS", "40"))),
        )


_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "Read",
            "description": "Read a UTF-8 text file. Paths must be inside an allowed workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "offset": {"type": "integer", "minimum": 0},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 200000},
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "Glob",
            "description": "List files matching a glob under an allowed workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "Grep",
            "description": "Search text recursively using a regular expression.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string"},
                    "glob": {"type": "string"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "Bash",
            "description": "Run a shell command in the skill working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout": {"type": "integer", "minimum": 1, "maximum": 300},
                },
                "required": ["command"],
            },
        },
    },
]


class OpenAICompatibleSkillStrategy:
    def __init__(self, *, project_root: Path, cwd: Path,
                 add_dirs: list[str] | None = None) -> None:
        self.settings = OpenAICompatibleSettings.from_env()
        self.project_root = project_root.resolve()
        self.cwd = cwd.resolve()
        self.allowed_roots = {self.project_root, self.cwd}
        self.allowed_roots.update(Path(p).resolve() for p in (add_dirs or []))
        self.client = AsyncOpenAI(
            api_key=self.settings.api_key,
            base_url=self.settings.base_url,
            timeout=float(os.getenv("SKILL_RUNNER_REQUEST_TIMEOUT", "1800")),
        )

    def _path(self, raw: str | None, *, default: Path | None = None) -> Path:
        candidate = Path(raw).expanduser() if raw else (default or self.cwd)
        if not candidate.is_absolute():
            candidate = self.cwd / candidate
        resolved = candidate.resolve()
        if not any(resolved == root or root in resolved.parents for root in self.allowed_roots):
            raise ValueError(f"허용된 작업공간 밖의 경로입니다: {resolved}")
        return resolved

    async def _tool(self, name: str, args: dict) -> str:
        if name == "Read":
            path = self._path(args.get("file_path"))
            offset = int(args.get("offset", 0))
            limit = min(int(args.get("limit", 200000)), 200000)
            return path.read_text(encoding="utf-8", errors="replace")[offset:offset + limit]

        if name == "Glob":
            root = self._path(args.get("path"), default=self.cwd)
            pattern = str(args.get("pattern") or "**/*")
            matches = [str(p) for p in root.glob(pattern) if p.is_file()]
            return "\n".join(sorted(matches)[:5000])

        if name == "Grep":
            import re
            root = self._path(args.get("path"), default=self.cwd)
            pattern = re.compile(str(args.get("pattern") or ""))
            file_glob = str(args.get("glob") or "*")
            matches: list[str] = []
            for path in root.rglob("*"):
                if not path.is_file() or not fnmatch.fnmatch(path.name, file_glob):
                    continue
                try:
                    for line_no, line in enumerate(
                        path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
                    ):
                        if pattern.search(line):
                            matches.append(f"{path}:{line_no}:{line}")
                            if len(matches) >= 2000:
                                return "\n".join(matches)
                except OSError:
                    continue
            return "\n".join(matches)

        if name == "Bash":
            command = str(args.get("command") or "")
            timeout = min(max(int(args.get("timeout", 120)), 1), 300)
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=str(self.cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return f"command timed out after {timeout}s"
            text = stdout.decode("utf-8", errors="replace")
            return f"exit_code={proc.returncode}\n{text[-200000:]}"

        raise ValueError(f"지원하지 않는 도구입니다: {name}")

    async def run(self, system_prompt: str, human_prompt: str,
                  report_tool: ToolReporter | None = None) -> str:
        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": human_prompt},
        ]
        for _turn in range(self.settings.max_turns):
            response = await self.client.chat.completions.create(
                model=self.settings.model,
                messages=messages,
                tools=_TOOLS,
                tool_choice="auto",
            )
            message = response.choices[0].message
            messages.append(message.model_dump(exclude_none=True))
            if not message.tool_calls:
                return message.content or ""
            for call in message.tool_calls:
                try:
                    args = json.loads(call.function.arguments or "{}")
                    if report_tool:
                        path = args.get("file_path") or args.get("path") or args.get("command") or ""
                        await report_tool(f"TOOL:{call.function.name}:{path}")
                    result = await self._tool(call.function.name, args)
                except Exception as exc:  # tool failure is returned to the model for recovery
                    result = f"ERROR: {type(exc).__name__}: {exc}"
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result,
                })
        raise RuntimeError(f"사내 모델 도구 호출이 {self.settings.max_turns}턴을 초과했습니다")

    async def lines(self, system_prompt: str, human_prompt: str) -> AsyncGenerator[str, None]:
        tool_lines: list[str] = []

        async def report(line: str) -> None:
            tool_lines.append(line)

        output = await self.run(system_prompt, human_prompt, report)
        for line in tool_lines:
            yield line
        for line in output.splitlines():
            if line.strip():
                yield line.strip()


def skill_runner_provider() -> str:
    provider = os.getenv("SKILL_RUNNER_PROVIDER", "claude_cli").strip().lower()
    aliases = {"claude": "claude_cli", "openai": "openai_compatible", "frentis": "openai_compatible"}
    provider = aliases.get(provider, provider)
    if provider not in {"claude_cli", "openai_compatible"}:
        raise RuntimeError(
            "SKILL_RUNNER_PROVIDER는 claude_cli 또는 openai_compatible 이어야 합니다"
        )
    return provider
