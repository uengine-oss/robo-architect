# Output Contracts

Final artifacts must keep the existing backend contracts.

Strategic:

```json
{ "action": "done", "strategicDiff": { "version": 1, "epics": [], "features": [], "userStories": [], "processes": [] }, "journeys": [] }
```

Clarify:

```json
{ "action": "clarify", "questions": [{ "index": 0, "text": "...", "options": ["...", "..."] }] }
```

Tactical/Plan:

```json
{ "tacticalDiff": [], "implementationPlan": { "version": 1, "architectureDecisions": [], "constitutionGaps": [] } }
```

Stage artifacts use the top-level keys documented in `references/contracts/stage-artifacts.md`.
