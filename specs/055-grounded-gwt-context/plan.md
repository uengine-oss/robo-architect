# Implementation Plan: Grounded GWT Context

1. 공용 legacy reference를 현행 Analyzer 압축 근거계약으로 갱신한다.
2. Intent/Plan/Tactical 출력 계약에 RULE 좌표 기반 GWT 작성·한계 규칙을 고정한다.
3. Detailed Tactical command DTO를 확장하고 staged consolidator가 기존 tacticalDiff
   GWT 형상으로 보존하게 한다.
4. Simplified/Detailed fixture로 GWT 보존·legacyRefs·중복/창작 방지를 검증한다.
5. shopmall Neo4j와 실제 Claude skill 실행으로 GWT 의미를 직접 판정한다.

## Constitution / 영향 경계

- 신규 Neo4j 라벨·관계·영속화 경로 없음.
- 기존 proposal applier와 GWT 스키마 재사용.
- 검색 알고리즘과 DDD 단계 의사결정은 변경하지 않고 입력 근거와 수렴 보존만 정합.

## T011 Strategy B 재검증 순서

1. Analyzer 최종 봉인 그래프와 새 Architect 전용 DB를 분리하고, 기존 A/B와 동일한 요구사항·함수·
   gold로 Simplified와 Detailed DDD 실제 API 경로를 각 1회 실행한다. `accept`/`apply`는 호출하지 않는다.
2. 템플릿 존재가 아니라 실제 Claude JSONL 도구 요청/응답, Proposal `legacyReferences`, stage artifact,
   최종 `strategicDiff`/`tacticalDiff`를 원문 코드까지 역추적한다.
3. 검색 결과는 충분하지만 후속 단계가 다시 검색하거나 근거를 잃는 경우에만 Proposal에 이미 저장한
   provenance를 공용 evidence packet으로 재사용하는 계약을 검토한다. packet은 실제 검색·상세 결과를
   구조화·중복 제거해 전달할 뿐, 이름/패턴으로 업무 의미를 생성하지 않는다.
4. 공통 원인이 입증되면 생산자와 Simplified/Detailed 소비자를 함께 고치고 최소 경로만 재실행한다.
   checker/gold/좌표/집계 단위를 먼저 배제하며, 최종 GWT는 함수·RULE·CALL/RW·TABLE/COLUMN/sample과
   레거시 원문에 모순이 없는지 의미 단위로 판정한다.
