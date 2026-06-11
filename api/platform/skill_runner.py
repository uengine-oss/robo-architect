"""
플랫폼 공통 스킬 러너. 038 skill_runner.py에서 승격.
PTY 기반 claude CLI 호출 + 스트리밍 라인 generator.
"""

from __future__ import annotations

import asyncio
import json
import queue
import re
import shutil
import subprocess
import threading
from pathlib import Path
from typing import AsyncGenerator

from api.platform.observability.smart_logger import SmartLogger

_PROJECT_ROOT = Path(__file__).parents[2]

# _stream_process_chunks 내부 큐 종료/에러 신호용 센티넬.
_STREAM_DONE = object()
_STREAM_ERR = object()


def skill_path(skill_root: str, skill_name: str) -> Path:
    """skills/{skill_root}/{skill_name}/SKILL.md 절대 경로를 반환한다."""
    return _PROJECT_ROOT / "skills" / skill_root / skill_name / "SKILL.md"


def _run_process_sync(
    cmd: list[str], cwd: str, timeout: int
) -> subprocess.CompletedProcess:
    """블로킹 subprocess.run. 워커 스레드에서 호출된다."""
    return subprocess.run(cmd, capture_output=True, cwd=cwd, timeout=timeout)


async def _stream_process_chunks(
    cmd: list[str], cwd: str, timeout: int
) -> AsyncGenerator[bytes, None]:
    """
    cmd 를 블로킹 subprocess 로 실행하고 stdout 바이트 청크를 도착하는 즉시 yield 한다.
    스폰·읽기는 전용 워커 스레드에서 수행하므로 이벤트 루프 종류와 무관하게 동작한다.

    - bufsize=0(언버퍼드): proc.stdout.read(n)가 데이터가 도착하는 즉시 반환 → 실시간 스트리밍 보존.
    - stderr 는 별도 스레드에서 끝까지 비워 파이프 버퍼 풀(deadlock)을 방지한다.
    - 소비자(async generator) 종료 시 finally 에서 서브프로세스를 확실히 kill 한다.
    """
    q: queue.Queue = queue.Queue(maxsize=256)
    holder: dict = {}

    def _reader() -> None:
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd,
                bufsize=0,
            )
            holder["proc"] = proc
            # stderr 드레인 스레드: 읽지 않으면 stderr 파이프가 차서 child 가 멈출 수 있다.
            threading.Thread(
                target=lambda: proc.stderr.read() if proc.stderr else None,
                daemon=True,
            ).start()
            while True:
                chunk = proc.stdout.read(4096)
                if not chunk:
                    break
                q.put(chunk)
        except Exception as e:  # noqa: BLE001 - 메인 코루틴으로 그대로 전달
            q.put((_STREAM_ERR, e))
        finally:
            q.put(_STREAM_DONE)

    threading.Thread(target=_reader, daemon=True).start()

    try:
        while True:
            item = await asyncio.wait_for(asyncio.to_thread(q.get), timeout=timeout)
            if item is _STREAM_DONE:
                break
            if isinstance(item, tuple) and item and item[0] is _STREAM_ERR:
                raise item[1]
            yield item
    finally:
        proc = holder.get("proc")
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                pass


async def run_skill_once(
    skill_root: str,
    skill_name: str,
    human_prompt: str,
    timeout: int = 120,
    add_dirs: list[str] | None = None,
) -> str | None:
    """
    스킬을 단회 실행하고 stdout 전체를 문자열로 반환한다.
    JSON 블록 추출이 필요한 경우 호출자가 직접 파싱.
    """
    claude_bin = shutil.which("claude") or "claude"
    sf = skill_path(skill_root, skill_name)

    if not sf.exists():
        SmartLogger.log("ERROR", f"Skill not found: {sf}",
                        category="platform.skill_runner.not_found", params={"skill": skill_name})
        return None

    cmd = [
        claude_bin, "-p", human_prompt,
        "--system-prompt-file", str(sf),
        "--output-format", "text",
        "--dangerously-skip-permissions",
    ]
    for d in (add_dirs or []):
        cmd += ["--add-dir", d]

    SmartLogger.log("INFO", f"Invoking skill: {skill_name}",
                    category="platform.skill_runner.start",
                    params={"skill": skill_name})
    try:
        # 루프-무관 블로킹 subprocess 를 워커 스레드에서 실행 (헤더 주석 참조).
        completed = await asyncio.to_thread(
            _run_process_sync, cmd, str(_PROJECT_ROOT), timeout
        )
        raw = completed.stdout.decode("utf-8", errors="replace").strip()

        stderr_str = completed.stderr.decode("utf-8", errors="replace").strip()
        if stderr_str:
            SmartLogger.log("WARN", f"Skill {skill_name} stderr: {stderr_str[:200]}",
                            category="platform.skill_runner.stderr", params={"skill": skill_name})

        SmartLogger.log("INFO", f"Skill {skill_name} done",
                        category="platform.skill_runner.done", params={"skill": skill_name})
        return raw

    except subprocess.TimeoutExpired:
        SmartLogger.log("ERROR", f"Skill {skill_name} timeout",
                        category="platform.skill_runner.timeout", params={"skill": skill_name})
    except Exception as e:
        SmartLogger.log("ERROR", f"Skill {skill_name} error: {e}",
                        category="platform.skill_runner.error",
                        params={"skill": skill_name, "error": str(e)})
    return None


async def run_skill_lines(
    skill_root: str,
    skill_name: str,
    human_prompt: str,
    add_dirs: list[str] | None = None,
    cwd: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    스킬을 실행하고 stdout 라인을 하나씩 yield하는 async generator.
    --output-format stream-json 으로 실시간 tool-use 이벤트를 포함해 스트리밍.
    protocol lines (TASK_START:, TASK_DONE:, PHASE:) + TOOL:ToolName:path 형식으로 yield.
    """
    claude_bin = shutil.which("claude") or "claude"
    sf = skill_path(skill_root, skill_name)

    if not sf.exists():
        SmartLogger.log("ERROR", f"Skill not found: {sf}",
                        category="platform.skill_runner.not_found", params={"skill": skill_name})
        yield "PHASE:error"
        return

    cmd = [
        claude_bin, "-p", human_prompt,
        "--system-prompt-file", str(sf),
        "--output-format", "stream-json",
        "--verbose",
        # 토큰 단위 실시간 스트리밍. 이게 없으면 assistant 메시지가 완성된 뒤
        # 전체 텍스트(narration+JSON)가 한 번에 도착해 "한꺼번에 덤프"되어 보인다.
        "--include-partial-messages",
        "--dangerously-skip-permissions",
    ]
    for d in (add_dirs or []):
        cmd += ["--add-dir", d]

    SmartLogger.log("INFO", f"Streaming skill (stream-json): {skill_name}",
                    category="platform.skill_runner.stream_start",
                    params={"skill": skill_name})

    chunks: AsyncGenerator[bytes, None] | None = None
    try:
        # 루프-무관 블로킹 subprocess + 워커 스레드 (헤더 주석 참조).
        # create_subprocess_exec 를 쓰면 Windows --reload(SelectorEventLoop)에서
        # NotImplementedError 로 즉사한다.
        chunks = _stream_process_chunks(cmd, cwd or str(_PROJECT_ROOT), timeout=1800)

        text_buffer = ""
        raw_buf = b""
        # 토큰 델타로 텍스트를 이미 스트리밍했는지 추적.
        # True면 뒤따라오는 assistant/result 이벤트의 텍스트는 중복이므로 무시.
        streamed_text = False

        while True:
            try:
                chunk = await chunks.__anext__()
            except StopAsyncIteration:
                break
            except asyncio.TimeoutError:
                SmartLogger.log("ERROR", f"Skill stream timeout (1800s): {skill_name}",
                                category="platform.skill_runner.stream_timeout",
                                params={"skill": skill_name})
                yield "PHASE:error"
                return

            raw_buf += chunk
            while b"\n" in raw_buf:
                json_bytes, raw_buf = raw_buf.split(b"\n", 1)
                json_line = json_bytes.decode("utf-8", errors="replace").strip()
                if not json_line:
                    continue

                try:
                    event = json.loads(json_line)
                except json.JSONDecodeError:
                    continue

                evt_type = event.get("type", "")

                # 1) 토큰 단위 실시간 스트리밍 (--include-partial-messages)
                if evt_type == "stream_event":
                    se = event.get("event", {})
                    se_type = se.get("type", "")
                    if se_type == "content_block_delta":
                        delta = se.get("delta", {})
                        if delta.get("type") == "text_delta":
                            streamed_text = True
                            text_buffer += delta.get("text", "")
                            while "\n" in text_buffer:
                                proto_line, text_buffer = text_buffer.split("\n", 1)
                                proto_line = proto_line.strip()
                                if proto_line:
                                    yield proto_line
                    elif se_type == "content_block_stop":
                        # 텍스트 블록 종료 시 마지막(개행 없는) 라인 flush
                        if text_buffer.strip():
                            yield text_buffer.strip()
                            text_buffer = ""

                # 2) assistant 이벤트: tool_use는 여기서(완성된 input) 추출.
                #    텍스트는 델타로 이미 스트리밍했으면 중복이므로 skip.
                elif evt_type == "assistant":
                    content = event.get("message", {}).get("content", [])
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        if block.get("type") == "text":
                            if streamed_text:
                                continue  # 델타로 이미 출력됨
                            text_buffer += block.get("text", "")
                            while "\n" in text_buffer:
                                proto_line, text_buffer = text_buffer.split("\n", 1)
                                proto_line = proto_line.strip()
                                if proto_line:
                                    yield proto_line
                        elif block.get("type") == "tool_use":
                            tool_name = block.get("name", "")
                            tool_input = block.get("input", {})
                            file_path = (
                                tool_input.get("file_path")
                                or tool_input.get("path")
                                or ""
                            )
                            yield f"TOOL:{tool_name}:{file_path}"

                # 3) result 이벤트: 델타 스트리밍이 없었던 경우에만 fallback 출력.
                elif evt_type == "result":
                    if streamed_text:
                        continue  # 델타로 이미 출력됨
                    result_text = event.get("result", "")
                    if result_text:
                        combined = text_buffer + result_text
                        for line in combined.splitlines():
                            line = line.strip()
                            if line:
                                yield line
                        text_buffer = ""

        # flush remaining text
        if text_buffer.strip():
            for line in text_buffer.strip().splitlines():
                line = line.strip()
                if line:
                    yield line

        SmartLogger.log("INFO", f"Skill stream done: {skill_name}",
                        category="platform.skill_runner.stream_done",
                        params={"skill": skill_name})

    except (GeneratorExit, asyncio.CancelledError):
        # 클라이언트(SSE) 연결 끊김 → generator가 닫힘. 서브프로세스를 정리하고 재-raise.
        # finally에서 chunks.aclose()(→ 서브프로세스 kill)가 수행되므로 여기서는 로그만.
        SmartLogger.log("WARN", f"Skill stream cancelled (client disconnect): {skill_name}",
                        category="platform.skill_runner.stream_cancelled",
                        params={"skill": skill_name})
        raise
    except Exception as e:
        # str(e)가 빈 예외(e.g. NotImplementedError)도 진단 가능하도록 타입까지 기록.
        SmartLogger.log("ERROR", f"Skill stream error: {skill_name}: {type(e).__name__}: {e}",
                        category="platform.skill_runner.stream_error",
                        params={"skill": skill_name, "error": str(e),
                                "errorType": type(e).__name__})
        yield "PHASE:error"
    finally:
        # 어떤 경로로 종료되든(완료/타임아웃/클라이언트 끊김/예외) 서브프로세스를 확실히 종료.
        # 이게 없으면 claude CLI 서브프로세스가 고아로 남아 누적 → 리소스 고갈.
        # chunks.aclose()가 _stream_process_chunks 의 finally(proc.kill())를 트리거한다.
        if chunks is not None:
            try:
                await chunks.aclose()
            except Exception:
                pass


def extract_json(raw: str) -> dict | list | None:
    """stdout에서 JSON 블록을 추출한다.
    ```json ... ``` 코드블록을 우선 시도하고, 없으면 첫 번째 {...} 또는 [...] 블록을 파싱.
    """
    # 1) ```json ... ``` 코드블록 우선
    code_match = re.search(r'```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```', raw, re.DOTALL)
    if code_match:
        try:
            return json.loads(code_match.group(1))
        except Exception:
            pass

    # 2) 마지막 {...} 블록 (narration에 {} 포함 가능 → 마지막 블록이 실제 JSON일 가능성 높음)
    matches = list(re.finditer(r'(\{[^`]*\})', raw, re.DOTALL))
    for m in reversed(matches):
        try:
            result = json.loads(m.group())
            if isinstance(result, dict) and result:
                return result
        except Exception:
            continue

    # 3) 첫 번째 [...] 블록
    arr_match = re.search(r'(\[.*?\])', raw, re.DOTALL)
    if arr_match:
        try:
            return json.loads(arr_match.group())
        except Exception:
            pass

    return None
