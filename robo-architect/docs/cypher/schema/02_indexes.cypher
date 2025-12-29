// ============================================================
// Event Storming Impact Analysis - Indexes
// ============================================================
// 쿼리 성능 최적화를 위한 인덱스 정의
// Neo4j 4.4+ 문법 사용
// ============================================================

// ------------------------------------------------------------
// TEXT 인덱스: name 속성 기반 텍스트 검색용
// ------------------------------------------------------------

// BoundedContext name 검색
CREATE TEXT INDEX index_bc_name IF NOT EXISTS
FOR (bc:BoundedContext)
ON (bc.name);

// Aggregate name 검색
CREATE TEXT INDEX index_agg_name IF NOT EXISTS
FOR (agg:Aggregate)
ON (agg.name);

// Command name 검색
CREATE TEXT INDEX index_cmd_name IF NOT EXISTS
FOR (cmd:Command)
ON (cmd.name);

// Event name 검색
CREATE TEXT INDEX index_evt_name IF NOT EXISTS
FOR (evt:Event)
ON (evt.name);

// Policy name 검색
CREATE TEXT INDEX index_policy_name IF NOT EXISTS
FOR (pol:Policy)
ON (pol.name);

// ------------------------------------------------------------
// RANGE 인덱스: UserStory 속성 검색용
// ------------------------------------------------------------

// UserStory role 검색
CREATE INDEX index_userstory_role IF NOT EXISTS
FOR (us:UserStory)
ON (us.role);

// UserStory priority 검색
CREATE INDEX index_userstory_priority IF NOT EXISTS
FOR (us:UserStory)
ON (us.priority);

// UserStory status 검색
CREATE INDEX index_userstory_status IF NOT EXISTS
FOR (us:UserStory)
ON (us.status);

// ------------------------------------------------------------
// 복합 인덱스: Event 버전 관리용
// ------------------------------------------------------------

// Event name + version 복합 인덱스
CREATE INDEX index_evt_name_version IF NOT EXISTS
FOR (evt:Event)
ON (evt.name, evt.version);

// Event version 검색
CREATE INDEX index_evt_version IF NOT EXISTS
FOR (evt:Event)
ON (evt.version);

// Event isBreaking 플래그 검색
CREATE INDEX index_evt_breaking IF NOT EXISTS
FOR (evt:Event)
ON (evt.isBreaking);

// ------------------------------------------------------------
// FULLTEXT 인덱스: 자연어 검색용
// ------------------------------------------------------------

// UserStory 전체 텍스트 검색
CREATE FULLTEXT INDEX fulltext_userstory IF NOT EXISTS
FOR (us:UserStory)
ON EACH [us.role, us.action, us.benefit];

// Requirement 전체 텍스트 검색
CREATE FULLTEXT INDEX fulltext_requirement IF NOT EXISTS
FOR (r:Requirement)
ON EACH [r.title, r.description];

// ------------------------------------------------------------
// UI 인덱스
// ------------------------------------------------------------

// UI name 검색
CREATE TEXT INDEX index_ui_name IF NOT EXISTS
FOR (ui:UI)
ON (ui.name);

// UI attachedToId 검색 (부착된 Command/ReadModel 조회용)
CREATE INDEX index_ui_attached IF NOT EXISTS
FOR (ui:UI)
ON (ui.attachedToId);