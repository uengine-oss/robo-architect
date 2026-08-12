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

