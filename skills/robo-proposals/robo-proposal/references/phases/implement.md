# Implement

Implementation happens **only inside the Proposal worktree**, and the server decides where that
worktree lives. **Never ask the user where to create it.**

## 1. Prepare the worktree (no questions)

Call `proposal_prepare_sandbox(proposalId, projectRoot=<absolute path of the target project repo>)`
once, at the start of the IMPLEMENT phase. `projectRoot` is the repository you are working in
(your working directory's repo root) — not robo-architect.

The server creates and returns:

- `worktreePath` = `<projectRoot>/.sandbox/proposal/<PRO-NNN>` — a git worktree **inside the
  current repository**
- `branch` = `proposal/<PRO-NNN>`

It also records `projectRoot` on the Proposal, which Accept later needs in order to merge the
branch and reflect the design into the live graph. If you skip this call, Accept fails with
`projectRoot 없음`.

Do not offer alternative locations, do not create a sibling directory such as
`<projectRoot>-PRO-NNN`, and do not implement in the main working tree.

## 2. Implement

- Read `PROPOSAL_<id>.md` first if it exists.
- If `PROPOSAL_<id>_TASKS.md` exists, follow it and check items off.
- Modify files **only inside `worktreePath`**. Never touch the parent checkout.
- Commit logical steps inside the worktree (on the `proposal/<PRO-NNN>` branch).
- Follow the Constitution and Implementation Plan decisions.
- Ask before proceeding when the Plan and the target code conflict.

## 3. Close the phase — required

When every task is implemented and committed, call:

```
proposal_update_implementation_status(proposalId, "DONE")
```

This is what completes the IMPLEMENT step (it moves the Proposal to `TESTING`). Until you call
it, `proposal_next_step` keeps returning `IMPLEMENT` / `run_implement` forever — reporting
"implementation finished" without this call leaves the lifecycle stuck.

Then call `proposal_next_step` again and perform the action it returns (`run_test`).
