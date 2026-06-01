# Feature Specification: DDD 발견 마법사 & 도메인 캔버스

**Feature Branch**: `035-ddd-discovery-canvases`

**Created**: 2026-05-31

**Status**: Draft

**Input**: User description: "ddd-starter 스킬(uengine-oss/ddd-starter-skill-kor)을 robo-architect에 통합한다. (1) BC를 생성/클릭하면 BC 전용 상세·설정 화면과 함께 **Bounded Context Canvas**가 만들어진다. (2) Aggregate 상세 속성에서 **Aggregate Design Canvas** 탭을 볼 수 있다. (3) 맨땅에서 요구사항/에픽을 추가할 때, 스킬이 안내하는 **인터뷰 흐름**(프로파일링 → 비즈니스 컨텍스트·핵심 액터 정의 → EventStorming → 서브도메인 분해 → core/supporting/generic 분류 → BC 정의)을 거칠 수 있다. (4) 기존 이벤트 도출 프롬프트와 겹치는 부분을 정리하되, **피보탈 이벤트(pivotal event)를 기점으로 서비스/서브도메인을 도출**하는 스킬의 방식을 존중하여 개선한다."

## Clarifications

### Session 2026-05-31

- Q: DDD 인터뷰 산출물(EventStorming, BC Canvas, Aggregate Canvas)의 진실의 원천은? → A: **그래프에 직접 반영**한다. 기존 Neo4j 그래프가 진실의 원천이며, 스킬/마법사 산출물은 propose→confirm으로 그래프 노드 속성에 매핑된다. 캔버스는 그래프를 투영(projection)한 뷰이고, `.ddd/` 마크다운은 그래프에서 생성하는 **보조 산출물(내보내기)**이다.
- Q: 캔버스/인터뷰 자동 생성 엔진은? → A: spec 034의 **이원화 엔진 설정**을 그대로 따른다. Settings의 `requirementGenerationEngine` 토글(in-process LLM vs 로컬 Claude IDE + `ddd-starter` 스킬)을 캔버스·인터뷰 생성에도 동일 적용하고, 로컬 도구 미설치 시 설치 안내를 제공한다.
- Q: 인터뷰 흐름의 적용 범위는? → A: **맨땅에서 시작(그린필드 전체 요구사항 초기 등록)과 에픽 추가 양쪽 모두**에서 마법사를 제공한다. 마법사는 프로파일링(0)부터 코드(8)까지 단계를 갖되 사용자가 추천 조합을 가감하여 일부 단계만 옵트인할 수 있다(에픽 추가 시에는 기존 컨텍스트를 입력으로 좁혀진 단계 조합을 추천).

### Session 2026-05-31 (2) — 기존 Ingestion 통합

- Q: DDD 마법사와 기존 Ingestion("문서 업로드" 일괄 투입; Requirements 탭 모달)의 관계는? → A: **병행(둘 다 유지) + 상호 진입구**. 두 경로 모두 Requirements 탭에서 제공하고 같은 그래프를 공유한다. 일괄 투입 모달에는 "인터뷰(마법사)로 시작" 링크를, 마법사에는 "문서 일괄 투입" 링크를 둔다.
- Q: 이벤트 도출 방식은? → A: **보완**. 기존 커맨드 중심 도출(Command→EMITS→Event)을 그대로 유지하고, 마법사가 **빅픽처 이벤트·피보탈·핫스팟 계층을 추가**한다. 겹치는 이벤트는 병합 후보로 제시(FR-009).
- Q: 마법사 후반 단계(Decompose→BC, Code→Aggregate/Command/Event)의 생성 주체는? → A: **기존 ingestion 설계 기계 재사용**. Decompose 확정은 `POST /bounded-context`, Code/설계 생성은 `POST /api/ingest/user-stories/design`(`incremental_design_runner`), 마무리는 spec 034 `design_reflect`. 마법사는 신규 생성기가 아니라 이들을 **오케스트레이션**한다.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - DDD 발견 마법사(8단계 옵트인) (Priority: P1)

요구사항 탭에서 "맨땅에서 시작" 또는 에픽 추가 시, 사용자는 DDD 발견 마법사를 열 수 있다. 마법사는 먼저 4개의 프로파일링 질문(프로젝트 유형 / DDD 경험 / 팀 규모 / 보유 산출물)으로 상황을 파악하고, 상황에 맞는 단계 조합(예: 그린필드+초보 → 0→1→2→3→4→7→8)을 추천한다. 사용자가 단계 조합을 확정하면 마법사는 선택된 단계만 순서대로 진행하며, 각 단계의 질문에 답하거나 초기 문서를 붙여넣는 방식 둘 다로 진행할 수 있다. 각 단계가 끝나면 산출물이 사용자에게 제시되고, 확인(propose→confirm)하면 **기존 요구사항 그래프(BoundedContext/Feature/UserStory/Aggregate/Event)에 직접 반영**된다(그래프가 진실의 원천). `.ddd/` 마크다운은 그래프로부터 생성되는 보조 내보내기 산출물로 함께 저장된다.

**Why this priority**: 맨땅에서 시작할 때 BC와 핵심 액터·서브도메인 경계를 잡는 과정이 현재는 비어 있다. 이 마법사가 전체 기능의 진입점이자 다른 캔버스/도출 기능의 기반 데이터를 만든다.

**Independent Test**: 빈 프로젝트에서 마법사를 열어 프로파일링 4문항에 답하고 추천 단계(최소 0→1→2→3)를 수행하면, `.ddd/` 산출물과 propose→confirm을 거친 BC 후보가 요구사항 트리에 나타나는 것으로 검증한다.

**Acceptance Scenarios**:

1. **Given** 요구사항이 비어 있는 프로젝트, **When** 사용자가 "DDD 발견 마법사"를 열고 프로파일링 4문항에 답한다, **Then** 상황에 맞는 단계 조합이 추천되고 사용자가 수행할 단계를 가감하여 확정할 수 있다.
2. **Given** 마법사가 1단계(Understand)에 있다, **When** 사용자가 질문에 답하거나 비즈니스 설명 문서를 붙여넣는다, **Then** 비즈니스 본질·사용자/이해관계자·목표가 정리된 산출물이 생성되고 핵심 액터가 식별된다.
3. **Given** 한 단계의 산출물이 생성됨, **When** 사용자가 "그래프에 반영"을 확인한다, **Then** 해당 산출물이 기존 그래프 노드(예: BoundedContext)에 매핑되고, 거부하면 그래프는 변경되지 않는다(확인 전에는 어떤 노드도 생성/수정되지 않음).
4. **Given** 진행 중인 마법사 세션, **When** 사용자가 단계를 중단했다 다시 연다, **Then** 이미 완료된 단계의 산출물·답변이 보존되어 이어서 진행할 수 있다.

---

### User Story 2 - 피보탈 이벤트 기반 EventStorming & 서브도메인 도출 (Priority: P1)

마법사의 Discover(2단계)에서 사용자는 도메인 사건을 과거형 동사로 시간순 발견한다. 시스템은 상태가 크게 바뀌는 분기점을 **피보탈 이벤트**로, 불확실·논쟁 지점을 **핫스팟**으로 표시한다. Decompose(3단계)에서는 피보탈 이벤트를 경계로 이벤트를 묶어 서브도메인(→ BC 후보)을 도출한다. 기존 요구사항 기반 이벤트 도출 로직과 겹치는 부분은 통합하되, "피보탈 이벤트를 기점으로 서비스/서브도메인을 도출"하는 방식을 1급으로 채택하여 개선한다.

**Why this priority**: 서브도메인/BC 경계의 품질이 이후 모든 캔버스·설계의 품질을 좌우한다. 피보탈 이벤트 기준 도출은 스킬의 핵심 가치이며 기존 도출 방식의 약점을 보완한다.

**Independent Test**: EventStorming 단계에서 10개 이상의 이벤트를 입력하면 피보탈 이벤트·핫스팟이 구분 표시되고, Decompose 단계에서 피보탈 이벤트 경계로 그룹핑된 서브도메인 맵(`.ddd/02`, `.ddd/03`)이 생성되는 것으로 검증한다.

**Acceptance Scenarios**:

1. **Given** Discover 단계, **When** 사용자가 이벤트들을 시간순으로 입력한다, **Then** 각 이벤트의 트리거(사용자/시간/외부)가 분류되고 피보탈 이벤트·핫스팟이 시각적으로 구분된다.
2. **Given** 피보탈 이벤트가 식별됨, **When** Decompose 단계로 진행한다, **Then** 피보탈 이벤트를 경계로 한 서브도메인 그룹과 그룹 간 의존성이 제안된다.
3. **Given** 이미 요구사항(US/Feature)에서 도출된 이벤트가 존재한다, **When** EventStorming을 실행한다, **Then** 중복 이벤트는 병합 후보로 표시되고 사용자가 피보탈 여부를 조정할 수 있다.

---

### User Story 3 - Bounded Context Canvas & BC 상세 화면 (Priority: P1)

사용자가 Bounded Context(에픽)를 생성하거나 트리/캔버스에서 클릭하면, BC 전용 상세·설정 화면이 열리고 그 안에 **Bounded Context Canvas** 탭이 있다. 캔버스에는 책임(목적), 전략 분류(core/supporting/generic), 유비쿼터스 언어 및 용어 충돌, 인바운드/아웃바운드 메시지(이벤트·커맨드·쿼리), 주요 비즈니스 결정 등이 표시된다. 캔버스는 마법사 Define(7단계) 산출물(`.ddd/07-bounded-contexts/<name>.md`) 기반으로 자동 생성되며, 사용자가 직접 편집할 수 있고 확정 시 그래프의 BC 속성과 동기화된다.

**Why this priority**: BC를 클릭했을 때 자기만의 상세 화면과 캔버스를 보여주는 것은 사용자가 명시적으로 요청한 핵심 요구이며, 전략 분류·통합 관계의 단일 조회 지점이 된다.

**Independent Test**: 임의의 BC를 클릭하여 상세 화면을 열고 "Canvas" 탭에서 책임·유비쿼터스 언어·인/아웃바운드 메시지가 표시·편집되며 저장 후 다시 열어도 유지되는 것으로 검증한다.

**Acceptance Scenarios**:

1. **Given** 그래프/트리에 BC가 존재, **When** 사용자가 BC를 클릭한다, **Then** BC 전용 상세·설정 화면이 열리고 Canvas 탭을 포함한다.
2. **Given** BC Canvas 탭, **When** 자동 생성을 요청한다, **Then** 설정된 엔진으로 책임·유비쿼터스 언어·인/아웃바운드 메시지 초안이 채워지고 propose→confirm으로 확정된다.
3. **Given** BC Canvas가 채워짐, **When** 사용자가 필드를 편집·저장한다, **Then** 변경이 `.ddd` 문서와 그래프 BC 속성에 함께 반영된다.

---

### User Story 4 - 비즈니스 컨텍스트 & 핵심 액터 정의 (Priority: P2)

마법사 Understand(1단계)에서 사용자는 비즈니스 본질(해결 문제·지불 이유·차별점), 사용자/이해관계자(역할별 가치·외부 이해관계자), 목표/가설(KPI·검증 가설·목표 상태)을 정리한다. 시스템은 답변 또는 붙여넣은 문서로부터 핵심 액터(역할)를 식별하여 산출물(`.ddd/01-business-context.md`)에 기록하고, 확인 시 그래프의 액터/페르소나 표현에 동기화한다.

**Why this priority**: core/supporting/generic 분류와 BC 경계 판단의 전제가 되는 맥락·액터 정보를 확보한다. 마법사의 한 단계이지만 다른 단계와 독립적으로 가치(이해관계자 정렬 문서)를 제공한다.

**Independent Test**: Understand 단계만 수행하여 3개 질문 그룹에 답하면 비즈니스 컨텍스트 문서와 식별된 핵심 액터 목록이 생성되는 것으로 검증한다.

**Acceptance Scenarios**:

1. **Given** Understand 단계, **When** 사용자가 3개 질문 그룹에 답한다, **Then** 비즈니스 컨텍스트 문서와 후보 핵심 액터 목록이 생성된다.
2. **Given** 사용자가 초기 비즈니스 설명 문서를 붙여넣음, **When** 분석을 요청한다, **Then** 문서에서 액터·목표·차별점이 추출되어 질문 답변 초안으로 채워진다.

---

### User Story 5 - Aggregate Design Canvas 탭 (Priority: P2)

Aggregate 상세 속성 화면에 **Aggregate Design Canvas** 탭이 추가된다. 캔버스에는 애그리거트 이름·책임, 상태 전이(상태 머신), 처리하는 커맨드, 발행하는 이벤트, 그리고 불변 조건(invariants)이 표시된다. 마법사 Code(8단계) 산출물(`.ddd/08-aggregates/<name>.md`) 기반으로 자동 생성되고 편집 가능하며, 기존 애그리거트 불변조건(spec 027) 표현과 동기화된다.

**Why this priority**: 애그리거트 단위의 설계 캔버스는 사용자가 요청한 항목이며, BC Canvas 다음 수준의 상세 설계 뷰를 제공한다. 기존 invariants/aggregate 드릴다운 위에 얹는다.

**Independent Test**: 임의의 Aggregate 상세를 열어 "Canvas" 탭에서 상태 전이·커맨드·이벤트·불변조건이 표시·편집되고 저장 후 유지되는 것으로 검증한다.

**Acceptance Scenarios**:

1. **Given** 그래프에 Aggregate가 존재, **When** 사용자가 Aggregate 상세를 연다, **Then** 속성 탭들 중 Aggregate Canvas 탭이 보인다.
2. **Given** Aggregate Canvas 탭, **When** 자동 생성을 요청한다, **Then** 상태 전이·커맨드·이벤트·불변조건 초안이 채워지고 propose→confirm으로 확정된다.
3. **Given** 캔버스에 불변조건이 정의됨, **When** 저장한다, **Then** 기존 애그리거트 불변조건 표현(spec 027)과 충돌 없이 동기화된다.

---

### User Story 6 - Core/Supporting/Generic 전략 분류 (Priority: P2)

마법사 Strategize(4단계) 또는 에픽/요구사항 추가 시, 시스템은 각 서브도메인/BC에 대해 전략 분류 질문("이 영역을 외부에 아웃소싱하면 고객이 알아챌까?" 등)을 제시하여 🔴Core / 🟡Supporting / ⚪Generic 으로 분류한다. 분류 결과는 BC의 속성으로 저장되어 BC Canvas와 컨텍스트 맵에서 시각적으로 구분된다.

**Why this priority**: 핵심 도메인 식별은 투자·팀 배치 의사결정의 근거이며, 사용자가 "이런 질문들이 있었어야 했다"고 명시적으로 지적한 누락 지점이다.

**Independent Test**: 서브도메인 목록에 대해 분류 질문에 답하면 각 항목이 core/supporting/generic으로 분류되어 BC 속성에 저장되고 컨텍스트 맵에서 색상/배지로 구분되는 것으로 검증한다.

**Acceptance Scenarios**:

1. **Given** 서브도메인/BC 목록이 존재, **When** Strategize 단계를 진행한다, **Then** 각 항목에 분류 질문이 제시되고 답변에 따라 core/supporting/generic이 제안된다.
2. **Given** 분류가 확정됨, **When** BC Canvas 또는 컨텍스트 맵을 본다, **Then** 분류가 배지/색상으로 표시된다.

---

### User Story 7 - 그래프 → .ddd 내보내기(보조 산출물) (Priority: P3)

그래프가 진실의 원천이므로, 마법사·캔버스의 모든 결과는 그래프에 반영된다. 사용자는 별도로 현행 그래프 상태를 `.ddd/` 마크다운(`00-plan` ~ `08-aggregates/`)으로 **내보내기(export)** 하여 버전관리·문서 공유·로컬 `ddd-starter` 스킬 입력으로 활용할 수 있다. 선택적으로, 외부에서 수정한 `.ddd` 문서를 다시 가져올 때는 차이를 변경안으로 제시하여 propose→confirm으로만 그래프에 반영한다(가져오기는 보조 기능).

**Why this priority**: 진실의 원천을 그래프로 정했으므로 `.ddd`는 보조 내보내기 산출물이다. 핵심 가치는 앞선 스토리에서 이미 제공되므로 마지막 우선순위.

**Independent Test**: 그래프에 BC/Aggregate가 있는 상태에서 "내보내기"를 실행하면 `.ddd/` 디렉토리에 단계별 마크다운이 현행 그래프 상태로 생성되는 것으로 검증한다.

**Acceptance Scenarios**:

1. **Given** 그래프에 BC/Aggregate/이벤트가 존재, **When** "그래프 → .ddd 내보내기"를 실행한다, **Then** `.ddd/` 단계별 문서가 현행 그래프 상태로 생성/갱신된다.
2. **Given** `.ddd` 문서를 외부에서 수정함, **When** "가져오기(선택)"를 실행한다, **Then** 차이가 변경안으로 제시되고 확인 시에만 그래프에 반영된다.

---

### Edge Cases

- 프로파일링에서 "단일 기능 추가"를 선택하면 빠른 경로(예: 2→3→7→8)만 추천되고 1·5·6단계는 생략 제안된다.
- 로컬 엔진(Claude IDE + `ddd-starter` 스킬)이 미설치인데 해당 엔진이 선택된 경우, 생성을 차단하지 않고 설치 안내를 제시하며 in-process 엔진으로의 전환을 제안한다.
- EventStorming에 이벤트가 너무 적어(예: 3개 미만) 피보탈 이벤트를 식별할 수 없을 때, 시스템은 추가 이벤트 입력을 유도한다.
- 이미 BC/Aggregate가 다른 경로(spec 034 등록)로 만들어진 상태에서 마법사를 실행하면 기존 노드와 중복 생성하지 않고 병합/갱신 후보로 제시한다.
- 자동 생성된 캔버스 초안을 사용자가 거부하면 `.ddd`·그래프 모두 변경되지 않는다(propose→confirm).
- 산출물 언어는 사용자 언어 설정(기어 아이콘, BCP-47)을 따른다.
- 동기화 중 그래프 스키마 변경이 필요해 보이는 캔버스 항목(신규 노드 종류)은 기존 매핑(Epic=BoundedContext, Feature=Feature, US=UserStory, 이벤트/애그리거트 등) 범위로만 반영하고, 매핑 불가 항목은 문서에만 남기고 안내한다.
- 마법사로 모델을 만든 뒤 사용자가 "문서 업로드" 일괄 ingestion을 실행하면, 일괄 경로는 이벤트스토밍 노드를 clear 후 재구축하므로 마법사 산출물(피보탈 표시 포함)이 덮어써질 수 있다 → 실행 전 경고하고, 피보탈/핫스팟·확정 BC는 보존하거나 증분 설계 경로 사용을 권한다(FR-027).
- 마법사 Discover 이벤트와 기존 커맨드 중심 도출 이벤트가 중복될 때, 동일 이벤트를 두 번 만들지 않고 병합 후보로 제시한다(FR-026/FR-009).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 시스템은 요구사항 탭에서 "맨땅에서 시작" 및 에픽 추가 진입점으로부터 **DDD 발견 마법사**를 열 수 있어야 한다.
- **FR-002**: 마법사는 시작 시 4개 프로파일링 질문(프로젝트 유형/DDD 경험/팀 규모/보유 산출물)을 제시하고, 답변에 따라 수행할 단계 조합을 추천해야 한다.
- **FR-003**: 마법사는 프로파일링(0)부터 코드(8)까지 전 단계를 제공하되, 사용자가 추천 조합을 가감하여 **일부 단계만 옵트인**해 수행할 수 있어야 한다.
- **FR-004**: 각 단계는 질문 응답과 초기 문서 붙여넣기 **두 가지 입력 방식**을 모두 지원해야 한다.
- **FR-005**: 시스템은 확정된 각 단계 산출물을 그래프에 반영한 뒤, 보조 산출물로 `.ddd/` 폴더의 마크다운(단계별 정해진 파일명·Mermaid 다이어그램 포함)을 그래프로부터 생성할 수 있어야 한다.
- **FR-006**: Understand(1단계)는 비즈니스 본질·사용자/이해관계자·목표 3개 질문 그룹을 다루고, 응답/문서로부터 **핵심 액터**를 식별해야 한다.
- **FR-007**: Discover(2단계)는 도메인 이벤트를 시간순으로 수집하고 각 이벤트의 트리거를 분류하며, **피보탈 이벤트**와 **핫스팟**을 구분 표시해야 한다.
- **FR-008**: Decompose(3단계)는 **피보탈 이벤트를 경계로** 이벤트를 묶어 서브도메인과 그룹 간 의존성을 도출해야 한다.
- **FR-009**: 기존 요구사항 기반 이벤트 도출과 EventStorming 결과가 겹칠 때, 시스템은 **중복 이벤트를 병합 후보로** 제시하고 피보탈 여부를 조정 가능하게 해야 한다.
- **FR-010**: Strategize(4단계)는 전략 분류 질문(예: "외부 아웃소싱 시 고객이 알아챌까?")으로 각 서브도메인/BC를 **Core/Supporting/Generic**으로 분류하고 BC 속성에 저장해야 한다.
- **FR-011**: 사용자가 BoundedContext를 생성하거나 클릭하면 시스템은 **BC 전용 상세·설정 화면**을 열고 그 안에 **Bounded Context Canvas 탭**을 제공해야 한다.
- **FR-012**: BC Canvas는 책임/목적, 전략 분류, 유비쿼터스 언어 및 용어 충돌, 인바운드/아웃바운드 메시지(이벤트·커맨드·쿼리), 주요 비즈니스 결정을 표시·편집할 수 있어야 한다.
- **FR-013**: Aggregate 상세 속성 화면은 **Aggregate Design Canvas 탭**을 제공하고, 상태 전이·처리 커맨드·발행 이벤트·불변 조건을 표시·편집할 수 있어야 한다.
- **FR-014**: 캔버스·인터뷰의 자동 생성은 Settings의 `requirementGenerationEngine` 토글(in-process LLM vs 로컬 Claude IDE + `ddd-starter` 스킬)을 따라 동작해야 한다.
- **FR-015**: 선택된 로컬 엔진이 미설치인 경우, 시스템은 생성을 차단하지 않고 **설치 안내**를 제시하고 대체 엔진 사용을 제안해야 한다.
- **FR-016**: 자동 생성된 모든 산출물(인터뷰 단계 결과·캔버스 초안)은 사용자에게 제시된 뒤 **확인(propose→confirm)** 시에만 그래프에 반영되어야 한다. 그래프가 진실의 원천이다.
- **FR-017**: 시스템은 현행 그래프 상태를 `.ddd/` 마크다운으로 **내보내기(export)** 할 수 있어야 한다. 외부에서 수정한 `.ddd` 문서의 **가져오기(import)** 는 선택 기능으로, 차이를 변경안으로 제시하여 확인 시에만 그래프에 반영한다.
- **FR-018**: `.ddd` 가져오기 시 그래프와 문서가 충돌하면 시스템은 **충돌 항목을 안내**하고 사용자가 채택할 측을 선택하게 해야 한다.
- **FR-019**: 마법사·캔버스의 그래프 반영은 기존 매핑(Epic=BoundedContext, Feature=Feature, US=UserStory, 도메인 이벤트, Aggregate)만 사용하고 **신규 노드 라벨/관계를 도입하지 않아야** 한다. 매핑 불가 항목은 `.ddd` 문서에만 남기고 안내한다.
- **FR-020**: 마법사 세션은 중단 후 재개 시 **완료된 단계의 답변·산출물을 보존**해야 한다.
- **FR-021**: 모든 생성 산출물은 사용자 언어 설정(기어 아이콘, BCP-47, 기본=브라우저 로케일)을 따라야 한다.
- **FR-022**: 자동 생성 진행 중(인터뷰·캔버스)에는 진행 상태가 **점진적으로 스트리밍**되어 사용자가 단계 진척을 확인할 수 있어야 한다.
- **FR-023**: 전략 분류 결과는 BC Canvas와 컨텍스트 맵에서 **시각적으로 구분**(배지/색상)되어야 한다.

#### Ingestion 통합 (FR-024 ~ FR-028)

- **FR-024**: DDD 마법사와 기존 "문서 업로드" 일괄 ingestion은 **Requirements 탭에서 병행 제공**되고 같은 Neo4j 그래프를 공유해야 한다. 두 진입구는 상호 링크(일괄 모달↔마법사)를 제공해야 한다.
- **FR-025**: 마법사의 후반 단계는 **신규 생성기를 두지 않고** 기존 설계 기계를 재사용해야 한다 — 서브도메인→BC 확정은 기존 BC 생성 경로, 설계 생성(Aggregate/Command/Event)은 기존 **증분 설계 실행기**(`/api/ingest/user-stories/design`), 미반영 식별·마무리는 기존 design-reflect 흐름.
- **FR-026**: 마법사의 이벤트 도출은 기존 **커맨드 중심 도출을 대체하지 않고 보완**해야 한다(빅픽처·피보탈·핫스팟 계층 추가). 두 경로가 같은 이벤트를 만들면 **병합 후보**로 제시해야 한다(FR-009 연계).
- **FR-027**: 전체 일괄 ingestion은 이벤트스토밍 노드를 **clear 후 재구축**하므로, 시스템은 (a) 마법사가 부여한 `Event.pivotal`/`hotspot`와 마법사 확정 산출물을 재구축 시 **보존**하거나, (b) 일괄 재투입이 모델을 재구축함을 **사전 경고**해야 한다. 마법사 확정 변경은 clear 대상이 아닌 증분 경로(BC 생성·증분 설계)로 반영하여 손실을 피해야 한다.
- **FR-028**: 마법사·캔버스 자동생성은 기존 ingestion과 **동일한 SSE 진행 표시**(진행 모달/스트림)와 **동일한 엔진 토글**(`requirementGenerationEngine`)을 사용해야 한다.

### Key Entities *(include if data involved)*

- **DDD 마법사 세션(DDD Wizard Session)**: 프로파일링 응답, 선택된 단계 조합, 단계별 진행 상태·답변. 중단/재개를 위해 보존됨(기존 030 clarification 세션 패턴 재사용 가능).
- **Bounded Context Canvas**: 한 BoundedContext(=Epic) 그래프 노드의 **투영 뷰**. 책임, 전략 분류, 유비쿼터스 언어/충돌, 인/아웃바운드 메시지, 비즈니스 결정. 그래프 BC 속성이 원천이며 `.ddd/07-bounded-contexts/<name>.md`로 내보내기(기존 `BoundedContextProjection`·`bc_canvas.py` 렌더러 재사용).
- **Aggregate Design Canvas**: 한 Aggregate 그래프 노드의 **투영 뷰**. 상태 전이, 커맨드, 이벤트, 불변 조건. 그래프가 원천이며 `.ddd/08-aggregates/<name>.md`로 내보내기(불변조건 spec 027, `AggregateProjection` 재사용).
- **비즈니스 컨텍스트(Business Context)**: 비즈니스 본질·사용자/이해관계자·목표·핵심 액터. 그래프(액터/페르소나 표현)가 원천이며 `.ddd/01-business-context.md`로 내보내기.
- **도메인 이벤트(Domain Event)**: 과거형 사건. 기존 Event 노드에 **피보탈 여부**·핫스팟 여부 속성 추가. EventStorming 산출물은 기존 이벤트 그래프에 반영.
- **서브도메인(Subdomain)**: 피보탈 이벤트 경계로 묶인 이벤트 그룹 → BoundedContext 후보. **전략 분류(core/supporting/generic)** 속성(기존 `contexts/classification` API는 core/supporting만 지원 → generic 확장 필요).
- **생성 엔진 설정**: `requirementGenerationEngine`(in-process LLM / 로컬 Claude IDE+스킬). Settings에 저장(그래프 아님).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 빈 프로젝트에서 사용자가 DDD 발견 마법사를 통해 첫 Bounded Context 후보 집합을 30분 이내에 도출할 수 있다.
- **SC-002**: EventStorming 단계에서 입력된 이벤트 중 피보탈 이벤트가 자동 후보로 표시되며, 사용자가 별도 학습 없이 피보탈/일반 구분을 조정할 수 있다.
- **SC-003**: 임의의 BC를 클릭하면 3초 이내에 전용 상세 화면이 열리고 Canvas 탭에서 책임·유비쿼터스 언어·인/아웃바운드 메시지를 확인할 수 있다.
- **SC-004**: 자동 생성된 BC/Aggregate 캔버스 초안의 핵심 필드(책임/언어/메시지, 상태전이/커맨드/이벤트/불변조건)가 대부분 채워져, 사용자가 처음부터 작성하지 않고 편집만으로 완성할 수 있다.
- **SC-005**: 마법사·캔버스의 모든 그래프 반영이 사용자 확인 단계를 거치며, 확인 없이 그래프가 변경되는 경우가 0건이다.
- **SC-006**: 마법사·캔버스 실행으로 기존 그래프 스키마(노드 라벨/관계)가 신규로 추가되는 건수가 0건이다.
- **SC-007**: 로컬 엔진 미설치 상황에서 사용자가 안내에 따라 설치하거나 대체 엔진으로 전환하여 생성을 완료할 수 있다(차단 0건).
- **SC-008**: core/supporting/generic 분류가 컨텍스트 맵/캔버스에서 시각적으로 구분되어, 사용자가 핵심 도메인을 한눈에 식별할 수 있다.

## Assumptions

- 매핑은 spec 034를 그대로 따른다: **Epic=`BoundedContext`, Feature=`Feature`, US=`UserStory`**. 도메인 이벤트·애그리거트는 기존 그래프 표현을 재사용한다.
- 캔버스/인터뷰 자동 생성 엔진은 spec 034의 **이원화 설정**을 재사용하며 신규 엔진을 추가하지 않는다(in-process=`get_llm`, 로컬=Claude IDE + `ddd-starter` 스킬 via `claude_code`/robo-spec MCP).
- **진실의 원천은 그래프**다. 캔버스는 그래프 노드의 투영 뷰이며, `.ddd` 마크다운은 그래프에서 생성하는 보조 내보내기 산출물이다.
- BC CRUD는 기존 requirements `bounded-context_crud`(POST·PATCH·DELETE `/bounded-context`)를 재사용한다. BC Canvas 자동생성은 기존 `POST /api/ddd-spec/generate-bounded-context`·`bc_canvas.py` 렌더러·`BoundedContextProjection`을 재사용한다.
- BC 상세 화면은 현재 부재(캔버스에서 BC 노드 클릭 시 무동작)이므로, 요구사항 탭 `EpicDetail`에 탭(Canvas 포함)을 추가하고 설계 캔버스에서 BC 클릭 시에도 동일 상세를 연다.
- Aggregate 상세 탭은 기존 `AggregateViewerInspector`/aggregate 드릴다운(spec 028) UI 위에 캔버스 탭을 추가하는 방식이며, `AggregateProjection`을 재사용한다.
- 인터뷰 마법사 세션·SSE·answer→encode→apply는 기존 030 clarification 세션 인프라 패턴을 재사용한다.
- 전략 분류는 기존 `contexts/classification`(core/supporting)을 **generic 포함 3분류로 확장**한다.
- 피보탈 이벤트는 기존 Event 노드/EventStorming 도출(event_storming, EventModeling `sequence`)에 **피보탈 플래그를 추가**하는 방식이며 신규 노드 라벨을 만들지 않는다.
- 설계 반영(이벤트→커맨드/애그리거트 등)이 필요한 경우 기존 change plan/apply(spec 004)·design_reflect(spec 034 US7) HITL 흐름을 재사용한다.
- 진행 스트리밍은 기존 SSE 인프라(`sse_starlette`, spec 034 보강 항목)를 재사용한다.
- 산출물 언어 정책은 기존 generation-language-policy(spec 031, 기어 아이콘 설정)를 따른다.
- 애그리거트 불변조건은 기존 spec 027 표현/저장을 재사용한다(중복 모델 도입 없음).
- `ddd-starter` 스킬은 사용자 로컬(`~/.claude/skills/ddd-starter`)에 설치되어 있으며, 로컬 엔진 경로에서 이를 호출한다(미설치 시 설치 안내).

## Dependencies

- 기존 **ingestion 파이프라인** (`api/features/ingestion/`): 일괄 ingestion(`/api/ingest/upload`+`/stream`, Requirements 탭 "문서 업로드" 모달), 증분 설계 실행기(`/api/ingest/user-stories/design`·`incremental_design_runner`), `events_from_user_stories`/`commands` 도출. 마법사 후반 단계가 이를 재사용/오케스트레이션.
- spec 034 (Epic/Feature/US 등록·이원화 생성 엔진·SSE 보강·propose→confirm·design_reflect)
- spec 027 (Aggregate 불변조건), spec 028 (Aggregate 탭 드릴다운)
- spec 022 (EventStorming 기반 spec 생성), 기존 이벤트 도출 로직
- spec 004 (change plan/apply HITL)
- spec 015/029 (claude_code PTY, robo-spec MCP, 로컬 도구 preflight)
- spec 031 (생성 언어 정책)
- 로컬 `ddd-starter` 스킬(uengine-oss/ddd-starter-skill-kor)
