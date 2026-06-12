from __future__ import annotations

import json
from typing import AsyncGenerator

from api.features.requirement_changes.requirement_changes_contracts import (
    ImplementationProgress,
    TaskItem,
    TaskStatus,
)


async def parse_tasks_stream(
    change_id: str,
    lines: AsyncGenerator[str, None],
) -> AsyncGenerator[str, None]:
    """robo-change-tasks stdout 라인을 SSE 이벤트로 변환하는 async generator."""
    tasks: dict[str, TaskItem] = {}
    phase = "planning"
    percentage = 0

    async for line in lines:
        if line.startswith("PHASE:"):
            phase = line[6:].strip()
            if phase == "executing":
                percentage = 30
            elif phase == "done":
                percentage = 100
            progress = ImplementationProgress(
                changeId=change_id,
                phase=phase,
                percentage=percentage,
                tasks=list(tasks.values()),
                message=f"Phase: {phase}",
            )
            yield f"data: {progress.model_dump_json()}\n\n"

        elif line.startswith("TASK:"):
            parts = line[5:].split(":", 2)
            if len(parts) >= 2:
                task_id = parts[0]
                title = parts[1] if len(parts) > 1 else ""
                status = TaskStatus(parts[2]) if len(parts) > 2 and parts[2] in TaskStatus.__members__ else TaskStatus.PENDING
                tasks[task_id] = TaskItem(taskId=task_id, title=title, status=status)
            progress = ImplementationProgress(
                changeId=change_id,
                phase=phase,
                percentage=percentage,
                tasks=list(tasks.values()),
            )
            yield f"data: {progress.model_dump_json()}\n\n"

        elif line.startswith("TASK_START:"):
            task_id = line[11:].strip()
            if task_id in tasks:
                tasks[task_id].status = TaskStatus.IN_PROGRESS
            progress = ImplementationProgress(
                changeId=change_id,
                phase=phase,
                percentage=min(percentage + 5, 90),
                tasks=list(tasks.values()),
            )
            yield f"data: {progress.model_dump_json()}\n\n"

        elif line.startswith("TASK_DONE:"):
            task_id = line[10:].strip()
            if task_id in tasks:
                tasks[task_id].status = TaskStatus.DONE
            done_count = sum(1 for t in tasks.values() if t.status == TaskStatus.DONE)
            total = max(len(tasks), 1)
            percentage = max(30, int(30 + 60 * done_count / total))
            progress = ImplementationProgress(
                changeId=change_id,
                phase=phase,
                percentage=percentage,
                tasks=list(tasks.values()),
            )
            yield f"data: {progress.model_dump_json()}\n\n"
