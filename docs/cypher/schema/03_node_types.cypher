// ============================================================
// Event Storming Impact Analysis - Node Types Definition
// ============================================================
// 각 노드 타입의 속성 정의 및 생성 패턴을 문서화합니다.
// ============================================================

// ############################################################
// 1. Requirement (요구사항)
// ############################################################
// 설명: 원본 요구사항 문서에서 추출한 요구사항
//
// 필수 속성:
//   - id: String (고유 식별자)
//   - title: String (요구사항 제목)
//
// 선택 속성:
//   - description: String (상세 설명)
//   - source: String (출처 문서명)
//   - createdAt: DateTime
//   - priority: String ("high", "medium", "low")
// ############################################################

CREATE (r:Requirement {
    id: "REQ-001",
    title: "주문 관리 기능",
    description: "고객이 주문을 생성, 조회, 취소할 수 있어야 한다",
    source: "기능요구사항서 v1.0",
    createdAt: datetime(),
    priority: "high"
});


// ############################################################
// 2. UserStory (사용자 스토리)
// ############################################################
// 설명: "As a [role], I want [action], so that [benefit]" 형식
// 관계: IMPLEMENTS → BoundedContext, Aggregate
//
// 필수 속성:
//   - id: String (고유 식별자)
//   - role: String (사용자 역할)
//   - action: String (원하는 행동)
//
// 선택 속성:
//   - benefit: String (기대 효과)
//   - priority: String
//   - status: String ("draft", "approved", "implemented")
//   - acceptanceCriteria: List<String>
//   - criteriaUserEdited: Boolean   (true once a user has edited acceptanceCriteria via the Properties panel; blocks ingestion regen of that field per spec 019)
//   - criteriaEditedAt: DateTime    (timestamp of the last manual criteria edit; null until first edit)
//   - clarifications: String (JSON) (spec 030 — append-only `List<ClarificationLogEntry>` of applied clarification answers
//                                    for this user story: {sessionId, questionId, question, answer, category, before, after, at};
//                                    absent/`"[]"` when no clarification has been applied. No new node label — same
//                                    provenance pattern as `criteriaUserEdited`.)
// ############################################################

CREATE (us:UserStory {
    id: "US-001",
    role: "customer",
    action: "cancel my order",
    benefit: "I can get a refund if I change my mind",
    priority: "high",
    status: "approved"
});


// ############################################################
// 3. BoundedContext (바운디드 컨텍스트)
// ############################################################
// 설명: 전략적 설계 단위, 도메인의 논리적 경계
// 관계: 
//   - HAS_AGGREGATE → Aggregate
//   - HAS_POLICY → Policy
//   - DEPENDS_ON ↔ BoundedContext
//
// 필수 속성:
//   - id: String (UUID, 고유 식별자)
//   - key: String (자연키, 멱등성 MERGE 기준)
//   - name: String (컨텍스트 이름)
//
// 선택 속성:
//   - description: String
//   - owner: String (담당 팀)
//   - classification: String (029) — 'core' | 'supporting'. /robo-plan 이
//       core 도메인은 clean architecture, supporting 은 default speckit
//       아키텍처로 plan.md 를 생성하기 위해 참조한다. 미설정 시 /robo-plan
//       이 개발자에게 묻고 그 답을 MCP `set_bc_classification` 로 다시
//       기록한다. enum validation 은 API 계층(PATCH /api/contexts/{id}/
//       classification)에서 수행하며, Cypher 제약은 추가하지 않는다.
// ############################################################

MERGE (bc:BoundedContext { key: "order" })
ON CREATE SET bc.id = randomUUID()
SET bc.name = "Order",
    bc.description = "주문 생성, 수정, 취소 및 주문 상태 관리",
    bc.owner = "Order Team",
    bc.classification = "core";


// ############################################################
// 4. Aggregate (애그리게이트)
// ############################################################
// 설명: 전술적 설계 핵심, 트랜잭션 일관성 경계
// 관계:
//   - HAS_COMMAND → Command
//
// 필수 속성:
//   - id: String (UUID)
//   - key: String (자연키)
//   - name: String
//
// 선택 속성:
//   - rootEntity: String
//   - invariants: List<String>   (027 이후 레거시 — Invariant 노드로 이관, 이관 후 비워짐)
//   - invariantsMigratedAt: DateTime  (027 — 레거시 invariants 이관 완료 스탬프)
//   - enumerations / valueObjects: String (JSON) — 어그리거트 내부 도메인 객체
//   - exceptions: String (JSON, 027) — 어그리거트 Exception 도메인 객체 카탈로그.
//       각 항목 {name, message, fields:[{name,type,description?}]}. GWT Then이
//       (Command·Invariant 공통) name으로 참조한다.
// ############################################################

MATCH (bc:BoundedContext { key: "order" })
MERGE (agg:Aggregate { key: "order.order" })
ON CREATE SET agg.id = randomUUID()
SET agg.name = "Order",
    agg.rootEntity = "Order",
    agg.invariants = [
        "주문 총액은 0보다 커야 함",
        "배송 시작 후에는 취소 불가"
    ]
MERGE (bc)-[:HAS_AGGREGATE]->(agg);


// ############################################################
// 5. Command (커맨드)
// ############################################################
// 설명: 사용자의 의도를 표현하는 명령
// 관계:
//   - EMITS → Event
//
// 필수 속성:
//   - id: String (UUID)
//   - key: String (자연키)
//   - name: String (동사형)
//
// 선택 속성:
//   - actor: String
//   - inputSchema: String (JSON)
// ############################################################

MATCH (agg:Aggregate { key: "order.order" })
MERGE (cmd:Command { key: "order.order.cancel-order" })
ON CREATE SET cmd.id = randomUUID()
SET cmd.name = "CancelOrder",
    cmd.actor = "customer",
    cmd.inputSchema = '{"orderId": "string", "reason": "string"}'
MERGE (agg)-[:HAS_COMMAND]->(cmd);


// ############################################################
// 6. Event (이벤트)
// ############################################################
// 설명: 도메인에서 발생한 사실 (과거형)
// 관계:
//   - TRIGGERS → Policy (다른 BC의 Policy)
//
// 필수 속성:
//   - id: String (UUID)
//   - key: String (자연키; 보통 version 포함)
//   - name: String (과거형)
//   - version: String
//
// 선택 속성:
//   - schema: String (JSON)
//   - isBreaking: Boolean
// ############################################################

MATCH (cmd:Command { key: "order.order.cancel-order" })
MERGE (evt:Event { key: "order.order.cancel-order.order-cancelled@1.0.0" })
ON CREATE SET evt.id = randomUUID()
SET evt.name = "OrderCancelled",
    evt.version = "1.0.0",
    evt.schema = '{"orderId": "string", "cancelledAt": "datetime", "reason": "string"}',
    evt.isBreaking = false
MERGE (cmd)-[:EMITS]->(evt);


// ############################################################
// 7. Policy (폴리시)
// ############################################################
// 설명: 다른 BC의 이벤트에 반응하여 자신의 Command를 호출
//       "When [Event] then [Command]" 패턴
// 관계:
//   - INVOKES → Command (자신의 BC에 있는)
//
// 필수 속성:
//   - id: String (UUID)
//   - key: String (자연키)
//   - name: String
//
// 선택 속성:
//   - condition: String (트리거 조건)
//   - description: String
// ############################################################

MATCH (bcPayment:BoundedContext { key: "payment" })
MERGE (pol:Policy { key: "payment.refund-on-order-cancellation" })
ON CREATE SET pol.id = randomUUID()
SET pol.name = "RefundOnOrderCancellation",
    pol.condition = "OrderCancelled received",
    pol.description = "주문 취소 이벤트 수신 시 환불 처리"
MERGE (bcPayment)-[:HAS_POLICY]->(pol);


// ############################################################
// 8. Property (속성)
// ############################################################
// 설명: Aggregate/Command/Event/UI/ReadModel 등 DDD 객체의 속성(필드) 정의
// 관계:
//   - HAS_PROPERTY → Property
//
// 필수 속성:
//   - id: String (UUID)
//   - name: String
//   - type: String (Java 타입 문자열)
//   - description: String
//   - isKey: Boolean
//   - isForeignKey: Boolean
//   - isRequired: Boolean
//   - parentType: String ("Aggregate"|"Command"|"Event"|"ReadModel")
//   - parentId: String (부모 노드 UUID)
//
// 선택 속성:
//   - type: String (e.g., string, int, datetime, ...)
//   - description: String
//   - isRequired: Boolean
//   - fkTargetHint: String? (2차 REFERENCES 생성을 위한 FK 대상 힌트; 예: "Aggregate:order.order:id")
// ############################################################

MATCH (cmd:Command { key: "order.order.cancel-order" })
MERGE (prop:Property { parentType: "Command", parentId: cmd.id, name: "orderId" })
ON CREATE SET prop.id = randomUUID()
SET prop.type = "UUID",
    prop.description = "주문 고유 식별자",
    prop.isKey = true,
    prop.isForeignKey = false,
    prop.isRequired = true
MERGE (cmd)-[:HAS_PROPERTY]->(prop);


// ############################################################
// 9. UI (와이어프레임)
// ############################################################
// 설명: Command/ReadModel에 부착되는 화면(와이어프레임) 스티커
// 관계:
//   - HAS_UI: BoundedContext → UI
//   - ATTACHED_TO: UI → Command/ReadModel
//   - HAS_PROPERTY: UI → Property (선택)
//
// 필수 속성:
//   - id: String (UUID)
//   - key: String (자연키)
//   - name: String
//
// 선택 속성:
//   - description: String
//   - template: String (예: HTML/마크다운/DSL 등)
//   - attachedToId: String (부착 대상 id)
//   - attachedToType: String ("Command" | "ReadModel")
//   - attachedToName: String
//   - userStoryId: String (근거가 된 UserStory id)
//
// Figma 연동 속성 (016-figma-document-binding):
//   - sceneGraph: String (JSON; open-pencil SerializedSceneGraph)
//   - designSource: String ("html" | "figma-bound" | "imported")
//   - figmaFileKey: String (도큐먼트 식별자)
//   - figmaPageId: String (소속 페이지)
//   - figmaNodeId: String (생성된 프레임 노드 id)
//   - figmaBindingId: String (생성 시점의 :FigmaBinding.id 스냅샷 — replace 후 "from previous binding" 판별용)
//   - figmaStoryboardCommandId: String (소속 스토리보드 = entry Command id)
//
// Figma 동기화 상태 속성 (v1.2 / FR-019b / FR-020):
//   - figmaSyncStatus: String ("ok" | "failed", null = 시도 안됨)
//   - figmaSyncLastError: String (마지막 실패 한국어 에러 메시지; status="ok" 시 null)
//   - figmaSyncLastAttemptAt: DateTime (마지막 시도 ISO 8601 타임스탬프; 성공/실패 무관)
// ############################################################

MATCH (bc:BoundedContext { key: "order" })
MATCH (cmd:Command { key: "order.order.cancel-order" })
MERGE (ui:UI { key: "ui.command." + cmd.id })
ON CREATE SET ui.id = randomUUID()
SET ui.name = "CancelOrder UI",
    ui.description = "주문 취소 화면: 주문번호 입력 후 취소 사유를 선택하고 '취소' 버튼 클릭",
    ui.template = "",
    ui.attachedToId = cmd.id,
    ui.attachedToType = "Command",
    ui.attachedToName = cmd.name,
    ui.userStoryId = "US-001"
MERGE (bc)-[:HAS_UI]->(ui)
MERGE (ui)-[:ATTACHED_TO]->(cmd);


// ############################################################
// 10. Given (GWT - Given/When/Then)
// ############################################################
// 설명: BDD 스타일의 Given/When/Then 구성 요소 중 Given
//       Command의 경우: Command 자체를 참조
//       Policy의 경우: Policy를 트리거하는 Event를 참조
// 관계:
//   - HAS_GIVEN: Command/Policy → Given
//   - REFERENCES: Given → Command/Event (참조 대상)
//
// 필수 속성:
//   - id: String (UUID)
//   - key: String (자연키)
//   - name: String (Given 설명)
//   - parentType: String ("Command" | "Policy")
//   - parentId: String (부모 노드 UUID)
//
// 선택 속성:
//   - description: String
//   - referencedNodeId: String (참조하는 노드 ID - Command 또는 Event)
//   - referencedNodeType: String ("Command" | "Event")
// ############################################################

MATCH (cmd:Command {key: "order.order.cancel-order"})
MERGE (given:Given {parentType: "Command", parentId: cmd.id, key: "given." + cmd.id})
ON CREATE SET given.id = randomUUID()
SET given.name = "Command: CancelOrder",
    given.description = "주문 취소 명령이 실행됨",
    given.referencedNodeId = cmd.id,
    given.referencedNodeType = "Command"
MERGE (cmd)-[:HAS_GIVEN]->(given)
MERGE (given)-[:REFERENCES]->(cmd);


// ############################################################
// 11. When (GWT - Given/When/Then)
// ############################################################
// 설명: BDD 스타일의 Given/When/Then 구성 요소 중 When
//       Command/Policy를 처리하는 Aggregate를 참조
// 관계:
//   - HAS_WHEN: Command/Policy → When
//   - REFERENCES: When → Aggregate (참조 대상)
//
// 필수 속성:
//   - id: String (UUID)
//   - key: String (자연키)
//   - name: String (When 설명)
//   - parentType: String ("Command" | "Policy")
//   - parentId: String (부모 노드 UUID)
//
// 선택 속성:
//   - description: String
//   - referencedNodeId: String (참조하는 Aggregate ID)
//   - referencedNodeType: String ("Aggregate")
// ############################################################

MATCH (cmd:Command {key: "order.order.cancel-order"})
MATCH (agg:Aggregate {key: "order.order"})
MERGE (when:When {parentType: "Command", parentId: cmd.id, key: "when." + cmd.id})
ON CREATE SET when.id = randomUUID()
SET when.name = "Aggregate: Order",
    when.description = "Order Aggregate가 Command를 처리함",
    when.referencedNodeId = agg.id,
    when.referencedNodeType = "Aggregate"
MERGE (cmd)-[:HAS_WHEN]->(when)
MERGE (when)-[:REFERENCES]->(agg);


// ############################################################
// 12. Then (GWT - Given/When/Then)
// ############################################################
// 설명: BDD 스타일의 Given/When/Then 구성 요소 중 Then
//       Command의 경우: Command가 emit하는 Event를 참조
//       Policy의 경우: Policy가 invoke하는 Command가 emit하는 Event를 참조
// 관계:
//   - HAS_THEN: Command/Policy → Then
//   - REFERENCES: Then → Event (참조 대상)
//
// 필수 속성:
//   - id: String (UUID)
//   - key: String (자연키)
//   - name: String (Then 설명)
//   - parentType: String ("Command" | "Policy")
//   - parentId: String (부모 노드 UUID)
//
// 선택 속성:
//   - description: String
//   - referencedNodeId: String (참조하는 Event ID)
//   - referencedNodeType: String ("Event")
// ############################################################

MATCH (cmd:Command {key: "order.order.cancel-order"})
MATCH (evt:Event {key: "order.order.cancel-order.order-cancelled@1.0.0"})
MERGE (then:Then {parentType: "Command", parentId: cmd.id, key: "then." + cmd.id})
ON CREATE SET then.id = randomUUID()
SET then.name = "Event: OrderCancelled",
    then.description = "주문 취소 이벤트가 발생함",
    then.referencedNodeId = evt.id,
    then.referencedNodeType = "Event"
MERGE (cmd)-[:HAS_THEN]->(then)
MERGE (then)-[:REFERENCES]->(evt);


// ############################################################
// 13. FigmaBinding (피그마 다큐먼트 바인딩 — 싱글톤)
// ############################################################
// 설명: 현재 Event Modeling 프로젝트와 외부 Figma 다큐먼트 1건의 연결 정보.
//       단일 활성 바인딩(`id="singleton"`)을 유지함. 016 feature(figma-document-binding) 참조.
// 관계:
//   - MAPS_STORYBOARD → BCPageMapping (스토리보드별 페이지 매핑)
//   - LOGGED ← BindingHistoryEvent (감사 로그)
//
// 필수 속성:
//   - id: String (고정 "singleton" — UNIQUE)
//   - figmaFileKey: String
//   - figmaFileName: String
//   - connectedBy: String
//   - connectedAt: DateTime
//   - status: String ("active" | "unreachable" | "disconnected")
//
// 선택 속성:
//   - lastSyncAt: DateTime
//
// 020 (figma-sync-recovery) 추가 advisory lock 필드 — :SyncRun 활성 시에만 non-null:
//   - currentRunId: String|null (활성 :SyncRun.id; 한 binding 당 동시에 1개 run)
//   - currentRunHolder: String|null (run 시작자의 actor — UI 노출용)
// ############################################################

// (생성 예시 — 실제 데이터는 런타임에 /api/figma-binding/connect 가 upsert)


// ############################################################
// 14. StoryboardPageMapping (스토리보드 ↔ Figma 페이지 매핑)
// ############################################################
// 설명: 좌측 BUSINESS PROCESSES 패널의 한 행(= entry Command 한 건 = 한 storyboard)이
//       바인딩된 Figma 다큐먼트의 한 페이지에 1:1 매핑된 기록.
//       UNIQUE: id (UUID), commandId (활성 매핑당 한 entry Command).
// 관계:
//   - MAPS_STORYBOARD ← FigmaBinding
//   - MAPS → Command (해당 storyboard의 entry command)
//
// 필수 속성:
//   - id: String (UUID)
//   - commandId: String (entry Command.id)
//   - figmaPageId: String (Figma page node id, 예: "0:42")
//   - figmaPageName: String (cached display name)
//   - status: String ("active" | "archived")
//
// 선택 속성:
//   - lastRenameAt: DateTime
// ############################################################


// ############################################################
// 15. BindingHistoryEvent (피그마 바인딩 감사 로그)
// ############################################################
// 설명: 016 feature의 모든 bind/sync/generate/disconnect 이벤트를 append-only로 저장.
// 관계:
//   - LOGGED → FigmaBinding
//
// 필수 속성:
//   - id: String (UUID)
//   - eventType: String ("connect" | "validate_failure" | "sync_storyboards" |
//                        "page_renamed" | "page_archived" | "disconnect" | "replace" |
//                        "generate_routed" | "orphan_ui_blocked")
//   - actor: String
//   - at: DateTime
//
// 선택 속성:
//   - figmaFileKey: String
//   - payload: String (JSON-encoded)
// ############################################################


// ############################################################
// 16. SyncRun (Figma 동기화 실행 요약 — 020)
// ############################################################
// 설명: 020 feature(figma-sync-recovery)의 retroactive full-sync 또는 manual-retry
//       1회 dispatch 당 1행. 개별 페이지/프레임 결과는 :UI.figmaSync* 에 저장하고,
//       :SyncRun 은 한 줄 요약(History 탭의 summary row)을 위한 집계 row.
//       이전 binding 으로 dispatch 된 run 은 bindingFileKey 가 현재 binding 과
//       다르므로 "이전 바인딩" 그룹 필터의 discriminator 역할.
// 관계:
//   - RUN_OF → FigmaBinding (project-scoped 조회용)
//
// 필수 속성:
//   - id: String (UUID — UNIQUE; runId 로 API 노출)
//   - kind: String ("retroactive-sync" | "manual-retry")
//   - bindingFileKey: String (run 시점의 figmaFileKey 스냅샷)
//   - actor: String
//   - startedAt: DateTime
//   - status: String ("running" | "succeeded" | "partially-succeeded" |
//                     "cancelled" | "aborted-binding-unreachable")
//
// 선택 속성:
//   - finishedAt: DateTime (status='running' 동안 null)
//   - summary: String (JSON-encoded
//        {storyboardsTotal, pagesCreated, pagesAlreadyOk, uisTotal,
//         framesPushed, generated, overwrites, failures})
// ############################################################


// ############################################################
// 17. UI 추가 속성 (020)
// ############################################################
// 설명: 016 v1.2 의 figmaSyncStatus / figmaSyncLastError / figmaSyncLastAttemptAt
//       에 더해 020 은 다음 1개 속성을 추가한다:
//
//   - figmaSyncBindingFileKey: String|null
//       — figmaSyncStatus 가 'ok' 또는 'failed' 로 set 될 때의
//         활성 :FigmaBinding.figmaFileKey 스냅샷. classifier 의
//         "이전 바인딩 (binding 이 replace 된 후 file key 가 다름)"
//         판단에 사용된다 (research D5).
// ############################################################


// ############################################################
// 18. Journey / JourneyStep (UI-layer 사용자 여정) — 025 v3 ui-flow-edges
// ############################################################
// 설명: 목적 있는 하나의 사용자 여정(Journey)과 그 단계(JourneyStep).
//       JourneyStep 은 'screen'(공유 UI 를 SHOWS) 또는 'gateway'(분기
//       다이아몬드). 단계 간 흐름은 NEXT 엣지(분기 조건 포함)로 표현한다.
//       재사용 화면은 여정마다 별도 JourneyStep 이 되며 모두 같은 UI 를 가리킨다.
//
// 관계:
//   - BoundedContext-[:HAS_JOURNEY]->Journey
//   - Journey-[:HAS_STEP]->JourneyStep
//   - JourneyStep-[:SHOWS]->UI                 (screen 단계만)
//   - JourneyStep-[:NEXT {condition}]->JourneyStep
//
// Journey 필수 속성:
//   - id: String (UUID v5, journey.key 기반)
//   - key: String (`<bc.key>.journey.<journeySlug>`)
//   - journeyId: String (journeySlug — 프런트 그룹핑/필터 키)
//   - name: String (여정명, 예: "정상 회원가입")
//   - description: String
//   - boundedContextId: String (소유 BC = 화면이 가장 많은 BC)
//   - source: String ("llm" | "manual")
//
// JourneyStep 필수 속성:
//   - id: String (UUID v5, step.key 기반)
//   - key: String (`<journey.key>.step.<kind>.<ref>`)
//   - kind: String ("screen" | "gateway")
//   - label: String (screen=화면명, gateway=의사결정 질문)
//   - sequence: Int (레이아웃 힌트 — 위상정렬 순위)
//   - source: String ("llm" | "manual")
// ############################################################

CREATE (j:Journey {
    id: "00000000-0000-5000-8000-000000000001",
    key: "membership.journey.normal-signup-abc123",
    journeyId: "normal-signup-abc123",
    name: "정상 회원가입",
    description: "신규 사용자가 약관 동의부터 가입 완료까지 진행하는 여정",
    boundedContextId: "<bc-uuid>",
    source: "llm",
    createdAt: datetime(),
    updatedAt: datetime()
});

CREATE (s:JourneyStep {
    id: "00000000-0000-5000-8000-000000000002",
    key: "membership.journey.normal-signup-abc123.step.gateway.approve-xyz",
    kind: "gateway",
    label: "가입 가능 여부?",
    sequence: 3,
    source: "llm",
    createdAt: datetime(),
    updatedAt: datetime()
});


// ############################################################
// 19. Feature (피처 — 026 requirements-tab)
// ############################################################
// 설명: BoundedContext(Epic)와 UserStory 사이의 그룹 단위.
//       관련 User Story 묶음을 나타낸다. 하나의 BC에 속하고
//       여러 User Story를 포함한다(Feature→UserStory: HAS_USER_STORY).
// 관계:
//   - BoundedContext-[:HAS_FEATURE]->Feature
//   - Feature-[:HAS_USER_STORY]->UserStory
//
// 필수 속성:
//   - id: String (UUID — ON CREATE randomUUID())
//   - key: String (자연키 — `<bc.key>.feature.<slug(name)>`, 멱등 MERGE 기준)
//   - name: String (Feature 이름)
//   - boundedContextId: String (소속 BC의 id — 조회 편의용 비정규화)
//   - source: String ("llm" | "manual")
//
// 선택 속성:
//   - description: String
//   - sequence: Int (트리 내 정렬 힌트)
//   - createdAt / updatedAt: DateTime
// ############################################################

MATCH (bc:BoundedContext { key: "order" })
MERGE (f:Feature { key: "order.feature.order-cancellation" })
ON CREATE SET f.id = randomUUID(), f.createdAt = datetime(), f.source = "llm"
SET f.name = "주문 취소",
    f.description = "고객이 주문을 취소하고 환불을 받는 기능 묶음",
    f.boundedContextId = bc.id,
    f.sequence = 1,
    f.updatedAt = datetime()
MERGE (bc)-[:HAS_FEATURE]->(f);


// ############################################################
// 20. Invariant (인베리언트 — 027 aggregate-invariants)
// ############################################################
// 설명: 어그리거트가 항상 준수해야 하는 비즈니스 규칙을 나타내는 1급 객체.
//       어그리거트 하위에 0..N개 부착. 디자인 트리에서만 노출(캔버스 스티커 아님).
//       세부 검증 조건은 (a) 커맨드의 GWT 인수조건을 VERIFIED_BY로 공유 참조하거나
//       (b) parentType="Invariant"인 인베리언트 전용 GWT 노드로 보유한다.
// 관계:
//   - Aggregate-[:HAS_INVARIANT]->Invariant
//   - Invariant-[:VERIFIED_BY]->Command   (커맨드 GWT 인수조건 공유 참조)
//   - Invariant-[:HAS_GWT]->GWT           (인베리언트 전용 GWT)
//
// 필수 속성:
//   - id: String (UUID — ON CREATE randomUUID())
//   - key: String (자연키 — `<aggregate.key>.invariant.<slug>-<hash>`, 멱등 MERGE 기준)
//   - declaration: String (규칙 선언문 — 자연어 문장)
//
// 선택 속성:
//   - name: String (짧은 제목)
//   - description: String
//   - source: String ("manual" | "ingested" | "migrated")
//   - seq: Int (어그리거트 내 정렬 순서)
//   - aggregateId: String (소유 Aggregate의 id — 조회 편의용 비정규화)
//   - createdAt / updatedAt: DateTime
//
// 참고: GWT 노드의 parentType 속성은 027부터 "Invariant" 값도 허용한다 —
//       인베리언트 전용 GWT는 GWT {parentType:"Invariant", parentId:<inv.id>}.
//       인베리언트 GWT는 Given·Then만 사용한다("When"은 규칙에 해당되지 않아
//       편집기에서 숨겨짐). Then은 어그리거트 exceptions 카탈로그의 Exception을
//       thenRef.exceptionName으로 참조해 예외 결과를 선언할 수 있다(Command GWT 공통).
// ############################################################

MATCH (agg:Aggregate { key: "order.order" })
MERGE (inv:Invariant { key: "order.order.invariant.order-total-positive-abc123def456" })
ON CREATE SET inv.id = randomUUID(), inv.createdAt = datetime(), inv.source = "manual"
SET inv.declaration = "주문 총액은 항상 0보다 커야 한다",
    inv.name = "주문 총액 양수",
    inv.aggregateId = agg.id,
    inv.seq = 1,
    inv.updatedAt = datetime()
MERGE (agg)-[:HAS_INVARIANT]->(inv);


// ############################################################
// 99. ImplementationFile (소스 파일 매핑 — 029)
// ############################################################
// 설명: Robo Architect 디자인 엘리먼트(Aggregate / Command / Event /
//       ReadModel)를 실제 구현 파일에 연결하는 노드. /robo-spec 의
//       단일 소스-매핑 원칙(R5)에 따라 워크스페이스 로컬 매니페스트
//       (.robo-link.json 등)는 사용하지 않고, 모든 매핑은 이 노드와
//       [:IMPLEMENTED_IN] 관계에만 저장된다.
//
// 관계:
//   - (:Aggregate|Command|Event|ReadModel)-[:IMPLEMENTED_IN]->(:ImplementationFile)
//     N:M (하나의 엘리먼트가 여러 파일에 걸칠 수 있고, 한 파일이 여러
//     엘리먼트를 백킹할 수 있음).
//
// 필수 속성:
//   - id: String (UUID)
//   - projectId: String (Robo Architect 프로젝트 UUID — 같은 프로젝트가
//       여러 워크스페이스에 링크되더라도 매핑은 워크스페이스 독립적)
//   - path: String (워크스페이스 루트 기준 POSIX 경로; 절대경로/'..' 금지 —
//       검증은 api/features/robo_spec/implementation_files.py 에서 수행)
//   - role: String (primary | interface-adapter | infrastructure | test | other)
//   - createdAt: DateTime ISO-8601
//   - lastSeenAt: DateTime ISO-8601 (/robo-implement 와 /robo-sync 가 파일을
//       관측할 때마다 갱신)
//
// 고유성: (projectId, path) — 01_constraints.cypher 에 unique constraint
//   추가됨(constraint_implementationfile_project_path).
// ############################################################

// 예시 — Order 어그리거트가 src/order/domain/Order.ts 에 구현됨
MATCH (agg:Aggregate { key: "order.order" })
MERGE (impl:ImplementationFile {
    projectId: "00000000-0000-0000-0000-000000000000",
    path: "src/order/domain/Order.ts"
})
ON CREATE SET impl.id = randomUUID(),
              impl.role = "primary",
              impl.createdAt = datetime(),
              impl.lastSeenAt = datetime()
ON MATCH SET impl.lastSeenAt = datetime()
MERGE (agg)-[:IMPLEMENTED_IN]->(impl);


// ############################################################
// 100. RequirementChange (요구사항 변경 레코드 — 038)
// ############################################################
// 설명: 요구사항 변경 단위. 자연어 프롬프트·직접 수정·수동 입력 3가지
//       진입점으로 생성되며, DRAFT→SUBMITTED→APPROVED→IMPLEMENTED 순으로
//       상태가 전이된다. EFFECT 관계를 통해 영향받는 UserStory·
//       BoundedContext·Aggregate에 연결된다.
//
// 관계:
//   - (RequirementChange)-[:EFFECT]->(UserStory|BoundedContext|Aggregate)
//   - (ChangeSet)-[:CONTAINS]->(RequirementChange)
//
// 필수 속성:
//   - id: String ("CHG-NNN", 전역 고유)
//   - title: String
//   - originalPrompt: String (원본 자연어 프롬프트 또는 수정 요약)
//   - author: String (생성자 ID / 이메일)
//   - createdAt: DateTime
//   - status: String (DRAFT|SUBMITTED|PLAN_APPROVED|DESIGN_APPLIED|APPROVED|REJECTED|IMPLEMENTED)
//
// 선택 속성:
//   - statusHistory: String (JSON 직렬화 List<{fromStatus,toStatus,at,actor,comment}>)
//   - sourceType: String (PROMPT|DIRECT_EDIT|MANUAL)
//   - changeSetId: String|null (소속 ChangeSet ID)
//
// ⚠ 삭제된 속성 (038 phase-2):
//   - designChanges: String — EFFECT 관계 속성(e.diff)으로 이전.
//       RequirementChange 1:N Target 구조에서 각 Target별 diff를 관계에 보관함으로써
//       선택적 undo와 충돌 감지가 가능해짐. SemanticDiff 포맷은 04_relationships.cypher 참고.
// ############################################################

CREATE (chg:RequirementChange {
    id: "CHG-001",
    title: "반품 기간 연장",
    originalPrompt: "반품 기간을 7일에서 14일로 변경",
    author: "user@example.com",
    createdAt: datetime(),
    status: "DRAFT",
    statusHistory: "[]",
    sourceType: "PROMPT",
    changeSetId: null
});

CREATE CONSTRAINT req_change_id IF NOT EXISTS
FOR (n:RequirementChange) REQUIRE n.id IS UNIQUE;


// ############################################################
// 101. ChangeSet (Change 묶음 — 038)
// ############################################################
// 설명: 관련된 여러 RequirementChange를 하나의 묶음으로 그룹화하는 노드.
//       CONTAINS 관계로 Change를 포함하며, ChangeSet 단위로 승인·반영 가능.
//
// 관계:
//   - (ChangeSet)-[:CONTAINS]->(RequirementChange)
//
// 필수 속성:
//   - id: String ("CS-NNN")
//   - title: String
//   - author: String
//   - createdAt: DateTime
//   - status: String (DRAFT|SUBMITTED|APPROVED|REJECTED|IMPLEMENTED)
// ############################################################

CREATE (cs:ChangeSet {
    id: "CS-001",
    title: "Q3 정책 변경 묶음",
    author: "user@example.com",
    createdAt: datetime(),
    status: "DRAFT"
});

CREATE CONSTRAINT changeset_id IF NOT EXISTS
FOR (n:ChangeSet) REQUIRE n.id IS UNIQUE;


// ############################################################
// 039 — Proposal Lifecycle Management
// ############################################################
// Proposal 노드: PRO-NNN 고유 ID, 생애주기 상태 관리
// 관계: (p:Proposal)-[:EFFECT]->(n) — 038 EFFECT 관계 재사용
//
// 선택 속성(인텐트 분해 관련):
//   - strategicDiff / tacticalDiff: String (JSON) — 인텐트 분해 결과
//   - clarificationLog: String (JSON List<{question,options,answer,at}>) — 명확화 Q&A
//   - intentFeedbackLog: String (JSON List<{feedback,at}>) — 분석 결과 보정용
//       자연어 피드백. 재분해 시 이전 diff와 함께 스킬 프롬프트에 실려 결과를
//       다시 생성한다(DRAFT 한정). FR-002a.
// ############################################################

CREATE CONSTRAINT proposal_id_unique IF NOT EXISTS
FOR (p:Proposal) REQUIRE p.id IS UNIQUE;

CREATE INDEX proposal_status IF NOT EXISTS
FOR (p:Proposal) ON (p.status);

CREATE INDEX proposal_author IF NOT EXISTS
FOR (p:Proposal) ON (p.author);

// ############################################################
// 041 — Constitution 노드: 프로젝트 헌장(설계원칙·기술스택·아키텍처 스타일·레포 전략)
//   - 그래프가 원천(Principle I). 레포 파일/프로포절 사본 아님.
//   - scope: "PROJECT"(루트 싱글톤) | "BOUNDED_CONTEXT"(BC 오버라이드)
//   - 속성: designPrinciples/techStack/architectureStyle/repoStrategy/repoMode/raw/updatedAt
//   - 관계: (:BoundedContext)-[:HAS_CONSTITUTION]->(:Constitution {scope:"BOUNDED_CONTEXT"})
//   - BC 유효(effective) 헌장 = 프로젝트 루트 + 해당 BC 오버라이드 병합(백엔드 계산)
// ############################################################

CREATE CONSTRAINT constitution_id_unique IF NOT EXISTS
FOR (c:Constitution) REQUIRE c.id IS UNIQUE;

CREATE INDEX constitution_scope IF NOT EXISTS
FOR (c:Constitution) ON (c.scope);

// ############################################################
// 042 — 속성 확장(신규 라벨/관계 없음):
//   Constitution.strategicMemory (JSON string) — 지속 DDD 전략 메모리.
//     · scope:"PROJECT" 노드: differentiation(차별성/가치제안/페르소나) + couplingPosture(기본 pub/sub vs sync) 섹션
//     · scope:"BOUNDED_CONTEXT" 노드: 해당 BC 의 contexts[bcKey] 섹션(분류/유비쿼터스 언어/비즈니스 결정)
//     · BC 유효 전략메모리 = 루트 + BC 오버라이드(섹션별 병합) — effective_for_bc() 계산
//     · constitution_hash 입력에 포함 → 수정 시 의존 Proposal plan staleness 유발(FR-021)
//   Proposal.decompositionMode ("SIMPLIFIED"|"DETAILED_DDD", 기본 SIMPLIFIED) — 분해 모드(FR-002)
//   Proposal.stagePlan (JSON string) — 스코프 인지 스테이지 플랜(applies/skip/reason, FR-009/FR-015)
//   Proposal.stageArtifacts (JSON string) — 스테이지별 리뷰 산출물(Proposal-scoped, FR-026)
//   Proposal.currentStage (string|null) — 확정 대기 중인 스테이지(재개용, FR-027)
//   Proposal.memoryConflicts (JSON string) — 메모리 vs 로컬결정 미해결 충돌(FR-019)
// ############################################################
