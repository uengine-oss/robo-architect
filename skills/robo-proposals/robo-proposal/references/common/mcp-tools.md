# MCP Tools

Use the `robo-proposal` MCP server for lifecycle state:

- `proposal_create`, `proposal_get`, `proposal_list`, `proposal_next_step`
- `proposal_save_stage_plan`, `proposal_skip_stage`, `proposal_save_stage_artifact`
- `proposal_save_draft`, `proposal_confirm_draft`, `proposal_reject_draft`
- `proposal_save_diff`
- `proposal_record_question`, `proposal_answer_question`, `proposal_resume`
- `proposal_generate_tasks`, `proposal_update_implementation_status`, `proposal_save_test_result`
- `proposal_prepare_sandbox`, `proposal_get_constitution`
- `proposal_submit`, `proposal_accept`, `proposal_rollback`

### `proposal_prepare_sandbox` — the worktree location is not a question

`proposal_prepare_sandbox(proposalId, projectRoot)` creates the git worktree at
`<projectRoot>/.sandbox/proposal/<PRO-NNN>` on branch `proposal/<PRO-NNN>` and records
`projectRoot` on the Proposal (Accept needs it). Call it once when `action = run_implement`, and
implement only inside the returned `worktreePath`. Never ask the user to choose a location and
never create a sibling directory like `<projectRoot>-PRO-NNN`.

### `proposal_update_implementation_status` — closes the IMPLEMENT step

Call `proposal_update_implementation_status(proposalId, "DONE")` when the implementation is
finished and committed. Without it the Proposal never leaves `IMPLEMENT`.

### `proposal_get_constitution` — is there a project Constitution node?

Returns `{exists, constitution}` for the project-root `:Constitution` node. When
`nextStep.phase = PROJECT_CONSTITUTION` the node does not exist yet: interview the architect,
then create it (see `references/phases/constitution.md`).

### `proposal_accept` — Accept writes the design to the live graph

`proposal_accept(proposalId)` is not a status flip: it merges the worktree branch and applies the
strategic + tactical Diff to the **live Neo4j graph** (BoundedContext / Feature / UserStory /
Aggregate / ValueObject / Enumeration / Command / Event / …), then sets `ACCEPTED`. It returns
`applied` and `liveGraph` (node counts per label) — report those. On `status:"failed"` the graph
was **not** written; surface the reason instead of reporting success.

### `proposal_create` — required arguments

Signature: `proposal_create(originalPrompt, title?, mode?, author?)`.

- `originalPrompt` **(required)** — the user's raw natural-language requirement text. Omitting it fails with pydantic `originalPrompt Field required`.
- `title` (optional) — auto-derived from `originalPrompt` if omitted.
- `mode` (optional, default `SIMPLIFIED`) — `SIMPLIFIED` or `DETAILED_DDD`. Pass the mode fixed by `mode-selection.md`.
- `author` (optional, default `mcp`).

Always pass at least `originalPrompt` and `mode`.

### `proposal_next_step` — the ordering authority

Returns `nextStep` with the extended imperative schema. Perform only its `action`:

```
phase, stage, action, requiresUserApproval, validationRef, reason,
allowedUserOverrides, retryContext, staleArtifacts
```

`action ∈ { generate_draft, await_approval, confirm, ask_question, run_implement, run_test, finalize }`. See `routing.md` for dispatch. Do not derive the next phase any other way.

### `proposal_save_draft` — validates before storing

Validates the artifact for the phase **before** persisting. Returns `status:"ok"` (stored, presentable) or `status:"invalid"` / `invalid-transition` (not stored). `proposal_confirm_draft` then does promotion only (no re-validation).

### `proposal_rollback` — user-explicit only

`proposal_rollback(proposalId, targetPhase[, targetStage])` moves back to a step in `allowedUserOverrides` and invalidates downstream artifacts (`staleArtifacts`). Only when the user explicitly requests it. Forward jumps are impossible — the server hard-blocks them.

Rules:

1. Neo4j is the source of truth. The server, not the LLM, owns lifecycle order/gates/validation.
2. Do not use workspace files to remember lifecycle state.
3. If a tool returns `invalid`, `invalid-transition`, or `blocked`, stop and report that failure — never auto-advance.
4. Store user-facing waits as interactions: questions as `QUESTION`, drafts as `DRAFT`.
