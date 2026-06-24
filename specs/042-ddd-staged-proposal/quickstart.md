# Quickstart: Staged DDD Decomposition Mode

**Feature**: 042-ddd-staged-proposal · **Date**: 2026-06-14

End-to-end walkthrough proving the feature. Assumes the backend runs per the dev runbook (`uvicorn api.main:app --reload --host 127.0.0.1 --port 8000`) and Neo4j Desktop is up on :7687.

## Scenario A — Simplified mode is unchanged (SC-006)

1. Open the Proposals tab → New Proposal. The dialog shows a **Simplified / Detailed DDD** switch, defaulting to **Simplified**.
2. Type a small local requirement, keep Simplified, submit.
3. **Expect**: the exact pre-feature flow — intent SSE → (optional clarify) → Strategic Diff, then Plan with the 041 Constitution gate. No stage-plan prompt, no DDD stage steps.

## Scenario B — Detailed mode, first proposal seeds strategic memory (US2 + US4)

1. New Proposal → pick **Detailed DDD** → enter a multi-context requirement (e.g. "add subscription billing with dunning and customer notifications") → submit.
2. **Scope step**: the system streams a proposed **stage plan** (which of Discover/Decompose/Strategize/Connect/Define/Tactical apply, which are recommended skipped, each with a reason). Confirm it.
3. **Discover**: review surfaced past-tense events, pivotal events, hotspots → confirm.
4. **Decompose**: review domain-named sub-domains + responsibilities + adjacency → confirm (rename one sub-domain to verify the edit carries forward).
5. **Strategize**: the system asks the differentiator + market-maturity questions for ambiguous sub-domains, classifies each **Core/Supporting/Generic** → confirm.
   - **Verify memory write**: open the Design side → Constitution → the differentiator/value proposition (project-root) and per-BC Core/Supporting/Generic now appear in **strategic memory**.
6. **Connect**: each cross-context interaction is labeled **Event/Command/Query**, defaulting to pub/sub; coupling warnings appear for any bidirectional-sync or deep sync chain; messaging channel named → confirm.
7. **Define**: per-BC canvas with ≥5 ubiquitous-language terms + autonomous business decisions; same-word/different-meaning clashes flagged → confirm.
8. **Tactical**: per-aggregate boundary rationale, ≥2 invariants, state transitions, throughput → confirm.
9. **Consolidate**: the staged decisions become a standard Strategic Diff + Tactical Diff. Proceed to the existing Plan/impact/confirm.
10. **Expect**: Impact Preview, task generation, and implementation behave exactly as for a Simplified proposal (SC-005).

## Scenario C — Second proposal reuses memory (SC-004)

1. New Proposal → **Detailed DDD** → a requirement touching a BC already classified in Scenario B.
2. At **Strategize** and **Define**, the recorded classification + ubiquitous language are **pre-loaded** and shown for confirm/amend.
3. **Expect**: zero from-scratch re-asks for the already-recorded BC. Changing nothing advances immediately.

## Scenario D — Conflict with memory (FR-019)

1. In a Detailed proposal, deliberately treat a BC recorded as **Generic** as if it were **Core** (or couple a recorded-pub/sub pair synchronously).
2. **Expect**: the stage surfaces a **conflict** and refuses to advance until you choose **Amend memory** or **Justify local exception** (with a justification). No silent override.

## Scenario E — Scope-aware skipping (US3)

1. Detailed proposal for a change confined to **one** existing BC.
2. **Expect**: the stage plan recommends **skipping** cross-context Connect and multi-subdomain Decompose, each with a reason; you can re-enable them. Discover is never offered as fully omitted (only "brief confirmation").
3. A purely strategic-design proposal → **Tactical** recommended skipped. A micro/local tweak → the system asks to collapse toward Simplified.

## Scenario F — Memory amendment marks plans stale (SC-008)

1. With a confirmed Detailed plan in place, go to Design → Constitution → re-classify a BC (e.g. Core → Supporting) in strategic memory and save.
2. **Expect**: the dependent proposal's plan flips to `planStale = true`, eligible for re-planning — identical to 041's Constitution-amendment staleness.

## Automated test entry points

- Backend: `api/features/proposal_lifecycle/tests/test_staged_ddd.py` (new) covers stage-plan confirm/skip rules (Discover-not-skippable), per-stage artifact validation, memory seed/reuse/conflict, consolidation shape parity, and staleness — extending the style of `test_plan_and_constitution.py`.
- Memory: `api/features/constitution/` effective-merge of `strategicMemory` (project-root + BC override).
- Frontend: `frontend/tests/manual-042-capture.spec.ts` (Playwright) drives Scenarios A–F for the manual/docx capture.
