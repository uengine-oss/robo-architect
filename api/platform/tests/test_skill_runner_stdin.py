"""Regression tests for Windows-safe skill prompt transport."""

import asyncio
import sys

from api.platform.skill_runner import (
    _run_process_sync,
    _stream_process_chunks_with_stdin,
)


def test_sync_process_preserves_long_stdin_bytes():
    prompt = ("주문-재고 전체 계획\n" * 20_000).encode("utf-8")
    completed = _run_process_sync(
        [sys.executable, "-c", "import sys; data=sys.stdin.buffer.read(); print(len(data))"],
        ".",
        10,
        prompt,
    )

    assert completed.returncode == 0
    assert int(completed.stdout.strip()) == len(prompt)


def test_stream_process_preserves_long_stdin_bytes():
    prompt = ("strategic+tactical+constitution+plan\n" * 20_000).encode("utf-8")

    async def collect() -> bytes:
        chunks = []
        async for chunk in _stream_process_chunks_with_stdin(
            [sys.executable, "-c", "import sys; data=sys.stdin.buffer.read(); print(len(data))"],
            ".",
            10,
            prompt,
        ):
            chunks.append(chunk)
        return b"".join(chunks)

    assert int(asyncio.run(collect()).strip()) == len(prompt)
