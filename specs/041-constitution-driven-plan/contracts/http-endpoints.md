# Contract: HTTP Endpoints (proposal_lifecycle)

All endpoints are under the existing `/api/proposals` prefix and appear in Swagger (`/docs`). SSE endpoints follow the existing `stream_intent` convention. Read/projection endpoints use read transactions; mutations follow propose→confirm (Principle IV).

## Constitution — Neo4j-backed (Design-side management) + proposal interview gate

**Revised (2026-06-11):** the Constitution lives in the graph (project-root node + per-BC override nodes). **Management endpoints live in a new `constitution` feature** (`/api/constitution`, `/api/bounded-contexts/{bcId}/constitution`), consumed by the **Design side**. The Proposals tab has **no** constitution view/edit endpoints — only a one-time interview gate.

### `GET /api/constitution` — project-root (Design side)
- **200**: `{ exists, scope: "PROJECT", fields: {designPrinciples, techStack, architectureStyle, repoStrategy, repoMode}, raw, constitutionHash, updatedAt }`; `exists=false` ⇒ interview required (FR-001).

### `PUT /api/constitution` — amend project-root (Design side)
Body: `{ raw, fields? }`. Upserts the `Constitution{scope:'PROJECT'}` node, bumps `updatedAt`/hash; dependent proposal plans become stale via derived staleness (FR-018). **200**: `{ constitutionHash }`.

### `GET /api/bounded-contexts/{bcId}/constitution` — per-BC override + effective
- **200**: `{ override: {…}|null, effective: {…} }` where `effective` = project-root merged with this BC's overrides (FR-003a).

### `PUT /api/bounded-contexts/{bcId}/constitution` — amend BC override (Design side)
Body: `{ raw?, fields? }`. Upserts `(:BoundedContext{id})-[:HAS_CONSTITUTION]->(:Constitution{scope:'BOUNDED_CONTEXT'})`. **200**: `{ constitutionHash }`.

### `DELETE /api/bounded-contexts/{bcId}/constitution` — drop the BC override (fall back to project-root).

### Proposal interview gate (Proposals tab) — interview ONLY, no view/edit
### `GET /api/proposals/{pid}/constitution`
Thin status check for the Plan gate: **200** `{ exists }` (delegates to project-root). No raw/edit surface.

### `GET /api/proposals/{pid}/stream/constitution` (SSE)
Runs the `robo-project-constitution` interview **only when the project-root Constitution is absent**, seeding from the Proposal's `originalPrompt`. On `done`, writes the **project-root** `Constitution` node (never a proposal copy). Streams `question` / `draft` / `done`.

### `POST /api/proposals/{pid}/constitution/answer`
Body: `{ questionIndex, answer }`. Advances the interview.

## Plan

### `GET /api/proposals/{pid}/stream/plan` (SSE)
Runs the `robo-proposal-plan` skill. Precondition: an approved `strategicDiff` and an existing Constitution (else **409** with `{ reason: "constitution_required" }`, routing the UI to the interview — FR-010). Streams:
- `event: tactical` → incremental Tactical Diff
- `event: impact` → impact analysis items (reuses `impact_builder`)
- `event: architecture` → `ArchitectureDecision` items + `constitutionGaps`
- `event: done` → `{ tacticalDiff, impactMap, implementationPlan }`

### `POST /api/proposals/{pid}/plan/confirm`
Persists the reviewed `implementationPlan` (+ `tacticalDiff`, `impactMap`) onto the Proposal node, stamping `constitutionHash` and `strategicVersion`. (Principle IV: confirm step.)

### `GET /api/proposals/{pid}/plan`
Returns the stored `ImplementationPlan` + derived `planStale`.

## Intent (modified)

### `GET /api/proposals/{pid}/stream/intent` (SSE) — MODIFIED
Now emits **only** Strategic Diff (Epic/Feature/UserStory/Process). No `tactical`/`architecture` events (FR-006). Re-running after a plan exists sets `planStale`.

## Submit (modified)

### `POST /api/proposals/{pid}/submit` — MODIFIED
Existing checks retained. Adds preconditions: `implementationPlan` present and `planStale = false`, else **400** `{ reason: "plan_required" | "plan_stale" }` (FR-010/FR-018).
