// ============================================================
// Event Storming Impact Analysis - Uniqueness Constraints
// ============================================================
// 각 노드 타입별 id 속성에 대한 유일성 제약조건을 정의합니다.
// Neo4j 4.4+ 문법 사용
// ============================================================

// ------------------------------------------------------------
// Requirement: 원 요구사항 노드
// ------------------------------------------------------------
CREATE CONSTRAINT constraint_requirement_id IF NOT EXISTS
FOR (r:Requirement)
REQUIRE r.id IS UNIQUE;

// ------------------------------------------------------------
// UserStory: "As a ... I want ... So that ..." 단위
// ------------------------------------------------------------
CREATE CONSTRAINT constraint_userstory_id IF NOT EXISTS
FOR (us:UserStory)
REQUIRE us.id IS UNIQUE;

// ------------------------------------------------------------
// BoundedContext: 전략적 설계 단위 (도메인 경계)
// ------------------------------------------------------------
CREATE CONSTRAINT constraint_boundedcontext_id IF NOT EXISTS
FOR (bc:BoundedContext)
REQUIRE bc.id IS UNIQUE;

// ------------------------------------------------------------
// Aggregate: 전술적 설계 핵심 (일관성 경계)
// ------------------------------------------------------------
CREATE CONSTRAINT constraint_aggregate_id IF NOT EXISTS
FOR (agg:Aggregate)
REQUIRE agg.id IS UNIQUE;

// ------------------------------------------------------------
// Command: 행위 (사용자 의도를 표현하는 명령)
// ------------------------------------------------------------
CREATE CONSTRAINT constraint_command_id IF NOT EXISTS
FOR (cmd:Command)
REQUIRE cmd.id IS UNIQUE;

// ------------------------------------------------------------
// Event: 상태 변화 (도메인에서 발생한 사실)
// ------------------------------------------------------------
CREATE CONSTRAINT constraint_event_id IF NOT EXISTS
FOR (evt:Event)
REQUIRE evt.id IS UNIQUE;

// ------------------------------------------------------------
// Policy: 이벤트 → 커맨드 트리거 (비즈니스 규칙)
// ------------------------------------------------------------
CREATE CONSTRAINT constraint_policy_id IF NOT EXISTS
FOR (pol:Policy)
REQUIRE pol.id IS UNIQUE;

// ============================================================
// Node Property Existence Constraints
// ============================================================

// UserStory는 role, action이 필수
CREATE CONSTRAINT constraint_userstory_role IF NOT EXISTS
FOR (us:UserStory)
REQUIRE us.role IS NOT NULL;

CREATE CONSTRAINT constraint_userstory_action IF NOT EXISTS
FOR (us:UserStory)
REQUIRE us.action IS NOT NULL;

// Event는 name과 version이 필수
CREATE CONSTRAINT constraint_event_name IF NOT EXISTS
FOR (evt:Event)
REQUIRE evt.name IS NOT NULL;

CREATE CONSTRAINT constraint_event_version IF NOT EXISTS
FOR (evt:Event)
REQUIRE evt.version IS NOT NULL;

// BoundedContext, Aggregate, Command, Policy는 name 필수
CREATE CONSTRAINT constraint_bc_name IF NOT EXISTS
FOR (bc:BoundedContext)
REQUIRE bc.name IS NOT NULL;

CREATE CONSTRAINT constraint_agg_name IF NOT EXISTS
FOR (agg:Aggregate)
REQUIRE agg.name IS NOT NULL;

CREATE CONSTRAINT constraint_cmd_name IF NOT EXISTS
FOR (cmd:Command)
REQUIRE cmd.name IS NOT NULL;

CREATE CONSTRAINT constraint_policy_name IF NOT EXISTS
FOR (pol:Policy)
REQUIRE pol.name IS NOT NULL;

// ------------------------------------------------------------
// Property: DDD 객체의 속성/필드
// ------------------------------------------------------------
CREATE CONSTRAINT constraint_property_id IF NOT EXISTS
FOR (prop:Property)
REQUIRE prop.id IS UNIQUE;

CREATE CONSTRAINT constraint_property_name IF NOT EXISTS
FOR (prop:Property)
REQUIRE prop.name IS NOT NULL;

// ------------------------------------------------------------
// UI: 와이어프레임 (Command/ReadModel에 부착)
// ------------------------------------------------------------
CREATE CONSTRAINT constraint_ui_id IF NOT EXISTS
FOR (ui:UI)
REQUIRE ui.id IS UNIQUE;

CREATE CONSTRAINT constraint_ui_name IF NOT EXISTS
FOR (ui:UI)
REQUIRE ui.name IS NOT NULL;