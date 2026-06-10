# Tasks: BPMN 활동–레거시 BL 룰 매핑 Recall 개선 (용어 정규화)

**Feature**: `036-bpmn-rule-mapping-recall` | **Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md)

**Input**: plan.md, spec.md(US1~US3), research.md(D1~D6), data-model.md, contracts/internal-mapper-contract.md, quickstart.md(Q1~Q7)

모든 경로는 저장소 루트 기준. 변경 표면은 `api/features/ingestion/hybrid/mapper/`로 국소. 신규 그래프 스키마/외부 REST 0건.

---

## Phase 1: Setup

- [x] T001 [P] env 플래그 컨벤션 확인 — `api/features/ingestion/hybrid/mapper/agentic_retriever.py`의 기존 `HYBRID_EMBED_*` 패턴을 참고해 `HYBRID_GLOSSARY_NORMALIZE`(기본 `"1"`) 읽기 헬퍼 위치 결정(상수 섹션 상단). 코드 변경 없이 배치 지점만 표시.
- [x] T002 [P] 신규 테스트 디렉터리/픽스처 자리 확인 — `api/features/ingestion/hybrid/mapper/tests/`에 본 피처 테스트 2종이 들어갈 위치와 기존 테스트 import 패턴 점검.

---

## Phase 2: Foundational (모든 User Story의 선행 — 블로킹)

**목표**: 정규화 순수 함수 모듈. US1/US2/US3가 공통으로 의존.

- [x] T003 신규 모듈 `api/features/ingestion/hybrid/mapper/term_normalizer.py` 생성 — `normalize_query(query, glossary, *, max_aliases_per_term=5) -> tuple[str, bool]` 구현. glossary 항목의 `term`/`aliases`가 query에 부분 문자열로 등장하면 그 항목의 `code_candidates`(상위 N개)를 query에 **append**(원문 보존, replace 금지). 빈 glossary → `(원문, False)`. 결정성(추가 토큰 순서 고정) 보장. (contracts C1)
- [x] T004 같은 파일에 `normalize_rule_blob(blob, rule, ctx, glossary, *, max_terms_per_candidate=3) -> tuple[str, bool]` 구현 — glossary 항목의 `code_candidates`가 rule의 `source_module`/`source_function`/`title`에 등장하면 그 항목의 `term`+`aliases`(상위 M개)를 blob에 append. 빈 glossary → `(원문, False)`. (contracts C1)

**Checkpoint**: term_normalizer 단독 임포트·호출 가능. 아직 파이프라인에 미배선.

---

## Phase 3: User Story 1 — 어휘 다른데 의미 같은 룰이 매핑됨 (Priority: P1) 🎯 MVP

**Goal**: glossary를 retrieval 임베딩 입력에 양방향 주입해, 어휘갭으로 탈락하던 정당한 룰을 매핑으로 회복(recall↑). floor·예산 불변.

**Independent Test**: 골든 픽스처에서 off→on 비교 시 회복(recovered) ≥ 1, 회귀(regressed) = 0 (SC-001).

- [x] T005 [US1] `agentic_retriever.run_agentic_retrieval`에 `glossary: list[GlossaryTerm] | None = None` 파라미터 추가 — `api/features/ingestion/hybrid/mapper/agentic_retriever.py`. 기본 None(하위 호환). 내부에서 `_candidates_for_task` 호출 시 전달. (contracts C2)
- [x] T006 [US1] `agentic_retriever._candidates_for_task`에 정규화 주입 — 같은 파일. 임베딩 직전 `query`와 각 `_rule_blob(ctx)`에 `term_normalizer` 적용. 조건: `os.getenv("HYBRID_GLOSSARY_NORMALIZE","1") != "0"` AND `glossary` 비어있지 않음. 그 외엔 원문(바이트 동일). `MIN_BL_INCLUSION`/top_k/in_scope 프리필터/임베딩 실패 폴백 **변경 없음**. (contracts C3, research D1/D2/D6)
- [x] T007 [US1] `activity_rule_mapper.map_tasks_to_rules`에서 배선 — `api/features/ingestion/hybrid/mapper/activity_rule_mapper.py`. 이미 추출된 `result.glossary`를 `run_agentic_retrieval(..., glossary=result.glossary)`로 전달(한 줄). 그 외 오케스트레이션 불변. (contracts C4, research D4)
- [x] T008 [P] [US1] 단위 테스트 `api/features/ingestion/hybrid/mapper/tests/test_term_normalizer.py` — normalize_query/normalize_rule_blob: 매칭 시 토큰 append, 미매칭·빈 glossary 시 `(원문, False)`, 토큰 상한 준수, 결정성(동일 입력→동일 출력). (quickstart Q6)
- [x] T009 [US1] 측정 하니스 `specs/036-bpmn-rule-mapping-recall/manual/run_mapping.py` — PDF 입력 + neo4j 분석 그래프로 `map_tasks_to_rules` 실행, 활동별 accept 매핑/사용자 노출 항목 수/wall-clock을 JSON으로 출력. `HYBRID_GLOSSARY_NORMALIZE` env로 off/on 제어. (quickstart Q2/Q3)
- [x] T010 [US1] 비교기 `specs/036-bpmn-rule-mapping-recall/manual/compare.py` — baseline(off)/normalized(on) JSON diff → `recovered`(on에만), `regressed`(off에만) 산출 및 판정 출력. (quickstart Q4)

**Checkpoint**: 골든 픽스처에서 recovered≥1·regressed=0 확인 → US1(MVP) 독립 완료.

---

## Phase 4: User Story 2 — 검토 화면 항목이 늘어나지 않음 (Priority: P1)

**Goal**: recall이 올라도 사용자 노출 항목(accept + near-miss)이 개선 전 대비 증가하지 않음을 보장·검증.

**Independent Test**: 동일 입력 off/on에서 사용자 노출 항목 수 delta ≤ 0 (SC-002).

- [x] T011 [US2] `compare.py`에 `user_visible_delta` 계산 추가 — `specs/036-bpmn-rule-mapping-recall/manual/compare.py`. off/on의 (accept 매핑 수 + 표시되는 near-miss reject 수) 차이를 산출, > 0이면 실패 표시. (quickstart Q4)
- [x] T012 [P] [US2] 불변식 가드 테스트 `api/features/ingestion/hybrid/mapper/tests/test_normalize_invariants.py` — `HYBRID_GLOSSARY_NORMALIZE=0`일 때 `_candidates_for_task`가 정규화 미적용 원문 경로를 타는지(바이트 동일), 그리고 정규화 on이어도 `MIN_BL_INCLUSION`/`bl_top_k`/`per_task_cap` 상수가 변경·참조 변형되지 않는지 검증. (spec FR-003/FR-005)
- [x] T013 [US2] near-miss 표시 경로 불변 확인 — `agentic_retriever`의 `REJECT_NEAR_MISS_FLOOR`/`REJECT_VISIBLE_CAP` 기반 노출 로직이 정규화와 무관하게 동일 상한을 유지하는지 코드 점검 및 하니스 출력에 near-miss 수 포함.

**Checkpoint**: off/on에서 user_visible_delta ≤ 0 확인 → US2 독립 완료.

---

## Phase 5: User Story 3 — 처리 비용이 상한 안에서 유지됨 (Priority: P2)

**Goal**: 정규화로 인한 소요 시간 증가가 개선 전 대비 ≤1.2x, 검증 후보 수 상한 불변.

**Independent Test**: 동일 입력 off/on wall-clock 비 ≤ 1.2, 활동당 검증 후보 수 불변 (SC-003).

- [x] T014 [US3] `compare.py`에 `wall_clock_ratio` 계산 추가 — on/off 전체 매핑 소요 시간 비를 산출, > 1.2면 실패 표시. (quickstart Q4, spec SC-003)
- [x] T015 [US3] 관찰성 로깅 — `agentic_retriever`(retrieval 종료 지점)에 `SmartLogger`로 `normalize_enabled`/`normalized_tasks`/`normalized_rules` 집계 기록. 검증 후보 수가 `bl_top_k`/`per_task_cap` 상한 내인지 동일 로그에 포함. (contracts C6, spec FR-008)
- [x] T016 [P] [US3] 하니스에 활동당 검증 후보 수 집계 추가 — `run_mapping.py`가 활동별 검증기 입력 후보 수를 출력해 off/on 동일(상한 내)임을 비교 가능하게. (spec SC-003)

**Checkpoint**: wall_clock_ratio ≤ 1.2 및 후보 수 상한 불변 확인 → US3 독립 완료.

---

## Phase 6: Polish & Cross-Cutting

- [x] T017 [P] 폴백 회귀 — glossary 빈 목록(또는 LLM 키 미설정) 경로에서 매핑이 무오류 완료되고 baseline과 동일(회귀 0)임을 확인하는 테스트/하니스 실행. (spec FR-006/SC-004, quickstart Q5)
- [x] T018 [P] 전체 매퍼 회귀 가드 — `HYBRID_GLOSSARY_NORMALIZE=0`에서 `api/features/ingestion/hybrid/mapper/tests/` 전체 pytest 통과 확인(기존 동작 바이트 동일). (quickstart Q7)
- [x] T019 [P] 스키마 diff 0 검증 — 본 피처가 neo4j 신규 노드 라벨/관계를 추가하지 않았음을 확인(스키마 스냅샷 diff 또는 코드 점검). (spec FR-007)

### 매뉴얼 생성 (Playwright before/after 캡처 → manual.md/.docx)

본 피처는 신규 UI가 없으므로 매뉴얼의 핵심 시연 = **기존 BPMN 내비게이터 화면의 off/on 대비**(어휘갭 룰 회복)와 측정 수치다. 전제: 앱 구동(`localhost:5199`) + neo4j에 analyzer 그래프(`zapamcom*` 분석) 적재 + LLM 키.

- [x] T020 [P] Playwright 설정 — `specs/036-bpmn-rule-mapping-recall/manual/artifacts/playwright.config.ts` 작성(034 패턴 복제: `baseURL` env override, workers:1, viewport 1440×900, `shot()` 헬퍼로 `manual/screenshots/`에 저장).
- [x] T021 Playwright before/after 캡처 스펙 — `specs/036-bpmn-rule-mapping-recall/manual/artifacts/playwright-036-recall.spec.ts`: 골든 픽스처(자동납부 본인확인 PDF)를 인제스트→BPMN 매핑 실행 후, 동일 활동("본인확인")의 룰 매핑 패널을 `HYBRID_GLOSSARY_NORMALIZE=0`/`=1` 각각으로 캡처 → `manual/screenshots/{01_off_missing.png, 02_on_recovered.png, 03_mapping_panel_detail.png}`. (US1 시각 증명, quickstart Q2/Q3)
- [x] T022 매뉴얼 본문 작성 — `specs/036-bpmn-rule-mapping-recall/manual/manual.md`(한국어): 기능 개요(어휘갭 문제·용어 정규화 해결) + before/after 스크린샷 임베드 + 골든 픽스처 A/B 측정표(recovered/regressed/user_visible_delta/wall_clock_ratio) + env 토글 안내. (quickstart 전체, spec FR-008/SC-001~005)
- [ ] T023 [P] manual.docx 변환 — `manual.md` → `manual.docx`(035/034 manual 산출물과 동일 포맷). 스크린샷 포함.

### 구현 중 발견 → 추가 완료 (실측 기반)

- [x] T024 **실경로 배선** — production 매핑은 lazy라 `map_tasks_to_rules`가 아니라 `explore_service.explore_task`가 `run_agentic_retrieval`을 직접 호출함을 발견. `explore_service._load_glossary(session_id)` 추가 + `explore_task`에서 `glossary=` 전달. (T007의 `map_tasks_to_rules` 배선은 레거시 호환용으로 유지.) contracts C7.
- [x] T025 **union-under-cap + 회복 상한** — 실측에서 순수 정규화가 비용 ~2x·회귀 다수 유발. `_candidates_for_task`를 baseline 전량 보존 + `HYBRID_GLOSSARY_MAX_RECOVERIES`(기본 3) 상한으로 재설계. 측정: 비용 1.07x·회복 23·회귀 1. contracts C8, spec Clarifications(2차).
- [x] T026 **골든 픽스처 A/B 실행** — golden036(ingest 완료) off/on 측정 → /tmp/036_{baseline,normalized}.json, manual.md 측정표 채움.

> **T021 완료** — 프런트(`localhost:5173`)+백엔드(8000) 구동 상태에서 localStorage `hybrid.session_id=golden036` 주입 → off/on DB 상태별 캡처(`01_off_missing`, `01b_off_panel`, `02_on_recovered`, `03_mapping_panel_detail`). R-count 배지로 회복 가시화(예: task10 R1→R4, task11 R1→R3). **T023(docx)만 잔여** — 로컬 pandoc 미설치(설치 시 변환).

---

## Dependencies & 실행 순서

```text
Phase 1 (T001,T002)  →  Phase 2 (T003,T004)  →  Phase 3/US1 (T005→T006→T007, T008∥, T009→T010)
                                                      │
                                                      ├─ Phase 4/US2 (T011,T012∥,T013)
                                                      ├─ Phase 5/US3 (T014,T015,T016∥)
                                                      └─ Phase 6 (T017∥,T018∥,T019∥,
                                                                  매뉴얼: T020∥→T021→T022→T023∥)
```

- **Foundational(T003/T004)이 모든 스토리를 블로킹** — 정규화 함수 없이는 주입 불가.
- **US1이 MVP** — T005~T007 배선 + T009/T010 하니스로 핵심 가치(recall↑) 독립 검증.
- US2/US3는 US1의 하니스를 확장하므로 US1 완료 후 진행. 서로 독립.
- `[P]`: 다른 파일·독립 작업이라 병렬 가능(T008 단위테스트, T012 가드테스트, T016/T017/T018/T019).

## Parallel 예시

- Phase 3 내: T008(test_term_normalizer.py)은 T005~T007 배선과 다른 파일이라 병렬 가능.
- Phase 6: T017/T018/T019는 서로 다른 검증이라 동시 실행 가능.

## Implementation Strategy

1. **MVP first**: Phase 1·2 + US1(T001~T010) → 골든 픽스처에서 recall 회복 확인. 여기까지가 기능의 본질.
2. **Incremental**: US2(화면 불변 가드) → US3(비용 상한 검증) 순으로 안전망 강화.
3. **Safety**: 전 과정 `HYBRID_GLOSSARY_NORMALIZE=0`이면 기존 경로와 바이트 동일 → 언제든 무변경 롤백.
