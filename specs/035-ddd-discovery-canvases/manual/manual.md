# DDD 발견 마법사 & 도메인 캔버스 — 사용자 매뉴얼

> 기능 035. 요구사항 탭에서 DDD(도메인 주도 설계) 8단계 프로세스를 대화형으로 진행하고,
> Bounded Context·Aggregate를 캔버스로 보고 편집합니다.
>
> **검증 수준 안내**: 본 매뉴얼은 구현된 화면·API를 기준으로 작성되었습니다. 백엔드 임포트
> 스모크(라우트 59개 등록 확인)와 마법사 로직 단위테스트 11건, 프런트엔드 프로덕션 빌드가
> 통과한 상태입니다. 라이브 스크린샷 캡처는 이 환경에 Neo4j/앱 스택이 떠 있지 않아 생략했습니다.

---

## 0. 들어가기 전에

- 위치: 상단 탭 **Requirements(요구사항)**.
- 핵심 개념: 이 기능이 만드는 모든 결과는 **그래프(Neo4j)에 저장**됩니다. 캔버스는 그래프를 보여주는
  화면이고, `.ddd/` 마크다운은 그래프에서 내보내는 보조 문서입니다.
- 안전장치: 마법사·캔버스가 만드는 모든 변경은 **먼저 제안되고, 사용자가 확인할 때만** 그래프에
  반영됩니다(거부하면 아무것도 바뀌지 않습니다).
- 생성 엔진: 설정의 `생성 엔진`이 **in-process(백엔드 LLM)** 또는 **Claude IDE(로컬 claude)** 중
  무엇이냐에 따라 자동생성 방식이 달라집니다. 로컬 도구가 없으면 막지 않고 안내 후 in-process로
  진행할 수 있습니다.

---

## 1. DDD 발견 마법사로 맨땅에서 시작하기

요구사항이 비어 있거나, 처음부터 도메인을 함께 잡고 싶을 때 사용합니다.

1. 요구사항 탭 상단 도구막대에서 **🧭 DDD 마법사** 버튼을 클릭합니다.
   - 같은 자리의 **📄 문서 업로드**(기존 일괄 분석)와 마법사는 **함께** 쓸 수 있고 같은 그래프를
     공유합니다.
2. **프로파일링(4문항)** — 프로젝트 유형 / DDD 경험 / 팀 규모를 고르고 **추천 받기**를 누릅니다.
   - 예: `신규(그린필드)` · `처음` · `4~10명` → 추천 단계가 계산됩니다.
3. **단계 선택** — 추천된 단계 조합이 체크리스트로 보입니다.
   - `Discover / Decompose / Define`은 **필수**(해제 불가), 나머지는 가감할 수 있습니다.
   - **시작**을 누르면 선택한 단계만 순서대로 진행합니다.
4. **단계 진행** — 각 단계에서:
   - 질문에 **답변/메모**를 적거나, **기존 문서를 붙여넣기** 할 수 있습니다(둘 다 가능).
   - **산출물 생성**을 누르면 그 단계의 초안(마크다운)과 **그래프 변경안** 목록이 나옵니다.
   - 변경안은 기본적으로 모두 체크되어 있으며, 원치 않는 항목은 체크를 해제합니다.
   - **확인 후 다음 →**을 누르면 체크된 변경만 그래프에 반영되고 다음 단계로 넘어갑니다.
   - 특정 단계가 불필요하면 **이 단계 건너뛰기**를 누릅니다.
5. 마지막 단계까지 확인하면 마법사가 닫히고 요구사항 트리가 새로고침됩니다.

> 중단했다 다시 열어도 이미 완료한 단계의 답변·산출물은 보존됩니다(세션 재개).

### 단계별로 무엇을 하나요?
| 단계 | 하는 일 |
|---|---|
| Understand | 비즈니스 본질·사용자·목표 정리, 핵심 액터 식별 |
| Discover | 도메인 사건을 시간순으로 모으고 **피보탈 이벤트/핫스팟** 표시 |
| Decompose | 피보탈 이벤트 경계로 **서브도메인(=Bounded Context 후보)** 도출 |
| Strategize | 각 영역을 **Core / Supporting / Generic**으로 분류 |
| Define | **Bounded Context Canvas** 작성 |
| Code | **Aggregate Design Canvas**(상태·커맨드·이벤트·불변조건) |

---

## 2. 피보탈 이벤트로 서브도메인 잡기

"상태가 크게 바뀌는 분기점"인 피보탈 이벤트를 기준으로 도메인을 가릅니다.

1. Discover 단계에서 사건을 시간순으로 입력합니다(예: `장바구니에 담김 → 주문이 확정됨 → 배송이 완료됨`).
2. 상태 전환의 분기점을 **피보탈(⭐)**, 논쟁/모호 지점을 **핫스팟(🔥)**으로 표시·토글합니다.
   - (API: `POST /api/requirements/pivotal-events/toggle`)
3. Decompose 단계에서 **서브도메인 제안**을 실행하면, 피보탈 이벤트 경계로 묶인 후보가 나옵니다.
   - (API: `GET /api/requirements/pivotal-events/subdomains/propose`)
4. 마음에 드는 후보를 확인하면 기존 BC 생성 경로로 **Bounded Context**가 만들어집니다.

> 기존 "문서 업로드" 분석이 만든 이벤트와 겹치면, 새로 만들지 않고 병합 후보로 보여줍니다.

---

## 3. Bounded Context Canvas 보기·편집

BC(에픽)의 책임·언어·관계를 한 화면에서 봅니다.

1. 요구사항 트리에서 **Epic(Bounded Context)**을 클릭합니다.
2. 상세 화면 상단의 **개요 / Canvas** 탭에서 **Canvas**를 선택합니다.
3. Canvas에는 다음이 표시됩니다:
   - 전략 분류 배지(🔴 Core / 🟡 Supporting / ⚪ Generic)
   - **책임(Purpose)**, **유비쿼터스 언어**, **인/아웃바운드 메시지**, **비즈니스 결정**, **가정**
4. **✨ 자동생성**: 설정된 엔진으로 초안을 채웁니다(기존 ddd-spec 생성기 재사용).
5. **✎ 편집** → 항목을 수정하고 **저장**합니다.
   - 저장은 BC의 속성만 갱신하며 **관계는 보존**됩니다.
   - 다른 사람이 먼저 수정했으면 충돌 안내(412)가 표시됩니다.
   - (API: `GET/PATCH /api/requirements/bounded-context/{bcId}/canvas`)

> 설계 캔버스에서 BC 노드를 더블클릭해도 같은 상세 화면으로 진입하도록 연동되어 있습니다.

---

## 4. Aggregate Design Canvas 보기·편집

애그리거트의 상태·규칙을 봅니다.

1. Aggregate 상세(인스펙터)에서 **Canvas** 탭을 엽니다.
2. 표시 항목: **설명, 상태 전이(Mermaid), 커맨드, 이벤트, 불변 조건, 보정 정책, Throughput**.
   - 불변 조건은 기존 기능(spec 027)의 표현을 그대로 씁니다.
3. **✎ 편집** → 수정 후 **저장**(속성만 갱신, 관계 보존).
   - (API: `GET/PATCH /api/requirements/aggregate/{aggregateId}/canvas`)

---

## 5. Core / Supporting / Generic 전략 분류

1. Strategize 단계 또는 BC Canvas에서 분류를 지정합니다.
2. 판별 질문 예시: *"이 영역을 외부에 아웃소싱하면 고객이 차이를 느낄까?"* → 느낀다면 **Core**.
3. 분류는 BC 속성으로 저장되고, 캔버스/컨텍스트 맵에서 **색상 배지**로 구분됩니다.
   - (API: `PATCH /api/contexts/{bcId}/classification`, 값: `core`·`supporting`·`generic`)

---

## 6. 그래프를 .ddd 문서로 내보내기

현재 모델을 사람이 읽고 버전관리할 수 있는 마크다운으로 내보냅니다.

1. **그래프 → .ddd 내보내기**를 실행합니다.
   - (API: `POST /api/requirements/ddd-export`, 기본 출력 폴더 `.ddd/`)
2. 생성물: `00-plan.md`, `02-event-storm.md`(피보탈/핫스팟 표시), `04-core-domain-chart.md`,
   `07-bounded-contexts/<이름>.md`, `08-aggregates/<이름>.md`.

> 진실의 원천은 그래프이고, `.ddd` 파일은 그래프에서 만들어지는 보조 산출물입니다.

---

## 7. 자주 묻는 질문

- **Q. 확인 안 했는데 그래프가 바뀌나요?** 아니요. 변경안을 **확인**해야만 반영됩니다. 빈 목록으로
  확인하면 아무것도 바뀌지 않습니다.
- **Q. Claude IDE 엔진을 골랐는데 안 돼요.** 로컬에 `claude` CLI가 없으면 시작 시 안내(409)가
  뜹니다. 설치하거나 **in-process** 엔진으로 전환하세요.
- **Q. "문서 업로드"(전체 분석)와 마법사를 같이 써도 되나요?** 됩니다. 단, 전체 문서 분석은 모델을
  다시 구성하므로, 마법사로 만든 결과 위에 전체 분석을 다시 돌릴 때는 사전 경고를 확인하세요.
- **Q. 생성 결과 언어는?** 기어(설정) 아이콘의 언어 설정을 따릅니다.

---

## 부록: 새로 추가된 API 요약

| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/api/requirements/ddd-wizard/start` | 마법사 시작(프로파일→추천 단계) |
| GET | `/api/requirements/ddd-wizard/{id}` | 세션 상태(재개) |
| POST | `/api/requirements/ddd-wizard/{id}/answer` | 답변/문서 제출 → 제안 |
| GET(SSE) | `/api/requirements/ddd-wizard/{id}/step/{step}/stream` | 단계 진행 스트림 |
| POST | `/api/requirements/ddd-wizard/{id}/step/{step}/confirm` | 단계 확정(그래프 반영) |
| POST | `/api/requirements/pivotal-events/toggle` | 피보탈/핫스팟 토글 |
| GET | `/api/requirements/pivotal-events/subdomains/propose` | 서브도메인 제안 |
| GET·PATCH | `/api/requirements/bounded-context/{bcId}/canvas` | BC 캔버스 |
| GET·PATCH | `/api/requirements/aggregate/{aggregateId}/canvas` | Aggregate 캔버스 |
| POST | `/api/requirements/ddd-export` | 그래프 → .ddd 내보내기 |
| PATCH | `/api/contexts/{bcId}/classification` | 전략 분류(core/supporting/generic) |
