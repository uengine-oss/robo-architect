from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
from pathlib import Path
from typing import AsyncGenerator

from api.platform.observability.smart_logger import SmartLogger

_PROJECT_ROOT = Path(__file__).parents[4]


def _skill_env() -> dict:
    """헤드리스 claude 서브프로세스용 환경.

    백엔드가 .env 의 (만료/무효일 수 있는) ANTHROPIC_API_KEY 를 os.environ 에 로드하면
    헤드리스 claude 가 그 키로 인증을 시도해 'Invalid API key' 로 즉시 실패한다.
    키를 제거하면 claude.ai 로그인(구독)으로 폴백한다.
    """
    env = dict(os.environ)
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        env.pop(k, None)
    return env


def _skill_path(skill_name: str) -> Path:
    return _PROJECT_ROOT / "skills" / "robo-changes" / skill_name / "SKILL.md"


async def run_specify_skill(change_id: str, original_prompt: str, domain_nodes: list[dict]) -> dict | None:
    """
    robo-change-specify 스킬을 claude -p --system-prompt-file 방식으로 호출한다.
    Constitution X: 스킬이 AI 워크플로우를 정의, 백엔드는 PTY 실행 + 파싱만 담당.

    Args:
        change_id: CHG-NNN
        original_prompt: 변경 내용 자연어
        domain_nodes: [{id, label, name}, ...] - Neo4j에서 사전 조회

    Returns:
        파싱된 dict {"changeId", "title", "effects": [...]} 또는 None
    """
    claude_bin = shutil.which("claude") or "claude"
    skill_file = _skill_path("robo-change-specify")

    if not skill_file.exists():
        SmartLogger.log("ERROR", f"Skill not found: {skill_file}",
                        category="requirement_changes.skill.not_found", params={})
        return None

    node_list = "\n".join(
        f"- id: {n['id']}, type: {n.get('label', '')}, name: {n.get('name', '')}"
        for n in (domain_nodes or [])
    )

    human_prompt = (
        f"Change ID: {change_id}\n"
        f"원본 프롬프트: {original_prompt}\n\n"
        f"현재 시스템 구성 요소 목록:\n{node_list or '(구성 요소 없음)'}\n\n"
        "위 변경 내용이 어떤 구성 요소에 영향을 주는지 분석하여 JSON으로 출력하세요."
    )

    cmd = [
        claude_bin, "-p", human_prompt,
        "--system-prompt-file", str(skill_file),
        "--output-format", "text",
        "--dangerously-skip-permissions",
    ]

    SmartLogger.log("INFO", f"Invoking robo-change-specify for {change_id}",
                    category="requirement_changes.skill.start",
                    params={"changeId": change_id, "cmd": " ".join(cmd[:4])})

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(_PROJECT_ROOT),
            env=_skill_env(),
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=120
        )
        raw = stdout_bytes.decode("utf-8", errors="replace").strip()
        stderr_str = stderr_bytes.decode("utf-8", errors="replace").strip()

        if stderr_str:
            SmartLogger.log("WARN", f"robo-change-specify stderr: {stderr_str[:200]}",
                            category="requirement_changes.skill.stderr", params={"changeId": change_id})

        # JSON 블록 추출 (마크다운 코드블록 처리)
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not json_match:
            SmartLogger.log("WARN", f"No JSON found in skill output for {change_id}: {raw[:200]}",
                            category="requirement_changes.skill.no_json", params={"changeId": change_id})
            return None

        result = json.loads(json_match.group())
        SmartLogger.log("INFO",
                        f"robo-change-specify done: {len(result.get('effects', []))} effects for {change_id}",
                        category="requirement_changes.skill.done",
                        params={"changeId": change_id, "effectCount": len(result.get("effects", []))})
        return result

    except asyncio.TimeoutError:
        SmartLogger.log("ERROR", f"robo-change-specify timeout for {change_id}",
                        category="requirement_changes.skill.timeout", params={"changeId": change_id})
    except Exception as e:
        SmartLogger.log("ERROR", f"robo-change-specify error for {change_id}: {e}",
                        category="requirement_changes.skill.error",
                        params={"changeId": change_id, "error": str(e)})
    return None


async def run_skill_lines(
    skill_name: str,
    args: dict,
    human_prompt: str | None = None,
    add_dirs: list[str] | None = None,
) -> AsyncGenerator[str, None]:
    """
    스킬을 실행하고 stdout 라인을 하나씩 yield하는 async generator.
    robo-change-tasks 같은 스킬의 스트리밍 출력(PHASE:/TASK:/TASK_DONE:)을 SSE로 전달할 때 사용.

    Args:
        skill_name: skills/robo-changes/ 아래 디렉터리명 (e.g. "robo-change-tasks")
        args: 스킬에 전달할 인자 dict. human_prompt가 제공된 경우 무시됨.
        human_prompt: 완전한 human turn 텍스트. 제공 시 args 무시.
        add_dirs: 추가로 접근 허용할 디렉터리 경로 목록 (--add-dir 플래그로 전달)
    """
    claude_bin = shutil.which("claude") or "claude"
    skill_file = _skill_path(skill_name)

    if human_prompt is None:
        args_str = "\n".join(f"--{k}: {v}" for k, v in args.items())
        human_prompt = f"Execute skill with parameters:\n{args_str}"

    cmd = [
        claude_bin, "-p", human_prompt,
        "--system-prompt-file", str(skill_file),
        "--output-format", "text",
        "--dangerously-skip-permissions",
    ]
    for d in (add_dirs or []):
        cmd += ["--add-dir", d]

    SmartLogger.log("INFO", f"Streaming skill: {skill_name}",
                    category="requirement_changes.skill.stream_start",
                    params={"skill": skill_name, "args": args})

    if not skill_file.exists():
        SmartLogger.log("ERROR", f"Skill not found: {skill_file}",
                        category="requirement_changes.skill.not_found", params={"skill": skill_name})
        yield f"PHASE:error"
        return

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(_PROJECT_ROOT),
            env=_skill_env(),
        )

        buf = b""
        while True:
            chunk = await asyncio.wait_for(proc.stdout.read(256), timeout=180)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line_bytes, buf = buf.split(b"\n", 1)
                line = line_bytes.decode("utf-8", errors="replace").strip()
                if line:
                    yield line

        # flush remaining
        if buf.strip():
            yield buf.decode("utf-8", errors="replace").strip()

        await proc.wait()

    except asyncio.TimeoutError:
        SmartLogger.log("ERROR", f"Skill stream timeout: {skill_name}",
                        category="requirement_changes.skill.stream_timeout",
                        params={"skill": skill_name})
        yield "PHASE:error"
    except Exception as e:
        SmartLogger.log("ERROR", f"Skill stream error: {skill_name}: {e}",
                        category="requirement_changes.skill.stream_error",
                        params={"skill": skill_name, "error": str(e)})
        yield "PHASE:error"
