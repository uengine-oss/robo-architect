# Implementation Plan

## 현재 배선

`skill_runner(cluster only markers) → intent_runner collector → Proposal.legacyReferences → ProposalDetail LegacyRefChip`

PLAN과 staged DDD는 marker를 일반 로그/출력으로 취급하며, collector는 검색 결과만 알고 상세 검토 호출을 구분하지 못한다.

## 목표 배선

`skill_runner tool events → typed legacy marker parser → shared stage collector adapter → Proposal legacyReferences v2 → list badge/header chip/collapsible detail/connection projection`

## 슬라이스

1. marker/collector v2 계약 테스트: 순서 변화, 여러 검색, 여러 상세, 실패, 파일 fallback, 구형 read.
2. skill runner에서 두 MCP 도구를 typed marker로 방출하고 shared collector adapter를 만든다.
3. INTENT, PLAN, staged DDD에 같은 adapter를 연결한다.
4. skill 지침을 목록→상세 흐름으로 변경한다.
5. 목록 배지·상세·연결선 projection을 단일 selector/composable에서 계산한다.
6. API/unit/build/실제 DDD/Playwright로 양끝 검증한다.

## 영향도

- Backend producer: `api/platform/skill_runner.py`.
- Storage/contract: `legacy_provenance.py`, `proposal_contracts.py`, Neo4j Proposal property.
- Stage consumers: `intent_runner.py`, `plan_runner.py`, `stage_runners/base.py`.
- LLM consumer: `skills/robo-proposals/robo-proposal-intent/SKILL.md` 및 동일 MCP를 허용하는 plan/stage skill.
- UI: `ProposalsPanel.vue`, `LegacyRefChip.vue`, Proposal detail/diff surfaces, i18n, frontend tests.

## Constitution/원칙 점검

- marker 해석과 UI count/match는 단일 진실로 재사용한다.
- 도구 오류와 parse 오류를 숨기지 않고 안전한 상태로 저장/표시한다.
- 검색 점수로 관계선을 추론하지 않고 실제 텍스트 증거만 사용한다.
- 사용자 기존 proposal과 구형 기록을 읽되 무기한 이중 쓰기는 하지 않는다.

## 롤백

Analyzer 생산자 전환과 함께 배포한다. 새 marker를 모르는 구버전 Architect로 부분 롤백하지 않는다. Git 커밋 단위로 Analyzer/Architect 포인터를 함께 되돌린다.

