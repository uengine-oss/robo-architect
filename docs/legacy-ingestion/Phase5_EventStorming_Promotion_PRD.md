# Phase 5 — Event Storming Promotion PRD

> **작성일**: 2026-05-04 (v1) → 2026-05-06 (v1.1 실측) → v2 (augment-only) → v3 (input boost) → v3.1 (GWT corrected) → v3.2 (Event.key fix) → **v4 (검증 완료 + Inspector source-of-truth refactor, 2026-05-08)**
> **상태**: v4 구현 완료 + 검증 완료. PRD 생성 (Phase 6) 진입 가능 — Phase 6 PRD 의 inject A~D 도 부분 구현됨 ([Phase6 status](Phase6_PRD_Generation_Traceability_Boost.md) 참조).
> **방향성 변천 한 줄 요약**:
>   - v1 (replace): 신 파이프라인 단독 영속 → wipe 위험 + LLM 비용 2배
>   - v2 (augment-only): legacy 결과 보존 + sid 태깅/PROMOTED_TO/SOURCED_FROM/ATTACHED_TO/cross-BC Policy
>   - v3 (input boost): legacy phase LLM input 에 BL 정보 합성 (5 phase 보강)
>   - v3.1 (GWT corrected): GWT 는 LLM skip 이 아니라 LLM 호출 유지 + BL 을 reference 로 inject. 사용자 통찰 "BL 의 GWT 는 설명식, LLM 이 그것을 보고 ES properties 의 schema-bound fieldValues 를 구성해야 의미가 있어짐."
>   - v3.2 (Event.key fix): `_create_standalone_event` 에 `evt.key` set 누락이 Event HAS_PROPERTY 0/N 의 root cause. 단순 slug set + 기존 데이터 backfill 로 해결.
>   - **v4 (2026-05-08)**: Event HAS_PROPERTY = 0 잔여 결함 닫음 (events_by_agg helper Cypher syntax + properties.py dict accessor). traceability shadow→analyzer 매칭 깨짐 수정. Inspector "출처" 탭 chain → sources-per-US 재설계 + 노드 타입별 primary source emphasis. PRD 생성 endpoint 보강 (fetch_bc_data + 노드별 source rule rollup). **검증 완료** — GWT thenFieldValues 90% schema-bound, ES → Rule chain 의미 정합성 입증.
>
> **검증 보고서**: [Phase5_Phase6_Verification_Report.md](Phase5_Phase6_Verification_Report.md) — v4 산출물의 종합 audit (BPM/BL → ES 추적 무결성, 의미 정합성, PRD 진입 가능성 평가). 핸드오프 §1~§9 의 변경 이력은 본 PRD §12 (v4 구현 status) 와 검증 보고서 로 통합됨.
> **참조 문서**:
> - `Hybrid_Ingestion_Architecture.md` §10/§11 — 신스키마 적용 + 탐색 비용 최적화 결과
> - `개선&재구조화.md` §9.6 — 후속 과제 진행 상태 + 본 PRD 진입점. Phase 2.5/2.6 폐기 결정 회의록도 포함
> - `../../../input_resource/2026-04-22-BusinessLogic-노드-구조변경-아키텍트안내.md` — analyzer 신스키마 (Rule/Example/Question + 관계·속성) reference. 위치는 `docs/legacy-ingestion/` 외부 (`input_resource/`)
>
> **최신 보강 (2026-05-09)**:
> - 후속 재검증 실측: `BpmTask 31`, mapped task `9`, 0-rule task `22`, `UserStory 35`, grounded US `13`, description-only US `22`
> - 관계 타입 실측: `PROMOTED_TO / SOURCED_FROM / IMPLEMENTS / ATTACHED_TO` 확인
> - 미영속: `PROMOTED_FROM / DERIVED_FROM / PRECONDITION_BY / GROUNDED_IN` (Phase 6 후속 과제로 유지)
> - Phase 6 Step 7(`session_id` 필터) 구현 완료 — PRD generation request/route/model-data 전파
> - Phase 6 Step 8 부분 진행 — 테스트 11건 통과: `test_prd_session_scope.py` 6건(`/generate`/`/download` session scope + node_ids 필터 + fetch 경계 처리) + `test_promote_to_es_traceability.py` 1건(Question fallback attach 로직) + `test_pipeline_verification.py` 2건(pipeline ready/not-ready 판정) + `test_pipeline_e2e_check.py` 2건(pipeline+PRD input ready 동시 판정)
> - Question attach 보완 — `promote_to_es.py` fallback 쿼리 수정(BC 1개 선정 후 orphan Question 전체 attach)
> - 최신 세션(`94b625fe`) 실측 검증: Question attach coverage **4/4** (`orphan_in_sid=0`)
> - 최신 세션(`94b625fe`) pipeline verifier 실측: `pipeline_ready=true` (BPM/Rule매핑/ES/PRD-ready 전부 true)
> - 최신 세션(`94b625fe`) e2e check 실측: `e2e_ready=true`, `prd_input_check.ready=true` (BC 6개 모두 spec 후보 충족)
>
> **선행 문서**: `Hybrid_Phase5_EventStorming_Promotion.md` (Phase 2.5/2.6 기반, **폐기 예정**)
>
> **인프라 사실**: 분석기 데이터와 robo-architect 자체 데이터는 **단일 Neo4j DB 에 공존** (실측). `ANALYZER_NEO4J_DATABASE` env 가 비어 있어 `get_session(database=ANALYZER_NEO4J_DATABASE)` 도 default DB 를 가리킴. 분석기 노드 (`Rule`/`Example`/`Question`/`Table`) 는 `session_id` 가 없고, robo-architect 가 만든 shadow 노드 (`Rule`/`BpmTask` 등) 는 `session_id` 보유로 구분.

이 문서는 사용자가 BPM + Rule 매핑을 검토한 후 "이벤트 스토밍 모델 생성" 트리거 시 실행되는 Phase 5 의 새 설계를 정의한다. 핵심 변경:
1. Phase 2.5 (BC pre-tag) / Phase 2.6 (ES role pre-tag) 폐기로, 모든 ES 요소 판정을 Phase 5 가 직접 수행
2. analyzer 신스키마 (Rule/Example/Question + flow_id/guard_rule_id/branch_from/coupled_domains/AFFECTS_TABLE) 의 풍부한 메타정보를 결정론적 분해 신호로 활용
3. 한 BpmTask 가 여러 ES 요소 (Aggregate/Command/Event/Policy/ReadModel) 의 결합체임을 인정하고, Task 단위 1:1 매핑이 아닌 "Task 분해" 모델 채택
4. 양방향 traceability 그래프로 영향도 분석 지원

---

## §1 목표 / 비목표

### 목표
- BPM 결과물 (BpmProcess + BpmTask + REALIZED_BY → Rule) + analyzer 신스키마 메타 → 일관된 Event Storming 모델 (UserStory/BoundedContext/Aggregate/Command/Event/Policy/ReadModel) 생성
- ES 노드 ↔ BPM ↔ analyzer 노드 간 traceability 엣지 형성으로 양방향 영향도 분석 가능
- 매핑 0건 task 도 문서 기반으로 US 생성 (코드 근거 없음을 마커로 명시)
- 멱등 — 같은 입력 → 같은 결과. 재실행 시 사용자 manual override 우선
- LLM 호출 최소화 — 결정론적으로 분해 가능한 부분은 LLM 안 거침

### 비목표
- 사용자 수동 편집 도구 신규 제공 (기존 ES 캔버스의 노드 편집 기능 그대로 활용)
- ES 도메인 모델 자체의 검증 (이름·서술 품질 평가는 사용자 책임)
- BC 자동 분리 (사용자가 BC 경계 조정은 캔버스에서 수동)

### 트리거
- **수동 유지** — BPMN 탭 "이벤트 스토밍 모델 생성" 버튼 → `POST /api/ingest/hybrid/{sid}/promote-to-es`
- 재실행 시 사용자 확인 다이얼로그 ("기존 ES 모델을 재생성하시겠습니까?")

---

## §2 입력 계약

Phase 5 가 시작될 때 그래프 상태 (zapamcom10060, **2026-05-06 실측**):

| 노드 / 관계 | 실측 | Phase 5 추출 경로 | 용도 |
|---|---|---|---|
| `BpmProcess` (`session_id` 보유) | 1 session | 메인 DB 직접 query | BC 후보 군집 시작점 |
| `BpmTask` | 33 | 메인 DB | US + Aggregate/Command/Event 분해 단위 |
| `BpmActor` | — | 메인 DB | UserStory.role |
| `(BpmTask)-[:REALIZED_BY]->(Rule)` | 28 (8/33 task) | 메인 DB | ES 요소 분해 입력 |
| `Rule` (analyzer, no `session_id`) | 59 | analyzer 영역 (같은 DB, `session_id IS NULL` 로 식별) | rule.statement = ES 요소 의도 |
| `Example` (analyzer) | 87 | analyzer 영역 | GWT + `then_.writes[]` (JSON-encoded) |
| `(Rule)-[:HAS_EXAMPLE]->(Example)` | 87 | analyzer 영역 | 1:N |
| `(Example)-[:AFFECTS_TABLE {op}]->(Table)` | **26** | analyzer 영역 — **현재 robo-architect 가 traverse 안 함** (§2.1 보강 필요) | Aggregate root 결정 신호 |
| `(FUNCTION)-[hr:HAS_RULE]->(Rule)` | 59 | analyzer 영역 — `hr` 속성: `local_id`, `flow_id`, `coupled_domains` (현재 추출), `guard_rule_id`, `branch_from` (**§2.1 보강 필요**) | hr 속성에 분기·흐름 메타 |
| `HAS_RULE.guard_rule_id` non-null | 16/59 | (위 보강) | Command precondition chain |
| `HAS_RULE.branch_from` non-null | 12/59 | (위 보강) | 별개 분기 Command |
| `HAS_RULE.coupled_domains` non-empty | 11/59 | 추출 중 | cross-BC Policy 후보 |
| `Question` (analyzer) | 4 | analyzer 영역 | 검토 메모 |
| `(FUNCTION)-[:HAS_QUESTION]->(Question)` | 4 | analyzer 영역 | BC 검토 메모 부착 |
| `(Rule)-[:NEXT]->(Rule)` | **33** | analyzer 영역 — **§2.1 보강 필요** | 함수 내 메인 시나리오 흐름 |
| `(Rule)-[:BRANCH]->(Rule)` | **14** | analyzer 영역 — **§2.1 보강 필요** | if/else 갈래 = Policy 분기 후보 |
| `(BpmTask)-[:SOURCED_FROM]->(DocumentPassage)` | Phase 4.1 산출 | 메인 DB | 문서 근거 |

> **수치 차이 주의**: PRD 초안의 51 / 108 / 34 / 23 / 27 / 12 는 이전 dump 시점 추정치. 위 표는 2026-05-06 현재 실측치.

**Rule 매핑 분포 (현 실측)**: 8 tasks 가 1+ 매핑, 25 tasks 0 매핑 (REALIZED_BY 28건).

---

## §2.1 RuleDTO / ExampleDTO 입력 보강 (Phase 5 선결 작업)

PRD §3.1 결정론 매트릭스의 신호 중 **5개**는 분석기 DB 에 실재하지만 현재 robo-architect 까지 흘러오지 않는다. Phase 5 본 구현 진입 전에 [`hybrid/code_to_rules/rule_extractor.py`](../../api/features/ingestion/hybrid/code_to_rules/rule_extractor.py) 와 [`hybrid/contracts.py`](../../api/features/ingestion/hybrid/contracts.py) 를 보강해 다음을 RuleDTO/ExampleDTO 가 carry 하도록 한다.

### 2.1.1 막혀 있는 신호와 막힌 위치

| §3.1 신호 | 분석기 DB | 막힌 위치 | 영향 |
|---|---|---|---|
| `Example.then_.writes[].op` (INSERT/UPDATE/DELETE) | ✅ JSON-encoded `then_` 안 (실측: `{"narrative":..., "writes":[{"table","op"}]}`) | `rule_extractor._humanize()` 가 `narrative` 만 뽑고 raw JSON 폐기 (`rule_extractor.py:135-137`) | Aggregate creation/mutation/removal Event 종류 결정 불가 |
| `HAS_RULE.guard_rule_id` | ✅ 16건 | `_QUERY` RETURN 절 부재 (`rule_extractor.py:41-50`) | Command precondition chain 추출 불가 |
| `HAS_RULE.branch_from` | ✅ 12건 | 같은 위치 부재 | 별개 분기 Command 추출 불가 |
| `(Rule)-[:NEXT]->(Rule)` | ✅ 33건 | query 자체 없음 | Saga/순차 invariant 추출 불가 |
| `(Rule)-[:BRANCH]->(Rule)` | ✅ 14건 | query 자체 없음 | Policy 분기 트리거 추출 불가 |
| `(Example)-[:AFFECTS_TABLE {op}]->(Table)` | ✅ 26건 | 같은 — query 안 함 | root Table 군집 → Aggregate 통합 (§4.2) 불가능 |

### 2.1.2 DTO 확장 명세

```python
# contracts.py — 추가 필드 (기존 필드는 그대로 보존)

class ExampleDTO(BaseModel):
    # ...기존 필드 유지 (example_id, given, when_, then_, is_boundary, description)
    writes: list[dict] = Field(default_factory=list)   # [{"table": str, "op": "INSERT"|"UPDATE"|"DELETE"}, ...]
    # 출처: AFFECTS_TABLE 엣지 (op 속성) 또는 then_ JSON 의 writes[] 둘 다 합치면 robust

class RuleDTO(BaseModel):
    # ...기존 필드 유지
    local_id: Optional[str] = None         # HAS_RULE.local_id ("R1"~"R8")
    flow_id: Optional[str] = None          # HAS_RULE.flow_id ("1", "2-1")
    guard_rule_id: Optional[str] = None    # HAS_RULE.guard_rule_id (선행 local_id)
    branch_from: Optional[str] = None      # HAS_RULE.branch_from (분기 부모 local_id)
    next_rule_local_ids: list[str] = Field(default_factory=list)    # NEXT 후속 local_id
    branch_rule_local_ids: list[str] = Field(default_factory=list)  # BRANCH 갈래 local_id
```

> `next_*`/`branch_*` 를 hash-id 가 아닌 **`local_id`** 로 carry 하는 이유: 같은 함수 내 분기 의도 표현이 목적이고, NEXT/BRANCH 관계 자체에 `function_id` 가 묶여 있어 (function, local_id) 만으로 식별 가능. cross-function 흐름은 PRD 범위 밖.

### 2.1.3 Cypher 보강 (rule_extractor.py)

```cypher
MATCH (f:FUNCTION)-[hr:HAS_RULE]->(r:Rule)
OPTIONAL MATCH (r)-[:HAS_EXAMPLE]->(e:Example)
OPTIONAL MATCH (e)-[at:AFFECTS_TABLE]->(tbl:Table)
WITH f, hr, r,
     collect(DISTINCT {
        example_id:  e.example_id,
        given:       e.given,
        when_:       e.when_,
        then_:       e.then_,         // raw JSON 보존 (humanize 는 별도 narrative 필드로)
        is_boundary: coalesce(e.is_boundary, false),
        description: e.description,
        writes:      collect(DISTINCT {table: tbl.name, op: at.op})
     }) AS examples
// NEXT/BRANCH 는 local_id 단위로 별도 collect (hr 와 같은 함수 한정)
OPTIONAL MATCH (r)-[nx:NEXT]->(rn:Rule)<-[hrn:HAS_RULE]-(f)
OPTIONAL MATCH (r)-[br:BRANCH]->(rb:Rule)<-[hrb:HAS_RULE]-(f)
WITH f, hr, r, examples,
     [x IN collect(DISTINCT hrn.local_id) WHERE x IS NOT NULL] AS next_local_ids,
     [x IN collect(DISTINCT hrb.local_id) WHERE x IS NOT NULL] AS branch_local_ids
RETURN
    coalesce(f.function_id, f.procedure_name, f.name) AS function_id,
    coalesce(f.procedure_name, f.name)                AS function_name,
    f.procedure_name                                  AS procedure_name,
    f.summary                                         AS function_summary,
    r.statement                                       AS statement,
    hr.local_id                                       AS local_id,
    hr.flow_id                                        AS flow_id,
    hr.guard_rule_id                                  AS guard_rule_id,
    hr.branch_from                                    AS branch_from,
    coalesce(hr.coupled_domains, [])                  AS coupled_domains,
    examples                                          AS examples,
    next_local_ids                                    AS next_rule_local_ids,
    branch_local_ids                                  AS branch_rule_local_ids
ORDER BY function_name, hr.local_id
```

> **AFFECTS_TABLE 와 then_.writes[] 둘 다 채워주는 이유**: 분석기가 둘 다 만들지만 일부 함수는 한쪽만 채워질 수 있음. ExampleDTO.writes 는 합집합 — `[{table, op}]` set 으로 dedup 후 carry. PRD §3.1 결정론 분류 (`writes[].op` 보유 여부) 의 robust 확보.

### 2.1.4 검증 (zapamcom10060)

보강 후 다음 실측치를 만족해야 한다:
- 추출된 RuleDTO 중 `guard_rule_id IS NOT NULL` = **16** ± 0
- 추출된 RuleDTO 중 `branch_from IS NOT NULL` = **12** ± 0
- 추출된 ExampleDTO 중 `writes` non-empty = **26** ± few (AFFECTS_TABLE 26건 + then_.writes JSON 합집합이라 약간 더 많을 수 있음)
- `next_rule_local_ids` 합산 = **33** ± 0
- `branch_rule_local_ids` 합산 = **14** ± 0

이 항목들이 통과하면 §3.1 매트릭스 100% 가용. Phase 5 본 구현 진입 가능.

---

## §3 신스키마 → ES 요소 매핑 매트릭스

각 분석기 메타 정보를 ES 요소 판정 신호로 변환:

### 3.1 결정론 신호 (LLM 호출 없이 분류)

> 각 신호의 **현재 가용성** 컬럼: ✅ = RuleDTO/ExampleDTO 가 이미 carry, ⏳ = §2.1 보강 후 carry. 보강 전엔 ⏳ 행은 dead signal.

| 분석기 정보 | ES 매핑 | 판정 규칙 | 현재 가용 |
|---|---|---|---|
| `Example.then_.writes[].op = "INSERT"` | **Aggregate creation Event** | 결정론 — 해당 Rule 1개당 1 Event | ⏳ §2.1 |
| `Example.then_.writes[].op = "UPDATE"` | **Aggregate state mutation invariant** | 결정론 — Rule.statement 가 invariant 본문 | ⏳ §2.1 |
| `Example.then_.writes[].op = "DELETE"` | **Aggregate removal Event** | 결정론 | ⏳ §2.1 |
| `Example.then_.writes` empty + (FUNCTION)-[:READS]->(Table) 존재 | **ReadModel query** | 결정론 | ⏳ §2.1 |
| `Rule.statement` 패턴 매칭 — head: `검증\|거부\|판정\|확인\|체크\|검사`, tail: `필수(다\|이다)\|오류(로 종료한다\|이다\|다)\|예외(이다\|다)` | **Command precondition** | head 또는 tail 매치. 실측 fixture (zapamcom10060) 의 statement 가 한국어 평서문 ("...오류로 종료한다", "...필수다") 위주라 head 만으로는 0건 매치 → tail 패턴 추가 | ✅ |
| `HAS_RULE.guard_rule_id` 보유 | **Command precondition chain** | R2.guard=R1 → Command(R2) 의 precondition 에 R1 statement 포함 | ⏳ §2.1 |
| `HAS_RULE.branch_from` 보유 | **별개 Command 분기** | R3.branch_from=R2 → R2 fail 시 R3 트리거 (별도 Command 후보) | ⏳ §2.1 |
| `HAS_RULE.coupled_domains[]` non-empty | **Cross-BC Policy** | 자기 Aggregate 영역을 벗어난 영향 → Policy 강력 후보 | ✅ |
| `Example.is_boundary = true` | **Command acceptance test (GWT)** | 경계값 = invariant 검증 케이스 | ✅ |
| 같은 root Table (`AFFECTS_TABLE` 도착점) 공유하는 Rule 군 | **같은 Aggregate** | Aggregate 멤버십 결정 | ⏳ §2.1 |
| 같은 `HAS_RULE.flow_id` (e.g., "2-1", "2-2") 공유 | **같은 Aggregate / 같은 분기** | 분기 묶음 | ⏳ §2.1 (필드 추가) |
| `(Rule)-[:NEXT]->(Rule)` chain | **Saga / Process flow** | 함수 내 시나리오 순서 | ⏳ §2.1 |
| `(Rule)-[:BRANCH]->(Rule)` | **Policy 트리거 분기** | 한 Rule 의 결과로 다른 Rule path 트리거 | ⏳ §2.1 |
| `Question` | **검토 메모 sticker** | 그대로 BC 에 부착, LLM 거치지 않음 | ✅ |

### 3.2 LLM 단계 (이름·서술만)

| 단계 | 입력 | LLM 출력 |
|---|---|---|
| **Aggregate 이름** | root Table name + 멤버 fn 군 | 한국어 도메인 명사 (e.g., "AuthHistory" → "실시간인증이력") |
| **Command displayName** | Rule.statement + Task.name | 한국어 명령형 짧은 라벨 |
| **Event name + displayName** | Rule.statement + Aggregate name | 영문 PascalCase + PastParticiple (e.g., "AuthHistoryRecorded") + 한국어 라벨 |
| **BoundedContext 그룹핑** | process.domain_keywords + Aggregate root tables 군집 | BC 1~N 개 + 각 BC name + Core/Supporting 분류 |
| **Policy name + 설명** | trigger Rule + invoke Rule + coupled_domains | 한국어 정책 이름 (e.g., "OnAuthFailedBuildErrorMessage") |
| **ReadModel name** | source Table + 호출 Task | 한국어 조회 모델 이름 |

### 3.3 결정론 vs LLM 분담 비율 목표
- 분류 결정 (어떤 ES 요소가 될지): **100% 결정론** (위 매트릭스)
- 그룹핑 (Aggregate 멤버십, BC 경계): 결정론 1차 (Table 공유 / domain_keywords) → 모호 시 LLM 보조
- 이름 / 서술: 100% LLM (이름은 도메인 용어 감성 필요)
- 총 LLM 호출 추정: BC 1 + Aggregate N×1 + Policy M×1 ≈ ~10~15 calls (Phase 5.A~G 통합)

---

## §4 분해 알고리즘

### 4.1 단일 Task 분해 (T → ES 요소들)

> **핵심 원칙**: UserStory 가 먼저 생성되고, **그 US 의 rule 집합** 을 분류해서 다운스트림 ES 요소를 만든다. 모든 다운스트림 노드는 자신을 구성한 US.id 를 carry 하고, 저장 시 IMPLEMENTS 엣지로 영속화 — US 한 점만 클릭해도 "이 US 가 어떤 Aggregate/Command/Event 를 만들었나" 한 번에 traceback.

```
입력:
  task = BpmTask
  task_rules = [(Rule, HAS_RULE rel, [Examples], [Questions of fn])]
  task_passages = Phase 4.1 결과 (top-2 DocumentPassage)
  task_actor = task.actor_ids[0] (또는 process actor fallback)

출력:
  TaskDecomposition {
    user_stories: [UserStoryDTO {id, rule_ids, ...}],      # rule_ids 가 핵심 — US ↔ Rule 직결
    aggregate_contributions: [AggCandidate {user_story_ids, rule_ids, ...}],
    commands: [CommandDTO {user_story_id, rule_ids, ...}],
    events: [EventDTO {user_story_id, derived_from_example_id, ...}],
    policies: [PolicyCandidate {user_story_id, ...}],
    read_models: [ReadModelDTO {user_story_id, ...}],
    questions: [QuestionRef],
  }

알고리즘:
  1. UserStory 생성 (먼저):
     - 매핑 1+ 있으면: 매핑 rules 의 statement 들을 LLM 1회로 묶어 1개 US 본문 작성
       us.rule_ids = [r.id for r in task.rules]   # ★ 모든 매핑 rule 을 US 가 carry
     - 매핑 0건이면: task.name + description + passages 로 LLM 1회 → US 1개 (source="document_only")
       us.rule_ids = []
     - role = task.actor_ids[0] resolved name (없으면 "system")
     - sequence = process.sequence_index * 100 + task.sequence_index
     - **us.task_id = task.id  ← (UserStory)-[:PROMOTED_FROM]->(BpmTask) 의 데이터**
     - **us.rule_ids → (UserStory)-[:SOURCED_FROM]->(Rule) 엣지 N 개로 영속화**

  2. Rule 분류 — 위 §3.1 매트릭스로 각 Rule 을 카테고리에 배치:
     - bucket["aggregate_invariant"] += UPDATE writes 가진 Rules
     - bucket["aggregate_creation"] += INSERT writes 가진 Rules
     - bucket["aggregate_removal"] += DELETE writes 가진 Rules
     - bucket["command_guard"] += statement 가 검증/판정 동사인 Rules + guard_rule_id chain
     - bucket["read_only"] += writes empty + READS 있는 Rules
     - bucket["cross_bc_policy"] += coupled_domains[] non-empty 인 Rules

  3. Aggregate 후보 추출:
     - bucket["aggregate_invariant"] + ["aggregate_creation"] + ["aggregate_removal"] 의 모든 Rules
     - root Table 별로 group (Example.then.writes[].table 의 가장 빈번한 것)
     - 각 group 이 1개 AggregateContribution:
         { root_table, member_rules, invariants, lifecycle_events,
           **user_story_ids = [us.id]**,    # ★ 본 Task US 가 이 Agg 를 implements
           **rule_ids = [r.id for r in member_rules]** }   # 출처 Rule

  4. Command 추출:
     - 1 Task = 1 Command 기본 (task.name 이 명령 의도)
     - precondition = bucket["command_guard"] 의 statement 들 (guard_rule_id 순)
       * **Orphan guard fallback**: `R.guard_rule_id` 가 가리키는 rule 이 `is_infra` / `is_meaningful_gwt` 필터로 drop 된 경우 (rule_classifier.index_by_function_local_id 로 lookup 실패) — 그 chain link 는 무시하고 R 자체의 statement 만 precondition 에 포함. 실측 (zapamcom10060) 4/15 케이스가 이에 해당, 정합성 깨지면 안 됨
     - emits = bucket["aggregate_invariant" + "_creation" + "_removal"] 의 Rules → 각 Event
     - branch_from 보유 Rule 군 별로 별도 Command (분기 명령)
       * **Orphan branch_from fallback**: 동일 — `R.branch_from` target 이 drop 된 경우 R 은 독립 Command 로 처리 (분기 부모 없음)
     - GWT = canonical Example 1건 (non-boundary 우선)
     - **command.user_story_id = us.id**  ← (Command)-[:IMPLEMENTS]->(US)
     - **command.rule_ids = [r.id for r in (guards + emit_sources)]**

  5. Event 추출:
     - bucket["aggregate_creation/_removal/_invariant"] 의 Rule 마다 1 Event
     - name = LLM 이 PastParticiple 변환 (Aggregate context + statement → "AuthHistoryRecorded")
     - sequence_within_command = HAS_RULE.local_id 순서
     - acceptance_tests = is_boundary=true Examples
     - **event.user_story_id = us.id**  (Command 의 US 상속)
     - **event.derived_from_rule_id = source_rule.id**
     - **event.derived_from_example_id = canonical_example.id**

  6. Policy 후보:
     - bucket["cross_bc_policy"] 의 Rules 마다 1 PolicyCandidate
     - trigger = 본 Task 의 Aggregate 의 Event
     - invoke = coupled_domains[0] 도메인의 Command (BC 확정 후 link)
     - **policy.user_story_id = us.id**  ← (Policy)-[:IMPLEMENTS]->(US)
     - **policy.source_rule_id = rule.id**

  7. ReadModel:
     - bucket["read_only"] 의 Rules → 1 ReadModel per source Table
     - query_keys = task.name 기반
     - **rm.user_story_ids = [us.id]**  ← (ReadModel)-[:IMPLEMENTS]->(US)
     - **rm.rule_ids = [r.id for r in read_only_rules]**

  8. Question:
     - 매핑된 Rule 들의 host FUNCTION 의 HAS_QUESTION → Question[]
     - Aggregate 의 BC 가 정해지면 그 BC 에 부착 (LLM 안 거침)
```

> **불변식**: 매핑 보유 task 에서 분해된 모든 Aggregate/Command/Event/Policy/ReadModel 노드는 **반드시** `user_story_id(s)` 와 `rule_id(s)` 둘 다 채워져 있어야 한다 — 이게 §5.2 시나리오 E (US → 다운스트림 ES) 의 불변식.
> **예외**: 매핑 0건 task 의 US 는 다운스트림 ES 요소를 만들지 않으므로 IMPLEMENTS 엣지 0개 (정합).

### 4.2 세션 단위 통합 (전체 Task → 전체 ES 모델)

```
1. 모든 Task 분해 결과 수집:
   all_decompositions = [decompose_task(t) for t in session.tasks]

2. UserStory 평탄화:
   user_stories = flatten(d.user_stories for d in all_decompositions)
   # 보통 33 tasks → 33~50 US (분기 task 는 ≥2 US)

3. Aggregate 통합 — root Table 공유 합치기:
   agg_by_root = group_by(all_decompositions.aggregate_contributions, key="root_table")
   for root, contribs in agg_by_root:
       merged = merge(contribs)  # member_rules + invariants + events 합집합
       aggregates.append(merged)
   # zapamcom10060 예: ZPAY_AP_RLTM_AUTH_HST → 1 Aggregate (b200/b205/b210/b400 합)

4. BoundedContext 그룹핑 (LLM 1회):
   - 입력: process.domain_keywords + aggregates 의 root_table 군 + Aggregate 간 cross 호출 (Policy)
   - LLM 출력: BC 2~5 개 + 각 BC.aggregate_keys + Core/Supporting 분류
   - 결정론 보장: Aggregate 1개는 정확히 1 BC 에 귀속

5. Command + Event 부착:
   - Command 는 본 Task 가 속한 Process 의 Aggregate 중 emits 대상이 있는 것에 부착
   - Event 는 emit 한 Command 의 BC 에 자동 귀속

6. Policy 본승격:
   - PolicyCandidate.trigger = source Aggregate.events[matching local_id]
   - PolicyCandidate.invoke = target BC 의 Command (이름 매칭으로 LLM 1회)
   - cross-BC 인 경우 kind="cross_bc"

7. ReadModel BC 부착:
   - ReadModel 은 본 Task 가 속한 Process 의 BC 중 source Table 의 Aggregate 가 있는 BC 에 부착
   - 없으면 Supporting BC "조회" 에 부착

8. Question 부착:
   - 각 Question 의 host FUNCTION → 매핑된 Task → Aggregate → BC
   - 그 BC 에 sticker 노드로 부착
```

### 4.3 매핑 0건 Task 처리

```
매핑 없는 task (zapamcom10060 기준 25/33):
  source = "document_only"
  user_stories = [LLM(task.name + task.description + passages → 1 US)]
  aggregates / commands / events = []  # 코드 근거 없음
  마커: us.benefit 끝에 "(문서 추론)" 표기 또는 us.metadata.source="document_only"
  
영향:
  - 이런 US 들은 BC 그룹핑 시 LLM 에게 "코드 매핑 없음" 명시
  - 사용자가 캔버스에서 "이 부분은 추가 분석 필요" 인식 가능
```

### 4.4 분기 & 흐름 활용 예 (zapamcom10060 b000_main_proc)

```
b000_main_proc (15 rules)
  R1: 입력 검증 (no writes)            → Command precondition
  R2: 인증 결과 판정 (no writes, branch_from null)  → Command guard
  R3: 성공 분기 - 이력 INSERT  (branch_from=R2)     → Aggregate creation Event
  R4: 실패 분기 - 오류 코드 SET (branch_from=R2)    → 별개 Command + Event
  R5..R10: R3 의 NEXT chain (guard_rule_id=R3)     → 후속 invariants
  R11..R15: R4 의 NEXT chain                       → 별개 분기 Commands

분해 결과:
  Aggregate "AuthHistory"
    invariants: R5~R10 statement
    events: R3 (AuthHistoryRecorded), R5..R10 의 UPDATE events
  Command "ProcessAuthResult"
    preconditions: [R1, R2]
    branches:
      success → emits AuthHistoryRecorded
      failure → emits AuthErrorRecorded (별개 Aggregate "AuthError" 또는 same)
  Policy: R10 의 coupled_domains=["order"] → "OnAuthSuccessNotifyOrder"
```

---

## §5 Traceability 그래프 — 영향도 분석

### 5.1 신규 관계

승격 시 자동 생성되는 traceability 엣지:

```
US 가 추적의 허브 (★ — 사용자 멘탈 모델)
  (UserStory)-[:PROMOTED_FROM {via:'task', source:'mapped'|'document_only'}]->(BpmTask)
  (UserStory)-[:SOURCED_FROM]->(Rule)            # ★ US 본문 구성한 BL 들 (N개)

US ← 다운스트림 ES 요소 (역추적 — "US 클릭 → 어떤 ES 가 만들어졌나")
  (Aggregate)-[:IMPLEMENTS]->(UserStory)         # ★ 이 Aggregate 가 실현하는 US
  (Command)-[:IMPLEMENTS]->(UserStory)           # ★
  (Event)-[:IMPLEMENTS]->(UserStory)             # ★ Command 의 US 상속
  (Policy)-[:IMPLEMENTS]->(UserStory)            # ★
  (ReadModel)-[:IMPLEMENTS]->(UserStory)         # ★

ES 노드 → BpmTask 직접 추적 (US 우회 경로)
  (Aggregate)-[:PROMOTED_FROM {via:'rules', rule_ids:[...]}]->(BpmTask)
  (Command)-[:PROMOTED_FROM]->(BpmTask)
  (Event)-[:PROMOTED_FROM {via:'aggregate_event', rule_id}]->(BpmTask)
  (Policy)-[:PROMOTED_FROM {via:'coupled_domain'}]->(BpmTask)
  (ReadModel)-[:PROMOTED_FROM]->(BpmTask)

ES 노드 → analyzer 코드 추적 (cross-DB / 같은 DB share 시 in-graph)
  (Aggregate)-[:DERIVED_FROM]->(Rule)            # rule_hash 기반 join
  (Aggregate)-[:GROUNDED_IN]->(Table)            # AFFECTS_TABLE root
  (Command)-[:PRECONDITION_BY]->(Rule)           # guard_rule_id chain Rules
  (Event)-[:DERIVED_FROM]->(Example)             # specific test case
  (ReadModel)-[:READS_FROM]->(Table)
  (Policy)-[:CROSSES]->(BoundedContext)          # source_bc + target_bc
  
검토 메모
  (Question)-[:ATTACHED_TO]->(BoundedContext)
  (Question)-[:RAISED_IN]->(FUNCTION)            # 원래 host
  
ES 그룹핑
  (BoundedContext)-[:HAS_USERSTORY]->(UserStory)
  (BoundedContext)-[:HAS_AGGREGATE]->(Aggregate)
  (BoundedContext)-[:HAS_POLICY]->(Policy)
  (BoundedContext)-[:HAS_READMODEL]->(ReadModel)
  (Aggregate)-[:HAS_COMMAND]->(Command)
  (Command)-[:EMITS]->(Event)
```

**왜 IMPLEMENTS + PROMOTED_FROM 두 엣지를 다?**: PROMOTED_FROM 은 "어느 BpmTask 에서 왔나" 단일 hop, IMPLEMENTS 는 "어느 US 를 실현하나" 의미적 관계. 한 BpmTask 에서 여러 US 가 분리되어 나오는 경우 (분기 task) 둘은 필요. Cypher 가 둘 다 traverse 하면 자연스럽게 정합.

### 5.2 영향도 분석 시나리오

**시나리오 A — 정방향: ES 노드 → 출처 코드**
> "이 Aggregate 의 invariant 는 어디 코드에서 왔나?"

```cypher
MATCH (a:Aggregate {id: $agg_id})-[:DERIVED_FROM]->(r:Rule)
MATCH (f:FUNCTION)-[hr:HAS_RULE]->(r)
OPTIONAL MATCH (r)-[:HAS_EXAMPLE]->(e:Example)
RETURN f.function_id, hr.local_id, r.statement,
       collect({given: e.given, when: e.when_, then: e.then_}) AS examples
```

**시나리오 B — 역방향: 코드 변경 → 영향받는 ES 노드**
> "Rule R3 의 statement 가 바뀌면 ES 모델에서 뭐가 영향받나?"

```cypher
MATCH (r:Rule {rule_hash: $hash})
OPTIONAL MATCH (a:Aggregate)-[:DERIVED_FROM]->(r)
OPTIONAL MATCH (c:Command)-[:PRECONDITION_BY]->(r)
OPTIONAL MATCH (e:Event)-[:DERIVED_FROM]->(:Example)<-[:HAS_EXAMPLE]-(r)
RETURN collect(DISTINCT a) AS aggregates,
       collect(DISTINCT c) AS commands,
       collect(DISTINCT e) AS events
```

**시나리오 C — 양방향: BC 변경 → 코드 영향**
> "이 BoundedContext 가 사라지면 어느 분석기 함수가 무관해지나?"

```cypher
MATCH (bc:BoundedContext {id: $bc_id})-[:HAS_AGGREGATE]->(a:Aggregate)
      -[:DERIVED_FROM]->(r:Rule)<-[:HAS_RULE]-(f:FUNCTION)
RETURN DISTINCT f.function_id, count(r) AS rules_in_bc
```

**시나리오 D — Task 매핑 변경 → 재승격 필요 ES 노드**
> "task1 의 매핑이 재탐색으로 변경됐다 — 어느 ES 노드를 재생성해야 하나?"

```cypher
MATCH (t:BpmTask {id: $task_id})<-[:PROMOTED_FROM]-(es)
RETURN labels(es)[0] AS type, es.id, es.name
// 결과 → 재승격 대상 노드 목록 (사용자 확인 후 재승격)
```

**시나리오 E — US 경유: "이 US 가 어떤 ES 요소를 만들었나" ★ (사용자 mental model)**
> UserStory 카드 클릭 → "이 US 가 어떤 BL 들로 구성됐고, 그 결과로 어떤 Aggregate / Command / Event / Policy / ReadModel 가 만들어졌나" 한 화면.

```cypher
MATCH (us:UserStory {id: $us_id})

// (1) 구성 BL 들 (US 본문 출처)
OPTIONAL MATCH (us)-[:SOURCED_FROM]->(r:Rule)
WITH us, collect(DISTINCT {
  rule_id: r.id, statement: r.title, fn: r.source_function
}) AS source_rules

// (2) 다운스트림 ES 요소들 (이 US 를 implements 하는 노드들)
OPTIONAL MATCH (es)-[:IMPLEMENTS]->(us)
WITH us, source_rules, collect(DISTINCT {
  type: labels(es)[0], id: es.id, name: es.name, displayName: es.displayName
}) AS implements

// (3) 상위 BpmTask + Process
OPTIONAL MATCH (us)-[:PROMOTED_FROM]->(t:BpmTask)<-[:HAS_TASK]-(p:BpmProcess)
RETURN us.id, us.role, us.action,
       p.name AS process,
       t.id AS task_id, t.name AS task_name,
       source_rules,
       implements
```

**시나리오 F — US 경유 역방향: "이 BL 의 변경이 어느 US 의 다운스트림 요소들을 흔드나"**
> Rule R3 의 statement 가 바뀌면 → 그 R3 가 SOURCED_FROM 인 US 들 → 그 US 를 IMPLEMENTS 하는 모든 ES 요소

```cypher
MATCH (r:Rule {rule_hash: $hash})
MATCH (us:UserStory)-[:SOURCED_FROM]->(r)
OPTIONAL MATCH (es)-[:IMPLEMENTS]->(us)
RETURN us.id, us.action,
       collect(DISTINCT {type: labels(es)[0], name: es.name}) AS impacted_es
```

### 5.3 기존 traceability UI 재활용 — 백엔드만 수정

**기존 자산 (그대로 재사용)**:
- 프론트: [InspectorPanel.vue:2284-2416](../../frontend/src/features/canvas/ui/InspectorPanel.vue#L2284) — "출처" 탭이 이미 풍부한 chain UI 구현
  - `DDD Node` → `Bounded Context` → `User Story` → `Business Logic` (흐름도 + 커플링 + GWT 아코디언) → `Function` (요약 + 코드 토글 + 테이블 컬럼)
  - 클릭 시 `GET /api/graph/traceability/{nodeId}` 자동 호출
  - chain[] 배열을 step.step 라벨로 분기 렌더 — 백엔드 응답 형태만 맞으면 그대로 동작
- 백엔드: [traceability.py:58-260](../../api/features/canvas_graph/routes/traceability.py#L58) — 라우터 + 응답 shape 그대로
- 라우터 prefix 는 `/api/graph` (확인됨)

**수정 필요 — 백엔드 Cypher 만**:
1. **`Business Logic` step Cypher 재작성** (라인 149 부근의 BL 쿼리):
   ```cypher
   -- 기존 (구스키마, 깨짐)
   MATCH (f)-[:HAS_BUSINESS_LOGIC]->(bl:BusinessLogic) WHERE f.function_id = $fid
   RETURN bl.sequence AS seq, bl.title AS title, bl.coupled_domain AS cd,
          bl.given AS given, bl.when AS wh, bl.then AS th

   -- 신스키마 + Phase 5 IMPLEMENTS 활용 (출처 US 의 SOURCED_FROM rule 만 한정)
   MATCH (us:UserStory {id: $us_id})-[:SOURCED_FROM]->(r:Rule)
   MATCH (f:FUNCTION)-[hr:HAS_RULE]->(r)
   OPTIONAL MATCH (r)-[:HAS_EXAMPLE]->(e:Example {is_boundary: false})
   WITH r, hr, f,
        head(collect(e)) AS canonical_e,    -- 대표 Example 1건
        collect(e) AS examples
   RETURN hr.local_id AS seq,                -- "R1", "R2" → BL[R1] 형식
          r.statement AS title,
          coalesce(hr.coupled_domains[0], '') AS cd,  -- list 첫 값 (또는 join)
          canonical_e.given AS given,
          canonical_e.when_ AS wh,
          canonical_e.then_ AS th,
          [x IN examples WHERE x.is_boundary | x.example_id] AS boundary_ids
   ORDER BY hr.local_id
   ```

2. **DDD Node → US 매핑에 IMPLEMENTS 우선** (라인 30-55, `_US_QUERIES`):
   ```cypher
   -- 신규: Aggregate/Command/Event/Policy/ReadModel 모두 IMPLEMENTS 로 통일
   MATCH (us:UserStory)<-[:IMPLEMENTS]-(n {id: $id})
   RETURN DISTINCT us.id, us.role, us.action, us.task_id AS src
   ```
   기존 `(:UserStory)-[:IMPLEMENTS]->(n)` 방향 (단수 IMPLEMENTS) 도 backward-compat 유지.

3. **Function step 의 source_unit_id 매칭**: Phase 5 가 생성한 `(US)-[:PROMOTED_FROM]->(BpmTask)` 의 `BpmTask.id` 를 src 로 사용 (US.task_id 또는 직접 traverse).

**프론트 최소 손질** (선택):
- step.step `'Business Logic'` 라벨은 그대로 두거나 `'Rules'` 로 rename — 데이터는 동일 형태 (`flow: [{seq, title, coupled_domain, given, when, then}]`)
- `seq` 가 정수 (구) → 문자열 R1/R2 (신) 로 바뀌므로 표시는 자동 (template 에서 `BL[{{ bl.seq }}]` → `R[{{ bl.seq }}]` 또는 그대로 `BL[R1]`)
- boundary example 표시 추가 (선택) — 위 쿼리의 `boundary_ids` 활용해 "경계값 케이스 N건" 배지

**작업 비용**: 백엔드 Cypher 2~3 곳 재작성 + 프론트 라벨 1줄 (선택). 새 컴포넌트 신규 작성 없음.

---

## §6 멱등성 + 재실행 정책

### 6.1 결정론 보장 부분
- Rule 분류 (§3.1) — 100% 결정론, 같은 입력 → 같은 분류
- Aggregate 멤버십 (root Table 공유) — 100% 결정론
- Question 부착 — 100% 결정론

### 6.2 비결정론 부분
- BC 그룹핑 (LLM 1회) — 같은 prompt 면 거의 같지만 LLM 변동 ±1 BC 가능
- ES 노드 이름/서술 (LLM) — 매번 다를 수 있음 (prompt 고정해도)

### 6.3 재실행 정책

**옵션 (선택)**: (C) 사용자 확인 후 wipe + 재생성
- 트리거 시 기존 ES 노드 존재 확인:
  - 0 개 → 즉시 진행
  - 1+ 개 → 모달 "기존 ES 모델을 재생성하시겠습니까? 사용자 수동 편집은 보존됩니다"
- 사용자 confirm 시:
  1. `clear_promoted_nodes(session_id)` — `(:UserStory|:Aggregate|:Command|:Event|:Policy|:ReadModel|:BoundedContext)` 중 `session_id` 매칭 노드만 wipe
  2. **단, manual override 마커가 있는 노드는 preserve** — `node.user_edited=true` 플래그 또는 별도 manual edge
  3. Phase 5 재실행
  4. 재실행 후 manual override 노드는 재생성 결과와 충돌 시 manual 우선

### 6.4 Manual override 마커
```
사용자가 캔버스에서 노드 편집 시:
  SET node.user_edited = true
  SET node.user_edited_at = datetime()

재실행 시:
  MERGE (n {id: $id, session_id: $sid}) ON CREATE SET ... ON MATCH SET ...
  WHERE n.user_edited IS NULL OR n.user_edited = false
  → 사용자 편집 노드는 SET 안 함
```

---

## §7 트리거 + UI

### 7.1 트리거
- **수동만** — `POST /api/ingest/hybrid/{sid}/promote-to-es`
- 위치: BPMN 탭 상단 또는 Navigator 의 BC 섹션 헤더 (현 구현 위치 유지)
- 사용자가 자신의 매핑 검토 끝낸 후 명시 클릭

### 7.2 UX 요구
- 진행 중 SSE 스트림 (Phase 1~4 와 동일 패턴):
  - "🔍 Aggregate 식별 중... (3/8)"
  - "🏷️ BoundedContext 명명 중..."
  - "⚖️ Policy 추출 중..."
  - "✅ 생성 완료: BC 3 / Aggregate 5 / Command 9 / Event 14 / Policy 2 / ReadModel 2"
- 완료 후 자동으로 Event Modeling 탭으로 전환
- 재실행 confirm 모달 (위 §6.3)

### 7.3 미해결 (별도 task)
- **버튼 스타일 polish** — 사용자 피드백: "버튼 스타일/위치가 부자연스럽고 촌스러움"
  - 본 PRD 범위 외, 별도 UI iteration 으로 정리
  - 후보: BPMN 탭 우측 상단 primary action / Navigator Process 섹션 위 / Footer fixed bar

---

## §8 검증 기준

### 8.1 zapamcom10060 기준 기대 출력 (3 process / 33 task / 51 rule / 8 매핑된 task)

| ES 요소 | 예상 개수 | 근거 |
|---|---|---|
| UserStory | 33~40 | task 33 + 분기 task 일부 ≥2 US |
| BoundedContext | 2~3 | 실시간인증 (Core) + 외부연동 (Supporting) + (선택) 공통 |
| Aggregate | 3~5 | AuthHistory + AuthError + (선택) ProcessLog (root Table 공유 군집) |
| Command | 8~10 | 매핑된 8 task × 평균 1 + 분기 추가 |
| Event | 12~16 | INSERT/UPDATE Rule 마다 1 (b000 의 8 매핑 rule + b200 의 7 + others) |
| Policy | 2~4 | coupled_domains 보유 17 rules → cross-BC 후보 |
| ReadModel | 1~2 | "원장등록 대상 조회" 등 read-only 매핑 task |
| Question (memo) | 23 | 그대로 보존 |

### 8.2 정합성 검증 쿼리
```cypher
// 1. 모든 Aggregate 가 정확히 1 BC 에 귀속
MATCH (a:Aggregate)
OPTIONAL MATCH (bc:BoundedContext)-[:HAS_AGGREGATE]->(a)
RETURN a.name, count(bc) AS bc_count
// expected: every count = 1

// 2. 매핑된 모든 task 가 1+ ES 노드 생성
MATCH (t:BpmTask)-[:REALIZED_BY]->(:Rule)
OPTIONAL MATCH (es)-[:PROMOTED_FROM]->(t)
WITH t, count(es) AS es_count
WHERE es_count = 0
RETURN t.id, t.name AS orphaned_task
// expected: empty

// 3. 매핑 0건 task 는 source="document_only" US 1개씩
MATCH (t:BpmTask) WHERE NOT (t)-[:REALIZED_BY]->()
OPTIONAL MATCH (us:UserStory {source: "document_only"})-[:PROMOTED_FROM]->(t)
RETURN t.id, count(us) AS us_count
// expected: every count = 1

// 4. 모든 Aggregate root Table 이 실제 analyzer Table 노드를 가리킴
MATCH (a:Aggregate)-[:GROUNDED_IN]->(t:Table)
RETURN a.name, t.name
// expected: 모든 Aggregate 가 Table 매칭됨

// 5. cross-BC Policy 의 source_bc != target_bc
MATCH (p:Policy {kind: 'cross_bc'})-[:CROSSES]->(bc:BoundedContext)
WITH p, collect(bc.id) AS bcs
WHERE size(bcs) >= 2
RETURN p.name, bcs
// expected: cross-BC policy 마다 ≥2 BC 결과
```

### 8.3 Traceability 검증
```cypher
// (1) 모든 ES 노드가 어느 BpmTask 에서 왔는지 추적 가능
MATCH (es) WHERE es:Aggregate OR es:Command OR es:Event OR es:Policy OR es:ReadModel OR es:UserStory
OPTIONAL MATCH (es)-[:PROMOTED_FROM]->(t:BpmTask)
WITH es, count(t) AS task_count
WHERE task_count = 0
RETURN labels(es)[0], es.id, es.name AS untracked
// expected: empty

// (2) ★ US 경유 추적 — 매핑 보유 task 의 모든 다운스트림 ES 노드는 IMPLEMENTS 필수
MATCH (es) WHERE es:Aggregate OR es:Command OR es:Event OR es:Policy OR es:ReadModel
MATCH (es)-[:PROMOTED_FROM]->(t:BpmTask)-[:REALIZED_BY]->(:Rule)
OPTIONAL MATCH (es)-[:IMPLEMENTS]->(:UserStory)
WITH es, count{(es)-[:IMPLEMENTS]->()} AS us_count
WHERE us_count = 0
RETURN labels(es)[0], es.id, es.name AS missing_implements
// expected: empty (매핑 보유 task 산출 ES 는 모두 1+ US 와 연결)

// (3) ★ US 가 SOURCED_FROM rule 한 묶음을 가져야 함 (매핑 보유 task 의 US 만)
MATCH (us:UserStory)-[:PROMOTED_FROM]->(t:BpmTask)-[:REALIZED_BY]->(r:Rule)
WITH us, collect(DISTINCT r.id) AS task_rules
OPTIONAL MATCH (us)-[:SOURCED_FROM]->(sr:Rule)
WITH us, task_rules, collect(DISTINCT sr.id) AS sourced_rules
WHERE size(sourced_rules) = 0 OR sourced_rules <> task_rules
RETURN us.id, task_rules, sourced_rules AS mismatch
// expected: empty (US 의 SOURCED_FROM 집합 = Task 의 REALIZED_BY 집합)

// (4) document_only US 는 SOURCED_FROM 0 개, IMPLEMENTS 받는 노드 0 개
MATCH (us:UserStory {source: 'document_only'})
OPTIONAL MATCH (us)-[:SOURCED_FROM]->(r:Rule)
OPTIONAL MATCH (es)-[:IMPLEMENTS]->(us)
WITH us, count(r) AS sources, count(es) AS implementers
WHERE sources > 0 OR implementers > 0
RETURN us.id, sources, implementers AS unexpected
// expected: empty
```

### 8.4 멱등성 검증
- 같은 session 에 Phase 5 재실행 (manual override 없을 때) → ES 노드 개수 ±1 BC 이내, Aggregate/Command/Event 개수 동일
- manual override 노드는 재실행 전후 그대로 유지 (`user_edited=true` 마커 보존)

### 8.5 UX 검증
- 매핑된 8 task 클릭 → Inspector 에 "이 task 가 기여한 ES 요소 N개" 표시 (PROMOTED_FROM 역방향)
- ES 캔버스의 Aggregate 클릭 → traceability 패널에 "출처: function `b000_main_proc`, Rules R3·R5·R6 — 81% confidence" 표시
- 매핑 0건 task 의 US → "📄 문서 추론" 배지 + Aggregate/Event 없음 (정합)

---

## §9 구현 순서 + 의존 관계

```
[0. 입력 보강 (선결, §2.1)]
  - api/features/ingestion/hybrid/code_to_rules/rule_extractor.py 의 _QUERY 보강
  - api/features/ingestion/hybrid/contracts.py 의 RuleDTO/ExampleDTO 필드 추가
  - 검증: §2.1.4 실측 카운트 (guard 16, branch 12, NEXT 33, BRANCH 14, writes ≈26)
  - 통과 후에만 [1] 진입

[1. Cypher 매트릭스 구현]
  - api/features/ingestion/hybrid/event_storming_bridge/rule_classifier.py 신규
  - 위 §3.1 결정론 분류 함수들

[2. Task 분해 함수]
  - decompose_task() — §4.1
  - 의존: rule_classifier

[3. 세션 단위 통합]
  - merge_decompositions() + LLM steps (BC 그룹핑, 이름 명명)
  - 의존: decompose_task

[4. Traceability 엣지 생성]
  - save_es_with_traceability() — §5.1 모든 PROMOTED_FROM/DERIVED_FROM 엣지
  - 의존: 통합 결과

[5. promote_to_es 재작성]
  - 기존 api/features/ingestion/hybrid/event_storming_bridge/promote_to_es.py 교체
  - 의존: 1~4

[6. 재실행 정책]
  - clear_promoted_nodes(session_id, preserve_manual=true)
  - 의존: 5

[7. SSE progress 이벤트]
  - 위 §7.2 progress 메시지 이벤트
  - 의존: 5

[8. Traceability route 확장]
  - api/features/canvas_graph/routes/traceability.py 신스키마 Cypher
  - 의존: 4 (관계가 먼저 있어야 traverse 가능)

[9. 검증]
  - §8.2~§8.5 쿼리 자동 실행 + 결과 비교

[별도 작업 (PRD 범위 외)]
  - UI 버튼 스타일 polish (§7.3)
  - Arbitration toast/strikethrough (§11.6 후속)
```

---

## §10 폐기 / 정리 대상

PRD 구현 시 동시 정리:

### 10.1 폐기 (제거)
- 기존 `Hybrid_Phase5_EventStorming_Promotion.md` — Phase 2.5/2.6 기반이라 entire 문서 deprecate (히스토리만 보존)
- `api/features/ingestion/hybrid/mapper/bc_identifier.py` — 이미 unwired, 파일 삭제
- `api/features/ingestion/hybrid/mapper/es_role_tagger.py` — 이미 unwired, 파일 삭제

### 10.1.1 보강 (선결, §2.1 참조)
- `api/features/ingestion/hybrid/code_to_rules/rule_extractor.py` `_QUERY` Cypher 확장 (guard_rule_id, branch_from, NEXT/BRANCH local_id, AFFECTS_TABLE op + raw `then_` JSON 보존)
- `api/features/ingestion/hybrid/contracts.py` — `RuleDTO` (`local_id`, `flow_id`, `guard_rule_id`, `branch_from`, `next_rule_local_ids`, `branch_rule_local_ids`) + `ExampleDTO` (`writes: list[dict]`) 필드 추가

### 10.2 재활용 vs 신설 — 명확화

> **중요**: legacy `workflow/phases/*` 의 **LLM 프롬프트, Pydantic 출력 스키마, Neo4j save 함수, 이름 정규화 헬퍼는 100% 재활용**. 신로직이 책임지는 건 **분해 알고리즘 + 입력 조립 + 호출 분기 + traceability 엣지** 뿐.

**재활용 (그대로 import)**:

| 자산 | 실재 위치 | 신로직에서 사용 |
|---|---|---|
| `IDENTIFY_BC_FROM_STORIES_PROMPT` (정의), `BoundedContextList` (스키마) | `event_storming/prompts.py` + `event_storming/structured_outputs.py` | BC 그룹핑 LLM 단계 |
| `EXTRACT_AGGREGATES_PROMPT`, `AggregateList` | `event_storming/prompts.py` + `event_storming/structured_outputs.py` | Aggregate 이름·구조 LLM (단 신 단축 프롬프트로 보강 가능 — PRD §3.2 의 "이름만" 모드) |
| `EXTRACT_COMMANDS_PROMPT`, `CommandList` | `event_storming/prompts.py` + `event_storming/structured_outputs.py` | Command displayName LLM |
| `EXTRACT_EVENTS_FROM_US_PROMPT` + `EventFromUSList` | `workflow/phases/events_from_user_stories.py` (둘 다 phases 안에 정의) | Event PastParticiple LLM |
| `IDENTIFY_POLICIES_PROMPT`, `PolicyList` | `event_storming/prompts.py` + `event_storming/structured_outputs.py` | Policy 명명 LLM (legacy `_name_cross_bc_policy` 가 더 단순한 cross-BC 단건 명명용) |
| `EXTRACT_READMODELS_PROMPT`, `ReadModelList` | `event_storming/prompts.py` + `event_storming/structured_outputs.py` | ReadModel LLM |
| `create_bounded_context`, `create_aggregate`, `create_command`, `create_event`, `create_policy`, `create_readmodel` | `event_storming/neo4j_ops/{bounded_contexts,aggregates,commands,events,policies,readmodels}.py` | 모든 노드 영속 |
| `get_neo4j_client()` | `event_storming/neo4j_client.py` | 위 create_* 메서드 보유 wrapper |
| `get_llm()` | `ingestion_llm_runtime.py` | LangChain LLM (`with_structured_output` 패턴) |
| `_name_cross_bc_policy` | `event_storming_bridge/promote_to_es.py` (현재) | 신 promote_to_es 가 흡수 |
| `dedup_key`, `canonicalize_role`, `canonicalize_action`, slug 헬퍼 | `workflow/utils/*` | 이름 정규화 |

> **legacy phase wrapper 함수** (`extract_aggregates_phase()` 등 `workflow/phases/*.py`) 는 **호출하지 않음**. 그 안의 프롬프트·스키마·LLM-호출 패턴은 reference 로만 사용. 신 layer 가 candidate dict 를 prompt args 로 직접 변환해 LLM 호출 + neo4j_ops.create_* 호출.

**신설 (PRD §3~§5 가 책임)** — 모두 `event_storming_bridge/` 안에 신설됨, 2026-05-06 구현 완료:

| 신규 모듈/함수 | 위치 | 책임 |
|---|---|---|
| `rule_classifier.py` | `event_storming_bridge/rule_classifier.py` | §3.1 결정론 분류 — Rule 동사 / Example.writes.op / coupled_domains 매트릭스 + guard chain propagation |
| `decompose_task()` / `merge_session_decompositions()` | `event_storming_bridge/decomposer.py` | §4.1 Task 단위 분해 + §4.2 세션 통합 (root Table 공유 Aggregate 합치기) |
| `name_session()` | `event_storming_bridge/naming.py` | §3.2 LLM 이름 부여 (BC 그룹핑 = legacy IDENTIFY_BC 프롬프트 재활용 + Aggregate/Command/Event/Policy/ReadModel 신 단축 프롬프트). Deterministic fallback 보장 |
| `save_named_session()` / `clear_promoted_nodes()` | `event_storming_bridge/persistence.py` | §5.1 모든 노드 MERGE + 26 종 traceability 엣지 (PROMOTED_FROM / IMPLEMENTS / SOURCED_FROM / DERIVED_FROM / GROUNDED_IN / PRECONDITION_BY / EMITS / HAS_*) + manual override 보존 |
| `hybrid_post_workflow_hook()` | `event_storming_bridge/promote_to_es.py` (재작성) | 위를 orchestrate — fetch → classify → decompose → merge → name → tag-orphan → wipe → persist → invariant check |

**Backwards-compat 유지**: `clear_promoted_nodes`, `ALL_PROMOTED_LABELS`, `hybrid_post_workflow_hook` export 모두 동일 — `router.py` / `ingestion_workflow_runner.py` 무수정.

**경계 명확화**:

```python
# 신 promote_to_es.py — orchestrate
async def promote_hybrid_to_es(session_id):
    # 1. 결정론 분해 (LLM 0회)
    decompositions = [decompose_task(t) for t in tasks]
    aggregates_raw = merge_session_decompositions(decompositions)
    
    # 2. LLM 단계 — legacy 프롬프트 그대로 import
    from api.features.ingestion.workflow.phases.aggregates import EXTRACT_AGGREGATES_PROMPT, AggregateList
    aggregates_named = await llm_name_aggregates(aggregates_raw, EXTRACT_AGGREGATES_PROMPT, AggregateList)
    
    # 3. 영속 — legacy save 함수 그대로
    from api.features.ingestion.event_storming.commands_create import create_aggregate
    for a in aggregates_named:
        create_aggregate(...)
    
    # 4. Traceability 엣지 — 신 함수
    save_es_with_traceability(decompositions)
```

**어떤 부분이 unwire 되나**:
- `workflow/phases/*.py` 의 **`extract_*_phase()` 함수** (workflow orchestrator) — hybrid 경로에서 호출 안 됨 (rfp/figma 만 쓰는 분기로 남거나, 추후 cleanup)
- `workflow/phases/*.py` 의 프롬프트·스키마·헬퍼 — 그대로 신 promote_to_es 가 import

**legacy `promote_to_es.py` (현재)**:
- `hybrid_post_workflow_hook` (354줄) — 신 promote_to_es 가 책임을 흡수하면서 사라짐. 단 cross-BC Policy LLM 명명 로직 (`_name_cross_bc_policy`) 은 신로직에 마이그레이션

### 10.3 보존
- `RuleDTO.context_cluster`, `Rule.es_role`, `Rule.es_role_confidence` — Phase 2.5/2.6 시절 필드. 신스키마에서 비어있지만 schema 호환 위해 유지

---

## §11 후속 (별도 PRD)

본 PRD 적용 후 추가 검토 가능 항목:
- **Question 자동 트리아지** — Question.text 가 정책 문서에서 답 가능한지 LLM 으로 1차 분류 (요구사항 PDF 와 매칭)
- **NEXT/BRANCH 흐름 시각화** — Aggregate 캔버스에 함수 내 Rule 흐름을 inline diagram 으로
- **coupled_domains 자동 BC 분리 제안** — 한 BC 내 Aggregate 가 다른 BC 의 Aggregate 를 자주 호출하면 BC 분리 제안
- **ES 모델 diff** — Phase 5 재실행 시 이전 모델과 비교 → "Aggregate X 가 사라짐, Event Y 가 추가됨" 사용자에게 표시
- **영향도 분석 UI** — 위 §5.2 시나리오들을 Inspector 에 expose

---

## §12 v4 구현 status (2026-05-08)

> 이 절은 v3.2 까지 구현 후 발견된 잔여 결함 + Inspector "출처" 탭 source-of-truth 정합 재설계 + PRD 생성 endpoint 보강 까지 포함하는 **이번 라운드 작업 정리**. 이전 핸드오프 (`Phase5_Phase6_HandOff.md`) 는 폐기됨 — 본 절 + [검증 보고서](Phase5_Phase6_Verification_Report.md) 가 sole source of truth.

### 12.1 닫힌 결함

| 결함 | 위치 | 수정 |
|---|---|---|
| Event HAS_PROPERTY = 0 (잔여) | `commands.py:790` events_by_agg helper Cypher 가 `RETURN DISTINCT e {...} ORDER BY e.name` 라 `DISTINCT` 후 변수 `e` 접근 불가 → SyntaxError → except 블록 → events_by_agg `{}` | `WITH DISTINCT e` 절 추가 + projection 변수 `evt.name` 으로 ORDER BY |
| Event 가 dict 인데 `getattr` 만 사용 | `properties.py:308-318` + `:429-441` 의 Event property prompt 구성에서 `getattr(evt, 'name', '')` 가 dict 에서 항상 빈 문자열 반환 → LLM 프롬프트 Event 섹션 비어 → property 미생성 | `isinstance(evt, dict)` 가드로 dict-aware 접근 |
| traceability BL 단계 누락 | `traceability.py:188-204` 의 BL Cypher 가 `(F)-[:HAS_RULE]->(shadow Rule)` 직매칭 — shadow Rule 은 FUNCTION 에 연결 안됨 → BL 단계 응답에서 빠짐 → Inspector 가 ES 단계 (DDD/BC/US) 까지만 표시 | shadow→analyzer Rule 매칭 (`source_function + statement`) 절 추가 후 FUNCTION 트래버스 |
| Inspector 출처 탭 의미 흐릿 | DDD Node + BC + US + BL + Function 5 단계 chain 으로 **출처가 아닌 조직화 노드 (DDD/BC) 가 반복** 노출. 노드 별 13 chains 표시 등 UX 문제 | sources-per-US 모델로 재설계 ([§12.3](#123-inspector-출처-탭-재설계)) |
| Inspector 가 노드 타입별 source emphasis 없음 | Aggregate 든 Event 든 동일 layout — 노드 의미 (Aggregate=Root Table, Event=GWT) 불부각 | 노드 타입별 primary source 박스 ([§12.4](#124-노드-타입별-primary-source-emphasis)) |

### 12.2 코드 변경 — backend / frontend

#### Backend

| 파일 | 변경 |
|---|---|
| [`workflow/phases/commands.py`](../../api/features/ingestion/workflow/phases/commands.py#L780) | `extract_commands_phase` 끝에 `events_by_agg` 빌드 헬퍼 추가 (Aggregate-HAS_COMMAND-Command-EMITS-Event chain). v4 Cypher syntax fix 포함 |
| [`workflow/phases/properties.py`](../../api/features/ingestion/workflow/phases/properties.py) | Event property prompt 구성 (single + chunked 두 path) 모두 `isinstance(evt, dict)` dict-aware 접근으로 통일 |
| [`event_storming/neo4j_ops/events.py`](../../api/features/ingestion/event_storming/neo4j_ops/events.py#L146) | `get_events_emitted_by_command` Cypher RETURN 에 `.key` 추가 (방어) |
| [`workflow/ingestion_workflow_context.py`](../../api/features/ingestion/workflow/ingestion_workflow_context.py#L195) | `sync_from_neo4j` Cypher RETURN 에 `.key` 추가 (resume 경로 방어) |
| [`canvas_graph/routes/traceability.py`](../../api/features/canvas_graph/routes/traceability.py) | (1) shadow→analyzer Rule 매칭 chain. (2) 응답 schema chains → sources-per-US 로 전면 재설계. (3) `rule.writes` 추가 (Example.AFFECTS_TABLE → table+op). (4) 신 endpoint `GET /traceability/userstory/{us_id}/source-rules` |
| [`prd_generation/prd_model_data.py`](../../api/features/prd_generation/prd_model_data.py) | `fetch_bc_data` Step 9 (UserStory + SOURCED_FROM + Example) + Step 10 (Question) 추가. `_attach_per_node_source_rules` 신설 — Aggregate/Command/Event 별 source rule rollup |
| [`prd_generation/prd_artifact_generation.py`](../../api/features/prd_generation/prd_artifact_generation.py) | render helper 6종: `render_source_rules_table`, `render_acceptance_tests`, `render_open_decisions`, `render_user_story_index`, `render_node_source_rules`, `render_node_source_examples`. `generate_bc_spec` 의 BC 헤더 직후 + Aggregate/Command/Event 블록 안에 wiring. `generate_claude_md` BC 리스트 + `generate_agent_config` 의 Source-of-truth grounding 가이드 절 |

#### Frontend

| 파일 | 변경 |
|---|---|
| [`canvas/ui/InspectorPanel.vue`](../../frontend/src/features/canvas/ui/InspectorPanel.vue) | 출처 탭 전면 재설계. chain rendering 제거, sources-per-US US 카드 list 로 교체. 단일 list (grounded + ungrounded 통합), 펼치면 BL 유무 분기 표시. 노드 타입별 primary source 박스 (Aggregate=Root Tables 3-tier fallback / Command·Event=Acceptance Test). 다크 테마 CSS 토큰 정합 |
| [`userStories/ui/UserStoryEditModal.vue`](../../frontend/src/features/userStories/ui/UserStoryEditModal.vue) | US 더블클릭 모달에 "Source Business Rules" 섹션 추가 (sourceRules.length > 0 가드). `/api/graph/traceability/userstory/{us_id}/source-rules` 호출 |
| [`requirementsIngestion/ui/RequirementsIngestionModal.vue`](../../frontend/src/features/requirementsIngestion/ui/RequirementsIngestionModal.vue) | 분석 데이터 stats 패널에 Question 카드 추가 (count > 0 일 때) |

### 12.3 Inspector "출처" 탭 재설계

핵심 framing 교정 (verification report §3.8 참조):

```
ES 노드 (Aggregate / Command / Event)
   │ IMPLEMENTS                ← 조직화 (출처가 아니라 어느 US 군집에 속함)
   ▼
UserStory                       ← gateway (narrative 컨테이너)
   │ SOURCED_FROM
   ▼
Rule (statement)                ← ★ 진짜 source 1 (의도)
   │ HAS_EXAMPLE
   ▼
Example (given/when_/then_)     ← ★ 진짜 source 2 (구체 시나리오)
   │ AFFECTS_TABLE
   ▼
Table (write op)                ← ★ 진짜 source 3 (DB 영향)
```

**기존 chain 모델 폐기 이유**:
- DDD Node + BC 가 매 chain 마다 반복 (예: Aggregate 가 13 US implements 시 13번 반복)
- "출처가 아닌 노드" (DDD Node, BC) 가 출처 list 에 표시되어 의미 혼선

**새 sources 모델**:
```json
{
  "node": { id, type, name },        // 클릭한 노드 (1번)
  "bc":   { id, name },              // 컨텍스트 (1번, 출처 아님)
  "sources": [                        // 진짜 출처: US 별
    {
      "us": { id, role, action },
      "rules": [{ seq, statement, given, when, then, writes, function_id }],
      "functions": [{ name, location, code, tables }]
    }
  ]
}
```

UI: 단일 US 카드 list. 펼치면 rules + function 표시. BL 매핑 없는 US 는 opacity 78% + "📄 매핑된 BL 없음 — BPM Task 자연어 설명만 source" 한 줄.

### 12.4 노드 타입별 primary source emphasis

각 노드 타입의 의미적 source 가 다름:

| 노드 | Primary Source 박스 | 데이터 소스 |
|---|---|---|
| Aggregate | 📊 **Root Tables** — 영속되는 DB 테이블 + 컬럼 + INSERT/UPDATE/DELETE | 3-tier: Example.AFFECTS_TABLE writes (best) → FUNCTION.WRITES → FUNCTION.READS (fallback) |
| Command | 🎯 **Acceptance Test** — 입력 + when + result | canonical Example given/when/then. **Rule.statement 가 헤더에서 의미적 condition 역할** (Example.when_ 가 phase 명일 때 보완) |
| Event | 🎯 **Acceptance Test** — full BDD GWT | 동일 |
| Policy / ReadModel | (primary 박스 없음, rules+functions 만) | — |

색상 코드: INSERT=emerald, UPDATE=amber, DELETE=red, READS=blue (다크 테마 정합).

### 12.5 검증 결과 — 핵심 수치

[검증 보고서](Phase5_Phase6_Verification_Report.md) 의 종합 audit (zapamcom10060 fixture):

| 검증 영역 | 결과 |
|---|---|
| 분석기 무손상 | FUNCTION 10 / Rule 116 (analyzer 59 + shadow 57) / Example 87 / AFFECTS_TABLE 26 ✅ |
| BPM ↔ BL 매핑 | 9 task / 29 REALIZED_BY edges / 12 distinct analyzer Rules matched (17 shadow Rule 은 분석기 FUNCTION 누락으로 매칭 실패) |
| US 생성 | 34 US (BL 매핑 11, BL 없음 23 — 0-rule task 유래) |
| Property 영속 | Aggregate 33 / Command 82 / **Event 75** / ReadModel 109 (Event 0 였던 결함 회복) |
| GWT thenFieldValues | **125 testCases 중 113 (90%)** schema-bound 채워짐 (이전 0%) |
| 의미 정합성 | Aggregate.invariants 가 Rule.statement 의 의도 일반화 (수동 sample 검증) |

### 12.6 알려진 한계 (architect 측 처리 외)

- **분석기 FUNCTION 노드 누락**: dbio 함수들 (b200/b205/b210/b400/b410) 이 FUNCTION 노드로 등록 안 됨 → 17 shadow Rule 의 analyzer 매칭 실패. 분석기 측 (robo-data-analyzer) 보강 필요
- **Example.when_ 의 phase-level 표현**: a000_input_validation 의 Example.when_ 이 모두 "입력값 검증" 같은 phase 명. 분석기 raw 데이터 한계 — Inspector 는 Rule.statement 헤더로 보완
- **0-rule task US**: 23/34 US 가 BPM Task description 만으로 생성 (조회/검증 task — 분석기가 read-only 함수 깊이 분석 못 함). PRD spec 에 "BL 없는 US" 로 표시됨

### 12.7 잔여 작업 (선택)

- **DERIVED_FROM / PRECONDITION_BY 엣지 영속** — 현 구현은 IMPLEMENTS-via-US 우회로 충분, 별도 영속 안 함. Phase 6 PRD §4 inject 의 fallback Cypher 가 이 우회를 활용
- **Question.ATTACHED_TO 부분 커버리지** — 4개 중 1개만 BC attach. promote_to_es.py fallback 절 강화 가능
- **decomposer / naming / persistence 모듈 cleanup** — Phase 5 augment-only 전환으로 미사용. Phase 6 본 구현 후 별도 PR 가능

---

*v1 작성: 2026-05-04 / v4 구현 + 검증 + 문서 통합: 2026-05-08*
