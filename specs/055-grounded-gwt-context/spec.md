# Feature Specification: Semantic-Frame-Grounded GWT Context

현재 교차 서비스 규칙·폐기 결정·실행 순서의 단일 진실은 Analyzer
`D:\work\robo\project\robo-data-analyzer\specs\131-cross-node-semantic-grounding\HANDOFF.md`다.

**Feature Branch**: `main`  
**Created**: 2026-08-10  
**Reframed**: 2026-08-12
**Status**: Complete — semantic-frame Simplified/Detailed actual replay verified

## Problem

이전 Architect 계약은 Analyzer 결과가 충분히 구조화되지 않았다는 문제를 함수 complete source/hash를
GWT packet에 추가해 Architect가 다시 검증하는 방식으로 보정하려 했다. 이는 Analyzer 분석의 의미를
약화하고 중복·토큰·혼동을 늘리므로 폐기됐다. Architect는 Analyzer가 소유한 canonical semantic frame과
parser 구조 사실을 목적별로 중복 제거해 소비해야 한다.

## User Scenarios

### US1 — Simplified가 semantic claims로 GWT를 만든다

Simplified Plan은 target responsibility, input/result roles, ordered flow, RULE/CALL/SYMBOL/TABLE claims,
sufficiency와 source coordinates를 읽고 Given/When/Then을 만든다. scenario는 실제 사용한 evidence ID를
남기며 원문 body를 정상 generation input으로 받지 않는다.

### US2 — Detailed DDD도 같은 packet과 refs를 보존한다

Define/Tactical/consolidation은 같은 semantic-frame projection을 사용하고 Command별 GWT와 evidence refs를
손실 없이 표준 tacticalDiff에 보존한다. 별도 의미 생성기나 두 번째 영속화 경로를 만들지 않는다.

### US3 — 근거가 부족하면 원문 재분석 대신 한계를 남긴다

`partial|insufficient` claim이나 missing context가 있으면 확인된 부분만 사용하고 필요한 evidence kind를
명시한다. 같은 원문을 Architect가 다시 읽어 의미를 보충하거나 이름·표본에 없는 값을 만들지 않는다.

## Requirements

- FR-001 Analyzer `semantic-frame/v1` projection은 target, claims, callees, data objects를 stable ID로 한 번씩
  제공하고 owner/order/coordinate/status/missing context를 보존한다.
- FR-002 complete source body와 새 source excerpt는 정상 GWT packet과 stage prompt에서 제외한다.
  source 조회는 사람의 감사·결함 추적을 위한 별도 read-only 경로다.
- FR-003 각 GWT scenario는 실제 사용한 RULE 및 필요한 CALL/SYMBOL/TABLE/COLUMN `evidenceRefs`를 남긴다.
- FR-004 Given은 입력·선행 상태, When은 Command/호출·처리, Then은 반환/Event/상태 변화 claim에 근거한다.
- FR-005 동일 claim/callee/data object는 packet에 한 번만 싣고 ID로 참조한다.
- FR-006 TacticalArtifact와 staged consolidator는 Command `gwt`, `evidenceRefs`, `userStoryRefs`, 입력
  field/property를 손실 없이 표준 tacticalDiff에 보존한다.
- FR-007 기존 Simplified Plan output schema와 proposal applier `_create_gwt` 경로를 재사용한다.
- FR-008 데이터 조회는 read-only Analyzer MCP만 사용하고 Architect가 Analyzer DB에 쓰지 않는다.
- FR-009 운영자가 지정한 Analyzer DB 이름을 모든 MCP 호출에 그대로 전달하고 프로젝트명으로 추측하지 않는다.
- FR-010 incomplete/unknown/cross-owner evidence와 구조 사실 변조는 fail-closed하며, Analyzer narrative를
  parser fact보다 우선해 사실을 바꾸지 않는다.

## 폐기된 계약

- `gwt-evidence/v2` complete source/hash 필수 계약
- `source.code_text`를 Architect prompt의 최상위 authority로 두는 계약
- 구조화 의미가 모호하면 같은 함수 원문을 Architect가 재독해해 보충하는 계약

안정적 evidence ID, RULE condition/effects/flow, symbol definition, outbound callee, direct table/column,
scenario evidence refs, 운영자 DB 전달과 stage 보존 로직은 새 계약에 맞게 적응할 수 있다.

## Success Criteria

- Analyzer 합격 전에는 실제 Architect 재실행을 시작하지 않는다.
- normal GWT packet의 complete source body와 새 excerpt가 0개다.
- 동일 claim/callee/data object 중복이 0이고 모든 scenario ref가 packet의 정확한 owner/evidence에 resolve된다.
- Simplified/Detailed가 같은 requirement·target·semantic packet에서 정상·경계·실패 GWT를 만들고 수렴
  전후 내용과 refs가 동일하다.
- source 직접 대조에서 fabrication 0, contradiction 0이며 omission과 needs_context를 별도 보고한다.
- 이전 21/21은 과거 기준선으로만 사용하고 새 semantic-frame 결과로 재주장하지 않는다.
- `accept/apply` 호출 0, 신규 GWT 영속화 경로 0이다.
