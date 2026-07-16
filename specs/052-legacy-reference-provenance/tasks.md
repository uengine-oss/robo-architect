# Tasks: 052 레거시 참조 프로버넌스 — 1차분 (사후 기록, 증거 포함)

2026-07-16 완료분. 검증 증거가 있는 항목만 체크. 후속(2차분)은 미체크로 명시.

## 1차분 — 완료 (전부 실기동 검증)

- [x] T001 skill_runner 마커 발신(LEGACYQ/LEGACYREF, additive 3 hunk — 사용자 WIP 보존)
      증거: PRO-005 intent SSE 에 `🔍 레거시 그래프 검색`/`→ 레거시 함수 22개 · 규칙 8개 참조됨 ⛓`.
- [x] T002 legacy_provenance.py 수집기(마커 파싱·ProvenanceCollector.save append)
      증거: GET /api/proposals/PRO-005 → legacyReferences 1 stage·22 nodes.
- [x] T003 CLI 초대형-결과 파일폴백 — 안내문 3포맷 + `{"result": ...}` 이중포장 언랩
      증거: PRO-005 는 137,505자 한도 초과(파일치환)였으나 22노드 전량 복원 기록.
      회귀 방지: `tests/test_legacy_provenance.py` 8/8 PASS(직접 러너 — pytest 미설치).
- [x] T004 intent_runner 소비(SSE legacy_ref + 사람친화 라인 + save(INTENT, clarify 포함))
      증거: T001/T002 와 동일 실행.
- [x] T005 proposal_contracts 응답 노출(legacyReferences) — additive.
- [x] T006 LegacyRefChip.vue + ProposalDetail 헤더 배치 + 팝오버(오른쪽 전개·z-index 1000)
      증거: goal-verify/output/evidence/052-chip-header.png · 052-chip-popover.png (눈검수 완료 —
      칩 "⛓ 레거시 근거 22", 팝오버에 스테이지·검색어·함수명·요약·규칙 배지, 가림 0).
- [x] T007 품질 대조 — 기록 22건의 name/rulesCount 를 Neo4j 원본과 건별 대조: 함수 18/18
      일치(앵커 3개만 rules 3+1+4=8 — SSE 수치와 정합). TABLE 4건 "불일치"는 검증 스크립트가
      물리명/논리명을 오비교한 것(기록은 계약대로 논리명) — 데이터 정상.

관련: 검색 선정·크기·직렬화 근본 개선은 analyzer `specs/057-cluster-result-refinement`
(같은 날 구현: 게이트 P5 h3/r2 골드 29/30, 계층화, compact 직렬화).

## 2차분 — 미완 (todo 메모리와 동기)

- [ ] T101 PLAN·DDD 스테이지 러너에 동일 collector 훅(plan_runner 1곳 + stage_runners/base 1곳).
- [ ] T102 Proposal 목록(ProposalsPanel) 초소형 `⛓N` 배지 — 목록 API 는 이미 전체 모델 반환(백엔드 0줄).
- [ ] T103 연결선 모드 ②-B(승인 시안 mock-legacy-chip.html — 이름/컬럼 실재 시에만 실선).
- [ ] T104 상세 접이식 섹션(US2 표 #6) 및 나머지 표면(#3·#7).
- [ ] T105 커밋 분리(사용자 지시 시) — 현재 전부 워킹트리.
