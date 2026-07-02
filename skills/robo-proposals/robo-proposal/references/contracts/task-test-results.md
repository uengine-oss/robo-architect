# Task And Test Contracts

Tasks:

```json
{ "tasks": [{ "id": "T001", "phase": "Phase 1: Setup", "text": "...", "files": [], "parallel": false }] }
```

TestRunResult:

```json
{ "proposalId": "PRO-NNN", "totalScenarios": 0, "passed": 0, "failed": 0, "skipped": 0, "items": [] }
```

Each test item:

```json
{ "scenarioId": "SC-001", "category": "acceptance", "storyId": "US-1", "storyTitle": "...", "scenario": "Given ... When ... Then ...", "result": "PASS", "reason": null }
```

`result` is `PASS`, `FAIL`, or `SKIPPED`.
