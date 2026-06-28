# Tasks: 코드분석 Task↔Rule 매핑 단위 정합 (045)

**입력**: plan.md · research.md · data-model.md · contracts/matching-contract.md · quickstart.md
**핵심**: 비교 단위 = 컨테이너 요약 → **개별 Rule blob(GWT+루틴 summary)**. 모듈 게이트 하드차단 제거. 임베딩 ≤30 청킹. 정밀도=기존 검증기/중재(불변). 전략 분기 0.
**영향 범위**: `api/features/ingestion/hybrid/` 한정. `run_agentic_retrieval`은 **2 caller**(`explore_service`=전체탐색, `activity_rule_mapper`=인제스천 자동매핑) → 공유 함수 수정으로 둘 다 일관 정상화.

---

## Phase 1: Setup (기준선·하니스)

- [X] T001 변경 전 기준선 재현: `C:/.../scratchpad/research_exp.py` 패턴으로 현 `_candidates_for_task`(컨테이너 게이트 有)를 test 세션 `eee29044`의 19 task에 호출 → **후보 0(전 task)** 캡처해 baseline 고정.
- [X] T002 [P] 변경 대상 4파일의 현 동작·호출부 정독 확정: `api/features/ingestion/hybrid/mapper/agentic_retriever.py`, `module_retriever.py`, `embeddings.py`, `rule_context.py` (+ 2 caller `explore_service.py`·`mapper/activity_rule_mapper.py`).

## Phase 2: Foundational (선행 차단 — 모든 스토리 전제)

- [X] T003 `api/features/ingestion/hybrid/mapper/embeddings.py` — `EmbeddingCache.embed_many`에 **≤30 청킹** 추가(엔드포인트 배치 상한 32·대배치 OOM 대응). 입력 순서·결과 불변, 단일 상수(`_EMBED_BATCH=30`)로. (hybrid 6개 공유처 전부 안전 이득.)
- [X] T004 `api/features/ingestion/hybrid/mapper/rule_context.py` — blob에 쓸 `function_summary`가 RuleContext에 채워짐을 확인(이미 제공). dbms도 owner_resolver로 루틴 summary 채워지는지 코드 경로 확인(변경 없으면 no-op).

**Checkpoint**: 임베딩이 ≤30 청크로 안전 호출(91개 전수 임베딩이 413/OOM 없이 동작).

## Phase 3: User Story 1 — 코드분석 결과가 설계에 반영 (P1) 🎯 MVP

**목표**: Task↔Rule 매핑이 0 → 양수로 회복(REALIZED_BY>0). **독립 테스트**: 시나리오 A 직접호출에서 19/19 task 후보 ≥1.

- [X] T005 [US1] `agentic_retriever.py` — `_candidates_for_task`의 **비교 단위 교체**: rule blob = `규칙:{title}\nGIVEN/WHEN/THEN\n[함수요약]{function_summary}` (research Q2 = GWT+summary). `function_summary` 없으면 그 줄 생략. 테이블/모듈/패키지는 blob에 넣지 않음.
- [X] T006 [US1] `agentic_retriever.py` — `_candidates_for_task`의 **컨테이너 프리필터 제거**: `module_fqns` 기반 in_scope 한정(룰 전탈락 원인) 제거 → 세션 전 rule을 후보 풀로(top-K cap 유지). 모듈 점수는 후보 배제 사유로 쓰지 않음(FR-002, 계약 M3).
- [X] T007 [US1] `agentic_retriever.py` — `run_agentic_retrieval`의 **process-level 모듈 게이트 하드차단 제거**(`process_max_score < min_module_score` → return 스킵 경로 폐기). 모듈 검색 결과는 약신호/로그만(필요 시). (research Q1: 게이트가 0건 직접원인.)
- [X] T008 [US1] `module_retriever.py` — `retrieve_top_modules`/`_module_rows` 호출을 **약신호/관측용으로 격하**(하드 게이트 호출 정리). 데드코드/거친-요약-게이트 잔재 청소(원칙 §3·§4).
- [X] T009 [US1] **검증(직접호출, 결정적)**: 변경 후 `_candidates_for_task`/`run_agentic_retrieval`를 test 세션 `eee29044`에 호출 → **19/19 task 후보 ≥1**(T001의 0 대비 0→N). 샘플 task top 후보가 도메인상 타당함 눈검증(quickstart 시나리오 A).
- [X] T010 [US1] **2-caller 일관 확인**: `explore_service.run_agentic_retrieval`(전체탐색)·`activity_rule_mapper.run_agentic_retrieval`(인제스천 자동) 둘 다 동일 후보 회복 경로를 타는지 확인(공유함수 수정이 양쪽 반영, 분기 0).

**Checkpoint**: 직접호출에서 후보 0→N 회복 = MVP 가치 달성.

## Phase 4: User Story 2 — 코드 구조 크기 무관 (P2)

**목표**: 파일당 함수 多·거대 프로시저 모두 매핑. **독립 테스트**: framework 그래프(파일당 17~21함수)에서 매핑 생성.

- [X] T011 [US2] **전략/크기 무관 확인**: 비교 단위가 Rule(항상 잘게)이라 컨테이너/루틴 크기와 무관함을, framework graph(현 test)에서 후보 생성으로 입증. `framework/dbms` 분기 0인지 코드 점검(헌법 II).
- [X] T012 [US2] dbms 경로 코드 검증(라이브 미확보): dbms 룰=구문→owner_resolver 루틴 복원 후 `source_function`/`function_summary` 채워지는 경로가 동일 매칭을 타는지 정독 확인. dbms 그래프 확보 시 동일 하니스 라이브 검증 예정(미검증 명시).

**Checkpoint**: 크기 의존 없음(framework 입증, dbms 코드경로 확인).

## Phase 5: User Story 3 — 부정확 매핑 차단 (P3)

**목표**: 매핑 늘려도 검증기/중재가 오매핑 차단. **독립 테스트**: 명백 오매핑 도배 없음.

- [X] T013 [US3] 정밀도 장치 불변 확인: `agent_validator`(검증기)·중재(arbitration)·`explore_service` 저장 인터페이스 무변경으로 후보→수락분만 `REALIZED_BY` 됨을 확인(FR-004).
- [X] T014 [US3] 관측성(헌법 IV / 계약 M7): 후보 0 또는 매핑 0 시 **경고 로그**(silent no-op 제거). 모듈 게이트 silent-empty 경로 제거됐는지 확인.

**Checkpoint**: 정밀도 유지 + silent 실패 제거.

## Phase 6: Polish & 라이브 검증 (cross-cutting)

- [X] T015 [P] 단일진실/매직넘버: blob 구성·청크 크기(30)·top-K·floor를 상수 한 곳으로(헌법 III). lean-blob의 모델 의존 가정은 research 링크 주석 1줄(장황 금지, §4 주석규칙).
- [X] T016 [P] 회귀(불변 확인): 생산자(analyzer) 그래프/스키마·프론트·신규 라벨/관계 0 — `git diff`로 mapper 4파일 외 변경 없음 확인.
- [X] T017 **라이브 풀런 검증**(quickstart 시나리오 B): architect api(test DB)+host+백엔드 기동 → 코드분석 모드 PDF 2개 → BPM → 전체탐색 → Neo4j `MATCH ()-[r:REALIZED_BY]->() RETURN count(r)` **> 0**, orphan Rule 대폭 감소, "전체 탐색"→"전체 재탐색" 전환 확인. 이벤트스토밍이 코드 규칙에 근거.
- [X] T018 `/speckit-analyze`로 spec↔plan↔tasks 교차 일관성 검증(읽기검증).

---

## Dependencies & 실행 순서
- Phase 1(기준선) → Phase 2(임베딩 청킹·컨텍스트) → **Phase 3(US1 = MVP 핵심)** → Phase 4(US2) → Phase 5(US3) → Phase 6(Polish/라이브).
- US1이 핵심 가치(0→N). US2/US3는 US1 위에서 검증·보강. T015~T016 [P] 병렬 가능(서로 다른 관심).
- T005·T006·T007은 같은 파일(agentic_retriever.py) → 순차(병렬 불가).

## MVP 범위
**Phase 1~3(T001~T010)** = MVP: 후보 0→N 회복으로 핵심 가치 달성. 나머지는 크기무관·정밀도·관측성·라이브 보강.

## 병렬 실행 예시
- Phase 6: `T015`(상수정리)·`T016`(회귀확인) 병렬.
- Phase 1: `T002`(정독) 병렬 가능.
