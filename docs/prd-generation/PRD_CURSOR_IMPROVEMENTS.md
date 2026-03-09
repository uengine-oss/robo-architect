# PRD Generation: Cursor 기반 개선 사항 정리

> **목적**: Cursor IDE 기반 PRD 생성에서 개선된 내용들을 정리하여, 향후 Claude Agent 기반 BC별 skills 적용 시 참고

## 개요

Event Storming 모델 기반 PRD 생성에서 Cursor IDE를 위한 개선 사항들을 정리한 문서입니다. 이 개선 사항들은 향후 Claude Agent 기반 BC별 skills에도 동일하게 적용되어야 합니다.

---

## 1. Database 관련 지시사항 강화

### 개선 내용

#### 1.1 `.cursorrules` - Database 섹션 강화
- BC Isolation, Transactions, Indexing, Connection Pooling, Migration 등 추가
- Database별 구체적인 가이드라인 추가 (PostgreSQL, MySQL, MongoDB, H2)

#### 1.2 Tech Stack별 Guidelines에 "Database & Persistence" 섹션 추가
- **Spring Boot**: Spring Data JPA + Database별 가이드
- **FastAPI**: SQLAlchemy + Database별 가이드
- **NestJS**: TypeORM/Prisma + Database별 가이드
- **Go**: GORM/sqlx + Database별 가이드

#### 1.3 Database별 구체적 지시사항 (`_get_database_specific_guidelines`)

**PostgreSQL**:
- `SERIAL`/`BIGSERIAL` 또는 `UUID` 사용
- `JSONB` 활용
- `TIMESTAMP WITH TIME ZONE` 사용
- 인덱싱 전략
- Connection pooling (HikariCP, asyncpg 등)

**MySQL**:
- `InnoDB` 스토리지 엔진
- `utf8mb4` 문자셋
- `AUTO_INCREMENT` 또는 UUID
- Connection pooling

**MongoDB**:
- `ObjectId` 또는 UUID
- 문서 구조 설계 (denormalization)
- 복합 인덱스
- 트랜잭션 (MongoDB 4.0+)

**H2**:
- In-memory/File-based 모드
- 개발/테스트용 (프로덕션 아님)

### 적용 위치
- `api/features/prd_generation/prd_artifact_generation.py`
  - `generate_cursor_rules()`: Database 섹션 강화
  - `_get_tech_stack_implementation_guidelines()`: Database & Persistence 섹션 추가
  - `_get_database_specific_guidelines()`: Database별 구체적 가이드라인 함수

---

## 2. Cursor @mention 기능 활용

### 개선 내용

#### 2.1 PRD.md에서 Rules 참조 시 @mention 형식 사용
- `@.cursorrules` (global rules)
- `@{{framework}}` (tech stack rules, 예: `@spring-boot`)
- `@ddd-principles`, `@eventstorming-implementation`, `@gwt-test-generation`

#### 2.2 BC Spec에서 Rules 참조 시 @mention 형식 사용
- 경로 대신 mention 형식으로 변경
- 예: `.cursor/rules/ddd-principles.mdc` → `@ddd-principles`
- Tip 메시지 추가: "Use @mention feature in Cursor to reference these rules"

#### 2.3 Tech Stack Rules의 Reference Files 섹션 강화
- 다른 rules를 @mention 형식으로 참조
- 예: `@ddd-principles`, `@eventstorming-implementation`, `@gwt-test-generation`

#### 2.4 세분화된 Rules에 "Related Rules" 섹션 추가
- **`@ddd-principles`**: `@eventstorming-implementation`, `@gwt-test-generation`, `@{{framework}}` 참조
- **`@gwt-test-generation`**: `@ddd-principles`, `@eventstorming-implementation`, `@{{framework}}` 참조
- **`@eventstorming-implementation`**: `@ddd-principles`, `@gwt-test-generation`, `@{{framework}}` 참조

### 적용 위치
- `api/features/prd_generation/prd_artifact_generation.py`
  - `generate_main_prd()`: PRD에서 @mention 형식 사용
  - `generate_bc_spec()`: BC spec에서 @mention 형식 사용
  - `generate_cursor_tech_stack_rule()`: Tech stack rules에서 @mention 형식 사용
  - `generate_ddd_principles_rule()`: Related Rules 섹션 추가
  - `generate_gwt_test_generation_rule()`: Related Rules 섹션 추가
  - `generate_eventstorming_implementation_rule()`: Related Rules 섹션 추가

---

## 3. 메인 PRD에서 Spec과 Rules 참조 명확화

### 개선 내용

#### 3.1 PRD 시작 부분에 "CRITICAL: Before Starting Implementation" 섹션 추가
- "진행해" 요청 시 반드시 해야 할 일들을 명확히 나열
- BC spec 파일을 먼저 읽도록 강조
- Cursor rules를 @mention으로 참조하도록 명시
- UI wireframe, Database, API, 서비스별 페이지 참조 명시

#### 3.2 Implementation Workflow 섹션 강화
- 각 요소의 구현 매핑 명시:
  - Command → REST API endpoints
  - Event → Message publishing
  - ReadModel → Query API endpoints
  - UI Wireframes → Frontend components/pages
  - Database schema requirements

#### 3.3 Development Guidelines에 UI Wireframe Implementation 섹션 추가
- BC spec의 UI wireframe 참조 방법
- Wireframe template 사용법
- Command/ReadModel에 연결된 UI 구현
- 서비스별 페이지 생성 가이드

#### 3.4 Implementation Checklist 강화
- BC spec 읽기와 Cursor rules 참조를 최우선으로 배치
- Database schema 설정 항목 추가
- UI wireframe 구현 항목 추가
- 서비스 페이지 생성 항목 추가

#### 3.5 File Reference Quick Guide 강화
- "진행해" 요청 시 파일 참조 순서 명시
- 각 파일의 역할과 포함 내용 명시
- UI wireframe, Database schema 포함 내용 강조

### 적용 위치
- `api/features/prd_generation/prd_artifact_generation.py`
  - `generate_main_prd()`: 전체 PRD 구조 강화

---

## 4. UI Wireframe, Database, API, 서비스별 페이지 구현 가이드

### 개선 내용

#### 4.1 UI Wireframe Implementation 섹션 추가
- **Reference BC Spec**: `specs/{{bc_name}}_spec.md`에서 UI wireframes 섹션 확인
- **Wireframe Templates**: `template` 필드 (HTML wireframes) 사용
- **Attached Commands**: Command에 연결된 UI → Form components 생성
- **Attached ReadModels**: ReadModel에 연결된 UI → Display/list components 생성
- **Frontend PRD**: `Frontend-PRD.md` 참조
- **Service Pages**: Command 페이지 (forms), ReadModel 페이지 (displays) 생성

#### 4.2 Database Schema Implementation 가이드
- Aggregate properties를 기반으로 database schema 생성
- `isKey`, `isForeignKey` 활용
- Database별 구체적 가이드라인 참조

#### 4.3 API Endpoint Implementation 가이드
- **Commands**: `POST /api/{{bc_name}}/{{command-name}}`
- **ReadModels**: `GET /api/{{bc_name}}/{{readmodel-name}}`
- Response codes, pagination, filtering 등 명시

### 적용 위치
- `api/features/prd_generation/prd_artifact_generation.py`
  - `generate_main_prd()`: Development Guidelines 섹션에 UI Wireframe Implementation 추가
  - `generate_bc_spec()`: UI wireframe template 필드 포함

---

## 5. Event 송수신 및 서비스별 의존성 관리

### 개선 내용

#### 5.1 Service Independence & Dependencies 섹션 추가
- **Independent Deployment**: 각 BC는 독립적으로 배포 가능
- **Event-Based Dependencies**: 직접 서비스 호출 없이 event contract만 의존
- **Backward Compatibility**: Event schema 변경 시 하위 호환성 유지
- **No Direct Service Calls**: BCs는 다른 BCs의 API를 직접 호출하지 않음
- **Dependency Direction**:
  - Event Publisher BC: Consumer에 대한 의존성 없음 (publish and forget)
  - Event Consumer BC (Policy): Event contract에만 의존, 서비스 구현에 의존하지 않음

#### 5.2 Event Publishing 강화
- **Schema Versioning**: Semantic versioning (v1.0.0, v1.1.0, v2.0.0)
- **Breaking Changes**: 새 버전 생성 시 이전 버전 유지
- **Independence**: Publisher BC는 Consumer BC에 의존하지 않음

#### 5.3 Event Consumption 강화
- **Reference Publisher BC Spec**: 다른 BC의 spec 파일 참조
- **Schema Contract**: Publisher BC spec의 정확한 event schema 사용
- **Version Support**: 여러 event 버전 지원 (backward compatibility)
- **Idempotency**: Event ID 추적 및 중복 처리 방지
- **Independence**: Consumer는 event contract에만 의존, publisher 서비스에 의존하지 않음

#### 5.4 Policy Implementation 강화
- **Service Dependencies**:
  - 직접 의존성 없음: Policy BC는 target BC 서비스에 의존하지 않음
  - Event Contract Dependency: Event contract(schema)에만 의존
  - 독립 배포: Policy BC는 독립적으로 배포/업데이트 가능
  - Target BC 가용성: Target BC가 일시적으로 불가능해도 처리 가능 (메시징 플랫폼에 큐잉)
- **Error Handling**:
  - Schema Mismatch: 스키마 불일치 시 DLQ로 전송
  - Version Mismatch: 여러 버전 지원 또는 미지원 버전 거부
  - Transient vs Permanent Failures: 일시적 실패는 재시도, 영구 실패는 DLQ

#### 5.5 Cross-BC Integration 체크리스트 강화
- Event contract 검증 (publisher/consumer BC spec 확인)
- Idempotency 구현
- Dead-letter queue 설정
- 서비스 독립성 검증
- Event contract 문서화

### 적용 위치
- `api/features/prd_generation/prd_artifact_generation.py`
  - `generate_main_prd()`: Service Independence & Dependencies 섹션 추가
  - `generate_main_prd()`: Event Publishing/Consumption 강화
  - `generate_main_prd()`: Policy Implementation 강화
  - `generate_main_prd()`: Cross-BC Integration 체크리스트 강화

---

## 6. 세분화된 Cursor Rules 구조

### 개선 내용

#### 6.1 Rules 세분화
기존의 단일 `.cursorrules` 파일을 다음과 같이 세분화:
- **`.cursorrules`**: Global DDD principles (always applied)
- **`.cursor/rules/ddd-principles.mdc`**: DDD patterns (always applied)
- **`.cursor/rules/eventstorming-implementation.mdc`**: Sticker-to-code mapping
- **`.cursor/rules/gwt-test-generation.mdc`**: GWT test patterns
- **`.cursor/rules/{{framework}}.mdc`**: Tech stack specific guidelines
- **`.cursor/rules/{{frontend_framework}}.mdc`**: Frontend framework guidelines (if applicable)

#### 6.2 Rules 간 상호 참조
- 각 rule 파일에 "Related Rules" 섹션 추가
- @mention 형식으로 다른 rules 참조

### 적용 위치
- `api/features/prd_generation/prd_artifact_generation.py`
  - `generate_ddd_principles_rule()`: DDD principles rule 생성
  - `generate_eventstorming_implementation_rule()`: Event Storming implementation rule 생성
  - `generate_gwt_test_generation_rule()`: GWT test generation rule 생성
  - `generate_cursor_tech_stack_rule()`: Tech stack specific rule 생성
  - `generate_frontend_cursor_rule()`: Frontend framework rule 생성

---

## 7. Frontend PRD 및 Rules 생성

### 개선 내용

#### 7.1 Frontend PRD 생성 (`Frontend-PRD.md`)
- UI wireframes 기반 frontend 구현 가이드
- API integration patterns
- State management guidelines
- Component/page 구조

#### 7.2 Frontend Cursor Rules 생성
- Frontend framework별 rule 파일 생성
- `globs` 패턴으로 frontend 파일에만 적용
- Backend API integration 가이드

### 적용 위치
- `api/features/prd_generation/prd_artifact_generation.py`
  - `generate_frontend_prd()`: Frontend PRD 생성
  - `generate_frontend_cursor_rule()`: Frontend Cursor rule 생성
- `api/features/prd_generation/routes/prd_export.py`
  - Frontend PRD 및 rules 조건부 생성 (Cursor 선택 시)

---

## 8. 조건부 파일 생성

### 개선 내용

#### 8.1 AI Assistant별 조건부 생성
- **Cursor 선택 시**:
  - `.cursorrules`
  - `.cursor/rules/*.mdc` (세분화된 rules)
  - `Frontend-PRD.md` (frontend 포함 시)
  - `.cursor/rules/{{frontend_framework}}.mdc` (frontend 포함 시)
- **Claude 선택 시**:
  - `CLAUDE.md`
  - `.claude/agents/{{bc_name}}_agent.md`

#### 8.2 Frontend 조건부 생성
- `include_frontend` 옵션에 따라 frontend 관련 파일 생성
- Cursor 선택 시에만 frontend PRD 및 rules 생성

### 적용 위치
- `api/features/prd_generation/routes/prd_export.py`
  - `download_prd_zip()`: 조건부 파일 생성 로직

---

## 9. BC Spec 강화

### 개선 내용

#### 9.1 UI Wireframe Template 필드 포함
- Neo4j에서 `template` 필드 조회 추가
- BC spec에 wireframe template 표시

#### 9.2 Cursor Rules 참조 명확화
- BC spec에서 관련 Cursor rules를 @mention 형식으로 참조
- 각 rule의 역할 명시

### 적용 위치
- `api/features/prd_generation/prd_model_data.py`
  - `fetch_bc_data()`: UI node의 `template` 필드 조회 추가
- `api/features/prd_generation/prd_artifact_generation.py`
  - `generate_bc_spec()`: UI wireframe template 표시, Cursor rules 참조 강화

---

## 10. 향후 Claude Agent 적용 시 고려사항

### 10.1 BC별 Skills 구조
Claude Agent 기반에서도 동일한 구조를 BC별 skills로 적용:
- **Global Skills**: DDD principles, Event Storming patterns
- **Tech Stack Skills**: Framework-specific guidelines
- **BC-specific Skills**: BC별 구현 가이드

### 10.2 Skills 간 상호 참조
- Cursor의 @mention과 유사하게 skills 간 참조 구조 필요
- Related Skills 섹션 추가

### 10.3 Event 송수신 및 의존성 관리
- Service Independence & Dependencies 가이드
- Event contract 버전 관리
- Cross-BC communication patterns

### 10.4 Database, UI, API 가이드
- Database별 구체적 가이드라인
- UI wireframe 구현 가이드
- API endpoint 구현 가이드

### 10.5 파일 참조 명확화
- BC spec 파일 참조 강조
- Skills 참조 방법 명시
- "진행해" 요청 시 참조 순서 명확화

---

## 참고 파일

- `api/features/prd_generation/prd_artifact_generation.py`: 주요 개선 사항이 적용된 파일
- `api/features/prd_generation/prd_model_data.py`: Neo4j 데이터 조회 개선
- `api/features/prd_generation/routes/prd_export.py`: 조건부 파일 생성 로직
- `api/features/prd_generation/prd_api_contracts.py`: API contracts (AIAssistant, FrontendFramework 등)

---

## 변경 이력

- 2024-XX-XX: Database 관련 지시사항 강화
- 2024-XX-XX: Cursor @mention 기능 활용
- 2024-XX-XX: 메인 PRD에서 Spec과 Rules 참조 명확화
- 2024-XX-XX: UI Wireframe, Database, API, 서비스별 페이지 구현 가이드
- 2024-XX-XX: Event 송수신 및 서비스별 의존성 관리
