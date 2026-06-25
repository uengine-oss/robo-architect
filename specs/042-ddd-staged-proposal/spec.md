# Feature Specification: Staged DDD Decomposition Mode for Proposals

**Feature Branch**: `042-ddd-staged-proposal`

**Created**: 2026-06-14

**Status**: Draft

**Input**: User description: "ddd-starter-skill 을 참고하여 robo-proposal 스킬과 전체 proposal 기능을 업그레이드. 각 proposal 입력 시 'DDD 상세 분해 모드' 와 '일반(간소화) 모드' 를 둔다. 상세 모드는 ddd-starter-skill 의 각 단계를 상세히 다루며 proposal 을 분석한다(intent → decomposition → strategize → … 각 DDD 단계를 명시). 일반 모드는 현재 수순(intent → plan)으로 바로 건너뛴다. proposal 의 성격에 따라 생략 가능한 단계는 생략한다. 사용자는 입력 다이얼로그의 스위치로 상세/간소화 모드를 선택하고, 상세 모드에서는 전략적 질문들을 단계단계 넘어가며 진행한다. (보강) ddd-starter 의 단계마다 중요한 의사결정 질문들이 있다 — '지금 업무에서 가장 차별적인/비즈니스적 차별성이 뭐냐', 전략적 설계에서 중요한 것들, 디컴포즈 후 컴바인할 때 느슨하게(loosely coupled) 설계할지·pub/sub 으로 갈지 동기 호출로 갈지 등. 이런 전략적 의사결정 사항은 한 번 정해지면 잘 안 바뀌므로 프로젝트의 Constitution(또는 별도 프로젝트 메모리)에 저장되어 재사용되어야 한다. 특히 최초 proposal 입력 때 이런 세부 의사결정이 많이 발생한다. ddd-starter 의 상세 내용을 면밀히 반영하고 테스트 계획까지 세워라."

## Overview

Today the Proposal lifecycle (039/040/041) decomposes a requirement through a fixed two-step path — **Intent** (Strategic Diff: Epic/Feature/UserStory/Process) then **Plan** (Tactical Diff + Constitution-grounded architecture). This is fast for small, well-understood changes, but it collapses the entire Domain-Driven Design conversation into a single intent pass. The deliberate, *staged* DDD decisions — "what is genuinely differentiating about this part of the business?", "is this domain Core, Supporting, or Generic?", "when we recombine these decomposed pieces, do we couple them loosely via pub/sub events or tightly via synchronous calls?" — never get asked one at a time, with a reviewable artifact and a decision gate per step.

This feature adds two things:

1. A **decomposition mode** selectable at proposal creation:
   - **Simplified mode** — today's behavior, unchanged: `Intent → Plan`, for quick/local changes.
   - **Detailed DDD mode** — the proposal is analyzed through the **explicit staged process of the `ddd-starter` skill** (Discover → Decompose → Strategize → Connect → Define → Tactical), where each stage asks its **specific decision questions**, produces a **reviewable stage artifact**, and waits for the architect to confirm or correct before advancing.

2. A **durable Strategic Decision Memory**. Many of the DDD questions — especially the strategic ones (business differentiator, Core/Supporting/Generic classification, the project's default integration/coupling posture, each Bounded Context's ubiquitous language and autonomous business decisions) — are decided **once** for a project and rarely change. These durable answers are written into the **project's Constitution / strategic memory** (reusing 041's project-root + per-Bounded-Context hierarchy), so the **first** proposal in a project — which surfaces the most such decisions — *seeds* the memory, and every **later** proposal *reads it back, skips re-asking, and only surfaces it for confirmation or amendment*. Per-proposal tactical detail (the specific events, aggregates, invariants this one change introduces) stays on the Proposal; only the durable strategic conclusions are promoted to memory.

Because a proposal is an *incremental* change to an existing model (not greenfield modelling), Detailed DDD mode is **scope-aware**: before walking the stages it classifies the proposal's reach and **proposes a tailored stage plan**, asking the architect whether to **skip** stages that don't apply. Whatever stages run, their results **converge into the same Strategic Diff, Tactical Diff, Impact Analysis, and Implementation Plan** the downstream stages already consume — so Impact Preview (040), Tasks, Implementation, and the Constitution gate (041) behave identically regardless of mode.

## Clarifications

### Session 2026-06-14

- Q: Do the staged DDD artifacts (event storm, sub-domain map, core-domain chart, message flow, BC canvas, aggregate canvas) become durable first-class domain graph nodes? → A: **No.** Per-proposal stage artifacts are recorded on the Proposal (like 041's `implementationPlan`); their durable graph effect is the existing Strategic/Tactical Diff applied at merge. The exception is the **durable strategic conclusions**, which are promoted to the project Constitution / strategic memory (next item).
- Q: Where do durable strategic decisions live, and what counts as "durable"? → A: In the **project Constitution / strategic memory** — reusing 041's **project-root + per-Bounded-Context** hierarchy with effective (merged) read. "Durable" = decisions that hold for the whole project across proposals: the business differentiator/value proposition, Core/Supporting/Generic classification per Bounded Context, the default integration/coupling posture (event-driven pub/sub vs. synchronous), and each BC's ubiquitous language + autonomous business decisions. Per-change events/aggregates/invariants are **not** durable and stay on the Proposal.
- Q: Same Constitution node, or a separate project-memory store? → A: **Extend the existing Constitution hierarchy** to carry these DDD strategic sections, because it already has the exact project-root + BC-override + effective-merge shape and is already propagated into Plan/Tasks/Implementation. (A sibling "strategic memory" store is an acceptable implementation alternative; the user is explicitly indifferent — resolved as: reuse Constitution.)
- Q: Does the mode toggle change downstream behavior (Impact/Tasks/Implement)? → A: **No.** Mode only changes *how* the Strategic/Tactical Diff + Plan are derived and reviewed. The artifacts handed downstream are mode-agnostic.
- Q: Is the mode chosen once, or switchable mid-flow? → A: Chosen at creation via the dialog switch; an architect MAY upgrade a Simplified proposal to Detailed before the Plan is confirmed, in which case the already-produced Strategic Diff **seeds** the staged flow rather than restarting.
- Q: Is "Understand" (ddd-starter Step 1) a per-proposal stage? → A: No — only its **durable** outputs (business differentiator/value proposition, key personas) are captured **once** into strategic memory (typically on the first proposal) and reused. "Organise" (Step 6, team topology) is out of scope for the proposal flow.
- Q: How are the Detailed-mode stages packaged as skills? → A: **One skill per stage** — separate `robo-proposal-*` skills (Discover, Decompose, Strategize, Connect, Define, Tactical), each independently invokable and resumable, so a single stage can be re-run without re-running the rest. They extend the relevant `ddd-starter` step references and feed each other in sequence.
- Q: Where are the durable DDD strategic sections stored? → A: **Extend the existing Constitution** node hierarchy (project-root + per-BC, effective merge) with the new strategic sections — confirmed, not a separate parallel store.
- Q: How are the per-stage card visualizations (core-domain chart, context map, BC canvas, aggregate canvas) presented for review? → A: Each stage artifact MUST be viewable in **two interchangeable renderings** — the rich **card/visual** form (default) and a plain **Markdown** form of the same data — switchable via an inline toggle. The chosen rendering is a view-only preference (it never alters the underlying artifact) and is shared across stages and read-only re-views.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Choose decomposition mode at proposal creation (Priority: P1)

As an architect creating a Proposal, I want a switch in the new-proposal dialog to choose between **Simplified** and **Detailed DDD** decomposition, so I can match the rigor of the analysis to the size and uncertainty of the change.

**Why this priority**: The mode switch is the entry point for the whole feature; without it there is no way to opt into staged DDD. It independently delivers value by making the existing fast path an explicit, named choice.

**Independent Test**: Open the new-proposal dialog, confirm a clearly-labeled Simplified/Detailed switch with a sensible default and a one-line explanation of each, create a proposal in each mode, and confirm the chosen mode is recorded on the proposal and visibly governs the next flow.

**Acceptance Scenarios**:

1. **Given** the new-proposal dialog, **When** I view it, **Then** a mode switch offers "Simplified" and "Detailed DDD" with a short description of each and a default selection.
2. **Given** I select Simplified and submit, **When** decomposition starts, **Then** the proposal runs today's `Intent → Plan` path with no added stages.
3. **Given** I select Detailed DDD and submit, **When** decomposition starts, **Then** the proposal enters the staged DDD flow (US2) beginning with scope classification (US3).
4. **Given** a proposal created in Simplified mode whose Plan is not yet confirmed, **When** I switch it to Detailed DDD, **Then** the staged flow starts seeded by the existing Strategic Diff rather than re-decomposing from the raw prompt.

---

### User Story 2 - Staged DDD walkthrough with the real per-stage decision questions (Priority: P1)

As an architect in Detailed DDD mode, I want each `ddd-starter` stage to ask its **actual** decision questions — not just a generic "decompose this" — so the deliberations that matter (differentiator, core/supporting/generic, loose vs. tight coupling, event vs. command vs. query, aggregate boundaries, invariants) are surfaced explicitly, one stage at a time, each producing a reviewable artifact I confirm before moving on.

**Why this priority**: This is the core behavioral change. The *substance* of the questions — drawn faithfully from the ddd-starter references — is what makes Detailed mode worth more than the existing intent pass.

**Independent Test**: Run a multi-context proposal in Detailed DDD mode and confirm each applicable stage presents its characteristic questions and artifact (below), no stage auto-advances without an explicit confirm/skip, and earlier stage outputs feed later stages.

**The stages and their characteristic decisions** (each is its own gated step):

- **Discover (event storm)** — surface the domain *events* (past tense) the change introduces/affects, lay them on a timeline, mark **Pivotal Events** (boundary candidates), **Hotspots** (ambiguities/disagreements, each classified *resolve-now* vs. *defer*), external systems, and actors.
- **Decompose (sub-domain map)** — place the affected events into sub-domains named in *domain* language (not technical), give each a one-line responsibility, draw adjacency, and apply the loose-coupling test (each sub-domain autonomously changeable; internally consistent language; neither too large nor too small).
- **Strategize (core domain chart)** — classify each affected sub-domain **Core / Supporting / Generic** using the **differentiator question** ("would a customer *feel the difference* if we built this vs. bought it?") and the **market-maturity question** ("is there already a good external solution?"); for Generic, note a build-vs-buy external-solution candidate.
- **Connect (domain message flow)** — for each cross-context interaction, classify it **Event (pub/sub) / Command / Query**, **defaulting to event-driven pub/sub** unless a synchronous response is genuinely required; run the coupling checks (no bidirectional synchronous dependency; synchronous call-chain depth ≤ 3 or an async note; flag any context talking to ≥ 5 others); name the messaging channel.
- **Define (Bounded Context Canvas)** — per affected BC capture Purpose, Strategic Classification, Domain Roles, Inbound/Outbound messages, **Ubiquitous Language** (≥ 5 terms), autonomous **Business Decisions**, and Assumptions; flag any term that is the *same word with a different meaning* in another context.
- **Tactical (Aggregate Design Canvas)** — per aggregate decide its boundary (the "must change together / one-transaction consistency" test), State Transitions, **Enforced Invariants** (≥ 2), Corrective Policies, Handled Commands, Created Events, and expected Throughput; keep aggregates small and distinguish Value Objects from Aggregates.

**Acceptance Scenarios**:

1. **Given** a Detailed DDD proposal with its stage plan agreed, **When** a stage runs, **Then** the system presents that stage's characteristic decision questions and produces its reviewable artifact, and does not begin the next stage until I confirm or skip.
2. **Given** the Strategize stage, **When** a sub-domain's classification is ambiguous, **Then** the system asks the differentiator and market-maturity questions rather than guessing, and records the resulting Core/Supporting/Generic with its rationale.
3. **Given** the Connect stage with two or more contexts, **When** I review a cross-context interaction, **Then** each is labeled Event/Command/Query, defaults to pub/sub unless synchronous is justified, and any coupling-rule violation (bidirectional sync, deep sync chain) is surfaced.
4. **Given** I correct a stage artifact (e.g. rename a sub-domain, re-classify Core→Supporting, change a message from Command to Event), **When** I confirm, **Then** the correction is carried into the inputs of subsequent stages.
5. **Given** I have completed the stages, **When** the flow concludes, **Then** the accumulated decisions consolidate into a Strategic Diff and (where the tactical stage ran) a Tactical Diff equivalent in shape to Simplified-mode output.
6. **Given** the Constitution gate (041) applies, **When** the staged flow reaches planning/architecture, **Then** the Constitution interview/gate runs exactly as in Simplified mode (not duplicated, not bypassed).

---

### User Story 3 - Scope-aware stage plan with skip prompts (Priority: P1)

As an architect, before the walkthrough I want the system to classify the proposal's reach and **propose which stages apply**, explicitly asking whether to skip the ones that don't — so a micro or single-context change does not force me through a full multi-context DDD ceremony.

**Why this priority**: A proposal is an incremental change; without scope-aware skipping, Detailed mode would be unusably heavy for the common small change, and the user's requirement explicitly calls for asking about skips.

**Independent Test**: Run three Detailed-mode proposals — one confined to a single Bounded Context, one a purely strategic-design change with no new tactical detail, one a micro/local tweak — and confirm the system proposes a reduced stage plan for each, asks before skipping, and lets the architect override.

**Acceptance Scenarios**:

1. **Given** a proposal confined to a single existing Bounded Context, **When** the stage plan is proposed, **Then** cross-context stages (inter-context Connect; multi-subdomain Decompose) are proposed **skipped** with a one-line reason, and I can re-enable them.
2. **Given** a proposal that only changes strategic design (no new aggregates/commands/events), **When** the stage plan is proposed, **Then** the Tactical stage is proposed **skipped**.
3. **Given** a micro/local intent, **When** the stage plan is proposed, **Then** the system asks whether to collapse to a minimal path (close to Simplified) and proceeds only on my confirmation.
4. **Given** any proposed skip, **When** I am asked, **Then** the decision is mine to confirm or reject — no stage is skipped silently — and the final stage plan (which ran, which were skipped, and why) is recorded on the proposal.
5. **Given** a behavior-changing proposal, **When** the stage plan is built, **Then** Discover is never proposed as fully omitted (consistent with ddd-starter's "discovery is not skippable" rule), though it MAY be reduced to a brief confirmation for a tightly-scoped change.

---

### User Story 4 - Capture durable strategic decisions into project memory and reuse them (Priority: P1)

As an architect, the strategic decisions that hold for the whole project — the business differentiator/value proposition, each Bounded Context's Core/Supporting/Generic classification, the default integration/coupling posture, and each BC's ubiquitous language and autonomous business decisions — must be saved **once** into the project's Constitution / strategic memory, so the **first** proposal seeds them and every **later** proposal reuses them instead of re-asking.

**Why this priority**: Without this, every proposal re-litigates settled strategy, which is both wasteful and a source of drift. Persisting durable decisions is what makes Detailed mode sustainable across many proposals; it is the user's explicit core ask and is independently demonstrable.

**Independent Test**: Run a first Detailed-mode proposal in a fresh project, answer the strategic questions, and confirm the differentiator, per-BC Core/Supporting/Generic, default coupling posture, and per-BC ubiquitous language are written to the project Constitution/strategic memory. Then run a second proposal touching the same BC and confirm those values are **read back and presented for confirmation, not re-asked from scratch**.

**Acceptance Scenarios**:

1. **Given** a project with no recorded strategic memory, **When** I complete a Detailed-mode proposal's strategic stages, **Then** the durable conclusions (differentiator/value proposition, per-BC Core/Supporting/Generic, default integration/coupling posture, per-BC ubiquitous language + business decisions) are written to the project Constitution / strategic memory at the correct level (project-root vs. per-BC).
2. **Given** strategic memory already records a BC's classification and ubiquitous language, **When** a later proposal's Strategize/Define stages run for that BC, **Then** the recorded values are loaded as the starting point and surfaced for confirm/amend, and are not asked again from a blank slate.
3. **Given** a proposal whose local decision conflicts with recorded strategic memory (e.g. it treats a Generic BC as Core, or couples two contexts synchronously against the recorded pub/sub default), **When** the stage runs, **Then** the conflict is surfaced and I must explicitly amend the memory or justify the local exception — it is not silently overridden.
4. **Given** I amend a strategic decision in memory (e.g. re-classify a BC Core→Supporting, or change the default coupling posture), **When** the amendment is saved, **Then** dependent proposal plans are marked stale / eligible for re-planning (consistent with 041's staleness rules) so plan and strategy cannot silently diverge.
5. **Given** the durable distinction, **When** the strategic stages run, **Then** per-change tactical detail (this proposal's specific new events/aggregates/invariants) is **not** promoted to project memory — only the durable strategic conclusions are.

---

### User Story 5 - Simplified mode stays fast and unchanged (Priority: P2)

As an architect making a quick or local change, when I pick Simplified mode the proposal must behave exactly as today — no extra questions, gates, or stages — so the new capability never taxes the common case.

**Why this priority**: Protecting the existing fast path is essential to adoption, but it depends on the mode switch (US1) existing.

**Independent Test**: Create a Simplified-mode proposal and confirm the steps (Intent, then Plan, with the existing Constitution gate) are identical to the pre-feature flow, with no DDD stage prompts.

**Acceptance Scenarios**:

1. **Given** Simplified mode, **When** the proposal is decomposed, **Then** the flow is the existing `Intent → Plan` with no added DDD stages or scope-plan prompt.
2. **Given** Simplified mode, **When** I review the result, **Then** the Strategic Diff, Tactical Diff, Impact, and Plan are produced as before.
3. **Given** Simplified mode in a project that already has strategic memory, **When** the plan is produced, **Then** the recorded strategic memory is still honored as input (Simplified mode reads memory but does not run the staged interview to extend it).

---

### User Story 6 - Mode-agnostic downstream convergence (Priority: P2)

As an architect, whichever mode I used, the downstream stages — Impact Preview (040), task generation, and implementation — must consume the **same** Strategic Diff, Tactical Diff, Impact Analysis, and Implementation Plan, so decomposition rigor never changes what gets built or how it is reviewed and merged.

**Why this priority**: Convergence is what lets Detailed mode be additive rather than a parallel pipeline; it depends on US2/US3 producing the standard artifacts.

**Independent Test**: Take one requirement, decompose it once in each mode, and confirm both runs yield downstream-compatible artifacts such that Impact Preview, Tasks, and Implementation operate without mode-specific branching.

**Acceptance Scenarios**:

1. **Given** a Detailed DDD proposal that completed its stages, **When** I open Impact Preview, generate tasks, or implement, **Then** those stages run against the same artifact shapes they use for a Simplified proposal.
2. **Given** a Detailed DDD proposal, **When** its plan is finalized, **Then** the Submit/plan-confirmation gates (041: confirmed plan + `planStale=false`) apply unchanged.

---

### Edge Cases

- **Multi-context proposal**: the Connect stage is required and not skippable without explicit override.
- **Single-BC local change**: cross-context stages are proposed skipped; the architect may re-enable them.
- **Strategic-only change**: the Tactical stage is proposed skipped; the resulting plan has no new Tactical Diff items.
- **First proposal in a project**: surfaces the most durable decisions; the strategic stages double as memory-seeding and may take longer — the architect is told so.
- **Later proposal in a populated project**: strategic memory is loaded; the strategic stages become confirm/amend rather than from-scratch interviews.
- **Local decision contradicts memory**: surfaced for amend-or-justify, never silently overridden (US4-AC3).
- **Strategic memory amended after a plan exists**: dependent plans marked stale (US4-AC4 / 041 rules).
- **Mode upgrade mid-flow**: switching Simplified→Detailed before plan confirmation seeds the staged flow from the existing Strategic Diff.
- **Detailed flow abandoned mid-stage**: completed stage artifacts and the stage plan are retained so the proposal resumes, not restarts.
- **Coupling-rule violation in Connect** (bidirectional sync, deep sync chain, fan-out ≥ 5): surfaced as a warning for the architect to resolve, not auto-fixed.
- **No Constitution yet**: the 041 Constitution gate fires before planning in both modes; Detailed mode adds the DDD strategic sections to that same memory rather than a second path.

## Requirements *(mandatory)*

### Functional Requirements

#### Mode selection

- **FR-001**: The new-proposal input dialog MUST present a switch to choose between **Simplified** and **Detailed DDD** decomposition, each with a short human-readable description and a default selection.
- **FR-002**: The chosen decomposition mode MUST be recorded on the Proposal and MUST govern which decomposition flow runs.
- **FR-003**: An architect MUST be able to upgrade a **Simplified** proposal to **Detailed DDD** while its Plan is not yet confirmed; doing so MUST seed the staged flow from the already-produced Strategic Diff rather than discarding it.

#### Detailed DDD staged flow

- **FR-004**: In Detailed DDD mode the system MUST analyze the proposal through the explicit `ddd-starter` stages — Discover, Decompose, Strategize, Connect, Define, and Tactical (aggregate design) — exposing them as distinct gated steps rather than a single intent pass.
- **FR-005**: Each running stage MUST present that stage's **characteristic decision questions** (enumerated in FR-005a…f) and produce a **reviewable stage artifact**, and MUST NOT advance until the architect explicitly confirms or skips.
- **FR-005a** (Discover): The stage MUST elicit domain events (past tense) for the change, order them, and identify Pivotal Events, Hotspots (each classified resolve-now vs. defer), external systems, and actors.
- **FR-005b** (Decompose): The stage MUST place affected events into domain-named sub-domains (not technical names), assign each a one-line responsibility, show adjacency, and apply the loose-coupling test (autonomous change, internal language consistency, right-sizing).
- **FR-005c** (Strategize): The stage MUST classify each affected sub-domain Core/Supporting/Generic, applying the **differentiator** and **market-maturity** questions when ambiguous, and MUST record a build-vs-buy candidate for Generic sub-domains.
- **FR-005d** (Connect): The stage MUST classify each cross-context interaction as Event/Command/Query, **default to event-driven pub/sub** unless synchronous is genuinely required, run the coupling checks (no bidirectional sync; sync chain depth ≤ 3 or async note; flag fan-out ≥ 5), and name the messaging channel.
- **FR-005e** (Define): The stage MUST produce, per affected Bounded Context, a canvas with Purpose, Strategic Classification, Domain Roles, Inbound/Outbound messages, Ubiquitous Language (≥ 5 terms), autonomous Business Decisions, and Assumptions, and MUST flag same-word/different-meaning terms across contexts.
- **FR-005f** (Tactical): The stage MUST produce, per aggregate, a boundary decision (must-change-together / one-transaction test), State Transitions, ≥ 2 Enforced Invariants, Corrective Policies, Handled Commands, Created Events, and expected Throughput, distinguishing Value Objects from Aggregates.
- **FR-005g**: Each stage artifact MUST be presentable in **two interchangeable renderings** — the rich **card/visual** form (default) and an equivalent plain **Markdown** form of the same data — switchable via an inline card ↔ Markdown toggle. The selected rendering MUST be a view-only preference that never mutates the artifact, MUST persist across stages and tab switches, and MUST also apply when re-viewing a completed stage read-only.
- **FR-006**: A stage's confirmed/corrected output MUST be carried forward as input to subsequent stages.
- **FR-007**: The staged flow MUST consolidate its accumulated decisions into a **Strategic Diff** and (when the tactical stage ran) a **Tactical Diff** equivalent in shape to Simplified-mode output.
- **FR-008**: The Constitution gate and interview (041) MUST run in Detailed DDD mode exactly as in Simplified mode — reused, not duplicated or bypassed.

#### Scope-aware stage planning

- **FR-009**: Before the walkthrough, the system MUST classify the proposal's reach (single vs. multiple Bounded Contexts; strategic-only vs. tactical; micro/local vs. structural) and MUST propose a **tailored stage plan** marking which stages apply and which are recommended skipped, each with a one-line reason.
- **FR-010**: The system MUST ask the architect to confirm any proposed skip; no stage may be skipped silently. The architect MUST be able to override a proposed skip (re-enable) or skip a stage the system kept.
- **FR-011**: For a proposal confined to a single existing Bounded Context, the system MUST propose skipping cross-context stages (inter-context Connect; multi-subdomain Decompose).
- **FR-012**: For a purely strategic-design change with no new tactical detail, the system MUST propose skipping the Tactical stage.
- **FR-013**: For a micro/local intent, the system MUST ask whether to collapse toward the minimal/Simplified path and MUST proceed only on confirmation.
- **FR-014**: The system MUST NOT propose fully omitting Discover for a behavior-changing proposal, though it MAY reduce Discover to a brief confirmation for a tightly-scoped change.
- **FR-015**: The final stage plan — which stages ran, which were skipped, and the reason per skip — MUST be recorded on the Proposal for auditability.

#### Strategic Decision Memory

- **FR-016**: The system MUST persist **durable strategic decisions** into the project's Constitution / strategic memory, reusing 041's project-root + per-Bounded-Context hierarchy with effective (merged) read. Durable decisions are, at minimum: the business differentiator/value proposition and key personas (project-root), per-BC Core/Supporting/Generic classification (per-BC), the default integration/coupling posture — event-driven pub/sub vs. synchronous (project-root, with per-pair specifics), and each BC's ubiquitous language + autonomous business decisions (per-BC).
- **FR-017**: On the **first** proposal that surfaces a given durable decision, the system MUST write it to memory at the correct level (project-root vs. per-BC).
- **FR-018**: On **later** proposals, the system MUST load recorded strategic memory as the starting point for the corresponding stages and surface it for **confirm/amend** rather than re-asking from a blank slate.
- **FR-019**: When a proposal's local decision conflicts with recorded strategic memory, the system MUST surface the conflict and require an explicit amend-memory or justify-local-exception choice; it MUST NOT silently override either.
- **FR-020**: Per-change tactical detail (the specific events/aggregates/invariants a single proposal introduces) MUST NOT be promoted to project memory; only durable strategic conclusions are.
- **FR-021**: Amending a strategic decision in memory MUST mark dependent proposal plans stale / eligible for regeneration (consistent with 041's staleness rules).
- **FR-022**: Strategic memory MUST be viewable and amendable from the Design side alongside the existing Constitution surface (041 FR-004), not buried in the Proposals tab.

#### Convergence & downstream parity

- **FR-023**: Regardless of mode, the artifacts handed to downstream stages (Impact Preview, task generation, implementation) MUST be the same Strategic Diff / Tactical Diff / Impact Analysis / Implementation Plan shapes; downstream stages MUST NOT require mode-specific branching.
- **FR-024**: Existing plan-confirmation and Submit gates (041: confirmed plan, `planStale=false`) and staleness rules MUST apply unchanged to Detailed DDD proposals.

#### Simplified mode preservation

- **FR-025**: Simplified mode MUST preserve the current `Intent → Plan` flow with no added DDD stages or scope-plan prompt, so the common/quick case is not taxed; it MUST still read recorded strategic memory as input but MUST NOT run the staged interview to extend it.

#### Artifacts & persistence

- **FR-026**: Intermediate DDD stage artifacts MUST be stored as **Proposal-scoped analysis records** (reviewable on the Proposal), not as new first-class domain graph nodes; the only durable domain-graph effect remains the Strategic/Tactical Diff applied via the existing merge path (graph is the source of truth, Principle I). Durable strategic conclusions are the exception and live in the Constitution/strategic memory (FR-016).
- **FR-027**: A Detailed DDD proposal abandoned mid-stage MUST retain its completed stage artifacts and stage plan so it can be resumed rather than restarted.

### Key Entities *(include if feature involves data)*

- **Decomposition Mode**: The per-Proposal choice of `Simplified` vs `Detailed DDD`. Recorded on the Proposal; governs the flow; defaults sensibly; upgradable before plan confirmation.
- **Stage Plan**: The scope-aware list of DDD stages for a Detailed proposal — which apply, which are skipped, and why — confirmed by the architect and recorded on the Proposal.
- **DDD Stage Artifact**: The reviewable output of one staged step — event storm (events/pivotal/hotspots), sub-domain map, core-domain chart (Core/Supporting/Generic), domain message flow (Event/Command/Query + coupling notes), Bounded Context Canvas, Aggregate Design Canvas. Proposal-scoped; feeds the next stage; consolidates into the Strategic/Tactical Diff.
- **Strategic Decision Memory**: The durable, project-level record of settled DDD strategy — business differentiator/value proposition, per-BC Core/Supporting/Generic, default coupling posture, per-BC ubiquitous language + business decisions. Stored in the project Constitution hierarchy (project-root + per-BC, effective merge). Seeded once; read/confirmed/amended thereafter; carried into Plan/Tasks/Implementation. Amendment triggers staleness.
- **Strategic Diff / Tactical Diff / Implementation Plan / Impact Analysis**: Existing 039–041 artifacts. This feature changes *how* they are derived and reviewed in Detailed mode, and adds strategic-memory inputs, but not their downstream shape or consumers.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At proposal creation the architect can choose Simplified or Detailed DDD, and the choice demonstrably governs the subsequent flow in 100% of new proposals.
- **SC-002**: In Detailed DDD mode every applicable stage is presented as a separate step that asks its characteristic decision questions and produces a reviewable artifact, and no stage advances without an explicit architect confirm or skip.
- **SC-003**: For a single-Bounded-Context or micro/local proposal, the system proposes a reduced stage plan and never forces a full multi-context DDD pass; every skip is an explicit, recorded, architect-confirmed decision.
- **SC-004**: A durable strategic decision (business differentiator, a given BC's Core/Supporting/Generic, the default coupling posture, a BC's ubiquitous language) is asked at most **once** per project: the first proposal records it, and every later proposal reuses it via confirm/amend — verified by zero from-scratch re-asks in a second proposal touching the same BC.
- **SC-005**: A given requirement decomposed in each mode yields downstream-equivalent Strategic Diff / Tactical Diff / Impact / Plan, such that Impact Preview, Tasks, and Implementation run with no mode-specific behavior.
- **SC-006**: Simplified mode introduces zero additional steps compared with the pre-feature flow.
- **SC-007**: For every Detailed DDD proposal, the recorded stage plan and stage artifacts let a reviewer reconstruct which DDD stages ran, which were skipped and why, and what each stage decided.
- **SC-008**: When strategic memory is amended, every dependent proposal plan is flagged stale within the same session, and any proposal whose local decision contradicts memory is surfaced rather than silently reconciled.

## Test Plan *(verification strategy)*

This plan enumerates the verifiable behaviors that prove the feature. Each item is acceptance-level (observable outcome, no implementation detail) and maps to the FRs/SCs above. `/speckit-plan` and `/speckit-tasks` expand these into concrete test tasks.

### TP-A — Mode selection & routing (US1, FR-001…003)

1. Dialog shows the Simplified/Detailed switch with descriptions and a default. *(FR-001)*
2. Simplified submission runs `Intent → Plan` with no added stages; Detailed submission enters the staged flow. *(FR-002)*
3. Upgrading a not-yet-confirmed Simplified proposal to Detailed seeds the staged flow from its existing Strategic Diff (no re-decompose from raw prompt). *(FR-003)*

### TP-B — Per-stage decision substance (US2, FR-004…007)

Run a deliberately multi-context, behavior-changing proposal and assert each stage's artifact contains its characteristic decisions:

1. **Discover** artifact lists past-tense events, ≥ 1 Pivotal Event, and any Hotspot classified resolve-now/defer. *(FR-005a)*
2. **Decompose** artifact names sub-domains in domain language, one-line responsibility each, with adjacency; loose-coupling test applied. *(FR-005b)*
3. **Strategize** artifact classifies each sub-domain Core/Supporting/Generic; an ambiguous one triggers the differentiator + market-maturity questions; a Generic one carries a build-vs-buy candidate. *(FR-005c)*
4. **Connect** artifact labels each cross-context message Event/Command/Query, defaults to pub/sub, names the channel, and raises a coupling warning for an injected bidirectional-sync or depth-4 sync chain. *(FR-005d)*
5. **Define** artifact yields a BC canvas per context with ≥ 5 ubiquitous-language terms and ≥ 1 autonomous business decision; an injected same-word/different-meaning term is flagged. *(FR-005e)*
6. **Tactical** artifact yields per-aggregate boundary rationale, state transitions, ≥ 2 invariants, commands, events, throughput; a Value Object is not modeled as an Aggregate. *(FR-005f)*
7. No stage advances without explicit confirm/skip; a correction in stage N (e.g. Core→Supporting) is visible as input to stage N+1. *(FR-005, FR-006)*
8. After the last stage, output consolidates into Strategic + Tactical Diff of the standard shape. *(FR-007)*

### TP-C — Scope-aware skipping (US3, FR-009…015)

1. Single-BC proposal → cross-context stages proposed skipped with reasons; architect can re-enable. *(FR-011)*
2. Strategic-only proposal → Tactical stage proposed skipped; resulting plan has no new tactical items. *(FR-012)*
3. Micro/local proposal → system asks to collapse toward Simplified; proceeds only on confirm. *(FR-013)*
4. No skip happens without an explicit prompt; the recorded stage plan reflects every ran/skipped decision and reason. *(FR-010, FR-015)*
5. Discover is never offered as fully omitted for a behavior-changing proposal (only reducible to brief confirmation). *(FR-014)*

### TP-D — Strategic memory seed & reuse (US4, FR-016…022)

1. **Seed**: first Detailed proposal in a fresh project writes differentiator/value proposition (project-root), per-BC Core/Supporting/Generic, default coupling posture, and per-BC ubiquitous language to the Constitution/strategic memory at the right level. *(FR-016, FR-017)*
2. **Reuse**: a second proposal touching the same BC loads those values and presents confirm/amend — asserted by zero from-scratch re-asks. *(FR-018, SC-004)*
3. **Conflict**: a proposal that treats a recorded-Generic BC as Core, or couples a recorded-pub/sub pair synchronously, surfaces the conflict and forces amend-or-justify. *(FR-019)*
4. **Boundary**: this proposal's specific new events/aggregates/invariants are on the Proposal only and absent from project memory. *(FR-020)*
5. **Amend staleness**: re-classifying a BC in memory flags dependent proposal plans stale. *(FR-021, SC-008)*
6. **Design-side surface**: strategic memory is viewable/amendable from the Design side, not the Proposals tab. *(FR-022)*

### TP-E — Convergence & Simplified preservation (US5/US6, FR-023…026)

1. The same requirement decomposed in each mode yields downstream-equivalent artifacts; Impact/Tasks/Implement run with no mode-specific branch. *(FR-023, SC-005)*
2. Detailed proposal honors the 041 plan-confirmation and Submit gates unchanged. *(FR-024)*
3. Simplified flow has the exact pre-feature step count; it reads strategic memory as input but does not run the staged interview. *(FR-025, SC-006)*
4. Constitution gate (041) fires once before planning in both modes — never duplicated. *(FR-008)*

### TP-F — Resilience (FR-027)

1. A Detailed proposal abandoned mid-stage retains its completed artifacts and stage plan and resumes from the next stage rather than restarting.

## Assumptions

- **Proposal-lifecycle scope**: This evolves the 039/040/041 Proposal lifecycle and its `robo-proposals/` skills (notably `robo-proposal-intent`, `robo-proposal-plan`, and the Constitution skill `robo-project-constitution`). The primary ingestion/design pipeline and the standalone `ddd-starter` skill are reused as references, not replaced.
- **Stage mapping**: Proposal stages map onto `ddd-starter` steps as Discover (2), Decompose (3), Strategize (4), Connect (5), Define (7), Tactical/Code (8). Step 1 (Understand) contributes only its *durable* outputs (differentiator/value proposition, personas) to strategic memory, captured once; Step 6 (Organise / team topology) is out of scope for the proposal flow.
- **Strategic memory home**: The durable DDD strategic sections extend the **existing Constitution hierarchy** (project-root + per-BC, effective merge from 041), because it already has the right shape and is already propagated to Plan/Tasks/Implementation. A separate sibling store is an acceptable implementation alternative.
- **Durable vs. per-proposal split**: Durable = business differentiator/value proposition, per-BC Core/Supporting/Generic, default coupling posture, per-BC ubiquitous language + business decisions. Per-proposal = the specific events/aggregates/invariants/message-flow of one change.
- **Reuse over reinvention**: Detailed mode reuses the `ddd-starter` staged guidance and decision questions, 041's inter-context Connect analysis (which already borrows ddd-starter Step 5), the existing clarification-question/SSE UX, and the existing impact/diff machinery — rather than building a parallel DDD engine.
- **Skill packaging (confirmed)**: The staged flow is realized as **one skill per stage** — separate, independently invokable/resumable `robo-proposal-*` skills for Discover, Decompose, Strategize, Connect, Define, and Tactical, each extending the matching `ddd-starter` step reference and chaining its artifact to the next. This lets a single stage be re-run in isolation (supporting FR-027 resume and stage-level amendment).
- **Strategic memory home (confirmed)**: The durable DDD strategic sections **extend the existing Constitution** node hierarchy (project-root + per-BC, effective merge from 041) rather than a separate parallel store.
- **Default mode**: A sensible default for the dialog switch (the existing fast path, Simplified) is assumed so the common case is unchanged unless the architect opts into Detailed.
- **Human-in-the-loop preserved**: Every stage, every skip, and every memory write/amend is a propose→review→confirm interaction consistent with the product's existing mutation discipline.
- **Language policy**: Stage questions and artifacts follow the user's configured generation language, consistent with the project-wide generation-language policy.

## Dependencies

- Builds on **039 Proposal Lifecycle** (Proposal/PRO-NNN state machine, sandbox worktree, `robo-proposals/` skills), **040 Proposal Impact Preview**, and **041 Constitution-driven Plan** (Intent/Plan split, Constitution project-root + per-BC hierarchy with effective merge, `implementationPlan`, staleness rules).
- Reuses the **ddd-starter** DDD modelling skill (`ddd-crew/ddd-starter-modelling-process`; Korean fork `uengine-oss/ddd-starter-skill-kor` / `jinyoung/ddd-starter-skill-korean`) — its staged process, orientation/skip decision tree (`references/00-orientation.md`), and the per-step decision guidance for Discover (02), Decompose (03), Strategize (04), Connect (05), Define (07), and Code (08).
- Reuses the existing SSE streaming and clarification-question UX, and the existing impact/diff machinery (038 EFFECT / SemanticDiff).
