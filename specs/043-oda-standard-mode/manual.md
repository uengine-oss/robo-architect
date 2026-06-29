# 사용자 매뉴얼 — ODA 표준 분해 모드 (043)

이 문서는 아키텍트가 Proposal 을 **ODA 표준 모드**로 분해·설계하는 방법을 설명합니다.

## 1. ODA 표준 모드란?

Proposal 을 만들 때 고르는 **분해 모드**의 세 번째 옵션입니다.

| 모드 | 설명 |
|------|------|
| 간소화(Simplified) | 빠른 경로: Intent → Plan (기존) |
| 상세 DDD(Detailed DDD) | DDD 단계별 분해 Discover→…→Tactical (기존) |
| **ODA 표준(ODA Standard)** | **TM Forum ODA 표준(SID·TMF Open API·ODA Component·UC·BDD)에 근거해 설계·검증 (신규)** |

ODA 표준 모드는 요청을 표준에 매핑하고, 표준이 이미 정의한 것을 재사용하며, 모든 요소를
**REUSE / EXTEND / NEW** 로 분류하고, "준수 후 확장" 을 **차단형 적합성 게이트**로 강제합니다.

## 2. ODA 표준 모드로 Proposal 만들기

1. Proposals 탭에서 **새 Proposal** 을 엽니다.
2. 요구사항을 자연어로 입력합니다 (예: "고객이 주문을 우선처리(expedite)하고 수수료를 부과한다").
3. 입력창 아래 **모드 스위치**에서 **ODA 표준** 을 선택합니다.
4. **AI 분석 시작** 을 누릅니다 → Proposal 이 DRAFT 로 생성되고 상세 화면의 **Intent 탭**에
   **ODA 표준 분해/설계** 트랙이 나타납니다.

## 3. 1단계 — 표준 정합성 분해 (Intent)

ODA 트랙의 **① 표준 정합성 매핑** 영역에서 **표준 정합성 분해 실행** 을 누릅니다. 진행 로그가
실시간으로 흐르고, 완료되면 다음이 표시됩니다.

- **Use Cases** — 매칭된 UCxxx (ODA use-case 라이브러리).
- **SID 엔티티** — 재사용할 표준 데이터 엔티티(Customer, Order …).
- **TMF API** — 기준이 되는 TMF Open API 와 버전(TMF622 v4 …).
- **Component 블록** — 기능이 속하는 블록(coreFunction / managementFunction / securityFunction).

이때 표준 정렬된 **strategicDiff(Epic/Feature/UserStory)** 도 함께 산출되어 Impact 탭에서 볼 수
있습니다.

## 4. 2단계 — 적합성 게이트 (차단형)

**② 적합성 게이트** 영역에 결과가 표시됩니다.

- **분류 표** — 각 엔티티/속성/오퍼레이션이 `REUSE` / `EXTEND` / `NEW` 로 분류됩니다.
- **게이트 배지**:
  - ✅ **PASS** — 표준을 준수. 다음 단계로 진행 가능.
  - ⛔ **FAIL** — 표준을 깨는 위반(표준 필드 제거/재타이핑, 표준 계약 파괴, 비인가 확장)이
    있습니다. **plan 수립과 제출이 차단됩니다.**
  - ⚠️ **WAIVED** — 면제되어 진행 허용된 상태.

### 위반 면제(waive)

게이트가 **FAIL** 이면 위반 목록 아래 입력란에 **면제 사유**를 적고 **면제하고 진행** 을 누릅니다.
사유는 필수이며 적합성 리포트에 기록됩니다. 면제 후 게이트는 **WAIVED** 가 되어 진행이 풀립니다.

> 사유 없이 제출/plan 을 시도하면 서버가 차단합니다(409). 면제만이 유일한 통과 경로입니다.

## 5. 3단계 — 표준 설계 산출물 (Plan)

게이트가 PASS 또는 WAIVED 가 되면 **③ 표준 산출물** 영역의 **표준 설계(plan) 실행** 버튼이
활성화됩니다. 실행하면 다음 네 가지 표준 산출물이 생성·첨부됩니다.

- **SID 데이터 모델** — 표준 엔티티/속성 재사용 + 인가된 추가형 확장(Characteristic 등).
- **TMF 계약** — TMF Open API 기준 계약, 오퍼레이션별 REUSE/EXTEND/NEW.
- **ODA 아키텍처** — core/management/security 블록, exposed/dependent API, 이벤트, Canvas 오퍼레이터.
- **BDD .feature** — ODA feature-kit 방언의 Cucumber/Gherkin 파일.

이 결과는 표준 **tacticalDiff** 로 수렴되어 이후 **Impact → Tasks → 구현(Implement)** 단계가
기존과 동일하게(분기 없이) 동작합니다.

## 6. 이후 흐름

- **Plan 단계로 진행** → 제출(DRAFT→SUBMITTED). ODA 모드는 이때도 적합성 게이트가 차단 상태면
  막힙니다.
- 이후 Plan / Impact / Tasks / 구현 / 검증 / 수락은 기존 Proposal 생애주기와 동일합니다.

## 7. 사전 조건 / 주의

- ODA 표준 지식 베이스(SID + use-case 라이브러리)가 있어야 합니다(`$ODA_KNOWLEDGE_ROOT`,
  기본 `/Users/uengine/oda-canvas`). 없으면 ODA 분해가 "지식 베이스를 찾을 수 없습니다" 로
  중단됩니다.
- 기존 간소화 / 상세 DDD 모드의 동작은 전혀 바뀌지 않습니다.
- ODA Component 의 실제 배포·BDD 실행은 본 모드의 범위가 아니라 `oda-componentize` 스킬의 영역입니다.

---

### 검증 메모(개발자용)

- 백엔드 단위 테스트: `api/features/proposal_lifecycle/tests/test_oda_standard.py` (29개) — 게이트
  PASS/FAIL/WAIVE, 분류 완전성, mode/산출물 from_neo4j 파싱, 지식 루트 해석, 스킬 결과 파서.
  기존 042 테스트 무회귀(전체 60 passed / 1 skipped).
- 프런트 빌드 통과, 앱 부팅 + 4개 ODA 라우트 등록 확인.
- 라이브 SSE 분해/설계(실제 `claude` + Neo4j + ODA 지식 루트)는 런타임 환경에서 quickstart 로 검증.
