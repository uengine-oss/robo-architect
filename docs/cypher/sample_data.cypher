// ============================================================
// Event Storming Impact Analysis - Sample Data
// ============================================================
// "주문 취소" 시나리오 기반 샘플 데이터
// 
// 핵심 패턴:
//   Order BC의 OrderCancelled Event가 발생하면
//   → Payment BC의 RefundOnCancel Policy가 반응
//   → Inventory BC의 RestoreStock Policy가 반응
//   → Notification BC의 NotifyOnCancel Policy가 반응
// ============================================================

// ############################################################
// STEP 1: BoundedContext 생성
// ############################################################

CREATE (bcOrder:BoundedContext {
    id: "BC-ORDER",
    name: "Order",
    description: "주문 생성, 수정, 취소 및 주문 상태 관리",
    owner: "Order Team"
});

CREATE (bcPayment:BoundedContext {
    id: "BC-PAYMENT",
    name: "Payment",
    description: "결제 처리 및 환불 관리",
    owner: "Payment Team"
});

CREATE (bcInventory:BoundedContext {
    id: "BC-INVENTORY",
    name: "Inventory",
    description: "상품 재고 관리",
    owner: "Inventory Team"
});

CREATE (bcNotification:BoundedContext {
    id: "BC-NOTIFICATION",
    name: "Notification",
    description: "이메일, SMS 등 알림 발송",
    owner: "Platform Team"
});


// ############################################################
// STEP 2: UserStory 생성
// ############################################################

CREATE (us1:UserStory {
    id: "US-001",
    role: "customer",
    action: "cancel my order",
    benefit: "I can get a refund if I change my mind",
    priority: "high",
    status: "approved"
});

CREATE (us2:UserStory {
    id: "US-002",
    role: "customer",
    action: "place an order",
    benefit: "I can purchase products I need",
    priority: "high",
    status: "implemented"
});


// ############################################################
// STEP 3: Aggregate 생성 (각 BC별)
// ############################################################

// Order BC
CREATE (aggOrder:Aggregate {
    id: "AGG-ORDER",
    name: "Order",
    rootEntity: "Order",
    invariants: ["주문 총액 > 0", "배송 후 취소 불가"]
});

// Payment BC
CREATE (aggPayment:Aggregate {
    id: "AGG-PAYMENT",
    name: "Payment",
    rootEntity: "Payment",
    invariants: ["환불액 <= 결제액"]
});

// Inventory BC
CREATE (aggInventory:Aggregate {
    id: "AGG-INVENTORY",
    name: "Inventory",
    rootEntity: "InventoryItem",
    invariants: ["재고 >= 0"]
});

// Notification BC
CREATE (aggNotification:Aggregate {
    id: "AGG-NOTIFICATION",
    name: "Notification",
    rootEntity: "Notification"
});


// ############################################################
// STEP 4: Command 생성 (각 BC별)
// ############################################################

// Order BC Commands
CREATE (cmdPlaceOrder:Command {
    id: "CMD-PLACE-ORDER",
    name: "PlaceOrder",
    actor: "customer"
});

CREATE (cmdCancelOrder:Command {
    id: "CMD-CANCEL-ORDER",
    name: "CancelOrder",
    actor: "customer"
});

// Payment BC Commands
CREATE (cmdProcessPayment:Command {
    id: "CMD-PROCESS-PAYMENT",
    name: "ProcessPayment",
    actor: "system"
});

CREATE (cmdProcessRefund:Command {
    id: "CMD-PROCESS-REFUND",
    name: "ProcessRefund",
    actor: "system"
});

// Inventory BC Commands
CREATE (cmdReserveStock:Command {
    id: "CMD-RESERVE-STOCK",
    name: "ReserveStock",
    actor: "system"
});

CREATE (cmdRestoreStock:Command {
    id: "CMD-RESTORE-STOCK",
    name: "RestoreStock",
    actor: "system"
});

// Notification BC Commands
CREATE (cmdSendEmail:Command {
    id: "CMD-SEND-EMAIL",
    name: "SendEmail",
    actor: "system"
});


// ############################################################
// STEP 5: Event 생성 (각 BC별)
// ############################################################

// Order BC Events
CREATE (evtOrderPlaced:Event {
    id: "EVT-ORDER-PLACED",
    name: "OrderPlaced",
    version: "1.0.0",
    isBreaking: false
});

CREATE (evtOrderCancelled:Event {
    id: "EVT-ORDER-CANCELLED",
    name: "OrderCancelled",
    version: "1.0.0",
    isBreaking: false
});

// Payment BC Events
CREATE (evtPaymentCompleted:Event {
    id: "EVT-PAYMENT-COMPLETED",
    name: "PaymentCompleted",
    version: "1.0.0",
    isBreaking: false
});

CREATE (evtRefundProcessed:Event {
    id: "EVT-REFUND-PROCESSED",
    name: "RefundProcessed",
    version: "1.0.0",
    isBreaking: false
});

// Inventory BC Events
CREATE (evtStockReserved:Event {
    id: "EVT-STOCK-RESERVED",
    name: "StockReserved",
    version: "1.0.0",
    isBreaking: false
});

CREATE (evtStockRestored:Event {
    id: "EVT-STOCK-RESTORED",
    name: "StockRestored",
    version: "1.0.0",
    isBreaking: false
});

// Notification BC Events
CREATE (evtEmailSent:Event {
    id: "EVT-EMAIL-SENT",
    name: "EmailSent",
    version: "1.0.0",
    isBreaking: false
});


// ############################################################
// STEP 6: Policy 생성 (각 BC별 - 외부 Event에 반응)
// ############################################################

// Payment BC Policy (Order Event에 반응)
CREATE (polProcessPayment:Policy {
    id: "POL-PROCESS-PAYMENT",
    name: "ProcessPaymentOnOrderPlaced",
    description: "When OrderPlaced then ProcessPayment"
});

CREATE (polRefundOnCancel:Policy {
    id: "POL-REFUND-ON-CANCEL",
    name: "RefundOnOrderCancelled",
    description: "When OrderCancelled then ProcessRefund"
});

// Inventory BC Policy (Order Event에 반응)
CREATE (polReserveStock:Policy {
    id: "POL-RESERVE-STOCK",
    name: "ReserveStockOnOrderPlaced",
    description: "When OrderPlaced then ReserveStock"
});

CREATE (polRestoreStock:Policy {
    id: "POL-RESTORE-STOCK",
    name: "RestoreStockOnOrderCancelled",
    description: "When OrderCancelled then RestoreStock"
});

// Notification BC Policy (여러 Event에 반응)
CREATE (polNotifyOrderPlaced:Policy {
    id: "POL-NOTIFY-ORDER-PLACED",
    name: "NotifyOnOrderPlaced",
    description: "When OrderPlaced then SendEmail"
});

CREATE (polNotifyOrderCancelled:Policy {
    id: "POL-NOTIFY-ORDER-CANCELLED",
    name: "NotifyOnOrderCancelled",
    description: "When OrderCancelled then SendEmail"
});

CREATE (polNotifyRefund:Policy {
    id: "POL-NOTIFY-REFUND",
    name: "NotifyOnRefundProcessed",
    description: "When RefundProcessed then SendEmail"
});


// ############################################################
// STEP 7: UserStory → BC/Aggregate (IMPLEMENTS)
// ############################################################

MATCH (us:UserStory {id: "US-001"}), (bc:BoundedContext {id: "BC-ORDER"})
CREATE (us)-[:IMPLEMENTS {confidence: 0.95}]->(bc);

MATCH (us:UserStory {id: "US-001"}), (agg:Aggregate {id: "AGG-ORDER"})
CREATE (us)-[:IMPLEMENTS {confidence: 0.92}]->(agg);

MATCH (us:UserStory {id: "US-002"}), (bc:BoundedContext {id: "BC-ORDER"})
CREATE (us)-[:IMPLEMENTS {confidence: 0.98}]->(bc);

MATCH (us:UserStory {id: "US-002"}), (agg:Aggregate {id: "AGG-ORDER"})
CREATE (us)-[:IMPLEMENTS {confidence: 0.95}]->(agg);


// ############################################################
// STEP 8: BC → Aggregate (HAS_AGGREGATE)
// ############################################################

MATCH (bc:BoundedContext {id: "BC-ORDER"}), (agg:Aggregate {id: "AGG-ORDER"})
CREATE (bc)-[:HAS_AGGREGATE {isPrimary: true}]->(agg);

MATCH (bc:BoundedContext {id: "BC-PAYMENT"}), (agg:Aggregate {id: "AGG-PAYMENT"})
CREATE (bc)-[:HAS_AGGREGATE {isPrimary: true}]->(agg);

MATCH (bc:BoundedContext {id: "BC-INVENTORY"}), (agg:Aggregate {id: "AGG-INVENTORY"})
CREATE (bc)-[:HAS_AGGREGATE {isPrimary: true}]->(agg);

MATCH (bc:BoundedContext {id: "BC-NOTIFICATION"}), (agg:Aggregate {id: "AGG-NOTIFICATION"})
CREATE (bc)-[:HAS_AGGREGATE {isPrimary: true}]->(agg);


// ############################################################
// STEP 9: BC → Policy (HAS_POLICY)
// ############################################################

// Payment BC owns its policies
MATCH (bc:BoundedContext {id: "BC-PAYMENT"}), (pol:Policy {id: "POL-PROCESS-PAYMENT"})
CREATE (bc)-[:HAS_POLICY]->(pol);

MATCH (bc:BoundedContext {id: "BC-PAYMENT"}), (pol:Policy {id: "POL-REFUND-ON-CANCEL"})
CREATE (bc)-[:HAS_POLICY]->(pol);

// Inventory BC owns its policies
MATCH (bc:BoundedContext {id: "BC-INVENTORY"}), (pol:Policy {id: "POL-RESERVE-STOCK"})
CREATE (bc)-[:HAS_POLICY]->(pol);

MATCH (bc:BoundedContext {id: "BC-INVENTORY"}), (pol:Policy {id: "POL-RESTORE-STOCK"})
CREATE (bc)-[:HAS_POLICY]->(pol);

// Notification BC owns its policies
MATCH (bc:BoundedContext {id: "BC-NOTIFICATION"}), (pol:Policy {id: "POL-NOTIFY-ORDER-PLACED"})
CREATE (bc)-[:HAS_POLICY]->(pol);

MATCH (bc:BoundedContext {id: "BC-NOTIFICATION"}), (pol:Policy {id: "POL-NOTIFY-ORDER-CANCELLED"})
CREATE (bc)-[:HAS_POLICY]->(pol);

MATCH (bc:BoundedContext {id: "BC-NOTIFICATION"}), (pol:Policy {id: "POL-NOTIFY-REFUND"})
CREATE (bc)-[:HAS_POLICY]->(pol);


// ############################################################
// STEP 10: Aggregate → Command (HAS_COMMAND)
// ############################################################

// Order Aggregate
MATCH (agg:Aggregate {id: "AGG-ORDER"}), (cmd:Command {id: "CMD-PLACE-ORDER"})
CREATE (agg)-[:HAS_COMMAND]->(cmd);

MATCH (agg:Aggregate {id: "AGG-ORDER"}), (cmd:Command {id: "CMD-CANCEL-ORDER"})
CREATE (agg)-[:HAS_COMMAND]->(cmd);

// Payment Aggregate
MATCH (agg:Aggregate {id: "AGG-PAYMENT"}), (cmd:Command {id: "CMD-PROCESS-PAYMENT"})
CREATE (agg)-[:HAS_COMMAND]->(cmd);

MATCH (agg:Aggregate {id: "AGG-PAYMENT"}), (cmd:Command {id: "CMD-PROCESS-REFUND"})
CREATE (agg)-[:HAS_COMMAND]->(cmd);

// Inventory Aggregate
MATCH (agg:Aggregate {id: "AGG-INVENTORY"}), (cmd:Command {id: "CMD-RESERVE-STOCK"})
CREATE (agg)-[:HAS_COMMAND]->(cmd);

MATCH (agg:Aggregate {id: "AGG-INVENTORY"}), (cmd:Command {id: "CMD-RESTORE-STOCK"})
CREATE (agg)-[:HAS_COMMAND]->(cmd);

// Notification Aggregate
MATCH (agg:Aggregate {id: "AGG-NOTIFICATION"}), (cmd:Command {id: "CMD-SEND-EMAIL"})
CREATE (agg)-[:HAS_COMMAND]->(cmd);


// ############################################################
// STEP 11: Command → Event (EMITS)
// ############################################################

// Order BC
MATCH (cmd:Command {id: "CMD-PLACE-ORDER"}), (evt:Event {id: "EVT-ORDER-PLACED"})
CREATE (cmd)-[:EMITS]->(evt);

MATCH (cmd:Command {id: "CMD-CANCEL-ORDER"}), (evt:Event {id: "EVT-ORDER-CANCELLED"})
CREATE (cmd)-[:EMITS]->(evt);

// Payment BC
MATCH (cmd:Command {id: "CMD-PROCESS-PAYMENT"}), (evt:Event {id: "EVT-PAYMENT-COMPLETED"})
CREATE (cmd)-[:EMITS]->(evt);

MATCH (cmd:Command {id: "CMD-PROCESS-REFUND"}), (evt:Event {id: "EVT-REFUND-PROCESSED"})
CREATE (cmd)-[:EMITS]->(evt);

// Inventory BC
MATCH (cmd:Command {id: "CMD-RESERVE-STOCK"}), (evt:Event {id: "EVT-STOCK-RESERVED"})
CREATE (cmd)-[:EMITS]->(evt);

MATCH (cmd:Command {id: "CMD-RESTORE-STOCK"}), (evt:Event {id: "EVT-STOCK-RESTORED"})
CREATE (cmd)-[:EMITS]->(evt);

// Notification BC
MATCH (cmd:Command {id: "CMD-SEND-EMAIL"}), (evt:Event {id: "EVT-EMAIL-SENT"})
CREATE (cmd)-[:EMITS]->(evt);


// ############################################################
// STEP 12: Event → Policy (TRIGGERS) - Cross-BC Communication!
// ############################################################

// OrderPlaced triggers policies in other BCs
MATCH (evt:Event {id: "EVT-ORDER-PLACED"}), (pol:Policy {id: "POL-PROCESS-PAYMENT"})
CREATE (evt)-[:TRIGGERS {priority: 1}]->(pol);

MATCH (evt:Event {id: "EVT-ORDER-PLACED"}), (pol:Policy {id: "POL-RESERVE-STOCK"})
CREATE (evt)-[:TRIGGERS {priority: 2}]->(pol);

MATCH (evt:Event {id: "EVT-ORDER-PLACED"}), (pol:Policy {id: "POL-NOTIFY-ORDER-PLACED"})
CREATE (evt)-[:TRIGGERS {priority: 3}]->(pol);

// OrderCancelled triggers policies in other BCs
MATCH (evt:Event {id: "EVT-ORDER-CANCELLED"}), (pol:Policy {id: "POL-REFUND-ON-CANCEL"})
CREATE (evt)-[:TRIGGERS {priority: 1}]->(pol);

MATCH (evt:Event {id: "EVT-ORDER-CANCELLED"}), (pol:Policy {id: "POL-RESTORE-STOCK"})
CREATE (evt)-[:TRIGGERS {priority: 2}]->(pol);

MATCH (evt:Event {id: "EVT-ORDER-CANCELLED"}), (pol:Policy {id: "POL-NOTIFY-ORDER-CANCELLED"})
CREATE (evt)-[:TRIGGERS {priority: 3}]->(pol);

// RefundProcessed triggers notification
MATCH (evt:Event {id: "EVT-REFUND-PROCESSED"}), (pol:Policy {id: "POL-NOTIFY-REFUND"})
CREATE (evt)-[:TRIGGERS {priority: 1}]->(pol);


// ############################################################
// STEP 13: Policy → Command (INVOKES) - Same BC
// ############################################################

// Payment BC
MATCH (pol:Policy {id: "POL-PROCESS-PAYMENT"}), (cmd:Command {id: "CMD-PROCESS-PAYMENT"})
CREATE (pol)-[:INVOKES]->(cmd);

MATCH (pol:Policy {id: "POL-REFUND-ON-CANCEL"}), (cmd:Command {id: "CMD-PROCESS-REFUND"})
CREATE (pol)-[:INVOKES]->(cmd);

// Inventory BC
MATCH (pol:Policy {id: "POL-RESERVE-STOCK"}), (cmd:Command {id: "CMD-RESERVE-STOCK"})
CREATE (pol)-[:INVOKES]->(cmd);

MATCH (pol:Policy {id: "POL-RESTORE-STOCK"}), (cmd:Command {id: "CMD-RESTORE-STOCK"})
CREATE (pol)-[:INVOKES]->(cmd);

// Notification BC
MATCH (pol:Policy {id: "POL-NOTIFY-ORDER-PLACED"}), (cmd:Command {id: "CMD-SEND-EMAIL"})
CREATE (pol)-[:INVOKES]->(cmd);

MATCH (pol:Policy {id: "POL-NOTIFY-ORDER-CANCELLED"}), (cmd:Command {id: "CMD-SEND-EMAIL"})
CREATE (pol)-[:INVOKES]->(cmd);

MATCH (pol:Policy {id: "POL-NOTIFY-REFUND"}), (cmd:Command {id: "CMD-SEND-EMAIL"})
CREATE (pol)-[:INVOKES]->(cmd);


// ############################################################
// 데이터 검증 쿼리
// ############################################################

// 전체 플로우 확인: OrderCancelled → 영향받는 모든 BC
// MATCH path = (evt:Event {name: "OrderCancelled"})-[:TRIGGERS]->(pol:Policy)<-[:HAS_POLICY]-(bc:BoundedContext)
// RETURN evt.name, pol.name, bc.name;

// 체이닝 확인: Command → Event → Policy → Command
// MATCH chain = (cmd1:Command)-[:EMITS]->(evt:Event)-[:TRIGGERS]->(pol:Policy)-[:INVOKES]->(cmd2:Command)
// RETURN cmd1.name, evt.name, pol.name, cmd2.name;
