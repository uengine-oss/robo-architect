---
name: robo-proposal
description: Proposal lifecycle을 시작, 재개, DDD 단계 진행, diff 수렴, tasks/test/implement까지 처리하는 단일 스킬
---

# Skill: robo-proposal

## 0. Scope

This is the single Proposal lifecycle skill. It replaces the previous Proposal lifecycle skills except `robo-proposal-oda`, which remains a separate standard-mode skill.

## 1. Routing Rules — The server is the single authority for ordering

**You are a thin renderer.** The `robo-proposal` MCP server owns lifecycle order, gates, and validation. Do **not** infer "the next phase/stage" yourself. Every turn (except the mode-selection gate in rule 4), call `proposal_next_step` and perform **only** the `action` it returns, for exactly the `phase`/`stage` it names. See `references/common/routing.md` for the action-dispatch table.

1. **No LLM self-override.** You may never choose a `phase`/`stage` to jump to on your own. Order comes from `proposal_next_step` only.
2. **User-explicit override only, guarded.** If (and only if) the *user* explicitly asks to move to a specific step, you may pass `phase:` to `proposal_next_step`. The server enforces the transition guard: a forward jump returns `blocked`/`invalid-transition` (obey it, do not proceed); a backward move to a step listed in `allowedUserOverrides` is a rollback — call `proposal_rollback`. If explicit input conflicts with a pending question/draft, the server returns `blocked` — surface it and stop.
3. If no explicit routing input exists, use the MCP tools to list/select/resume a Proposal, then drive via `proposal_next_step`.
4. **Mode-selection gate (new Proposal only):** Before calling `proposal_create` for a brand-new Proposal, decide the decomposition mode per `references/phases/mode-selection.md`. If the user did **not** explicitly name a mode, you MUST ask which mode to use (with a short description of each) and wait — do not create the Proposal or generate any Diff yet. If the user gave an explicit mode, skip the question and create immediately with that mode. This gate does not apply when resuming an existing Proposal. **This is the only place you decide flow; after the Proposal exists, the server decides.**
5. Ask at most one core question at a time. Store the question with `proposal_record_question` before waiting for an answer. (The mode-selection question in rule 4 is asked before the Proposal exists, so it is a plain conversational question and is not recorded via `proposal_record_question`.)
6. **Validate-before-present (P1).** Store draft artifacts with `proposal_save_draft`, which **validates before storing**. If it returns `status:"invalid"` (or `invalid-transition`), the draft was **not** saved — fix the listed violations and call `proposal_save_draft` again (regeneration loop). Retry at most **3 times** (`retryContext.maxAttempts`); if still failing, surface the violations to the user, ask for help, and **do not advance**. Only a draft that `proposal_save_draft` accepted may be presented to the user and later promoted with `proposal_confirm_draft`.

Always read:

- `references/common/routing.md`
- `references/common/mcp-tools.md`
- `references/common/output-contracts.md`
- `references/common/validator-rules.md`
- `references/common/report-contract.md`

**Present/output rule (013-report-mcda):** whenever you show a step artifact, question, or
validation error, follow `references/common/report-contract.md` — output the server's
`reportMarkdown` verbatim and render the `nextStep.progressMeta` header; only fall back to
the lightweight key table when `reportMarkdown` is absent.

## 2. Reference Loading Table

| Situation | Read |
|---|---|
| new Proposal / mode choice | `references/phases/mode-selection.md` |
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
