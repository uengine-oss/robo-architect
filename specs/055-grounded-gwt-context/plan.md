# Implementation Plan: Semantic-Frame-Grounded GWT

이 plan은 Analyzer spec131의 `semantic-frame/v1` 생산·저장·MCP 계약이 자동/결정론/직접 의미 판정으로
닫힌 뒤 시작한다.

1. 현재 complete-source WIP의 producer/consumer/test/skill 참조를 keep/adapt/remove로 분류한다.
2. Analyzer deduplicated semantic-frame MCP projection을 Proposal provenance에 손실 없이 저장한다.
3. Intent/Plan/Define/Tactical prompt를 source 재독해가 아닌 claims/roles/flow/status/evidence refs 소비로 바꾼다.
4. Simplified와 Detailed가 동일한 packet을 재사용하고 후속 단계의 동일 node 재조회가 없게 한다.
5. scenario별 evidenceRefs owner/존재/claim-type/구조 사실 정합을 fail-closed 검증한다.
6. Tactical command DTO와 staged consolidator가 GWT/evidenceRefs/userStoryRefs를 보존하게 한다.
7. source body 0, 중복 ID 0, unresolved ref 0, cross-owner ref 0 계약 테스트와 전체 회귀를 수행한다.
8. Analyzer가 닫힌 뒤 새 Architect DB/output root에서 Simplified/Detailed 실제 경로를 각 최소 1회 실행한다.
9. actual tool calls, Proposal provenance, stage inputs, final GWT/refs를 Analyzer claim과 레거시 원문에 직접 대조한다.
10. verification과 작업보고를 새 결과로 교체하고 임시 실행물만 정리한다.

## 영향 경계

- 기존 DDD 단계 의사결정과 proposal applier 영속화 경로는 유지한다.
- Architect가 업무 의미를 결정론적으로 생성하지 않는다.
- `ROBO_CLUSTER_MCP_URL=http://127.0.0.1:15502/robo/mcp`와 운영자 지정 Analyzer DB를 사용한다.
- 기존 dirty WIP·보존 DB/log를 reset/checkout/clean/overwrite하지 않고 `accept/apply`를 호출하지 않는다.

현재 단계는 Analyzer 완료 대기이며 Architect actual 실행은 금지한다.
