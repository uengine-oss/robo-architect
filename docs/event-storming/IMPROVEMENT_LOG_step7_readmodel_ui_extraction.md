# ReadModel 및 UI 생성 개선 로그

**작성일**: 2025-01-XX  
**개선 범위**: ReadModel 추출 및 UI 생성 로직 개선

## 📋 개요

이번 개선에서는 ReadModel 추출과 UI 생성 로직을 backend-generators의 노하우를 적용하여 개선했습니다.

### 주요 개선 사항

1. **ReadModel 추출 프롬프트 개선**
   - backend-generators의 `command_readmodel_extractor.py`에서 ReadModel 추출 부분의 노하우 적용
   - XML 구조로 재구성 및 상세 가이드라인 추가
   - ReadModel 카테고리화 (Data Retrieval, Search/Filtering, Statistics/Reports, UI Support Data)
   - Actor 분류 및 isMultipleResult 필드 추가

2. **UI 생성 로직 개선**
   - Policy로 호출되는 Command는 UI 생성 제외 (이미 구현되어 있었으나 정확도 개선)
   - Command ID 기반 필터링 추가로 더 정확한 필터링

---

## 🔍 개선 상세

### 1. ReadModel 추출 프롬프트 개선

#### Before (개선 전)
- 간단한 텍스트 기반 프롬프트
- 기본적인 명명 규칙만 제공
- Actor 분류 없음
- isMultipleResult 필드 없음
- 카테고리화 및 예제 부족

#### After (개선 후)
- 구조화된 XML 기반 프롬프트 (가독성 및 구조화 향상)
- 상세한 ReadModel 카테고리화 (4가지 카테고리)
- 명확한 Actor 분류 (User Story의 role 기반, 자연스러운 도메인 적합한 actor 이름 사용)
- isMultipleResult 필드 추가 (list/collection vs single item 구분)
- 명명 규칙 강화 및 예제 추가
- Traceability 요구사항 강화
- Event-Based Projection 가이드라인 추가

#### 참고한 backend-generators 코드
**위치**: `backend-generators/src/project_generator/workflows/sitemap/command_readmodel_extractor.py`

**참고한 내용 (ReadModel 부분만):**
- `<section id="readmodel_extraction">` 섹션 (라인 298-352)
- ReadModel 추출 규칙:
  - Data Retrieval (Single Retrieval, List Retrieval)
  - Search and Filtering
  - Statistics and Reports
  - UI Support Data
- ReadModel 명명 규칙 (Noun + Purpose 패턴)
- Actor 분류 (user, admin, system)
- isMultipleResult 필드
- Bounded Context 할당 전략

**제외한 부분:**
- Command 추출 부분 (`<section id="command_extraction">`) - Command 추출 단계에서 이미 사용됨
- 청킹 처리 로직 - 향후 공통 모듈로 처리 예정

### 2. ReadModelCandidate 모델 개선

**변경 파일**: `api/features/ingestion/event_storming/state.py`

**추가된 필드:**
- `actor: str` - ReadModel을 사용하는 actor (User Story의 role 기반)
- `isMultipleResult: bool` - list/collection 결과인지 single item 결과인지 구분

### 3. ReadModel 생성 로직 개선

**변경 파일**: 
- `api/features/ingestion/event_storming/neo4j_ops/readmodels.py`
- `api/features/ingestion/workflow/phases/readmodels.py`

**변경 사항:**
- `create_readmodel` 함수에 `actor`와 `is_multiple_result` 파라미터 추가
- Neo4j에 `actor`와 `isMultipleResult` 필드 저장
- ReadModel 생성 시 LLM이 생성한 `actor`와 `isMultipleResult` 값 전달

### 4. UI 생성 로직 개선

**변경 파일**: `api/features/ingestion/workflow/phases/ui_wireframes.py`

**개선 사항:**
- Policy로 호출되는 Command를 더 정확하게 필터링
- Command ID 기반 필터링 추가 (기존에는 Command name만 사용)
- Policy 생성 시 `invoke_command_id`를 Policy 객체에 저장하여 UI 생성 시 활용

**로직:**
1. Policy 생성 시 `invoke_command_id`를 Policy 객체에 저장
2. UI 생성 시 Policy의 `invoke_command_id`와 `invoke_command` (name)를 모두 수집
3. Command의 ID 또는 name이 Policy-invoked 목록에 있으면 UI 생성 스킵

**이유:**
- Policy로 호출되는 Command는 다른 BC의 Event에 의해 자동으로 트리거됨
- 사용자가 직접 호출하는 것이 아니므로 UI가 필요 없음
- 예: `OrderCancelled` Event → Policy → `ProcessRefund` Command (UI 불필요)

---

## 📝 변경된 파일 목록

### 프롬프트
- `api/features/ingestion/event_storming/prompts.py`
  - `EXTRACT_READMODELS_PROMPT`: XML 구조로 재구성, 상세 가이드라인 추가

### 모델
- `api/features/ingestion/event_storming/state.py`
  - `ReadModelCandidate`: `actor`, `isMultipleResult` 필드 추가

### Neo4j Operations
- `api/features/ingestion/event_storming/neo4j_ops/readmodels.py`
  - `create_readmodel`: `actor`, `is_multiple_result` 파라미터 추가 및 저장

### Workflow Phases
- `api/features/ingestion/workflow/phases/readmodels.py`
  - ReadModel 생성 시 `actor`와 `isMultipleResult` 전달
- `api/features/ingestion/workflow/phases/policies.py`
  - Policy 생성 시 `invoke_command_id`를 Policy 객체에 저장
- `api/features/ingestion/workflow/phases/ui_wireframes.py`
  - Policy-invoked Command 필터링 로직 개선 (ID 기반 추가)

---

## 🎯 개선 효과

### ReadModel 추출
- ✅ 더 정확한 ReadModel 카테고리화
- ✅ Actor 분류로 ReadModel 사용자 명확화
- ✅ isMultipleResult로 단일/목록 결과 구분
- ✅ Event-Based Projection 가이드라인으로 CQRS 패턴 명확화

### UI 생성
- ✅ Policy로 호출되는 Command는 UI 생성 제외 (불필요한 UI 생성 방지)
- ✅ Command ID 기반 필터링으로 더 정확한 필터링
- ✅ 사용자가 직접 호출하는 Command와 ReadModel에만 UI 생성

---

## 🔄 워크플로우 순서

현재 워크플로우 순서는 변경되지 않았습니다:

1. **User Stories** 생성
2. **Bounded Contexts** 생성
3. **Aggregates** 생성
4. **Commands** 생성
5. **Events** 생성
6. **ReadModels** 생성 ← 개선됨
7. **Properties** 생성
8. **Policies** 생성
9. **UI Wireframes** 생성 ← 개선됨

**중요**: Policy 생성이 UI 생성보다 먼저 실행되므로, Policy-invoked Command를 정확히 필터링할 수 있습니다.

---

## 📚 참고 사항

### ReadModel 추출 vs backend-generators 차이점

**backend-generators의 경우:**
- 요구사항 문서에서 직접 Command/ReadModel 추출 (한 번에 함께 추출)
- 청킹 처리 필수 (대용량 요구사항)
- Bounded Context 할당 전략 포함

**현재 Event Storming 워크플로우:**
- User Story → BC → Aggregate → Command → Event → ReadModel 순서
- ReadModel은 Event를 기반으로 한 CQRS projection으로 생성
- BC별로 순차 처리 (청킹은 향후 공통 모듈로 처리 예정)

### UI 생성 전략

**UI가 생성되는 경우:**
- Command: Policy로 호출되지 않는 Command (사용자가 직접 호출)
- ReadModel: 모든 ReadModel (사용자가 조회하는 데이터)

**UI가 생성되지 않는 경우:**
- Command: Policy로 호출되는 Command (자동 트리거)
- Command: ui_description이 없는 Command

**이유:**
- Policy로 호출되는 Command는 다른 BC의 Event에 의해 자동으로 트리거되므로 사용자 인터페이스가 필요 없음
- 예: `OrderCancelled` Event → Policy → `ProcessRefund` Command (백엔드 자동 처리)

---

## ✅ 검증 체크리스트

개선 후 다음 사항들을 확인해야 합니다:

- [ ] ReadModel에 `actor` 필드가 생성되는지 확인
- [ ] ReadModel에 `isMultipleResult` 필드가 생성되는지 확인
- [ ] Policy로 호출되는 Command에 UI가 생성되지 않는지 확인
- [ ] 사용자가 직접 호출하는 Command에 UI가 생성되는지 확인
- [ ] ReadModel에 UI가 생성되는지 확인

---

## 🔮 향후 개선 가능 사항

1. **청킹/스캐닝 처리**
   - ReadModel 추출에도 대용량 처리 로직 추가 (향후 공통 모듈로 처리)

2. **ReadModel CQRS Operations**
   - ReadModel에 대한 CQRS Operations (TRIGGERED_BY Event) 생성
   - 현재는 ReadModel만 생성하고, CQRS Operations는 별도 단계에서 처리

3. **UI 생성 최적화**
   - UI 생성 시 더 많은 컨텍스트 제공 (Aggregate 정보, 관련 Events 등)
   - UI 템플릿 품질 향상

---

**참고**: backend-generators의 `command_readmodel_extractor.py`에서 **ReadModel 추출 부분만** 참고했으며, Command 관련 내용은 제외했습니다. Command 추출은 Event Storming 워크플로우에서 별도 단계로 처리되므로, 해당 단계에서 Command 관련 노하우를 적용했습니다.
