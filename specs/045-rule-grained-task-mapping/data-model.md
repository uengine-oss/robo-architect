# Data Model: 045 Rule-grained Task↔Code Mapping

**신규 Neo4j 스키마 = 0** (헌법/계약 준수). 기존 엔티티의 **읽기·비교 방식**만 바뀐다. 아래는 매칭에 관여하는 기존 엔티티와 그 관계.

## 엔티티 (전부 기존)

### BpmTask (업무 단계) — 매핑 한쪽 끝
- 출처: 하이브리드 BPM 산출(세션 노드, PascalCase). 매핑 변경 없음.
- 매칭 질의에 쓰는 필드: `name`, `description`(+ 소속 `BpmProcess.name`/`domain_keywords`).

### Rule (코드 규칙) — 매칭의 **비교 기본 단위**
- 출처: code_to_rules(세션 노드 `:Rule`, `session_id`). 본 피처는 이 노드를 **그대로** 비교 단위로 삼는다.
- 비교에 쓰는 필드: `title`, `given`, `when`, `then`(GWT), `source_function`(소속 루틴 식별).

### RuleContext (Rule의 분석그래프 컨텍스트) — blob 보강 (기존 `rule_context.build_rule_contexts`)
- 생산자(analyzer) 그래프에서 Rule의 소속 루틴을 조회해 채움(읽기 전용, 변경 0):
  - `function_summary` — 소속 루틴 요약 ★ **blob에 채택**(research Q2).
  - `reads_tables` / `writes_tables` — 관련 테이블(미채택, 커버리지 44/91).
  - `source_function` / `source_module` — 소속 루틴/컨테이너 식별(약신호용).
- dbms: 룰이 구문에 붙어도 owner_resolver가 상위 루틴으로 복원해 `source_function`/`summary`를 채움(기존, 전략무관).

### Task↔Rule 매핑 (`REALIZED_BY`) — 산출(기존 관계 재사용)
- `(:BpmTask)-[:REALIZED_BY]->(:Rule)` — 검증기 통과 후보가 저장됨(기존 `explore_service` 흐름).
- 본 피처가 0건 → 양수로 회복시키는 대상. **관계 타입·저장 인터페이스 변경 0.**

## 비교(매칭) 단위 — 변경의 핵심

| | 변경 전 | 변경 후 |
|---|---|---|
| 1차 비교 대상 | 코드 컨테이너(FILE/CLASS) **요약** | **개별 Rule blob** = `title + given/when/then + function_summary` |
| 컨테이너/루틴 | 하드 게이트(요약 점수 미달 시 후보 전탈락) | 약신호/로그만(하드 차단 제거) |
| 정밀도 책임 | (사실상 검증 도달 못 함) | 기존 LLM 검증기/중재(불변) |

## 검증 규칙(요구 → 데이터 관점)
- FR-006: 관련 코드 존재 Task엔 `REALIZED_BY ≥ 1`(0건 재발 금지).
- FR-002: 컨테이너 요약 점수 낮음이 Rule 후보 전탈락의 사유가 되어선 안 됨.
- FR-005: 생산자 노드/라벨/관계 불변(읽기만).

## 상태/전이
- 별도 상태기계 없음. 전체탐색(explore) 1회 = (세션 rule 임베딩 → task별 top-K 후보 → 검증기 → REALIZED_BY upsert) 기존 흐름, 비교 단위만 교체.
