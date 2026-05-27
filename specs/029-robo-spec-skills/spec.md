# Feature Specification: Robo Spec Skills & MCP Bridge

**Feature Branch**: `029-robo-spec-skills`

**Created**: 2026-05-25

**Status**: Draft

**Input**: User description: "claude code 용 skill 과 mcp 서버를 만드는데, claude code 에서 speckit 과 거의 같은 실행하는 방법으로, /robo-plan 과 /robo-tasks, /robo-implement 를 실행할수 있다 … /robo-sync 명령을 보내면, 소스코드에 개발자가 임의로 수정한 aggregate, event 등 속성 값 등의 변경이 역반영될 수 있다."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Plan an implementation from a Robo Architect design (Priority: P1)

A developer who has designed a Bounded Context (BC) / Aggregate inside Robo Architect opens Claude Code in the linked project and types `/robo-plan <feature-id | BC-name | Aggregate-name>`. The skill pulls the design (BC type, aggregates, commands, events, read models, policies, invariants, user stories) from Robo Architect via the MCP bridge, asks the developer the minimum number of clarifying questions required to disambiguate architecture style (e.g., when BC classification is missing), and produces a `plan.md` under `specs/<NNN>-<slug>/`. The plan reflects **clean architecture** when the BC is marked *core*, and the **default speckit architecture** when it is marked *supporting*.

**Why this priority**: This is the entry point of the entire developer loop. Without `/robo-plan` working end-to-end against a real Robo Architect design, none of the downstream commands (`/robo-tasks`, `/robo-implement`, `/robo-sync`) have anything to operate on, and the Robo Architect ↔ code link cannot be established.

**Independent Test**: Pick a BC that exists in Robo Architect, run `/robo-plan <BC-name>`, and verify that (a) the MCP returned the BC + its aggregates/commands/events, (b) `plan.md` exists under a freshly created `specs/<NNN>-<slug>/`, (c) the architecture section of `plan.md` matches the BC's `core | supporting` classification, and (d) **no** `data-model.md` and **no** `contracts/*.md` files were generated (those remain authoritative inside Robo Architect).

**Acceptance Scenarios**:

1. **Given** a BC named `Order` is classified as `core` in Robo Architect, **When** the developer runs `/robo-plan Order`, **Then** a new `specs/<NNN>-order/plan.md` is produced whose architecture section follows clean architecture (entities/use-cases/interface-adapters/frameworks layering) and references the aggregates/commands/events as they currently exist in Robo Architect — without rewriting them locally.
2. **Given** a BC named `Notification` is classified as `supporting`, **When** the developer runs `/robo-plan Notification`, **Then** the produced `plan.md` follows the default speckit architecture conventions instead of clean architecture.
3. **Given** the argument does not uniquely resolve to one feature/BC/Aggregate in Robo Architect, **When** `/robo-plan` runs, **Then** the skill shows the candidate matches and asks the developer to pick one before generating any file.
4. **Given** the BC has no `core | supporting` classification set in Robo Architect, **When** `/robo-plan` runs, **Then** the skill explicitly asks the developer which architecture style to apply and records the answer back to Robo Architect via MCP so the question is not re-asked next time.
5. **Given** `/robo-plan` runs successfully, **When** inspecting the produced `specs/<NNN>-<slug>/` directory, **Then** there is no `spec.md`, no `data-model.md`, and no `contracts/` subdirectory — the design source of truth stays in Robo Architect.

---

### User Story 2 - Generate tasks and track checkbox progress visible in Robo Architect (Priority: P1)

After `plan.md` exists, the developer runs `/robo-tasks` to get a `tasks.md` containing an ordered checklist of implementation steps tied to specific aggregates/commands/events/read-models. As the developer (or Claude Code) checks boxes off in `tasks.md`, Robo Architect reflects the progress on the corresponding design elements in its UI (e.g., per-aggregate or per-command progress indicators).

**Why this priority**: A visible feedback loop between code progress and the design canvas is what makes the integration worth installing. Tasks are the natural surface for that loop, and without it the developer has no incentive to keep using `/robo-tasks` over plain speckit.

**Independent Test**: Run `/robo-plan` then `/robo-tasks` on a known BC; verify `tasks.md` is produced and the items reference real aggregates/commands/events by name. Tick a checkbox in `tasks.md`, and confirm Robo Architect's Design tab shows that same element as in-progress / done within a reasonable refresh interval.

**Acceptance Scenarios**:

1. **Given** `plan.md` exists for BC `Order`, **When** `/robo-tasks` runs, **Then** `tasks.md` is produced under the same `specs/<NNN>-order/` directory, with tasks grouped/labelled by the aggregate, command, event, or read-model they implement.
2. **Given** the developer toggles a checkbox in `tasks.md` from `[ ]` to `[x]`, **When** Robo Architect's Design tab is open, **Then** the corresponding design element is shown with an in-progress / completed indicator without the developer pushing to Robo Architect manually.
3. **Given** Robo Architect cannot currently reach the linked project path, **When** the developer toggles a checkbox, **Then** the progress indicator stays at its last known state and the UI shows a clear "code link offline" affordance rather than a stale or fake "complete" badge.

---

### User Story 3 - Open the implementation file from the design tab (Priority: P2)

When the developer clicks an Aggregate, Command, Event, or Read Model on Robo Architect's Design tab, Robo Architect opens the actual implementation file in the linked Claude Code workspace's editor — using the file location dictated by `plan.md` (which is itself derived from BC type and the element name).

**Why this priority**: Closes the inverse direction of the loop (design → code navigation). Valuable, but useless without P1 (because there is no `plan.md` to derive paths from and no created files to point at). Hence P2.

**Independent Test**: With a `plan.md` produced and at least one implementation file present at the location it predicts, click the matching element on the Design tab; the file opens in the developer's editor.

**Acceptance Scenarios**:

1. **Given** `plan.md` predicts file path `src/order/domain/Order.ts` for aggregate `Order`, **When** the developer clicks the `Order` aggregate node in the Design tab, **Then** the editor opens that file.
2. **Given** the predicted path does not yet exist on disk, **When** the developer clicks the element, **Then** the design tab shows a "not implemented yet" affordance — not a generic editor error — and offers to scaffold the file via the relevant task in `tasks.md`.
3. **Given** more than one file could plausibly back a single design element (e.g., separate command handler + aggregate method), **When** the developer clicks the element, **Then** the developer is shown the list of candidate files and picks one rather than the system silently guessing.

---

### User Story 4 - Run the implementation loop via /robo-implement (Priority: P2)

With `plan.md` and `tasks.md` in place, the developer runs `/robo-implement` to have Claude Code work through the open tasks. The skill behaves like speckit's `implement` skill but is constrained to the file locations and architecture style dictated by the upstream `plan.md`, and it ticks `tasks.md` checkboxes as it completes items so the Robo Architect UI stays current.

**Why this priority**: Directly delivers the "from design to code" automation, but it strictly depends on P1 and P2 working. It is the natural payoff once the previous loops are solid.

**Independent Test**: After `/robo-plan` and `/robo-tasks`, run `/robo-implement` against a small BC; confirm that the produced code lives under the locations referenced by `plan.md`, that `tasks.md` checkboxes get updated, and that the same items appear as complete in Robo Architect.

**Acceptance Scenarios**:

1. **Given** an unticked task targeting Aggregate `Order`, **When** `/robo-implement` finishes implementing it, **Then** the corresponding checkbox in `tasks.md` is ticked and Robo Architect reflects the change without manual refresh.
2. **Given** the BC is `core`, **When** `/robo-implement` produces code, **Then** files are placed in clean-architecture-aligned directories (domain / use cases / interface adapters / infrastructure) consistent with `plan.md` — not in flat or default speckit layout.
3. **Given** `/robo-implement` cannot complete a task (e.g., ambiguous invariant), **When** it stops, **Then** the task stays unticked, the reason is recorded in `tasks.md` or its companion, and Robo Architect shows the same item as "blocked" rather than "done".

---

### User Story 5 - Reverse sync developer edits back into Robo Architect via /robo-sync (Priority: P2)

A developer manually edits an aggregate's properties, an event's payload, or a command's parameters directly in source code. They run `/robo-sync`, and those changes are detected and pushed back into Robo Architect via MCP, updating the canonical design — so Robo Architect remains the source of truth while still tolerating in-code edits.

**Why this priority**: Without `/robo-sync`, the "source of truth = Robo Architect" rule breaks the first time a developer edits the code. It is essential to the long-term integrity of the loop, but operationally less critical than the forward path (P1/P2) for an initial release.

**Independent Test**: Modify an aggregate property in a generated source file (e.g., add a field), run `/robo-sync`, and verify the same property appears on the aggregate in Robo Architect afterwards. Run `/robo-sync` again with no edits and verify it is a no-op (does not invent or duplicate changes).

**Acceptance Scenarios**:

1. **Given** the developer adds a new property to aggregate `Order` in code, **When** `/robo-sync` runs, **Then** the aggregate in Robo Architect has the new property after the command completes.
2. **Given** the developer renames an event, **When** `/robo-sync` runs, **Then** the developer is asked to confirm the rename (rename vs. delete-and-create) before any destructive change is applied to Robo Architect.
3. **Given** no source code changes have been made since the last sync, **When** `/robo-sync` runs, **Then** Robo Architect is not modified and the command reports "no changes".
4. **Given** a sync conflict exists (e.g., the design changed in Robo Architect at the same time the code changed locally), **When** `/robo-sync` runs, **Then** the command surfaces the conflict and asks the developer to resolve it rather than silently overwriting either side.

---

### User Story 6 - Skills install by direct file copy, not Jinja templating (Priority: P1)

The robo-* skill set is shipped as a self-contained directory tree under a `/robo-spec` root inside the Robo Architect project. When a project is wired up from Robo Architect to a Claude Code workspace (PRD/init), the contents of `/robo-spec` are copied **verbatim** into the workspace's `.claude/skills/` (and any sibling locations the install requires) — no Jinja rendering, no per-project string substitution at install time.

**Why this priority**: This is a hard constraint from the developer that governs how every other story is delivered. Getting it wrong (e.g., generating skills via Jinja at install time) creates per-install drift and makes the skill set unmaintainable. It must be true from day one.

**Independent Test**: Wire any new project to Robo Architect, observe the install copy step, and confirm that the files in the target workspace's skill directories are byte-identical to the files under `/robo-spec` in this repo (after path translation). Confirm no Jinja markers (`{{`, `{%`) appear in the shipped skill files.

**Acceptance Scenarios**:

1. **Given** the `/robo-spec` directory contains the canonical skill sources, **When** a project is initialized from Robo Architect into a Claude Code workspace, **Then** the files copied into the workspace's `.claude/skills/` are byte-identical to the originals under `/robo-spec`.
2. **Given** a skill author wants to update the behavior of `/robo-plan`, **When** they edit only the file under `/robo-spec`, **Then** the next project init copies the updated file verbatim — without anyone touching a template engine.
3. **Given** any file under `/robo-spec`, **When** searched for Jinja control tokens (`{{`, `{%`), **Then** none are found.

---

### Edge Cases

- The MCP server cannot reach the Robo Architect backend (network down, service offline) — the skills must fail loudly with a clear remediation message, not produce a half-filled `plan.md`.
- The argument to `/robo-plan` matches both a BC and an Aggregate of the same name — the developer must be shown the ambiguity and pick.
- The developer renames an Aggregate in Robo Architect after `plan.md` and `tasks.md` already exist — running any robo-* command must surface the drift (the names referenced locally no longer match the design) rather than silently writing to stale paths.
- `tasks.md` contains a checkbox for an item that no longer exists in Robo Architect (e.g., a command was deleted) — the progress reflection must not crash; it should mark the item as orphaned.
- A BC has no aggregates yet — `/robo-plan` should still produce a plan skeleton that flags the design as incomplete rather than emitting an empty file.
- Two developers run `/robo-sync` against the same project concurrently — only one set of changes should reach Robo Architect, and the other developer should be told their sync was rejected (or asked to re-sync after rebase).
- The workspace was once initialized but is now offline — clicking an element in the Design tab should fall back to "code link offline" rather than appear broken (see US2 / US3).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose four user-invocable Claude Code commands — `/robo-plan`, `/robo-tasks`, `/robo-implement`, `/robo-sync` — and MUST NOT expose `/robo-specify` (because the spec source of truth is Robo Architect, not a local `spec.md`).
- **FR-002**: `/robo-plan`, `/robo-tasks`, and `/robo-implement` MUST behave as direct extensions of their `speckit-*` counterparts (i.e., inherit the same workflow semantics where not overridden by FR-003..FR-008).
- **FR-003**: `/robo-plan` MUST accept an argument that may be a Robo Architect feature id, a BC name, or an Aggregate name, and MUST resolve it to exactly one design element via the MCP bridge before producing any file. If the argument is ambiguous or unresolved, the system MUST ask the developer to disambiguate before writing files.
- **FR-004**: `/robo-plan` MUST produce `plan.md` under `specs/<NNN>-<slug>/` and MUST NOT produce `spec.md`, `data-model.md`, or any file under a `contracts/` subdirectory for that feature directory.
- **FR-005**: `/robo-plan` MUST derive the architectural style in `plan.md` from the resolved BC's classification: clean architecture if the BC is `core`, default speckit architecture if the BC is `supporting`. If classification is missing, the system MUST ask the developer which style to use and SHOULD persist the answer back to Robo Architect so the question is not re-asked.
- **FR-006**: The MCP server MUST be the sole channel through which the robo-* skills read or write Robo Architect data (BC classification, aggregates, commands, events, read models, policies, invariants, user stories, progress markers). Skills MUST NOT call Robo Architect HTTP/DB directly.
- **FR-007**: `/robo-tasks` MUST produce a `tasks.md` whose checkbox items are individually attributable to specific design elements (aggregate, command, event, read model, or invariant) by name, so that progress can be reflected per-element in Robo Architect.
- **FR-008**: When a checkbox in `tasks.md` changes state in the linked workspace, Robo Architect MUST reflect the new state on the corresponding design element in its Design tab. When the link is offline, Robo Architect MUST show "code link offline" rather than a stale state.
- **FR-009**: Clicking an Aggregate, Command, Event, or Read Model on Robo Architect's Design tab MUST open the implementation file in the linked Claude Code workspace's editor, using the file location dictated by `plan.md`. If the file does not yet exist, the UI MUST show a "not implemented yet" affordance instead of erroring.
- **FR-010**: `/robo-implement` MUST place produced code in the locations and architectural layering dictated by the upstream `plan.md`, and MUST tick the matching checkboxes in `tasks.md` as items complete.
- **FR-011**: `/robo-sync` MUST detect developer-made changes to aggregate properties, event payloads, command parameters, and equivalent design-bearing constructs in source code, and push those changes back into Robo Architect via MCP. The system MUST ask the developer to confirm before applying destructive changes (renames, deletions) to the design. With no changes since the last sync, `/robo-sync` MUST be a no-op.
- **FR-012**: The robo-* skill set MUST live under a single `/robo-spec` root directory in the Robo Architect repository, and MUST be installed into a target Claude Code workspace by **verbatim file copy** — no Jinja rendering, no per-install template substitution. Updating a skill MUST be a single-file edit under `/robo-spec`.
- **FR-013**: The system MUST detect drift between local artifacts (`plan.md` / `tasks.md` / source) and the current Robo Architect design (renames, deletions, classification changes) and surface it on the next robo-* command invocation rather than silently writing against stale names or paths.

### Key Entities

- **Robo Architect Design**: The canonical source of BC classification, aggregates, commands, events, read models, policies, invariants, and user stories. Owned by Robo Architect; consumed by the skills via MCP.
- **`plan.md`**: A per-feature local artifact derived from a Robo Architect design element, recording chosen architecture (clean vs. default), file-location plan, and references back to design elements by name. Re-generatable; not a source of truth.
- **`tasks.md`**: A per-feature local artifact whose checkboxes are mapped one-to-one (or one-to-many) onto Robo Architect design elements, and whose state drives the progress indicators on Robo Architect's Design tab.
- **MCP Bridge**: The single transport between the skills and Robo Architect. Provides read access for `/robo-plan` and `/robo-tasks`, progress write-back for `/robo-implement`, and reverse design write-back for `/robo-sync`.
- **`/robo-spec` Source Tree**: The canonical, verbatim-copied set of skill files (and any companion assets) that gets dropped into a Claude Code workspace at project init time.
- **Code Link**: The per-project association recording which Claude Code workspace path corresponds to which Robo Architect project, used for opening files from the Design tab and for routing progress events.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer who already has a Robo Architect design for a BC can go from `/robo-plan <BC-name>` to a runnable scaffold via `/robo-tasks` + `/robo-implement` without manually authoring a `spec.md`, `data-model.md`, or `contracts/*.md` for that feature.
- **SC-002**: After `/robo-plan` for a `core` BC, the produced `plan.md` is judged by a reviewer to follow clean architecture layering in 100% of cases where the BC is correctly classified, and to follow the default speckit architecture in 100% of cases where the BC is classified as `supporting`.
- **SC-003**: When a checkbox in `tasks.md` changes state, the corresponding indicator in Robo Architect's Design tab updates within 5 seconds in 95% of observed cases (assuming the workspace is online).
- **SC-004**: When a developer clicks an Aggregate, Command, Event, or Read Model in the Design tab, the linked file opens in the editor in under 2 seconds in at least 90% of cases where the file exists at the predicted path.
- **SC-005**: After a developer makes structural edits to aggregates/events/commands in source code and runs `/robo-sync`, the change is visible in Robo Architect in 100% of non-conflicting cases; in conflicting cases, the system never silently overwrites either side.
- **SC-006**: For any release of the `/robo-spec` directory, the files copied into a freshly initialized workspace are byte-identical to the originals under `/robo-spec` (verifiable by checksum).

## Assumptions

- Robo Architect already exposes (or can be extended to expose) the data the MCP server needs: BC classification (`core` vs `supporting`), aggregates, commands, events, read models, policies, invariants, user stories, and per-element progress indicators. The classification field may be absent on some BCs; in that case, the skill asks the developer.
- The Claude Code workspace path for each Robo Architect project is already known to the system (established as part of the existing project-init flow). This feature does not redesign workspace linkage; it consumes it.
- Architecture conventions: "clean architecture" here means the standard four-layer split (entities / use cases / interface adapters / frameworks & drivers) applied per-BC; "default speckit architecture" means whatever the upstream `speckit-plan` skill produces unmodified.
- `/robo-implement` builds on `/speckit-implement`'s semantics for the actual coding loop — this feature does not redefine how implementation is sequenced beyond enforcing layout from `plan.md` and writing back checkbox progress.
- Conflict detection for `/robo-sync` is scoped to design-relevant constructs (aggregates, commands, events, read models, their fields/params/payloads). Free-form code changes outside those constructs are not the concern of `/robo-sync`.
- The "copy verbatim from `/robo-spec`" install mechanism is plumbed through the existing project-init flow in Robo Architect; this feature owns the contents of `/robo-spec` and the rule that they are copied as-is.
