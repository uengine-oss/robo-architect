# Contract Delta: 슬림 룰 계약 소비 (044 supersede)

**역할**: 본 문서는 044 `graph-consumer-contract.md`에 대한 **046 supersede 델타**. 소비자가 analyzer 슬림 그래프(spec 039)를 읽는 현행 계약을 확정한다. 044 본문의 해당 조항은 본 델타로 대체된다.

## 044 C2 — 비즈니스로직 (부분 supersede)

**044 원문**: `:EXAMPLE {id, given, when_, then_, description}` / `HAS_RULE` rel 속성 = `local_rule_id, flow_id, coupled_domains`.

**046 대체**:
- `:EXAMPLE {id, given, when_, then_}` — **`description` 소멸**. 소비자는 읽지 않는다.
- `HAS_RULE` rel 속성 = **`coupled_domains`뿐**. `local_rule_id`·`flow_id` 소멸.
- 나머지(`:RULE {id, statement}`, `:QUESTION {id, text, reason}`, EXAMPLE의 is_boundary 부재 → example_id 정렬 폴백)는 044 C2 그대로 유효.

## 044 C3 — 룰 흐름 (전체 supersede = 폐기)

**044 원문**: `local_id ≔ HAS_RULE.local_rule_id`; `branch_from ≔ (parent)-[:BRANCH]->(r)`; `guard_rule_id ≔ (prev)-[:NEXT]->(r)`; NEXT/BRANCH(rule)는 owner_id로 qualify.

**046 대체**: **룰 레벨 흐름 계약 전면 폐기.**
- `local_id`·`flow_id`·`guard_rule_id`·`branch_from`·`next_rule_local_ids`·`branch_rule_local_ids` — 소비 안 함.
- 룰→룰 `NEXT`/`BRANCH` 엣지 — 존재하지 않음(`BRANCH` rel 타입 자체 폐기). 도출 서브쿼리 제거.
- **주의**: 구문 실행흐름 `NEXT`(StatementNext, dbms)·`BpmTask.NEXT`는 별개 — 유지. 폐기 대상은 **룰→룰** 흐름뿐.
- 룰 순서/분기 의미는 `statement` 텍스트·예시에 내재(소비자가 별도 재구성 안 함).

## 044 C4 — 오퍼레이션 단위 (불변)

유지. 룰/예시의 논리적 오너 = 가장 가까운 루틴(`{FUNCTION,PROCEDURE,METHOD,TRIGGER}`). dbms 구문→상위 프로시저 `PARENT_OF*` 상승. framework 0칸. 소비자 식별(`op.id`)·이름·`source_function`·요약은 이 루틴에서 취함.

## 044 C5 — 테이블 영향 (불변)

유지. `(:EXAMPLE)-[:AFFECTS_TABLE {op}]->(:TABLE {name})` 이름매칭. writes[]로 룰에 운반.

## 소비자 식별자

- RuleDTO.id = `rule_<sha1(function_id | statement)[:12]>`. (044까지는 `function_id | local_id | statement`였음 → local_id 소멸로 단순화.)
- 동일 (function, statement) 룰은 하나로 dedup.

## 관측성 (044 C7 유지)

소비자→생산자 매칭 0이면 경고 로그(silent no-op 금지). rule_extractor의 Phase 2 실패 시 WARN + 빈 리스트 반환은 기존 유지(부재 흡수는 graceful, 조용한 성공위장 아님).
