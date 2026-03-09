# Claude Code Skills 개선 계획

> **목적**: Cursor 기반에서 개선된 rules 구조를 Claude Code의 skills 구조로 동일하게 적용

## 현재 상황 분석

### Cursor 기반 구조 (개선 완료)
```
.cursorrules                          # Global DDD principles
.cursor/rules/
  ├── ddd-principles.mdc              # DDD patterns (always applied)
  ├── eventstorming-implementation.mdc # Sticker-to-code mapping
  ├── gwt-test-generation.mdc         # GWT test patterns
  ├── {framework}.mdc                 # Tech stack specific (Spring Boot, FastAPI, etc.)
  └── {frontend_framework}.mdc        # Frontend specific (Vue, React) - if applicable

specs/
  └── {bc_name}_spec.md               # BC별 상세 스펙 (rules를 @mention으로 참조)
```

**참조 방식:**
- BC spec에서: `@ddd-principles`, `@eventstorming-implementation`, `@{framework}` 등으로 참조
- Rules 간 상호 참조: "Related Rules" 섹션에서 @mention 사용

### Claude 기반 구조 (현재 - 개선 필요)
```
.claude/
  ├── agents/
  │   └── {bc_name}_agent.md          # BC별 agent (모든 내용이 포함됨)
  └── (skills 디렉토리 없음!)

CLAUDE.md                              # 프로젝트 컨텍스트
specs/
  └── {bc_name}_spec.md               # BC별 상세 스펙
```

**문제점:**
1. ❌ 공통 skills가 없음 - 각 agent에 중복된 내용 포함
2. ❌ Skills 간 상호 참조 구조 없음
3. ❌ BC spec에서 skills 참조 방법이 명확하지 않음
4. ❌ Cursor에서 개선된 내용(database guidelines, UI wireframe, event handling 등)이 Claude에 반영되지 않음

---

## 개선 방향

### 1. Skills 구조 생성 (Cursor rules와 동일한 세분화)

```
.claude/
  ├── agents/
  │   └── {bc_name}_agent.md          # BC별 agent (skills 참조)
  └── skills/
      ├── ddd-principles.md           # DDD patterns (공통)
      ├── eventstorming-implementation.md # Sticker-to-code mapping (공통)
      ├── gwt-test-generation.md      # GWT test patterns (공통)
      ├── {framework}.md             # Tech stack specific (Spring Boot, FastAPI, etc.)
      └── {frontend_framework}.md    # Frontend specific (Vue, React) - if applicable
```

### 2. Skills 생성 함수 추가

Cursor의 rules 생성 함수들을 참고하여 Claude skills 생성 함수 추가:

```python
def generate_claude_skill_ddd_principles(config: TechStackConfig) -> str:
    """DDD principles skill - Cursor의 generate_ddd_principles_rule과 동일한 내용"""
    pass

def generate_claude_skill_eventstorming_implementation(config: TechStackConfig) -> str:
    """Event Storming implementation skill - Cursor의 generate_eventstorming_implementation_rule과 동일한 내용"""
    pass

def generate_claude_skill_gwt_test_generation(config: TechStackConfig) -> str:
    """GWT test generation skill - Cursor의 generate_gwt_test_generation_rule과 동일한 내용"""
    pass

def generate_claude_skill_tech_stack(config: TechStackConfig) -> str:
    """Tech stack specific skill - Cursor의 generate_cursor_tech_stack_rule과 동일한 내용"""
    pass

def generate_claude_skill_frontend(config: TechStackConfig) -> str:
    """Frontend framework skill - Cursor의 generate_frontend_cursor_rule과 동일한 내용"""
    pass
```

### 3. Agent 파일 개선 (Skills 참조)

BC별 agent 파일에서:
- 공통 내용 제거 (skills로 이동)
- Skills 참조 방법 명시
- BC별 특화 내용만 포함

**Before (현재):**
```markdown
# Agent Configuration: Order Management

## Implementation Guidelines
- DDD principles...
- Event Storming patterns...
- Tech stack guidelines...
- (모든 내용이 agent에 포함됨)
```

**After (개선):**
```markdown
# Agent Configuration: Order Management

## Required Skills
Before implementing, ensure you have loaded these skills:
- `.claude/skills/ddd-principles.md` - DDD patterns and BC boundaries
- `.claude/skills/eventstorming-implementation.md` - Sticker-to-code mapping
- `.claude/skills/gwt-test-generation.md` - Test patterns
- `.claude/skills/{framework}.md` - {framework} implementation guidelines
- `.claude/skills/{frontend_framework}.md` - Frontend guidelines (if applicable)

## BC-Specific Implementation
(BC별 특화 내용만 포함)
```

### 4. BC Spec에서 Skills 참조 명확화

BC spec 파일에서 Claude skills 참조 방법 명시:

```markdown
# Order Management Bounded Context Specification

> **Note**: For implementation guidance, refer to:
> - **Skills**: `.claude/skills/ddd-principles.md`, `.claude/skills/eventstorming-implementation.md`, `.claude/skills/{framework}.md`
> - **Agent**: `.claude/agents/order_management_agent.md`
```

### 5. PRD에서 Skills 구조 명시

메인 PRD에서 Claude Code 사용 시 skills 구조를 명확히 안내:

```markdown
### AI Assistant Configuration Files

**Using Claude Code**:
- **`.claude/skills/`**: Common implementation skills (DDD, Event Storming, Tech Stack)
  - `ddd-principles.md` - DDD patterns (always reference)
  - `eventstorming-implementation.md` - Sticker-to-code mapping
  - `gwt-test-generation.md` - Test patterns
  - `{framework}.md` - Tech stack specific guidelines
  - `{frontend_framework}.md` - Frontend guidelines (if applicable)
- **`.claude/agents/{bc_name}_agent.md`**: BC-specific agent configuration
```

---

## 구현 계획

### Phase 1: Skills 생성 함수 추가
1. `generate_claude_skill_ddd_principles()` - Cursor의 `generate_ddd_principles_rule()` 내용 기반
2. `generate_claude_skill_eventstorming_implementation()` - Cursor의 `generate_eventstorming_implementation_rule()` 내용 기반
3. `generate_claude_skill_gwt_test_generation()` - Cursor의 `generate_gwt_test_generation_rule()` 내용 기반
4. `generate_claude_skill_tech_stack()` - Cursor의 `generate_cursor_tech_stack_rule()` 내용 기반
5. `generate_claude_skill_frontend()` - Cursor의 `generate_frontend_cursor_rule()` 내용 기반 (if applicable)

### Phase 2: Agent 파일 개선
1. `generate_agent_config()` 함수 수정
   - 공통 내용 제거
   - Skills 참조 섹션 추가
   - BC별 특화 내용만 포함

### Phase 3: 파일 생성 로직 업데이트
1. `routes/prd_export.py`의 `download_prd_zip()` 함수 수정
   - Skills 파일 생성 추가
   - `files_to_generate` 리스트에 skills 추가

### Phase 4: PRD 및 Spec 파일 업데이트
1. `generate_main_prd()` - Claude Code 사용 시 skills 구조 명시
2. `generate_bc_spec()` - Claude skills 참조 방법 명시
3. `generate_claude_md()` - Skills 참조 추가

---

## Cursor vs Claude 구조 비교

| 항목 | Cursor | Claude (개선 후) |
|------|--------|------------------|
| **Global Rules** | `.cursorrules` | (없음 - skills로 통합) |
| **DDD Principles** | `.cursor/rules/ddd-principles.mdc` | `.claude/skills/ddd-principles.md` |
| **Event Storming** | `.cursor/rules/eventstorming-implementation.mdc` | `.claude/skills/eventstorming-implementation.md` |
| **GWT Tests** | `.cursor/rules/gwt-test-generation.mdc` | `.claude/skills/gwt-test-generation.md` |
| **Tech Stack** | `.cursor/rules/{framework}.mdc` | `.claude/skills/{framework}.md` |
| **Frontend** | `.cursor/rules/{frontend_framework}.mdc` | `.claude/skills/{frontend_framework}.md` |
| **BC별** | (없음 - spec에서 참조) | `.claude/agents/{bc_name}_agent.md` |
| **참조 방식** | `@mention` (예: `@ddd-principles`) | 파일 경로 명시 (예: `.claude/skills/ddd-principles.md`) |

---

## 주요 개선 사항 (Cursor에서 Claude로 이전)

### 1. Database Guidelines
- ✅ Database별 구체적 가이드라인 (PostgreSQL, MySQL, MongoDB, H2)
- ✅ Connection pooling, indexing, migration 전략
- **적용 위치**: Tech stack skill에 포함

### 2. UI Wireframe Implementation
- ✅ BC spec의 UI wireframe template 참조
- ✅ Command/ReadModel에 연결된 UI 구현 가이드
- **적용 위치**: Event Storming implementation skill + Frontend skill

### 3. Event 송수신 및 의존성 관리
- ✅ Service Independence & Dependencies
- ✅ Event schema versioning, backward compatibility
- ✅ Idempotency, Dead-letter queues
- **적용 위치**: Event Storming implementation skill

### 4. API Endpoint 구현
- ✅ Command → REST API endpoints
- ✅ ReadModel → Query API endpoints
- ✅ Response codes, pagination, filtering
- **적용 위치**: Event Storming implementation skill + Tech stack skill

### 5. Frontend Implementation
- ✅ Command에 UI 버튼/폼 + API 연결
- ✅ ReadModel에 페이지 + API 연결
- ✅ Progressive BC integration (메인 페이지 → BC별 기능)
- **적용 위치**: Frontend skill

### 6. Implementation Checklists
- ✅ 100% Coverage 체크리스트
- ✅ 모든 Event Storming 요소 구현 확인
- **적용 위치**: 각 skill에 포함

---

## 참고 파일

- `docs/PRD_CURSOR_IMPROVEMENTS.md` - Cursor 기반 개선 사항 정리
- `api/features/prd_generation/prd_artifact_generation.py` - Cursor rules 생성 함수들
  - `generate_ddd_principles_rule()`
  - `generate_eventstorming_implementation_rule()`
  - `generate_gwt_test_generation_rule()`
  - `generate_cursor_tech_stack_rule()`
  - `generate_frontend_cursor_rule()`

---

## 다음 단계

1. ✅ **현재**: Cursor 기반 개선 사항 정리 완료 (`PRD_CURSOR_IMPROVEMENTS.md`)
2. 🔄 **진행 중**: Claude Skills 개선 계획 수립 (이 문서)
3. ⏳ **다음**: Skills 생성 함수 구현
4. ⏳ **다음**: Agent 파일 개선
5. ⏳ **다음**: 파일 생성 로직 업데이트
6. ⏳ **다음**: PRD 및 Spec 파일 업데이트
