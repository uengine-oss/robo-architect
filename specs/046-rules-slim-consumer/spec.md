# Feature Specification: 룰 슬림 계약 소비자 정합 (rules-slim-consumer)

**Feature Branch**: `046-rules-slim-consumer`

**Created**: 2026-07-01

**Status**: Draft

**Input**: analyzer spec 039(code_rules_examples 응답구조 최소화)로 소멸한 그래프 계약 요소를 architect 하이브리드 코드-인제스천 소비자가 정합. 044 계약 C2(부분)·C3를 supersede.

## 배경 (Why)

analyzer(생산자)가 코드분석 3분할 중 분할③(`code_rules_examples`)의 LLM 응답을 최소화하면서 architect(소비자)가 읽던 그래프 계약에서 다음이 **소멸**했다:

1. `HAS_RULE` 엣지의 `flow_id`·`local_rule_id` 속성
2. 룰→룰 `NEXT`/`BRANCH` 엣지 (`BRANCH` rel 타입 자체 폐기 — 구문 실행흐름 `NEXT`=StatementNext는 유지)
3. `EXAMPLE` 노드의 `description` 속성

이 요소들은 룰의 **흐름(flow) 구조**(순서·분기·선행조건)를 소비자에 전달하던 것이다. analyzer는 흐름 정보가 LLM 응답 폭주·헤맴의 원인이고 순서/분기 의미는 이미 `statement` 텍스트와 예시에 담겨 있다고 판단해 제거했다. 따라서 소비자는 이 흐름 계약에 대한 **의존을 걷어내고**, 그 흐름을 재구성/소비하던 로직을 함께 제거해야 한다.

**영향 국소성(전수 확인)**: 영향은 analyzer 그래프를 소비하는 단일 루트(`api/features/ingestion/hybrid/`)에 갇혀 있다. 제거 필드는 `save_rules`가 애초에 `:Rule` 세션노드에 영속화하지 않아 되읽기 의존이 없고, 문서→BPM·매퍼·캔버스·PRD 루트의 동명 심볼(`BpmTask.description`, BPMN `flow` id 등)은 무관하다.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 하이브리드 인제스천이 슬림 그래프에서 무오류 동작 (Priority: P1)

레거시 코드 분석 그래프(analyzer 산출)를 입력으로 하이브리드 인제스천을 실행하면, 흐름 계약(flow_id/룰NEXT/BRANCH/EXAMPLE.description)이 사라진 상태에서도 **크래시·조용한 실패 없이** Business Rule(GWT)을 추출하고 이벤트스토밍 승격까지 완주한다.

**Why this priority**: 계약 소멸이 소비자를 깨지 않는 것이 이 작업의 존재 이유. 이것만 충족돼도 파이프라인이 산다.

**Independent Test**: framework 전략(예: zapamcom) 재인제스천을 돌려 Rule 추출·저장·ES 승격이 오류 로그 0으로 완료되는지 확인.

**Acceptance Scenarios**:

1. **Given** analyzer가 슬림 계약으로 산출한 framework 그래프, **When** 하이브리드 인제스천을 실행, **Then** Rule 추출 개수·GWT·AFFECTS_TABLE writes·QUESTION이 정상이고 오류 0.
2. **Given** analyzer가 슬림 계약으로 산출한 dbms 그래프(룰이 자식 구문 노드에 분산), **When** 하이브리드 인제스천을 실행, **Then** 각 룰이 상위 **루틴**(PROCEDURE/FUNCTION 등)에 귀속되어 추출되고 오류 0.
3. **Given** 흐름 계약이 없는 그래프, **When** Rule을 추출, **Then** 룰 식별자가 `(function, statement)` 기준으로 안정적으로 부여되고 중복 없이 dedup된다.

### User Story 2 - 흐름 의존 로직·데드코드 제거로 소비자 정합 (Priority: P1)

소비자 코드에서 flow_id/guard/branch/local_id/EXAMPLE.description을 읽거나 재구성하던 로직과, 그 흐름 로직이 존재이유였던 **미배선(데드) 이벤트스토밍 결정론 클러스터**가 코드베이스에서 사라진다.

**Why this priority**: 원칙(수정=탈바꿈, 영향0 데드=통째 폐기). 껍데기 필드/데드 파일이 남으면 6개월 뒤 오독·유지보수 부채.

**Independent Test**: 제거 심볼(`flow_id`·`guard_rule_id`·`branch_from`·`next_rule_local_ids`·`branch_rule_local_ids`·`local_id`(룰)·`ExampleDTO.description`)을 전수 grep해 소비자 코드 잔재 0. 삭제된 데드 파일을 import하는 곳 0.

**Acceptance Scenarios**:

1. **Given** 정합 완료, **When** 제거 심볼을 전수 grep, **Then** 소비자 실코드(주석 포함) 잔재 0.
2. **Given** 데드 ES 클러스터 삭제, **When** LIVE 승격 경로(`promote_to_es`) 및 앱 부팅, **Then** import 오류 0(클러스터가 어디에서도 참조되지 않음).

### User Story 3 - 계약 문서·프론트 표시 정합 (Priority: P2)

권위 계약 문서(044 graph-consumer-contract)가 슬림 계약을 반영하고, 프론트의 룰 흐름 잔재 표시가 제거된다.

**Why this priority**: 계약 문서는 소비자 정합의 단일 진실. 프론트 배지는 사용자 노출이나 소량.

**Independent Test**: 044 계약 C2/C3가 본 스펙으로 supersede 표기됨. 프론트 UserStoryDetail에 `local_id` 배지 없음.

**Acceptance Scenarios**:

1. **Given** 044 계약 문서, **When** 열람, **Then** C2(EXAMPLE.description·HAS_RULE.flow_id/local_rule_id)·C3(룰 흐름 도출)이 046으로 대체됨이 명시되고 C4/C5는 불변.
2. **Given** UserStory 상세 화면, **When** 렌더, **Then** 소멸한 `local_id` 순번 배지가 표시되지 않고 나머지 표시는 정상.

### Edge Cases

- 한 루틴 아래 같은 `statement`가 여러 자식 구문에 붙는 dbms 상황: `(routine, statement)` 식별자로 dedup되어 RuleDTO 1개로 수렴(같은 룰이므로 정상).
- 흐름 로직을 소비하던 데드 클러스터를 삭제해도 LIVE 경로가 이를 참조하지 않으므로 런타임/부팅 영향 0.
- 프론트가 `local_id` 없는 RuleDTO를 받을 때: 순번 배지만 사라지고 GWT/statement 등 나머지는 정상.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 소비자 DTO(`RuleDTO`)는 `local_id`·`flow_id`·`guard_rule_id`·`branch_from`·`next_rule_local_ids`·`branch_rule_local_ids` 필드를 **더 이상 보유하지 않는다**. `ExampleDTO`는 `description` 필드를 보유하지 않는다.
- **FR-002**: Rule 추출은 그래프에서 흐름 속성(`HAS_RULE.flow_id`/`local_rule_id`)·룰 `NEXT`/`BRANCH` 엣지·`EXAMPLE.description`을 **읽지 않는다**.
- **FR-003**: 룰 식별자는 `(function_id, statement)`로 결정론적·안정적으로 부여되어야 하며, 동일 (function, statement)는 하나의 RuleDTO로 dedup된다.
- **FR-004**: dbms 그래프에서 룰이 자식 구문 노드에 분산돼도 각 룰은 **가장 가까운 상위 루틴**(라벨 ∈ {FUNCTION, PROCEDURE, METHOD, TRIGGER})에 귀속되어 추출된다(044 C4 유지). framework 경로는 동작 불변(무회귀).
- **FR-005**: LLM 컨텍스트 빌더(`bpm_context_builder`)는 흐름 요소(local_id 태그·guard_rule_id·branch_from)를 컨텍스트에 넣지 않는다. 유지 요소(statement·AFFECTS_TABLE writes·coupled_domains·GWT)는 그대로 제공한다.
- **FR-006**: 흐름 로직이 존재이유였던 **미배선 데드 이벤트스토밍 결정론 클러스터**(rule_classifier·decomposer·naming·persistence)는 통째 삭제된다. 삭제 전 어떤 LIVE 경로도 이를 참조하지 않음이 확인되어야 한다.
- **FR-007**: 권위 계약 문서(044 graph-consumer-contract)는 C2(EXAMPLE.description·HAS_RULE.flow_id/local_rule_id 부분)·C3(룰 흐름 도출 전체)이 046으로 supersede됨을 명시한다. C4/C5는 불변.
- **FR-008**: 프론트 UserStory 상세의 `local_id` 순번 배지가 제거된다. 그 외 룰 표시는 불변.
- **FR-009**: 제거·삭제 후 어떤 조용한 실패(빈 결과 삼킴)도 없어야 한다 — 계약 소멸은 소비자를 깨지 않고 graceful하게 흡수된다.

### Key Entities

- **RuleDTO**: 소비자 룰 표현. 유지 속성 = id·given·when·then·title(statement)·source_function·source_module·confidence·examples·coupled_domains. 제거 = 흐름 6필드.
- **ExampleDTO**: 룰의 구체 예시. 유지 = example_id·given·when_·then_·is_boundary·writes(AFFECTS_TABLE). 제거 = description.
- **오퍼레이션 단위(루틴)**: 룰의 논리적 오너(044 C4). dbms 구문→상위 프로시저 복원의 기준. 본 스펙에서 불변.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 제거 심볼 전수 grep 시 소비자 실코드(주석 포함) 잔재 **0건**.
- **SC-002**: 삭제된 데드 클러스터 4파일을 import하는 코드 **0건**, 앱 부팅·`promote_to_es` 경로 import 오류 **0건**.
- **SC-003**: framework 재인제스천에서 Rule/Example/AFFECTS_TABLE/QUESTION 개수·GWT가 정합 전 대비 **무회귀**(LLM 런변동 제외)이고 오류 로그 **0건**.
- **SC-004**: dbms 재인제스천에서 룰이 상위 루틴에 귀속되어 추출되고 오류 로그 **0건**.
- **SC-005**: 044 계약 문서의 C2/C3가 046 supersede로 정확히 표기되고, 소비자 코드와 계약 문서가 100% 일치.

## Assumptions

- analyzer는 이미 슬림 계약으로 산출한다(spec 039 생산자 완료·검증). 본 스펙은 소비자만 정합한다.
- 데드 ES 클러스터(rule_classifier·decomposer·naming·persistence)는 LIVE 승격 경로(`promote_to_es`, LLM 기반)가 전혀 임포트하지 않는 폐쇄 데드 섬이다(전수 확인). 향후 재도입 필요 시 git 이력에서 복원 가능.
- 제거 필드는 `:Rule` 세션노드에 영속화되지 않으므로 되읽기 소비자 영향이 없다.
- 재인제스천 LLM = frentis(qwen SGLang) config 유지.
