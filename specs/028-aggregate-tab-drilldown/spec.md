# Feature Specification: Aggregate Tab Drill-Down & Canvas UX

**Feature Branch**: `028-aggregate-tab-drilldown`
**Created**: 2026-05-18
**Status**: Draft
**Input**: User description: "어그리거트 탭 상단에 어그리거트 탭은 디자인 탭에서 어떤 어그리거트를 선택한 뒤 속성창이 뜰텐데 어그레거트에 대한 속성 창이 디자인 탭에서 눌러줬을 때 거기에서 디테일을 볼 수 있는 버튼이 눌려지면 그러면 어그리거트 탭으로 넘어가면서 해당 어그리거트에 대한 어그리거트 디테일을 볼 수 있게 연결을 좀 해주고 또한 그냥 어그리거트가 선택된 상태에서 탭으로 이동했을 때 알아서 들어올 수 있게 해주고, Aggregate 탭에서 지금은 Bounded Context를 끌어다 캔버스에 넣어야만 나오는데 어그리거트 아이콘을 끌어 넣었을 때도 보일 수 있어야 하고, 그루핑 박스 자체에 어그리거트 색상(노란색) 바탕을 약간 입혀서 어그리거트 내부임을 느끼게 하고, 레이블에 «Aggregate» 스테레오타입을 표시"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Drill into an aggregate from the Design tab (Priority: P1)

While modeling in the Design tab, a user selects an aggregate node and its property panel opens. The property panel offers a "detail" action. Activating it switches the application to the Aggregate tab and immediately presents the detailed view (aggregate root, properties, value objects, enumerations, relationships) of the aggregate that was selected — without the user having to manually find and drag anything.

**Why this priority**: This is the core connective tissue the feature requests. Today there is no path from "I found an aggregate in the Design tab" to "I want to inspect/edit its internals" — the user must remember the name and re-locate it in the Aggregate tab. This single capability delivers the primary value and is independently demonstrable.

**Independent Test**: Open the Design tab, select an aggregate, open its property panel, click the detail action. Verify the active tab becomes the Aggregate tab and the chosen aggregate's detailed view is shown and focused.

**Acceptance Scenarios**:

1. **Given** the Design tab is active and an aggregate node is selected with its property panel open, **When** the user activates the detail action in the property panel, **Then** the application switches to the Aggregate tab and the selected aggregate's detailed view is displayed and brought into view.
2. **Given** the targeted aggregate's detail is not yet present on the Aggregate tab canvas, **When** the detail action is activated, **Then** the aggregate is loaded onto the Aggregate tab canvas and centered/focused.
3. **Given** the targeted aggregate's detail is already present on the Aggregate tab canvas, **When** the detail action is activated, **Then** the existing detail is reused (not duplicated) and brought into focus.
4. **Given** a non-aggregate node is selected in the Design tab, **When** its property panel is open, **Then** the detail action is not offered (or is inert).

---

### User Story 2 - Selection carries over when switching tabs manually (Priority: P2)

A user has an aggregate selected in the Design tab and then switches to the Aggregate tab using the normal tab navigation (not the detail button). The Aggregate tab automatically loads and focuses that same aggregate, so the user does not have to re-select or re-drag it.

**Why this priority**: It removes a smaller but frequent friction point and reinforces the mental model that the two tabs share a "current aggregate". It depends conceptually on the same loading mechanism as US1, so it is valuable but secondary.

**Independent Test**: Select an aggregate in the Design tab, then click the Aggregate tab in the tab bar. Verify the selected aggregate is loaded and focused on the Aggregate tab without further action.

**Acceptance Scenarios**:

1. **Given** exactly one aggregate is selected in the Design tab, **When** the user switches to the Aggregate tab via the tab bar, **Then** that aggregate's detailed view is loaded and focused.
2. **Given** no aggregate (or a non-aggregate node) is selected in the Design tab, **When** the user switches to the Aggregate tab, **Then** the Aggregate tab opens in its normal state (showing previously loaded content or the empty state) with no forced change.
3. **Given** the selected aggregate is already loaded on the Aggregate tab, **When** the user switches tabs, **Then** it is focused without being reloaded or duplicated.

---

### User Story 3 - Drop an aggregate directly onto the Aggregate tab canvas (Priority: P2)

In the Aggregate tab, the user can drag an aggregate item (its icon/entry) from the navigator and drop it onto the canvas to view that single aggregate's detail. Currently only dragging a Bounded Context works; dragging an aggregate has no effect.

**Why this priority**: It closes a clear functional gap that confuses users (the aggregate icon looks draggable but does nothing). It is independent of US1/US2 and testable on its own, but the drill-down button is the headline value, so this is P2.

**Independent Test**: Open the Aggregate tab, drag an aggregate item from the navigator onto the canvas. Verify that aggregate's detailed view appears.

**Acceptance Scenarios**:

1. **Given** the Aggregate tab is active, **When** the user drags an aggregate item onto the canvas, **Then** that aggregate's detailed view is added to the canvas and focused.
2. **Given** the Aggregate tab already shows other aggregates, **When** an aggregate item is dropped, **Then** the new aggregate is added alongside existing content without removing it.
3. **Given** the dropped aggregate is already present on the canvas, **When** it is dropped again, **Then** it is not duplicated; the existing detail is focused.
4. **Given** a Bounded Context is dragged onto the Aggregate tab canvas, **When** it is dropped, **Then** the existing behavior (showing all of that context's aggregates) is preserved.

---

### User Story 4 - Aggregate boundary is visually identifiable (Priority: P3)

The grouping box that surrounds an aggregate's contents on the Aggregate tab canvas is visually styled so users immediately recognize it as an aggregate boundary: it carries a subtle aggregate-colored (yellow) background tint instead of the current neutral/dark fill, and its label region displays an `«Aggregate»` stereotype marker.

**Why this priority**: It is a visual clarity improvement, not a functional capability. It is valuable for reducing confusion but the feature still works without it, so it is lowest priority.

**Independent Test**: Load any aggregate on the Aggregate tab and visually confirm the grouping box has a light yellow tint and an `«Aggregate»` stereotype label.

**Acceptance Scenarios**:

1. **Given** an aggregate is displayed on the Aggregate tab canvas, **When** the user views its grouping box, **Then** the box background shows a subtle yellow (aggregate-color) tint that visually distinguishes it from a non-aggregate container.
2. **Given** an aggregate grouping box is displayed, **When** the user reads its label region, **Then** an `«Aggregate»` stereotype indicator is visible alongside the box's name.
3. **Given** the application is in light or dark theme, **When** the grouping box is rendered, **Then** the yellow tint and stereotype label remain legible and consistent in both themes.

---

### Edge Cases

- The aggregate selected in the Design tab no longer exists in the underlying model (deleted/renamed) by the time the user drills in — the Aggregate tab should show a clear "not found / unavailable" state rather than a blank or error screen.
- Multiple nodes are selected in the Design tab when switching tabs — only a single, unambiguous aggregate selection triggers auto-load; ambiguous multi-selection does not force a change (see US2 scenario 2).
- The detail action is activated for an aggregate whose data is still loading — the Aggregate tab should show a loading state and then resolve to the detail.
- An aggregate is dropped onto the canvas while its detail data fails to load — the canvas should surface a retryable error for that aggregate without breaking other already-loaded content.
- The same aggregate is reached via two paths (e.g., dropped, then drilled into) — it must never appear twice on the canvas.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Design tab's aggregate property panel MUST provide a clearly labeled action that opens the selected aggregate's detail in the Aggregate tab.
- **FR-002**: Activating the detail action MUST switch the active tab to the Aggregate tab.
- **FR-003**: When the detail action is activated, the Aggregate tab MUST display the detailed view of the specific aggregate that was selected, loading it if it is not already present.
- **FR-004**: The detail action MUST focus/center the target aggregate so it is immediately visible after the tab switch.
- **FR-005**: The system MUST NOT create a duplicate detail view when the target aggregate is already loaded on the Aggregate tab; it MUST reuse and focus the existing one.
- **FR-006**: The detail action MUST only be available (or active) when the selected Design-tab node is an aggregate.
- **FR-007**: When exactly one aggregate is selected in the Design tab and the user switches to the Aggregate tab through normal tab navigation, the Aggregate tab MUST automatically load and focus that aggregate.
- **FR-008**: When the Design-tab selection is empty, non-aggregate, or ambiguous (multiple items), switching to the Aggregate tab MUST NOT force a load or change of canvas content.
- **FR-009**: The Aggregate tab canvas MUST accept a dropped aggregate item and display that aggregate's detailed view.
- **FR-010**: Dropping an aggregate item MUST add it without removing aggregates already on the canvas, and MUST NOT duplicate an aggregate already present.
- **FR-011**: The existing ability to drop a Bounded Context onto the Aggregate tab canvas (showing all its aggregates) MUST be preserved.
- **FR-012**: The aggregate grouping box on the Aggregate tab canvas MUST display a subtle aggregate-colored (yellow) background tint that distinguishes it as an aggregate boundary.
- **FR-013**: The aggregate grouping box label region MUST display an `«Aggregate»` stereotype indicator.
- **FR-014**: The yellow tint and stereotype indicator MUST remain legible and consistent across the application's light and dark themes.
- **FR-015**: When a targeted aggregate cannot be found or its data fails to load, the Aggregate tab MUST present a clear, non-blocking error or empty state instead of failing silently.

### Key Entities *(include if feature involves data)*

- **Aggregate**: A domain aggregate selected in the Design tab and inspected in the Aggregate tab. Relevant attributes for this feature: identity, name, owning Bounded Context, and the detailed contents shown in the Aggregate tab (root entity, properties, value objects, enumerations, relationships).
- **Current Aggregate Selection**: The shared notion of "which aggregate the user is currently focused on", set by selecting in the Design tab and consumed by the Aggregate tab for drill-down and tab-switch auto-load.
- **Aggregate Grouping Box**: The visual container on the Aggregate tab canvas that bounds one aggregate's contents and conveys, through color and stereotype label, that everything inside belongs to that aggregate.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can go from "an aggregate selected in the Design tab" to "its detail visible and focused in the Aggregate tab" in a single action (one click of the detail button).
- **SC-002**: After switching to the Aggregate tab via the detail action or via normal tab navigation with one aggregate selected, the target aggregate's detail is visible without any further user input in 100% of attempts.
- **SC-003**: Dragging an aggregate item onto the Aggregate tab canvas results in that aggregate's detail appearing in 100% of attempts, with zero duplicate detail views when the same aggregate is added again.
- **SC-004**: In a usability check, users correctly identify the yellow-tinted, `«Aggregate»`-labeled grouping box as an aggregate boundary without prompting.
- **SC-005**: The previously supported Bounded Context drop behavior continues to work unchanged (no regression).

## Assumptions

- "디테일" / "비율" in the dictated input refers to viewing the aggregate's **detail** view; "비율" is treated as a transcription artifact and not a separate ratio/percentage feature.
- The detail action and tab-switch auto-load resolve the target aggregate by its identity; if it is missing from the underlying model the system shows a not-found state (FR-015).
- Drilling in or switching tabs **adds and focuses** the target aggregate on the Aggregate tab canvas rather than clearing previously loaded aggregates, consistent with the existing additive Bounded Context drop behavior.
- "Selected aggregate" for the tab-switch auto-load (US2) means a single, unambiguous aggregate selection; multi-selection is treated as ambiguous and does not trigger auto-load.
- The aggregate's color is the existing aggregate accent color already used elsewhere in the product (yellow); the grouping box uses a low-opacity tint of it so contained content stays readable.
- The `«Aggregate»` stereotype uses the standard guillemet stereotype convention already familiar from modeling notation.
- The Aggregate tab and Design tab are existing tabs within the same application shell; this feature connects them and does not introduce new tabs.
