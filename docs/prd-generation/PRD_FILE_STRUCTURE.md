# PRD 생성 파일 구조 및 목적

> Event Storming 모델 기반으로 생성되는 PRD 파일들의 구성, 목적, 내용을 정리한 문서

## 개요

이 문서는 Event Storming 모델에서 PRD를 생성할 때, Cursor와 Claude 각 AI Assistant에 따라 생성되는 파일들의 구조, 목적, 그리고 포함된 내용을 설명합니다.

---

## 공통 파일 (Cursor & Claude 공통)

### 1. `PRD.md` - 메인 Product Requirements Document

**목적**: 전체 시스템의 아키텍처, 원칙, 가이드라인 제공

**포함 내용**:
- 프로젝트 개요 및 기술 스택
- Bounded Contexts 목록 및 통계
- DDD 원칙 및 아키텍처 가이드라인
- Event-Driven Architecture 패턴
- Cross-BC 통신 규칙
- Service Independence & Dependencies
- AI Assistant별 설정 파일 참조 방법
- Implementation Workflow
- Database Guidelines
- UI Wireframe Implementation 가이드 (frontend 포함 시)

**역할**: 
- 전체 시스템의 고수준 아키텍처 이해
- BC별 구현 전 시작점
- 다른 파일들의 참조 지점

---

### 2. `specs/{bc_name}_spec.md` - BC별 상세 스펙

**목적**: 각 Bounded Context의 완전한 요구사항 정의 (WHAT을 구현할지)

**포함 내용**:
- BC 개요 및 설명
- **Aggregates**: 모든 properties, types, invariants, enumerations, value objects
- **Commands**: inputSchema, 모든 properties, actor, category, description
- **Events**: schema, 모든 properties, version, description
- **ReadModels**: 모든 properties, provisioningType, actor, isMultipleResult
- **Policies**: triggerEvent, invokeCommand, cross-BC 관계
- **UI Wireframes**: HTML templates, attached Commands/ReadModels, descriptions
- **GWT Test Cases**: Given/When/Then 시나리오, field values
- Implementation Notes
- Related Files (AI Assistant별 rules/skills 참조)

**역할**:
- 구현 시 필수 참조 문서 (MUST READ FIRST)
- 모든 데이터와 스키마의 단일 소스
- BC별 완전한 요구사항 정의

---

### 3. `Frontend-PRD.md` - Frontend Product Requirements Document

**조건**: `include_frontend == true`일 때만 생성

**목적**: Frontend 아키텍처, 전략, UI 개요 제공 (WHAT/WHY)

**포함 내용**:
- Frontend 기술 스택
- **UI Wireframes Overview**: 모든 BC의 UI 목록
- **Query Screens (ReadModels)**: 모든 ReadModel 목록
- **Frontend Implementation Strategy**: 
  - Phase 1: Main Landing Page (시작점)
  - Phase 2: BC Features 추가 (점진적)
  - Phase 3: Integration & Polish
- UI/UX Requirements
- Wireframe Implementation Overview
- Reference Files (Backend PRD, BC Specs, Frontend Tech Stack Rules/Skills)

**역할**:
- Frontend 구현 전략 및 아키텍처 가이드
- Backend PRD와 함께 읽어야 하는 문서
- 전체 UI 목록 제공

**참고**: 기술적 구현 패턴(HOW)은 Frontend Tech Stack Rules/Skills 참조

---

### 4. `README.md` - 프로젝트 개요

**목적**: 프로젝트 기본 정보 제공

**포함 내용**:
- 프로젝트 이름
- Bounded Contexts 목록 및 설명

---

### 5. `docker-compose.yml` & `Dockerfile` (선택적)

**조건**: `include_docker == true`일 때만 생성

**목적**: Docker 기반 개발 환경 설정

**포함 내용**:
- Database 서비스 설정 (PostgreSQL, MySQL, MongoDB 등)
- 애플리케이션 서비스 설정
- 네트워크 및 볼륨 설정

---

## Cursor 전용 파일

### 1. `.cursorrules` - 전역 Cursor 규칙

**목적**: 프로젝트 전체에 적용되는 DDD 원칙 및 코딩 표준

**포함 내용**:
- DDD 네이밍 규칙 (Commands, Events, Aggregates, ReadModels)
- Bounded Context 경계 원칙
- Aggregate 규칙
- Command-Event 패턴
- CQRS 패턴
- Technology Stack Standards
- Database Guidelines
- Code Quality Standards

**참조 방식**: `@.cursorrules` (mention)

---

### 2. `.cursor/rules/ddd-principles.mdc` - DDD 원칙 규칙

**목적**: DDD 패턴 및 원칙 (항상 적용)

**포함 내용**:
- Naming Conventions
- Bounded Context Boundaries
- Aggregate Rules
- Command-Event Pattern
- CQRS Pattern
- Important Reminders
- Related Rules 참조

**메타데이터**:
```yaml
alwaysApply: true
description: Domain-Driven Design (DDD) principles and patterns
```

**참조 방식**: `@ddd-principles` (mention)

---

### 3. `.cursor/rules/eventstorming-implementation.mdc` - Event Storming 구현 규칙

**목적**: Event Storming 스티커를 코드로 매핑하는 패턴

**포함 내용**:
- Command Implementation (Handler, REST API Endpoints)
- Event Implementation (Class, Publishing, Consumption)
- Aggregate Implementation
- ReadModel Implementation (Projection, Query API Endpoints)
- Policy Implementation (Event Listener, Command Invocation)
- UI Wireframe Implementation
- Complete UI Implementation Checklist

**메타데이터**:
```yaml
alwaysApply: false
description: Event Storming sticker-to-code implementation patterns
globs: **/*
```

**참조 방식**: `@eventstorming-implementation` (mention)

---

### 4. `.cursor/rules/gwt-test-generation.mdc` - GWT 테스트 생성 규칙

**목적**: GWT (Given/When/Then) 테스트 작성 가이드

**포함 내용**:
- GWT Test Pattern 구조
- Test Coverage (Commands, Aggregates, Events, Policies, ReadModels)
- Framework-Specific Patterns (Spring Boot, FastAPI, NestJS, Go)
- Best Practices
- Test Data (Fixtures, Builders, Factories)

**메타데이터**:
```yaml
alwaysApply: false
description: GWT (Given/When/Then) test generation guidelines
globs: **/*Test*.java,**/*Test*.kt,**/*test*.py,**/*test*.ts,**/*test*.go,**/*spec*.ts
```

**참조 방식**: `@gwt-test-generation` (mention)

---

### 5. `.cursor/rules/{framework}.mdc` - 기술 스택 규칙

**예시**: `spring-boot.mdc`, `fastapi.mdc`, `nestjs.mdc`

**목적**: 특정 기술 스택의 구현 가이드라인 (HOW)

**포함 내용**:
- Technology Stack 정보
- Code Structure
- Implementation Guidelines:
  - Commands (Handler, Validation, Transaction)
  - Database & Persistence (ORM, Connection Pooling, Migration)
  - Events (Publishing, Consumption)
  - ReadModels (Projection, Query)
  - REST Controllers
  - Testing
- Database별 구체적 가이드라인 (PostgreSQL, MySQL, MongoDB, H2)
- Complete Implementation Checklist
- Reference Files

**메타데이터**:
```yaml
alwaysApply: false
description: {framework} ({language}) implementation guidelines
globs: **/*.{extensions}
```

**참조 방식**: `@{framework}` (예: `@spring-boot`, `@fastapi`)

---

### 6. `.cursor/rules/{frontend_framework}.mdc` - Frontend 프레임워크 규칙

**조건**: `include_frontend == true`일 때만 생성

**예시**: `vue.mdc`, `react.mdc`

**목적**: Frontend 프레임워크의 기술적 구현 패턴 (HOW)

**포함 내용**:
- Frontend Framework 정보
- Code Structure (디렉토리 구조)
- Implementation Guidelines:
  - Component Structure
  - API Integration 패턴
  - State Management 패턴
  - Routing
  - Styling
- Complete Implementation Checklist:
  - Commands 구현 체크리스트
  - ReadModels 구현 체크리스트
  - UI Wireframes 구현 체크리스트
- Reference Files (Frontend-PRD.md, Backend PRD, BC Specs)

**메타데이터**:
```yaml
alwaysApply: false
description: {frontend_fw} frontend implementation guidelines
globs: frontend/**/*.{extensions},src/**/*.{extensions}
```

**참조 방식**: `@{frontend_framework}` (예: `@vue`, `@react`)

**참고**: Frontend-PRD.md는 아키텍처/전략(WHAT/WHY), 이 파일은 기술적 구현 패턴(HOW)

---

## Claude 전용 파일

### 1. `CLAUDE.md` - Claude AI 컨텍스트

**목적**: Claude AI가 프로젝트 컨텍스트를 이해하는 데 사용

**포함 내용**:
- 프로젝트 기본 정보 (이름, 배포, 스택, 메시징, 데이터베이스)
- Bounded Contexts 목록
- Reference Files (Main PRD, BC Specs, AI Assistant Guides)

---

### 2. `.claude/skills/ddd-principles.md` - DDD 원칙 Skill

**목적**: DDD 패턴 및 원칙 (항상 참조)

**포함 내용**:
- Naming Conventions
- Bounded Context Boundaries
- Aggregate Rules
- Command-Event Pattern
- CQRS Pattern
- Important Reminders
- Related Skills 참조

**참조 방식**: `.claude/skills/ddd-principles.md` (파일 경로)

---

### 3. `.claude/skills/eventstorming-implementation.md` - Event Storming 구현 Skill

**목적**: Event Storming 스티커를 코드로 매핑하는 패턴

**포함 내용**:
- Command Implementation
- Event Implementation
- Aggregate Implementation
- ReadModel Implementation
- Policy Implementation (Service Independence & Dependencies 포함)
- UI Wireframe Implementation
- Complete UI Implementation Checklist

**참조 방식**: `.claude/skills/eventstorming-implementation.md` (파일 경로)

---

### 4. `.claude/skills/gwt-test-generation.md` - GWT 테스트 생성 Skill

**목적**: GWT (Given/When/Then) 테스트 작성 가이드

**포함 내용**:
- GWT Test Pattern 구조
- Test Coverage
- Framework-Specific Patterns
- Best Practices
- Test Data

**참조 방식**: `.claude/skills/gwt-test-generation.md` (파일 경로)

---

### 5. `.claude/skills/{framework}.md` - 기술 스택 Skill

**예시**: `spring-boot.md`, `fastapi.md`, `nestjs.md`

**목적**: 특정 기술 스택의 구현 가이드라인 (HOW)

**포함 내용**:
- Technology Stack 정보
- Code Structure
- Implementation Guidelines (Commands, Database, Events, ReadModels, REST Controllers, Testing)
- Database & Persistence (Database별 구체적 가이드라인)
- Complete Implementation Checklist
- Reference Files

**참조 방식**: `.claude/skills/{framework}.md` (파일 경로)

---

### 6. `.claude/skills/{frontend_framework}.md` - Frontend 프레임워크 Skill

**조건**: `include_frontend == true`일 때만 생성

**예시**: `vue.md`, `react.md`

**목적**: Frontend 프레임워크의 기술적 구현 패턴 (HOW)

**포함 내용**:
- Frontend Framework 정보
- Code Structure
- Implementation Guidelines (Component, API Integration, State Management)
- Complete Frontend Implementation Checklist
- Related Skills 참조

**참조 방식**: `.claude/skills/{frontend_framework}.md` (파일 경로)

**참고**: Frontend-PRD.md는 아키텍처/전략(WHAT/WHY), 이 파일은 기술적 구현 패턴(HOW)

---

### 7. `.claude/agents/{bc_name}_agent.md` - BC별 Agent 설정

**목적**: BC별 구현 가이드 및 참조 방법 (HOW)

**포함 내용**:
- Scope & Boundaries (BC 범위, 디렉토리)
- **Required Skills**: 참조할 skills 파일 목록
- **Key Components**: 
  - Aggregates 개수 및 이름
  - Commands 개수 및 구현 가이드
  - Events 개수 및 구현 가이드
  - ReadModels 개수 및 이름
  - Policies 개수 및 구현 가이드
- BC-Specific Implementation Notes
- BC-Specific Constraints
- Reference Files (Spec, Skills, Main PRD, CLAUDE.md)
- Getting Started (구현 순서)

**역할**:
- BC별 구현 로드맵
- Skills 참조 방법 안내
- BC별 특화 제약사항

**참고**: 
- Spec 파일은 데이터 정의(WHAT), Agent 파일은 구현 가이드(HOW)
- 공통 구현 패턴은 Skills에서 참조

---

## 파일 구조 비교

### Cursor 구조

```
프로젝트 루트/
├── PRD.md                                    # 메인 PRD
├── Frontend-PRD.md                           # Frontend PRD (frontend 포함 시)
├── .cursorrules                              # 전역 규칙
├── .cursor/
│   └── rules/
│       ├── ddd-principles.mdc                # DDD 원칙 (alwaysApply: true)
│       ├── eventstorming-implementation.mdc  # Event Storming 구현
│       ├── gwt-test-generation.mdc           # GWT 테스트
│       ├── {framework}.mdc                   # 기술 스택 규칙
│       └── {frontend_framework}.mdc         # Frontend 규칙 (frontend 포함 시)
├── specs/
│   └── {bc_name}_spec.md                     # BC별 스펙
├── README.md
├── docker-compose.yml                        # (docker 포함 시)
└── Dockerfile                                # (docker 포함 시)
```

### Claude 구조

```
프로젝트 루트/
├── PRD.md                                    # 메인 PRD
├── Frontend-PRD.md                           # Frontend PRD (frontend 포함 시)
├── CLAUDE.md                                 # Claude 컨텍스트
├── .claude/
│   ├── skills/
│   │   ├── ddd-principles.md                # DDD 원칙
│   │   ├── eventstorming-implementation.md   # Event Storming 구현
│   │   ├── gwt-test-generation.md            # GWT 테스트
│   │   ├── {framework}.md                    # 기술 스택 Skill
│   │   └── {frontend_framework}.md           # Frontend Skill (frontend 포함 시)
│   └── agents/
│       └── {bc_name}_agent.md                # BC별 Agent
├── specs/
│   └── {bc_name}_spec.md                     # BC별 스펙
├── README.md
├── docker-compose.yml                        # (docker 포함 시)
└── Dockerfile                                # (docker 포함 시)
```

---

## 역할 분리 요약

### 1. 아키텍처 & 전략 (WHAT/WHY)

| 파일 | 목적 |
|------|------|
| `PRD.md` | 전체 시스템 아키텍처 및 원칙 |
| `Frontend-PRD.md` | Frontend 아키텍처, 전략, UI 개요 |

### 2. 데이터 정의 (WHAT)

| 파일 | 목적 |
|------|------|
| `specs/{bc_name}_spec.md` | BC별 완전한 요구사항 (properties, schemas, templates) |

### 3. 구현 가이드 (HOW)

| 파일 | 목적 |
|------|------|
| `.cursorrules` / `.claude/skills/*.md` | 공통 구현 패턴 (DDD, Event Storming, Tech Stack) |
| `.cursor/rules/{framework}.mdc` / `.claude/skills/{framework}.md` | 기술 스택별 구현 패턴 |
| `.cursor/rules/{frontend_framework}.mdc` / `.claude/skills/{frontend_framework}.md` | Frontend 기술적 구현 패턴 |
| `.claude/agents/{bc_name}_agent.md` | BC별 구현 가이드 및 참조 방법 |

---

## 참조 방식 비교

### Cursor

- **@mention 형식**: `@ddd-principles`, `@spring-boot`, `@vue`
- **자동 적용**: `alwaysApply: true` 설정 시 자동 적용
- **파일 타입 필터링**: `globs` 패턴으로 특정 파일에만 적용

### Claude

- **파일 경로 명시**: `.claude/skills/ddd-principles.md`
- **명시적 로드**: Agent 파일에서 필요한 skills 명시
- **단순한 구조**: 메타데이터 없이 Markdown 파일

---

## 구현 워크플로우

### Cursor

1. `PRD.md` 읽기 → 전체 아키텍처 이해
2. `specs/{bc_name}_spec.md` 읽기 → BC별 요구사항 확인
3. `@.cursorrules` 참조 → 전역 규칙 확인
4. `@ddd-principles`, `@eventstorming-implementation` 참조 → 공통 패턴 확인
5. `@{framework}` 참조 → 기술 스택 패턴 확인
6. `Frontend-PRD.md` + `@vue` 참조 (frontend 포함 시)

### Claude

1. `PRD.md` 읽기 → 전체 아키텍처 이해
2. `.claude/agents/{bc_name}_agent.md` 읽기 → BC별 구현 가이드 확인
3. Required Skills 로드 → `.claude/skills/*.md` 파일들 로드
4. `specs/{bc_name}_spec.md` 읽기 → BC별 요구사항 확인
5. `Frontend-PRD.md` 읽기 (frontend 포함 시)

---

## 주요 차이점

| 항목 | Cursor | Claude |
|------|--------|--------|
| **참조 방식** | @mention (`@ddd-principles`) | 파일 경로 (`.claude/skills/ddd-principles.md`) |
| **자동 적용** | `alwaysApply: true` 가능 | 명시적 로드 필요 |
| **BC별 가이드** | 없음 (spec에서 rules 참조) | `.claude/agents/{bc_name}_agent.md` |
| **전역 규칙** | `.cursorrules` | 없음 (skills로 통합) |
| **메타데이터** | frontmatter (alwaysApply, globs) | 없음 |

---

## 파일 생성 조건

### 공통 조건

- `PRD.md`: 항상 생성
- `README.md`: 항상 생성
- `specs/{bc_name}_spec.md`: BC 개수만큼 생성

### 조건부 생성

- `Frontend-PRD.md`: `include_frontend == true` && `frontend_framework != null`
- `docker-compose.yml`, `Dockerfile`: `include_docker == true`

### AI Assistant별

- **Cursor**: `.cursorrules`, `.cursor/rules/*.mdc` 파일들
- **Claude**: `CLAUDE.md`, `.claude/skills/*.md`, `.claude/agents/*.md` 파일들

---

## 참고

- 각 파일의 상세 내용은 실제 생성되는 파일을 참조하세요.
- 파일 구조는 Event Storming 모델의 BC 구조에 따라 동적으로 생성됩니다.
- 기술 스택 선택에 따라 생성되는 파일 내용이 달라집니다.
