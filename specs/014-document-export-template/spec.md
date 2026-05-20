# Feature Specification: Selectable Design-Document Export with Templates

**Feature Branch**: `014-document-export-template`
**Created**: 2026-05-06
**Status**: Backfilled (reverse-engineered from existing implementation)
**Input**: Backfill from existing code at `frontend/src/features/exportDocument/ui/ExportDocumentDialog.vue`, `frontend/src/features/exportDocument/ui/ExportDocumentTemplate.vue`, `frontend/src/features/exportDocument/ui/exporters/captureExporter.js`, `frontend/src/features/canvas/ui/CanvasWorkspace.vue` (entry point)

## User Scenarios & Testing

### User Story 1 - Preview a polished "설계 산출물" (design deliverable) of the current model (Priority: P1)

From the canvas toolbar, the architect clicks "설계 산출물" to open a full-screen dialog rendering a paginated, print-ready document built from the live Neo4j model (Bounded Contexts, Aggregates, Commands, Events, Policies, Read Models, User Stories, plus a Mermaid Context Map of cross-BC policy edges). The cover, table of contents, and per-section pages are all generated client-side from `/api/contexts` and `/api/contexts/{id}/full-tree`.

**Why this priority**: This is the user's main "show the architecture to a stakeholder" surface. Without it, the model is only consumable through the canvas.

**Independent Test**: Open the canvas with at least one BC, click the export-document button, and verify the dialog renders the main cover (with BC/Aggregate/User Story counts), TOC, and at least one section.

**Acceptance Scenarios**:

1. **Given** the canvas has ≥1 BoundedContext, **When** the user opens the export dialog, **Then** `loadAllData()` calls `/api/contexts` and, for each context, `/api/contexts/{id}/full-tree`, and a paginated document is rendered.
2. **Given** the document is open, **When** the user toggles section checkboxes (사용자 스토리 / Bounded Context / 모델 전반 정보 / API 명세 / Aggregate 상세), **Then** sections appear/disappear and section numbers re-index in order.

### User Story 2 - Export to PDF via the browser print dialog (Priority: P1)

The user clicks "PDF로 내보내기"; the dialog clones the scrollable document into a new window with a curated print stylesheet (`EXPORT_CSS`, `@page { size: A4; margin: 16mm 14mm; }`), forces page breaks at `.page` boundaries, prevents internal breaks within `.block`, and triggers `window.print()`.

**Why this priority**: Zero-dependency PDF path that works in every browser.

**Independent Test**: With the dialog open, click "PDF로 내보내기" and verify a new tab opens, populated with the styled document, with the print dialog visible.

**Acceptance Scenarios**:

1. **Given** the dialog is open, **When** the user clicks PDF export, **Then** a popup window is opened, populated with `EXPORT_CSS` + page-broken HTML, and `print()` is called after `onload`.
2. **Given** popups are blocked, **When** PDF export is clicked, **Then** an error snackbar reads "팝업이 차단되었습니다. 팝업 허용 후 다시 시도하세요."

### User Story 3 - Export to editable Word (.docx) and PowerPoint (.pptx) (Priority: P1)

The user clicks "Word (.docx) 로 내보내기" or "PowerPoint (.pptx) 로 내보내기"; the system uses native object generation (`docx`, `pptxgenjs`) for text and tables — so the output is editable — and only renders Mermaid diagrams as captured images (`html-to-image`). Sub-sections of the same Bounded Context are coalesced into a single Word section / PPT slide cluster to avoid wasted pages.

**Why this priority**: Stakeholders frequently need to edit, comment, or re-style the deliverable; static-image-only exports break that workflow.

**Independent Test**: Click "Word 로 내보내기", wait for completion, open the saved `.docx`, and verify that table cells contain selectable text (not images).

**Acceptance Scenarios**:

1. **Given** the dialog has finished loading, **When** the user clicks Word export, **Then** `exporters/captureExporter.exportToWord(data, container, onProgress)` is called with the template's reactive data and DOM container, progress is reflected in the loading text, and a `.docx` is downloaded named `설계산출물-{YYYY-MM-DD}.docx`.
2. **Given** PPT export is invoked, **Then** the same data flow runs through `exportToPPT`, producing a `.pptx` with one slide cluster per BoundedContext.
3. **Given** the export is in progress (`isExporting=true`), **When** the user clicks the close button, **Then** the dialog refuses to close until the export resolves.

### User Story 4 - Cross-BC Context Map auto-generated as a Mermaid diagram (Priority: P2)

When the model contains policies that link an Event in one Bounded Context to a Command in another Bounded Context (cross-BC policies), the template auto-derives a Mermaid `graph LR` Context Map: BCs colored by `domainType` (Core / Supporting / Generic), edges labeled with the policy names, rendered to inline SVG in the document and captured as an image during Word/PPT export.

**Why this priority**: Bounded-context relationships are the most-asked-about diagram in architecture reviews; auto-deriving it saves manual upkeep.

**Independent Test**: Create two BCs, add a policy in BC-A whose `triggerEventId` belongs to BC-B and `invokeCommandId` belongs to BC-A. Open the export dialog and verify a Mermaid diagram appears in the "컨텍스트 간 연관 관계" section.

**Acceptance Scenarios**:

1. **Given** ≥1 cross-BC policy exists, **When** the document renders, **Then** `crossBCPolicies` is non-empty and a Mermaid SVG is rendered into `.ctx-map-wrap`.
2. **Given** zero cross-BC policies, **When** the document renders, **Then** the "컨텍스트 간 연관 관계" block is omitted entirely.

### Edge Cases

- A user story not assigned to any BC is shown under `'미배정'` (Unassigned) in the user-story table.
- Bounded Contexts are sorted by domain type: Core (0) → Supporting (1) → Generic (2) → others (9).
- The last `.page`/`.block` element has its trailing `page-break-after` reset to `auto` so the PDF doesn't end with a blank page.
- During export, the `.no-print` and `.section-selector` elements are cloned-then-stripped so the section toggles never appear in the output.
- All three export formats are mutually exclusive at runtime (the `isExporting` flag guards re-entrancy).
- Mermaid render failures are caught and logged; the rest of the document still exports.

## Requirements

### Functional Requirements

- **FR-001**: System MUST present a full-screen dialog ("설계 산출물 미리보기") triggered from the canvas toolbar, hosting a `<ExportDocumentTemplate>` and an export dropdown (PDF / Word / PowerPoint).
- **FR-002**: The template MUST load all Bounded Contexts via `GET /api/contexts` and, for each, `GET /api/contexts/{id}/full-tree` concurrently (`Promise.all`), populating a `fullTrees` map keyed by context id.
- **FR-003**: The user MUST be able to toggle inclusion of the five section groups: User Stories, Bounded Context, Model Overview, API Specification, Aggregate Detail. Section numbering MUST recompute reactively.
- **FR-004**: A main cover page MUST display the project brand "Robo Architect", the title "소프트웨어 아키텍처 설계서", live counts of Bounded Contexts / Aggregates / User Stories, and the current locale date.
- **FR-005**: A Bounded-Context summary table MUST list, per BC, domain type, description, and counts of Aggregates / Commands / Events / Read Models / User Stories.
- **FR-006**: When ≥1 cross-BC policy exists, the template MUST auto-generate a Mermaid `graph LR` Context Map applying domain-type CSS classes (`core` / `supporting` / `generic`) and labeled edges per policy.
- **FR-007**: PDF export MUST open a new browser window populated with `EXPORT_CSS` and the cloned, break-prepared document HTML, then call `window.print()` after `onload`.
- **FR-008**: Word export MUST produce a native `.docx` (`docx` library) with editable text and tables, and MUST capture Mermaid SVGs as images via `html-to-image`. Filename MUST be `설계산출물-{YYYY-MM-DD}.docx`.
- **FR-009**: PowerPoint export MUST produce a native `.pptx` (`pptxgenjs`) with the same data-vs-image policy as Word; filename MUST be `설계산출물-{YYYY-MM-DD}.pptx`.
- **FR-010**: While `isExporting=true` the dialog MUST disable the Export button, render a loading overlay with the live status text (e.g., "Word 생성 중... (45%)"), and refuse to close.
- **FR-011**: The system MUST coalesce sub-sections belonging to the same Bounded Context into a single Word section / PPT slide cluster (per the docstring in `captureExporter.js`).
- **FR-012**: Export results MUST surface user-visible feedback through a Snackbar (success or error) auto-dismissed after 3.5 s.
- **FR-013**: This feature is fully frontend-driven; it MUST NOT require any export-specific backend endpoint beyond the existing `GET /api/contexts*` reads. Backend serialization helpers, if added later, are optional and out of scope.

### Key Entities

- **BoundedContext** (Neo4j label `BoundedContext`, exposed via `/api/contexts`): primary section grouping; carries `domainType`, `description`.
- **Full-tree payload** (`/api/contexts/{id}/full-tree` response): a denormalized tree of `aggregates[].commands[].events[]`, `aggregates[].events[]`, `policies[]`, `readmodels[]`, `userStories[]`, `uis[]` used as the document's source of truth.
- **CrossBCPolicy** (computed): `{fromBC, fromEvent, policy, toBC, toCommand}` derived by walking the full-trees and matching `policy.triggerEventId` and `policy.invokeCommandId` to their owning Bounded Contexts.
- **ExportPayload** (in-memory): `{data: {allContexts, fullTrees, sortedContexts, allUserStories, crossBCPolicies, sectionNumbers, selectedSections, helpers:{...}}, container: HTMLElement}` passed into `captureExporter.exportToWord` / `exportToPPT`.
- **Selectable Sections** (UI state): `{userStories, boundedContext, modelOverview, apiSpecification, aggregateDetail}` — booleans driving inclusion and numbering.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A user can open the dialog, select sections, and download a Word/PPT/PDF in under 30 seconds for a model with ≤10 Bounded Contexts.
- **SC-002**: 100% of textual content (BC names, descriptions, table cells, user story fields) in the Word/PPT output is selectable/editable text — not images.
- **SC-003**: 100% of cross-BC policies present in the model appear both in the Mermaid Context Map and in the "컨텍스트 간 연관 관계 상세" table.
- **SC-004**: The PDF output respects A4 page size with 16 mm × 14 mm margins and never breaks inside a `.block` element.
- **SC-005**: Concurrent loading of `/api/contexts/{id}/full-tree` MUST tolerate per-context errors (one failed tree must not abort the dialog).
- **SC-006**: Section numbering matches the user's section selections at all times — toggling a section off renumbers the remainder without gaps.

## Assumptions

- This feature reads from existing canvas/contexts read-side endpoints; it does not introduce new backend routes.
- `mermaid`, `docx`, `pptxgenjs`, `html-to-image`, and `file-saver` are already bundled with the frontend (no installation step required at runtime).
- The export filename convention `설계산출물-{YYYY-MM-DD}.{ext}` is intentional and matches downstream stakeholder expectations.
- The Mermaid Context Map is constrained to `graph LR` orientation; alternative layouts are out of scope.
- Custom user-defined templates (e.g., user-uploaded `.dotx`) are not implemented in the current code; the "template" today is the fixed `ExportDocumentTemplate.vue` with togglable sections. Any future per-customer templating would be additive.
- The example files under `export_document_example/` are reference outputs for designing this feature; they are not consumed by the running app.
