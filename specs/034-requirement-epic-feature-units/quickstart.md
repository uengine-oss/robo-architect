# Quickstart: Epic / Feature 단위 요구사항 등록·뷰·편집·레이더 필터링

**Feature**: 034-requirement-epic-feature-units | **Date**: 2026-05-30

수동 스모크 시나리오. 사전: 백엔드 `uvicorn api.main:app --reload --host 127.0.0.1 --port 8000`, 프런트 `vite` 기동, Neo4j 연결, Requirements 탭 진입.

## Q1 — "+" 단위 선택 노출 (FR-001)
1. Requirements 탭에서 "+" 클릭.
2. **기대**: Epic / Feature / User Story 단위 선택지가 보인다.

## Q2 — Epic 수동 등록 (FR-002)
1. "+" → Epic → 수동 탭 → 이름·설명 입력 → 확정.
2. **기대**: 트리 최상위에 새 Epic 추가, 선택 가능. (`POST /bounded-context` 201)

## Q3 — Feature 등록(소속 Epic 지정) (FR-003)
1. "+" → Feature → 소속 Epic 선택 → 이름 입력 → 확정.
2. **기대**: 해당 Epic 하위에 Feature 추가.

## Q4 — AI 제안 흐름 + 폴백 (FR-005, FR-006)
1. "+" → Feature → AI 제안 탭 → 자연어 설명 입력 → "제안" 요청.
2. **기대**: 후보 목록 표시 → 검토 후 확정/수정/취소 가능.
3. (음성 테스트) LLM 키 미설정/0건 → 후보 빈 상태 + 수동 탭으로 폴백 가능.

## Q5 — User Story 등록 회귀 (FR-004, SC-006)
1. "+" → User Story → 기존처럼 자연어 propose 또는 수동 입력 → 확정.
2. **기대**: 기존과 동일하게 동작(회귀 없음), 적절한 Feature 배치.

## Q6 — Epic 뷰 페이지 (FR-007)
1. 트리에서 Epic 노드 선택.
2. **기대**: Epic 전용 뷰에 이름·설명·출처 + 하위 Feature 목록/요약 표시(≤2초, SC-003).

## Q7 — Feature 뷰 페이지 (FR-008)
1. 트리에서 Feature 노드 선택.
2. **기대**: Feature 전용 뷰에 이름·설명 + 하위 User Story 목록 표시.
3. User Story 노드 선택 → 기존 상세 그대로(FR-009).
4. (빈 상태) 하위 없는 Epic/Feature → 빈 상태 + 추가 CTA(US2-AC4).

## Q8 — Epic/Feature 편집 (FR-010, FR-011, FR-012, SC-004)
1. Feature 뷰 → "편집" → 이름 변경 → 저장.
2. **기대**: 새로고침 없이 트리·뷰에 새 이름 반영. 하위 User Story 연결 유지.
3. 이름을 비우고 저장 시도 → 검증 오류로 차단.
4. 편집 중 "취소" → 변경 폐기, 직전 상태 유지.

## Q9 — radar 범위 필터링 (FR-013, FR-014, FR-015, SC-005)
1. Feature A 선택 → radar가 A 범위 10카테고리 점수 표시.
2. 다른 Feature B 선택 → 점수가 B 범위로 갱신(범위 혼입 0건).
3. Epic 선택 → 하위 모든 Feature/US 합산.
4. 전체(선택 해제) → 프로젝트 전체로 갱신.
5. 요구사항 0건 범위 선택 → 빈/중립 상태(정보, 오류 아님).

## Q10 — 수동 배치 보호 (FR-016)
1. 수동 등록/배치한 Feature·User Story 확인 후 자동 재분류 트리거(인제스천 재실행 등).
2. **기대**: 수동 항목이 임의로 덮어써지지 않음.

## Q11 — 하위 US 자동 생성 (in-process) (FR-018/019/022, SC-007)
1. Settings에서 생성 엔진을 "in-process LLM"으로 설정.
2. 새 Feature를 등록 → 확정 직후 하위 User Story 후보가 자동 제안된다.
3. 진행 표시(SSE)가 보이고, 도중 취소가 가능하다.
4. 후보 중 일부만 선택·수정 후 확정 → **선택 항목만** 해당 Feature 아래 트리에 추가.
5. 모두 미선택(취소) → 트리에 아무 US도 추가되지 않음.

## Q12 — 하위 US 자동 생성 (Claude IDE) + 설치 안내 (FR-020/021, SC-008)
1. Settings에서 생성 엔진을 "Claude IDE"로 설정.
2. (설치된 환경) Epic/Feature 등록 → speckit-specify 스킬로 하위 US 생성, 동일 제안→확인 흐름.
3. (미설치 환경) 로컬에 claude/speckit 없음 → 생성 대신 **설치 안내** 표시(생성 시도 안 함).
4. claude만 있고 speckit 스킬만 없는 경우 → 부분 설치 안내(Edge Case).

## Q13 — DDD 적합성·입도·정합성 검증 (FR-024~028, SC-009)
1. 의도적으로 다른 BC에 더 어울리는 Feature를 어떤 Epic에 추가.
2. **기대**: "이 Feature는 BC X가 더 적절" 경고 + 재배치 교정안 제안.
3. 지나치게 큰 범위의 Feature 추가 → 분할안 제안.
4. 기존 spec과 충돌하는 요구사항 추가 → 충돌 지점 + 정합 방향(병합/대체/구분) 제안.
5. 교정안 거부하고 강행 → 경고는 남되 차단되지 않음(BC가 전혀 없으면 BC 선행 요구).
6. 적합한 케이스 → 경고 없이 통과.
7. (스킬 부재 시) robo-spec `robo-validate`(또는 speckit-specify override)로 검증이 끊김 없이 동작.

## Q14 — 설계 자동 반영: Event Modeling/Design 진입 (FR-030~034, SC-011)
1. 설계가 반영되지 않은 US를 하나 이상 만든다.
2. Requirements → **Event Modeling**(또는 **Design**) 탭으로 이동.
3. **기대**: "설계에 반영하시겠습니까?"(대상 US) 프롬프트 표시.
4. "예" → 설계 생성 진행(SSE) → 새 사용자 journey 추가/Aggregate 생성·변경안 생성 → 사용자 확인 후 그래프 반영.
5. "아니오" → 변경 없이 진입, 다음 진입 시 다시 식별.
6. 미반영 US가 없으면 → 프롬프트 없이 평소처럼 진입.
7. "이번 세션 동안 묻지 않기" 선택 시 반복 억제.

## Out-of-band 점검
- **언어 정책(FR-017)**: 기어 아이콘 언어를 바꾼 뒤 AI 제안 텍스트가 해당 언어로 생성되는지.
- **회귀(SC-006)**: 기존 User Story 추가/상세/명확화 e2e 통과.
- **스키마 불변**: `docs/cypher/schema/` diff 0건, 신규 노드 라벨/관계 0건.
