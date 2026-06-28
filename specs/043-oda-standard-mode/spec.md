# Feature Specification: ODA 표준 분해 모드 (ODA Standard Decomposition Mode)

**Feature Branch**: `043-oda-standard-mode`

**Created**: 2026-06-28

**Status**: Draft

**Input**: User description: ".claude/skills/oda-* 스킬들을 보고, proposal 에서 intent 를 분해해서 plan 을 세울때 ODA 표준에 맞추어 스펙을 검증, oda 표준을 근거한 설계를 할 수 있도록 하는 기능을 구현해보자. 옵션을 주면 ODA 표준을 근거하는것으로 ... 지금 Simple | DDD 심화 옵션이 있는데, 여기에 ODA 표준 옵션이 추가되는거지."

## Summary

Proposal 을 생성할 때 아키텍트가 고르는 **분해 모드**에 세 번째 옵션 **"ODA 표준"** 을 추가한다.
현재 두 모드(Simplified, DDD 심화)는 변경 없이 유지된다. ODA 표준 모드를 선택하면 Proposal 의
intent 분해와 plan 수립이 **TM Forum ODA 표준 지식 베이스**(SID/GB922 데이터 모델, TMF Open API,
ODA Component/Canvas 모델, Use-Case 라이브러리, BDD feature-kit)를 근거로 진행된다 —
요청을 표준에 매핑하고, 표준이 이미 정의한 것을 재사용하며, 모든 요소를 **REUSE / EXTEND / NEW**
로 분류하고, "준수 후 확장(comply-then-extend)" 거버넌스를 **차단형 적합성 게이트**로 강제한다.
결과 산출물은 표준 강도의 ODA 설계 패키지(적합성 리포트, SID 파생 데이터 모델, TMF Open API 계약,
ODA Component/Canvas 아키텍처, Cucumber/Gherkin `.feature` 파일)이며, 동시에 기존 strategic/tactical
diff 로 **수렴**하여 다운스트림(plan/impact/tasks/implement)은 분기 없이 동작한다.

## Clarifications

### Session 2026-06-28

- Q: ODA 표준 모드가 산출해야 할 범위는? → A: 전체 ODA 산출물 + BDD `.feature` 파일
  (검증/분류 + SID 파생 데이터 모델 + TMF Open API 계약 + ODA Component/Canvas 아키텍처 +
  ODA feature-kit 방언의 Cucumber/Gherkin `.feature` 파일).
- Q: 적합성 게이트가 FAIL(표준 위반)일 때 동작은? → A: 진행 차단 — 아키텍트가 명시적으로
  면제(waive)해야만 plan/submit 으로 진행 가능. 면제 사유를 기록한다.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - ODA 표준 모드로 Proposal 분해하기 (Priority: P1)

아키텍트가 새 Proposal 을 작성하면서 모드 스위치에서 **"ODA 표준"** 을 선택한다. 자연어 요청을
입력하고 진행하면, 시스템이 요청을 ODA 표준 지식 베이스에 매핑한다: 가장 가까운 Use Case(UCxxx),
관련 SID 도메인/엔티티, 기준이 되는 TMF Open API, 그리고 기능이 속할 ODA Component 블록
(coreFunction / managementFunction / securityFunction)을 식별해 **표준 정합성(Standards
Alignment)** 으로 제시한다. 아키텍트는 매핑을 검토·확정하고, 그 결과가 strategic diff(Epic/Feature/
UserStory)로 수렴된다.

**Why this priority**: 이 스토리가 없으면 ODA 모드 자체가 존재하지 않는다. 표준 매핑이 ODA 모드의
근본 가치 — "표준을 근거한 설계" — 의 시작점이며, 나머지 모든 산출물이 이 매핑 위에 쌓인다.

**Independent Test**: ODA 표준 모드로 Proposal 을 생성하고 자연어 요청을 입력한 뒤, 시스템이
UC/SID/TMF/Component 매핑을 제시하고 아키텍트가 확정하면 strategic diff 가 생성되는 것까지로
독립 검증 가능. 이것만으로도 "표준에 근거한 의도 분해"라는 가치를 전달한다.

**Acceptance Scenarios**:

1. **Given** Proposal 작성 화면에 모드 스위치가 Simplified / DDD 심화 / ODA 표준 3개로 표시될 때,
   **When** 아키텍트가 "ODA 표준" 을 선택하고 자연어 요청을 입력해 진행하면,
   **Then** 시스템은 표준 매핑(매칭된 UCxxx 와 의도 인용, SID 후보 엔티티+출처, 기준 TMF API+버전,
   대상 Component 블록)을 표준 정합성 섹션으로 제시한다.
2. **Given** 표준 매핑이 제시되었을 때, **When** 아키텍트가 매핑을 확정하면,
   **Then** 분해 결과는 표준 strategic diff(Epic/Feature/UserStory)로 수렴되어 기존 Proposal
   상세 뷰에서 그대로 보인다.
3. **Given** 요청에 부합하는 Use Case 가 지식 베이스에 없을 때, **When** 분해를 진행하면,
   **Then** 시스템은 "매칭되는 UC 없음(provisional)" 을 명시하고 신규 UC 번호를 잠정 할당한다.

---

### User Story 2 - 적합성 게이트로 표준 준수 강제하기 (Priority: P1)

ODA 표준 모드의 모든 설계 요소(엔티티, 속성, API 오퍼레이션)는 **REUSE / EXTEND / NEW** 로
분류되고, "준수 후 확장" 규칙에 따라 점검된다. 표준을 깨는 변경(예: TMF 표준 오퍼레이션 계약 파괴,
SID 표준 필드 제거/재타이핑, 비표준 확장 메커니즘 사용)이 발견되면 적합성 게이트가 **FAIL** 로
판정되어 plan 수립 및 제출 진행이 **차단**된다. 아키텍트는 위반을 해소하거나, 명시적으로
**면제(waive)** 하고 사유를 기록해야만 진행할 수 있다.

**Why this priority**: 게이트가 없으면 "ODA 표준에 맞추어 검증" 이라는 핵심 요구가 충족되지 않는다.
차단형 게이트가 표준 정합성을 보장하는 강제 장치다.

**Independent Test**: 표준을 깨는 요소를 포함한 분해를 만든 뒤, 게이트가 FAIL 로 표시되고 진행이
막히며, 면제 후에는 사유 기록과 함께 진행이 풀리는지로 독립 검증 가능.

**Acceptance Scenarios**:

1. **Given** 분해/설계 요소가 산출되었을 때, **When** 적합성 점검이 실행되면,
   **Then** 각 요소가 REUSE/EXTEND/NEW 로 태깅되고, 적합성 매트릭스와 확장 델타가 적합성 리포트로
   기록되며 게이트 결과(PASS/FAIL)가 표시된다.
2. **Given** 적합성 게이트가 FAIL 일 때, **When** 아키텍트가 plan 수립 또는 제출을 시도하면,
   **Then** 시스템은 진행을 차단하고 위반 항목을 눈에 띄게 노출한다.
3. **Given** FAIL 상태에서, **When** 아키텍트가 위반을 명시적으로 면제하고 사유를 입력하면,
   **Then** 진행이 허용되고 면제 사실과 사유가 적합성 리포트에 기록된다.
4. **Given** 모든 요소가 표준을 준수(REUSE/추가형 확장만)할 때, **When** 적합성 점검이 실행되면,
   **Then** 게이트는 PASS 로 판정되어 추가 조치 없이 다음 단계로 진행된다.

---

### User Story 3 - 표준 근거 ODA 설계 산출물 생성하기 (Priority: P2)

게이트 통과(또는 면제) 후, plan 단계에서 ODA 표준 모드는 표준에서 파생된 설계 산출물을 생성한다:
**SID 파생 데이터 모델**(표준 엔티티·속성 재사용, 추가형 확장만), **TMF Open API 계약**(API 별
오퍼레이션 REUSE/EXTEND/NEW, 추가형 OpenAPI 단편만), **ODA Component/Canvas 아키텍처**(3개 기능
블록 매핑, exposed/dependent API, 이벤트 알림, 참여 Canvas 오퍼레이터), 그리고 ODA feature-kit
방언의 **Cucumber/Gherkin `.feature` 파일**. 이 산출물들은 Proposal 에 첨부되어 검토 가능하다.

**Why this priority**: P1(매핑+게이트)이 ODA 모드의 최소 가치라면, 표준 파생 설계 산출물은 "표준을
근거한 설계"를 실제 구현 가능한 형태로 완성한다. P1 이후에 독립적으로 더해질 수 있는 가치 슬라이스다.

**Independent Test**: 게이트를 통과한 ODA Proposal 의 plan 을 수립하고, 데이터 모델·계약·아키텍처·
`.feature` 산출물이 표준 출처 인용과 함께 생성·첨부되는지로 독립 검증 가능.

**Acceptance Scenarios**:

1. **Given** 적합성 게이트가 PASS(또는 면제)된 ODA Proposal, **When** plan 을 수립하면,
   **Then** SID 파생 데이터 모델이 표준 엔티티 인용과 함께 생성되고, 추가된 속성마다 인가된 확장
   메커니즘(Characteristic / @type 서브타이핑 / 추가형 enum)과 사유가 태깅된다.
2. **Given** 동일 plan 단계, **When** 계약을 생성하면, **Then** TMF API 별 계약이 생성되고 각
   오퍼레이션이 REUSE/EXTEND/NEW 로 태깅되며 확장은 추가형 단편으로만 표현된다.
3. **Given** 동일 plan 단계, **When** 아키텍처를 도출하면, **Then** 기능이 core/management/security
   블록에 매핑되고 exposed/dependent API, 이벤트 알림, 참여 Canvas 오퍼레이터가 식별된다.
4. **Given** 동일 plan 단계, **When** 검증 산출물을 생성하면, **Then** ODA feature-kit 방언의
   `.feature` 파일(UCxxx-Fyyy, Scenario Outline/Examples, 기존 step 재사용)이 작성된다.
5. **Given** ODA plan 이 완료되었을 때, **When** 다운스트림으로 진행하면, **Then** 결과가 표준
   tactical diff 로 수렴되어 기존 impact/tasks/implement 단계가 분기 없이 동작한다.

---

### User Story 4 - 모드 간 무회귀 및 전환 (Priority: P3)

ODA 표준 모드 추가가 기존 두 모드의 동작을 바꾸지 않는다. Simplified 와 DDD 심화 Proposal 은
이전과 동일하게 동작한다. 모드는 Proposal 생성 시 선택되며, 각 Proposal 은 자신이 어떤 모드로
분해되었는지 표시한다.

**Why this priority**: 무회귀는 필수 품질이지만 새 가치를 더하지는 않으므로 P3. 기존 사용자 흐름을
보호한다.

**Independent Test**: Simplified / DDD 심화 Proposal 을 생성·진행했을 때 ODA 추가 이전과 동일한
결과가 나오는지, ODA Proposal 이 모드 라벨로 구분되는지로 독립 검증 가능.

**Acceptance Scenarios**:

1. **Given** ODA 모드가 추가된 후, **When** 아키텍트가 Simplified 또는 DDD 심화로 Proposal 을
   생성하면, **Then** 해당 모드의 기존 흐름과 산출물이 변경 없이 동작한다.
2. **Given** 여러 모드의 Proposal 이 존재할 때, **When** 목록/상세를 보면,
   **Then** 각 Proposal 의 분해 모드가 명확히 식별된다.

---

### Edge Cases

- **지식 베이스 부재**: ODA 표준 지식 베이스(SID/UC 라이브러리)가 해석되지 않으면, ODA 모드는
  표준 없이 묵묵히 진행하지 않고 아키텍트에게 경로를 요청하거나 ODA 모드 사용 불가를 명시한다.
- **부분 매핑**: 요청 일부만 표준에 매핑되는 경우(일부 신규 개념), 매핑된 부분은 REUSE/EXTEND 로,
  나머지는 NEW 로 분류하고 NEW 비중을 리포트에 드러낸다.
- **면제 후 표준 갱신**: 면제된 위반이 있는 Proposal 에서 이후 표준/입력이 바뀌면, 게이트 결과와
  면제 기록이 최신 상태를 반영하도록 재평가 대상이 된다.
- **모드 업그레이드**: 이미 Simplified/DDD 로 진행 중인 Proposal 을 ODA 표준으로 전환하려는 경우의
  허용 여부와 재분해 동작 (가정: 기존 모드 업그레이드 메커니즘과 일관되게 처리).
- **다운스트림 호환**: ODA 모드가 표준 diff 로 수렴하지 못하는 산출물(순수 ODA 전용 아키텍처
  메타데이터)은 다운스트림을 깨지 않도록 부가 정보로만 전달된다.
- **게이트 우회 시도**: FAIL 상태에서 면제 없이 제출 API 가 직접 호출되어도 진행이 차단된다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 시스템은 Proposal 생성 시 분해 모드 선택지로 **Simplified, DDD 심화, ODA 표준** 세
  가지를 제시해야 한다(ODA 표준이 신규).
- **FR-002**: 시스템은 선택된 분해 모드를 Proposal 에 영속하고, 목록/상세에서 모드를 식별 가능하게
  표시해야 한다.
- **FR-003**: ODA 표준 모드 선택 시, 시스템은 자연어 요청을 ODA 표준 지식 베이스에 매핑해 가장
  가까운 Use Case(UCxxx)와 그 의도, SID 도메인/후보 엔티티(출처 인용), 기준 TMF Open API(버전),
  대상 ODA Component 블록(core/management/security)을 **표준 정합성** 으로 제시해야 한다.
- **FR-004**: 시스템은 ODA 표준 모드의 모든 설계 요소(엔티티·속성·오퍼레이션)를 **REUSE /
  EXTEND / NEW** 로 분류하고, 분류를 표준 우선순위(REUSE > EXTEND > NEW)에 따라 편향해야 한다.
- **FR-005**: 시스템은 ODA 표준 모드에서 **적합성 리포트**(표준 기준선, 적합성 매트릭스, 확장 델타
  상세, 게이트 결과)를 산출해 Proposal 에 첨부해야 한다.
- **FR-006**: 시스템은 "준수 후 확장(comply-then-extend)" 하드 규칙(표준 필드 제거/재타이핑,
  표준 계약 파괴, 비인가 확장 메커니즘) 위반 시 적합성 게이트를 **FAIL** 로 판정해야 한다.
- **FR-007**: 적합성 게이트가 FAIL 일 때, 시스템은 plan 수립 및 Proposal 제출 진행을 **차단**하고
  위반 항목을 눈에 띄게 노출해야 한다.
- **FR-008**: 시스템은 아키텍트가 FAIL 위반을 **명시적으로 면제(waive)** 하고 사유를 입력한 경우에만
  진행을 허용하며, 면제 사실과 사유를 적합성 리포트에 기록해야 한다.
- **FR-009**: ODA 표준 모드의 plan 단계는 **SID 파생 데이터 모델**(표준 엔티티/속성 재사용+출처
  인용, 추가된 속성마다 인가된 확장 메커니즘과 사유 태깅)을 생성해야 한다.
- **FR-010**: ODA 표준 모드의 plan 단계는 **TMF Open API 계약**(API 별, 오퍼레이션 REUSE/EXTEND/
  NEW 태깅, 표준 오퍼레이션 재작성 없이 추가형 단편만)을 생성해야 한다.
- **FR-011**: ODA 표준 모드의 plan 단계는 **ODA Component/Canvas 아키텍처**(3개 기능 블록 매핑,
  exposed/dependent API, 이벤트 알림, 참여 Canvas 오퍼레이터와 UC 참조)를 도출해야 한다.
- **FR-012**: ODA 표준 모드는 ODA feature-kit 방언의 **Cucumber/Gherkin `.feature` 파일**
  (UCxxx-Fyyy 명명, Scenario Outline/Examples, 가능한 경우 기존 step 재사용)을 산출물로
  생성해야 한다.
- **FR-013**: 시스템은 ODA 표준 모드의 분해 결과를 표준 **strategic diff** 로, plan 결과를 표준
  **tactical diff** 로 수렴시켜 다운스트림(impact/tasks/implement)이 분기 없이 동작하도록 해야 한다.
- **FR-014**: 시스템은 ODA 표준 지식 베이스가 해석되지 않으면 표준 없이 진행하지 않고, 경로를
  요청하거나 ODA 모드 불가를 명시해야 한다.
- **FR-015**: ODA 표준 모드 추가가 기존 Simplified / DDD 심화 모드의 흐름·산출물·결과에 회귀를
  일으키지 않아야 한다.
- **FR-016**: 시스템은 ODA 표준 모드 진행 중 각 게이트(매핑 확정, 적합성, 면제)에 사람 확정
  단계를 두어, 확정된 결과만 영속해야 한다.
- **FR-017**: 적합성 게이트 결과는 입력/표준 변경 시 재평가 가능한 상태로 유지되어, 오래된 PASS/
  면제가 silently 유효한 것으로 취급되지 않아야 한다.

### Key Entities

- **Decomposition Mode**: Proposal 의 분해 방식. 값: Simplified, DDD 심화, **ODA 표준**(신규).
  Proposal 에 귀속.
- **ODA Standards Alignment**: 요청을 표준에 매핑한 결과 — 매칭 UCxxx(+의도), SID 도메인/후보
  엔티티(+출처), 기준 TMF API(+버전), 대상 Component 블록. Proposal 에 귀속.
- **Conformance Report (적합성 리포트)**: 표준 기준선, 적합성 매트릭스, 요소별 REUSE/EXTEND/NEW
  분류, 확장 델타 상세, 게이트 결과(PASS/FAIL), 면제 기록(사유 포함). Proposal 에 귀속.
- **Conformance Gate Result**: PASS / FAIL / WAIVED 판정과 차단 상태. 진행 가능 여부를 결정.
- **SID-derived Data Model**: 표준 SID 엔티티에서 파생된 데이터 모델 + 인가된 추가형 확장.
- **TMF Open API Contract**: TMF API 기준 계약 + 추가형 확장 단편. 오퍼레이션별 분류 태깅.
- **ODA Component Architecture**: core/management/security 기능 블록, exposed/dependent API,
  이벤트 알림, 참여 Canvas 오퍼레이터.
- **BDD Feature File**: ODA feature-kit 방언의 Cucumber/Gherkin `.feature` 산출물(UCxxx-Fyyy).
- **Strategic / Tactical Diff**: ODA 산출물이 수렴하는 표준 표현. 다운스트림 분기 방지의 핵심.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 아키텍트는 Proposal 생성 화면에서 세 분해 모드(Simplified / DDD 심화 / ODA 표준)
  중 ODA 표준을 한 번의 선택으로 활성화할 수 있다.
- **SC-002**: ODA 표준 모드로 진행한 Proposal 의 100% 가 표준 정합성 매핑(UC/SID/TMF/Component)을
  표시한다.
- **SC-003**: ODA 표준 모드 산출물의 모든 데이터 요소·API 오퍼레이션이 REUSE/EXTEND/NEW 중 하나로
  명시 분류된다(미분류 0건).
- **SC-004**: 표준을 깨는 위반이 있는 Proposal 은 면제 없이는 plan/제출로 진행되지 않는다(우회 0건).
- **SC-005**: 면제로 진행된 모든 Proposal 은 적합성 리포트에 면제 사유가 기록되어 있다(누락 0건).
- **SC-006**: ODA 표준 plan 을 완료한 Proposal 은 SID 데이터 모델·TMF 계약·ODA 아키텍처·`.feature`
  네 종류 산출물을 모두 보유한다.
- **SC-007**: ODA 표준 모드 추가 후에도 Simplified / DDD 심화 모드의 기존 결과가 변하지 않는다
  (무회귀: 기존 동작 100% 유지).
- **SC-008**: ODA 표준 모드로 분해/계획한 결과는 기존 impact/tasks/implement 단계를 코드 분기 없이
  통과한다(다운스트림 호환 100%).

## Assumptions

- ODA 표준 지식 베이스는 기존에 캡처된 로컬 지식(SID/GB922, TMF Open API, ODA Canvas use-case
  라이브러리, BDD feature-kit, ODA Component 모델)을 출처로 한다. 이는 `oda-specify` / `oda-plan`
  스킬이 참조하는 지식 루트와 동일하다.
- ODA 표준 모드는 DDD 심화의 6단계 위저드를 그대로 재사용하지 않고, ODA 고유의 의도 분해(표준 정합성
  + 적합성)와 plan(SID 데이터 모델 + TMF 계약 + ODA 아키텍처 + BDD)을 별도 트랙으로 수행한다.
  단, 산출은 기존 strategic/tactical diff 로 수렴하여 다운스트림은 무분기로 유지된다.
- 적합성 게이트의 하드 규칙(표준 필드 제거/재타이핑, 표준 계약 파괴, 비인가 확장)은 `oda-specify`/
  `oda-plan` 의 conformance-and-extension 규칙을 따른다.
- 신규 모드는 기존 Proposal 모드 업그레이드/스위치 메커니즘과 일관되게 동작한다(별도 재설계 없음).
- 모드 라벨·설명 등 LLM/UI 텍스트는 사용자 언어 설정(BCP-47, 기본=브라우저 로케일) 정책을 따른다.

## Dependencies

- 기존 042 분해 모드 스위치(Simplified / DDD 심화)와 staged 분해 인프라.
- 기존 Proposal 생애주기(diff 수렴 → plan/impact/tasks/implement) 및 041 Constitution/plan 단계.
- ODA 표준 지식 베이스(`oda-specify`/`oda-plan` 가 참조하는 SID/UC/TMF/feature-kit) 가용성.

## Out of Scope

- ODA Component 의 실제 배포·BDD 실행(컨테이너화, Canvas 온보딩, Keycloak 통합, 라이프사이클
  검증) — 이는 `oda-componentize` 스킬의 영역으로 본 기능 범위 밖이다.
- ODA 표준 지식 베이스 자체의 갱신·확장·관리.
- 기존 Simplified / DDD 심화 모드의 동작 변경.
