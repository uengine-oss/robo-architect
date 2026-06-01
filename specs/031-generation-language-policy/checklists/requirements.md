# Specification Quality Checklist: Generation Output Language Policy

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-05-28
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)  *(BCP-47, `Accept-Language`, contextvar are named in Assumptions/FRs as transport-level mechanisms; this is a policy whose definition is inseparable from the transport channel choice — recorded explicitly so reviewers can challenge it)*
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders  *(US1–US3 are plain-language journeys; FRs are testable without code knowledge)*
- [x] All mandatory sections completed  *(User Scenarios, Requirements, Success Criteria, Assumptions)*

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain  *(FR-010 resolved in [research.md §D2](../research.md) before /speckit-implement: server-side fallback = `en-US`, overridable via `GENERATION_LANGUAGE_DEFAULT` env var. spec.md FR-010 updated to reflect the decision.)*
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable  *(SC-001–SC-007 each name a quantity, a percentage, or a verifiable artifact)*
- [x] Success criteria are technology-agnostic  *(metrics are about user-visible language correctness and audit coverage, not framework specifics)*
- [x] All acceptance scenarios are defined  *(every user story has Given/When/Then scenarios)*
- [x] Edge cases are identified  *(eight edge cases enumerated, including unsupported tags, missing header, mixed-language sessions, LLM misbehavior, displayName interaction)*
- [x] Scope is clearly bounded  *(UI i18n explicitly out of scope; retroactive translation out of scope; LLM-quality remediation out of scope)*
- [x] Dependencies and assumptions identified  *(Assumptions section names the LLM-layer prerequisite, the Electron-shell coupling, the no-schema-change constraint, the orthogonality with Domain Terminology)*

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria  *(FRs map to SCs and to US Acceptance Scenarios; FR-008 / FR-015 explicitly testable via the single-chokepoint regression)*
- [x] User scenarios cover primary flows  *(P1 = locale default; P2 = manual override; P3 = future-proofing)*
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification beyond what's necessary to define the policy boundary

## Notes

- All items now PASS. FR-010 resolved during planning (research.md §D2 → `en-US` with `GENERATION_LANGUAGE_DEFAULT` env override); spec.md updated in lockstep.
- The "language-policy as cross-cutting concern" framing (US3, FR-008, FR-015, SC-005) is the spec's load-bearing design choice — the chokepoint is enforced via the AST regression test at `api/tests/regression/test_language_chokepoint.py` (T023).
