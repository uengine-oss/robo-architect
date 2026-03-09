# PRD 생성: 구현체 지시사항 및 옵션 반영 현황

> **목적**: 이벤트 스토밍 요소들과 PRD 모달 옵션들이 실제 구현체 지시사항에 모두 반영되었는지 확인

## 개요

이 문서는 다음 두 가지를 확인합니다:
1. **이벤트 스토밍 요소들**이 구현체 지시사항에 반영되었는지
2. **PRD 모달에서 선택된 옵션들**이 PRD 생성에 반영되었는지

---

## 1. 이벤트 스토밍 요소 → 구현체 지시사항 매핑

### 1.1 Aggregate (집계)

#### ✅ 반영 현황: 완전 반영

**BC Spec에 포함:**
- Root Entity
- Invariants (비즈니스 불변식)
- Enumerations (열거형)
- Value Objects (값 객체)
- Properties (속성, isKey, isForeignKey 포함)

**구현 지시사항:**
- `generate_eventstorming_implementation_rule()`: Aggregate Implementation 섹션
  - Root Entity 사용
  - Invariants 강제
  - Properties 타입 매핑
  - Enumerations 상태 관리
  - Value Objects 구현

**Tech Stack Rules:**
- `generate_cursor_tech_stack_rule()`: Framework별 Aggregate 구현 패턴
- Database별 가이드라인 (`_get_database_specific_guidelines()`)

---

### 1.2 Command (명령)

#### ✅ 반영 현황: 완전 반영

**BC Spec에 포함:**
- Command name, actor, category
- Input Schema
- Description
- Properties

**구현 지시사항:**
- `generate_eventstorming_implementation_rule()`: Command Implementation 섹션
  - Command Handler 패턴
  - REST API Endpoints (`POST /api/{{bc_name}}/{{command-name}}`)
  - Input Schema → DTO 매핑
  - Actor Authorization
  - Event Emission

**Tech Stack Rules:**
- Framework별 Command Handler 패턴
- HTTP Response Codes (201, 200, 204, 400, 403)

---

### 1.3 Event (이벤트)

#### ✅ 반영 현황: 완전 반영

**BC Spec에 포함:**
- Event name, version
- Schema
- Description
- Properties

**구현 지시사항:**
- `generate_eventstorming_implementation_rule()`: Event Implementation 섹션
  - Event Class (past tense naming)
  - Event Publishing (messaging platform)
  - Event Consumption (Policies)
  - Schema Versioning
  - Idempotency

**Tech Stack Rules:**
- Messaging platform별 이벤트 발행/구독 패턴
- Schema versioning 가이드라인

**PRD Main:**
- Event Publishing 섹션 (Service Independence 강조)
- Event Consumption 섹션 (Schema Contract, Version Support, Idempotency)

---

### 1.4 ReadModel (읽기 모델)

#### ✅ 반영 현황: 완전 반영

**BC Spec에 포함:**
- ReadModel name, actor
- Provisioning Type (CQRS)
- isMultipleResult (list/collection/single result)
- Properties

**구현 지시사항:**
- `generate_eventstorming_implementation_rule()`: ReadModel Implementation 섹션
  - CQRS Pattern
  - Projection Handler
  - Query API Endpoints:
    - Single: `GET /api/{{bc_name}}/{{readmodel-name}}/{{id}}`
    - List: `GET /api/{{bc_name}}/{{readmodel-name}}?filter=value&page=1&size=10`
    - Collection: `GET /api/{{bc_name}}/{{readmodel-name}}`
  - Actor Support (filtering/authorization)
  - Denormalization

**Tech Stack Rules:**
- Framework별 Query API 패턴
- Database별 ReadModel 최적화

---

### 1.5 Policy (정책)

#### ✅ 반영 현황: 완전 반영

**BC Spec에 포함:**
- Policy name, description
- Trigger Event (from BC)
- Invoke Command (to BC)

**구현 지시사항:**
- `generate_eventstorming_implementation_rule()`: Policy Implementation 섹션
  - Event Listener (messaging platform subscription)
  - Cross-BC Events 처리
  - Command Invocation (async via messaging)
  - Idempotency
  - Data Mapping

**PRD Main:**
- Policy Implementation 섹션 (Service Dependencies 명확화)
  - 직접 의존성 없음
  - Event Contract Dependency만
  - 독립 배포 가능

---

### 1.6 UI Wireframe (UI 와이어프레임)

#### ✅ 반영 현황: 완전 반영

**BC Spec에 포함:**
- UI name, description
- Template (HTML wireframe)
- Attached to Command/ReadModel

**구현 지시사항:**
- `generate_eventstorming_implementation_rule()`: UI Wireframe Implementation 섹션
  - Attached to Command → Form components
  - Attached to ReadModel → Display/list components
  - Wireframe Template 사용
  - API Integration (Command POST, ReadModel GET)
  - State Management (framework-specific)

**Frontend PRD:**
- `generate_frontend_prd()`: UI wireframes 기반 frontend 구현 가이드
- Frontend Cursor Rules: `generate_frontend_cursor_rule()`

**PRD Main:**
- Development Guidelines → UI Wireframe Implementation 섹션

---

### 1.7 GWT Test Cases (Given/When/Then 테스트)

#### ✅ 반영 현황: 완전 반영

**BC Spec에 포함:**
- GWT for Command/Event/ReadModel
- Given/When/Then references
- Test Cases (scenarios)

**구현 지시사항:**
- `generate_gwt_test_generation_rule()`: GWT test patterns
- Framework별 테스트 패턴
- DDD principles 기반 테스트 구조

---

## 2. PRD 모달 옵션 → PRD 생성 반영 현황

### 2.1 Language (언어)

#### ✅ 반영 현황: 완전 반영

**옵션:**
- Java, Kotlin, TypeScript, Python, Go

**반영 위치:**
- `generate_main_prd()`: Technology Stack 테이블
- `generate_cursor_tech_stack_rule()`: Language 섹션
- `_get_file_extensions_for_language()`: 파일 확장자 결정
- `_get_code_structure_guide()`: 언어별 코드 구조

---

### 2.2 Framework (프레임워크)

#### ✅ 반영 현황: 완전 반영

**옵션:**
- Spring Boot, Spring WebFlux, NestJS, Express, FastAPI, Gin, Fiber

**반영 위치:**
- `generate_main_prd()`: Technology Stack 테이블, Framework별 가이드 참조
- `generate_cursor_tech_stack_rule()`: Framework별 구현 가이드라인
- `_get_tech_stack_implementation_guidelines()`: Framework별 상세 가이드
- `_get_code_structure_guide()`: Framework별 프로젝트 구조
- Rules 파일명: `.cursor/rules/{framework}.mdc`
- @mention: `@{framework}`

---

### 2.3 Messaging Platform (메시징 플랫폼)

#### ✅ 반영 현황: 완전 반영

**옵션:**
- Kafka, RabbitMQ, Redis Streams, Pulsar, In-memory

**반영 위치:**
- `generate_main_prd()`: Technology Stack 테이블, Event Publishing/Consumption 섹션
- `generate_eventstorming_implementation_rule()`: Event Publishing/Consumption에 messaging platform 명시
- `generate_cursor_tech_stack_rule()`: Messaging 섹션
- Policy Implementation: messaging platform 기반 async invocation

---

### 2.4 Database (데이터베이스)

#### ✅ 반영 현황: 완전 반영

**옵션:**
- PostgreSQL, MySQL, MongoDB, H2

**반영 위치:**
- `generate_main_prd()`: Technology Stack 테이블, Database & Persistence 섹션
- `generate_cursor_tech_stack_rule()`: Database & Persistence 섹션
- `_get_database_specific_guidelines()`: Database별 구체적 가이드라인
- Framework별 ORM/ODM 가이드 (Spring Data JPA, SQLAlchemy, TypeORM, GORM)

---

### 2.5 Deployment Style (배포 스타일)

#### ✅ 반영 현황: 완전 반영

**옵션:**
- Microservices, Modular Monolith

**반영 위치:**
- `generate_main_prd()`: Technology Stack 테이블, Deployment 섹션
- `generate_cursor_tech_stack_rule()`: Deployment 섹션
- Messaging hint: Modular Monolith → In-memory event bus

---

### 2.6 Frontend Framework (프론트엔드 프레임워크)

#### ✅ 반영 현황: 완전 반영

**옵션:**
- Vue, React

**반영 위치:**
- `generate_main_prd()`: Frontend 섹션 (조건부)
- `generate_frontend_prd()`: Frontend PRD 생성
- `generate_frontend_cursor_rule()`: Frontend Cursor Rules 생성
- Rules 파일명: `.cursor/rules/{frontend_framework}.mdc`
- @mention: `@{frontend_framework}`

**조건부 생성:**
- `include_frontend == true` AND `ai_assistant == CURSOR`일 때만 생성

---

### 2.7 AI Assistant (AI 어시스턴트)

#### ✅ 반영 현황: 완전 반영

**옵션:**
- Cursor, Claude

**반영 위치:**
- **Cursor 선택 시:**
  - `.cursorrules` 생성
  - `.cursor/rules/*.mdc` 생성 (ddd-principles, eventstorming-implementation, gwt-test-generation, {framework}, {frontend_framework})
  - Frontend PRD/Rules (조건부)
- **Claude 선택 시:**
  - `CLAUDE.md` 생성
  - `.claude/agents/{bc_name}_agent.md` 생성

**조건부 생성:**
- `prd_export.py`: `download_prd_zip()` 및 `generate_prd()`에서 조건부 처리

---

### 2.8 기타 옵션

#### ✅ 반영 현황: 완전 반영

**옵션:**
- `project_name`: README, 파일명에 사용
- `package_name`: Java/Kotlin 패키지 구조에 사용
- `include_docker`: Dockerfile, docker-compose.yml 생성
- `include_kubernetes`: (향후 확장 가능)
- `include_tests`: GWT test generation rule 참조

---

## 3. 구현체 지시사항 상세 확인

### 3.1 Command → REST API 매핑

#### ✅ 명확히 반영됨

**지시사항:**
- `POST /api/{{bc_name}}/{{command-name}}`
- Input Schema → DTO 매핑
- Response Codes (201, 200, 204, 400, 403)
- Actor Authorization

**위치:**
- `generate_eventstorming_implementation_rule()`: Command Implementation → REST API Endpoints

---

### 3.2 Event → Messaging Platform 매핑

#### ✅ 명확히 반영됨

**지시사항:**
- Event Publishing: `{messaging_platform}` 사용
- Event Consumption: `{messaging_platform}` consumer
- Schema Versioning
- Idempotency

**위치:**
- `generate_eventstorming_implementation_rule()`: Event Publishing/Consumption
- `generate_main_prd()`: Event Publishing/Consumption 섹션

---

### 3.3 ReadModel → Query API 매핑

#### ✅ 명확히 반영됨

**지시사항:**
- Single: `GET /api/{{bc_name}}/{{readmodel-name}}/{{id}}`
- List: `GET /api/{{bc_name}}/{{readmodel-name}}?filter=value&page=1&size=10`
- Collection: `GET /api/{{bc_name}}/{{readmodel-name}}`
- isMultipleResult에 따른 반환 타입

**위치:**
- `generate_eventstorming_implementation_rule()`: ReadModel Implementation → Query API Endpoints

---

### 3.4 Policy → Event Listener + Command Invocation 매핑

#### ✅ 명확히 반영됨

**지시사항:**
- Event Listener: `{messaging_platform}` subscription
- Command Invocation: async via `{messaging_platform}`
- Cross-BC Events 처리
- Idempotency

**위치:**
- `generate_eventstorming_implementation_rule()`: Policy Implementation
- `generate_main_prd()`: Policy Implementation 섹션 (Service Dependencies 명확화)

---

### 3.5 UI Wireframe → Frontend Component 매핑

#### ✅ 명확히 반영됨

**지시사항:**
- Attached to Command → Form components
- Attached to ReadModel → Display/list components
- Wireframe Template 사용
- API Integration

**위치:**
- `generate_eventstorming_implementation_rule()`: UI Wireframe Implementation
- `generate_frontend_prd()`: Frontend PRD
- `generate_frontend_cursor_rule()`: Frontend Rules

---

### 3.6 Aggregate → Database Schema 매핑

#### ✅ 명확히 반영됨

**지시사항:**
- Properties → Database columns
- isKey → Primary key
- isForeignKey → Foreign key
- Database별 구체적 가이드라인

**위치:**
- `generate_main_prd()`: Database & Persistence 섹션
- `_get_database_specific_guidelines()`: Database별 가이드
- `generate_cursor_tech_stack_rule()`: Database & Persistence 섹션

---

## 4. 체크리스트

### 4.1 이벤트 스토밍 요소 반영

- [x] Aggregate → 구현 지시사항 (Root Entity, Invariants, Properties, Enumerations, Value Objects)
- [x] Command → REST API 매핑 (Endpoint, Input Schema, Response Codes)
- [x] Event → Messaging Platform 매핑 (Publishing, Consumption, Versioning, Idempotency)
- [x] ReadModel → Query API 매핑 (Single/List/Collection, Actor filtering)
- [x] Policy → Event Listener + Command Invocation 매핑 (Cross-BC, Async)
- [x] UI Wireframe → Frontend Component 매핑 (Form/Display, Template, API Integration)
- [x] GWT Test Cases → Test Generation Rule

### 4.2 PRD 모달 옵션 반영

- [x] Language → 코드 구조, 파일 확장자, 패턴
- [x] Framework → 구현 가이드라인, 프로젝트 구조, Rules 파일
- [x] Messaging Platform → Event Publishing/Consumption 패턴
- [x] Database → Persistence 가이드라인, Database별 구체적 지시사항
- [x] Deployment Style → 배포 패턴
- [x] Frontend Framework → Frontend PRD, Frontend Rules (조건부)
- [x] AI Assistant → Cursor Rules / Claude Agents (조건부)
- [x] 기타 옵션 (project_name, package_name, include_docker, include_tests)

### 4.3 구현체 지시사항 명확성

- [x] Command → REST API 엔드포인트 패턴 명시
- [x] Event → Messaging Platform 사용법 명시
- [x] ReadModel → Query API 패턴 명시 (isMultipleResult 기반)
- [x] Policy → Event Listener + Command Invocation 패턴 명시
- [x] UI Wireframe → Frontend Component 매핑 명시
- [x] Aggregate → Database Schema 매핑 명시
- [x] Service Independence & Dependencies 명확화
- [x] Event Contract & Schema Versioning 명확화

---

## 5. 결론

### ✅ 모든 항목 반영 완료

1. **이벤트 스토밍 요소들**이 모두 구현체 지시사항에 반영됨:
   - Aggregate, Command, Event, ReadModel, Policy, UI Wireframe, GWT Test Cases
   - 각 요소별 명확한 구현 패턴 제공

2. **PRD 모달 옵션들**이 모두 PRD 생성에 반영됨:
   - Language, Framework, Messaging, Database, Deployment, Frontend Framework, AI Assistant
   - 각 옵션별 동적 콘텐츠 생성

3. **구현체 지시사항**이 명확함:
   - Sticker-to-code 매핑 명확
   - Tech stack별 구체적 가이드라인
   - Database별 구체적 지시사항
   - Service Independence & Dependencies 명확화

---

## 참고 파일

- `api/features/prd_generation/prd_artifact_generation.py`: 주요 생성 로직
- `api/features/prd_generation/routes/prd_export.py`: 조건부 파일 생성 로직
- `api/features/prd_generation/prd_model_data.py`: Neo4j 데이터 조회
- `api/features/prd_generation/prd_api_contracts.py`: API contracts
