# Routing — server-driven, thin renderer

The server owns ordering. You do **not** compute "the next phase." While a Proposal is in progress, every turn:

1. Call `proposal_next_step(proposalId)`.
2. Read `nextStep` and perform **only** its `action` for its `phase`/`stage`. Do not substitute your own step.

## Action dispatch (`nextStep.action`)

`proposal_next_step` returns an extended, imperative action:

```json
{
  "phase": "TACTICAL_DIFF", "stage": null, "action": "generate_draft",
  "requiresUserApproval": true, "validationRef": "tactical", "reason": "...",
  "allowedUserOverrides": [{"phase":"STRATEGIC_DIFF","stage":null}],
  "retryContext": null, "staleArtifacts": []
}
```

| `action` | Do exactly this |
|---|---|
| `generate_draft` | Generate the artifact for `phase`/`stage` in canonical shape, call `proposal_save_draft`. If it returns `invalid`, run the regeneration loop (see interaction-runstate.md). On success, present the validated draft and — because `requiresUserApproval` is true — wait for the user, then `proposal_confirm_draft`. |
| `await_approval` | A validated draft is already pending. Present it and wait for the user's approve/reject, then `proposal_confirm_draft` / `proposal_reject_draft`. |
| `ask_question` | A question is pending (or must be asked). Record with `proposal_record_question`, wait, then `proposal_answer_question`. |
| `confirm` | An internal, no-approval transition (e.g. `SUBMIT`). Execute the corresponding tool (`proposal_submit`) without asking the user, then call `proposal_next_step` again. |
| `run_implement` | Proceed to implementation for the approved tasks (Implement phase). |
| `run_test` | Proceed to the review/test step. |
| `finalize` | All checks done; finalize (accept / live-DB reflection) — `proposal_accept`. |

`requiresUserApproval: true` means you MUST wait for the user before the promoting tool call. Never auto-confirm an approval gate.

## Present step — render, don't re-summarize (013-report-mcda)

Whenever you present an artifact/question/validation error to the user, follow
`references/common/report-contract.md`:

1. Output `nextStep.progressMeta.headerMarkdown` first (thin `📍 진행 N/M · 현재 → 다음` line).
2. Output the tool response's `reportMarkdown` **verbatim** (server SSOT body).
3. Output `nextStep.progressMeta.footerMarkdown` last (진행 재요약 + `## 다음 행동 선택` 액션 목록).
   Order = **header → reportMarkdown → footer** (진행 상단 → 본문 → 선택지 하단, D1).
4. If `reportMarkdown` is absent, use the lightweight fallback (all top-level keys as a table),
   never stop the flow.

## Stop conditions — never auto-advance past a server signal

If any tool returns `blocked`, `invalid-transition`, or `invalid` (validation), surface the server's message verbatim and **stop**. Do not pick another phase, do not retry a different step, do not "work around" it. Re-call `proposal_next_step` only after the blocking condition is resolved (question answered, draft fixed/confirmed, or user-requested rollback).

## Explicit routing input

- `mode: SIMPLIFIED | DETAILED_DDD` applies only at the mode-selection gate for a brand-new Proposal.
- A **user-explicit** `phase:` may be passed to `proposal_next_step`. The server guards it: forward jumps return `blocked`; a `phase` in `allowedUserOverrides` is a legal rollback (call `proposal_rollback`). You never originate a `phase` yourself — only relay the user's explicit request.
- For a **new** Proposal with no explicit `mode`, do not assume `SIMPLIFIED`. Apply the mode-selection gate in `references/phases/mode-selection.md` first.
