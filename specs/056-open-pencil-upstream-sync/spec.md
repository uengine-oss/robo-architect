# Feature Specification: open-pencil upstream 동기화 + 컴포넌트 생성 고도화 + Proposal 초안 스토리보드

**Feature Branch**: `056-open-pencil-upstream-sync`
**Base Branch**: `044-design-import`
**Created**: 2026-09-04
**Status**: 구현 완료 (Implemented)
**Input**: 사용자 요청 — "open-pencil 저장소가 어떻게 업데이트 되었는지 확인하고 기존 연동해 놓은 것과 비교하여 컴포넌트 생성 기능이라던지 무엇을 업데이트하면 좋을지 비교검토", 이어서 "Proposal 단에서 초안을 제시할 때 디자인된 결과로 스토리보드가 곧바로 보이면 좋겠다 — 설계와 디자인이 다 맞춰진 후에야 유저저니를 볼 수 있는 지금이 아니라, proposal 초기에 보이는 게 open-pencil 사용의 취지에 맞다"

---

## 개요

Robo Architect는 화면 렌더링 엔진으로 **open-pencil**(오픈소스 디자인 에디터)을 서브모듈로 품고 있다.
그동안 쓰던 것은 2026-04-10에 분기한 fork(`jinyoung/open-pencil`)였고, 그 사이 upstream
(`open-pencil/open-pencil`)은 약 **1,491 커밋**, 릴리즈로는 **v0.12 → v0.13 → v0.14.0**(2026-08-11)만큼
전진해 있었다.

이 피처는 두 가지를 한다.

1. **동기화와 재이식** — 서브모듈을 upstream master 기준으로 올리고, Robo Architect가 쓰던 커스텀
   (federation 컴포넌트, 컴포넌트 라이브러리 렌더 서비스)을 v0.14의 새 패키지 구조 위에 다시 얹는다.
2. **초안 스토리보드** — Proposal의 Intent(전략 분해) 결과가 나오는 즉시, 그 저니(user journey)의
   각 화면을 open-pencil 와이어프레임으로 렌더해 Intent 탭에서 바로 보여준다.

두 번째가 이 피처의 사용자 가치다. 지금까지 유저 저니 화면은 설계(Aggregate·Command·Event)와
디자인(Figma 바인딩)이 모두 맞춰진 **뒤에야** 볼 수 있었다. 초안 단계에서 "이 요구사항이 화면으로는
어떻게 생겼나"를 못 보면, 이해관계자는 텍스트 다이어그램만 보고 승인 여부를 판단해야 한다.

---

## 조사 결과 — upstream이 해결해 준 것

| 항목 | fork(2026-04-10) | upstream master(2026-09-03) |
|---|---|---|
| JSX `<Instance>` | 동작하지 않음 — `Instance is not defined` / `Component resolution depth exceeded` | 2026-05-31 정식 지원, 2026-07-21 오버라이드 추가 |
| 인스턴스 해석 | 백엔드가 `$INSTANCE:Name\|k=v` 마커 프레임을 심고 사후 retype | 이름·ID·COMPONENT_SET(variant prop 매칭)으로 렌더러가 직접 해석 |
| 자식 오버라이드 | 마커 문자열 파싱 | `overrides={{ 'label:text': '…' }}` → `instanceOverrides`에 기록되어 컴포넌트 동기화에도 잔존 |
| 컴포넌트 도구 | 없음 | `create_component`·`create_instance`·`combine_as_variants`·`expose_instance_swap`·`node_to_component`·`get_components`·`design_to_component_map`·`design_to_tokens` |
| 컴포넌트 라이브러리 | `.fig` 파일을 매번 로드해 카탈로그 추출 | 퍼블리시/리비전/오프라인 카탈로그 + `insert_library_component`(안정 asset key) |
| 입출력 | `.fig` 위주 | HTML/CSS/Tailwind/JSX 임포트, HTML 번들·PPTX·PDF 내보내기 |
| MCP | stdio | `openpencil-mcp-http` + 다중 문서/페이지 타겟팅 + ACP 원격 MCP |
| 패키지 구조 | `@open-pencil/core` 단일 | `scene-graph`·`fig`·`kiwi`·`pen`·`dom-css`로 분리 (v0.14 breaking) |

spec 024 `lessons-learned.md`의 **L4**("open-pencil의 `<Component>`/`<Instance>` JSX가 깨져 있다")는
upstream에서 해결됐다. 따라서 마커 우회는 라이브러리 렌더 경로에서 제거 가능하다.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — upstream 동기화 후에도 기존 화면이 그대로 동작한다 (Priority: P1)

아키텍트로서, open-pencil을 최신 upstream으로 올린 뒤에도 Design 탭의 화면 편집·미리보기·AI 채팅이
전과 같이 동작하기를 원한다. Neo4j에 이미 저장된 sceneGraph를 다시 만들 필요가 없어야 한다.

**Independent Test**: 기존 sceneGraph가 붙은 UI 노드의 Design 탭을 열어 프레임이 렌더되고 저장이
동작하는지 확인.

**Acceptance Scenarios**:
1. **Given** Neo4j에 기존 포맷(`nodes` 맵 + base64 `images`)의 sceneGraph가 있을 때,
   **When** Design 탭을 열면, **Then** FrameEditor가 프레임을 렌더한다.
2. **Given** FrameEditor에서 요소를 편집했을 때, **When** 저장을 누르면,
   **Then** 같은 JSON 포맷으로 다시 저장된다.
3. **Given** upstream이 `instanceOverrides`를 Map으로 바꿨을 때, **When** 직렬화·역직렬화하면,
   **Then** 오버라이드가 손실되지 않는다.

### User Story 2 — 네이티브 `<Instance>`로 컴포넌트를 조립한다 (Priority: P1)

와이어프레임 생성 에이전트로서, 디자인 시스템 컴포넌트를 마커 우회 없이 JSX 원문법으로 배치하고
싶다. 변형(variant)을 고르고 자식 텍스트를 오버라이드할 수 있어야 한다.

**Independent Test**: 렌더 서비스 `/render`에 `<Instance component="…" overrides={{…}} />` JSX를
보내 INSTANCE 노드가 포함된 sceneGraph가 오는지 확인.

**Acceptance Scenarios**:
1. **Given** 컴포넌트 라이브러리가 로드됐을 때, **When** `<Instance component="btn-main-task"
   overrides={{ "label:text": "장바구니에 추가" }} />`를 렌더하면, **Then** INSTANCE 노드와 오버라이드된
   텍스트가 나온다.
2. **Given** COMPONENT_SET의 속성명에 공백이 있을 때(`Property 1`), **When**
   `variant={{ "Property 1": "Default" }}`를 주면, **Then** 해당 변형이 선택된다.
3. **Given** 레거시 `$INSTANCE:Name|text=…` 마커 JSX가 들어올 때, **When** 렌더하면,
   **Then** 서비스가 `<Instance>`로 변환해 동일 결과를 만든다(하위 호환).
4. **Given** 존재하지 않는 아이콘 이름이 JSX에 있을 때, **When** 렌더하면,
   **Then** 렌더 전체가 실패하지 않고 같은 크기의 플레이스홀더가 대신 들어간다.

### User Story 3 — Proposal 초안에서 저니를 스토리보드로 본다 (Priority: P1)

PO/아키텍트로서, Proposal의 Intent 분해가 끝나는 즉시 그 저니의 화면들을 와이어프레임 카드로
훑어보고 싶다. 설계·디자인 정합을 기다릴 필요가 없어야 한다.

**Independent Test**: 저니가 있는 DRAFT Proposal을 열어 Intent 탭 상단에 스토리보드가 나타나고
화면이 순서대로 렌더되는지 확인.

**Acceptance Scenarios**:
1. **Given** Intent가 `strategicDiff`와 `journeys`를 산출했을 때, **When** 저장이 끝나면,
   **Then** 백엔드가 자동으로 스토리보드 생성을 시작한다.
2. **Given** 스토리보드 생성이 진행 중일 때, **When** Intent 탭을 보면,
   **Then** 진행률(`n/m 화면`)과 대기 중 카드가 보이고 완료된 화면부터 차례로 채워진다.
3. **Given** 저니에 분기(gateway) 스텝이 있을 때, **When** 스토리보드를 보면,
   **Then** 분기는 마름모 표기로 흐름 안에 표시되고 렌더 대상에서는 제외된다.
4. **Given** 저니가 아예 없고 UserStory만 있을 때, **When** 스토리보드를 만들면,
   **Then** UserStory 순서로 흐름을 합성해 렌더한다.
5. **Given** 렌더된 화면 카드가 있을 때, **When** ✎를 누르면,
   **Then** open-pencil 편집기가 열리고 저장 시 그 스텝에 반영된다.

### Edge Cases

- 한 화면 렌더가 실패해도 나머지는 계속 진행하고, 실패 카드만 "렌더 실패"로 표시한다.
- 렌더 예산은 화면 12개(`STORYBOARD_MAX_STEPS`)로 제한해 큰 저니에서도 폭주하지 않는다.
- 동시 렌더는 2개(`_RENDER_CONCURRENCY`)로 제한한다.
- 생성 중 새로고침해도 부분 결과가 Neo4j에 저장돼 있어 이어서 보인다.
- 컴포넌트 라이브러리 서비스가 죽어 있으면 카탈로그 컨텍스트 없이(순수 프리미티브로) 렌더한다.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 서브모듈은 upstream master 기반 브랜치에서 동작해야 하며, 이전 fork 상태는 별도
  브랜치로 보존해야 한다.
- **FR-002**: sceneGraph JSON 전송 포맷(`{nodes, rootId, images}`)은 변경 없이 유지해야 한다 —
  Neo4j 저장분, Figma 플러그인, `ddd_spec/wireframe_render.py`가 이 포맷을 읽는다.
- **FR-003**: 렌더 서비스는 네이티브 `<Instance>`와 레거시 `$INSTANCE:` 마커를 **모두** 받아야 한다.
- **FR-004**: 컴포넌트 카탈로그(`/components?format=prompt`)는 변형 속성과 오버라이드 가능한 텍스트
  자식 이름을 포함해야 한다.
- **FR-005**: Intent 완료 직후 스토리보드 생성이 자동으로 예약되어야 한다.
- **FR-006**: 스토리보드는 `Proposal.storyboard` 속성에 저장되고, 부분 완료 상태도 저장되어야 한다.
- **FR-007**: `ProposalResponse`에 실리는 스토리보드는 sceneGraph를 제외한 경량 버전이어야 한다
  (목록 응답이 수 MB가 되지 않도록).
- **FR-008**: 스토리보드 화면은 open-pencil 편집기로 수정하고 되저장할 수 있어야 한다.
- **FR-009**: 신규 Neo4j 노드·관계는 만들지 않는다 — `Proposal`에 속성 1개만 추가한다.

### Key Entities

- **Proposal.storyboard** (신규 속성, JSON 문자열):
  `{status, generatedAt, total, done, failed, journeys: [{id, name, description, steps: [...]}]}`
- **storyboard step**: `{id, name, kind: 'screen'|'gateway', next: [id], description, userStoryId,
  status: 'pending'|'done'|'failed'|'skipped', sceneGraph, frameId, summary, error}`

---

## Success Criteria *(mandatory)*

- **SC-001**: `bun run build:packages`와 프론트엔드 프로덕션 빌드가 통과한다. ✅
- **SC-002**: `/render`가 네이티브 Instance·레거시 마커·컴포넌트 배치 3가지 입력을 모두 처리한다. ✅
- **SC-003**: 저니 4화면 Proposal의 스토리보드가 실패 0으로 완료된다. ✅
  (실측: 화면당 노드 121~392개, 디자인 시스템 인스턴스 16~58개)
- **SC-004**: Intent 탭에서 스토리보드 → 편집기까지 Playwright 시나리오가 통과한다. ✅
- **SC-005**: 기존 proposal_lifecycle 테스트가 회귀 없이 통과한다. ✅ (77 passed, 1 skipped)

---

## 구현 결과 (2026-09-04)

| 구분 | 내용 |
|---|---|
| open-pencil 서브모듈 | 브랜치 `robo-upstream-sync` = upstream master `cb7ceea6` + 재이식 커밋 2건. 이전 fork는 `robo-fork-legacy`(`d0b4dd9`)로 보존 |
| 신규 백엔드 | `services/storyboard_runner.py`, `routes/proposals_storyboard.py`, `tests/test_storyboard.py` |
| 신규 프런트 | `features/proposals/ui/ProposalStoryboard.vue` |
| 신규 federation | `open-pencil/src/federation/FramePreviewChat.vue` (044가 참조하던 누락 컴포넌트) |
| 신규 API | `GET/POST /api/proposals/{id}/storyboard`, `PUT …/storyboard/steps/{stepId}` |
| 신규 스크립트 | `scripts/seed_proposal_storyboard_demo.py` (LLM 없이 재현 가능한 시드) |
| 테스트 | 단위 9건 신규(총 77 passed), Playwright `proposal-storyboard.spec.ts` 1건 |
| 시연 | `frontend/tests/.artifacts/storyboard/proposal-storyboard-demo.webm` |

자세한 이식 과정과 함정은 [implementation-notes.md](implementation-notes.md), 사용법은
[manual.md](manual.md), 개발 런북은 [quickstart.md](quickstart.md)를 참고한다.
