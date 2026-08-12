# Feature Specification: Grounded GWT Context

**Feature Branch**: `main`  
**Created**: 2026-08-10  
**Status**: In Progress

## Problem

Analyzer의 RULE 계약이 `statement`에서 `anchor_line/cond/then/nl`로 바뀌었지만
Proposal 스킬의 조회 계약은 옛 형상을 전제로 한다. 또한 Detailed DDD의 Tactical 산출물과
수렴기는 Command GWT를 운반하지 않아 Detailed 결과는 GWT가 0개가 된다.

## User Scenarios

### US1 — Simplified가 좌표 있는 근거로 GWT를 만든다 (P1)

Claude가 레거시 후보를 검색하고 GWT용 상세을 읽으면 RULE 파일행, 직접 호출/RW,
테이블·컬럼·실제 샘플을 근거로 UserStory acceptanceCriteria와 Command GWT를 만든다.

### US2 — Detailed DDD도 같은 근거와 같은 GWT 계약을 쓴다 (P1)

Tactical 단계가 Aggregate/Command/Event와 함께 Command별 정상·경계·실패 GWT를 내고,
수렴기가 이를 표준 tacticalDiff에 손실 없이 보존한다.

### US3 — 근거가 부족하면 창작 대신 한계를 남긴다 (P1)

RULE·표본에 없는 필드값이나 상태를 만들지 않으며, 소스 전문이 꼭 필요한 예외만 기존
full detail로 재조회한다.

## Requirements

- FR-001 공용 `legacy-reference.md`는 Analyzer 현행 RULE `line/text/tables`와
  `node_detail(view="gwt")`를 명시하며 Simplified/Detailed가 함께 사용한다.
- FR-002 GWT의 각 Given/When/Then은 사용한 함수·RULE 행·테이블/샘플 근거로 역추적된다.
- FR-003 동일 RULE/소스 전문을 검색과 상세 양쪽에서 중복 주입하지 않는다.
- FR-004 TacticalArtifact의 handledCommand는 `name`, `legacyRefs`, `userStoryRefs`,
  `gwt`를 운반할 수 있다.
- FR-005 staged consolidator는 Command의 `gwt`, `userStoryRefs`, 입력 필드/properties를
  표준 tacticalDiff로 복사하며 새 GWT 생성기를 만들지 않는다.
- FR-006 기존 Simplified Plan output schema와 proposal applier GWT 경로를 재사용한다.
- FR-007 데이터 조회는 read-only Analyzer MCP만 사용하고 Architect가 DB에 직접 쓰지 않는다.

## Success Criteria

- shopmall 동일 요구에서 Simplified와 Detailed 모두 Command당 정상 1개와 경계/실패
  1개 이상을 생성한다.
- 봉인된 `calc_discount`, `load_target_orders`, `get_code_name` 표본의 값·분기·R/W 금지
  주장을 위반하지 않는다.
- GWT 생성용 MCP 입력 바이트가 현행 검색+full detail 대비 70% 이상 감소한다.
- Detailed 수렴 전후 Command의 GWT 개수와 내용이 동일하다.
- 적용기 기존 `_create_gwt` 외의 두 번째 영속화 경로는 0개다.

