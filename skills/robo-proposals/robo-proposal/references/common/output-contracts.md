# Output Contracts

Final artifacts must keep the existing backend contracts.

Strategic:

```json
{ "action": "done", "strategicDiff": { "version": 1, "epics": [], "features": [], "userStories": [], "processes": [] }, "journeys": [] }
```

Clarify (Proposal lifecycle questions after `proposal_create` only):

```json
{ "action": "clarify", "questions": [{ "index": 0, "text": "...", "options": ["...", "..."] }] }
```

This contract does **not** apply to the pre-creation mode-selection gate. When a
new Proposal request has no explicit mode, prefer the host's structured question
tool (`AskUserQuestion` in Claude Code; equivalent `AskQuestion` in other hosts).
If unavailable, ask the same question in plain text. Emit no JSON envelope in
either case.

Tactical/Plan:

```json
{ "tacticalDiff": [], "implementationPlan": { "version": 1, "architectureDecisions": [], "constitutionGaps": [] } }
```

Stage artifacts use the top-level keys documented in `references/contracts/stage-artifacts.md`.
