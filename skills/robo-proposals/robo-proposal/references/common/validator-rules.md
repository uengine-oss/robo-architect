# Validator Rules

Backend validation is authoritative. **The full validator contracts are documented in
`references/contracts/` — build every artifact from those before you submit, so you do
not have to discover the shape through retries.**

- **Before generating**, read the matching contract doc and copy its shape:
  - Strategic Diff → `references/contracts/strategic-diff.md`
  - Tactical Diff → `references/contracts/tactical-diff.md` (labels, `properties`, `fields`, **GWT**)
  - DDD stage artifacts → `references/contracts/stage-artifacts.md` (required arrays, enums, element shapes)
- Fix validator feedback before adding new analysis. `retryContext.maxAttempts` is small
  (2–3); each attempt may reveal a new constraint, so **satisfy the whole documented shape
  in the first attempt** rather than probing one field at a time.
- Use canonical tactical fields only: `aggregateId`, `boundedContextId`, `commandId`, `triggerEventId`, `invokeCommandId`, `userStoryRefs`.
- Do not use legacy aliases such as `aggregate`, `boundedContext`, `emittedBy`, `trigger`, `invokes`, or `traces`.
- A validator error like `given block is required` on a value that *is* present means the
  **shape** is wrong (e.g. a string where an object `{ "fieldValues": {…} }` is required),
  not that the value is missing — see the GWT section of `tactical-diff.md`.
- Every final artifact must be valid JSON.
- Invalid transition means stop with an error envelope or one confirmation question.
- **Fallback (only if a documented shape still fails):** the authoritative sources are
  `api/features/proposal_lifecycle/services/tactical_contract.py`,
  `.../proposal_ai_validation.py`, and `.../stage_runners/*.py`. If you can read the repo,
  consult them and then update the contract docs so the next run does not need to.
