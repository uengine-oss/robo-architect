# Phase 1 Data Model: Staged DDD Decomposition Mode

**Feature**: 042-ddd-staged-proposal · **Date**: 2026-06-14

Per Principle I, the Neo4j graph is the source of truth. This feature adds **no new node labels** and **no new relationships**. It extends two existing nodes — `Proposal` (per-proposal staged state) and `Constitution` (durable strategic memory) — with JSON-string properties parsed into Pydantic models.

## 1. Proposal node — new properties

Added alongside the existing 039/041 properties.

| Property | Type (stored) | Parsed model | Meaning |
|---|---|---|---|
| `decompositionMode` | string | enum `SIMPLIFIED`\|`DETAILED_DDD` | Chosen at creation; default `SIMPLIFIED`. Governs the flow. (FR-002) |
| `stagePlan` | JSON string | `StagePlan` | Scope-aware list of stages: applies/skip/reason; architect-confirmed. (FR-009, FR-015) |
| `stageArtifacts` | JSON string | `dict[stage → StageArtifact]` | Proposal-scoped reviewable output of each completed stage. (FR-026) |
| `currentStage` | string\|null | enum stage name | The stage awaiting confirmation; null when not in a staged flow or completed. |
| `memoryConflicts` | JSON string | `list[MemoryConflict]` | Unresolved conflicts between this proposal and recorded strategic memory. (FR-019) |

`decompositionMode` defaults to `SIMPLIFIED` at `CREATE (p:Proposal …)`. The other four are written only when Detailed mode runs.

### StagePlan
```
StagePlan {
  version: int = 1
  stages: list[StagePlanItem]
  classifiedReach: str | None     # human-readable scope summary ("single-BC tactical change")
}
StagePlanItem {
  stage: enum(DISCOVER, DECOMPOSE, STRATEGIZE, CONNECT, DEFINE, TACTICAL)
  applies: bool
  recommendSkip: bool
  skipped: bool                   # final architect decision
  reason: str                     # one-line reason for the recommendation (FR-010/FR-015)
}
```
Validation: `DISCOVER.skipped` MUST be false for a behavior-changing proposal (FR-014) — enforced at confirm time. Every item MUST carry a `reason`.

### StageArtifact (discriminated by `stage`)
One reviewable record per stage. Shapes follow the ddd-starter stage references (FR-005a…f):

```
DiscoverArtifact   { events:[{name,actor?,external?}], pivotalEvents:[str], hotspots:[{text, disposition: RESOLVE_NOW|DEFER}] }
DecomposeArtifact  { subDomains:[{name, responsibility, eventRefs:[str]}], adjacency:[{from,to}], couplingNotes:[str] }
StrategizeArtifact { classifications:[{subDomain, kind: CORE|SUPPORTING|GENERIC, rationale, buildVsBuy?}] }
ConnectArtifact    { interactions:[{from,to,message,kind: EVENT|COMMAND|QUERY, sync:bool, rationale?}], couplingWarnings:[str], messagingChannel?:str }
DefineArtifact     { contexts:[{ name, purpose, classification, domainRoles:[str], inbound:[{from,message,type}], outbound:[{to,message,type}], ubiquitousLanguage:[{term,definition}], businessDecisions:[str], assumptions:[str], languageClashes:[str] }] }
TacticalArtifact   { aggregates:[{ name, boundaryRationale, stateTransitions:[{from,to,trigger}], invariants:[str], correctivePolicies:[str], handledCommands:[str], createdEvents:[str], throughput? }] }
```
Validation highlights: `StrategizeArtifact.classifications[*].kind` required; `DefineArtifact.contexts[*].ubiquitousLanguage` length ≥ 5; `TacticalArtifact.aggregates[*].invariants` length ≥ 2 (mirrors ddd-starter checklists; surfaced as warnings, not hard failures, so a thin change isn't blocked).

### MemoryConflict
```
MemoryConflict {
  bcId: str | null
  field: str                      # e.g. "classification", "couplingPosture"
  memoryValue: str
  proposalValue: str
  resolution: AMEND_MEMORY | JUSTIFY_LOCAL | UNRESOLVED   # default UNRESOLVED (FR-019)
  justification: str | None
}
```

## 2. Constitution node — extended property

| Property | Type (stored) | Parsed model | Meaning |
|---|---|---|---|
| `strategicMemory` | JSON string | `StrategicMemory` | Durable DDD strategy. On `scope:'PROJECT'`: project-level sections. On `scope:'BOUNDED_CONTEXT'`: that BC's sections. (FR-016) |

### StrategicMemory
```
StrategicMemory {
  version: int = 1
  differentiation: { valueProposition: str, personas: [str], differentiator: str } | None   # project-root only
  couplingPosture: { default: PUBSUB|SYNC, rationale: str, pairs: [{from,to,kind,sync}] } | None  # project-root only
  contexts: dict[ bcKey → ContextStrategy ]                                                  # per-BC sections
}
ContextStrategy {
  classification: CORE | SUPPORTING | GENERIC
  rationale: str
  buildVsBuy: str | None
  ubiquitousLanguage: [{term, definition}]
  businessDecisions: [str]
  purpose: str | None
  domainRoles: [str]
}
```

### Effective merge (extends `effective_for_bc`)
For a BC, the effective `strategicMemory` = project-root sections + that BC's `contexts[bcKey]` override (BC wins per section). `differentiation`/`couplingPosture` come only from project-root. Per-BC override may also be stored under the BC's own `contexts[bcKey]`.

### Staleness (FR-021)
`constitution_hash` input is extended to cover `strategicMemory` so any amendment bumps the project Constitution hash; `_mark_proposals_stale` then marks dependent proposal plans stale exactly as in 041.

## 3. State transitions (Detailed mode stage machine)

Per-proposal `currentStage` progression (skipped stages are passed through):

```
(none) → SCOPE(stage plan proposed) → [confirm]
   → DISCOVER → [confirm/skip]
   → DECOMPOSE → [confirm/skip]
   → STRATEGIZE → [confirm/skip] ── writes durable memory (project-root + per-BC)
   → CONNECT → [confirm/skip] ───── writes couplingPosture memory
   → DEFINE → [confirm/skip] ─────── writes per-BC ubiquitous language + business decisions
   → TACTICAL → [confirm/skip]
   → CONSOLIDATE (strategicDiff + tacticalDiff) → existing plan_runner impact + confirm_plan
```
Resumable: on reconnect, resume at the first non-skipped stage whose artifact is absent (FR-027). This stage machine sits **before** the existing 039 proposal status machine (`DRAFT→SUBMITTED→…`); a Detailed proposal stays `DRAFT` until consolidation + plan confirmation, identical to Simplified.

## 4. Schema documentation updates

No new labels/relationships, so `docs/cypher/schema/03_node_types.cypher` / `04_relationships.cypher` get **comment-only** additions documenting the new `Proposal.decompositionMode`/`stagePlan`/`stageArtifacts`/`currentStage`/`memoryConflicts` and `Constitution.strategicMemory` properties (per the Development Workflow rule that schema docs precede emitting code, even for property-only changes).
