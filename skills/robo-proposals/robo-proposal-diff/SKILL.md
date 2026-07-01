---
name: robo-proposal-diff
description: Proposal Strategic/Tactical Diff and architecture plan generator for Simplified and Detailed DDD flows.
---

# Skill: robo-proposal-diff

## Purpose
Generate Proposal Diff artifacts for four explicit scenarios:

- `SIMPLIFIED_STRATEGIC`: natural language requirement -> Strategic Diff only.
- `SIMPLIFIED_TACTICAL`: approved Strategic Diff + Constitution -> Tactical Diff + implementationPlan.
- `DETAILED_STRATEGIC_FROM_DDD`: Discover/Decompose/Strategize artifacts -> Strategic Diff.
- `DETAILED_TACTICAL_FROM_DDD`: Connect/Define/Tactical artifacts -> Tactical Diff.

The runner always passes a `scenario:` line. Use it to load only the references needed for that scenario.

## Reference Selection
Always read:

- `skills/robo-proposals/robo-proposal-diff/references/common-contract.md`

Then read only one scenario entrypoint:

- Strategic scenarios: `references/strategic-diff.md`
- Tactical scenarios: `references/tactical-diff.md`

Do not read legacy individual Diff skill references.

## Input
The human prompt includes:

- `Proposal ID`
- `scenario`
- original prompt and/or approved Strategic Diff
- optional Constitution
- optional Detailed DDD artifacts
- optional backend validator feedback for retry attempts

## Output
Before JSON, narrate the analysis in Korean using concise tagged lines such as `[요구사항]`, `[전략]`, `[전술]`, `[아키텍처]`, `[검증]`.

For `SIMPLIFIED_STRATEGIC` and `DETAILED_STRATEGIC_FROM_DDD`:

```json
{ "action": "done", "strategicDiff": { "version": 1, "epics": [], "features": [], "userStories": [], "processes": [] }, "journeys": [] }
```

For `SIMPLIFIED_STRATEGIC` only, if truly blocked by ambiguity:

```json
{ "action": "clarify", "questions": [{ "index": 0, "text": "...", "options": ["...", "..."] }] }
```

For `SIMPLIFIED_TACTICAL`:

```json
{ "tacticalDiff": [], "implementationPlan": { "version": 1, "architectureDecisions": [], "constitutionGaps": [] } }
```

For `DETAILED_TACTICAL_FROM_DDD`:

```json
{ "tacticalDiff": [] }
```

## Rules
1. Follow `scenario` exactly. Do not emit Tactical Diff in Strategic scenarios.
2. Backend validator feedback is authoritative. On retry, fix every listed violation.
3. Use canonical field names only. Legacy aliases are contract failures.
4. Every CREATE item needs a stable `tempId` or `nodeId` and parent refs.
5. No name-only design nodes. Tactical Aggregate/Command/Event/ReadModel items need concrete properties and schemas.
6. Keep generated names in the user's language where appropriate, but property/schema keys must be English camelCase.
