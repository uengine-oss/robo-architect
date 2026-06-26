# Phase 1 Data Model: analyzer 그래프 소비 계약

소비자(architect)가 의존하는 **생산자(analyzer) 현행 출력**의 데이터모델. 본 작업은 이 모델을 변경하지 않고 **소비자를 여기에 맞춘다**.

## 노드 (생산자 적재 = 읽기 대상)

| 노드 종류 | 라벨(단일 UPPER_SNAKE) | 식별 | 소비자가 읽는 주요 속성 |
|---|---|---|---|
| 컨테이너 | `:FILE` `:CLASS` `:INTERFACE` `:RECORD` | `id` | `id, name, summary, stereotype` |
| 루틴(호출가능) | `:FUNCTION` `:PROCEDURE` `:METHOD` `:TRIGGER` | `id` | `id, name, summary, stereotype, file_path, start_line, end_line, code_text` |
| 구문(dbms 자식) | `:SELECT` `:IF` `:LOOP` `:CALL` `:CASE` `:MERGE` … | `id`(`{parent}:{type}:{line}`) | `id, summary, start_line, end_line`; `name=""`(표시는 `타입[라인]`) |
| 테이블/컬럼/스키마 | `:TABLE` `:COLUMN` `:SCHEMA` | `id` | `t.name`; `c.name, c.dtype, c.is_primary_key` |
| 폴더 | `:PACKAGE` | `id` | `name` |
| 비즈니스로직 | `:RULE` `:EXAMPLE` `:QUESTION` | `id` | `r.statement`; `e.id/given/when_/then_/description`; `q.id/text/reason` |
| 외부 stub(예외) | `:FUNCTION:EXTERNAL` `:MODULE:EXTERNAL` | `id` | (다중라벨 유일 예외, 보존) |

- **식별 불변식**: 모든 노드 자기식별 = `id`. 폐기 속성(`function_id/module_id/fqn/example_id/procedure_name/moduleStereotype/file_name`)은 **읽지 않는다**.
- **대소문자 불변식**: 라벨은 UPPER_SNAKE. PascalCase 라벨/키는 소비자 자체 세션노드에만 허용(생산자 그래프 읽기엔 금지).
- **구분 불변식**: 생산자 노드는 `session_id` 미보유 → `session_id IS NULL`로 소비자 자체 노드와 구분.

## 엣지 (생산자 16종 중 소비자 사용분)

| 엣지 | 의미 | 끝점/속성 | 소비자 용도 |
|---|---|---|---|
| `PARENT_OF` | 부모→자식(루틴→구문, 구문→하위구문) | parent_id, child_id | **오너복원 상승 / 테이블 하향수집** |
| `HAS_MEMBER` | 그릇→루틴/데이터 | parent_id, child_id | 모듈↔루틴 |
| `BELONGS_TO` | 소속(→Package) | child→parent | 패키지 소속 |
| `CALLS` | 호출 | caller_id, callee_id | 호출맥락 |
| `HAS_RULE` | 노드→룰 | source_id, target_id; **rel: `local_rule_id`, `flow_id`, `coupled_domains`** | 룰 추출(★ local_rule_id) |
| `HAS_EXAMPLE` | 룰→예시 | source_id, target_id | 예시 |
| `HAS_QUESTION` | 노드→질문 | source_id, target_id | 질문 |
| `NEXT` | 룰 메인순서(rule) / 구문 실행순서(stmt) | rule: owner_id, 끝점=local_rule_id | **guard(선행조건) 도출** |
| `BRANCH` | 룰 분기 | owner_id, 끝점=local_rule_id | **branch_from(분기부모) 도출** |
| `READS`/`WRITES` | 코드노드→테이블 | source_id, target_id; rel: op/dml | **테이블 영향(자식에 부착)** |
| `HAS_COLUMN` | 테이블→컬럼 | parent_id, child_id | 컬럼 |
| `AFFECTS_TABLE` | 예시→테이블(이름매칭) | source_id, table_name, op | 예시 테이블효과 |

- **미존재(읽지 말 것)**: `ROLE`, `HAS_FUNCTION`, `HAS_VARIABLE`, `BELONGS_TO_PACKAGE`, `:Actor`, `:HAS_BUSINESS_LOGIC`. HAS_RULE rel의 `local_id`/`guard_rule_id`/`branch_from`.

## 파생 규칙 (소비자가 계산) — 본 작업 핵심

### R1. 오퍼레이션 단위 복원 (owner_resolver)
```
입력: 룰 오너 노드 n (HAS_RULE source)
규칙: n.label ∈ {FUNCTION,PROCEDURE,METHOD,TRIGGER} 이면 n 이 오퍼레이션.
      아니면 (n)<-[:PARENT_OF]-(p) 로 상승, 라벨이 루틴집합에 들 때까지 반복.
      찾은 루틴 op 의 op.id(식별)·op.name(이름)·op.summary(매칭요약)·source_function=op.name.
framework: n 이 이미 루틴 → 0회 상승.
```
Cypher 형태(개념): `MATCH (op)-[:PARENT_OF*0..]->(n) WHERE op:FUNCTION OR op:PROCEDURE OR op:METHOD OR op:TRIGGER` (가장 가까운 op 선택; 0..= framework 자기자신 포함).

### R2. 룰 흐름 도출 (local_rule_id 기반)
- `local_id` := `hr.local_rule_id`.
- `branch_from(rid)` := `(parent)-[:BRANCH]->(rid)` 의 parent local_rule_id.
- `guard_rule_id(rid)` := `(prev)-[:NEXT]->(rid)` 의 prev local_rule_id.

### R3. 테이블 영향 하향수집
- 오퍼레이션 op 의 테이블 효과 := `(op)-[:PARENT_OF*0..]->(d)-[rw:READS|WRITES]->(:TABLE)` 합집합(op 자신 + 모든 자손 구문).

### R4. 대표 예시
- `canonical` := 예시들을 `example_id` 정렬 후 첫째(is_boundary 미사용). traceability 인라인 `{is_boundary:false}` 필터 제거.

## 상태/검증 규칙
- 0-match 쓰기(소비자→생산자 엣지 MERGE)는 매칭 0이면 경고 로그(조용한 no-op 금지, FR-005).
- framework 경로는 R1~R3에서 동작 불변(0칸 상승·자식 없음)이어야 함(회귀 게이트).
