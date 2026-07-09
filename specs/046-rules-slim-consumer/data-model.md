# Phase 1 Data Model: 룰 슬림 계약 소비자 정합

DTO/그래프 소비 스키마의 전(前)→후(後). 저장 스키마 신규/변경 없음(제거만).

## RuleDTO (api/features/ingestion/hybrid/contracts.py)

| 필드 | 전 | 후 | 비고 |
|---|---|---|---|
| id | ✅ | ✅ | 식별자. 해시 입력이 `function_id|statement`로 변경(값 형식 동일 `rule_<sha1[:12]>`) |
| given / when / then | ✅ | ✅ | 대표 예시 GWT |
| source_function / source_module | ✅ | ✅ | |
| confidence | ✅ | ✅ | |
| title (statement) | ✅ | ✅ | 분류 기준 |
| examples: list[ExampleDTO] | ✅ | ✅ | 중첩 예시 |
| coupled_domains | ✅ | ✅ | HAS_RULE.coupled_domains |
| **local_id** | ✅ | ❌ 제거 | 흐름 |
| **flow_id** | ✅ | ❌ 제거 | 흐름 |
| **guard_rule_id** | ✅ | ❌ 제거 | 흐름(선행조건) |
| **branch_from** | ✅ | ❌ 제거 | 흐름(분기부모) |
| **next_rule_local_ids** | ✅ | ❌ 제거 | 흐름(NEXT) |
| **branch_rule_local_ids** | ✅ | ❌ 제거 | 흐름(BRANCH) |
| context_cluster / es_role / es_role_confidence | ✅(legacy) | ✅ 유지 | 본 스펙 무관(별도 legacy) |

## ExampleDTO (contracts.py)

| 필드 | 전 | 후 | 비고 |
|---|---|---|---|
| example_id / given / when_ / then_ | ✅ | ✅ | |
| is_boundary | ✅ | ✅ | |
| **description** | ✅ | ❌ 제거 | EXAMPLE.description 소멸 |
| writes: list[dict] | ✅ | ✅ | AFFECTS_TABLE {table, op} — 라이브 로직 |

## 그래프 read 계약 (소비 시점)

| 읽던 것 | 전 | 후 |
|---|---|---|
| `HAS_RULE.coupled_domains` | ✅ | ✅ 유지 |
| `HAS_RULE.local_rule_id` | ✅ | ❌ 안 읽음 |
| `HAS_RULE.flow_id` | ✅ | ❌ 안 읽음 |
| `(rule)-[:NEXT]->(rule)` 도출 | ✅ | ❌ 제거(엣지 없음) |
| `(rule)-[:BRANCH]->(rule)` 도출 | ✅ | ❌ 제거(rel 타입 폐기) |
| `EXAMPLE.description` | ✅ | ❌ 안 읽음 |
| `EXAMPLE.{given,when_,then_}` + `AFFECTS_TABLE{op}` | ✅ | ✅ 유지 |
| 루틴 오너 복원(PARENT_OF*0..→루틴, C4) | ✅ | ✅ 유지 |
| 구문 NEXT(StatementNext, dbms) | (무관) | 유지 — 룰흐름 아님 |

## 파생 데이터(제거되는 중간표현)

- `dbms_rule_linearizer` 레코드에서 `flow_id`·`guard_rule_id`·`branch_from`·`next_rule_local_ids`·`branch_rule_local_ids`·`local_id`(P-id) 제거 → 남는 키: `function_id, function_name, function_summary, statement, coupled_domains, examples`.
- `bpm_context_builder` us_rule dict에서 `local_id`·`flow_id`·`guard_rule_id`·`branch_from` 제거 → 남는 키: `rule_id, statement, source_function, given, when_, then_, is_boundary, coupled_domains, examples`.

## ClassifiedRule / SessionDecomposition (삭제)

`rule_classifier.ClassifiedRule`, `decomposer.SessionDecomposition` 등 데드 클러스터의 자료구조는 파일과 함께 삭제(소비처 0).
