# Specification Quality Checklist: 설치본 런타임 감독과 복구

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-17
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain — 2건 모두 2026-09-17 사용자 결정으로 해소
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded — 비목표 명시 (릴리스 빌드=robo-workspace 소유 · SSO · 강제 이어받기 · mac 패키징)
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## 해소된 결정 (2026-09-17)

| 물음 | 답 | 범위에 미친 영향 |
|---|---|---|
| 설치본 저장소 구성 | **Ontological 로 맞춘다** | 사용자·프로젝트 관리가 설치본 범위 안으로 들어옴 (US6 · FR-028~032 · SC-010/011) |
| 인수 검증 환경 | **Windows 장비 있다** | 실제 설치본을 오프라인으로 잰다 (FR-033~035 · SC-001). mac 패키징은 미검증으로 명시 |

## 선행 조건 — 이 스펙 밖

릴리스 빌드가 나와야 SC-001 을 시작할 수 있다. 현재 막혀 있다:

- ~~서브모듈 포인터 둘이 **원격에 없는 커밋**을 가리켜 clone 이 실패한다~~ —
  **2026-09-17 해소.** 두 브랜치를 올렸고 빈 저장소에서 포인터 커밋 fetch 확인
  (`5534115` · `e1c3d65`). "쓰기 권한 없음(403)"은 틀린 판정이었다
- ~~`antlr-code-parser` 는 실측 403~~ — **권한 받아 09-17 푸시 완료** (`3160b6c`).
  다만 올린 것만으로는 릴리스에 안 들어가 `workspace.json` pin 을 같이 고쳤다
  (커밋 `893766a`, **미푸시 — 하네스 차단**)
- `enterprise-delivery-p` 의 `893766a`(antlr pin) 미푸시 — **하네스가 막았다. 사용자 몫.**
  릴리스를 실제로 막는 것은 이것 하나다
- `robo-workspace` PR #1 미병합 — **막지 않는다.** 두 커밋이 delivery 에 같은 SHA 로
  있고 릴리스는 delivery 에서 돈다. 정리 목적
- `ROBO_LLM_API_KEY` · `OPENAI_API_KEY` 미설정 — required 6 중 이 둘만 비어 있다

**남은 셋은 `robo-workspace` / 타 팀 저장소 소유다.** 계획 단계에서 이 선행 조건의
해소 여부에 따라 태스크 순서가 갈린다.

> **물려받은 차단 판정은 실측 없이 믿지 않는다.** 위 첫 항목은 "권한 없음"으로
> 여섯 곳에 적혀 회차마다 넘어갔는데, 재 보니 권한이 있었다. 같은 줄에 묶여 있던
> `antlr` 만 진짜였다 (done-v2 §64).

## Notes

- 이 체크리스트는 스펙 품질만 판정한다. **기능이 동작한다는 판정이 아니다.**
- SC-008 이 요구하는 "결함을 심어 검사가 무는 것"은 구현·검증 단계에서 수행한다.
