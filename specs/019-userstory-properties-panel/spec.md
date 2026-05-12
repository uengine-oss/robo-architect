# Feature Specification: Unified UserStory Editing in Properties Panel

**Feature Branch**: `019-userstory-properties-panel`
**Created**: 2026-05-08
**Status**: Draft
**Input**: User description: "지금 그 그... 유저스토리를 더블클릭했을 때는 팝업이 뜨고 나머지 다른 객체들을 더블클릭하면 속성창 쪽에 뜨는데 그렇게 분리되서는 안되고 유저스토리 또한 속성창에 뜨도록 하고 생성된 그... Acceptance Criteria도 같이 표시되고 수정 가능하게 속성 창을 만들어줘요. 그리고 그렇게 생성된 acceptance criteria가 이후 given when then을 만들 때 참고될 수 있도록 해줘야 돼 given when then 테스트 케이스를 만들 때"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Edit UserStory in the unified Properties panel (Priority: P1)

As an analyst working in the design canvas, when I double-click any object on the canvas — including a UserStory — I want it to open in the same Properties panel I already use for Events, Commands, Aggregates, and other elements. Today, double-clicking a UserStory pops up a separate modal dialog, which breaks the otherwise consistent editing flow and forces me to switch between two different UI surfaces depending on what I clicked.

**Why this priority**: This is the core complaint and the unblocker for everything else in this feature. Without unification, the second requirement (showing/editing Acceptance Criteria inline) and the third (feeding criteria into GWT generation) have nowhere coherent to live. It is also an MVP slice on its own — even with no other change, removing the popup and routing UserStory editing through the existing Properties panel delivers immediate value.

**Independent Test**: Can be fully tested by opening the canvas, double-clicking a UserStory node, and confirming that the Properties panel (the same one used for Events/Commands) opens with the UserStory's role, action, benefit, priority, and status fields editable — and that no separate modal/popup appears.

**Acceptance Scenarios**:

1. **Given** the canvas is open and the Properties panel is hidden, **When** the user double-clicks a UserStory node, **Then** the Properties panel opens (or focuses) and displays the UserStory's editable fields, and no modal popup is shown.
2. **Given** the Properties panel is already showing another object (e.g., a Command), **When** the user double-clicks a UserStory, **Then** the Properties panel switches to display the UserStory and replaces the previous object's content.
3. **Given** the user edits a field in the UserStory Properties panel and confirms the change, **When** the change is saved, **Then** the new value is reflected on the canvas, in the navigator tree, and persists across page reloads.
4. **Given** the user double-clicks a UserStory from the navigator tree (not the canvas), **When** the panel opens, **Then** the same Properties panel surface is used (no separate modal), keeping behavior consistent regardless of where the double-click originates.

---

### User Story 2 - View and edit Acceptance Criteria inline (Priority: P1)

When the Properties panel shows a UserStory, I want to see the list of Acceptance Criteria that were generated for that story (during requirements ingestion), and I want to be able to edit them — adding, removing, reordering, and modifying individual criteria — directly inside the Properties panel without leaving it.

**Why this priority**: Acceptance Criteria are the contract that turns a one-line user story into a testable unit. Today they are generated upstream but not surfaced for review or refinement, so analysts cannot correct or extend them. This must be P1 because it is what makes the unified Properties panel actually useful for UserStories — without it, we have only renamed the popup. It also gates User Story 3 (criteria-driven GWT generation), which depends on having editable, trustworthy criteria.

**Independent Test**: Can be tested by selecting a UserStory that already has generated Acceptance Criteria, opening the Properties panel, confirming all generated criteria are visible, editing one criterion's text, adding a new criterion, deleting an existing one, and verifying that the changes persist after closing and re-opening the panel.

**Acceptance Scenarios**:

1. **Given** a UserStory has Acceptance Criteria generated during ingestion, **When** the user opens that UserStory in the Properties panel, **Then** the panel displays each criterion as an editable item in an ordered list.
2. **Given** the Properties panel is showing a UserStory's criteria, **When** the user edits the text of one criterion and confirms, **Then** the change is persisted and visible on subsequent opens.
3. **Given** the Properties panel is showing a UserStory's criteria, **When** the user adds a new criterion, **Then** the new item is appended to the list and persisted with the UserStory.
4. **Given** the Properties panel is showing a UserStory's criteria, **When** the user removes a criterion, **Then** the item is removed from the list and the deletion persists.
5. **Given** a UserStory has no Acceptance Criteria yet (e.g., authored manually after ingestion), **When** opened in the Properties panel, **Then** the criteria section is shown as an empty editable list with an obvious affordance to add the first criterion.

---

### User Story 3 - Acceptance Criteria inform Given-When-Then generation (Priority: P2)

When the system generates Given-When-Then test cases for the Commands and Policies linked to a UserStory, it should treat that UserStory's current Acceptance Criteria as authoritative input — so the GWTs reflect the criteria the analyst actually approved or edited, rather than only deriving GWTs from the surrounding domain elements.

**Why this priority**: This is the payoff for editing criteria — it closes the loop between "what the analyst said the story must do" and "what the test cases verify." It is P2 (not P1) because it depends on Story 2 being in place (criteria must exist and be editable before they can be authoritative input), and because the existing GWT generation already produces something usable; this story improves fidelity rather than enabling a missing capability. It is independently testable once Stories 1 and 2 ship.

**Independent Test**: Can be tested by: (a) opening a UserStory, editing its Acceptance Criteria to a known set of statements, (b) triggering GWT generation for a Command linked to that UserStory, and (c) confirming the produced GWT scenarios reflect the edited criteria (not only the pre-edit ingestion criteria or unrelated domain context).

**Acceptance Scenarios**:

1. **Given** a UserStory with edited Acceptance Criteria and a Command linked to it, **When** GWT generation is triggered for that Command, **Then** the resulting GWT scenarios visibly correspond to the current Acceptance Criteria (each criterion is reflected in at least one scenario or explicitly accounted for).
2. **Given** a UserStory whose Acceptance Criteria have been edited after the initial ingestion run, **When** GWT generation is triggered, **Then** the generator uses the current (edited) criteria, not a stale snapshot from ingestion.
3. **Given** a UserStory with no Acceptance Criteria, **When** GWT generation is triggered for a linked Command, **Then** the generator falls back to the existing behavior (deriving GWT from command/event/aggregate context) without error.
4. **Given** a UserStory linked to multiple Commands, **When** GWT is generated for each Command, **Then** the same Acceptance Criteria are referenced consistently across all linked Commands' GWT generation.

---

### Edge Cases

- **UserStory deleted while Properties panel is open**: Panel must clear gracefully and not retain stale fields that could be re-saved.
- **Concurrent edit**: If a UserStory's criteria are being regenerated by an ingestion run while the user is editing them in the Properties panel, the user's manual edits must not be silently overwritten — the system must either block, warn, or merge predictably.
- **Very long criteria list**: A UserStory with many criteria (e.g., 20+) must remain readable and editable in the Properties panel without breaking the layout.
- **Criterion text containing special characters or multi-line content**: Editing must preserve line breaks and special characters when persisted and when later consumed by GWT generation.
- **Reordering**: If the order of criteria carries meaning (and it should, since it influences readability and the order GWT scenarios may follow), the panel must support stable reordering and persistence.
- **Existing modal still bookmarked / linked from elsewhere**: Any existing entry points (navigator tree double-click, deep links, keyboard shortcuts) that previously opened the modal must now route to the Properties panel instead — no orphaned UI path that still launches the old popup.
- **Empty criteria submitted to GWT**: When a UserStory has zero criteria, the GWT generator must not produce empty/placeholder scenarios attributed to "criterion #1" — fallback behavior (Story 3, scenario 3) must engage.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST display UserStory editing in the same Properties panel surface used for other canvas objects (e.g., Events, Commands, Aggregates), and MUST NOT open a separate modal/popup for UserStory editing.
- **FR-002**: System MUST treat all entry points that currently open the UserStory editor (canvas double-click, navigator tree double-click, and any equivalent action) as routing to the unified Properties panel.
- **FR-003**: The Properties panel for a UserStory MUST allow the user to view and edit the existing UserStory fields (role, action, benefit, priority, status) with the same interaction patterns used for other object types in the panel.
- **FR-004**: The Properties panel for a UserStory MUST display all Acceptance Criteria currently associated with that UserStory, in the order they are stored.
- **FR-005**: The Properties panel MUST allow the user to add a new Acceptance Criterion, edit the text of any existing criterion, remove a criterion, and reorder criteria.
- **FR-006**: Edits to Acceptance Criteria made in the Properties panel MUST persist with the UserStory such that they are visible after closing the panel, navigating away, and reopening the same UserStory, and MUST survive a full page reload.
- **FR-007**: When Given-When-Then test cases are generated for any Command, Policy, or related element linked to a UserStory, the generator MUST consume that UserStory's current persisted Acceptance Criteria as input alongside the existing domain context.
- **FR-008**: When a UserStory has no Acceptance Criteria, GWT generation MUST fall back to its prior behavior (deriving scenarios from domain context only) without erroring or producing placeholder criteria-based scenarios.
- **FR-009**: System MUST remove or fully replace the legacy UserStory popup/modal entry path so that no user action results in the old separated-popup experience after this feature ships.
- **FR-010**: The Properties panel MUST visually distinguish UserStory-specific sections (in particular Acceptance Criteria) so that users can locate and operate on them quickly, consistent with how other type-specific sections are presented for Events, Commands, etc.
- **FR-011**: System MUST validate Acceptance Criteria edits against the same rules that apply to ingestion-generated criteria (e.g., non-empty text per criterion) and surface validation errors inline in the Properties panel.
- **FR-012**: When Acceptance Criteria are regenerated by a future ingestion run on the same UserStory, the system MUST preserve manual edits — once a user has edited a UserStory's Acceptance Criteria via the Properties panel, subsequent ingestion runs MUST NOT overwrite that field, while still applying their normal updates to other UserStory fields. The "user has edited" signal is durable per UserStory and is only cleared by a future explicit reset action (out of scope for this feature).

### Key Entities

- **UserStory**: A unit of intent expressed in role/action/benefit form, with priority and status. Now also carries an ordered list of Acceptance Criteria as a first-class, user-editable attribute (previously generated upstream but not surfaced for editing). Linked to Commands and Policies that implement it.
- **Acceptance Criterion**: A single, human-readable statement describing a condition the UserStory must satisfy to be considered done. Owned by exactly one UserStory; ordered within that UserStory's list. Acts as a contract input for downstream GWT generation.
- **Given-When-Then (GWT) Scenario**: A test case attached to a Command or Policy. After this feature, scenarios produced for an element linked to a UserStory reflect that UserStory's current Acceptance Criteria, in addition to the surrounding domain context already used today.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of UserStory editing actions (canvas double-click, navigator double-click, and any other entry point) open the unified Properties panel; zero entry points still open the legacy popup.
- **SC-002**: An analyst can review and finalize all Acceptance Criteria for a UserStory in the Properties panel without opening any other dialog or page.
- **SC-003**: Edits to Acceptance Criteria persist across reload with no data loss in 100% of test cases (covering edit, add, remove, reorder).
- **SC-004**: For UserStories that have at least one Acceptance Criterion, every GWT generation run produces output where each criterion is observably reflected (each criterion is referenced or addressed by at least one generated scenario).
- **SC-005**: Time for an analyst to "open a UserStory and edit one of its Acceptance Criteria" (measured from double-click to confirmed save) is no slower than the current popup-based flow, and ideally faster, because no modal context switch is required.
- **SC-006**: After this feature ships, support/feedback reports about "the UserStory editor feels different from other objects" drop to zero in the next review cycle.

## Assumptions

- The existing Properties panel is the correct host for this unified editing experience, and its current type-based rendering pattern can accommodate a new UserStory case without architectural rework.
- Acceptance Criteria are already produced during requirements ingestion and stored in association with the UserStory; this feature surfaces and makes them editable rather than introducing a new generation step.
- The order of Acceptance Criteria is meaningful (analysts will rely on it for narrative flow and as the implicit order GWT scenarios may follow), and therefore persistence must preserve order.
- GWT generation is an existing capability that runs against Commands/Policies; this feature extends its inputs rather than replacing the generator.
- "Linked to a UserStory" is an existing relationship in the model (UserStory ↔ Command and UserStory ↔ Policy) that the GWT generator can already follow or be made to follow without introducing a new relationship type.
- Removing the legacy popup is acceptable; there is no requirement to keep both surfaces available behind a flag.
- The audience for editing Acceptance Criteria is the same role that authors UserStories today (analyst / domain modeler) — no new permission model is required for this feature.
