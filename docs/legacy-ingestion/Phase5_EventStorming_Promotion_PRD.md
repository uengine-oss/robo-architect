# Phase 5 — Event Storming Promotion PRD

> **작성일**: 2026-05-04
> **상태**: 설계 — 구현 미착수
> **선결**: §10 (analyzer 신스키마 적용), §11 (탐색 비용 최적화) 완료
> **참조 문서**: `Hybrid_Ingestion_Architecture.md` §11, `2026-04-22-BusinessLogic-노드-구조변경-아키텍트안내.md`
> **선행 문서**: `Hybrid_Phase5_EventStorming_Promotion.md` (Phase 2.5/2.6 기반, **폐기 예정**)

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

Phase 5 가 시작될 때 그래프 상태 (zapamcom10060 기준 실측):

| 노드 / 관계 | 개수 | 용도 |
|---|---|---|
| `BpmProcess` (`session_id` 보유) | 3 | BC 후보 군집 시작점 |
| `BpmTask` | 33 | US + Aggregate/Command/Event 분해 단위 |
| `BpmActor` | 2 | UserStory.role |
| `(BpmTask)-[:REALIZED_BY]->(Rule)` | 29 (8/33 task) | ES 요소 분해 입력 |
| `Rule` (analyzer, no session_id) | 51 | rule.statement = ES 요소 의도 |
| `Example` (analyzer) | 108 | GWT + writes[] = AFFECTS_TABLE |
| `(Rule)-[:HAS_EXAMPLE]->(Example)` | 108 | 1:N |
| `(Example)-[:AFFECTS_TABLE {op}]->(Table)` | 34 | Aggregate root 결정 신호 |
| `(FUNCTION)-[hr:HAS_RULE]->(Rule)` | 51 | hr 속성에 분기·흐름 메타 |
| `Question` (analyzer) | 23 | 검토 메모 |
| `(FUNCTION)-[:HAS_QUESTION]->(Question)` | 23 | BC 검토 메모 부착 |
| `(Rule)-[:NEXT]->(Rule)` | 27 | 함수 내 메인 시나리오 흐름 |
| `(Rule)-[:BRANCH]->(Rule)` | 12 | if/else 갈래 = Policy 분기 후보 |
| `(BpmTask)-[:SOURCED_FROM]->(DocumentPassage)` | Phase 4.1 산출 | 문서 근거 |

**Rule 매핑 분포 (현 실측)**: 8 tasks 가 1+ 매핑 (8/7/5/3/3/1/1/1), 25 tasks 0 매핑.

---

## §3 신스키마 → ES 요소 매핑 매트릭스

각 분석기 메타 정보를 ES 요소 판정 신호로 변환:

### 3.1 결정론 신호 (LLM 호출 없이 분류)

| 분석기 정보 | ES 매핑 | 판정 규칙 |
|---|---|---|
| `Example.then_.writes[].op = "INSERT"` | **Aggregate creation Event** | 결정론 — 해당 Rule 1개당 1 Event |
| `Example.then_.writes[].op = "UPDATE"` | **Aggregate state mutation invariant** | 결정론 — Rule.statement 가 invariant 본문 |
| `Example.then_.writes[].op = "DELETE"` | **Aggregate removal Event** | 결정론 |
| `Example.then_.writes` empty + (FUNCTION)-[:READS]->(Table) 존재 | **ReadModel query** | 결정론 |
| `Rule.statement` 동사 매칭 `^(검증|거부|판정|확인|체크)` | **Command precondition** | 정규식 |
| `HAS_RULE.guard_rule_id` 보유 | **Command precondition chain** | R2.guard=R1 → Command(R2) 의 precondition 에 R1 statement 포함 |
| `HAS_RULE.branch_from` 보유 | **별개 Command 분기** | R3.branch_from=R2 → R2 fail 시 R3 트리거 (별도 Command 후보) |
| `HAS_RULE.coupled_domains[]` non-empty | **Cross-BC Policy** | 자기 Aggregate 영역을 벗어난 영향 → Policy 강력 후보 |
| `Example.is_boundary = true` | **Command acceptance test (GWT)** | 경계값 = invariant 검증 케이스 |
| 같은 root Table (`AFFECTS_TABLE` 도착점) 공유하는 Rule 군 | **같은 Aggregate** | Aggregate 멤버십 결정 |
| 같은 `HAS_RULE.flow_id` (e.g., "2-1", "2-2") 공유 | **같은 Aggregate / 같은 분기** | 분기 묶음 |
| `(Rule)-[:NEXT]->(Rule)` chain | **Saga / Process flow** | 함수 내 시나리오 순서 |
| `(Rule)-[:BRANCH]->(Rule)` | **Policy 트리거 분기** | 한 Rule 의 결과로 다른 Rule path 트리거 |
| `Question` | **검토 메모 sticker** | 그대로 BC 에 부착, LLM 거치지 않음 |

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
     - emits = bucket["aggregate_invariant" + "_creation" + "_removal"] 의 Rules → 각 Event
     - branch_from 보유 Rule 군 별로 별도 Command (분기 명령)
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
  - "✅ 승격 완료: BC 3 / Aggregate 5 / Command 9 / Event 14 / Policy 2 / ReadModel 2"
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
[1. Cypher 매트릭스 구현]  ← 시작점
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

### 10.2 재활용 vs 신설 — 명확화

> **중요**: legacy `workflow/phases/*` 의 **LLM 프롬프트, Pydantic 출력 스키마, Neo4j save 함수, 이름 정규화 헬퍼는 100% 재활용**. 신로직이 책임지는 건 **분해 알고리즘 + 입력 조립 + 호출 분기 + traceability 엣지** 뿐.

**재활용 (그대로 import)**:

| 자산 | 위치 | 신로직에서 사용 |
|---|---|---|
| `IDENTIFY_BC_FROM_STORIES_PROMPT` + `BCList` 스키마 | `workflow/phases/bounded_contexts.py` | BC 그룹핑 LLM 단계 |
| `EXTRACT_AGGREGATES_PROMPT` + `AggregateList` | `workflow/phases/aggregates.py` | Aggregate 이름·구조 LLM |
| `EXTRACT_COMMANDS_PROMPT` + `CommandList` | `workflow/phases/commands.py` | Command displayName LLM |
| `EXTRACT_EVENTS_FROM_US_PROMPT` + `EventFromUSList` | `workflow/phases/events_from_user_stories.py` | Event PastParticiple LLM |
| `IDENTIFY_POLICIES_PROMPT` + `PolicyList` | `workflow/phases/policies.py` | Policy 명명 LLM |
| `EXTRACT_READMODELS_PROMPT` + `ReadModelList` | `workflow/phases/readmodels.py` | ReadModel LLM |
| `*_PROPERTIES_PROMPT` | `workflow/phases/properties.py` | 노드 프로퍼티 LLM |
| `GENERATE_GWT_PROMPT` | `workflow/phases/gwt.py` | GWT 본문 LLM |
| `UI_WIREFRAME_PROMPT` | `workflow/phases/ui_wireframes.py` | UI 생성 LLM |
| `create_bounded_context`, `create_aggregate`, `create_command`, `create_event`, `create_policy`, `create_readmodel` | `event_storming/` ops | 모든 노드 영속 |
| `dedup_key`, `canonicalize_role`, `canonicalize_action`, slug 헬퍼 | `workflow/utils/*` | 이름 정규화 |

**신설 (PRD §3~§5 가 책임)**:

| 신규 모듈/함수 | 책임 |
|---|---|
| `rule_classifier.py` | §3.1 결정론 분류 — Rule 동사 / Example.writes.op / coupled_domains 매트릭스 |
| `decompose_task()` | §4.1 Task 단위 분해 (Aggregate/Command/Event/Policy/ReadModel 후보 + US 와의 IMPLEMENTS) |
| `merge_session_decompositions()` | §4.2 세션 통합 (root Table 공유 Aggregate 합치기) |
| `save_es_with_traceability()` | §5.1 PROMOTED_FROM / IMPLEMENTS / SOURCED_FROM / DERIVED_FROM 엣지 생성 |
| 신 `promote_to_es.py` | 위를 orchestrate — 각 LLM 단계는 legacy 프롬프트 호출, 입력은 정제된 candidate dict |

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

*작성일: 2026-05-04 — Phase 5 Event Storming Promotion PRD v1*
