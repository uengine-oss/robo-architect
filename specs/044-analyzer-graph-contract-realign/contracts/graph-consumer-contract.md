# Contract: analyzer 그래프 소비자 계약 (권위 단일 문서)

**역할**: architect(소비자)가 analyzer(생산자) Neo4j 그래프를 읽을 때의 **단일 권위 계약**. 생산자 현행 출력 + 소비자 실제 동작과 100% 일치해야 함(FR-006/SC-005). spec 036의 `internal-mapper-contract.md`는 본 문서로 **대체·정정**(stale 표기 폐기).

**불변 전제**: 생산자(analyzer) 출력은 고정 기준(본 작업서 변경 0). 소비자만 본 계약에 맞춘다.

## C1. 식별·라벨·대소문자
- 노드 자기식별 = **`id`** (모든 종류). 폐기키 읽기 금지: `function_id, module_id, variable_id, fqn, example_id, rule_hash, procedure_name, moduleStereotype, file_name`.
- 라벨 = **단일 UPPER_SNAKE = antlr 타입**. 역할(호출가능/그릇)은 **타입에서 파생**(라벨 아님). 예외 = 외부 stub `:FUNCTION:EXTERNAL`/`:MODULE:EXTERNAL`.
- 소비자 자체 세션노드(`:Rule/:Command/:Event/:Aggregate/:Policy {session_id}`)는 PascalCase 유지 = **본 계약 비대상**. 생산자 노드는 `session_id IS NULL`로 구분.

## C2. 비즈니스로직 (framework·dbms 동일)
- `:RULE {id, statement}` / `:EXAMPLE {id, given, when_, then_, description}` / `:QUESTION {id, text, reason}`.
- `:EXAMPLE`에 **`is_boundary` 없음** — 인라인 `{is_boundary:false}` 매칭 금지. 대표예시는 `example_id` 정렬 폴백.
- `HAS_RULE` rel 속성 = **`local_rule_id`, `flow_id`, `coupled_domains`** 뿐. `local_id/guard_rule_id/branch_from` **없음**.

## C3. 룰 흐름 (도출)
- `local_id` ≔ `HAS_RULE.local_rule_id`.
- 분기부모 `branch_from(r)` ≔ `(parent)-[:BRANCH]->(r)` 의 parent `local_rule_id`.
- 선행조건 `guard_rule_id(r)` ≔ `(prev)-[:NEXT]->(r)` 의 prev `local_rule_id`.
- NEXT/BRANCH(rule)는 `owner_id`로 qualify, 끝점은 같은 오너의 HAS_RULE `local_rule_id`로 식별.

## C4. 오퍼레이션 단위 (framework·dbms 통일 규칙) ★
- **정의**: 룰/예시/질문의 논리적 오너 = "그것을 감싸는 가장 가까운 **루틴**(라벨 ∈ `{FUNCTION,PROCEDURE,METHOD,TRIGGER}`)".
- **해석**: 룰 오너 노드 n →
  - n이 루틴이면 n (framework: 항상 여기, 0칸).
  - 아니면 `(op)-[:PARENT_OF*1..]->(n)` 중 op가 루틴인 **가장 가까운** op (dbms 구문 → 상위 프로시저).
- **사용**: 소비자의 식별(`op.id`)·이름·`source_function`(그룹핑 키)·매칭요약(`op.summary`)은 **이 op에서** 취한다. 구문 노드의 `name=""`/구문요약을 직접 쓰지 않는다.
- **모듈(파일/클래스)은 단위 아님** — `parent_module`은 보조 메타로만.

## C5. 테이블 영향 (하향 수집)
- 오퍼레이션 op의 READS/WRITES ≔ `(op)-[:PARENT_OF*0..]->(d)-[:READS|WRITES]->(:TABLE)` 합집합. (dbms: DML이 자식 구문에 부착되므로 자손까지 수집. framework: 자식 없어 op 자신만.)
- `:TABLE {name}`로 표시. `READS|WRITES` rel `op`/`dml` 속성 사용. `(:EXAMPLE)-[:AFFECTS_TABLE {op}]->(:TABLE {name})`는 이름매칭.

## C6. 컨테이너/모듈
- `(m) WHERE m:FILE OR m:CLASS OR m:INTERFACE OR m:RECORD` → `m.id, m.name, m.summary, m.stereotype`. (폐기 폴백 `f.fqn/f.moduleStereotype` 금지.)

## C7. 관측성
- 소비자→생산자 엣지 MERGE가 매칭 0이면 **경고 로그**(조용한 no-op 금지).

## C8. 회귀 게이트
- 본 계약의 C4/C5 적용 후 **framework 경로 동작 불변**(0칸 상승·자식 없음). dbms 경로에서만 신규 상승/수집이 발생.

---
### 부록: 소비처 정합 대상 파일(본 계약 적용)
`code_to_rules/rule_extractor.py`, `mapper/{owner_resolver(신규),rule_context,module_retriever,glossary_extractor,agent_validator}.py`, `bpm_context_builder.py`, `event_storming_bridge/{rule_classifier,decomposer,promote_to_es}.py`, `canvas_graph/routes/traceability.py`, `prd_generation/prd_model_data.py`, 프론트 `RequirementsIngestionModal.vue`, robo-data-frontend 루틴 룰표시.
