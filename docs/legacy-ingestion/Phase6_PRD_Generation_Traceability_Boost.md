# Phase 6 — PRD Generation Traceability Boost PRD

> **작성일**: 2026-05-06 (v1) → 2026-05-06 (v1.1 — `prd_generation/` 코드 deep-dive 결과 반영) → **v1.2 (2026-05-08, 부분 구현)**
> **상태**: **부분 구현됨** (§7 의 Step 1 / 2 / 3 / 4 / 5 / 6 + **7** 완료 — fetch_bc_data + render helpers + generate_bc_spec + generate_claude_md + generate_agent_config + session_id scope wiring). Step 8 (통합 테스트) / 9 (Cursor 수동 검증) 잔여. 구현 status 는 [§7.3 신설](#73-구현-status-2026-05-08) 참조.
> **선결**: Phase 5 v4 ([`Phase5_EventStorming_Promotion_PRD.md`](Phase5_EventStorming_Promotion_PRD.md) §12) 구현 완료. Neo4j 에 traceability 엣지 (SOURCED_FROM / IMPLEMENTS / PROMOTED_TO / ATTACHED_TO + 분석기 HAS_RULE / HAS_EXAMPLE / AFFECTS_TABLE) 영속된 상태가 입력 전제.
>
> **참고**: 본 PRD §3 ~ §6 의 spec markdown 구조는 v1.1 에서 설계한 그대로 [`prd_artifact_generation.py`](../../api/features/prd_generation/prd_artifact_generation.py) 의 render helper + `generate_bc_spec` wiring 으로 구현됨. 다음 작업자는 §7.3 의 잔여 항목에 집중.
> **참조 문서**:
> - `Phase5_EventStorming_Promotion_PRD.md` §5 — 영속된 traceability 엣지 카탈로그
> - `../../../input_resource/2026-04-22-BusinessLogic-노드-구조변경-아키텍트안내.md` — analyzer Rule/Example/Question 신스키마
> - 본 PRD §4 / §5 — 실제 [`prd_generation/`](../../api/features/prd_generation/) 코드 인용 (라인 번호 표시)

이 문서는 사용자가 이벤트 스토밍 캔버스에서 **"PRD 생성"** 트리거 시 실행되는 PRD 생성 파이프라인의 보강 설계를 정의한다. 현재 흐름의 결정적 빈틈 — Phase 5 가 만든 traceability 그래프를 PRD markdown 이 활용하지 않아 분석기 코드 근거 (Rule.statement / Example GWT / source_function / Table) 가 Cursor·Claude Code 입력에 도달하지 않는 문제 — 를 해소해 **바이브 코딩의 input quality** 를 끌어올린다.

핵심 변경:
1. PRD 생성의 BC 데이터 fetch Cypher 를 Phase 5 traceability 엣지를 traverse 하도록 확장
2. Cursor / Claude Code 가 받는 markdown (`specs/{bc_name}_spec.md` 등) 에 **분석기 근거 inline 섹션** 추가 — Rule.statement, Example.given/when_/then_, source_function, AFFECTS_TABLE Table, Question 모두 노드별로 표시
3. PRD 생성 입력 schema 자체를 traceability-aware DTO 로 정리 — 후속 LLM-driven 보강 (예: 코드 근거 기반 Acceptance Criteria 자동 생성) 으로 확장 가능한 토대 제공

---

## §0.1 최신 그래프 스냅샷 보강 (2026-05-09)

> 본 PRD 본문은 v1.2(2026-05-08) 기준으로 작성되었고, 아래는 동일 fixture 계열의 후속 재검증 결과를 반영한 운영 메모다.

### 현재 관계 타입 실측 (PRD fetch 영향)

`db.relationshipTypes()` 기준 확인된 핵심 타입:

- `PROMOTED_TO`
- `SOURCED_FROM`
- `IMPLEMENTS`
- `ATTACHED_TO`
- `HAS_RULE`, `HAS_EXAMPLE`, `AFFECTS_TABLE`

아직 미확인(미영속) 타입:

- `PROMOTED_FROM`
- `DERIVED_FROM`
- `PRECONDITION_BY`
- `GROUNDED_IN`

### 설계-구현 간 해석 정렬

- 본 PRD §4~§5 에 기술된 "심화 traceability 엣지 기반 fetch" 목표는 유지.
- 다만 현시점 구현은 **US gateway fallback traversal** 비중이 높고, 위 심화 엣지는 명시 관계로 영속되지 않은 상태다.
- 따라서 다음 작업자는 "Cypher fallback 유지"와 "심화 엣지 영속화"를 분리된 마일스톤으로 관리하는 것이 안전하다.

### 최신 우선순위 (Step 8~9 + 보강)

1. Step 8 통합 테스트 3시나리오 (full/partial/none analyzer).
2. Step 9 Cursor/Claude 수동 검증.
3. Question attach coverage 개선은 코드 반영 + 최신 세션 실측 확인(1/4 → 4/4, sid=`94b625fe`).
4. 심화 엣지 영속 (`DERIVED_FROM/PRECONDITION_BY/GROUNDED_IN`)은 별도 PR로 분리.

---

## §1 목표 / 비목표

### 목표
- 이벤트 스토밍 노드 (BC / Aggregate / Command / Event / Policy / ReadModel / UserStory) 가 가리키는 분석기 데이터를 **PRD markdown 본문에 전부 inline** — Cursor / Claude Code 가 추적 가능한 단일 input artifact 만들기
- 한 노드 → 그 노드의 source code 근거 (Rule.statement / Example GWT / source_function / Table.column) 를 한 섹션 안에서 한눈에 볼 수 있게 — **컨텍스트 전환 0** (별도 Neo4j query 없이도 충분한 LLM input)
- 신스키마 traceability 엣지를 traverse 하는 **단일 fetch DTO** 정의 — PRD 빌더 / Inspector UI / 향후 PRD diff / regression 도구가 공유
- 구버전 ES 그래프 (Phase 5 이전, traceability 엣지 없는 노드) 도 graceful fallback — 기존 markdown 출력 유지

### 비목표
- LLM 으로 PRD 본문 자체를 새로 생성 (현 markdown 빌더는 결정론. 본 PRD 도 결정론 layer 만 보강)
- Cursor 의 `.cursorrules` / Claude Code 의 `.claude/skills/*` 형식 변경 (입력 schema 만 풍부하게)
- 코드 자동 생성 (PRD 가 input 이지만 output 은 사용자가 Cursor / Claude 에 던짐)

### 트리거
- **수동 유지** — `POST /api/prd/generate` (BC 목록 반환), `POST /api/prd/download` (ZIP 일괄). 본 PRD 가 보강하는 건 그 안의 markdown 빌더와 fetch 단계만

---

## §2 입력 계약 — 현재 영속된 traceability 그래프

Phase 5 promote-to-es 완료 후 Neo4j 가 carry 하는 입력 (zapamcom10060 정상 분석기 데이터 기준 실측):

| 노드 / 엣지 | 카운트 (예시) | PRD 가 가져와야 할 정보 |
|---|---|---|
| `BoundedContext` | 2~5 | name, displayName, description, rationale, domainType |
| `(BC)-[:HAS_USERSTORY]->(UserStory)` | N×US | BC 별 US 군집 |
| `(BC)-[:HAS_AGGREGATE]->(Aggregate)` | N×Agg | BC 별 Aggregate 군집 |
| `(BC)-[:HAS_POLICY]->(Policy)` | N×Pol | BC 별 자동화 정책 |
| `(BC)-[:HAS_READMODEL]->(ReadModel)` | N×RM | BC 별 조회 모델 |
| `(Aggregate)-[:HAS_COMMAND]->(Command)` | M×Cmd | Aggregate 별 명령 |
| `(Command)-[:EMITS]->(Event)` | K×Evt | Command 별 발행 이벤트 |
| `(Aggregate)-[:GROUNDED_IN]->(Table)` | N | Aggregate 의 root DB 테이블 + 컬럼 |
| `(Aggregate)-[:DERIVED_FROM]->(Rule)` | N×R | Aggregate invariant 의 코드 근거 (Rule.statement) |
| `(Command)-[:PRECONDITION_BY]->(Rule)` | M×R | Command guard chain (statement 들) |
| `(Event)-[:DERIVED_FROM]->(Example)` | K | Event 의 acceptance test (Example.given/when_/then_) |
| `(UserStory)-[:SOURCED_FROM]->(Rule)` | US×R | US 본문 구성한 BL 들 |
| `(any_es)-[:IMPLEMENTS]->(UserStory)` | many | 다운스트림 ES 가 어느 US 를 실현하는지 |
| `(any_es)-[:PROMOTED_FROM]->(BpmTask)` | many | BPM Task 출처 |
| `(Question)-[:ATTACHED_TO]->(BoundedContext)` | Q | 검토 대기 정책 질문 |
| `Rule` (analyzer) — `statement`, `given`, `when`, `then`, `source_function`, `local_id` | 59 | 비즈니스 규칙 한 줄 + 대표 GWT |
| `Example` (analyzer) — `given`, `when_`, `then_`, `is_boundary`, `description` | 87 | 구체 시나리오 (boundary case 포함) |
| `Table` (analyzer) — `name` + `(:HAS_COLUMN)->(:Column {name, dtype, is_primary_key})` | 2 | DB 스키마 |
| `FUNCTION` (analyzer) — `function_id`, `procedure_name`, `summary`, `code_text`, `start_line`, `end_line`, `file_path` | 17 | 원본 코드 위치 |

> **문서/노트** 는 현재 PRD markdown 에 들어있지만 분석기 추적 정보는 없는 상태. 이 PRD 가 채울 영역.

---

## §2.1 Phase 5 노드 속성 ↔ PRD 빌더 기대 dict 의 gap

> **중요한 발견**: 현재 `prd_artifact_generation.py:generate_bc_spec()` 은 **legacy ES phase (workflow runner) 가 만들던 풍부한 노드 속성** 을 기대한다. Phase 5 신 파이프라인은 그 속성들을 set 하지 않으므로, 분석기 데이터가 정상이라도 PRD 출력에 빈 섹션이 다수 생긴다. Phase 6 는 traceability 엣지 추가뿐 아니라 **이 gap 도 메워야** 한다.

### 2.1.1 Aggregate 노드 — 큰 gap

| 빌더 기대 키 ([generate_bc_spec:570-617](../../api/features/prd_generation/prd_artifact_generation.py#L570)) | Phase 5 set 함? | gap 메우기 전략 |
|---|---|---|
| `id`, `name`, `displayName` | ✅ | — |
| `rootEntity` | ❌ (Phase 5 는 `rootTable` 만 set) | `rootTable` 로 fallback 또는 LLM 명명 |
| `invariants: list[str]` | ❌ | **DERIVED_FROM Rule.statement 들의 collect 가 곧 invariants** |
| `enumerations: list[{name, values}]` | ❌ | legacy phase 산출. Phase 6 범위 외 — 빈 list 허용 |
| `valueObjects: list[{name}]` | ❌ | 동일 — 빈 list 허용 |
| `properties[]: [{id, name, displayName, type, isKey, isForeignKey, fkTargetHint, description}]` | ❌ (Phase 5 는 `Property` 노드 만들지 않음) | **GROUNDED_IN Table.HAS_COLUMN 으로 자동 채움** — `col.name → properties[].name`, `col.dtype → type`, `col.is_primary_key → isKey` |
| `commands[]`, `events[]` (nested) | ✅ (Phase 5 가 Aggregate-HAS_COMMAND-Command-EMITS-Event chain set) | — |

### 2.1.2 Command 노드 — 중간 gap

| 빌더 기대 키 ([generate_bc_spec:585-602](../../api/features/prd_generation/prd_artifact_generation.py#L585)) | Phase 5 set 함? | gap 메우기 |
|---|---|---|
| `id`, `name`, `displayName`, `actor` | ✅ | — |
| `category` | ❌ | "Create"/"Update"/"Delete"/"Query" 자동 추론 (Phase 5 가 Command 가 EMITS Event 의 writeOp 로 결정 가능) |
| `inputSchema: str (JSON)` | ❌ | **PRECONDITION_BY Rule 들의 source_function 의 input parameter 추출** — 또는 빈 schema 허용 |
| `description` | ❌ | Rule.statement 첫 줄 또는 displayName 그대로 |
| `properties[]` | ❌ | Phase 6 가 LLM 호출로 생성하거나 (out-of-scope) skip |

### 2.1.3 Event 노드 — 중간 gap

| 빌더 기대 키 ([generate_bc_spec:597-617](../../api/features/prd_generation/prd_artifact_generation.py#L597)) | Phase 5 set 함? | gap 메우기 |
|---|---|---|
| `id`, `name`, `displayName` | ✅ | — |
| `version` | ❌ | 기본 `"v1"` |
| `schema: str (JSON)` | ❌ | DERIVED_FROM Example.then_ JSON 의 writes[] 그대로 |
| `description` | ❌ | Rule.statement 으로 fallback |
| `properties[]` | ❌ | Example.then_ JSON 의 writes[] → `[{name: table.column, type: dtype}]` |

### 2.1.4 UI / GWT — legacy phase 가 만들고 Phase 6 는 fetch 시 활용

> **변경 이력 v1.1 → v1.2**: Phase 5 가 augment-only 로 전환됨 (인계 문서 v2 참조). Phase 5 는 ES 노드를 더 이상 생성/wipe 하지 않으며, **legacy ES phase 가 만든 UserStory / Aggregate / Command / Event / Policy / ReadModel / GWT / UI 를 그대로 보존**한다. 따라서 GWT 영속을 신 파이프라인에 넣자던 v1.1 결정은 폐기 — legacy GWT 활용 + 분석기 Example 보강의 두 트랙으로 정리.

#### UI Wireframe — legacy 결과 그대로

- legacy phase 가 LLM 으로 HTML template 생성. 분석기 데이터로 추출 불가능
- Phase 6 fetch_bc_data 가 기존대로 `(BC)-[:HAS_UI]->(UI)` 그대로 traverse — 변경 없음
- 매 promote-to-es 시 legacy 가 새 UI 만들고 augment-only Phase 5 가 sid 만 부착 (wipe 안 함). 누적 방지는 사용자 명시 reset 시 `clear_promoted_nodes` 가 처리 (UI 라벨도 ALL_PROMOTED_LABELS 에 포함)

#### GWT — 두 출처 합집합 (legacy 결과 + 분석기 Example)

- **legacy GWT** (LLM 기반): 이미 `(Command/Policy)-[:HAS_GWT]->(GWT)` 로 영속. Phase 6 fetch_bc_data 의 Step 8 이 그대로 traverse
- **분석기 Example GWT** (결정론, 신규): 매핑된 task → REALIZED_BY shadow Rule → 분석기 Rule.HAS_EXAMPLE → Example 의 `given / when_ / then_ / is_boundary / writes` 풀 활용. legacy GWT 가 미생성한 케이스 또는 boundary case 보완용
- **Phase 6 fetch 시점에 둘 다 표면화**:
  ```cypher
  // legacy GWT
  OPTIONAL MATCH (parent)-[:HAS_GWT]->(gwt:GWT)
  // analyzer Example (보완)
  OPTIONAL MATCH (us:UserStory)-[:SOURCED_FROM]->(r:Rule)-[:HAS_EXAMPLE]->(ex:Example)
  WITH gwt, ex,
       coalesce(gwt.givenRef, ex.given) AS given,
       coalesce(gwt.whenRef, ex.when_) AS when_,
       coalesce(gwt.thenRef, ex.then_) AS then_
  ```
- 결과: PRD spec markdown 의 GWT 섹션이 legacy 우선 + 분석기 fallback. 둘 다 없으면 섹션 자동 생략

#### 통합 결정

| 라벨 | Phase 5 동작 | Phase 6 fetch 동작 | 결과 |
|---|---|---|---|
| UI | sid 태깅만 (보존) | 기존 `(BC)-[:HAS_UI]->(UI)` 그대로 | legacy LLM HTML template 그대로 |
| GWT | sid 태깅만 (보존) | legacy `(parent)-[:HAS_GWT]->(GWT)` + 분석기 Example fallback | LLM GWT + 분석기 결정론 GWT 합집합 |

신 파이프라인은 어떤 ES 노드도 영속/wipe 하지 않음. `ALL_PROMOTED_LABELS` 와 `clear_promoted_nodes` 는 사용자 명시 `/reset` 호출 시에만 사용.

### 2.1.5 가장 중요 — invariants 자동 채우기

`generate_bc_spec()` 의 Aggregate 섹션 ([line 575](../../api/features/prd_generation/prd_artifact_generation.py#L575)) 이 `agg.invariants` 가 비면 "Invariants" 줄 자체를 안 만든다. Phase 6 의 fetch_bc_data Cypher 가:

```cypher
OPTIONAL MATCH (agg)-[:DERIVED_FROM]->(invR:Rule)
WITH agg, ..., collect(DISTINCT invR.title) AS derived_invariants
WITH agg { ..., invariants: coalesce(agg.invariants, []) + derived_invariants } AS agg ...
```

처럼 합집합으로 채우면 빌더 수정 0줄로 invariants 표시.

---

## §2.2 PRD 출력 artifact 카탈로그 (실제 19종)

[`routes/prd_export.py:148-206`](../../api/features/prd_generation/routes/prd_export.py#L148) 가 ZIP 으로 묶는 파일 전체. Phase 6 가 traceability 정보를 inject 할 후보 열거:

| 파일 | 빌더 함수 ([line](../../api/features/prd_generation/prd_artifact_generation.py)) | 조건 | traceability inject 우선순위 |
|---|---|---|---|
| `PRD.md` | `generate_main_prd()` ([8-499](../../api/features/prd_generation/prd_artifact_generation.py#L8)) | 항상 | ⭐⭐⭐ 최우선 — BC 헤더 표에 `derived_rule_count` 추가 |
| `specs/{bc}_spec.md` | `generate_bc_spec()` ([550-807](../../api/features/prd_generation/prd_artifact_generation.py#L550)) | 각 BC | ⭐⭐⭐ 최우선 — Aggregate Invariants / Command Preconditions / Event GWT / Open Decisions 모두 |
| `CLAUDE.md` | `generate_claude_md()` ([810-839](../../api/features/prd_generation/prd_artifact_generation.py#L810)) | Claude 만 | ⭐⭐ — BC 목록 옆에 `(N rules / M questions)` |
| `.claude/agents/{bc}_agent.md` | `generate_agent_config()` ([1920-2085](../../api/features/prd_generation/prd_artifact_generation.py#L1920)) | Claude×BC | ⭐⭐ — BC 별 agent 가 알아야 할 핵심 invariants top-5 |
| `.claude/skills/eventstorming-implementation.md` | `generate_claude_skill_eventstorming_implementation()` ([1508-1648](../../api/features/prd_generation/prd_artifact_generation.py#L1508)) | Claude | ⭐ — generic. inject 안 해도 OK |
| `.cursorrules` | `generate_cursor_rules()` ([842-951](../../api/features/prd_generation/prd_artifact_generation.py#L842)) | 항상 | ⭐ — generic |
| `.cursor/rules/*.mdc` (4~7개) | 각 generator | Cursor | ⭐ — generic |
| `Frontend-PRD.md` | `generate_frontend_prd()` ([2098+](../../api/features/prd_generation/prd_artifact_generation.py#L2098)) | include_frontend | ⭐⭐ — UI Wireframe 옆 ReadModel.SOURCED_FROM Rule list |
| `README.md` | `generate_readme()` | 항상 | — |
| `docker-compose.yml`, `Dockerfile` | docker generators | include_docker | — |

> **§3 의 출력 schema** 는 위 표의 ⭐⭐⭐ / ⭐⭐ 를 모두 채운 모습이다.

---

## §3 출력 schema — 보강된 PRD markdown 구조

`specs/{bc_name}_spec.md` 한 파일 안의 섹션을 보강. 현재 항목은 유지하고 **분석기 근거 섹션**을 노드별로 추가.

### 3.1 BoundedContext 헤더 (현행 유지 + 1개 추가)

```markdown
# Bounded Context: {bc.displayName}

- **Name (slug)**: `{bc.name}`
- **Domain Type**: {bc.domainType}
- **Description**: {bc.description}
- **Rationale**: {bc.rationale}

## Open Decisions (정책 검토 대상)        ← 신규 섹션
- **Q1 (host fn `{q.host_function}`)**: {q.text}
  - Reason: {q.reason}
- **Q2** ...
```

> Question 노드를 ATTACHED_TO 엣지로 가져와 BC 헤더 직후 노출. 정책 결정 미해결 항목을 PRD 입력에 명시 → Cursor / Claude 가 "이건 사용자 결정 필요" 인식 가능.

### 3.2 Aggregate 섹션 보강

```markdown
## Aggregate: {agg.displayName} (`{agg.name}`)

### Root Table (분석기 grounded)         ← 신규
- **Table**: `{table.name}` ({컬럼 N개})
  - `{col.name}`: {col.dtype}{ " 🔑 PK" if col.is_primary_key }
  - ...

### Invariants (코드 근거)                ← 신규
| seq | Rule.statement | host function | given | when | then |
|---|---|---|---|---|---|
| R3 | "인증이력을 INSERT 한다" | `b000_main_proc` | acnt_num=N | 인증 성공 | 이력 행 추가 |
| R5 | "..." | ... | ... | ... | ... |

### Lifecycle Events
- `{event.name}` ({event.displayName}) — write op `{event.writeOp}` on `{event.targetTable}`
  - Source Example: `{example.example_id}` (boundary={is_boundary})
    - Given: `{example.given}`
    - When: `{example.when_}`
    - Then: `{example.then_}`
```

> Aggregate 섹션의 "Invariants" 표는 `(Aggregate)-[:DERIVED_FROM]->(Rule)<-[hr:HAS_RULE]-(f:FUNCTION)` traverse 결과. seq 는 `hr.local_id`. PRD-input 으로 Cursor 가 받으면 Aggregate 의 invariant 코드를 작성할 때 그대로 인용 가능.

### 3.3 Command 섹션 보강

```markdown
## Command: {cmd.displayName} (`{cmd.name}`)

- **Aggregate**: {agg.displayName}
- **Actor**: {cmd.actor}
- **Branch**: {cmd.branch_local_id or 'main'}

### Preconditions (코드 근거)            ← 신규
| seq | Rule.statement | host function |
|---|---|---|
| R1 | "청구번호가 0이면 오류로 종료한다" | `a000_input_validation` |
| R2 | "업무구분이 공백이면 오류로 종료한다" | `a000_input_validation` |
| ... | ... | ... |

### Emits Events
- `{event.name}` (op={op}, table={table})
```

### 3.4 Event 섹션 보강

```markdown
## Event: {event.displayName} (`{event.name}`)

- **Write op**: `{event.writeOp}` on Table `{event.targetTable}`
- **Sequence within command**: `{event.sequenceWithinCommand}`

### Acceptance test (Example GWT)         ← 신규
- **Example id**: `{example.example_id}`
- **Boundary case**: `{example.is_boundary}`
- **Given**: {example.given}
- **When**: {example.when_}
- **Then**: {example.then_}

### Source code                           ← 신규
- **Function**: `{function.procedure_name}` ({function.file_path}:{function.start_line}-{function.end_line})
- **Function summary**: {function.summary}
```

### 3.5 ReadModel 섹션 보강

```markdown
## ReadModel: {rm.displayName} (`{rm.name}`)

### Source rules (read-only)              ← 신규
| seq | Rule.statement | host function |
|---|---|---|
| ... | ... | ... |

### Source tables                         ← 신규
- `{table.name}` ({access})
```

### 3.6 Policy 섹션 보강

```markdown
## Policy: {pol.name}

- **Description**: {pol.description}
- **Kind**: {pol.kind}  (`per_fn` / `cross_bc` / `same_bc_reactive`)

### Trigger / Invoke
- Trigger Event: {trigger_event.name} ({source_bc.displayName})
- Invoke Command: {invoke_command.name} ({target_bc.displayName})

### Coupled domains (cross-BC 영향)       ← 신규
- {coupled_domain[0]}, {coupled_domain[1]}, ...

### Source rule
- **Rule.statement**: "{rule.statement}"
- **Function**: `{function.procedure_name}`
```

### 3.7 UserStory 인덱스 (BC 헤더 직후) — 보강

```markdown
## User Stories — code-traced

| US id | role | action | source rules (count) | implements |
|---|---|---|---|---|
| {us.id} | {us.role} | {us.action} | {len(sourced_rules)} ({fn1,fn2,...}) | Aggregate, Cmd, Event |
| ... | ... | ... | ... | ... |
```

> US 별로 SOURCED_FROM 개수 + IMPLEMENTS 받는 다운스트림 노드 수 한 줄 — Cursor 가 "이 US 가 무엇을 만드는지" 한눈에.

---

## §4 데이터 fetch — 보강 패치 (실제 8-step Cypher 위에 4 단계 inject)

[`prd_model_data.py:fetch_bc_data()`](../../api/features/prd_generation/prd_model_data.py#L9) 는 이미 **Step 1 ~ Step 8** 의 풍부한 traverse 를 보유 (Aggregate Properties / Commands / Events / ReadModel / Policy / UI / GWT). Phase 6 는 그 위에 **추가 4 단계**를 inject — 기존 RETURN dict 의 키 동일, 새 필드만 nested.

### 4.1 inject 위치 + 신 절

> 중요: 기존 빌더가 기대하는 키 (e.g. `agg.invariants`, `agg.properties[]`, `cmd.description`) 를 **신 절이 자동 채움**. 빌더 수정 최소화.

#### inject A — Aggregate 의 invariants/properties 자동 채우기 ([Step 1 ~ Step 4 사이](../../api/features/prd_generation/prd_model_data.py#L14-L73))

기존 Step 1 (`OPTIONAL MATCH (agg)-[:HAS_PROPERTY]->(aggProp:Property)`) **다음에** 추가:

```cypher
// inject A.1 — DERIVED_FROM Rule 들을 invariants 로 자동 채움
OPTIONAL MATCH (agg)-[:DERIVED_FROM]->(invR:Rule)
OPTIONAL MATCH (invF:FUNCTION)-[invHR:HAS_RULE]->(invR)
WITH bc, agg, aggProps,
     collect(DISTINCT {
       seq: invHR.local_id,
       statement: invR.title,
       fn: coalesce(invF.procedure_name, invF.name),
       given: invR.given, when_: invR.when, then: invR.then
     }) AS derivedInvariants

// inject A.2 — GROUNDED_IN Table 의 컬럼 → properties 자동 채움 (Phase 5 가 Property 미생성 시 fallback)
OPTIONAL MATCH (agg)-[:GROUNDED_IN]->(tbl:Table)
OPTIONAL MATCH (tbl)-[:HAS_COLUMN]->(col:Column)
WITH bc, agg, aggProps, derivedInvariants,
     tbl,
     collect(DISTINCT {
       id: col.name, name: col.name, displayName: col.name,
       type: coalesce(col.dtype, 'STRING'),
       isKey: coalesce(col.is_primary_key, false),
       isForeignKey: false, fkTargetHint: '', description: coalesce(col.description, '')
     }) AS columnProps
```

그 후 Step 4 의 Aggregate collect 시 ([line 50-73](../../api/features/prd_generation/prd_model_data.py#L50)) 변경:

```cypher
WITH bc, collect(DISTINCT {
    id: agg.id, name: agg.name, displayName: agg.displayName,
    rootEntity: coalesce(agg.rootEntity, agg.rootTable),                    // ← rootTable fallback
    invariants: coalesce(agg.invariants, []) + [d IN derivedInvariants WHERE d.statement IS NOT NULL | d.statement],
                                                                            // ← Phase 5 가 invariants 미생성 시 Rule.statement 들이 채움
    derivedInvariantsDetail: derivedInvariants,                             // ← 신규: spec 표 렌더용 (statement / fn / GWT)
    enumerations: agg.enumerations, valueObjects: agg.valueObjects,
    properties: CASE WHEN size(aggProps) > 0 THEN aggProps ELSE columnProps END,
                                                                            // ← Property 미생성 시 컬럼으로 자동
    rootTable: { name: tbl.name, columns: columnProps },                    // ← 신규: GROUNDED_IN Table 정보
    commands: commands, events: events
}) AS aggData
```

#### inject B — Command 의 description / preconditions 채우기 ([Step 2](../../api/features/prd_generation/prd_model_data.py#L25-L31))

기존 Step 2 직후:

```cypher
// inject B.1 — PRECONDITION_BY Rule 들을 preconditions 표로
OPTIONAL MATCH (cmd)-[:PRECONDITION_BY]->(precR:Rule)
OPTIONAL MATCH (precF:FUNCTION)-[precHR:HAS_RULE]->(precR)
WITH bc, agg, aggProps, cmd, cmdProps,
     coalesce(cmd.description,
              head([precR.title]) +                                         // ← 첫 precondition statement 를 description fallback
              CASE WHEN size(collect(DISTINCT precR)) > 1 THEN ' (외 N건)' ELSE '' END
     ) AS cmdDescription,
     collect(DISTINCT {
       seq: precHR.local_id, statement: precR.title,
       fn: coalesce(precF.procedure_name, precF.name)
     }) AS preconditions
```

cmd 컬렉션에 `preconditions` 필드 추가 ([line 37-43](../../api/features/prd_generation/prd_model_data.py#L37)):

```cypher
collect(DISTINCT {
    id: cmd.id, name: cmd.name, displayName: cmdDisplayName, actor: cmd.actor,
    category: coalesce(cmdCategory, 'Update'),                             // ← fallback
    inputSchema: coalesce(cmdInputSchema, '{}'),                           // ← fallback
    description: cmdDescription, properties: cmdProps,
    preconditions: [p IN preconditions WHERE p.statement IS NOT NULL]      // ← 신규
}) as commands,
```

#### inject C — Event 의 description / acceptance test 채우기 ([Step 3](../../api/features/prd_generation/prd_model_data.py#L33-L41))

기존 Step 3 직후:

```cypher
// inject C — DERIVED_FROM Example 을 acceptance test + schema fallback
OPTIONAL MATCH (evt)-[:DERIVED_FROM]->(canonEx:Example)
WITH bc, agg, aggProps, cmd, cmdProps, ..., evt, evtProps, evtSchema,
     coalesce(evtDescription, evt.name + ' 발행됨') AS evtDescription2,
     {
       id: canonEx.example_id, given: canonEx.given,
       when_: canonEx.when_, then_: canonEx.then_,
       boundary: canonEx.is_boundary
     } AS acceptanceTest
```

evt 컬렉션에 `acceptanceTest` 추가:

```cypher
collect(DISTINCT {
    id: evt.id, name: evt.name, displayName: evtDisplayName,
    version: coalesce(evt.version, 'v1'), schema: coalesce(evtSchema, '{}'),
    description: evtDescription2, properties: evtProps,
    writeOp: evt.writeOp, targetTable: evt.targetTable,                    // ← 신규
    acceptanceTest: acceptanceTest                                          // ← 신규
}) as events
```

#### inject D — UserStory + Question + ATTACHED_TO ([Step 8 후, RETURN 직전](../../api/features/prd_generation/prd_model_data.py#L122-L134))

```cypher
// inject D.1 — UserStory + sourced rules
OPTIONAL MATCH (bc)-[:HAS_USERSTORY]->(us:UserStory)
OPTIONAL MATCH (us)-[:SOURCED_FROM]->(usR:Rule)
OPTIONAL MATCH (us)-[:PROMOTED_FROM]->(usT:BpmTask)
WITH bc, aggData, rmData, polData, uiData, gwtData,
     collect(DISTINCT {
       id: us.id, role: us.role, action: us.action,
       source: us.source, task_id: usT.id, sequence: us.sequence,
       sourceRules: collect(DISTINCT {
         id: usR.id, statement: usR.title, fn: usR.source_function
       })
     }) AS userStoryData

// inject D.2 — ATTACHED_TO Question (Open Decisions)
OPTIONAL MATCH (q:Question)-[:ATTACHED_TO]->(bc)
OPTIONAL MATCH (q)-[:RAISED_IN]->(qF:FUNCTION)
WITH bc, aggData, rmData, polData, uiData, gwtData, userStoryData,
     collect(DISTINCT {
       id: q.question_id, text: q.text, reason: q.reason,
       host_function: coalesce(qF.procedure_name, qF.name)
     }) AS questionData
```

기존 RETURN ([line 124-134](../../api/features/prd_generation/prd_model_data.py#L124)) 에 4개 키 추가:

```cypher
RETURN {
    id: bc.id, name: bc.name, displayName: bc.displayName, description: bc.description,
    rationale: bc.rationale,                          // ← 신규
    domainType: bc.domainType,                        // ← 신규
    aggregates: [a IN aggData WHERE a.id IS NOT NULL],
    readmodels: [r IN rmData WHERE r.id IS NOT NULL],
    policies: [p IN polData WHERE p.id IS NOT NULL],
    uis: [u IN uiData WHERE u.id IS NOT NULL],
    gwts: [g IN gwtData WHERE g.id IS NOT NULL],
    userStories: [u IN userStoryData WHERE u.id IS NOT NULL],   // ← 신규
    questions: [q IN questionData WHERE q.id IS NOT NULL]       // ← 신규
} as bc_data
```

### 4.2 session_id 필터링 (multi-session 충돌 방지)

현재 `fetch_bc_data($bc_id)` 는 bc_id 만 사용. 같은 BC 가 여러 session 에 존재 시 (예: 사용자가 promote-to-es 두 번 → 신 BC + 기존 BC manual edited 잔존) cross-session traverse 위험.

**보강**: 함수 시그니처에 `session_id: str | None = None` 추가:

```python
def fetch_bc_data(bc_id: str, session_id: str | None = None) -> dict | None:
    sid_filter = "AND coalesce(bc.session_id, '') = $sid" if session_id else ""
    query = f"MATCH (bc:BoundedContext {{id: $bc_id}}) {sid_filter} ..."
    ...
```

`get_bcs_from_nodes(node_ids, session_id=None)` 도 마찬가지. router 의 `/generate`, `/download` endpoint 가 request body 에 `session_id` 추가 받음.

### 4.3 가벼운 fallback — 분석기 데이터 부재 시

Phase 5 의 shadow Rule 만 있고 analyzer 가 비었을 때 (현 zapamcom10060 mapping 깨진 상태) Cypher 의 `MATCH (invF:FUNCTION)-[invHR:HAS_RULE]->(invR)` 가 0건. 그 경우 derivedInvariants 가 비어 — invariants 도 비어 — 빌더가 "Invariants" 섹션 자체 생략. 정합 OK.

추가로 shadow Rule 만으로도 statement 보유. fallback 절:

```cypher
OPTIONAL MATCH (us:UserStory)-[:SOURCED_FROM]->(shR:Rule {session_id: bc.session_id})
WHERE NOT (:FUNCTION)-[:HAS_RULE]->(shR)   // analyzer 매칭 실패한 shadow only
WITH ..., collect(DISTINCT shR.title) AS shadowOnlyStatements
```

shadowOnlyStatements 도 invariants 합집합에 포함하면 분석기 데이터 부재 케이스도 커버. 단 source_function / fn 정보는 shadow Rule.source_function 으로.



### 4.2 Python DTO

```python
# api/features/prd_generation/prd_model_data.py — 새 DTO 정의

class TracedRuleRef(TypedDict):
    seq: str | None       # HAS_RULE.local_id
    statement: str | None # Rule.title
    fn: str | None        # source FUNCTION.procedure_name
    given: str | None     # Rule.given (representative)
    when_: str | None
    then: str | None

class TracedExample(TypedDict):
    id: str | None
    given: str | None
    when_: str | None
    then_: str | None
    boundary: bool

class TracedAggregate(TypedDict):
    # legacy fields
    id: str
    name: str
    displayName: str
    rootTable: str | None
    memberFunctions: list[str]
    # NEW — Phase 6 traceability
    table: dict | None         # {name, columns: [{name, dtype, pk}]}
    invariants: list[TracedRuleRef]

class TracedCommand(TypedDict):
    id: str
    name: str
    displayName: str
    actor: str
    branch: str | None
    aggregate_key: str
    implements_us: str | None
    preconditions: list[TracedRuleRef]    # NEW
    emits: list[dict]                      # event + canonical example   # NEW

# (similar shapes for ReadModel, Policy, UserStory)
```

> 이 DTO 들은 `prd_artifact_generation.py` 의 markdown 빌더에 직접 입력. legacy fetch 결과와 동일 키 (id/name/displayName) 보존하므로 기존 빌더는 수정 없이 동작 → 신 섹션만 추가.

---

## §5 markdown builder 보강 — 실제 라인별 inject

§4 의 Cypher 보강만으로 `agg.invariants` / `cmd.preconditions` / `evt.acceptanceTest` / `bc.questions` / `bc.userStories` 가 dict 에 이미 들어옴. **빌더 함수의 핵심 보강은 새 섹션 5개 추가**.

### 5.1 `generate_bc_spec()` ([line 550-807](../../api/features/prd_generation/prd_artifact_generation.py#L550))

기존 spec 구조 ([실제 출력 예시 §6.2 참조]) 안에 다음 위치에 inject:

| 신 섹션 | inject 위치 (line) | 호출 헬퍼 | 조건 |
|---|---|---|---|
| **Open Decisions** (BC 헤더 직후) | 569 직후 | `render_open_decisions(bc.questions)` | `len(bc.questions) > 0` |
| **User Stories — code-traced** | Open Decisions 직후 | `render_user_stories_index(bc.userStories)` | `len(bc.userStories) > 0` |
| **Aggregate Root Table schema** | 575 ("Root Entity:" 줄) 직후 | `render_aggregate_table_schema(agg.rootTable)` | `agg.rootTable.name` |
| **Aggregate Invariants 표** | 576 ("Invariants:" 직후) 의 list 대체 | `render_invariants_table(agg.derivedInvariantsDetail)` | `len(...) > 0`, 비면 기존 list 사용 |
| **Command Preconditions 표** | 591 (Command 의 Description 직후) | `render_command_preconditions(cmd.preconditions)` | `len(...) > 0` |
| **Event Acceptance Test** | 612 (Event 의 schema 직후) | `render_event_acceptance_test(evt.acceptanceTest)` | `evt.acceptanceTest.given` |

> 각 헬퍼는 `len == 0` / 핵심 키 None 일 때 빈 문자열 반환 → spec 깔끔.

### 5.2 헬퍼 함수 signature

```python
# api/features/prd_generation/prd_artifact_generation.py 에 신 섹션으로 추가

def render_open_decisions(questions: list[dict]) -> str:
    if not questions: return ""
    out = "\n## Open Decisions (정책 검토 필요)\n\n"
    for q in questions:
        out += f"> ⚠️ **Q (host fn `{q['host_function']}`)**: {q['text']}\n"
        out += f"> - Reason: {q.get('reason', '')}\n\n"
    return out

def render_user_stories_index(user_stories: list[dict]) -> str:
    if not user_stories: return ""
    out = "\n## User Stories — code-traced\n\n"
    out += "| US id | role | action | source rules | source |\n"
    out += "|---|---|---|---|---|\n"
    for us in user_stories:
        rule_count = len(us.get("sourceRules", []))
        fns = sorted({r.get("fn") for r in us.get("sourceRules", []) if r.get("fn")})
        fn_str = f" ({', '.join(list(fns)[:3])}{'…' if len(fns) > 3 else ''})" if fns else ""
        out += f"| {us['id']} | {us.get('role','')} | {us.get('action','')[:60]} | {rule_count}{fn_str} | {us.get('source','')} |\n"
    return out

def render_aggregate_table_schema(table: dict) -> str:
    if not table or not table.get("name"): return ""
    out = f"\n#### Root Table (분석기 grounded)\n- **Table**: `{table['name']}`\n"
    cols = table.get("columns") or []
    if cols:
        out += "  - Columns:\n"
        for c in cols:
            pk = " 🔑" if c.get("isKey") else ""
            out += f"    - `{c['name']}`: {c.get('type','')}{pk}\n"
    return out

def render_invariants_table(invariants_detail: list[dict]) -> str:
    if not invariants_detail: return ""
    out = "\n#### Invariants (코드 근거)\n\n"
    out += "| seq | Rule.statement | host fn | given | when | then |\n"
    out += "|---|---|---|---|---|---|\n"
    for inv in invariants_detail:
        out += (f"| {inv.get('seq','')} | {inv.get('statement','')[:80]} | "
                f"`{inv.get('fn','')}` | {(inv.get('given','') or '')[:40]} | "
                f"{(inv.get('when_','') or '')[:40]} | {(inv.get('then','') or '')[:40]} |\n")
    return out

def render_command_preconditions(preconds: list[dict]) -> str:
    if not preconds: return ""
    out = "\n  - **Preconditions (코드 근거)**:\n\n"
    out += "    | seq | Rule.statement | host fn |\n"
    out += "    |---|---|---|\n"
    for p in preconds:
        out += f"    | {p.get('seq','')} | {p.get('statement','')[:80]} | `{p.get('fn','')}` |\n"
    return out

def render_event_acceptance_test(test: dict) -> str:
    if not test or not test.get("given"): return ""
    boundary = " (boundary case)" if test.get("boundary") else ""
    return (f"\n  - **Acceptance Test**{boundary}:\n"
            f"    - **Given**: {test.get('given','')}\n"
            f"    - **When**: {test.get('when_','')}\n"
            f"    - **Then**: {test.get('then_','')}\n")
```

### 5.3 `generate_main_prd()` ([line 8-499](../../api/features/prd_generation/prd_artifact_generation.py#L8))

BC 요약 표 ([line 75 부근](../../api/features/prd_generation/prd_artifact_generation.py#L75)) 에 컬럼 2개 추가:

```python
# 기존: | BC Name | Aggregates | Commands | Events | ReadModels | Policies | UIs |
# 신:  | ... | Source Rules | Open Questions |   ← 추가

source_rules_count = sum(len(us.get("sourceRules", [])) for us in bc.get("userStories", []))
question_count = len(bc.get("questions", []))
```

### 5.4 `generate_claude_md()` ([line 810-839](../../api/features/prd_generation/prd_artifact_generation.py#L810))

BC 목록 줄 ([line 825 부근](../../api/features/prd_generation/prd_artifact_generation.py#L825)) 에 traceability 통계 한 줄:

```python
# 기존: - BC: {name} ({id})
# 신:   - BC: {name} ({id}) — {agg_count} aggregates, {rule_count} traced rules, {q_count} open questions
```

### 5.5 `generate_agent_config()` ([line 1920-2085](../../api/features/prd_generation/prd_artifact_generation.py#L1920))

BC 별 agent 가 알아야 할 핵심 invariants top-5 + open questions 섹션 추가 — Aggregates 섹션 ([line 1980 부근](../../api/features/prd_generation/prd_artifact_generation.py#L1980)) 다음:

```python
out += "\n## Critical Invariants (top 5 by frequency)\n"
top_invariants = sorted(
    [(inv['statement'], inv['fn']) for agg in bc['aggregates'] for inv in agg.get('derivedInvariantsDetail', [])],
    key=lambda x: x[0]
)[:5]
for stmt, fn in top_invariants:
    out += f"- `{fn}`: {stmt}\n"

if bc.get("questions"):
    out += "\n## Open Decisions — handle these only with user confirmation\n"
    for q in bc["questions"]:
        out += f"- {q['text']} (host fn: `{q['host_function']}`)\n"
```

### 5.6 length 제한 + Cursor / Claude 친화 포맷

- 한 BC 의 spec 평균 추정: 5 Aggregate × 3 invariant + 9 Command × 5 precond + 14 Event × 1 GWT ≈ 250~400 줄. Cursor/Claude single-file context 한도 안전
- 30+ Aggregate 모놀리스 (예외 fixture) 시: spec 분할 옵션 (`specs/{bc}/{agg}.md`) — 후속 §8
- 코드 식별자는 모두 백틱: function 이름, Table.column, Rule.local_id (예: `R3`)
- Acceptance Test GWT 는 `**Given**` / `**When**` / `**Then**` 굵기 — Cursor/Claude 가 BDD 패턴 인식
- Open Decisions 는 `> ⚠️` blockquote 로 강조



### 5.1 Cursor / Claude 친화 부분

- 모든 코드 식별자 (`function`, `Table.name`, `column.name`) 는 백틱 표시 → IDE 가 클릭 가능 링크로 인식
- `function.file_path:start_line-end_line` 표기 — Cursor 가 직접 코드 점프
- Acceptance Test 의 GWT 는 `**Given**` / `**When**` / `**Then**` 굵기 + bullet → BDD 패턴 인식
- Open Decisions 는 `> ⚠️ {question}` blockquote 로 강조
- Aggregate Invariants 표는 `| seq | statement | fn | given | when | then |` 형태 — Cursor 가 표 인식 시 컬럼 정렬 유지

### 5.2 길이 제한

LLM context 제약 — 한 BC 의 spec 이 너무 길면 분할:
- BC 당 평균: 5 Aggregate × 3 invariant × 1 줄 + 9 Command × 5 precond + 14 Event × 1 GWT ≈ 200~300 줄
- Cursor / Claude Code 의 single-file context 한도 (보통 1만 줄 미만) 안에 들어옴 — 분할 불필요
- 만약 한 BC 가 30+ Aggregate 보유 시 (대형 monolith): Aggregate 별 별도 파일 (`specs/{bc_name}/{agg_name}.md`) 로 분할 옵션 — 후속 §7

---

## §6 검증 기준

### 6.1 traceability 흐름 검증

```cypher
// (1) 영속된 BC 의 모든 Aggregate 가 fetch 결과에 invariants 보유
MATCH (bc:BoundedContext)-[:HAS_AGGREGATE]->(a:Aggregate)
OPTIONAL MATCH (a)-[:DERIVED_FROM]->(r:Rule)
WITH a, count(r) AS rc
RETURN a.name, rc
// expected: 모든 Aggregate 의 rc > 0 (Phase 5 가 정상 영속한 경우)

// (2) PRD fetch DTO 의 invariants 카운트 = DERIVED_FROM 카운트
// → integration test 로 비교

// (3) markdown 출력에 분석기 statement 포함 검증
// → fixture 기반 string assertion: "{rule.statement}" in spec_markdown
```

### 6.2 zapamcom10060 기대 출력

분석기 정상 + Phase 5 정상 후 가정한 spec markdown:

```markdown
# Bounded Context: 실시간인증 (Core Domain)

## Open Decisions
- **Q1 (host fn `b800_skb_rltm_auth_err_msg_make`)**: R3(FROZEN)이 R2(잔액부족)보다 먼저 체크되는가?
  - Reason: 조건 순서가 코드 선언 순서로만 드러남. 정책 문서 확인 필요

## User Stories — code-traced
| US id | role | action | source rules | implements |
|---|---|---|---|---|
| us_task_05f890 | system | 인증결과 처리 | 7 (b000_main_proc, b400_*) | Agg:AuthHistory, Cmd:ProcessAuthResult, Event×3 |
| ... |

## Aggregate: 실시간인증이력 (`AuthHistory`)

### Root Table
- **Table**: `zpay_ap_rltm_auth_hst` (5 columns)
  - `acnt_num`: NUMBER 🔑 PK
  - `op_cl`: VARCHAR2(2)
  - ...

### Invariants
| seq | statement | host function | given | when | then |
|---|---|---|---|---|---|
| R3 | "성공 시 인증이력을 INSERT 한다" | `b000_main_proc` | 인증결과=성공 | 결과 반영 | hst 행 추가 |
| R5 | "..." | ... | ... | ... | ... |

### Lifecycle Events
- `AuthHistoryRecorded` (실시간인증이력 기록됨) — INSERT on `zpay_ap_rltm_auth_hst`
  - Source Example: `b000_main_proc::R3::1` (boundary=false)
    - **Given**: acnt_num=12345, op_cl="01", auth_rslt="0000"
    - **When**: 인증 성공 처리
    - **Then**: hst INSERT (acnt_num=12345, ...)

## Command: 인증결과 처리 (`ProcessAuthResult`)

### Preconditions
| seq | statement | host function |
|---|---|---|
| R1 | "청구번호가 0이면 오류로 종료한다" | `a000_input_validation` |
| R2 | "업무구분이 공백이면 오류로 종료한다" | `a000_input_validation` |
| ... |

### Emits Events
- `AuthHistoryRecorded` (op=INSERT, table=zpay_ap_rltm_auth_hst)
- ...
```

위 형태 markdown 의 byte 수 vs legacy markdown:
- legacy: 노드 속성만 ≈ 50 줄/BC
- 신: 분석기 근거 inline ≈ 250~400 줄/BC

### 6.3 Cursor / Claude 입력 품질 (수동 검증)

생성된 spec markdown 을 Cursor / Claude Code 에 input 으로 주고:
- 작업 1: "이 Aggregate 의 invariant 코드를 작성하라" → 한국어 statement → Java/Python class 변환 정확도
- 작업 2: "이 Command 의 precondition 검증 로직을 작성하라" → R1~RN guard chain 인식
- 작업 3: "이 Event 의 acceptance test 작성하라" → Example.given/when_/then_ 그대로 BDD test 변환

각 작업에서 LLM 이 "이 statement 가 어디 (which Rule.local_id) 에서 왔는지" 정확히 인식하면 traceability 흐름 성공.

---

## §7 구현 순서 + 의존 관계

> 라인 번호는 [`prd_model_data.py`](../../api/features/prd_generation/prd_model_data.py) / [`prd_artifact_generation.py`](../../api/features/prd_generation/prd_artifact_generation.py) 현 시점 (2026-05-06).

```
[0. (생략 — v1.2 결정) Phase 5 augment-only 모델로 전환됨에 따라 신 파이프라인이
    어떤 ES 노드도 영속하지 않으므로 GWTCandidate / _merge_gwt 작업 자체가 불필요.
    fetch 시점에 legacy GWT + 분석기 Example fallback 합집합으로 처리 (§4.1 inject C 참조).]

[1. fetch_bc_data() Cypher 보강 — §4.1 inject A~D]
  - prd_model_data.py 의 단일 query 안에 4개 절 추가 (라인 14~135 안)
  - inject A: 라인 14~25 직후 (Aggregate Properties 와 Commands 사이)
  - inject B: 라인 25~31 직후 (Commands 의 Properties 다음)
  - inject C: 라인 33~41 직후 (Events 의 Properties 다음)
  - inject D: 라인 113~122 직후 (UI / GWT 다음, RETURN 직전)
  - RETURN 절 (라인 124~134) 에 4개 신 키 추가
  - 검증: zapamcom10060 fixture 로 fetch_bc_data 호출 → returned dict 에 .questions / .userStories / agg.derivedInvariantsDetail / cmd.preconditions / evt.acceptanceTest / agg.rootTable 키 존재 확인

[2. markdown 헬퍼 함수 6 개 신설]
  - prd_artifact_generation.py 끝부분에 추가
  - render_open_decisions, render_user_stories_index, render_aggregate_table_schema,
    render_invariants_table, render_command_preconditions, render_event_acceptance_test
  - 각 함수 단위 테스트 (빈 input → "" 반환 / 정상 input → 기대 markdown)
  - 의존: 없음 (순수 함수)

[3. generate_bc_spec() 보강 — §5.1 표 위치별 inject]
  - 6 곳에 헬퍼 호출 + 섹션 append
  - 라인 569 직후 (Open Decisions, User Stories — 두 헬퍼 연속 호출)
  - 라인 575 직후 (Root Table schema — Aggregate 루프 안)
  - 라인 576 (Invariants list 자리) 를 render_invariants_table 우선, 비면 기존 list
  - 라인 591 직후 (Command Preconditions — Command 루프 안)
  - 라인 612 직후 (Event Acceptance Test — Event 루프 안)
  - 의존: 1, 2

[4. generate_main_prd() BC 요약 표 보강 — §5.3]
  - 라인 75 부근 (BC summary table) 에 컬럼 2개 추가
  - 의존: 1

[5. generate_claude_md() — §5.4]
  - 라인 825 부근 BC 목록 줄에 traceability stat 추가
  - 의존: 1

[6. generate_agent_config() — §5.5]
  - 라인 1980 부근 Aggregates 섹션 다음에 Critical Invariants top-5 + Open Decisions 섹션
  - 의존: 1, 2

[7. session_id 필터 추가 — §4.2]
  - fetch_bc_data(bc_id, session_id=None)
  - get_bcs_from_nodes(node_ids, session_id=None)
  - PRDGenerationRequest 에 session_id: str | None 필드 (Pydantic)
  - routes/prd_export.py 의 /generate, /download 가 request.session_id 전달
  - 의존: 1

[8. 통합 테스트 — §6.2 fixture]
  - zapamcom10060 promote-to-es 후 /api/prd/download 호출 → ZIP 풀어서 BC spec markdown 의 string assertion
  - 분석기 데이터 부재 / 일부 부재 / 풀 데이터 3 가지 시나리오 모두 graceful 출력 확인
  - 의존: 3, 6

[9. Cursor / Claude 수동 검증 — §6.3]
  - 풀 데이터 fixture 로 ZIP 받아 Cursor 에 import → "Aggregate X 의 invariant 코드 작성" 시나리오 평가
  - LLM 이 Rule.statement 를 정확히 인용하는지 / acceptance test GWT 가 BDD 코드로 변환되는지

[별도 작업 (Phase 6 범위 외) — §8]
  - UI Wireframe 생성 (Phase 5 가 이를 만들지 않음 — 현재는 legacy phase 가 만든 43건 활용)
  - LLM-driven Gherkin 자동 생성
  - PRD diff (이전 ES 모델 vs 현재)
  - bidirectional sync (사용자가 spec 수정 → ES 노드 sync)
```

### 7.1 의존 그래프

```
[2 헬퍼] ─┐
         ├→ [3 generate_bc_spec]──┐
[1 Cypher]┤                       ├→ [8 통합 테스트] → [9 수동 검증]
         ├→ [4 generate_main_prd] ┤
         ├→ [5 generate_claude_md]┤
         └→ [6 generate_agent_cfg]┘
[7 session_id] ─→ (보강 후 모든 endpoint)
```

### 7.2 안전한 PR 분할 안

본 PRD 의 작업을 한 PR 에 다 넣으면 약 600~800 줄 변경. 분할 추천:

- **PR-1**: 1, 2, 3 (핵심 — Cypher 보강 + spec 빌더). 즉시 가치 ⭐⭐⭐
- **PR-2**: 4, 5, 6 (PRD.md / CLAUDE.md / agent_config 보강). 부수 가치 ⭐⭐
- **PR-3**: 7 (session_id 필터). 안전성 ⭐
- **PR-4**: 8, 9 (테스트 + 수동 검증)

### 7.3 구현 status (2026-05-08)

> 2026-05-09 보강으로 Step 7(session_id 필터)까지 구현 완료. 다음 에이전트는 Step 8~9 를 진행하면 본 PRD 를 닫을 수 있음.

| Step | 항목 | 상태 | 위치 |
|---|---|---|---|
| 1 | `fetch_bc_data()` Cypher 보강 (inject A~D) | ✅ **구현됨** | [`prd_model_data.py`](../../api/features/prd_generation/prd_model_data.py) Step 9 (UserStory + SOURCED_FROM + Example) + Step 10 (Question) + `_attach_per_node_source_rules` (Aggregate/Command/Event 별 source rule rollup with 3-tier table fallback) |
| 2 | markdown 헬퍼 함수 6 개 신설 | ✅ **구현됨** + 추가 2개 | [`prd_artifact_generation.py`](../../api/features/prd_generation/prd_artifact_generation.py) 최상단: `render_source_rules_table` / `render_acceptance_tests` / `render_open_decisions` / `render_user_story_index` + 추가로 노드별 `render_node_source_rules` / `render_node_source_examples` |
| 3 | `generate_bc_spec()` 보강 (6 곳 inject) | ✅ **구현됨** | BC 헤더 직후 (Open Decisions + UserStory index) + grounded US 들의 "User Stories — analyzer-grounded detail" 절 + Aggregate/Command/Event 블록 안에 per-node source rules + Event 의 acceptance examples |
| 4 | `generate_main_prd()` BC 요약 표 보강 | ⚠️ **부분** | BC summary 표는 v1.1 design 그대로 — source rule count 컬럼은 미추가 (다음 작업자가 마저) |
| 5 | `generate_claude_md()` BC 목록 보강 | ✅ **구현됨** | 각 BC 별 `(N aggregates, M grounded US, K open questions)` 메타 표시 |
| 6 | `generate_agent_config()` Critical Invariants top-5 + Open Decisions | ⚠️ **부분** | "Source-of-truth grounding" 가이드 절 추가 (grounded vs description-only US 구분 + Open Decisions 정책 안내). 단 Critical Invariants top-5 자동 추출은 미구현 — 다음 작업자가 마저 |
| 7 | `session_id` 필터 추가 | ✅ **구현됨** (2026-05-09) | `PRDGenerationRequest.session_id` 추가 + `routes/prd_export.py` 의 `/generate`/`/download` 에서 전달 + `get_bcs_from_nodes(node_ids, session_id=None)` / `fetch_bc_data(bc_id, session_id=None)` / `_attach_per_node_source_rules(..., session_id=None)` 반영 |
| 8 | 통합 테스트 (zapamcom10060 fixture) | ⚠️ **부분 구현** (2026-05-09) | 테스트 11건 통과: `test_prd_session_scope.py` 6건 (`/generate`/`/download` session_id 전달, node_ids 분기 session 필터, fetch full-data shape, partial/none graceful, fetch 전파) + `test_promote_to_es_traceability.py` 1건 (Question fallback orphan 전체 attach 검증) + `test_pipeline_verification.py` 2건 (pipeline ready / not-ready 판정) + `test_pipeline_e2e_check.py` 2건 (pipeline + PRD input 동시 ready 판정). fixture 기반 end-to-end 시나리오는 잔여 |
| 9 | Cursor / Claude 수동 검증 | ❌ **미구현** | 풀 데이터 fixture 로 ZIP 받아 Cursor 에 import → "Aggregate X 의 invariant 코드 작성" 시나리오 평가 |

**핵심 framing 보완 — verification report §3.8 적용**:

기존 §4 의 fallback Cypher 설계를 **source-of-truth 계층** framing 으로 명확화. ES 노드의 진짜 source 는 US 가 아닌 **Rule + Example + (Function)**:

```
ES 노드 (Aggregate / Command / Event)
   │ IMPLEMENTS                ← 조직화 (출처 아님)
   ▼
UserStory                       ← gateway
   │ SOURCED_FROM
   ▼
Rule.statement                  ← ★ source 1
   │ HAS_EXAMPLE
   ▼
Example.given/when_/then_       ← ★ source 2
   │ AFFECTS_TABLE (op)
   ▼
Table                           ← ★ source 3 (Aggregate root grounding)
```

Phase 6 의 fetch_bc_data 가 IMPLEMENTS US 까지가 아니라 **Rule/Example/Table 까지 traverse 해야 함**. 본 PRD §4 의 fallback Cypher 가 정확히 이 chain — 다음 작업자는 framing 일관성을 위해 v1.2 의 §3.8 (verification report) 인용 권장.

**Inspector "출처" 탭 재설계** (Phase 5 v4 §12.3 와 정합):

같은 세션에 Inspector 의 출처 탭도 chain → sources-per-US 로 재설계됨. PRD spec markdown 의 inject 결과와 **개념적으로 동일 source-of-truth** 를 보여줌. 다음 작업자가 PRD 출력과 Inspector 출력의 일관성 검증 시 이 framing 활용.

---

## §8 후속 (별도 PRD)

- **PRD diff 도구** — Phase 5 재실행 시 이전 PRD 와 비교, "Aggregate X 의 invariant R3 가 추가됨 / R5 가 사라짐" 시각화. 변경 이력 자동 추적.
- **LLM 보강 섹션** — `traceability` 정보를 LLM 에 주고 "Acceptance Criteria (Gherkin)" / "API Contract (OpenAPI snippet)" 자동 생성. 결정론 layer 위에 LLM-suggested layer.
- **Aggregate-별 spec 분할** — 한 BC 가 너무 크면 `specs/{bc_name}/{agg_name}.md` 분할. 인덱스 markdown 이 모든 sub-spec 링크.
- **bidirectional sync** — Cursor / Claude 가 spec 수정 후 사용자 commit 하면 Inspector UI 가 변경 감지, "이 invariant 가 변경되었음 — Aggregate 재검토 필요" 모달.

---

## §9 PRD 생성 보강 vs 현 흐름 비교

| 단계 | 현재 (Phase 5 직후) | Phase 6 (본 PRD) |
|---|---|---|
| Neo4j 영속 | ✅ traceability 26 종 엣지 | ✅ 동일 |
| PRD fetch Cypher | ❌ HAS_*/EMITS 만 | ✅ + SOURCED_FROM/DERIVED_FROM/PRECONDITION_BY/GROUNDED_IN/ATTACHED_TO |
| PRD markdown | 노드 속성만 (50 줄/BC) | 분석기 근거 inline (250~400 줄/BC) |
| Cursor / Claude 입력 | "Aggregate Order 가 있다" 수준 | "Aggregate AuthHistory — root_table=zpay_ap_rltm_auth_hst, invariants=[R3 statement..., R5 statement...], events=[AuthHistoryRecorded with given/when/then]" |
| 코드 ↔ 도메인 추적 | ❌ 끊김 | ✅ Aggregate → Rule.statement → function:line 까지 단일 markdown |
| Open Decisions | ❌ Question 누락 | ✅ BC 헤더에 Q&A 모달 |

---

*작성일: 2026-05-06 — Phase 6 PRD Generation Traceability Boost v1*
