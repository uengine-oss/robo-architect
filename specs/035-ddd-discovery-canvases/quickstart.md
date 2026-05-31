# Quickstart: DDD 발견 마법사 & 도메인 캔버스

전제: 백엔드 `uvicorn api.main:app --reload`, 프런트 dev 서버, Neo4j 기동. 엔진 기본=in-process(설정에서 claude-ide 전환 가능).

## Q1 — 맨땅에서 마법사 시작 (US1)
1. 요구사항 탭, 트리가 비어 있을 때 "DDD 발견 마법사" 진입.
2. 프로파일링 4문항(프로젝트 유형/DDD 경험/팀 규모/보유 산출물) 응답.
3. 추천 단계 조합(예: Understand→Discover→Decompose→Strategize→Define→Code)이 체크리스트로 제시 → 가감 후 시작.

## Q2 — Understand & 핵심 액터 (US4)
1. 비즈니스 본질/사용자/목표 3그룹 질문에 응답 또는 기존 문서 붙여넣기.
2. 핵심 액터 후보가 식별되어 산출물에 기록 → 확인 시 그래프 반영.

## Q3 — EventStorming & 피보탈 (US2)
1. 도메인 이벤트를 시간순 입력(또는 LLM 초안).
2. 피보탈⭐·핫스팟🔥 후보가 표시 → 토글로 조정(`POST /pivotal-events/toggle`).
3. 기존 요구사항에서 도출된 이벤트와 중복 시 병합 후보 표시.

## Q4 — Decompose (피보탈 경계) (US2)
1. 피보탈 이벤트 경계로 서브도메인 후보 제안(`subdomains/propose`).
2. 확인 시 BC 노드로 생성(`POST /bounded-context`).

## Q5 — Strategize 3분류 (US6)
1. 각 서브도메인/BC에 분류 질문("외부 아웃소싱 시 고객이 알아챌까?").
2. core/supporting/generic 확정 → 배지 표시(컨텍스트 맵/캔버스).

## Q6 — BC 상세 & Canvas (US3)
1. 트리/설계 캔버스에서 BC 클릭 → BC 전용 상세(탭) 오픈.
2. Canvas 탭에서 책임·유비쿼터스 언어·인/아웃바운드·비즈니스 결정 확인.
3. "자동생성"(엔진 토글 적용, SSE) → 초안 propose→confirm → 편집·저장(`PATCH /contexts/{id}/canvas`).
4. 다시 열어도 유지(SC-003: 3초 내 오픈).

## Q7 — Aggregate Canvas (US5)
1. Aggregate 상세(AggregateViewerInspector)에서 Canvas 탭 선택.
2. 상태전이(Mermaid)·커맨드·이벤트·불변조건 확인/편집.
3. 자동생성(`generate-aggregate`) → propose→confirm.

## Q8 — 에픽 추가 경로 마법사 (US1)
1. 에픽 추가 다이얼로그에서 마법사 진입 → 기존 컨텍스트 기반 좁혀진 단계 추천.

## Q9 — 엔진 전환 & 설치 안내 (US1/FR-015)
1. Settings에서 `requirementGenerationEngine`=claude-ide 선택.
2. 미설치 시 생성 시도 → 차단 없이 설치 안내 + in-process 전환 제안(`GET /local-tooling/status`).

## Q10 — .ddd 내보내기 (US7)
1. "그래프 → .ddd 내보내기"(`POST /ddd-export`) → `.ddd/` 트리 생성 확인.
2. (선택) 외부 수정 후 가져오기 → diff propose→confirm.

## Q11 — propose→confirm 무변경 보장 (FR-016)
1. 임의 단계/캔버스 초안을 "거부" → 그래프 노드 생성/수정 0건 확인.

## Q12 — 언어 정책 (FR-021)
1. 기어 아이콘 언어를 변경 → 마법사/캔버스 산출물이 해당 언어로 생성됨.

## Q13 — Ingestion 병행 & 상호 진입구 (US1/FR-024)
1. Requirements 탭에서 "문서 업로드"(기존 일괄)와 "DDD 마법사"(신규)가 함께 보임.
2. 일괄 모달의 "인터뷰로 시작" → 마법사 진입, 마법사의 "문서 일괄 투입" → 일괄 모달 진입(같은 그래프 공유).

## Q14 — 후반 단계 = 기존 설계 기계 재사용 (FR-025)
1. 마법사 Decompose 확정 → BC 생성(기존 `POST /bounded-context`).
2. 마법사 Code 단계 → 기존 증분 설계(`/api/ingest/user-stories/design`)가 동일 진행 모달로 스트리밍되어 Aggregate/Command/Event 생성.
3. Event Modeling/Design 탭에서 결과 확인(기존 design-reflect와 동일).

## Q15 — 전체 ingestion clear 경고/보존 (FR-027)
1. 마법사로 BC·피보탈 이벤트 확정.
2. 이후 "문서 업로드"(전체) 실행 시 "모델 재구축" 경고 표시.
3. 진행해도 `Event.pivotal/hotspot`·확정 BC가 보존되거나(보존 경로), 증분 경로 사용이 권장됨.

## Out-of-band 회귀
- 기존 `ddd_spec` `specs/bounded-contexts/` 생성 경로 무회귀(research R2).
- 신규 Neo4j 라벨/관계 0건(스키마 diff).
- spec 030 clarification / 034 child-story·design-reflect 무영향.
