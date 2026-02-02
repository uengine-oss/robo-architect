# Step 2: Bounded Context 추출 개선 - 개선 로그

## 개선 일자
2025-01-XX

## 개선 목표
Event Storming 워크플로우의 Bounded Context 추출 단계에서 backend-generators의 노하우를 활용하여 더 정확하고 근거 있는 BC 추출을 구현합니다.

---

## 참고한 backend-generators 코드

### 1. `bounded_context_generator.py` - `_build_task_guidelines` 메서드
**위치**: `backend-generators/src/project_generator/workflows/bounded_context/bounded_context_generator.py` (라인 447-656)

**참고한 내용:**
- 상세한 Task Guidelines 프롬프트 구조
- Core Principles (High Cohesion, Low Coupling, Event Action Range, Event Flow, Actor Grouping)
- Domain Classification Strategy (Core Domain, Supporting Domain, Generic Domain)
- Bounded Context Division Guidelines
- Output Format 및 Field Requirements

**적용 사항:**
- Event Storming에 맞게 Core Principles 통합
- Domain Classification Strategy 추가 (Core/Supporting/Generic)
- Bounded Context Identification Rules 강화
- Analysis Approach 추가

### 2. `bounded_context_generator.py` - `_build_prompt` 메서드
**위치**: `backend-generators/src/project_generator/workflows/bounded_context/bounded_context_generator.py` (라인 312-372)

**참고한 내용:**
- Persona 정보 (System Prompt)
- Task Guidelines 구조
- Language Guide
- XML 형식의 입력 구조

**적용 사항:**
- 프롬프트를 구조화된 XML 형식으로 개선
- Core Instructions 섹션 추가
- Guidelines를 섹션별로 구조화

### 3. `bounded_context_generator.py` - Domain Classification
**위치**: `backend-generators/src/project_generator/workflows/bounded_context/bounded_context_generator.py` (라인 475-519)

**참고한 내용:**
- Core Domain, Supporting Domain, Generic Domain의 특성
- 각 도메인 타입의 예시
- Implementation Strategy 가이드

**적용 사항:**
- Domain Classification Strategy를 프롬프트에 통합
- 각 도메인 타입의 특성과 예시 추가
- BC 분류 시 도메인 타입 고려하도록 가이드

---

## 구현 내용

### 1. 프롬프트 구조 강화

#### Before (기존)
```python
IDENTIFY_BC_FROM_STORIES_PROMPT = """Analyze the following User Stories and identify candidate Bounded Contexts.

User Stories:
{user_stories}

Guidelines for identifying Bounded Contexts:
1. Group related functionality that shares domain concepts
2. Consider organizational boundaries (different teams)
...
"""
```

#### After (개선 후)
```python
IDENTIFY_BC_FROM_STORIES_PROMPT = """Analyze the following User Stories and identify candidate Bounded Contexts following Domain-Driven Design principles.

<core_instructions>
<title>Bounded Context Division Task</title>
<task_description>...</task_description>

<guidelines>
<title>Bounded Context Division Guidelines</title>

<section id="core_principles">
<title>Core Principles</title>
<rule id="1">**High Cohesion, Low Coupling:** ...</rule>
<rule id="2">**Event Action Range:** ...</rule>
...
</section>

<section id="domain_classification">
<title>Domain Classification Strategy</title>
<core_domain>...</core_domain>
<supporting_domain>...</supporting_domain>
<generic_domain>...</generic_domain>
</section>

<section id="identification_rules">
<title>Bounded Context Identification Rules</title>
...
</section>
</guidelines>
</core_instructions>

<analysis_approach>
...
</analysis_approach>
"""
```

### 2. Core Principles 추가
- **High Cohesion, Low Coupling**: 관련된 행동과 데이터를 그룹화하면서 컨텍스트 간 의존성 최소화
- **Event Action Range**: 이벤트의 액션 범위를 고려하여 BC 경계 생성
- **Event Flow**: 이벤트 간 관계를 고려하여 플로우 생성
- **Actor Grouping**: 어떤 액터(역할)가 어떤 User Story를 담당하는지 고려
- **Business Capability Alignment**: BC가 비즈니스 역량과 정렬되도록 보장
- **User Story Grouping**: 도메인 개념, 데이터 소유권, 비즈니스 프로세스를 공유하는 User Story 그룹화

### 3. Domain Classification Strategy 추가
- **Core Domain**: 비즈니스 경쟁 우위에 직접적인 영향, 사용자 대면 기능, 전략적 중요성
- **Supporting Domain**: Core Domain 기능을 가능하게 하는 내부 비즈니스 프로세스
- **Generic Domain**: 산업 전반에 걸친 공통 기능, 서드파티 솔루션으로 대체 가능

각 도메인 타입에 대한 특성과 예시를 제공하여 LLM이 적절히 분류할 수 있도록 가이드.

### 4. Bounded Context Identification Rules 강화
- User Story 그룹화 규칙
- 조직적 경계 고려
- 스케일링 요구사항 고려
- 데이터 소유권 고려
- 과도한 세분화 방지
- 과도한 통합 방지
- User Story 할당 규칙 (각 User Story는 정확히 하나의 BC에 속함)

### 5. Analysis Approach 추가
LLM이 분석할 때 고려해야 할 사항:
- Domain Concepts: User Story에서 언급된 주요 비즈니스 개념
- Actor Patterns: 관련 Story에서 함께 나타나는 액터(역할)
- Business Processes: 설명된 비즈니스 프로세스나 워크플로우
- Data Ownership: 각 BC가 소유하고 관리할 데이터
- Integration Points: BC 간 통신이 필요한 지점

---

## 개선 효과

### Before (기존)
- 간단한 가이드라인만 제공
- 도메인 분류 전략 없음
- Core Principles 명시 없음
- 분석 접근법이 불명확

### After (개선 후)
- 구조화된 Task Guidelines 제공
- Domain Classification Strategy로 BC 분류 품질 향상
- Core Principles로 DDD 원칙 준수 강화
- 명확한 Analysis Approach로 일관된 분석 보장
- 더 상세하고 근거 있는 BC 추출

---

## 참고 사항

### Event Storming vs backend-generators 차이점

**backend-generators의 경우:**
- Requirements Document, Actors, Events를 입력으로 받음
- PBC (Pre-Built Component) 매칭 가능
- Traceability를 위한 refs (line number references) 사용
- BC 관계 및 설명 생성

**Event Storming의 경우:**
- User Stories만 입력으로 받음
- PBC 정보 없음 (선택적)
- Traceability는 user_story_ids로 추적
- BC 관계는 Policy 단계에서 처리

따라서 backend-generators의 모든 기능을 그대로 적용하기보다는, Event Storming의 컨텍스트에 맞게 조정하여 적용했습니다.

### 향후 개선 가능 사항

1. **BC 관계 분석 강화**
   - backend-generators의 `relations` 및 `explanations` 생성 로직 참고
   - BC 간 상호작용 패턴 분석

2. **PBC 매칭** (선택적)
   - PBC 정보가 제공되는 경우 매칭 규칙 적용

3. **Traceability 강화**
   - User Story의 원본 요구사항과의 연결 강화
   - Requirements line number 참조 (현재는 user_story_ids만 사용)

---

## 테스트 시나리오

### 1. 정상 케이스
- 여러 User Story가 명확한 도메인 경계로 분리되는 경우
- Core Domain, Supporting Domain, Generic Domain이 적절히 분류되는 경우

### 2. 경계 케이스
- User Story가 여러 BC에 걸치는 경우 (하나의 Primary BC 할당)
- 도메인 경계가 모호한 경우

### 3. 검증 케이스
- 모든 User Story가 BC에 할당되었는지 확인
- BC 이름이 PascalCase인지 확인
- Rationale이 충분히 상세한지 확인

---

## 참고 파일

### 수정된 파일
- `api/features/ingestion/event_storming/prompts.py`
  - `IDENTIFY_BC_FROM_STORIES_PROMPT` 프롬프트 강화

### 참고한 backend-generators 파일
- `backend-generators/src/project_generator/workflows/bounded_context/bounded_context_generator.py`
  - `_build_task_guidelines` 메서드 (라인 447-656)
  - `_build_prompt` 메서드 (라인 312-372)
  - Domain Classification Strategy (라인 475-519)
