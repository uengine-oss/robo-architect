# Feature Specification: Figma-Component-Aware Wireframe Generation

**Feature Branch**: `024-figma-component-aware-wireframe`
**Created**: 2026-05-12
**Status**: Draft
**Input**: User description: "기존에 피그마 컴포넌트 파일을 읽어다가 그걸 기반으로 와이어프레임을 생성하는 기능을, 연결된 피그마 다큐먼트에 컴포넌트 정의가 포함된 페이지가 있는 경우 그 컴포넌트들을 먼저 VLM 으로 파악해서 메타데이터(이름·생김새)를 채우고, 와이어프레임 생성 시 그 컴포넌트들을 우선 사용하도록 한다. 와이어프레임 생성 옵션에 HTML / Figma 외 'Figma + 컴포넌트' 옵션을 추가한다."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Scan and index the bound Figma file's component library (Priority: P1)

A design lead has already bound a Figma document (spec 016) that contains a "Components" page with `COMPONENT` / `COMPONENT_SET` nodes — buttons, cards, inputs, headers, list items, the team's design system. They open the FigmaBinding modal and click "컴포넌트 스캔". The system traverses the bound file, finds every component, fetches a thumbnail per component, sends each thumbnail to a vision LLM that returns one sentence describing what the component is and what it's for, and persists the result as `:FigmaComponent` nodes attached to the singleton binding. A success toast reports "N 개 인식됨" and the modal shows the catalog size.

**Why this priority**: This is the foundation — without an indexed catalog the downstream "use components in wireframes" feature has nothing to choose from. It is independently valuable because the catalog can be inspected in Neo4j (or via the list endpoint) even before wireframe wiring lands.

**Independent Test**: With a binding pointed at a Figma file that has ≥3 `COMPONENT` nodes across one or more pages, click "컴포넌트 스캔". Verify (a) `MATCH (c:FigmaComponent) RETURN count(c)` matches the actual COMPONENT/COMPONENT_SET count, (b) each row has a non-empty `name` and `vlmDescription`, (c) the modal's catalog count badge updates without page refresh.

**Acceptance Scenarios**:

1. **Given** an active binding to a Figma file with `COMPONENT` nodes on pages A and B, **When** the modeler clicks "컴포넌트 스캔", **Then** `:FigmaComponent` nodes are created for every COMPONENT/COMPONENT_SET, each with `bindingFileKey`, `figmaNodeId`, `name`, `pageName`, `vlmDescription` populated, and `(b:FigmaBinding)-[:HAS_COMPONENT]->(c:FigmaComponent)` edges exist.
2. **Given** a re-scan after a previous successful scan, **When** the modeler clicks scan again, **Then** components matching the same `figmaNodeId` are updated in place (not duplicated), components no longer present in the Figma file are removed, and new components are added.
3. **Given** the bound Figma file has zero `COMPONENT`/`COMPONENT_SET` nodes, **When** scan runs, **Then** the operation completes with `componentCount: 0`, the toast says "컴포넌트를 찾지 못했습니다", and no `:FigmaComponent` rows are created.
4. **Given** the VLM call fails or times out for a specific component, **When** scan continues, **Then** that component is persisted with an empty `vlmDescription` (rather than aborting the whole scan), and the response summary lists per-component VLM failures.
5. **Given** the binding is missing or disconnected, **When** scan is requested, **Then** the endpoint returns `404 no_active_binding`.

---

### User Story 2 — Add "Figma + Components" wireframe generation mode (Priority: P1)

In the requirements ingestion upload modal, the existing "UI 생성" toggle (`HTML` / `Figma UI`) gains a third option: "Figma + Components". When selected, ingestion-phase wireframe generation injects the bound Figma file's component catalog into the LLM system prompt (in addition to or in place of the local open-pencil catalog) so the LLM picks the user's own components, and the resulting sceneGraph references them by `figmaNodeId`.

**Why this priority**: This is the user-visible outcome — designers get wireframes built from their own design system rather than generic shapes. Without this option, the catalog from US1 is invisible.

**Independent Test**: With a binding that has ≥5 components scanned, upload a small RFP, select "Figma + Components" mode, run ingestion to completion. Verify (a) the generated `:UI` nodes' `sceneGraph` contains nodes that reference `figmaNodeId` values present in `:FigmaComponent`, (b) SmartLogger emits `ingestion.ui_wireframe.figma_components.success` events naming the picked components, (c) screens for which the LLM couldn't find a fitting component fall back without aborting the run.

**Acceptance Scenarios**:

1. **Given** the binding has a non-empty component catalog, **When** the user uploads with `ui_generation_mode = "figma-with-components"`, **Then** for each generated UI the LLM is prompted with the bound catalog (name + vlmDescription per component) and its JSON output is parsed into a sceneGraph whose nodes carry `figmaNodeId` pointers to `:FigmaComponent`.
2. **Given** the binding has zero components scanned, **When** the user opens the upload modal, **Then** the "Figma + Components" toggle option is rendered disabled with a tooltip "바운드 파일에 컴포넌트 없음 — 먼저 스캔하세요"; the upload payload cannot be sent with this mode selected.
3. **Given** the binding is fully disconnected, **When** the upload modal opens, **Then** the "Figma + Components" option is hidden entirely (not just disabled).
4. **Given** mid-ingestion the LLM names a component that doesn't exist in the catalog, **When** the sceneGraph converter runs, **Then** that screen falls back to the `Figma UI` (generic) generator and a `figma_component_unresolved` warning is logged with the missing component name.

---

### User Story 3 — Expose component catalog size on the binding (Priority: P2)

The frontend toggle (US2) and the FigmaBinding modal need to know how many components are currently indexed. `GET /api/figma-binding` returns `componentCount: int` alongside the existing fields so the UI doesn't need a second round-trip just to gate the toggle.

**Why this priority**: Quality-of-life — without it, every modal mount makes 2 HTTP calls. Independently valuable because it's the smallest readable signal of "is the catalog ready".

**Independent Test**: With ≥1 binding and 0 components: `GET /api/figma-binding` returns `componentCount: 0`. After scan: same endpoint returns the actual count without scanning again.

**Acceptance Scenarios**:

1. **Given** an active binding with N scanned components, **When** the client calls `GET /api/figma-binding`, **Then** the response includes `componentCount: N`.
2. **Given** no active binding, **When** the client calls `GET /api/figma-binding`, **Then** the response is `null` (unchanged from current behavior).

---

## Edge Cases

- The bound Figma file changes between scan and ingestion (component deleted, renamed). Resolution: at ingestion time, validate each LLM-named component against the current `:FigmaComponent` table; missing rows trigger fallback per US2 AS-4.
- A binding REPLACE wipes the catalog: the new binding starts empty (caller must rescan). The existing `clear_ui_sync_status_for_binding_replace` repo helper has a sibling `clear_figma_components_for_binding_replace`.
- VLM provider misconfigured: scan still records components without descriptions; the LLM gets the catalog with only names (still better than nothing).
- Figma `/v1/images` returns expired URLs (TTL ~30 days): we download immediately during scan and discard the URL post-VLM. Storage of long-lived thumbnails is out of scope.
- Concurrent scans on the same binding: the second call returns `409 scan_in_progress` (in-memory flag, single-singleton binding so no cross-key contention).

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System SHALL accept a `POST /api/figma-binding/components/scan` request and synchronously enumerate every `COMPONENT`/`COMPONENT_SET` node in the bound Figma file across all pages.
- **FR-002**: System SHALL persist each scanned component as a `:FigmaComponent` Neo4j node with `id`, `bindingFileKey`, `figmaNodeId`, `name`, `pageName`, `widthPx`, `heightPx`, `vlmDescription`, `scannedAt`, attached to the singleton `:FigmaBinding` via `[:HAS_COMPONENT]`.
- **FR-003**: System SHALL invoke a vision LLM with each component's thumbnail and a strict 1-sentence-output prompt; VLM failures SHALL NOT abort the scan.
- **FR-004**: System SHALL accept `ui_generation_mode = "figma-with-components"` on both `/api/ingest/upload` and `/api/ingest/upload/figma` and reject any other value other than `"html"` / `"figma"` / `"figma-with-components"`.
- **FR-005**: System SHALL include the bound catalog (each component's name and vlmDescription) in the LLM system prompt for the ingestion UI-wireframe phase when in `figma-with-components` mode.
- **FR-006**: System SHALL convert the LLM's component-pick JSON into a sceneGraph whose component-instance nodes reference `:FigmaComponent.figmaNodeId`.
- **FR-007**: System SHALL fall back to the existing `figma` (generic) wireframe path for any screen whose LLM output names a component absent from the catalog, and SHALL log a `figma_component_unresolved` warning.
- **FR-008**: System SHALL expose `componentCount: int` in `GET /api/figma-binding`.
- **FR-009**: System SHALL provide `GET /api/figma-binding/components` returning the list of scanned components and `DELETE /api/figma-binding/components` to clear the catalog.
- **FR-010**: System SHALL return `404 no_active_binding` for scan/list/delete when no active binding exists, and `409 scan_in_progress` for concurrent scans.
- **FR-011**: Frontend SHALL render the "Figma + Components" toggle option disabled when `componentCount == 0` or binding inactive, with a tooltip describing the reason.

### Non-functional / Constraints

- VLM concurrency capped at 3 to limit cost and respect provider rate limits.
- Scan endpoint runs synchronously; if expected scale exceeds ~150 components, future work (out of scope here) will lift it to SSE.
- No new env var; VLM uses the existing `get_llm()` provider abstraction.

### Key Entities

- **FigmaComponent** — A scanned component definition from the bound Figma file. Lives in Neo4j. Replaces nothing; net-new.
- **FigmaBinding** (extended) — Adds `[:HAS_COMPONENT]` outgoing edges and an aggregated `componentCount` exposed in responses.
- **IngestionSession.ui_generation_mode** (extended) — Allowed set grows from `{html, figma}` to `{html, figma, figma-with-components}`.

---

## Success Criteria *(mandatory)*

- **SC-001**: For a bound Figma file with N COMPONENT/COMPONENT_SET nodes, a scan produces exactly N `:FigmaComponent` rows.
- **SC-002**: At least 80% of scanned components have a non-empty `vlmDescription` (assumes a working VLM provider).
- **SC-003**: When `figma-with-components` mode is used with a non-empty catalog, ≥60% of generated UI sceneGraphs contain at least one component instance referencing a real `:FigmaComponent.figmaNodeId` (the rest fall back, which is acceptable).
- **SC-004**: The UI toggle's enabled/disabled state matches `componentCount > 0` 100% of the time within 500ms of binding modal close.
