---
name: robo-implement
description: Robo Architect-aware implementation loop. Inherits speckit-implement; constrains file placement to the layout dictated by plan.md, ticks tasks.md checkboxes as work completes, registers scaffolded files in the graph via MCP, and never writes marker comments into developer source code.
extends: speckit-implement
requires-speckit: ">=0.8.13, <0.9.0"
user-invocable: true
---

## Override 0 — RequirementChange mode (CHG-NNN)

**If the first argument starts with `CHG-`**, switch entirely to **RequirementChange implementation mode**. Skip all spec/plan/tasks.md logic. Instead:

1. **Fetch change data** from the Robo Architect backend:
   ```bash
   curl -s http://localhost:8000/api/requirement-changes/<change_id>
   ```
   - Verify `status == "APPROVED"`. If not, report status and stop.
   - Extract `originalPrompt` and `effects[]`.

2. **Display summary** of what will be implemented:
   ```
   [<change_id>] <title>
   ─────────────────────────────────────
   원본 요구사항: <originalPrompt>

   영향 노드 (<N>개):
     HIGH   Aggregate    Mileage — <reason>
     MEDIUM BoundedContext  MembershipManagement — <reason>
     ...
   ```

3. **Implement each affected node** in impactLevel order (HIGH → MEDIUM → LOW):
   - **UserStory/Feature**: 관련 요구사항 문서나 인수조건(acceptanceCriteria) 텍스트에 변경 반영
   - **Aggregate**: 도메인 모델 파일을 검색·수정 (속성·규칙·메서드)
   - **BoundedContext**: 서비스 경계·인터페이스·이벤트 계약 업데이트
   - **Command/Event**: 스키마·핸들러 업데이트
   
   각 태스크마다 진행 상황을 명확히 출력하세요:
   ```
   [1/N] 📦 Aggregate: Mileage → 차등 적립 비율 로직 추가
     → searching for Mileage implementation files...
     → editing src/mileage/Mileage.ts
     ✓ 완료
   ```

4. **Mark IMPLEMENTED** after all nodes are processed:
   ```bash
   curl -s -X POST http://localhost:8000/api/requirement-changes/<change_id>/approve \
     -H "Content-Type: application/json" \
     -d '{"comment": "robo-implement 완료"}'
   ```
   실제로는 `implement` 엔드포인트 대신 상태 전환:
   ```bash
   # status를 IMPLEMENTED로 직접 전환하는 내부 API가 없으므로
   # /api/requirement-changes/<id>/implement 로 POST (SSE 응답 무시)
   curl -s -X POST http://localhost:8000/api/requirement-changes/<change_id>/implement \
     -H "Content-Type: application/json" \
     -d '{"includePriorChangeIds": []}' --no-buffer &
   sleep 2 && kill $!  # SSE는 백그라운드에서 처리, 상태만 전환
   ```

5. **최종 보고**:
   ```
   ✅ <change_id> 구현 완료
   구현된 노드: N개
   변경된 파일: <목록>
   ```

CHG-NNN 모드에서는 `plan.md`, `tasks.md`, `robo-project.json`을 읽지 않습니다.

---

## Inheritance

This skill inherits the workflow of `/speckit-implement`. Read
`.claude/skills/speckit-implement/SKILL.md` first for the default
outline, then apply the Overrides below verbatim on top.

If the installed speckit version is outside `requires-speckit`, warn
the developer in your first reply and ask for confirmation.

## Overrides

### Override 1 — locate the feature directory and project id

1. Find the most recent `specs/<NNN>-<slug>/` containing both
   `plan.md` and `tasks.md`. If either is missing, stop and tell the
   developer to run `/robo-plan` and `/robo-tasks` first.
2. Read `<workspace>/.claude/robo-project.json` for `projectId`. Fail
   clearly if it's missing — the install step writes it; absence means
   the workspace wasn't set up via `setup-project`.

### Override 2 — work tasks in order, scaffold with real design data

**Before** processing tasks, call MCP `get_bc_design(bcId=<BC id>)`
once to fetch the live design slice. The response gives every
Aggregate / Command / Event / ReadModel its full **`properties[]`**
list (name + type + isKey + isForeignKey + isRequired) **and** its
existing `implementationFiles[]`. Build an in-memory map
`{elementId → {kind, name, properties, files}}` from this — it's the
source of truth for what each scaffold should contain.

For each unticked checkbox in `tasks.md` (in order from top to
bottom):

1. Parse the task line: extract the task description and the
   `<!-- @robo elementId="..." kind="..." -->` marker (if any).
2. Look up the file path for this element in `plan.md`'s "File
   Layout" section. **Use that exact path — do not invent paths.**
3. Look up the element in the map you built from `get_bc_design`.
   Its `properties[]` is what populates the scaffold. **Do not emit
   an empty `constructor(public readonly id: string)` stub** —
   every property the graph already has must appear in the scaffold
   so the file mirrors the canonical design.

4. Create the file with **real scaffolding driven by the design**:
   - For a `core` BC's **Aggregate** at `entities/<Name>.ts`: emit a
     TypeScript class with one constructor parameter per
     `properties[]` entry. Mark `isKey: true` ones as
     `public readonly`, others as `public`. Map graph types to TS
     types with the same naming style the existing scaffolds use
     (`String` → `string`, `UUID` → `string`, `Object` →
     `object`, `List<Object>` → `object[]`, `Boolean` →
     `boolean`, `Date` / `DateTime` → `Date`, `Long`/`Int` → `number`,
     anything else → keep as-is). Include the `// TODO: invariants`
     placeholder above the constructor.

     Example shape for an aggregate the graph reports with 3
     properties (id [isKey], email, status):

     ```ts
     export class MemberAccount {
       // TODO: invariants
       constructor(
         public readonly id: string,
         public email: string,
         public status: string,
       ) {}
     }
     ```

   - For a **Command** at `usecases/<Name>.ts`: emit a class whose
     `handle(...)` method takes one parameter per property in the
     command's `properties[]`. If the graph reports zero properties,
     emit `handle()` with no params (NOT an arbitrary `id` stub).
   - For an **Event** at `events/<Name>.ts` (when emitted): emit a
     `readonly` class — every property is `public readonly`.
   - For a **ReadModel** at `readmodels/<Name>.ts`: same as Aggregate
     but every property `readonly`.
   - For a **Repository** at
     `frameworks_and_drivers/<Name>Repository.ts`: emit an interface
     `IXxxRepository` with `findById(id: <id-type>)` and
     `save(entity: <Name>)` signatures, then a stub class implementing
     it. Pull the id type from the matching aggregate's id-typed
     property in the design map.
   - Match the architectural layer of the file to the layer's purpose.

5. After the file is created, call MCP
   `register_implementation_files`:

   ```
   register_implementation_files(
       projectId   = <from .claude/robo-project.json>,
       elementId   = <from the @robo marker>,
       files       = [{"path": "<predicted path>", "role": "primary"}],
       mode        = "merge"
   )
   ```

   Choose the `role` based on the layer:
     - `entities/` → `"primary"`
     - `usecases/` → `"primary"`
     - `interface_adapters/` → `"interface-adapter"`
     - `frameworks_and_drivers/` → `"infrastructure"`
     - test files → `"test"`

6. Atomically rewrite the checkbox line in `tasks.md` from `- [ ]` to
   `- [x]` (write-temp-then-rename so a concurrent reader never sees
   a half-written file). Preserve the `@robo` marker exactly.

**If `get_bc_design` returns zero properties for an element, the
graph is genuinely empty for that element.** In that case (and only
that case) it is OK to scaffold `constructor(public readonly id:
string)` as a placeholder, but you MUST surface a warning to the
developer that the element has no design-side properties and they
may want to add them in Robo Architect before continuing.

### Override 3 — never write marker comments into source

Under no circumstances write `// @robo:aggregate=...` or any analogous
annotation into the developer's source files. `/robo-sync` uses full
AST extraction instead (research R7). Marker comments are explicitly
rejected as invasive and formatter-fragile.

### Override 4 — stop on the first blocking task

If a task cannot complete (e.g., ambiguous invariant, missing
information), leave the checkbox unticked and append a short reason
comment on the line below:

```markdown
- [ ] T003 Implement OrderInvariant <!-- @robo elementId="..." kind="Aggregate" -->
  <!-- blocked: invariant declaration is empty in the design -->
```

Then stop and report to the developer. Do not continue to the next
task — blocked items often cascade, and ticking later ones would lie
about the implementation state.

## What this skill does NOT do

- Does NOT regenerate `plan.md` or `tasks.md`.
- Does NOT write tests unless an explicit task asks for one.
- Does NOT push design changes back to the graph — that's
  `/robo-sync`.
- Does NOT scaffold full method bodies. Minimal stubs only; the
  developer fills in business logic.
