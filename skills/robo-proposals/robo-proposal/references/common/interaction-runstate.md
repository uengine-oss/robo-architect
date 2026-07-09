# Interaction RunState

## User decision (question)

1. Produce one question only.
2. Call `proposal_record_question`.
3. Return an `action:"clarify"` envelope and stop.
4. On answer, use `proposal_answer_question`, then `proposal_resume`.

## Draft — validate before presenting (P1)

The server validates on **save**, not on confirm. So a saved draft is already valid; a presented draft is always one the user can approve without a later large rewrite.

1. Generate the artifact in canonical shape.
2. Call `proposal_save_draft`.
   - **On `status:"ok"`** → the draft passed validation and is stored. Present it in the order **`headerMarkdown` (진행 상단) → `reportMarkdown` verbatim → `footerMarkdown` (선택지 하단)** (see `references/common/report-contract.md`), then — because the step's `requiresUserApproval` is true — wait for the user.
   - **On `status:"invalid"`** → the draft was **rejected and not stored**. Read `violations`, fix them, and call `proposal_save_draft` again. This is the **regeneration loop**.
   - **On `status:"invalid-transition"`** → a prior required step is incomplete. Surface the message and stop; do not draft this phase yet.
3. Promote only after the user approves, via `proposal_confirm_draft` (promotion only — it does not re-validate).

### Regeneration loop cap (max 3)

Retry `proposal_save_draft` at most **3 times** for the same step (`nextStep.retryContext.maxAttempts`). `retryContext.attempts` counts consecutive validation failures for the current phase. If the 3rd attempt still returns `invalid` (`retryContext.exhausted` is true):

- Do **not** advance to the next step or fabricate a passing artifact.
- Surface the remaining `violations` to the user and ask how to proceed (request the missing information / a decision).

## Approval gate

Whenever `nextStep.requiresUserApproval` is true, you must wait for an explicit user approval before the promoting tool call (`proposal_confirm_draft`, `proposal_submit` for user-visible steps, `proposal_accept`). Never self-approve.

## Rollback

If the user explicitly asks to go back to an earlier step, check it is in `nextStep.allowedUserOverrides`, then call `proposal_rollback(proposalId, targetPhase[, targetStage])`. Downstream artifacts become stale/invalid (server clears them and lists them in `staleArtifacts`); re-run those steps via `proposal_next_step`.

Resume context should include the Proposal summary, pending interaction, recent interaction window, and confirmed artifact summary. Do not replay the full history unless the user asks.
