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
MATCH (bc:BoundedContext {id: "BC-ORDER"})
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

MATCH (bc:BoundedContext {id: "BC-ORDER"})
MATCH (agg:Aggregate {id: "AGG-ORDER"})
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

MATCH (bc:BoundedContext {id: "BC-PAYMENT"})
MATCH (pol:Policy {id: "POL-REFUND-ON-CANCEL"})
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

MATCH (agg:Aggregate {id: "AGG-ORDER"})
MATCH (cmd:Command {id: "CMD-CANCEL-ORDER"})
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

MATCH (cmd:Command {id: "CMD-CANCEL-ORDER"})
MATCH (evt:Event {id: "EVT-ORDER-CANCELLED"})
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

MATCH (evt:Event {id: "EVT-ORDER-CANCELLED"})
MATCH (pol:Policy {id: "POL-REFUND-ON-CANCEL"})
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

MATCH (pol:Policy {id: "POL-REFUND-ON-CANCEL"})
MATCH (cmd:Command {id: "CMD-PROCESS-REFUND"})
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

MATCH (bc1:BoundedContext {id: "BC-ORDER"})
MATCH (bc2:BoundedContext {id: "BC-PAYMENT"})
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

MATCH (bc:BoundedContext {id: "BC-ORDER"})
MATCH (ui:UI {id: "UI-CMD-CANCEL-ORDER"})
CREATE (bc)-[:HAS_UI]->(ui);


// ############################################################
// 10. ATTACHED_TO
// ############################################################
// 방향: UI → Command/ReadModel
// 의미: UI가 특정 Command/ReadModel에 부착됨 (화면이 어떤 액션/조회에 대응하는지)
//
// ############################################################

MATCH (ui:UI {id: "UI-CMD-CANCEL-ORDER"})
MATCH (cmd:Command {id: "CMD-CANCEL-ORDER"})
CREATE (ui)-[:ATTACHED_TO]->(cmd);


// ############################################################
// 11. HAS_PROPERTY
// ############################################################
// 방향: (Aggregate|Command|Event|ReadModel|UI) → Property
// 의미: 해당 객체가 특정 속성을 포함함
//
// ############################################################

MATCH (cmd:Command {id: "CMD-CANCEL-ORDER"})
MATCH (prop:Property {id: "PROP-ORDER-ID"})
CREATE (cmd)-[:HAS_PROPERTY]->(prop);


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
