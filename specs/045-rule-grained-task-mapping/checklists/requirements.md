# Specification Quality Checklist: 코드분석 Task↔Rule 매핑 단위 정합

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-06-29
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) — 근본원인 절은 "비교 단위가 컨테이너라 거칠다" 수준의 개념·근거이고, 요구사항/성공기준은 산출물(매핑 생성) 관점. 특정 함수·API 시그니처는 명시하지 않음.
- [x] Focused on user value and business needs — US1=코드분석이 설계에 반영(핵심 가치).
- [x] Written for non-technical stakeholders — "파일/규칙/업무 단계" 일상어 + 비유 가능 수준.
- [x] All mandatory sections completed — User Scenarios / Requirements / Success Criteria 작성.

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain — 합리적 기본값으로 채움(아래 Notes).
- [x] Requirements are testable and unambiguous — FR-001~007 각각 검증 가능(비교 단위, 게이트 금지, 전략무관, 정밀도, 생산자 불변, 0건 방지, 비용 상한).
- [x] Success criteria are measurable — 0%→상승, 0→N 후보, 코드 모양 무관, 오매핑 억제.
- [x] Success criteria are technology-agnostic — "매핑이 생성된다/후보가 회복된다" 산출 기준(특정 점수/엔진 미명시; 0.45 등 수치는 근거 절에만 증거로 표기).
- [x] All acceptance scenarios are defined — US1~3 Given/When/Then.
- [x] Edge cases are identified — 무관 task / 거대 단위 / 규칙 0 / 경합 / 규칙 폭증.
- [x] Scope is clearly bounded — 범위=소비자 매칭 로직, 비목표=생산자/신규스키마/프론트/BPM·ES 생성.
- [x] Dependencies and assumptions identified — Assumptions 절(추출 품질·세션 규모·기존 인터페이스 재사용·dbms 미검증·생산자 불변).

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria — FR↔US/Edge/SC 대응.
- [x] User scenarios cover primary flows — 코드분석→매핑→이벤트스토밍 주흐름.
- [x] Feature meets measurable outcomes defined in Success Criteria — SC-001~004.
- [x] No implementation details leak into specification — HOW(어느 함수/문턱 조정 등)는 plan으로 미룸.

## Notes

- **수치(0.31/0.61/0.45)**: 요구사항이 아니라 "왜 컨테이너가 거친가"의 **증거**로 Background 절에만 둠. 요구/성공기준은 수치 비의존(산출=매핑 생성).
- **dbms 라이브 검증**: 현재 dbms 그래프 미확보 → SC-004에 "확보 시 확인"으로 명시(미검증 구간 솔직 표기, 추정 금지).
- **HOW 결정 보류(→ /speckit-plan)**: ① 컨테이너 게이트 제거 vs 약화, ② Rule 임베딩 blob 구성(예시 GWT만 vs 루틴요약/테이블 포함), ③ 비용 상한 방식 — 구현 설계에서 확정.
