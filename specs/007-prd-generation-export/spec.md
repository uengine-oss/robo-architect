# Feature Specification: PRD and AI-Agent Context Bundle Export

**Feature Branch**: `007-prd-generation-export`
**Created**: 2026-05-06
**Status**: Backfilled (reverse-engineered from existing implementation)
**Input**: Backfill from existing code at `api/features/prd_generation/router.py`, `api/features/prd_generation/routes/prd_export.py`, `api/features/prd_generation/routes/tech_stacks.py`, `api/features/prd_generation/prd_api_contracts.py`, `frontend/src/features/prdGeneration/ui/PRDGeneratorModal.vue`

## User Scenarios & Testing

### User Story 1 - Generate a coding-agent-ready project bundle from the current Event Storming model (Priority: P1)

After modeling Bounded Contexts, Aggregates, Commands, Events, Policies, and ReadModels on the canvas, the architect opens the PRD Generator, picks a tech stack (language, framework, database, messaging, deployment style, AI assistant), and downloads a ZIP containing a `PRD.md`, per-BC spec files, AI-assistant rules/skills (Cursor `.mdc` rules or Claude `.claude/skills/*.md`), optional `CLAUDE.md`/agent files, and optional Docker scaffolding. The bundle is opened in Cursor or Claude Code and used to generate the actual implementation.

**Why this priority**: This is the central "ship a runnable project" path that turns the visual model into something a downstream coding agent can act on. Without it, the modeling work has no executable output.

**Independent Test**: Open the modal, accept defaults (Java + Spring Boot + Cursor), click Download, and verify the resulting ZIP contains `PRD.md`, `.cursorrules`, `.cursor/rules/spring-boot.mdc`, and `specs/<bc>_spec.md` for every modeled BC.

**Acceptance Scenarios**:

1. **Given** ≥1 BoundedContext exists in Neo4j, **When** the user calls `POST /api/prd/generate` with a `TechStackConfig`, **Then** the API returns the planned `files_to_generate` list, the affected BCs, and the `download_url` `/api/prd/download` — without producing any artifacts.
2. **Given** the same payload, **When** the user calls `POST /api/prd/download`, **Then** a streamed `application/zip` is returned with `Content-Disposition: attachment; filename={project_name}_prd_{timestamp}.zip`.
3. **Given** zero BCs exist, **When** either endpoint is called, **Then** the API returns HTTP 404 with `"No Bounded Contexts found for the given nodes"`.

### User Story 2 - Pick a tech stack from a curated catalog (Priority: P1)

The modal must show only valid combinations (e.g., Spring Boot under Java/Kotlin, NestJS under TypeScript). The frontend fetches the catalog from `GET /api/prd/tech-stacks` and filters frameworks by selected language client-side.

**Why this priority**: Stack selection drives every generated file; an invalid combination produces a broken bundle.

**Independent Test**: Open the modal and verify that switching language to `python` filters frameworks down to `fastapi`.

**Acceptance Scenarios**:

1. **Given** the modal mounts, **When** `GET /api/prd/tech-stacks` returns, **Then** `languages`, `frameworks` (each with a `languages` whitelist), `messaging` (with `description`), `deployments`, `databases`, and `frontend_frameworks` populate the form.
2. **Given** the user changes language to one that does not support the current framework, **When** the watcher fires, **Then** the framework auto-resets to the first compatible option.

### User Story 3 - Tailor output by AI assistant (Cursor vs Claude) (Priority: P2)

The architect chooses Cursor or Claude as the target. For Cursor, the bundle includes `.cursorrules` and `.cursor/rules/*.mdc` (DDD principles, event-storming implementation, GWT test generation, the chosen tech-stack rule, optional API gateway). For Claude, it additionally includes `CLAUDE.md`, `.claude/skills/*.md` mirroring the same topics, and `.claude/agents/{bc}_agent.md` per BoundedContext.

**Why this priority**: The two assistants consume different file conventions; a one-size-fits-all bundle wastes context and confuses the agent.

**Acceptance Scenarios**:

1. **Given** `ai_assistant=cursor` and `deployment=microservices`, **When** the bundle is built, **Then** it includes `.cursor/rules/api-gateway.mdc` and excludes any `CLAUDE.md` or `.claude/*` files.
2. **Given** `ai_assistant=claude`, **When** the bundle is built, **Then** it includes `CLAUDE.md`, `.claude/skills/ddd-principles.md`, `.claude/skills/eventstorming-implementation.md`, `.claude/skills/gwt-test-generation.md`, `.claude/skills/{framework}.md`, and `.claude/agents/{bc}_agent.md` for each BC.

### User Story 4 - Optionally include a frontend slice and Docker scaffolding (Priority: P3)

When `include_frontend=true` and `frontend_framework` is set (Vue or React), a `Frontend-PRD.md` and a frontend rule/skill are added. When `include_docker=true`, `docker-compose.yml` and `Dockerfile` are added.

**Why this priority**: Backend-only generation is the dominant use case; frontend/docker are additive opt-ins.

**Acceptance Scenarios**:

1. **Given** `include_frontend=true, frontend_framework=vue, ai_assistant=cursor`, **When** the bundle is built, **Then** `Frontend-PRD.md` and `.cursor/rules/vue.mdc` are present.
2. **Given** `include_docker=true`, **When** the bundle is built, **Then** `docker-compose.yml` and `Dockerfile` are present at the ZIP root.

### Edge Cases

- The `node_ids` field in `PRDGenerationRequest` is *ignored* for BC selection — PRD generation always covers all Bounded Contexts (see comment in `prd_export.py`). The frontend sends it for forward compatibility but the backend documents this explicitly.
- BC names are slugged for filenames: `name.lower().replace(' ', '_')`; an unnamed BC becomes `unknown`.
- The ZIP is built fully in-memory (`io.BytesIO`) and re-wrapped before streaming — bundle size scales with model size; no disk staging.
- File-name and content count must match between `/generate` (planning) and `/download` (build) — divergence is a regression.
- Snapshot logging includes `zip_bytes`, `zip_sha256`, `zip_build_ms` for traceability.

## Requirements

### Functional Requirements

- **FR-001**: System MUST expose `GET /api/prd/tech-stacks` returning `{languages, frameworks, messaging, deployments, databases, frontend_frameworks}` with each framework carrying a `languages` whitelist for client-side filtering.
- **FR-002**: System MUST expose `POST /api/prd/generate` accepting `PRDGenerationRequest{node_ids?, tech_stack: TechStackConfig}` and returning `{success, bounded_contexts:[{id,name}], tech_stack, files_to_generate, download_url}`.
- **FR-003**: System MUST expose `POST /api/prd/download` accepting the same payload and returning a `StreamingResponse` of `application/zip` with a timestamped filename `{project_name}_prd_{YYYYMMDD_HHMMSS}.zip`.
- **FR-004**: PRD generation MUST always include all Bounded Contexts in the model regardless of `node_ids`; if zero BCs exist, MUST return HTTP 404.
- **FR-005**: Bundle MUST always contain `PRD.md`, `.cursorrules`, `README.md`, and `specs/{bc}_spec.md` for each BC.
- **FR-006**: When `ai_assistant=claude`, bundle MUST additionally contain `CLAUDE.md`, `.claude/skills/ddd-principles.md`, `.claude/skills/eventstorming-implementation.md`, `.claude/skills/gwt-test-generation.md`, `.claude/skills/{framework}.md`, and `.claude/agents/{bc}_agent.md` per BC.
- **FR-007**: When `ai_assistant=cursor`, bundle MUST additionally contain `.cursor/rules/ddd-principles.mdc`, `.cursor/rules/eventstorming-implementation.mdc`, `.cursor/rules/gwt-test-generation.mdc`, and `.cursor/rules/{framework}.mdc`.
- **FR-008**: When `deployment=microservices`, bundle MUST additionally contain `.cursor/rules/api-gateway.mdc` (Cursor) or `.claude/skills/api-gateway.md` (Claude).
- **FR-009**: When `include_frontend=true` and `frontend_framework` is set, bundle MUST additionally contain `Frontend-PRD.md` and a frontend rule (`.cursor/rules/{frontend}.mdc`) or skill (`.claude/skills/{frontend}.md`).
- **FR-010**: When `include_docker=true`, bundle MUST additionally contain `docker-compose.yml` and `Dockerfile`.
- **FR-011**: BC filenames MUST be derived as `(bc.name or 'unknown').lower().replace(' ', '_')`.
- **FR-012**: All generation/download invocations MUST emit `SmartLogger` events under `api.prd.generate.*`, `api.prd.download.*`, `api.prd.tech_stacks.*` including `http_context`, duration, and (for download) `zip_bytes` and `zip_sha256`.
- **FR-013**: The supported enums are fixed: `Language ∈ {java, kotlin, typescript, python, go}`; `Framework ∈ {spring-boot, spring-webflux, nestjs, express, fastapi, gin, fiber}`; `MessagingPlatform ∈ {kafka, rabbitmq, redis-streams, pulsar, in-memory}`; `Database ∈ {postgresql, mysql, mongodb, h2}`; `DeploymentStyle ∈ {microservices, modular-monolith}`; `FrontendFramework ∈ {vue, react}`; `AIAssistant ∈ {cursor, claude}`.
- **FR-014**: The frontend modal MUST gate the workflow as a 3-step wizard (Config → Preview → Download), where Preview calls `/generate` and Download calls `/download`.
- **FR-015**: Generated artifact contents MUST be derived from the live Neo4j model via `api.features.prd_generation.prd_model_data.get_bcs_from_nodes(None)` and `api.features.prd_generation.prd_artifact_generation.*` generators (one per artifact kind).

### Key Entities

- **BoundedContext** (Neo4j label `BoundedContext`): primary unit of bundling; one `specs/{bc}_spec.md` and (for Claude) one `.claude/agents/{bc}_agent.md` per instance.
- **TechStackConfig** (pydantic model): user-selected `language`, `framework`, `messaging`, `deployment`, `database`, `project_name`, `package_name`, `include_docker`, `include_kubernetes`, `include_tests`, `ai_assistant`, `frontend_framework`, `include_frontend`.
- **PRDGenerationRequest** (pydantic model): `{node_ids?: list[str] | None, tech_stack: TechStackConfig}` — `node_ids` is forward-compat only.
- **Generated Artifact**: in-memory string written into a `zipfile.ZipFile` entry; identified by its path within the ZIP (e.g., `PRD.md`, `.cursor/rules/spring-boot.mdc`, `specs/orders_spec.md`).

## Success Criteria

### Measurable Outcomes

- **SC-001**: For a model with N BoundedContexts, the downloaded ZIP contains at least N spec files (`specs/*_spec.md`) and, when `ai_assistant=claude`, exactly N agent files (`.claude/agents/*_agent.md`).
- **SC-002**: The `files_to_generate` list returned by `/generate` MUST match the actual ZIP entries produced by `/download` for the same payload.
- **SC-003**: A user can go from opening the modal to a downloaded ZIP in under 30 seconds for a typical model (≤10 BCs), measured from modal mount to download completion.
- **SC-004**: Downloaded `Content-Disposition` header MUST contain a filename ending in `.zip` and prefixed with the configured `project_name`.
- **SC-005**: The bundle MUST be openable in the target AI assistant (Cursor or Claude Code) without manual restructuring.

## Assumptions

- A single Neo4j instance holds the canonical Event Storming model; there is no project/tenant scoping at the PRD layer.
- The frontend ignores `node_ids` for BC scoping but may send `selectedNodes` IDs for analytics/forward-compat — the backend authoritatively expands to "all BCs".
- Generator functions in `prd_artifact_generation.py` are deterministic given the same model + config (otherwise SHA logging would be misleading).
- The user runs the generated bundle in an environment where Cursor/Claude Code can read its conventional rule/skill paths; the API does not validate the receiving environment.
- Kubernetes scaffolding (`include_kubernetes`) is part of the contract but not currently emitted into the ZIP by the route — this is treated as a known limitation rather than a violation.
