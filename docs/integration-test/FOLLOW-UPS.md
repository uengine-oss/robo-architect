# 통합검증 — 후속·미구현 정리 (이후 탭에서 진행)

통합 검증 중 발견했지만 **해당 탭 범위를 넘어가거나(다른 탭/공유 모듈), 신규 feature 규모이거나, 미구현인** 항목을 모은다. 각 항목은 **어느 탭/세션이 이어받을지**로 그룹핑.

> 출처 표기: `[I##]`는 [tabs/proposals.md](tabs/proposals.md), `[Stories I##]`는 [tabs/stories.md](tabs/stories.md) 이슈 원장 참조.
> 상태: 🔴 미구현 · 🟠 보완필요(부분) · 🟡 경미/간헐 · 🔵 설계과제(신규 feature)

---

## A. Process 탭 (BPM · Event Modeling) 에서 다룰 것

| 항목 | 상태 | 내용 | 비고 |
|---|---|---|---|
| **[I18-C] 이벤트모델링 미리보기 오버레이** | 🔵 | 040 미리보기에서 **신규(CREATE) Command/Event/ReadModel이 Processes 뷰어에 안 보임**. Data 뷰어만 오버레이(라이브+diff 합성)가 있고, processes/design/process 뷰어는 라이브 읽기전용뿐. | 현재는 A(processes 재매핑)+안내(PreviewBanner notice)로 완화. **완전 해결 = 이벤트모델링에 Data와 동급 오버레이 구현**(`build_event_modeling_preview` + eventModeling.store preview-source + App.vue 오케스트레이션). 미러 대상 `event_modeling.py` ~1040줄 = speckit 피처화 권장(예: 044). |
| 042/043 통합 검증 본체 | 🟠 | 단일 Process탭(BPM⇄EM 토글), task=UI 일관화, ES 승격 UI 등 042/043 기능 자체의 라이브 검증 | Process 탭 정식 검증 시 수행(아직 미실행) |

## B. Design / Data / Process 공유 — 모델 편집(model_modifier)

| 항목 | 상태 | 내용 | 비고 |
|---|---|---|---|
| **[I20] 챗에 ValueObject 타입 없음** | 🟠 | 챗(model_modifier)으로 "VO 추가" 시 ValueObject 노드가 아니라 **Property(또는 VO타입 속성)**로 들어감. `targetType` enum에 ValueObject 부재([react_streaming.py:652](../../api/features/model_modifier/react_streaming.py#L652)). | 진짜 VO 노드 생성하려면: react_prompt/react_streaming targetType에 ValueObject 추가 + model_change_application 생성 핸들링. (apply_chat_drafts·preview_edit는 이미 valueObjects 컬렉션 지원.) Data/Design 챗 검증 시 함께. |
| 040 design/process 뷰어 오버레이 부재(공통) | 🔵 | I18-C와 동일 근원 — **design(UI)·process(BPM) 미리보기도 신규 요소 미표시**. 신규 UI를 Design preview로, 신규 Process를 Process preview로 "열기"해도 라이브만 보임. | Design/Process 탭에서 040 "열기" 검증 시 동일 안내(notice)는 이미 적용됨. 오버레이는 I18-C와 묶어 처리. |

## C. Code 탭 (Claude Code)

| 항목 | 상태 | 내용 | 비고 |
|---|---|---|---|
| **[I14] 종료된 proposal의 Code 세션 잔존** | 🟡 | proposal이 ACCEPTED/DESTROYED 되어 worktree가 삭제돼도 Code 탭 세션이 남아 `GET /api/claude-code/tree?root=.../.sandbox/proposal/PRO-NNN` **400 반복**(무해, 콘솔 로그). | (a) proposal terminal 상태/worktree 제거 시 해당 Code 세션 prune (b) FileTreePane이 root 부재를 우아하게 처리. Code 탭 세션 수명주기 검증 시. |
| **[I16] 폴더 피커 = 활성 세션** | 🟡 | Code 탭 폴더 피커가 **활성 세션**의 workdir만 바꿈 — main("프로젝트") 세션이 아니면 proposal projectRoot(=main 기준)가 안 바뀜. 잔여 세션과 겹치면 혼동. | main 루트 변경 동작을 명확히(또는 "프로젝트 루트 변경" 별도 UI) + 세션 정리(I14). Code 탭 검증 시. |

## D. Proposals 자체 후속 (이 탭 재방문 시)

| 항목 | 상태 | 내용 | 비고 |
|---|---|---|---|
| **041 Constitution / Plan 단계** | 🔴 미구현 | intent→plan 분리, 프로젝트 Constitution(인터뷰→constitution.md), plan 단계(전략+impact+아키텍처 구현계획)까지. **spec.md만 존재**(plan.md·tasks.md·코드 0). | 신규 feature. speckit으로 plan→tasks→구현 진행 필요. 현재 Proposals 흐름은 intent→submit→implement 단일 분해. |
| **[I4] impactMap 재생성 폴백** | 🟡 간헐 | 피드백 재생성 시 `robo-proposal-context`가 빈응답/timeout이면 `_fallback_impact_map`(빈약)으로 떨어짐. | 재현성 확인 → context 스킬 timeout 상향 또는 폴백 진입 로깅. 비결정적(LLM). |
| **[I12] property 중복노드 / divergence** | 🟡 | force-accept-with-failures 시 그래프엔 설계 전부 반영·코드는 부분(설계상 OK) + `apply`가 동일 property 노드를 **중복 생성**. | property 중복은 proposal_apply dedup. divergence는 사용자 인지(검증 FAIL≠그래프 미반영). |
| **[I2] 039 quickstart 스크립트 경로** | 🟡 확인 | quickstart가 `services/migration`, `schema_migrator --feature=039` 참조 — 실제 경로/동작 미확인. | 마이그레이션/스키마 스크립트 실재 확인. |

## E-2. 인증·감사 추적 (cross-cutting — 무인증 환경)

| 항목 | 상태 | 내용 | 비고 |
|---|---|---|---|
| **[Stories I7] 편집자 신원 미기록** | 🔵 | 편집 이력(033)에 `userName: "unknown user"`, `userEmail: "unknown@…MacBookPro.local"`(호스트명 fallback)로 기록됨 — 실제 사용자(`learning@uengine.org`) 반영 안 됨. **현재 로그인/인증 없는 환경**이라 신원 컨텍스트 부재. | 인증 도입 시 개선. 모든 편집/변경 이력(033·038·챗편집)에 동일 적용. 신규 feature(인증/사용자 컨텍스트) 규모. |

## E-3. DDD 마법사 (035) — LLM 출력 신뢰성

| 항목 | 상태 | 내용 | 비고 |
|---|---|---|---|
| **[Stories I32] Strategize 분류(classification) 영속 불안정** | 🟡 | 배선은 정상(`after.classification`→`bc.classification`+`bc.domainType` 둘 다 세팅, 이름해석·name오염방지 완료). 그러나 **LLM이 Strategize에서 구조화된 classification 변경을 안정적으로 발행 안 함** → 3회 시도 모두 domainType None. | 결정적 보강 필요: 엔진에서 step=strategize일 때 답변/artifact의 분류를 **결정적으로 파싱해 BC update 강제 생성**(LLM 의존 제거), 또는 분류 전용 경량 LLM 호출. 마법사 재방문 시. |
| **[Stories I22] 마법사 BC가 영문 기술명 없이 한글 name=displayName** | 🟡 | 마법사 BC create가 영문명 자동파생 안 함(서브도메인명이 한글). I1(수동/AI제안)과 달리 입력칸 없음. | 영문명 자동파생 또는 인제스천 정합. |

## E. 횡단(cross-cutting) — 아직 미검증 입력/연동 (해당 탭에서)

| 영역 | 스펙 | 비고 |
|---|---|---|
| 인제스천 토큰/서스펜드/배치 영속 | 017, 018 | Stories 탭 인제스천(S2/S3) 검증 시 포함 |
| PRD 생성/익스포트 | 007 | Stories/문서 |
| Figma 동기화/바인딩/와이어프레임 | 009, 016, 020, 024 | Design/외부연동 탭 |
| Confluence 인제스천 | 013 | 입력 |
| 문서 익스포트 템플릿 | 014 | 횡단 |
| Electron 데스크탑 / HTML policy / 시작 피커 | 023, 032 | 셸 |
| 생성 언어 정책 | 031 | 모든 생성 경로(Stories S14 등) |

---

## 우선순위 제안

1. **각 탭 정식 검증 시 해당 그룹 항목을 함께 처리** (A→Process, B→Design/Data, C→Code, E→Stories 등).
2. **신규 feature(🔵)** — I18-C(이벤트모델링 오버레이), 041(Constitution/Plan) — **speckit으로 별도 spec**(044~) 떠서 SDD로 진행 권장.
3. **경미(🟡)** — I4/I12/I14/I16/I2 — 해당 탭 검증 중 묶어서, 또는 백로그 유지.
