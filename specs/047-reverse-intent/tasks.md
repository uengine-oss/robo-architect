# Tasks: 코드에서 요구사항 역추출 (Reverse Intent)

**Feature**: `specs/047-reverse-intent/` | **Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md)

원천: plan.md(구조·기술) · spec.md(US1/US2/US3) · research.md(D1~D7) · data-model.md · contracts/reverse-intent-api.md.
경로 접두어 생략형 = `api/features/proposal_lifecycle/` (백엔드), `frontend/src/features/proposals/` (프론트).
PoC 원천 = `project/reverse-intent-poc/reverse_intent/`.

## 진행 현황 (2026-07-08)
- **구현 완료**: T001~T014(백엔드 전부 + 프론트 배선) · T016~T019(라벨·그룹카드). 백엔드 import 스모크 OK, 프론트 vite build OK.
- **실환경 검증 완료(결정론)**: 소스목록(neo4j/skill/test 자동식별) · 그룹핑(test DB 커버리지100%·중복0·인프라필터) · 읽는 카드(논리명·성격 한국어). = T009·T004·T016·T021 근거.
- **미검증(라이브 필요)**: T015 LLM end-to-end(create→stream→N intent콜→merged strategicDiff)는 로컬 구독 claude + 풀스택 기동 필요 — 재사용하는 intent 스킬은 PoC서 7op→7US 실증됨. T020 ⑥미완 폴백·T022 예산분할 스트레스·T023~T025 폴리시는 이후.
- **미커밋**(요청 시만). WIP(spec 046)와 파일 0겹침.

---

## Phase 1: Setup

- [ ] T001 `services/reverse_intent/__init__.py` 생성(빈 패키지) + PoC 원천 파일 대조 준비(grouping/brief/merge/pipeline 읽어둠).

## Phase 2: Foundational (모든 스토리 선행 — 차단)

- [ ] T002 `proposal_contracts.py`: `DecompositionMode`에 `REVERSE_INTENT="REVERSE_INTENT"` 추가(기존 3값 뒤) + 신규 요청모델 `CreateReverseProposalRequest{db:str, title:Optional[str]}`. 기존 enum 소비처(plan_runner/oda_conformance) 전수 grep해 새 값이 기본 경로 유지(회귀 0) 확인.
- [ ] T003 [P] `services/reverse_intent/neo4j_read.py`: analyzer 그래프 세션 획득 헬퍼 = `get_session(database=ANALYZER_NEO4J_DATABASE)` 얇은 래퍼(무인자 세션 오용 방지, research D3). 단일 진실.

## Phase 3: User Story 1 — 문서 없이 코드에서 요구사항 도출 (P1) 🎯 MVP

**목표**: 분석 그래프 선택 → 자연어 0줄 → strategicDiff 생성. **독립 검증**: `test` DB로 create→stream→strategicDiff, UserStory↔원본 op 1:1(SC-002).

- [ ] T004 [P] [US1] `services/reverse_intent/grouping.py`: PoC `grouping.py` 이식(assign_groups=쓰기허브 앵커·차순위 읽기·로직, 전 op 커버리지100%·중복0, `INFRA_TABLE_HINTS` 필터 ON). 세션은 T003 헬퍼로 analyzer DB. Cypher(`_ALL_OPS_QUERY`) 그대로.
- [ ] T005 [P] [US1] `services/reverse_intent/brief.py`: PoC `brief.py` 이식(무손실 렌더 + `split_by_budget` 오퍼레이션 원자, 규칙 중간 분할 금지). `TOKEN_BUDGET` 명명 상수.
- [ ] T006 [P] [US1] `services/reverse_intent/merge.py`: PoC `merge.py` 이식(테이블 dedup 병합, `_sourceTables` 보존).
- [ ] T007 [US1] `services/intent_runner.py`: `_build_reverse_prompt(brief_text)` 추가(PoC intent_runner의 역방향 지시 이식). 기존 `_save_intent_result`·`extract_json` 재사용. PoC intent_runner/skill_runner/neo4j_client 복사본은 **이식하지 않음**(폐기, research D2).
- [ ] T008 [US1] `services/reverse_intent/pipeline.py`: async 오케스트레이터 = analyzer 세션→assign_groups→split_by_budget→(브리프별 `skill_runner.run_skill_once("robo-proposals","robo-proposal-intent", _build_reverse_prompt(brief))`)→`merge_strategic_diffs`. 브리프 진행을 async generator로 yield(SSE용).
- [ ] T009 [US1] `services/reverse_source.py`: `list_sources()` = system DB `SHOW DATABASES` → 각 DB 오퍼레이션 프로브(>0)만 반환, 실패 시 `[ANALYZER_NEO4J_DATABASE]` 폴백(research D4). 명시적 에러(헌법 IV).
- [ ] T010 [US1] `routes/proposals_reverse.py`: `GET /reverse/sources`(T009) · `POST /reverse`(Proposal 노드 생성 mode=REVERSE_INTENT·reverseScope·합성 originalPrompt, db 오퍼레이션0이면 400) · `GET /{id}/stream/reverse`(T008 파이프라인 SSE: phase/log_line/brief_result/strategic_diff/done/error, 최종 strategicDiff 저장). contracts/reverse-intent-api.md 준수.
- [ ] T011 [US1] `router.py`: `proposals_reverse.router` 등록(기존 include 패턴).
- [ ] T012 [US1] `ui/ProposalCreate.vue`: 종류 라디오 `modeOptions`에 "코드에서 역추출(REVERSE_INTENT)" 추가 + 선택 시 자연어 textarea → 분석그래프 드롭다운 스왑(`GET /reverse/sources` 로드). submit 분기(REVERSE는 `store.createReverseProposal(db)`).
- [ ] T013 [US1] `stores/proposals.store.js`: `createReverseProposal(db)`(POST /reverse) + `subscribeToReverseIntent(id)`(EventSource `/{id}/stream/reverse`). `strategic_diff` 이벤트를 기존 intent 핸들러와 동일하게 `currentProposal.strategicDiff`에 병합(재사용).
- [ ] T014 [US1] `ui/ProposalDetail.vue`: `isReverse` computed 추가 + Intent 탭에서 결과는 기존 `IntentDecompositionView` 그대로(무수정 재사용) 표시.
- [ ] T015 [US1] **실 검증**(quickstart): `test` DB로 end-to-end 실행 → strategicDiff 생성, UserStory↔원본 op 1:1(누락·환각·중복0, SC-002) 원 그래프 대조. LLM 전 결정론(grouping/brief) 단독 검증도 포함.

**체크포인트**: US1 완료 = 문서 없이 코드→요구사항 MVP 동작(P2/P3 없이도 가치).

## Phase 4: User Story 2 — 사람이 읽을 수 있는 그룹 카드 (P2)

**목표**: 그룹을 업무명+작업목록 카드로. **독립 검증**: 그룹 카드가 logical_name(제목)+op logical_name(본문)으로 렌더, ⑥ 미완 시 폴백.

- [ ] T016 [P] [US2] `services/reverse_intent/labels.py`: 그룹 라벨 조립 = 제목(table logical_name→description→name 폴백) + kind 태그(write=핵심데이터/read=조회/logic=로직) + 대표 stereotype 한국어 매핑표(Command=데이터변경·Query=조회·BatchProcessor=일괄처리·Validator=검증·Adapter=연동·Aggregator=집계·EventTrigger=이벤트트리거·…·없음=기타) + op logical_name 접두어 정리.
- [ ] T017 [US2] `services/reverse_intent/pipeline.py` + `routes/proposals_reverse.py`: 실행 초반 `groups` SSE 이벤트 emit(카드 필드=labels.py 산출). grouping 결과에 라벨 부착.
- [ ] T018 [P] [US2] `ui/AnchorGroupList.vue`: `StagePlanReview.vue` 복제 → 그룹 카드 목록(제목·성격배지·작업수·작업목록). 라벨/키만 교체.
- [ ] T019 [US2] `ui/ReverseIntentTrack.vue`: 모드 전용 트랙 컨테이너(소스선택 확인→그룹카드(T018)→실행 로그). `OdaStandardTrack.vue` 패턴. ProposalDetail isReverse에서 마운트.
- [ ] T020 [US2] **검증**: `test`(⑥완비)=업무명 카드 정상 / ⑥ 미완 그래프(또는 logical_name None 테이블)=폴백 라벨 + 가독성 경고(FR-013).

## Phase 5: User Story 3 — 사이즈 무관·무손실·무중복 (P3)

**목표**: 대용량 무손실. **독립 검증**: 큰 DB 전체 실행, 커버리지100%·중복0·예산분할 무결.

- [ ] T021 [US3] **검증**: 규칙 많은 그룹(예 RWIS RDD01DD 계열)에서 전 op 정확히 1그룹(커버리지100%·op↔group 중복0, SC-004). 카운트 대조.
- [ ] T022 [US3] **검증**: 예산 초과 그룹이 오퍼레이션 경계에서만 분할(규칙 중간 분할 0, FR-009). part/total 확인.

## Phase 6: Polish & Cross-Cutting

- [ ] T023 [P] `tests/test_reverse_intent.py`: grouping/brief/merge 결정론 단위테스트(고정 입력→고정 출력, 커버리지·중복 불변식).
- [ ] T024 [P] **회귀**: 기존 3모드(SIMPLIFIED/DETAILED_DDD/ODA) create·intent·plan 정상 + analyzer 그래프 노드/관계 수 실행 전후 동일(읽기전용, FR-015).
- [ ] T025 마무리: PoC 참조·데드 제거, 마커주석 0, `INFRA_TABLE_HINTS`/`TOKEN_BUDGET` 단일 상수 확인(헌법 III), 응답/로그 한국어 가독.

---

## Dependencies

- **Setup(T001) → Foundational(T002~T003) → US1(T004~T015)**. US1이 MVP.
- **US2(T016~T020)**: US1의 grouping/pipeline/route/store 위에 얹음(그룹 표시). US1 선행.
- **US3(T021~T022)**: 검증 위주. US1 완료 후 가능.
- **Polish(T023~T025)**: 전체 후.
- T004/T005/T006 [P] 병렬(서로 다른 파일). T007→T008(빌더 필요). T009→T010→T011 순차(라우트). 프론트 T012→T013→T014 순차(store 의존).

## Parallel 예시

- Foundational 후: `T004`·`T005`·`T006` 동시(grouping/brief/merge 독립 파일).
- US2: `T016`(labels)·`T018`(AnchorGroupList) 동시.
- Polish: `T023`·`T024` 동시.

## MVP 범위

**US1(T001~T015)** 만으로 "문서 없이 코드→요구사항" 완성. US2(가독 카드)·US3(대용량 검증)은 증분.

## 검증 기준(스토리별)

- US1: `test` DB end-to-end → strategicDiff, op↔US 1:1(SC-002), 하류 plan 무변경 통과(SC-005).
- US2: 그룹 카드 업무명 렌더(SC-003), 폴백 동작(FR-013).
- US3: 커버리지100%·중복0(SC-004), 예산분할 무결(FR-009).
