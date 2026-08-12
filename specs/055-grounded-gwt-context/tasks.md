# Tasks: Semantic-Frame-Grounded GWT

현재 교차 서비스 실행 순서는 Analyzer spec131 HANDOFF가 소유한다. Analyzer semantic frame이 닫히기 전
Architect 실제 실행을 시작하지 않는다.

## 보존된 기준선

- [x] T001~T010 기존 RULE 좌표 GWT, Detailed consolidation, provenance와 회귀 기준선 보존
- [x] T011 과거 Strategy B Simplified/Detailed 표본 GWT 21/21 직접 source 정합 기록 보존
- [x] T012a complete-source `gwt-evidence/v2` 방향이 목표와 반대임을 확인하고 폐기 결정 문서화

## semantic-frame 소비 전환

- [x] T012b complete-source WIP producer/consumer/test/skill keep/adapt/remove inventory
- [x] T012c Analyzer `semantic-frame/v1` deduplicated MCP/provenance 소비 계약 구현
- [x] T012d Intent/Plan/Define/Tactical에서 source body 제거 및 claims/roles/flow/status 소비 전환
- [x] T012e scenario evidenceRefs 존재·owner·claim-type·구조 사실 fail-closed 검증
- [x] T012f Simplified/Detailed stage 재사용과 Tactical/consolidation 무손실 보존 검증
- [x] T012g source body/새 excerpt 0, duplicate/unresolved/cross-owner ref 0, 전체 회귀
- [x] T012h Analyzer 합격 뒤 새 격리 DB/output의 실제 두 경로 최소 replay와 원문 직접 대조
- [x] T012i verification/HANDOFF/작업보고 결과 교체와 임시 실행물 정리

## 금지

- complete source/hash를 정상 Architect generation packet에 넣지 않는다.
- Analyzer 부족 의미를 Architect의 원문 재독해나 이름 기반 추측으로 보충하지 않는다.
- `accept/apply`를 호출하지 않는다.
