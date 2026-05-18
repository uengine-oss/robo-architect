# Feature Specification: Aggregate Invariants

**Feature Branch**: `figma-integration`
**Created**: 2026-05-17
**Status**: Draft
**Input**: User description: "인베리언트라고 하는 객체를 추가적으로 만들고 하나 이상의 인베리언트가 어그리거트의 하위로 부착될 수 있는 노드로 식별될 수 있어야 한다. 인베리언트들은 커맨드의 Given-When-Then 및 인수조건과 연결될 수 있고, 같은 내용이면 같은 것으로 취급되어 한 곳을 편집하면 같이 관리되어야 한다. 인베리언트는 조건에 대한 선언문이며, 준수를 위한 세부 GWT 조건은 커맨드에 붙은 GWT 스티커를 레퍼런싱할 수 있다. 캔버스에 스티커로 나타나지는 않고, 어그리거트 디자인 트리에서 어그리거트 하위 객체로 드릴다운해 열 수 있다. 클릭하면 커맨드의 GWT 편집창과 거의 같은 창에서 선언문과 세부 GWT 조건을 설정한다."

## Overview

The robo-architect tool already lets planners model **Aggregates** and the **Commands** they handle, and attach **Given-When-Then (GWT)** conditions — the acceptance criteria — to those Commands. Today, the business rules an Aggregate must *always* uphold (its invariants) are only a loose list of plain-text strings on the Aggregate, with no structure, no traceability, and no link to the GWT conditions that actually verify them.

This feature introduces the **Invariant** as a first-class modeling object. One or more Invariants can be attached under an Aggregate. Each Invariant is a named declaration of a rule the Aggregate must satisfy, and it carries a set of detailed GWT conditions that specify *how* the rule is verified. Crucially, those GWT conditions can be **shared** with the acceptance criteria already attached to Commands: when the same condition is referenced from both a Command and an Invariant, editing it in either place updates the single shared condition everywhere it appears.

Invariants are managed through the **Aggregate design tree** (the left-hand tree shown on the Design tab), not as canvas stickers.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Manage Invariants under an Aggregate (Priority: P1)

A planner opens the Design tab and expands an Aggregate in the left design tree. Below the Aggregate, alongside its other design objects, they see an **Invariants** group. They can drill into it to see each Invariant, add a new Invariant, edit its declaration statement, and remove Invariants that no longer apply.

**Why this priority**: This is the foundational capability — without the ability to see, create, and edit Invariant objects in the tree, none of the connection or sharing behaviors have a home. It delivers standalone value: planners can finally capture aggregate business rules as structured, named objects instead of loose text.

**Independent Test**: Can be fully tested by opening the Design tab, expanding an Aggregate, adding an Invariant with a declaration statement, editing the statement, and deleting it — verifying the tree reflects each change and the declaration persists across reloads.

**Acceptance Scenarios**:

1. **Given** an Aggregate with no Invariants, **When** the planner expands the Aggregate in the design tree, **Then** an Invariants group is shown that can be drilled into.
2. **Given** the Invariants group is open, **When** the planner adds a new Invariant and types a declaration statement, **Then** the Invariant appears as a drill-down node under the Aggregate and the statement is saved.
3. **Given** an existing Invariant, **When** the planner clicks it, **Then** a property editor opens showing the declaration statement and any detailed conditions.
4. **Given** an existing Invariant, **When** the planner edits its declaration statement and saves, **Then** the new statement is reflected in the tree and persists across page reloads.
5. **Given** an existing Invariant, **When** the planner deletes it, **Then** it is removed from the tree and from the Aggregate, while shared conditions referenced elsewhere are preserved.
6. **Given** any view of the model canvas, **When** Invariants exist on an Aggregate, **Then** no Invariant sticker is drawn on the canvas — Invariants appear only in the design tree.

---

### User Story 2 - Attach detailed GWT conditions to an Invariant, shared with Command acceptance criteria (Priority: P2)

A planner opens an Invariant's property editor. Below the declaration statement, they specify the detailed Given-When-Then conditions that define *how the invariant is upheld*. For each condition they can either **reference an existing GWT condition** already attached to a Command in the same Aggregate (so it becomes shared) or **declare a new invariant-only condition**. The editor is the same GWT editing experience used for Commands. When a shared condition is edited from either side, the change applies to every place that references it.

**Why this priority**: This is the core value of the feature — turning invariants into verifiable, traceable rules linked to acceptance criteria. It depends on US1 (the Invariant object must exist first) but, once US1 is in place, delivers the connective tissue between aggregate rules and command behavior.

**Independent Test**: Can be tested by opening an Invariant, adding one condition that references a Command's existing acceptance criterion and one freshly declared condition, editing the shared condition's wording, and confirming the change appears on the Command's acceptance criteria; then editing the same shared condition from the Command side and confirming the Invariant reflects it.

**Acceptance Scenarios**:

1. **Given** an Invariant's property editor is open, **When** the planner adds a detailed condition, **Then** they can choose to reference an existing Command GWT condition or declare a new one.
2. **Given** an Invariant condition that references a Command's acceptance criterion, **When** the planner edits that condition's text from the Invariant editor, **Then** the same text is updated on the Command's acceptance criterion.
3. **Given** a GWT condition referenced by both a Command and an Invariant, **When** the planner edits it from the Command side, **Then** the Invariant editor shows the updated condition.
4. **Given** an Invariant condition declared as new (invariant-only), **When** the planner saves it, **Then** it exists as a standalone invariant condition and does not appear on any Command unless explicitly referenced later.
5. **Given** two conditions whose underlying source is the same shared condition, **When** the planner views either, **Then** they are presented as the same condition rather than as two independent copies.
6. **Given** a shared condition referenced in multiple places, **When** the planner edits it, **Then** the change propagates to all referencing places without an additional confirmation prompt.
7. **Given** the Invariant condition editor, **When** the planner opens it, **Then** it uses the same GWT field-editing experience as the Command's GWT editor.

---

### User Story 3 - Seed Invariants from existing data and ingestion (Priority: P3)

Aggregates already carry a plain-text list of invariant strings, and new requirements are regularly ingested through the document/event-storming pipeline. So planners do not start from an empty slate, existing invariant strings are converted into first-class Invariant objects, and the ingestion pipeline extracts candidate Invariants from incoming requirements automatically.

**Why this priority**: This removes manual re-entry and keeps the new structured model populated as the project evolves, but the feature is already valuable without it (planners can author Invariants by hand). It is therefore the lowest priority.

**Independent Test**: Can be tested by opening an Aggregate that has legacy invariant text, confirming each text entry now appears as an Invariant object in the design tree; and by running an ingestion of a requirements document and confirming candidate Invariants appear under the relevant Aggregates.

**Acceptance Scenarios**:

1. **Given** an Aggregate with legacy plain-text invariant entries, **When** its Invariants are first accessed, **Then** each text entry is migrated into a first-class Invariant object with that text as its declaration statement, with no data loss.
2. **Given** legacy invariant text has been migrated, **When** the planner views the Aggregate afterward, **Then** the invariants are managed only as Invariant objects and the legacy plain-text list is no longer the source of truth.
3. **Given** a requirements document is ingested, **When** the pipeline identifies aggregate-level rules, **Then** candidate Invariants are created under the relevant Aggregates and are visible in the design tree.
4. **Given** an ingestion-created Invariant, **When** the planner reviews it, **Then** it is editable and deletable exactly like a manually created Invariant.

---

### Edge Cases

- **Deleting a shared condition's last reference**: When an Invariant that references a shared condition is deleted, the shared condition remains as long as at least one other Command or Invariant still references it; it is only removed when no references remain.
- **Referencing a Command outside the Aggregate**: An Invariant references conditions from Commands within the same Aggregate; conditions from Commands of other Aggregates are not offered as reference candidates.
- **Editing a shared condition that another planner is also viewing**: The last saved edit wins; the shared condition reflects the most recent save (consistent with how Command GWT editing already behaves).
- **Migration when legacy text is empty or duplicated**: Empty legacy invariant strings are skipped; identical duplicate strings on the same Aggregate produce a single Invariant.
- **Invariant with no detailed conditions**: An Invariant may exist with only a declaration statement and no GWT conditions; it is valid but flagged as incompletely specified.
- **Ingestion produces an Invariant that duplicates an existing one**: A re-ingestion of the same requirement does not create duplicate Invariant objects on the same Aggregate.

## Requirements *(mandatory)*

### Functional Requirements

#### Invariant object & design tree

- **FR-001**: System MUST provide an **Invariant** as a first-class modeling object that is attached under an Aggregate, with zero or more Invariants per Aggregate.
- **FR-002**: Each Invariant MUST have a **declaration statement** — a human-readable sentence stating the rule the Aggregate must uphold.
- **FR-003**: System MUST display Invariants in the Aggregate design tree on the Design tab as drill-down child objects of their Aggregate, presented consistently with the Aggregate's other design objects.
- **FR-004**: System MUST NOT render Invariants as stickers or nodes on the model canvas; Invariants are surfaced only through the design tree.
- **FR-005**: Users MUST be able to create a new Invariant under an Aggregate, edit its declaration statement, and delete it.
- **FR-006**: System MUST persist Invariants and their declaration statements so they survive page reloads and are shared across users of the same model.

#### Invariant property editor & detailed conditions

- **FR-007**: System MUST open a property editor when a user clicks an Invariant, showing the declaration statement and the Invariant's detailed Given-When-Then conditions.
- **FR-008**: The detailed-condition editor for an Invariant MUST use the same Given-When-Then editing experience that is used for editing a Command's GWT conditions.
- **FR-009**: Users MUST be able to add a detailed GWT condition to an Invariant either by **referencing an existing GWT condition attached to a Command in the same Aggregate** or by **declaring a new invariant-only condition**.
- **FR-010**: When a condition is referenced from both a Command and an Invariant (or from multiple Invariants), the system MUST treat it as a **single shared condition**, not as independent copies.
- **FR-011**: System MUST allow a shared condition to be edited from either the Invariant editor or the Command's GWT editor, and MUST apply the edit to the single shared condition so the change is visible everywhere it is referenced.
- **FR-012**: System MUST propagate edits to a shared condition to all referencing locations **without prompting the user for confirmation** about the propagation.
- **FR-013**: A condition declared as new (invariant-only) MUST exist independently and MUST NOT appear on any Command unless it is later explicitly referenced.
- **FR-014**: Users MUST be able to remove a detailed condition from an Invariant; removal MUST detach it from that Invariant only, and MUST NOT delete the underlying shared condition while other references to it remain.
- **FR-015**: When an Invariant is deleted, any invariant-only conditions that belong solely to it MUST be removed, while shared conditions still referenced elsewhere MUST be preserved.

#### Connection to acceptance criteria

- **FR-016**: System MUST let an Invariant's detailed conditions connect to the acceptance criteria (GWT conditions) of the Commands handled by the same Aggregate, so an acceptance criterion can serve as proof that an invariant is upheld.
- **FR-017**: System MUST present conditions that resolve to the same underlying shared condition as identical wherever they appear, so planners can recognize that editing one affects the other.

#### Seeding & ingestion

- **FR-018**: System MUST migrate each Aggregate's existing plain-text invariant entries into first-class Invariant objects, using each text entry as the declaration statement, with no loss of the original text.
- **FR-019**: After migration, Invariants MUST be managed exclusively as Invariant objects; the legacy plain-text invariant list MUST no longer be the source of truth.
- **FR-020**: The requirements ingestion pipeline MUST be able to extract candidate Invariants from incoming requirements and attach them to the relevant Aggregates.
- **FR-021**: Ingestion-created Invariants MUST be editable and deletable in the same way as manually created Invariants.
- **FR-022**: Re-ingesting the same requirement MUST NOT create duplicate Invariant objects on the same Aggregate.

### Key Entities *(include if feature involves data)*

- **Invariant**: A first-class object representing a business rule an Aggregate must always uphold. Attached under exactly one Aggregate. Has a declaration statement (the rule, in plain language) and an ordered set of detailed conditions. May originate from manual authoring, migration of legacy text, or ingestion. Has a state of "completely specified" vs. "declaration only" depending on whether it has detailed conditions.
- **Aggregate**: An existing modeling object; now also owns zero or more Invariants in addition to its Commands and other design objects.
- **GWT Condition (Given / When / Then)**: An existing condition unit used as Command acceptance criteria. Now also usable as an Invariant's detailed condition. A single GWT Condition may be **shared** — referenced by one or more Commands and/or one or more Invariants — and edits to it apply to all references.
- **Command**: An existing modeling object handled by an Aggregate; its acceptance criteria (GWT conditions) can be referenced by the Aggregate's Invariants.
- **Reference link**: The connection by which a Command or an Invariant uses a shared GWT Condition. Multiple reference links to one GWT Condition is what makes it shared.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A planner can locate, open, and read every Invariant of an Aggregate entirely from the design tree, with no Invariant requiring the canvas to be inspected.
- **SC-002**: A planner can create a new Invariant and give it a declaration statement in under 30 seconds.
- **SC-003**: When a shared condition is edited in one place, 100% of the other places that reference it reflect the change with no further user action.
- **SC-004**: After migration, 100% of each Aggregate's pre-existing invariant text entries are present as Invariant objects with their original wording intact.
- **SC-005**: A planner who knows the Command GWT editor needs no additional instruction to edit an Invariant's detailed conditions, because the editing experience is the same.
- **SC-006**: For an Invariant condition that references a Command acceptance criterion, a planner can confirm in under 10 seconds that the two are the same shared condition.
- **SC-007**: Re-running ingestion of an unchanged requirements document produces zero duplicate Invariant objects.

## Assumptions

- The feature applies to the existing Aggregate design model; Aggregates, Commands, and GWT conditions already exist as modeling concepts and are reused rather than reinvented.
- "The same GWT editor" refers to reusing the existing Command GWT editing interface for the Invariant detailed-condition editor, so planners get an identical experience.
- Sharing a condition is established by **explicit referencing** — the planner picks an existing Command acceptance criterion to reference — rather than by automatic text matching. Two separately authored conditions with coincidentally identical text are not auto-merged.
- Editing a shared condition propagates silently (no confirmation dialog), per the planner's stated preference; impact awareness, if needed, is handled by the project's existing change-impact tooling outside this feature.
- An Invariant references conditions only from Commands of the **same Aggregate**, keeping the invariant scoped to the aggregate boundary.
- Migration of legacy invariant text happens once per Aggregate (on first access of its Invariants) and is non-destructive — the original text is preserved as the declaration statement.
- Ingestion-based extraction of Invariants reuses the existing requirements ingestion pipeline; defining the exact extraction prompt/heuristics is an implementation detail deferred to planning.
- Concurrent-edit conflicts on a shared condition follow the same last-write-wins behavior already used for Command GWT editing; no new locking mechanism is introduced.
- This feature targets the planner ("기획자") persona who already uses the Design tab and the requirements/event-modeling features.

## Design Refinements (post-spec, accepted during implementation)

These planner-directed refinements were accepted after the initial spec and are reflected in
the implementation:

- **DR-1 — Invariant GWT has no "When".** An invariant's detailed condition uses only Given and
  Then; "When" is meaningless for an always-true rule. The shared GWT editor hides the When row
  for invariant-owned bundles (referenced Command bundles keep it).
- **DR-2 — A GWT Then may declare an Exception outcome.** In addition to (or instead of) the
  normal outcome, a Then can reference an **Exception** object presented to the user. This
  applies to both Command GWT and Invariant GWT.
- **DR-3 — Exception is an Aggregate domain object.** An Exception is created and managed as a
  domain object of its Aggregate, a sibling of enumerations and value objects. It has a name, a
  user-facing message, and structured fields. A GWT Then references one by name.
- **DR-4 — Invariant editing lives in the right-side property panel.** Invariant property
  editing is shown in the existing right-side Inspector panel (not a separate modal), reached by
  selecting an Invariant in the design tree. The Given-When-Then editor is one reusable,
  optionalized component shared between invariant-owned and referenced-Command conditions.

## Verification & Documentation

- **End-to-end tests**: `frontend/tests/aggregate-invariants.spec.ts` — Playwright drives the
  real navigator tree and right-side property panel with the backend mocked at the network
  boundary. Three tests cover the design-tree Invariants group (S1), the editor opening in the
  property panel (S2 / DR-4), and the When-less GWT editor with Exception support (DR-1 / DR-2).
  All three pass.
- **User manual**: `specs/027-aggregate-invariants/manual/USER-GUIDE.md` (with screen captures
  in `manual/images/`) and the converted `manual/USER-GUIDE.docx`.
