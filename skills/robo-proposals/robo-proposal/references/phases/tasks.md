# Tasks

Break Strategic Diff, Tactical Diff, Constitution, and Implementation Plan into implementable tasks. Do not implement code.

Output:

```json
{ "tasks": [{ "id": "T001", "phase": "Phase 1: Setup", "text": "도메인 디렉터리 구조 생성", "files": ["src/domain/"], "parallel": false }] }
```

Rules:

- Cover every meaningful Strategic/Tactical change.
- Order by dependency: setup, domain, behavior/API, frontend, tests.
- Keep tasks as logical commit units.
- If Constitution or Plan conflicts with a task, mark it clearly instead of hiding it.
