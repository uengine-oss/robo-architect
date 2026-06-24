# Quickstart: Constitution-driven Plan Stage

End-to-end flow a developer/architect follows once this feature ships.

## Prerequisites
- Backend running: `uvicorn api.main:app --reload --host 127.0.0.1 --port 8000`
- A Proposal target project (`projectRoot`) per 039.

## Happy path

1. **Create a Proposal** with a natural-language requirement. Tip: include any tech preferences inline (e.g. "as Spring Boot microservices behind an nginx ingress, Vue frontend") — they will pre-seed the Constitution.
2. **Intent (strategic only)** — open the Proposal; the Intent stage streams a Strategic Diff (Epics/Features/UserStories/Processes). Review/correct it. No tactical or architecture detail appears here.
3. **Constitution** — if the project has none yet, the system opens the interview:
   - Pre-filled answers (drawn from your prompt) are shown for you to accept/override.
   - Recommended fit-for-purpose defaults appear for areas your prompt didn't pin down.
   - Answer the remaining gap questions (design principles, tech stack, monolith/microservices, repo strategy). The Constitution file is written to the target repo.
   - If a Constitution already exists, this step is skipped (an "Amend constitution" link remains).
4. **Plan** — run the Plan stage. It streams the Tactical Diff, an impact analysis, and the architecture plan (deployment env, ingress, service mesh/framework, frontend, repo mapping). Any aspect the Constitution is silent on is listed under "Constitution gaps." Review and **Confirm plan**.
5. **Submit** — submit is enabled only once a confirmed, non-stale plan exists. Submitting proceeds into the existing 039 flow (IMPLEMENTING → TESTING → …).
6. **Tasks & Implement** — task generation reviews the Constitution + plan (flagging conflicts), and implementation receives both as context, so generated code honors the declared architecture.

## Staleness check
- Amend the Constitution, or re-run Intent to change the Strategic Diff → the Plan is flagged **stale** and Submit is blocked until you re-run Plan. This guarantees plan, constitution, and model never silently diverge.

## Acceptance smoke (maps to spec)
- Intent output contains zero tactical/architecture items (SC-002).
- A plan is never produced without a Constitution (SC-001 / FR-010).
- Every plan lists all five architecture aspects or explicit gaps (SC-003).
- Amending the Constitution flags dependent plans stale in-session (SC-005).

## Tests
- Playwright: `frontend/tests/verify-proposal-constitution-plan.spec.ts` drives create → intent → interview → plan → submit-gate.
- Backend: pytest under `api/features/proposal_lifecycle/tests/` for `plan_runner`, `constitution_runner`, submit-gate, and staleness.
