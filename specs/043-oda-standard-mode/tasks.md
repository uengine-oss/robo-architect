# Tasks: ODA 표준 분해 모드 (043)

**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)
**Created**: 2026-06-28

규칙: `[P]` = 서로 다른 파일이라 병렬 가능. 게이트/파서(순수 로직) → SSE/라우트 → 프런트 → 테스트 순.

## Phase A — 계약 & 순수 로직 (테스트 우선 대상)

- [ ] **T001** `proposal_contracts.py`: `DecompositionMode.ODA_STANDARD` 추가. (US1, FR-001)
- [ ] **T002** `proposal_contracts.py`: `OdaAlignment`, `OdaConformanceItem`,
  `OdaConformanceReport`, `OdaArtifacts`, `WaiveConformanceRequest` 모델 추가
  (extra="allow"). (US1/US2/US3, FR-003/005/009-012)
- [ ] **T003** `proposal_contracts.py`: `ProposalResponse` 에 `odaAlignment/odaConformance/
  odaArtifacts` 필드 + `from_neo4j` 파싱(None 안전). (FR-002/005)
- [ ] **T004** `services/oda_conformance.py` 신규: `evaluate_gate`, `all_classified`,
  `can_proceed` 순수 함수. (US2, FR-004/006/007)
- [ ] **T005** `services/oda_conformance.py`: `apply_waiver(pid,reason)`,
  `ensure_can_proceed(pid)`(차단 시 dict 반환/예외). (US2, FR-008)

## Phase B — 러너 (시퀀서/파서)

- [ ] **T006** `services/oda_runner.py`: `resolve_knowledge_root()` (env→walk→fallback) +
  존재 검증. (FR-014)
- [ ] **T007** `services/oda_runner.py`: `parse_intent_result(data)`,
  `parse_plan_result(data)` — 스킬 JSON → alignment/conformance/diff/artifacts. (FR-003/013)
- [ ] **T008** `services/oda_runner.py`: `stream_oda_intent(pid)` SSE — 스킬(phase=intent)
  실행 → strategicDiff + alignment + 1차 conformance 저장. (US1, FR-003/013/016)
- [ ] **T009** `services/oda_runner.py`: `stream_oda_plan(pid)` SSE — 스킬(phase=plan) 실행 →
  tacticalDiff + odaArtifacts + 최종 게이트 저장. (US3, FR-009-013)

## Phase C — 라우트 & 게이트 강제

- [ ] **T010** `routes/proposals_oda.py` 신규: `GET stream/oda/intent`, `GET stream/oda/plan`,
  `GET oda/conformance`, `POST oda/waive`. (US1/US2/US3)
- [ ] **T011** `router.py`: `proposals_oda` 라우터 include. (US1)
- [ ] **T012** `routes/proposals_plan.py` + `proposals_crud.py`(submit): ODA 모드면
  `ensure_can_proceed` 게이트 → FAIL+미면제 409. (US2, FR-007)

## Phase D — 스킬

- [ ] **T013** `skills/robo-proposals/robo-proposal-oda/SKILL.md` 신규: extends oda-specify/
  oda-plan, phase(intent|plan), 지식 루트 근거 매핑/분류/게이트/산출 + diff 수렴 JSON. (US1/US3, FR-003/004/009-013)

## Phase E — 프런트엔드

- [ ] **T014** `ui/ProposalCreate.vue`: 세 번째 모드 옵션 `ODA_STANDARD` + 생성 후 detail 위임. (US1, FR-001)
- [ ] **T015** [P] `app/messages.js`: ko/en i18n 키(modeOda*, oda 패널). (FR-001, 언어정책)
- [ ] **T016** `proposals.store.js`: `subscribeToOdaIntent/Plan`, `waiveConformance`,
  `fetchConformance`. (US1/US2/US3)
- [ ] **T017** `ui/OdaStandardTrack.vue` 신규: 정합성 매핑 + 적합성 게이트(매트릭스/PASS-FAIL/위반/
  면제) + 산출물 미리보기. (US1/US2/US3, FR-003/005/007/008)
- [ ] **T018** `ui/ProposalDetail.vue`: mode==ODA_STANDARD → OdaStandardTrack 렌더 분기. (US1/US4)

## Phase F — 테스트 & 문서

- [ ] **T019** `tests/test_oda_standard.py`: 게이트(PASS/FAIL/WAIVE), all_classified,
  mode 파싱(from_neo4j), knowledge-root 해석, parse_intent/plan. (US1/US2/US3, SC-002/003/004/005)
- [ ] **T020** 백엔드 pytest 전체 + 042 무회귀 확인; frontend 빌드. (US4, SC-007/008)
- [ ] **T021** `specs/043-oda-standard-mode/manual.md`: 사용자 관점 ODA 모드 사용법 문서. (문서화)

## 의존 그래프

A(T001-005) → B(T006-009) → C(T010-012) → E(T016-018);
D(T013) 는 B/C 와 독립(스킬 파일); E(T014/015) 는 A 이후 가능;
F(T019) 는 A/B 후, T020/T021 은 전체 후.
