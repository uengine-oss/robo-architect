---
name: robo-proposal
description: Proposal lifecycle을 시작, 재개, DDD 단계 진행, diff 수렴, tasks/test/implement까지 처리하는 단일 스킬
---

# Skill: robo-proposal

## 0. Scope

This is the single Proposal lifecycle skill. It replaces the previous Proposal lifecycle skills except `robo-proposal-oda`, which remains a separate standard-mode skill.

## 1. Routing Rules

1. If the prompt contains explicit `mode`, `phase`, `stage`, or `scenario`, honor that input before reading Neo4j state.
2. If explicit input conflicts with pending state, stop with one question or a validator-style error. Do not continue silently.
3. If no explicit routing input exists, use the `robo-proposal` MCP tools to list/select/resume a Proposal and call `proposal_next_step`.
4. Ask at most one core question at a time. Store the question with `proposal_record_question` before waiting for an answer.
5. Store draft artifacts with `proposal_save_draft`; only confirmed artifacts may be promoted to canonical fields.

Always read:

- `references/common/routing.md`
- `references/common/mcp-tools.md`
- `references/common/output-contracts.md`
- `references/common/validator-rules.md`

## 2. Reference Loading Table

| Situation | Read |
|---|---|
| start/resume | `references/common/state-model.md`, `references/common/interaction-runstate.md`, `references/phases/start-or-resume.md` |
| scope/stagePlan | `references/phases/scope.md`, `references/contracts/stage-artifacts.md` |
| Detailed DDD stage | `references/phases/detailed-ddd.md`, `references/contracts/stage-artifacts.md` |
| Strategic/Tactical Diff | `references/phases/diff.md`, `references/contracts/strategic-diff.md`, `references/contracts/tactical-diff.md` |
| Constitution | `references/phases/constitution.md` |
| Context impact | `references/phases/context.md` |
| Tasks | `references/phases/tasks.md`, `references/contracts/task-test-results.md` |
| Test | `references/phases/test.md`, `references/contracts/task-test-results.md` |
| Implement | `references/phases/implement.md` |

## 3. Output Contract Rules

Final artifacts keep the existing canonical contracts:

- Strategic: `{ "action": "done", "strategicDiff": { ... }, "journeys": [] }`
- Tactical/Plan: `{ "tacticalDiff": [], "implementationPlan": { ... } }`
- Stage artifacts: top-level key matching the stage artifact name.
- Tasks/Test: contracts in `references/contracts/task-test-results.md`.

Intermediate states use an envelope:

```json
{ "action": "clarify | interrupt | draft | error | nextStep", "proposalId": "PRO-NNN", "phase": "SCOPE", "artifact": {}, "questions": [], "draftRef": null, "nextStep": null, "validation": null }
```

## 4. Error And Validator Rules

Backend validator feedback is authoritative. On retry, fix the listed violations before creating new content. If MCP tools are missing or fail, do not use ad hoc files as state; return a clear `error` envelope explaining that the `robo-proposal` MCP server must be enabled.

## 5. Safety Rules

Implement mode may modify files only inside the Proposal worktree. Do not change the parent or main project. ODA mode is not handled here; route ODA requests to `robo-proposal-oda`.
