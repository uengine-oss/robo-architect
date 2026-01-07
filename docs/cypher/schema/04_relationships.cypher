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
