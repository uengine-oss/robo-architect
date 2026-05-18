// ============================================================
// Event Storming Impact Analysis - Relationship Types
// ============================================================
// 관계 타입의 의미, 속성 및 생성 패턴을 정의합니다.
// 
// 핵심 패턴:
//   Event가 발생하면 → 다른 BC의 Policy가 반응 → 해당 BC의 Command 호출
// ============================================================

// ############################################################
// 1. IMPLEMENTS
// ############################################################
// 방향: UserStory → BoundedContext / Aggregate
// 의미: UserStory가 특정 BC 또는 Aggregate에서 구현됨
//
// 속성:
//   - createdAt: DateTime
//   - confidence: Float (AI 추론 신뢰도, 0.0 ~ 1.0)
// ############################################################

MATCH (us:UserStory {id: "US-001"})
MATCH (bc:BoundedContext {key: "order"})
CREATE (us)-[:IMPLEMENTS {
    createdAt: datetime(),
    confidence: 0.95
}]->(bc);


// ############################################################
// 2. HAS_AGGREGATE
// ############################################################
// 방향: BoundedContext → Aggregate
// 의미: BC가 해당 Aggregate를 포함함
//
// 속성:
//   - isPrimary: Boolean (주요 Aggregate 여부)
// ############################################################

MATCH (bc:BoundedContext {key: "order"})
MATCH (agg:Aggregate {key: "order.order"})
CREATE (bc)-[:HAS_AGGREGATE {
    isPrimary: true
}]->(agg);


// ############################################################
// 3. HAS_POLICY
// ############################################################
// 방향: BoundedContext → Policy
// 의미: BC가 해당 Policy를 소유함
//       Policy는 외부 Event에 반응하여 자신의 Command를 호출
// ############################################################

MATCH (bc:BoundedContext {key: "payment"})
MATCH (pol:Policy {key: "payment.refund-on-order-cancellation"})
CREATE (bc)-[:HAS_POLICY]->(pol);


// ############################################################
// 4. HAS_COMMAND
// ############################################################
// 방향: Aggregate → Command
// 의미: Aggregate가 해당 Command를 처리함
//
// 속성:
//   - isIdempotent: Boolean
// ############################################################

MATCH (agg:Aggregate {key: "order.order"})
MATCH (cmd:Command {key: "order.order.cancel-order"})
CREATE (agg)-[:HAS_COMMAND {
    isIdempotent: true
}]->(cmd);


// ############################################################
// 5. EMITS
// ############################################################
// 방향: Command → Event
// 의미: Command 실행 결과로 Event가 발생함
//
// 속성:
//   - isGuaranteed: Boolean
// ############################################################

MATCH (cmd:Command {key: "order.order.cancel-order"})
MATCH (evt:Event {key: "order.order.cancel-order.order-cancelled@1.0.0"})
CREATE (cmd)-[:EMITS {
    isGuaranteed: true
}]->(evt);


// ############################################################
// 6. TRIGGERS
// ############################################################
// 방향: Event → Policy (다른 BC의 Policy)
// 의미: Event 발생 시 다른 BC의 Policy가 반응
//
// 이것이 Event Storming의 핵심 Cross-BC 통신 패턴:
//   BC-A의 Event → BC-B의 Policy → BC-B의 Command
//
// 속성:
//   - priority: Integer
//   - isEnabled: Boolean
// ############################################################

MATCH (evt:Event {key: "order.order.cancel-order.order-cancelled@1.0.0"})
MATCH (pol:Policy {key: "payment.refund-on-order-cancellation"})
CREATE (evt)-[:TRIGGERS {
    priority: 1,
    isEnabled: true
}]->(pol);


// ############################################################
// 7. INVOKES
// ############################################################
// 방향: Policy → Command (같은 BC 내의 Command)
// 의미: Policy가 자신의 BC에 있는 Command를 호출
//
// 속성:
//   - isAsync: Boolean
// ############################################################

MATCH (pol:Policy {key: "payment.refund-on-order-cancellation"})
MATCH (cmd:Command {key: "payment.refund.process-refund"})
CREATE (pol)-[:INVOKES {
    isAsync: true
}]->(cmd);


// ############################################################
// 8. DEPENDS_ON (BC간 의존성)
// ############################################################
// 방향: BoundedContext → BoundedContext
// 의미: BC 간의 이벤트 기반 의존 관계
//       (Event → Policy 관계에서 자동 유추 가능)
//
// 속성:
//   - integrationPattern: String ("event", "sync")
// ############################################################

MATCH (bc1:BoundedContext {key: "order"})
MATCH (bc2:BoundedContext {key: "payment"})
CREATE (bc1)-[:DEPENDS_ON {
    integrationPattern: "event"
}]->(bc2);


// ############################################################
// 9. HAS_UI
// ############################################################
// 방향: BoundedContext → UI
// 의미: BC가 해당 UI(와이어프레임) 스티커를 포함/소유함
//
// ############################################################

MATCH (bc:BoundedContext {key: "order"})
MATCH (ui:UI {key: "ui.command.<commandId>"})
CREATE (bc)-[:HAS_UI]->(ui);


// ############################################################
// 10. ATTACHED_TO
// ############################################################
// 방향: UI → Command/ReadModel
// 의미: UI가 특정 Command/ReadModel에 부착됨 (화면이 어떤 액션/조회에 대응하는지)
//
// ############################################################

MATCH (ui:UI {key: "ui.command.<commandId>"})
MATCH (cmd:Command {key: "order.order.cancel-order"})
CREATE (ui)-[:ATTACHED_TO]->(cmd);


// ############################################################
// 11. HAS_PROPERTY
// ############################################################
// 방향: (Aggregate|Command|Event|ReadModel|UI) → Property
// 의미: 해당 객체가 특정 속성을 포함함
//
// ############################################################

MATCH (cmd:Command {key: "order.order.cancel-order"})
MATCH (prop:Property {parentType: "Command", parentId: cmd.id, name: "orderId"})
CREATE (cmd)-[:HAS_PROPERTY]->(prop);


// ############################################################
// 12. REFERENCES (외래키 참조)
// ############################################################
// 방향: Property(src FK) → Property(tgt PK)
// 의미: FK가 PK를 참조함 (BC 경계 넘어도 허용)
//
// 최소 강제 조건(운영 로직에서 검증):
//   - tgt.isKey = true 인 경우만 생성
//   - 생성 시 src.isForeignKey = true 세팅
//
// ############################################################
MATCH (src:Property {parentType: "ReadModel", parentId: "<readModelId>", name: "orderId"})
MATCH (tgt:Property {parentType: "Aggregate", parentId: "<aggregateId>", name: "id"})
CREATE (src)-[:REFERENCES]->(tgt);


// ############################################################
// 13. HAS_GIVEN
// ############################################################
// 방향: Command/Policy → Given
// 의미: Command/Policy가 Given 구성 요소를 가짐
//
// ############################################################

MATCH (cmd:Command {key: "order.order.cancel-order"})
MATCH (given:Given {parentType: "Command", parentId: cmd.id})
CREATE (cmd)-[:HAS_GIVEN]->(given);


// ############################################################
// 14. HAS_WHEN
// ############################################################
// 방향: Command/Policy → When
// 의미: Command/Policy가 When 구성 요소를 가짐
//
// ############################################################

MATCH (cmd:Command {key: "order.order.cancel-order"})
MATCH (when:When {parentType: "Command", parentId: cmd.id})
CREATE (cmd)-[:HAS_WHEN]->(when);


// ############################################################
// 15. HAS_THEN
// ############################################################
// 방향: Command/Policy → Then
// 의미: Command/Policy가 Then 구성 요소를 가짐
//
// ############################################################

MATCH (cmd:Command {key: "order.order.cancel-order"})
MATCH (then:Then {parentType: "Command", parentId: cmd.id})
CREATE (cmd)-[:HAS_THEN]->(then);


// ============================================================
// Feature 016 — Figma Document Binding 관계 정의
// ============================================================
//
// MAPS_STORYBOARD : (FigmaBinding)-[:MAPS_STORYBOARD]->(StoryboardPageMapping)
//   - 활성 바인딩이 보유한 storyboard ↔ Figma 페이지 매핑들
//   - replace 시 기존은 status='archived' 처리, 새 매핑은 신규 생성
//
// MAPS : (StoryboardPageMapping)-[:MAPS]->(Command)
//   - 한 매핑이 가리키는 entry Command (= storyboard의 식별자)
//
// LOGGED : (BindingHistoryEvent)-[:LOGGED]->(FigmaBinding)
//   - append-only 감사 이벤트 → 활성 바인딩
//
// ============================================================


// ============================================================
// Feature 020 — Figma Sync Recovery 관계 정의
// ============================================================
//
// RUN_OF : (SyncRun)-[:RUN_OF]->(FigmaBinding)
//   - 한 :SyncRun 은 dispatch 시점의 binding 을 가리킨다.
//   - cardinality: many → 1 (한 binding 에 여러 run; replace 후 새 run 들은
//     새 binding 을 가리키며 이전 run 들은 그대로 이전 binding 노드를 가리키지만
//     :FigmaBinding 은 singleton 이라 동일 노드 — 식별은 :SyncRun.bindingFileKey
//     로 함).
//   - 사용처: GET /api/figma-binding/sync-runs 가 binding 별 run 을 fetch 할 때.
//
// ============================================================


// ============================================================
// Event Storming Flow 시각화
// ============================================================
//
//  ┌─────────────────────────────────────────────────────────┐
//  │  BC: Order                                              │
//  │  ┌───────────┐    ┌─────────────┐    ┌──────────────┐  │
//  │  │ Aggregate │───>│   Command   │───>│    Event     │  │
//  │  │   Order   │    │ CancelOrder │    │OrderCancelled│──┼──┐
//  │  └───────────┘    └─────────────┘    └──────────────┘  │  │
//  └─────────────────────────────────────────────────────────┘  │
//                                                               │
//  ┌─────────────────────────────────────────────────────────┐  │
//  │  BC: Payment                                            │  │
//  │  ┌──────────────────┐    ┌───────────────┐              │  │
//  │  │      Policy      │<───┤   (Event)     │<─────────────┼──┘
//  │  │RefundOnCancel    │    │               │              │
//  │  └────────┬─────────┘    └───────────────┘              │
//  │           │                                             │
//  │           ▼                                             │
//  │  ┌───────────────┐    ┌──────────────────┐              │
//  │  │    Command    │───>│      Event       │              │
//  │  │ ProcessRefund │    │ RefundProcessed  │              │
//  │  └───────────────┘    └──────────────────┘              │
//  └─────────────────────────────────────────────────────────┘
//
// ============================================================


// ############################################################
// HAS_JOURNEY / HAS_STEP / SHOWS / NEXT — 사용자 여정 그래프 (025 v3)
// ############################################################
// 사용자 여정 레이어. 기존 데이터 흐름(UI→Command→Event→ReadModel→UI)과는
// 별개. 흐름은 JourneyStep 간 NEXT 엣지로 표현(분기 가능).
//
// HAS_JOURNEY: BoundedContext → Journey   (소유 — 화면이 가장 많은 BC)
// HAS_STEP:    Journey → JourneyStep
// SHOWS:       JourneyStep → UI           (screen 단계만; UI 는 여정 간 공유)
// NEXT:        JourneyStep → JourneyStep  (흐름 엣지)
//   - id: String (UUID v5, `uuid5(NS, "<src.step.key>-><tgt.step.key>#<slug(condition)>")`)
//   - condition: String (gateway 출구 분기 라벨; 그 외 "")
//   - documentExcerpt: String (원본 문서 인용; ≤500자)
//   - source: String ("llm" | "manual")
//   - createdAt / updatedAt: DateTime
// ############################################################

MATCH (bc:BoundedContext {id: "<bc-id>"})
MATCH (j:Journey {id: "<journey-id>"})
MERGE (bc)-[:HAS_JOURNEY]->(j);

MATCH (j:Journey {id: "<journey-id>"})
MATCH (s:JourneyStep {id: "<step-id>"})
MERGE (j)-[:HAS_STEP]->(s);

MATCH (s:JourneyStep {id: "<screen-step-id>"})
MATCH (u:UI {id: "<ui-id>"})
MERGE (s)-[:SHOWS]->(u);

MATCH (a:JourneyStep {id: "<step-a-id>"})
MATCH (b:JourneyStep {id: "<step-b-id>"})
MERGE (a)-[r:NEXT {id: "<deterministic-uuid5>"}]->(b)
ON CREATE SET r.createdAt = datetime()
SET r.condition = "",
    r.documentExcerpt = "원본 문서 인용",
    r.source = "llm",
    r.updatedAt = datetime();


// ############################################################
// HAS_FEATURE / HAS_USER_STORY — 요구사항 그룹 계층 (026 requirements-tab)
// ############################################################
// Epic(BC) → Feature → UserStory 드릴다운 계층.
// UserStory의 BC 소속은 기존 UserStory-[:IMPLEMENTS]->BoundedContext 유지.
//
// HAS_FEATURE: BoundedContext → Feature   (BC가 Feature 소유)
//   - createdAt: DateTime
//
// HAS_USER_STORY: Feature → UserStory     (Feature가 US 포함)
//   - 카디널리티: UserStory는 최대 1개 Feature에 소속(없으면 미분류)
//   - source: String ("llm" | "manual") — 자동 분류/수동 재배치 구분
//   - confidence: Float (LLM 분류 신뢰도; manual은 생략 가능)
//   - createdAt: DateTime
//
// drag-n-drop 재배치 = 기존 HAS_USER_STORY 1개 삭제 후 대상 Feature로
// 신규 MERGE(source='manual'). 재인제스트는 source='manual' 관계를 보존.
// ############################################################

MATCH (bc:BoundedContext { key: "order" })
MATCH (f:Feature { key: "order.feature.order-cancellation" })
MERGE (bc)-[hf:HAS_FEATURE]->(f)
ON CREATE SET hf.createdAt = datetime();

MATCH (f:Feature { key: "order.feature.order-cancellation" })
MATCH (us:UserStory { id: "US-001" })
MERGE (f)-[hus:HAS_USER_STORY]->(us)
ON CREATE SET hus.createdAt = datetime()
SET hus.source = "llm", hus.confidence = 0.9;


// ############################################################
// HAS_INVARIANT / VERIFIED_BY — 인베리언트 그래프 (027 aggregate-invariants)
// ############################################################
// HAS_INVARIANT: Aggregate → Invariant
//   - 어그리거트가 보유하는 인베리언트(불변식). cardinality 1 → many.
//
// VERIFIED_BY: Invariant → Command
//   - 인베리언트의 세부 검증 조건이 커맨드의 GWT 인수조건을 "공유 참조"함.
//   - cardinality many → many (한 커맨드 GWT가 여러 인베리언트에서 공유될 수 있고
//     한 인베리언트가 여러 커맨드를 참조할 수 있음).
//   - 공유 참조이므로 GWT 노드는 물리적으로 1개 — 어느 쪽에서 편집해도 자동 전파.
//   - VERIFIED_BY 엣지 1개를 지워도 커맨드 GWT 자체는 보존됨.
//
// 인베리언트 전용 GWT는 HAS_GWT(Invariant → GWT, parentType="Invariant")로 표현하며
// 별도 관계 정의 없이 기존 HAS_GWT 관계를 재사용한다.
// ############################################################

MATCH (agg:Aggregate { key: "order.order" })
MATCH (inv:Invariant { key: "order.order.invariant.order-total-positive-abc123def456" })
MERGE (agg)-[:HAS_INVARIANT]->(inv);

MATCH (inv:Invariant { key: "order.order.invariant.order-total-positive-abc123def456" })
MATCH (cmd:Command { key: "order.order.cancel-order" })
MERGE (inv)-[vb:VERIFIED_BY]->(cmd)
ON CREATE SET vb.createdAt = datetime();
