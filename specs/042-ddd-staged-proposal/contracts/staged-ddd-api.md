# API Contracts: Staged DDD Decomposition Mode

**Feature**: 042-ddd-staged-proposal · **Date**: 2026-06-14

All endpoints are added under the existing proposal-lifecycle router prefix `/api/proposals`. They follow the established patterns: SSE streams (`text/event-stream`, Principle III) for stage execution, plain JSON POST for confirm/skip (Principle IV). New routes live in a new module `routes/proposals_staged.py`; the mode field rides on existing CRUD. All MUST appear in Swagger `/docs`.

## Modified — proposal creation carries the mode

`POST /api/proposals/` — `CreateProposalRequest` gains:
```
decompositionMode: "SIMPLIFIED" | "DETAILED_DDD" = "SIMPLIFIED"
```
Response `ProposalResponse` gains `decompositionMode`, `stagePlan`, `stageArtifacts`, `currentStage`, `memoryConflicts` (the latter four null/empty for Simplified). (FR-001, FR-002)

## New — mode upgrade (FR-003)

`POST /api/proposals/{id}/mode`
```
Request:  { "decompositionMode": "DETAILED_DDD" }
Response: ProposalResponse   (currentStage set to scope; staged flow seeded from existing strategicDiff)
Errors:   409 { reason: "plan_confirmed" }  if the plan is already confirmed (cannot upgrade)
```

## New — scope classification / stage plan (US3)

`GET /api/proposals/{id}/stream/scope` — SSE. Runs `robo-proposal-scope`, streams `log_line`, ends with:
```
event: stage_plan
data: { "stagePlan": StagePlan }      # applies/recommendSkip/reason per stage (FR-009)
```

`POST /api/proposals/{id}/stage-plan/confirm` (FR-010, FR-015)
```
Request:  { "stages": [ { "stage": "...", "skipped": bool } ... ] }
Response: ProposalResponse            # stagePlan persisted; currentStage = first non-skipped stage
Errors:   422 { reason: "discover_not_skippable" }   if DISCOVER skipped on a behavior-changing proposal (FR-014)
```

## New — per-stage execution (US2, one route, stage in path)

`GET /api/proposals/{id}/stream/stage/{stage}` — SSE, where `{stage}` ∈ `discover|decompose|strategize|connect|define|tactical`. Runs `robo-proposal-{stage}`, seeded with prior stage artifacts + (for strategize/connect/define) existing strategic memory. Streams `phase` + `log_line`, then:
```
event: artifact
data: { "stage": "...", "artifact": StageArtifact }

event: conflicts            # only when local decision diverges from memory (FR-019)
data: { "conflicts": [ MemoryConflict ] }

event: done
data: { "stage": "...", "nextStage": "..." | null }
```
Precondition: the prior non-skipped stage's artifact MUST exist, else `409 { reason: "prior_stage_incomplete" }`.

## New — per-stage confirm / skip (Principle IV gate)

`POST /api/proposals/{id}/stage/{stage}/confirm`
```
Request:  { "artifact": StageArtifact,                      # architect-edited (FR-005, FR-006)
            "conflictResolutions": [ { bcId, field, resolution: "AMEND_MEMORY"|"JUSTIFY_LOCAL", justification? } ] }
Response: ProposalResponse                                  # artifact stored; durable sections promoted to memory; currentStage advances
Errors:   409 { reason: "unresolved_conflicts", conflicts: [...] }   # cannot advance with UNRESOLVED conflicts (FR-019)
```
On confirm of `strategize`/`connect`/`define`, the durable sections are written to the Constitution `strategicMemory` at the correct level (FR-016/FR-017); per-change tactical detail is **not** promoted (FR-020).

`POST /api/proposals/{id}/stage/{stage}/skip`
```
Request:  { "reason": "..." }
Response: ProposalResponse                                  # stage marked skipped; currentStage advances
Errors:   422 { reason: "discover_not_skippable" }          # FR-014
```

## New — consolidate staged result into standard artifacts (US6/FR-023)

`POST /api/proposals/{id}/staged/consolidate`
```
Request:  {}
Response: ProposalResponse   # strategicDiff (+ tacticalDiff if Tactical ran) written in the SAME shapes as Simplified mode
```
After consolidation the proposal uses the **existing** `GET /{id}/stream/plan` + `POST /{id}/plan/confirm` (041) unchanged — impact build and plan confirmation are mode-agnostic.

## Extended — strategic memory on the Constitution surface (FR-022)

The existing constitution feature (`api/features/constitution/router.py`) read/update endpoints are extended so the project-root and per-BC payloads include `strategicMemory`, editable from the Design-side `ConstitutionEditor.vue`. No new prefix.

```
GET  /api/constitution/project                 → { ..., strategicMemory }
PUT  /api/constitution/project                 ← { raw?, strategicMemory? }   # amend → marks proposals stale (FR-021)
GET  /api/constitution/bc/{bcId}/effective      → merged strategicMemory (project-root + BC override)
PUT  /api/constitution/bc/{bcId}               ← { raw?, strategicMemory? }    # per-BC override
```

## SSE event vocabulary (consistent with intent/plan runners)

`phase` · `log_line` · `stage_plan` · `artifact` · `conflicts` · `done` · `error`. Error payloads: `{ code, message }`. Parse-failure codes per stage: `<STAGE>_PARSE_FAILED`.
