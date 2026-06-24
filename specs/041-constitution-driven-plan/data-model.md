# Phase 1 Data Model: Constitution-driven Plan Stage

**Revised (2026-06-11):** the Constitution is stored as **Neo4j node(s)** — a project-root node plus per-Bounded-Context override nodes — **not** as a repo file and never per-Proposal. This introduces **one new node label (`Constitution`) and one new relationship (`HAS_CONSTITUTION`)**, which MUST be reflected in `docs/cypher/schema/` before code that emits them ships (Constitution dev-workflow). The `Proposal` node still gains plan-related JSON properties.

## Entities

### Constitution (Neo4j node — project-root + per-BC override)

The target project's durable engineering decisions, stored in the graph (Principle I).

| Property | Type | Notes |
|----------|------|-------|
| id | string | e.g. `CON-ROOT` (project) or `CON-<bcId>` |
| scope | enum `PROJECT` \| `BOUNDED_CONTEXT` | Hierarchy level |
| designPrinciples | string (markdown) | Free-form principles |
| techStack | string (markdown) | Languages, frameworks, datastores |
| architectureStyle | enum `MONOLITH` \| `MICROSERVICES` \| null | Drives FR-011/FR-012 |
| repoStrategy | enum `MONOREPO` \| `REPO_PER_SERVICE` \| null | `REPO_PER_SERVICE` ⇒ `repoMode` set |
| repoMode | enum `SPLIT_GIT` \| `REUSE_EXISTING` \| null | Only for `REPO_PER_SERVICE` |
| raw | string (markdown) | Full constitution document |
| updatedAt | datetime | Bumped on every amend (staleness source) |

**Graph shape**:
- Project-root: a singleton `(:Constitution {scope:'PROJECT', id:'CON-ROOT'})`.
- Per-BC override: `(:BoundedContext)-[:HAS_CONSTITUTION]->(:Constitution {scope:'BOUNDED_CONTEXT'})`.

**Effective constitution for a BC** (FR-003a) = project-root fields overlaid with that BC's non-null override fields (BC wins where set). Computed in the backend, not stored.

**Validation**: project-root `architectureStyle` and `repoStrategy` required before a plan may be produced (FR-002, FR-010). `repoMode` required iff `repoStrategy = REPO_PER_SERVICE`.

**Staleness mirror**: a `constitutionHash` (hash of the *effective* project-root constitution, or its `updatedAt`) is stamped onto a Proposal's `implementationPlan` when confirmed, so a later amend flags the plan stale (FR-018). The Constitution body itself is **not** copied onto the Proposal.

### ImplementationPlan (stored as JSON on `Proposal.implementationPlan`)

The constitution-grounded *how* of a Proposal. Output of the Plan stage.

| Field | Type | Notes |
|-------|------|-------|
| version | int | Bumped on each re-plan |
| architectureDecisions | list[ArchitectureDecision] | The five required aspects + (microservices) integration/channel/dev-env + extras |
| constitutionGaps | list[string] | Required aspects the Constitution is silent on (FR-013) |
| interContextIntegrations | list[InterContextIntegration] | Cross-context interactions classified Event/Command/Query (FR-011a); empty for monolith |
| messagingChannel | string \| null | pub/sub channel impl, default Kafka (FR-011b); null for monolith / no pub/sub |
| serviceDevEnvironments | list[ServiceDevEnvironment] | Per-service Docker dev env, scoped for multi-repo (FR-011c); empty for monolith |
| tacticalSummary | string | Narrative tying tactical diff to the plan |
| constitutionHash | string | Hash of the Constitution this plan was built against (staleness) |
| strategicVersion | int | `strategicDiff.version` this plan was built against (staleness) |

### InterContextIntegration (ddd-starter Connect)

| Field | Type | Notes |
|-------|------|-------|
| fromContext / toContext | string | The two Bounded Contexts/services |
| message | string | e.g. `OrderConfirmed`, `ChargePayment`, `GetCustomerCredit` |
| kind | enum `EVENT` \| `COMMAND` \| `QUERY` | Event = pub/sub async; Command/Query = directed; default lean to EVENT |
| sync | bool | Whether a synchronous response is required |
| rationale | string | Why this pattern (intent analysis) |

### ServiceDevEnvironment (per microservice, multi-repo-ready)

| Field | Type | Notes |
|-------|------|-------|
| service | string | Service / Bounded Context name |
| runtime | string | e.g. "JDK 21 / Spring Boot 3" |
| dockerBaseImage | string | Docker base image |
| dependencies | list[string] | Infra deps scoped to THIS service (e.g. `["kafka","postgres"]`) |
| composeServices | list[string] | Local `docker-compose` deps for this service's scope only |
| scopeNote | string | What this developer must reflect/run in a multi-repo split — and nothing else |

**Microservices completeness**: when `architectureStyle = MICROSERVICES` and ≥2 contexts, a complete plan additionally requires `INTER_CONTEXT_INTEGRATION`, `MESSAGING_CHANNEL`, and `DEV_ENVIRONMENT` aspects (decision or explicit gap), with the structured fields above populated — enforced by `ImplementationPlan.is_complete(style, contextCount)`.

### ArchitectureDecision

| Field | Type | Notes |
|-------|------|-------|
| aspect | enum `DEPLOYMENT_ENV` \| `INGRESS` \| `SERVICE_MESH_FRAMEWORK` \| `FRONTEND` \| `REPO_MAPPING` \| string | Five required aspects are first-class; extra aspects allowed |
| decision | string | The chosen approach |
| rationale | string | Why — ideally traceable to a Constitution decision (FR-014) |
| constitutionRef | string \| null | Which Constitution section justifies it; null ⇒ flagged as a gap |

**Validation**: a Plan is "complete" iff every required `aspect` is present in `architectureDecisions` **or** listed in `constitutionGaps` (SC-003).

### Proposal (existing node — extended)

New properties on the existing `Proposal` node (all JSON/string scalars; **no new label**):

| Property | Type | Purpose |
|----------|------|---------|
| implementationPlan | JSON string | Serialized `ImplementationPlan` (stamps the project-root constitution hash it was built against) |
| constitutionHash | string | Snapshot of the effective project-root Constitution hash at confirm time; compared against the current node to detect drift |
| planStale (derived) | bool | Computed: stamped `constitutionHash` ≠ current project-root Constitution hash OR `strategicDiff.version` advanced since plan |

Existing properties unchanged: `strategicDiff`, `tacticalDiff`, `impactMap`, `status`, `statusHistory`, `projectRoot`, etc. **`tacticalDiff` is now produced by the Plan stage, not Intent.**

## State & transitions (unchanged statuses)

```
DRAFT ──intent (strategic only)──▶ DRAFT
DRAFT ──plan (tactical+impact+arch)──▶ DRAFT (implementationPlan set)
DRAFT ──submit [requires confirmed plan]──▶ SUBMITTED
   ▲                                            │
   └──── re-run intent / amend constitution ◀──┘  (sets planStale; blocks submit until re-plan)
SUBMITTED → IMPLEMENTING → TESTING → PENDING_ACCEPTANCE → ACCEPTED / DESTROYED  (unchanged; 039)
```

**Submit gate (extends existing rule in `proposals_crud.py`)**: requires `strategicDiff` present **and** `implementationPlan` present **and** `planStale = false`.

## Staleness rule (FR-018)

`planStale = (Proposal.constitutionHash != hash(current project-root Constitution node)) OR (strategicDiff.version > implementationPlan.strategicVersion)`. The "current" hash is read from the `Constitution{scope:'PROJECT'}` node, so amending the Constitution on the Design side automatically flags dependent proposals. Surfaced in the UI and enforced at the submit gate; never silently overridden.
