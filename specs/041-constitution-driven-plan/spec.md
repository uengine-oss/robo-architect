# Feature Specification: Constitution-driven Plan Stage for the Proposal Lifecycle

**Feature Branch**: `041-constitution-driven-plan`

**Created**: 2026-06-11

**Status**: Draft

**Input**: User description: "다음의 constitution.md 가 프로젝트 레포에 저장된게 없다면 그걸 만들어줘야 한다. 설계원칙/기술스택/모듈리스-마이크로서비스/레포스타일 인터뷰 스킬 기반으로 컨스티튜션 파일이 저장되어야 한다. 이 파일을 기반으로 설계를 구체화 — intent 단계는 전략적 diff 만, plan 단계(robo-plan)에서 전략적 요소 + impact 분석 + constitution 포함 구현계획(마이크로서비스 아키텍처 세부사항: 배포환경/ingress/service mesh/프레임워크/프론트엔드) 을 세운다. tasks.md 추출 시 이를 검토하고, implementation 까지 전달되어야 한다."

## Overview

Today the Proposal lifecycle (039/040) performs requirement decomposition in a **single** intent step (`robo-proposal-intent`): one pass produces both the **Strategic Diff** (Epic/Feature/UserStory/Process) and the **Tactical Diff** (Aggregate/Command/Event/ReadModel/Policy) at once, with no explicit architectural plan and no record of the target project's engineering ground rules. As a result, the *how* of building a Proposal (deployment topology, monolith vs. microservices, framework and frontend choices, repository strategy) is invented ad hoc at implementation time and is never reviewed against a stable set of project decisions.

This feature introduces a **project Constitution** and a dedicated **Plan stage** between intent and implementation:

1. A **Constitution** captures the target project's durable engineering decisions — design principles, technology stack, monolith-vs-microservices posture, and repository strategy — gathered through a guided **interview** when no constitution exists yet, and saved as a reviewable artifact.
2. The current single decomposition is **split** into two stages:
   - **Intent** produces only the **Strategic Diff** (the *what*: Epics/Features/UserStories/Processes).
   - **Plan** consumes the Strategic Diff **plus** the Constitution to produce the tactical/strategic refinement, an **impact analysis**, and a **constitution-grounded implementation plan** that includes concrete microservice architecture details (deployment environment, ingress, service mesh / framework, frontend stack, repository layout).
3. The Constitution and the Plan are **carried forward** into task generation (tasks must be reviewed against them) and into implementation, so generated code honors the project's declared architecture.

## Clarifications

### Session 2026-06-11

- Q: Does the intent→plan split apply only to the Proposal lifecycle, or also to the primary ingestion/design pipeline? → A: **Proposal lifecycle only** (039/040). The primary ingestion/design pipeline is untouched by this feature.

### Session 2026-06-11 (revised — Constitution storage, hierarchy & UI placement) — SUPERSEDES the earlier "repo file" decision

- Q: Where is the Constitution persisted? → A: **In Neo4j nodes** (graph is the source of truth, Principle I), **not** as a file in the target repo. (Reverses the earlier `projectRoot` file decision.)
- Q: What is the scope/hierarchy? → A: **A single project-root Constitution + one Constitution per Bounded Context (override).** A BC's *effective* Constitution = the project-root Constitution merged with that BC's overrides (BC field wins where set). There is **never** a per-Proposal Constitution.
- Q: Where is the management UI? → A: **On the Design side.** A **"헌장 (Constitution)" entry point/icon lives at the Design root** (project-level Constitution) and **at each Bounded Context root** (that BC's Constitution), editable anytime by the architect. The **Proposals tab contains no Constitution view/edit UI.**
- Q: What does the Proposal flow do about the Constitution? → A: **Only triggers the interview when no project-root Constitution exists yet** (a one-time gate before planning), which creates the **project-root** Constitution node. It does not display a persistent Constitution tab and does not create proposal-scoped constitutions.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Establish a Project Constitution via Interview (Priority: P1)

As an architect starting (or first time formalizing) a project, when I begin a Proposal and the project has **no constitution yet**, the system guides me through a short interview covering: design principles, technology stack, whether the system is a monolith or microservices, and the repository strategy (single mono-repo vs. one repo per service; for separate repos, whether the system simply splits git or reuses an existing repo). My answers are saved as a durable, human-readable Constitution that subsequent stages read.

**Why this priority**: Nothing downstream (plan, tasks, implementation) can be grounded in project decisions until those decisions are captured once. This is the foundation that the rest of the feature depends on, and it delivers standalone value: even with no other change, a team gains a recorded, reviewable set of ground rules.

**Independent Test**: Start a Proposal in a project with no constitution; complete the interview; confirm a Constitution artifact is created, contains the four decision areas (principles, tech stack, monolith/microservices, repo strategy), and is viewable/editable afterward — all without running the plan or implementation stages.

**Acceptance Scenarios**:

1. **Given** a project with no **project-root** constitution, **When** I start a Proposal and reach planning, **Then** the system offers to run the constitution interview as a one-time gate (no persistent constitution tab in Proposals).
2. **Given** I am in the interview, **When** I answer the design-principles, tech-stack, monolith/microservices, and repo-strategy questions, **Then** a **project-root Constitution node** is created in the graph capturing exactly those answers.
3. **Given** a project that **already has** a project-root constitution, **When** I start a new Proposal, **Then** the interview is **skipped** and the existing Constitution is reused; the Proposals tab shows **no** constitution view/edit surface (amending is done on the Design side).
3b. **Given** I am on the **Design side**, **When** I open the "헌장" entry point at the Design root or at a Bounded Context root, **Then** I can view and edit the project-root or that BC's Constitution at any time, and a BC's effective constitution reflects project-root + BC overrides.
4. **Given** I choose "microservices" with "separate repository per service", **When** I complete the interview, **Then** the repo-strategy decision (split git vs. reuse existing repo) is recorded for later stages to honor.
5. **Given** my Proposal's natural-language prompt already states technical preferences (e.g. a language, framework, "microservices", a deployment hint, or a frontend choice), **When** the interview starts, **Then** those preferences appear as **pre-filled/proposed** answers I can accept or override — they are not re-asked from scratch.
6. **Given** the prompt does not pin down a required decision area, **When** the interview runs, **Then** the system **recommends a fit-for-purpose default** suited to the project's intent (with a one-line rationale) for me to confirm or change.

---

### User Story 2 - Split Intent (Strategic Diff) from Plan (Architecture & Impact) (Priority: P1)

As an architect, I want the requirement decomposition to happen in two reviewable stages: an **Intent** stage that yields only the strategic diff (Epics/Features/UserStories/Processes), and a separate **Plan** stage that takes that strategic diff together with the Constitution and produces the architectural and tactical detail plus an impact analysis — so I can review and correct the *what* before committing effort to the *how*.

**Why this priority**: The split is the core behavioral change of this feature and is independently demonstrable. It improves correctness (the strategic shape is confirmed before tactical/architectural work) and creates the seam where the Constitution is applied.

**Independent Test**: Run a Proposal's Intent stage and confirm its output contains **only** the strategic diff (no tactical Aggregate/Command/Event detail and no architecture plan). Then run the Plan stage and confirm it adds the tactical refinement, the impact analysis, and the architecture plan — and that it consumed the Constitution.

**Acceptance Scenarios**:

1. **Given** a natural-language requirement, **When** the Intent stage runs, **Then** its result is limited to the Strategic Diff (Epic/Feature/UserStory/Process) and does not include tactical or architectural detail.
2. **Given** an approved Strategic Diff and an existing Constitution, **When** the Plan stage runs, **Then** it produces (a) strategic/tactical refinement, (b) an impact analysis against the existing model, and (c) a constitution-grounded implementation plan.
3. **Given** the project has no constitution when the Plan stage is requested, **When** I start planning, **Then** the system first routes me to the constitution interview (User Story 1) before producing the plan.

---

### User Story 3 - Constitution-grounded Microservice Architecture Plan (Priority: P2)

As an architect, the Plan stage's implementation plan must spell out concrete microservice architecture details consistent with the Constitution: deployment environment, ingress, service mesh / framework, frontend stack, and how services map onto the chosen repository strategy. This becomes the authoritative design the team reviews before any code.

**Why this priority**: This is the substance that makes the plan actionable. It depends on US1 (constitution) and US2 (plan stage) existing, hence P2.

**Independent Test**: With a Constitution declaring "microservices" and a chosen stack, run the Plan stage and confirm the plan enumerates deployment environment, ingress, service mesh/framework, frontend choice, and per-service repository placement — and that each choice is traceable to a Constitution decision (or flagged where the Constitution is silent).

**Acceptance Scenarios**:

1. **Given** a Constitution declaring microservices and a tech stack, **When** the Plan stage runs, **Then** the plan includes deployment environment, ingress, service mesh/framework, and frontend decisions consistent with the Constitution.
2. **Given** a Constitution declaring a monolith, **When** the Plan stage runs, **Then** the plan reflects a single-deployable architecture and does not fabricate microservice infrastructure (no inter-context integration, messaging channel, or per-service dev environments).
3. **Given** the Constitution is silent on a required architectural choice, **When** the plan is produced, **Then** the gap is explicitly surfaced (rather than silently assumed) for the architect to resolve.
4. **Given** a microservices Constitution with two or more Bounded Contexts, **When** the Plan stage runs, **Then** the plan classifies each cross-context interaction (request/response vs. pub/sub, defaulting to event-driven pub/sub), names the messaging channel (e.g. Kafka), and defines a Docker-based, scope-limited developer environment per service for a future multi-repo split.

---

### User Story 4 - Carry Constitution & Plan into Tasks and Implementation (Priority: P2)

As an architect, when I generate the task list and then implement a Proposal, the task-generation step must **review** the Constitution and the Plan, and the implementation step must receive them, so the produced tasks and code honor the declared principles, stack, topology, and repository strategy.

**Why this priority**: Without propagation, the Constitution and Plan are documentation that implementation ignores. This closes the loop, but it depends on US1–US3 being in place.

**Independent Test**: Generate tasks for a planned Proposal and confirm the task list reflects the Plan's architecture (e.g., service boundaries, repo placement) and references the Constitution; then run implementation and confirm the Constitution and Plan are available to the implementing stage as inputs.

**Acceptance Scenarios**:

1. **Given** a completed Plan and Constitution, **When** tasks are generated, **Then** the task list is consistent with the Plan's architecture and is checked against the Constitution before being finalized.
2. **Given** generated tasks, **When** implementation runs, **Then** the Constitution and the Plan are passed through as inputs to the implementing stage.
3. **Given** a task that would violate a Constitution decision (e.g., placing code in a repo layout the Constitution forbids), **When** tasks are generated or reviewed, **Then** the conflict is surfaced rather than silently produced.

---

### Edge Cases

- **Constitution already exists**: interview is skipped; existing Constitution is reused; an explicit "amend" path is offered (US1-AC3).
- **Constitution amended after a Plan exists**: the affected Proposal's plan is marked stale / eligible for re-planning so the plan and constitution cannot silently diverge.
- **Monolith projects**: the plan must not invent microservice infrastructure (ingress, mesh) it does not need (US3-AC2).
- **Separate-repos strategy with a pre-existing repo**: the plan must respect "reuse existing repo" vs. "split git into new repos" as captured in the interview.
- **Constitution is silent on a needed decision**: the gap is surfaced for the architect, never silently defaulted (US3-AC3).
- **Re-running Intent after Plan exists**: changing the Strategic Diff after planning marks the downstream plan/tasks as needing regeneration.
- **Proposal started directly at Plan without Intent**: system requires an approved Strategic Diff (and a Constitution) before producing a plan.

## Requirements *(mandatory)*

### Functional Requirements

#### Constitution

- **FR-001**: The system MUST detect whether the project already has a **project-root Constitution** (a Neo4j node) at the start of a Proposal.
- **FR-002**: When no Constitution exists, the system MUST offer a guided interview that captures, at minimum: (a) design principles, (b) technology stack, (c) monolith vs. microservices posture, and (d) repository strategy (mono-repo vs. repo-per-service; for separate repos, split-git vs. reuse-existing-repo).
- **FR-002a**: The interview MUST seed itself from technical preferences already present in the Proposal's original natural-language prompt, presenting them as pre-filled/proposed answers (clearly marked, overridable) rather than re-asking them.
- **FR-002b**: For any required decision area not pinned down by the prompt, the interview MUST recommend a fit-for-purpose default suited to the project's intent, with a short rationale, for the architect to confirm or change. (Where spec-kit's existing constitution skill already provides this "derive from input / recommend" behavior, it MUST be reused/extended rather than reimplemented.)
- **FR-002c**: The interview MUST be **dependency-aware and minimal**: questions form a tree where a higher-level answer opens or closes downstream questions (choosing monolith MUST suppress gateway/ingress, service-mesh, deployment-target, and repo-per-service follow-ups; choosing microservices unlocks them; choosing a mono-repo suppresses the split-git/reuse-existing follow-up). The interview MUST ask the fewest questions needed for the complexity level the architect is actually heading toward, skipping anything already seeded or confidently recommended.
- **FR-003**: The system MUST persist the interview answers as a **project-root Constitution Neo4j node** (the graph is the source of truth, Principle I) — **never** as a per-Proposal copy and **not** as a file in the target repo.
- **FR-003a**: The system MUST support a **two-level Constitution hierarchy**: one **project-root** Constitution plus an optional **per-Bounded-Context** Constitution (override). The **effective** Constitution for a BC MUST be computed as the project-root Constitution merged with that BC's overrides (BC value wins where present); stages that need a BC-specific constitution MUST consume the effective (merged) result.
- **FR-004**: The architect MUST be able to view and amend any Constitution (project-root and per-BC) **at any time from the Design side** — a "헌장" entry point at the Design root and at each Bounded Context root. Editing MUST NOT be located in the Proposals tab.
- **FR-005**: When a project-root Constitution already exists, the Proposal flow MUST reuse it and skip the interview; it MUST NOT show a Constitution view/edit surface in the Proposals tab (amend happens on the Design side, FR-004).
- **FR-005a**: The Proposal flow MUST trigger the Constitution interview **only** when no project-root Constitution exists, as a one-time gate before planning, and the interview MUST create the **project-root** Constitution node (not a proposal-scoped one).

#### Stage Split (Intent ↔ Plan)

- **FR-006**: The Intent stage MUST produce **only** the Strategic Diff (Epic/Feature/UserStory/Process) and MUST NOT produce tactical (Aggregate/Command/Event/ReadModel/Policy) or architectural detail.
- **FR-007**: The system MUST provide a distinct **Plan** stage that runs after Intent.
- **FR-008**: The Plan stage MUST take the approved Strategic Diff and the Constitution as inputs.
- **FR-009**: The Plan stage MUST produce (a) tactical/strategic refinement, (b) an impact analysis against the existing domain model, and (c) a constitution-grounded implementation plan.
- **FR-010**: If the Plan stage is requested while no Constitution exists, the system MUST route the user to the constitution interview before planning.

#### Architecture Plan

- **FR-011**: The implementation plan MUST include concrete microservice architecture decisions consistent with the Constitution, covering at minimum: deployment environment, ingress, service mesh / framework, frontend stack, and the mapping of services onto the repository strategy.
- **FR-011a**: When the plan involves **two or more Bounded Contexts/services**, it MUST analyze the **inter-context integration intent** — classifying each cross-context interaction as request/response (Command/Query, synchronous) vs. publish/subscribe (Event, asynchronous), reusing the ddd-starter "Connect" decision guidance — and MUST default to an **event-driven pub/sub** style unless a synchronous interaction is genuinely required.
- **FR-011b**: For any pub/sub integration, the plan MUST define the **messaging channel implementation** (defaulting to Kafka unless the Constitution's tech stack dictates another broker).
- **FR-011c**: For a microservices architecture, the plan MUST define a **per-service developer environment** (Docker-based, with that service's scoped infrastructure dependencies, e.g. Kafka), such that a future multi-repo split lets each developer reflect/run only the slice relevant to their own microservice (an explicit scope note per service).
- **FR-012**: When the Constitution declares a monolith, the plan MUST reflect a single-deployable architecture and MUST NOT fabricate microservice-only infrastructure.
- **FR-013**: When the Constitution is silent on a required architectural decision, the plan MUST surface the gap explicitly for the architect rather than silently defaulting.
- **FR-014**: Each architectural decision in the plan SHOULD be traceable to the Constitution decision that justifies it (or be flagged as a Constitution gap).

#### Propagation

- **FR-015**: Task generation MUST review the Constitution and the Plan, and the resulting task list MUST be consistent with the Plan's architecture.
- **FR-016**: Task generation MUST surface any task that would conflict with a Constitution decision rather than producing it silently.
- **FR-017**: The implementation stage MUST receive the Constitution and the Plan as inputs.
- **FR-018**: When the Constitution or the Strategic Diff changes after a Plan exists, the system MUST mark the dependent plan/tasks as stale / eligible for regeneration so plan, constitution, and model cannot silently diverge.

### Key Entities *(include if feature involves data)*

- **Constitution**: The target project's durable engineering decisions — design principles, technology stack, monolith/microservices posture, repository strategy. Stored as **Neo4j node(s)**: one **project-root** Constitution + optional **per-Bounded-Context** Constitution overrides. The **effective** constitution for a BC = project-root merged with that BC's overrides. Created once via interview (project-root) and amendable anytime from the Design side; read by Plan, Tasks, and Implementation. Never per-Proposal.
- **Strategic Diff**: The *what* of a Proposal — proposed Epics/Features/UserStories/Processes. Output of the Intent stage; input to the Plan stage. (Existing concept; this feature narrows the Intent stage to produce only this.)
- **Implementation Plan**: The *how* of a Proposal — tactical/strategic refinement plus the constitution-grounded architecture decisions (deployment environment, ingress, mesh/framework, frontend, repository mapping). Output of the Plan stage; input to Tasks and Implementation.
- **Impact Analysis**: The assessment of how the planned change affects the existing domain model, produced during the Plan stage.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For any project without a prior Constitution, starting a Proposal results in a saved Constitution covering all four decision areas before a plan is produced — a plan is never produced without a Constitution.
- **SC-002**: The Intent stage output contains zero tactical or architectural elements (only strategic diff items) in every run.
- **SC-003**: Every Plan produced includes all five required architecture aspects (deployment environment, ingress, mesh/framework, frontend, repository mapping) or an explicit, itemized list of Constitution gaps where any is missing.
- **SC-004**: Every generated task list for a planned Proposal can be traced back to the Plan's architecture, and any Constitution conflict is surfaced rather than emitted silently.
- **SC-005**: When a Constitution is amended, every dependent Proposal plan is flagged stale within the same session, so no plan silently contradicts the current Constitution.
- **SC-006**: Architects can independently confirm the two stages in the Proposal flow — the *what* (strategic) is reviewable and correctable before any *how* (architecture/tactical) work begins.

## Assumptions

- **Scope of "constitution.md"**: This refers to the **target project being designed via the Proposal lifecycle** (the `projectRoot` target project from feature 039), not robo-architect's own internal constitution. Robo-architect already maintains its own constitution at `.specify/memory/constitution.md`; this feature is about the *user's* project under design.
- **Proposal-lifecycle scope**: The intent→plan split applies **only** to the 039/040 Proposal lifecycle. Constitution **management** (view/edit/override) lives on the Design side and is shared by the whole product, not proposal-scoped.
- **Constitution persistence**: Stored as **Neo4j node(s)** — a project-root Constitution + per-BC overrides — not a repo file and not per-Proposal. The graph is the source of truth (Principle I). Implementation reads the effective (merged) constitution from the graph; if a file copy is needed inside the sandbox at implement time, it is a *projection* of the node, regenerable.
- **Reuse of existing flow**: This feature evolves the existing Proposal lifecycle skills (`robo-proposal-intent`, `robo-proposal-tasks`, `robo-proposal-implement`) and the proposal state machine (039) rather than introducing a parallel pipeline; the new Plan stage slots between Intent and task generation.
- **New "Plan" stage naming**: The user proposed naming the new proposal-planning stage "robo-plan". A robo-plan skill already exists for the speckit/feature-graph flow; the proposal-lifecycle plan stage will be named to avoid collision (e.g., `robo-proposal-plan`) — exact naming is an implementation detail resolved in planning.
- **Interview UX**: The constitution interview follows the existing clarification-question pattern (sequential, selectable answers) already used by intent/clarify flows.
- **Reuse of spec-kit's constitution capability**: spec-kit already ships a `speckit-constitution` skill that derives constitution values from user input / repo context. This feature reuses/extends it for the seeding (FR-002a) and fit-for-purpose recommendation (FR-002b) behavior rather than building a new generator.
- **Architecture vocabulary**: Terms like ingress, service mesh, and frontend stack are *captured as the project's declared choices*; this feature does not mandate any particular technology — it records and propagates whatever the architect declares.
- **Human-in-the-loop preserved**: Constitution creation, plan, tasks, and implementation remain propose→review→confirm steps consistent with the product's existing mutation discipline.

## Dependencies

- Builds on the **039 Proposal Lifecycle** (Proposal/PRO-NNN state machine, sandbox worktree, `robo-proposals/` skills) and **040 Proposal Impact Preview**.
- Reuses the existing impact/diff machinery (038 EFFECT / SemanticDiff) for the Plan stage's impact analysis.
- Reuses the existing SSE streaming and clarification-question UX patterns.
- Reuses the **ddd-starter** DDD modelling skill — Step 5 "Connect / Message Flow" (Event pub/sub vs Command vs Query classification + coupling checks) — for the Plan stage's inter-context integration analysis (FR-011a). Canonical source: https://github.com/jinyoung/ddd-starter-skill-korean.
