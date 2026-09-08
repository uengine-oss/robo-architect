"""배달앱(음식 주문) 데모 도메인 모델 시드 — LLM 호출 없이 순수 Cypher.

제품 브로슈어 스크린샷용으로 각 탭(Contexts / Stories / Design canvas /
Event modeling / Data)이 실제 내용을 렌더링하도록 일관된 소규모 모델을 만든다.

    env -u NEO4J_PASSWORD -u NEO4J_USER -u NEO4J_URI PYTHONPATH=. \
        uv run python scripts/seed_demo_model.py [--wipe]

멱등: 모든 노드를 자연키(key/id)로 MERGE 한다.
--wipe: 이 스크립트가 만든 노드(demoSeed='delivery-demo')만 삭제한다.
        :Proposal 노드는 절대 건드리지 않는다.
"""

from __future__ import annotations

import argparse

from dotenv import load_dotenv

load_dotenv()  # api.platform.neo4j 임포트 전에 .env 해석

from api.platform.neo4j import get_session  # noqa: E402

TAG = "delivery-demo"

# ─────────────────────────────────────────────────────────────────────────────
# 1. BoundedContext
# ─────────────────────────────────────────────────────────────────────────────
BOUNDED_CONTEXTS = [
    {
        "key": "order",
        "name": "주문",
        "displayName": "주문",
        "description": "고객이 가게 메뉴를 장바구니에 담고 주문을 생성·확정·취소하는 핵심 컨텍스트",
        "owner": "주문팀",
        "domainType": "core",
        "classification": "core",
    },
    {
        "key": "delivery",
        "name": "배달",
        "displayName": "배달",
        "description": "확정된 주문에 라이더를 배차하고 픽업부터 배달 완료까지 상태를 추적한다",
        "owner": "배달팀",
        "domainType": "core",
        "classification": "core",
    },
    {
        "key": "payment",
        "name": "결제",
        "displayName": "결제",
        "description": "주문 금액 결제 승인과 주문 취소 시 환불을 처리한다 (PG 연동)",
        "owner": "결제팀",
        "domainType": "supporting",
        "classification": "supporting",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# 2. Feature (BC = Epic 하위 묶음)
# ─────────────────────────────────────────────────────────────────────────────
FEATURES = [
    ("order", "order.feature.menu-cart", "메뉴 탐색·장바구니",
     "고객이 가게 메뉴를 둘러보고 옵션·수량을 골라 장바구니에 담는 기능 묶음", 1),
    ("order", "order.feature.order-place", "주문 접수",
     "장바구니를 주문으로 확정하고 사장님이 접수하기까지의 흐름", 2),
    ("order", "order.feature.order-cancel", "주문 취소·환불",
     "고객이 조리 전 주문을 취소하고 자동으로 환불받는 기능 묶음", 3),
    ("delivery", "delivery.feature.rider-dispatch", "라이더 배차",
     "접수된 주문에 가장 가까운 라이더를 자동 배차한다", 1),
    ("delivery", "delivery.feature.delivery-tracking", "실시간 배달 추적",
     "고객이 픽업부터 배달 완료까지 라이더 위치와 예상 도착 시각을 확인한다", 2),
]

# ─────────────────────────────────────────────────────────────────────────────
# 3. Aggregate + Property
# ─────────────────────────────────────────────────────────────────────────────
AGGREGATES = [
    {
        "bc": "order", "key": "order.cart", "name": "Cart", "displayName": "장바구니",
        "rootEntity": "Cart",
        "props": [
            ("cartId", "UUID", "장바구니 식별자", True, False, True),
            ("customerId", "UUID", "장바구니 소유 고객", False, True, True),
            ("storeId", "UUID", "담긴 메뉴가 속한 가게", False, True, True),
            ("items", "List<CartItem>", "메뉴·옵션·수량 목록", False, False, True),
            ("totalAmount", "Money", "장바구니 총액", False, False, True),
        ],
    },
    {
        "bc": "order", "key": "order.order", "name": "Order", "displayName": "주문",
        "rootEntity": "Order",
        "props": [
            ("orderId", "UUID", "주문 식별자", True, False, True),
            ("customerId", "UUID", "주문한 고객", False, True, True),
            ("storeId", "UUID", "주문을 받은 가게", False, True, True),
            ("status", "OrderStatus", "주문 상태 (PLACED/ACCEPTED/DELIVERING/COMPLETED/CANCELLED)", False, False, True),
            ("orderAmount", "Money", "결제 대상 총 금액", False, False, True),
            ("deliveryAddress", "Address", "배달 주소", False, False, True),
            ("placedAt", "DateTime", "주문 확정 시각", False, False, True),
        ],
        "enumerations": '[{"name":"OrderStatus","values":["PLACED","ACCEPTED","DELIVERING","COMPLETED","CANCELLED"]}]',
        "valueObjects": '[{"name":"Money","fields":[{"name":"amount","type":"Long"},{"name":"currency","type":"String"}]},'
                        '{"name":"Address","fields":[{"name":"roadAddress","type":"String"},{"name":"detail","type":"String"},{"name":"entryNote","type":"String"}]}]',
        "exceptions": '[{"name":"OrderNotCancellable","message":"조리가 시작된 주문은 취소할 수 없습니다","fields":[{"name":"orderId","type":"UUID"}]},'
                      '{"name":"BelowMinimumOrderAmount","message":"가게 최소주문금액에 미달합니다","fields":[{"name":"orderAmount","type":"Money"},{"name":"minimumAmount","type":"Money"}]}]',
    },
    {
        "bc": "delivery", "key": "delivery.delivery", "name": "Delivery", "displayName": "배달",
        "rootEntity": "Delivery",
        "props": [
            ("deliveryId", "UUID", "배달 식별자", True, False, True),
            ("orderId", "UUID", "배달 대상 주문", False, True, True),
            ("riderId", "UUID", "배차된 라이더", False, True, False),
            ("status", "DeliveryStatus", "배달 상태 (ASSIGNED/PICKED_UP/DELIVERING/COMPLETED)", False, False, True),
            ("estimatedArrivalAt", "DateTime", "예상 도착 시각", False, False, False),
        ],
        "enumerations": '[{"name":"DeliveryStatus","values":["ASSIGNED","PICKED_UP","DELIVERING","COMPLETED"]}]',
    },
    {
        "bc": "payment", "key": "payment.payment", "name": "Payment", "displayName": "결제",
        "rootEntity": "Payment",
        "props": [
            ("paymentId", "UUID", "결제 식별자", True, False, True),
            ("orderId", "UUID", "결제 대상 주문", False, True, True),
            ("method", "PaymentMethod", "결제 수단 (CARD/EASY_PAY/POINT)", False, False, True),
            ("amount", "Money", "승인 금액", False, False, True),
            ("approvedAt", "DateTime", "승인 시각", False, False, False),
        ],
        "enumerations": '[{"name":"PaymentMethod","values":["CARD","EASY_PAY","POINT"]}]',
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# 4. Command → Event (타임라인 sequence 포함)
# ─────────────────────────────────────────────────────────────────────────────
COMMANDS = [
    {
        "agg": "order.cart", "key": "order.cart.add-cart-item",
        "name": "AddCartItem", "displayName": "장바구니 담기", "actor": "고객",
        "inputSchema": '{"cartId":"UUID","menuId":"UUID","options":"List<String>","quantity":"Int"}',
        "props": [("menuId", "UUID", "담을 메뉴", False, True, True),
                  ("quantity", "Int", "수량", False, False, True)],
        "event": {"key": "order.cart.add-cart-item.cart-item-added@1.0.0", "name": "CartItemAdded",
                  "displayName": "장바구니 담김", "seq": 1,
                  "schema": '{"cartId":"UUID","menuId":"UUID","quantity":"Int","totalAmount":"Money"}',
                  "props": [("cartId", "UUID", "장바구니 식별자", True, False, True),
                            ("totalAmount", "Money", "담은 뒤 총액", False, False, True)]},
        "gwt": {"given": "장바구니에 담을 메뉴를 선택했다", "when": "Cart", "then": "CartItemAdded",
                "cases": ["옵션과 수량을 고른 뒤 담기를 누르면 하단 바 총액이 즉시 갱신된다",
                          "다른 가게 메뉴를 담으면 장바구니를 비울지 확인 모달이 뜬다"]},
    },
    {
        "agg": "order.order", "key": "order.order.place-order",
        "name": "PlaceOrder", "displayName": "주문하기", "actor": "고객",
        "inputSchema": '{"cartId":"UUID","deliveryAddress":"Address","paymentMethod":"PaymentMethod","requestNote":"String"}',
        "props": [("cartId", "UUID", "주문으로 전환할 장바구니", False, True, True),
                  ("deliveryAddress", "Address", "배달 주소", False, False, True)],
        "event": {"key": "order.order.place-order.order-placed@1.0.0", "name": "OrderPlaced",
                  "displayName": "주문 접수됨", "seq": 2,
                  "schema": '{"orderId":"UUID","customerId":"UUID","storeId":"UUID","orderAmount":"Money","placedAt":"DateTime"}',
                  "props": [("orderId", "UUID", "주문 식별자", True, False, True),
                            ("orderAmount", "Money", "결제 대상 금액", False, False, True)]},
        "gwt": {"given": "장바구니 총액이 가게 최소주문금액 이상이다", "when": "Order", "then": "OrderPlaced",
                "cases": ["주소·요청사항·결제수단을 확인하고 결제하기를 누르면 주문이 생성된다",
                          "최소주문금액 미만이면 BelowMinimumOrderAmount 예외로 결제 버튼이 비활성화된다"]},
    },
    {
        "agg": "payment.payment", "key": "payment.payment.approve-payment",
        "name": "ApprovePayment", "displayName": "결제 승인", "actor": "시스템",
        "inputSchema": '{"orderId":"UUID","amount":"Money","method":"PaymentMethod"}',
        "props": [("orderId", "UUID", "결제 대상 주문", False, True, True)],
        "event": {"key": "payment.payment.approve-payment.payment-approved@1.0.0", "name": "PaymentApproved",
                  "displayName": "결제 승인됨", "seq": 3,
                  "schema": '{"paymentId":"UUID","orderId":"UUID","amount":"Money","approvedAt":"DateTime"}',
                  "props": [("paymentId", "UUID", "결제 식별자", True, False, True),
                            ("orderId", "UUID", "결제 대상 주문", False, True, True)]},
        "gwt": {"given": "주문이 접수되어 결제 요청이 도착했다", "when": "Payment", "then": "PaymentApproved",
                "cases": ["PG 승인이 성공하면 결제 승인 이벤트가 발행된다",
                          "한도 초과 등으로 승인이 거절되면 주문은 자동으로 취소된다"]},
    },
    {
        "agg": "order.order", "key": "order.order.accept-order",
        "name": "AcceptOrder", "displayName": "주문 확정", "actor": "사장님",
        "inputSchema": '{"orderId":"UUID","estimatedCookingMinutes":"Int"}',
        "props": [("estimatedCookingMinutes", "Int", "예상 조리 시간(분)", False, False, True)],
        "event": {"key": "order.order.accept-order.order-accepted@1.0.0", "name": "OrderAccepted",
                  "displayName": "주문 확정됨", "seq": 4,
                  "schema": '{"orderId":"UUID","storeId":"UUID","estimatedCookingMinutes":"Int"}',
                  "props": [("orderId", "UUID", "주문 식별자", True, False, True)]},
        "gwt": {"given": "결제가 승인된 주문이다", "when": "Order", "then": "OrderAccepted",
                "cases": ["사장님이 조리 시간을 입력하고 접수하면 고객에게 확정 알림이 간다"]},
    },
    {
        "agg": "delivery.delivery", "key": "delivery.delivery.assign-rider",
        "name": "AssignRider", "displayName": "라이더 배차", "actor": "시스템",
        "inputSchema": '{"orderId":"UUID","pickupLocation":"Location"}',
        "props": [("orderId", "UUID", "배차 대상 주문", False, True, True)],
        "event": {"key": "delivery.delivery.assign-rider.rider-assigned@1.0.0", "name": "RiderAssigned",
                  "displayName": "라이더 배차됨", "seq": 5,
                  "schema": '{"deliveryId":"UUID","orderId":"UUID","riderId":"UUID","estimatedArrivalAt":"DateTime"}',
                  "props": [("deliveryId", "UUID", "배달 식별자", True, False, True),
                            ("riderId", "UUID", "배차된 라이더", False, True, True)]},
        "gwt": {"given": "주문이 확정되어 배차 요청이 발생했다", "when": "Delivery", "then": "RiderAssigned",
                "cases": ["가게 반경 3km 내 라이더 중 가장 가까운 라이더에게 배차된다",
                          "배차 가능한 라이더가 없으면 30초 간격으로 재시도한다"]},
    },
    {
        "agg": "delivery.delivery", "key": "delivery.delivery.start-delivery",
        "name": "StartDelivery", "displayName": "픽업·배달 시작", "actor": "라이더",
        "inputSchema": '{"deliveryId":"UUID","pickedUpAt":"DateTime"}',
        "props": [("deliveryId", "UUID", "배달 식별자", False, True, True)],
        "event": {"key": "delivery.delivery.start-delivery.delivery-started@1.0.0", "name": "DeliveryStarted",
                  "displayName": "배달 시작됨", "seq": 6,
                  "schema": '{"deliveryId":"UUID","orderId":"UUID","startedAt":"DateTime"}',
                  "props": [("deliveryId", "UUID", "배달 식별자", True, False, True)]},
        "gwt": {"given": "라이더가 가게에서 음식을 수령했다", "when": "Delivery", "then": "DeliveryStarted",
                "cases": ["픽업 완료를 누르면 고객 화면의 상태가 '배달중'으로 바뀐다"]},
    },
    {
        "agg": "delivery.delivery", "key": "delivery.delivery.complete-delivery",
        "name": "CompleteDelivery", "displayName": "배달 완료", "actor": "라이더",
        "inputSchema": '{"deliveryId":"UUID","photoUrl":"String"}',
        "props": [("photoUrl", "String", "전달 완료 사진", False, False, False)],
        "event": {"key": "delivery.delivery.complete-delivery.delivery-completed@1.0.0", "name": "DeliveryCompleted",
                  "displayName": "배달 완료됨", "seq": 7,
                  "schema": '{"deliveryId":"UUID","orderId":"UUID","completedAt":"DateTime"}',
                  "props": [("orderId", "UUID", "배달 대상 주문", False, True, True)]},
        "gwt": {"given": "라이더가 배달지에 도착했다", "when": "Delivery", "then": "DeliveryCompleted",
                "cases": ["전달 사진을 등록하고 완료를 누르면 주문 상태가 COMPLETED 로 바뀐다"]},
    },
    {
        "agg": "order.order", "key": "order.order.cancel-order",
        "name": "CancelOrder", "displayName": "주문 취소", "actor": "고객",
        "inputSchema": '{"orderId":"UUID","reason":"String"}',
        "props": [("orderId", "UUID", "취소할 주문", False, True, True),
                  ("reason", "String", "취소 사유", False, False, True)],
        "event": {"key": "order.order.cancel-order.order-cancelled@1.0.0", "name": "OrderCancelled",
                  "displayName": "주문 취소됨", "seq": 8,
                  "schema": '{"orderId":"UUID","reason":"String","cancelledAt":"DateTime"}',
                  "props": [("orderId", "UUID", "주문 식별자", True, False, True),
                            ("reason", "String", "취소 사유", False, False, True)]},
        "gwt": {"given": "주문이 아직 조리 시작 전이다", "when": "Order", "then": "OrderCancelled",
                "cases": ["조리 시작 전이면 즉시 취소되고 전액 환불이 시작된다",
                          "조리가 시작된 뒤에는 OrderNotCancellable 예외로 취소가 거부된다"]},
    },
    {
        "agg": "payment.payment", "key": "payment.payment.refund-payment",
        "name": "RefundPayment", "displayName": "환불 처리", "actor": "시스템",
        "inputSchema": '{"paymentId":"UUID","refundAmount":"Money"}',
        "props": [("refundAmount", "Money", "환불 금액", False, False, True)],
        "event": {"key": "payment.payment.refund-payment.payment-refunded@1.0.0", "name": "PaymentRefunded",
                  "displayName": "환불 완료됨", "seq": 9,
                  "schema": '{"paymentId":"UUID","orderId":"UUID","refundAmount":"Money","refundedAt":"DateTime"}',
                  "props": [("paymentId", "UUID", "결제 식별자", True, False, True)]},
        "gwt": {"given": "주문이 취소되었다", "when": "Payment", "then": "PaymentRefunded",
                "cases": ["카드 결제는 승인 취소로, 포인트는 즉시 원복으로 환불된다"]},
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# 5. Policy (BC 간 이벤트 → 커맨드 체인)
# ─────────────────────────────────────────────────────────────────────────────
POLICIES = [
    ("payment", "payment.approve-payment-on-order-placed", "ApprovePaymentOnOrderPlaced", "주문 접수 시 결제 승인",
     "주문이 접수되면 등록된 결제수단으로 승인을 요청한다", "OrderPlaced 수신",
     "order.order.place-order.order-placed@1.0.0", "payment.payment.approve-payment"),
    ("order", "order.accept-order-on-payment-approved", "AcceptOrderOnPaymentApproved", "결제 승인 시 가게 접수 요청",
     "결제가 승인되면 가게 포스에 주문 확정 요청을 전달한다", "PaymentApproved 수신",
     "payment.payment.approve-payment.payment-approved@1.0.0", "order.order.accept-order"),
    ("delivery", "delivery.assign-rider-on-order-accepted", "AssignRiderOnOrderAccepted", "주문 확정 시 라이더 배차",
     "주문이 확정되면 조리 완료 예상 시각에 맞춰 라이더를 배차한다", "OrderAccepted 수신",
     "order.order.accept-order.order-accepted@1.0.0", "delivery.delivery.assign-rider"),
    ("payment", "payment.refund-on-order-cancelled", "RefundOnOrderCancelled", "주문 취소 시 환불",
     "주문이 취소되면 승인된 결제를 전액 환불한다", "OrderCancelled 수신",
     "order.order.cancel-order.order-cancelled@1.0.0", "payment.payment.refund-payment"),
]

# ─────────────────────────────────────────────────────────────────────────────
# 6. ReadModel (+ CQRS operation)
# ─────────────────────────────────────────────────────────────────────────────
READMODELS = [
    {
        "bc": "order", "key": "order.readmodel.store-menu", "name": "StoreMenuView",
        "displayName": "가게 메뉴 목록", "actor": "고객", "provisioningType": "CQRS",
        "description": "가게별 카테고리·메뉴·가격·인기 배지를 보여주는 조회 모델",
        "isMultipleResult": "true",
        "props": [("storeId", "UUID", "가게 식별자", True, False, True),
                  ("menuName", "String", "메뉴명", False, False, True),
                  ("price", "Money", "판매가", False, False, True),
                  ("isPopular", "Boolean", "인기 메뉴 여부", False, False, False)],
        "trigger": "order.cart.add-cart-item.cart-item-added@1.0.0",
        "operationType": "UPDATE",
    },
    {
        "bc": "order", "key": "order.readmodel.order-status", "name": "OrderStatusView",
        "displayName": "주문 현황", "actor": "고객", "provisioningType": "CQRS",
        "description": "접수→조리→픽업→배달중→완료 단계를 보여주는 주문 현황 조회 모델",
        "isMultipleResult": "false",
        "props": [("orderId", "UUID", "주문 식별자", True, False, True),
                  ("status", "OrderStatus", "현재 주문 상태", False, False, True),
                  ("storeName", "String", "가게 이름", False, False, True),
                  ("orderAmount", "Money", "결제 금액", False, False, True)],
        "trigger": "order.order.accept-order.order-accepted@1.0.0",
        "operationType": "UPDATE",
    },
    {
        "bc": "delivery", "key": "delivery.readmodel.delivery-tracking", "name": "DeliveryTrackingView",
        "displayName": "실시간 배달 추적", "actor": "고객", "provisioningType": "CQRS",
        "description": "라이더 위치와 예상 도착 시각을 지도 위에 실시간으로 보여주는 조회 모델",
        "isMultipleResult": "false",
        "props": [("deliveryId", "UUID", "배달 식별자", True, False, True),
                  ("riderLocation", "Location", "라이더 현재 위치", False, False, True),
                  ("estimatedArrivalAt", "DateTime", "예상 도착 시각", False, False, True)],
        "trigger": "delivery.delivery.start-delivery.delivery-started@1.0.0",
        "operationType": "UPDATE",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# 7. Invariant
# ─────────────────────────────────────────────────────────────────────────────
INVARIANTS = [
    ("order.order", "order.order.invariant.min-order-amount", "최소주문금액 충족",
     "주문 금액은 가게가 설정한 최소주문금액 이상이어야 한다", 1, "order.order.place-order"),
    ("order.order", "order.order.invariant.cancel-before-cooking", "조리 전에만 취소 가능",
     "주문은 조리가 시작되기 전(status=PLACED 또는 ACCEPTED)에만 취소할 수 있다", 2, "order.order.cancel-order"),
    ("delivery.delivery", "delivery.delivery.invariant.single-rider", "배달당 라이더 1명",
     "하나의 배달에는 동시에 한 명의 라이더만 배차될 수 있다", 1, "delivery.delivery.assign-rider"),
    ("payment.payment", "payment.payment.invariant.refund-le-approved", "환불 금액 상한",
     "환불 금액은 승인된 결제 금액을 초과할 수 없다", 1, "payment.payment.refund-payment"),
]

# ─────────────────────────────────────────────────────────────────────────────
# 8. UI (Command / ReadModel 부착)
# ─────────────────────────────────────────────────────────────────────────────
UIS = [
    ("order", "Command", "order.cart.add-cart-item", "메뉴 상세·옵션 시트",
     "메뉴 사진·설명·옵션 선택과 수량 스텝퍼, 하단 '장바구니 담기' 버튼", "US-002"),
    ("order", "Command", "order.order.place-order", "주문·결제 화면",
     "배달 주소, 요청사항, 결제수단, 쿠폰 섹션과 최종 결제 금액 및 '결제하기' 버튼", "US-003"),
    ("order", "Command", "order.order.cancel-order", "주문 취소 화면",
     "취소 사유 선택과 환불 예정 금액 안내, '주문 취소' 확인 버튼", "US-004"),
    ("order", "ReadModel", "order.readmodel.store-menu", "가게 홈 화면",
     "가게 배너·평점·최소주문금액과 카테고리별 메뉴 카드 리스트", "US-001"),
    ("order", "ReadModel", "order.readmodel.order-status", "주문 현황 화면",
     "접수→조리→픽업→배달중→완료 타임라인과 주문 상세 요약", "US-005"),
    ("delivery", "Command", "delivery.delivery.start-delivery", "라이더 픽업 화면",
     "배차된 주문 카드와 '픽업 완료' 슬라이드 버튼, 가게 전화 걸기", "US-007"),
    ("delivery", "Command", "delivery.delivery.complete-delivery", "라이더 배달 완료 화면",
     "전달 완료 사진 촬영과 '배달 완료' 버튼, 고객 요청사항 표시", "US-008"),
    ("delivery", "ReadModel", "delivery.readmodel.delivery-tracking", "배달 추적 화면",
     "라이더 위치 지도, 예상 도착 시각 카운트다운, 라이더 안전번호 연결", "US-006"),
]

# ─────────────────────────────────────────────────────────────────────────────
# 9. UserStory
# ─────────────────────────────────────────────────────────────────────────────
USER_STORIES = [
    ("US-001", "order", "order.feature.menu-cart", None, "고객",
     "가게의 메뉴를 카테고리별로 훑어보고 옵션과 가격을 확인한다", "원하는 음식을 빠르게 고를 수 있다",
     "high", "approved",
     ["메뉴 카드에 사진·가격·인기 배지가 보인다", "카드를 누르면 옵션 시트가 열린다",
      "최소주문금액과 배달팁이 가게 헤더에 표시된다"]),
    ("US-002", "order", "order.feature.menu-cart", "order.cart.add-cart-item", "고객",
     "옵션과 수량을 골라 메뉴를 장바구니에 담는다", "여러 메뉴를 한 번에 주문할 수 있다",
     "high", "approved",
     ["하단 고정 바에 총액과 '주문하기' 버튼이 보인다", "다른 가게 메뉴를 담으면 확인 모달이 뜬다"]),
    ("US-003", "order", "order.feature.order-place", "order.order.place-order", "고객",
     "배달 주소와 결제수단을 확인하고 주문을 확정한다", "안전하게 결제를 마칠 수 있다",
     "high", "approved",
     ["주소·요청사항·결제수단·쿠폰 섹션이 보인다", "최소주문금액 미만이면 결제 버튼이 비활성화된다"]),
    ("US-004", "order", "order.feature.order-place", "order.order.accept-order", "사장님",
     "들어온 주문을 확인하고 예상 조리 시간을 입력해 접수한다", "주방 상황에 맞춰 주문을 받을 수 있다",
     "high", "approved",
     ["신규 주문이 소리와 함께 포스 화면 상단에 뜬다", "접수 시 고객에게 확정 알림이 발송된다"]),
    ("US-005", "order", "order.feature.order-cancel", "order.order.cancel-order", "고객",
     "조리가 시작되기 전에 주문을 취소한다", "마음이 바뀌어도 전액 환불받을 수 있다",
     "medium", "approved",
     ["취소 사유를 선택하면 환불 예정 금액이 안내된다", "조리 시작 후에는 취소 버튼이 사라진다"]),
    ("US-006", "order", "order.feature.order-cancel", None, "고객",
     "취소한 주문의 환불 진행 상태를 확인한다", "돈이 언제 돌아오는지 알 수 있다",
     "low", "draft",
     ["환불 방식(카드 승인취소/포인트 원복)과 예상 소요일이 표시된다"]),
    ("US-007", "delivery", "delivery.feature.rider-dispatch", "delivery.delivery.assign-rider", "시스템",
     "확정된 주문에 가장 가까운 라이더를 자동 배차한다", "배달 대기 시간을 줄일 수 있다",
     "high", "approved",
     ["가게 반경 3km 내 라이더 중 최단 거리 순으로 배차한다", "가능한 라이더가 없으면 30초 간격으로 재시도한다"]),
    ("US-008", "delivery", "delivery.feature.rider-dispatch", "delivery.delivery.start-delivery", "라이더",
     "가게에서 음식을 수령하고 픽업 완료를 기록한다", "고객에게 정확한 배달 시작을 알릴 수 있다",
     "medium", "approved",
     ["픽업 완료를 누르면 고객 화면 상태가 '배달중'으로 바뀐다"]),
    ("US-009", "delivery", "delivery.feature.delivery-tracking", "delivery.delivery.complete-delivery", "라이더",
     "전달 완료 사진을 등록하고 배달을 완료 처리한다", "비대면 배달 분쟁을 줄일 수 있다",
     "medium", "approved",
     ["사진 없이 완료하면 확인 모달이 한 번 더 뜬다", "완료 시 주문 상태가 COMPLETED 로 바뀐다"]),
    ("US-010", "delivery", "delivery.feature.delivery-tracking", None, "고객",
     "주문 접수부터 배달 완료까지 단계를 실시간으로 본다", "언제 도착할지 알 수 있다",
     "high", "approved",
     ["타임라인(접수→조리→픽업→배달중→완료)이 보인다", "지도에 라이더 위치와 예상 도착 시각이 표시된다"]),
    ("US-011", "payment", None, "payment.payment.approve-payment", "고객",
     "등록된 간편결제 수단으로 즉시 결제를 승인받는다", "복잡한 카드 입력 없이 주문할 수 있다",
     "high", "approved",
     ["승인 실패 시 사유와 함께 다른 결제수단을 제안한다"]),
]

# ─────────────────────────────────────────────────────────────────────────────
# 10. Journey / JourneyStep
# ─────────────────────────────────────────────────────────────────────────────
JOURNEY = {
    "bc": "order",
    "key": "order.journey.food-order",
    "slug": "food-order",
    "name": "음식 주문 여정",
    "description": "메뉴 탐색부터 배달 완료 확인까지 고객이 겪는 전체 흐름",
    "steps": [
        ("browse", "screen", "메뉴 탐색", 1, "ui.readmodel.order.readmodel.store-menu"),
        ("cart", "screen", "장바구니", 2, "ui.command.order.cart.add-cart-item"),
        ("min-amount", "gateway", "최소주문금액 충족?", 3, None),
        ("checkout", "screen", "주문·결제", 4, "ui.command.order.order.place-order"),
        ("status", "screen", "주문 현황", 5, "ui.readmodel.order.readmodel.order-status"),
        ("tracking", "screen", "배달 추적", 6, "ui.readmodel.delivery.readmodel.delivery-tracking"),
        ("cancel", "screen", "주문 취소", 7, "ui.command.order.order.cancel-order"),
    ],
    "next": [
        ("browse", "cart", ""),
        ("cart", "min-amount", ""),
        ("min-amount", "checkout", "총액 ≥ 최소주문금액"),
        ("min-amount", "browse", "총액 < 최소주문금액 — 메뉴 더 담기"),
        ("checkout", "status", ""),
        ("status", "tracking", "주문 확정됨"),
        ("status", "cancel", "조리 시작 전 취소"),
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
def seed(session) -> dict[str, int]:
    counts: dict[str, int] = {}

    def bump(k: str, n: int = 1) -> None:
        counts[k] = counts.get(k, 0) + n

    # --- BoundedContext -----------------------------------------------------
    for bc in BOUNDED_CONTEXTS:
        session.run(
            """
            MERGE (bc:BoundedContext {key: $key})
              ON CREATE SET bc.id = randomUUID(), bc.createdAt = datetime()
            SET bc.name = $name, bc.displayName = $displayName,
                bc.description = $description, bc.owner = $owner,
                bc.domainType = $domainType, bc.classification = $classification,
                bc.demoSeed = $tag, bc.updatedAt = datetime()
            """,
            tag=TAG, **bc,
        ).consume()
        bump("BoundedContext")

    # --- Feature ------------------------------------------------------------
    for bc_key, key, name, desc, seq in FEATURES:
        session.run(
            """
            MATCH (bc:BoundedContext {key: $bc_key})
            MERGE (f:Feature {key: $key})
              ON CREATE SET f.id = randomUUID(), f.createdAt = datetime()
            SET f.name = $name, f.description = $desc, f.source = 'llm',
                f.boundedContextId = bc.id, f.sequence = $seq,
                f.demoSeed = $tag, f.updatedAt = datetime()
            MERGE (bc)-[:HAS_FEATURE]->(f)
            """,
            bc_key=bc_key, key=key, name=name, desc=desc, seq=seq, tag=TAG,
        ).consume()
        bump("Feature")

    # --- Aggregate + Property ----------------------------------------------
    for agg in AGGREGATES:
        session.run(
            """
            MATCH (bc:BoundedContext {key: $bc_key})
            MERGE (a:Aggregate {key: $key})
              ON CREATE SET a.id = randomUUID(), a.createdAt = datetime()
            SET a.name = $name, a.displayName = $displayName,
                a.rootEntity = $rootEntity, a.invariants = [],
                a.enumerations = $enumerations, a.valueObjects = $valueObjects,
                a.exceptions = $exceptions,
                a.demoSeed = $tag, a.updatedAt = datetime()
            MERGE (bc)-[:HAS_AGGREGATE]->(a)
            """,
            bc_key=agg["bc"], key=agg["key"], name=agg["name"],
            displayName=agg["displayName"], rootEntity=agg["rootEntity"],
            enumerations=agg.get("enumerations", "[]"),
            valueObjects=agg.get("valueObjects", "[]"),
            exceptions=agg.get("exceptions", "[]"), tag=TAG,
        ).consume()
        bump("Aggregate")
        bump("Property", _props(session, "Aggregate", "Aggregate", agg["key"], agg["props"]))

    # --- Command / Event / GWT / Property -----------------------------------
    for cmd in COMMANDS:
        session.run(
            """
            MATCH (a:Aggregate {key: $agg})
            MERGE (c:Command {key: $key})
              ON CREATE SET c.id = randomUUID(), c.createdAt = datetime()
            SET c.name = $name, c.displayName = $displayName, c.actor = $actor,
                c.inputSchema = $inputSchema, c.demoSeed = $tag, c.updatedAt = datetime()
            MERGE (a)-[:HAS_COMMAND]->(c)
            """,
            agg=cmd["agg"], key=cmd["key"], name=cmd["name"],
            displayName=cmd["displayName"], actor=cmd["actor"],
            inputSchema=cmd["inputSchema"], tag=TAG,
        ).consume()
        bump("Command")
        bump("Property", _props(session, "Command", "Command", cmd["key"], cmd["props"]))

        ev = cmd["event"]
        session.run(
            """
            MATCH (c:Command {key: $cmd_key})
            MATCH (a:Aggregate {key: $agg})<-[:HAS_AGGREGATE]-(bc:BoundedContext)
            MERGE (e:Event {key: $key})
              ON CREATE SET e.id = randomUUID(), e.createdAt = datetime()
            SET e.name = $name, e.displayName = $displayName, e.version = '1.0.0',
                e.schema = $schema, e.payload = $schema, e.isBreaking = false,
                e.sequence = $seq, e.demoSeed = $tag, e.updatedAt = datetime()
            MERGE (c)-[:EMITS]->(e)
            MERGE (bc)-[:HAS_EVENT]->(e)
            """,
            cmd_key=cmd["key"], agg=cmd["agg"], key=ev["key"], name=ev["name"],
            displayName=ev["displayName"], schema=ev["schema"], seq=ev["seq"], tag=TAG,
        ).consume()
        bump("Event")
        bump("Property", _props(session, "Event", "Event", ev["key"], ev["props"]))

        g = cmd["gwt"]
        import json as _json
        session.run(
            """
            MATCH (c:Command {key: $cmd_key})
            MERGE (gwt:GWT {key: $key})
              ON CREATE SET gwt.id = randomUUID(), gwt.createdAt = datetime()
            SET gwt.parentType = 'Command', gwt.parentId = c.id,
                gwt.givenRef = $given, gwt.whenRef = $when, gwt.thenRef = $then,
                gwt.testCases = $cases, gwt.demoSeed = $tag, gwt.updatedAt = datetime()
            MERGE (c)-[:HAS_GWT]->(gwt)
            """,
            cmd_key=cmd["key"], key="gwt." + cmd["key"],
            given=_json.dumps({"name": g["given"]}, ensure_ascii=False),
            when=_json.dumps({"name": f"Aggregate: {g['when']}"}, ensure_ascii=False),
            then=_json.dumps({"name": f"Event: {g['then']}"}, ensure_ascii=False),
            cases=_json.dumps(
                [{"scenarioDescription": c} for c in g["cases"]], ensure_ascii=False
            ),
            tag=TAG,
        ).consume()
        bump("GWT")

    # --- Policy -------------------------------------------------------------
    for bc_key, key, name, display, desc, cond, evt_key, cmd_key in POLICIES:
        session.run(
            """
            MATCH (bc:BoundedContext {key: $bc_key})
            MATCH (e:Event {key: $evt_key})
            MATCH (c:Command {key: $cmd_key})
            MERGE (p:Policy {key: $key})
              ON CREATE SET p.id = randomUUID(), p.createdAt = datetime()
            SET p.name = $name, p.displayName = $display, p.description = $desc,
                p.condition = $cond, p.demoSeed = $tag, p.updatedAt = datetime()
            MERGE (bc)-[:HAS_POLICY]->(p)
            MERGE (e)-[:TRIGGERS]->(p)
            MERGE (p)-[:INVOKES]->(c)
            """,
            bc_key=bc_key, key=key, name=name, display=display, desc=desc,
            cond=cond, evt_key=evt_key, cmd_key=cmd_key, tag=TAG,
        ).consume()
        bump("Policy")

    # --- ReadModel + CQRS ---------------------------------------------------
    for rm in READMODELS:
        session.run(
            """
            MATCH (bc:BoundedContext {key: $bc_key})
            MERGE (r:ReadModel {key: $key})
              ON CREATE SET r.id = randomUUID(), r.createdAt = datetime()
            SET r.name = $name, r.displayName = $displayName,
                r.description = $description, r.provisioningType = $provisioningType,
                r.actor = $actor, r.isMultipleResult = $isMultipleResult,
                r.demoSeed = $tag, r.updatedAt = datetime()
            MERGE (bc)-[:HAS_READMODEL]->(r)
            """,
            bc_key=rm["bc"], key=rm["key"], name=rm["name"], displayName=rm["displayName"],
            description=rm["description"], provisioningType=rm["provisioningType"],
            actor=rm["actor"], isMultipleResult=rm["isMultipleResult"], tag=TAG,
        ).consume()
        bump("ReadModel")
        bump("Property", _props(session, "ReadModel", "ReadModel", rm["key"], rm["props"]))

        session.run(
            """
            MATCH (r:ReadModel {key: $rm_key})
            MATCH (e:Event {key: $evt_key})
            MERGE (cfg:CQRSConfig {key: $cfg_key})
              ON CREATE SET cfg.id = randomUUID()
            SET cfg.demoSeed = $tag
            MERGE (r)-[:HAS_CQRS]->(cfg)
            MERGE (op:CQRSOperation {key: $op_key})
              ON CREATE SET op.id = randomUUID()
            SET op.operationType = $op_type, op.triggerEventId = e.id, op.demoSeed = $tag
            MERGE (cfg)-[:HAS_OPERATION]->(op)
            MERGE (op)-[:TRIGGERED_BY]->(e)
            """,
            rm_key=rm["key"], evt_key=rm["trigger"],
            cfg_key="cqrs." + rm["key"], op_key="cqrsop." + rm["key"],
            op_type=rm["operationType"], tag=TAG,
        ).consume()
        bump("CQRSConfig")
        bump("CQRSOperation")

    # --- Invariant ----------------------------------------------------------
    for agg_key, key, name, decl, seq, verified_by in INVARIANTS:
        session.run(
            """
            MATCH (a:Aggregate {key: $agg_key})
            MATCH (c:Command {key: $cmd_key})
            MERGE (i:Invariant {key: $key})
              ON CREATE SET i.id = randomUUID(), i.createdAt = datetime()
            SET i.name = $name, i.declaration = $decl, i.source = 'manual',
                i.seq = $seq, i.aggregateId = a.id,
                i.demoSeed = $tag, i.updatedAt = datetime()
            MERGE (a)-[:HAS_INVARIANT]->(i)
            MERGE (i)-[:VERIFIED_BY]->(c)
            """,
            agg_key=agg_key, key=key, name=name, decl=decl, seq=seq,
            cmd_key=verified_by, tag=TAG,
        ).consume()
        bump("Invariant")

    # --- UI -----------------------------------------------------------------
    for bc_key, target_type, target_key, name, desc, us_id in UIS:
        label = "Command" if target_type == "Command" else "ReadModel"
        session.run(
            f"""
            MATCH (bc:BoundedContext {{key: $bc_key}})
            MATCH (t:{label} {{key: $target_key}})
            MERGE (u:UI {{key: $key}})
              ON CREATE SET u.id = randomUUID(), u.createdAt = datetime()
            SET u.name = $name, u.displayName = $name, u.description = $desc,
                u.template = '', u.designSource = 'html',
                u.attachedToId = t.id, u.attachedToType = $target_type,
                u.attachedToName = t.name, u.userStoryId = $us_id,
                u.demoSeed = $tag, u.updatedAt = datetime()
            MERGE (bc)-[:HAS_UI]->(u)
            MERGE (u)-[:ATTACHED_TO]->(t)
            """,
            bc_key=bc_key, target_key=target_key,
            key=f"ui.{target_type.lower()}.{target_key}",
            name=name, desc=desc, target_type=target_type, us_id=us_id, tag=TAG,
        ).consume()
        bump("UI")

    # --- UserStory ----------------------------------------------------------
    for (us_id, bc_key, feature_key, cmd_key, role, action, benefit,
         priority, status, criteria) in USER_STORIES:
        session.run(
            """
            MATCH (bc:BoundedContext {key: $bc_key})
            MERGE (us:UserStory {id: $id})
              ON CREATE SET us.createdAt = datetime()
            SET us.role = $role, us.action = $action, us.benefit = $benefit,
                us.priority = $priority, us.status = $status,
                us.acceptanceCriteria = $criteria,
                us.demoSeed = $tag, us.updatedAt = datetime()
            MERGE (us)-[:IMPLEMENTS]->(bc)
            """,
            bc_key=bc_key, id=us_id, role=role, action=action, benefit=benefit,
            priority=priority, status=status, criteria=criteria, tag=TAG,
        ).consume()
        bump("UserStory")
        if feature_key:
            session.run(
                """
                MATCH (f:Feature {key: $fk}), (us:UserStory {id: $id})
                MERGE (f)-[:HAS_USER_STORY]->(us)
                """,
                fk=feature_key, id=us_id,
            ).consume()
        if cmd_key:
            session.run(
                """
                MATCH (c:Command {key: $ck}), (us:UserStory {id: $id})
                MERGE (us)-[:IMPLEMENTS]->(c)
                """,
                ck=cmd_key, id=us_id,
            ).consume()

    # --- Journey ------------------------------------------------------------
    j = JOURNEY
    session.run(
        """
        MATCH (bc:BoundedContext {key: $bc_key})
        MERGE (jn:Journey {key: $key})
          ON CREATE SET jn.id = randomUUID(), jn.createdAt = datetime()
        SET jn.journeyId = $slug, jn.name = $name, jn.description = $desc,
            jn.boundedContextId = bc.id, jn.source = 'llm',
            jn.demoSeed = $tag, jn.updatedAt = datetime()
        MERGE (bc)-[:HAS_JOURNEY]->(jn)
        """,
        bc_key=j["bc"], key=j["key"], slug=j["slug"], name=j["name"],
        desc=j["description"], tag=TAG,
    ).consume()
    bump("Journey")

    for ref, kind, label, seq, ui_key in j["steps"]:
        session.run(
            """
            MATCH (jn:Journey {key: $jkey})
            MERGE (s:JourneyStep {key: $key})
              ON CREATE SET s.id = randomUUID(), s.createdAt = datetime()
            SET s.kind = $kind, s.label = $label, s.sequence = $seq,
                s.journeyId = $slug, s.source = 'llm',
                s.demoSeed = $tag, s.updatedAt = datetime()
            MERGE (jn)-[:HAS_STEP]->(s)
            """,
            jkey=j["key"], key=f"{j['key']}.step.{kind}.{ref}", kind=kind,
            label=label, seq=seq, slug=j["slug"], tag=TAG,
        ).consume()
        bump("JourneyStep")
        if ui_key:
            session.run(
                """
                MATCH (s:JourneyStep {key: $skey}), (u:UI {key: $ukey})
                MERGE (s)-[:SHOWS]->(u)
                """,
                skey=f"{j['key']}.step.{kind}.{ref}", ukey=ui_key,
            ).consume()

    step_kind = {ref: kind for ref, kind, _, _, _ in j["steps"]}
    for src, tgt, cond in j["next"]:
        session.run(
            """
            MATCH (a:JourneyStep {key: $akey}), (b:JourneyStep {key: $bkey})
            MERGE (a)-[r:NEXT {id: $id}]->(b)
              ON CREATE SET r.createdAt = datetime()
            SET r.condition = $cond, r.documentExcerpt = '', r.source = 'llm',
                r.updatedAt = datetime()
            """,
            akey=f"{j['key']}.step.{step_kind[src]}.{src}",
            bkey=f"{j['key']}.step.{step_kind[tgt]}.{tgt}",
            id=f"{j['key']}.next.{src}->{tgt}", cond=cond,
        ).consume()
        bump("NEXT")

    return counts


def _props(session, label: str, parent_type: str, parent_key: str, props) -> int:
    """Create HAS_PROPERTY children for a node addressed by `key`."""
    rows = [
        {"name": n, "type": t, "description": d,
         "isKey": k, "isForeignKey": fk, "isRequired": req}
        for (n, t, d, k, fk, req) in props
    ]
    if not rows:
        return 0
    session.run(
        f"""
        MATCH (parent:{label} {{key: $parent_key}})
        UNWIND $rows AS row
        MERGE (p:Property {{parentType: $parent_type, parentId: parent.id, name: row.name}})
          ON CREATE SET p.id = randomUUID()
        SET p.displayName = row.name, p.type = row.type, p.description = row.description,
            p.isKey = row.isKey, p.isForeignKey = row.isForeignKey,
            p.isRequired = row.isRequired, p.demoSeed = $tag
        MERGE (parent)-[:HAS_PROPERTY]->(p)
        """,
        parent_key=parent_key, parent_type=parent_type, rows=rows, tag=TAG,
    ).consume()
    return len(rows)


def wipe(session) -> int:
    """Delete ONLY nodes tagged by this seed. :Proposal is never matched."""
    rec = session.run(
        """
        MATCH (n) WHERE n.demoSeed = $tag AND NOT n:Proposal
        WITH collect(n) AS ns
        CALL { WITH ns UNWIND ns AS n DETACH DELETE n }
        RETURN size(ns) AS deleted
        """,
        tag=TAG,
    ).single()
    return int((rec or {}).get("deleted", 0))


def main() -> None:
    ap = argparse.ArgumentParser(description="배달앱 데모 도메인 모델 시드")
    ap.add_argument("--wipe", action="store_true", help="시드가 만든 노드만 삭제하고 종료")
    args = ap.parse_args()

    with get_session() as session:
        if args.wipe:
            print(f"wiped {wipe(session)} demo nodes (demoSeed={TAG})")
            return
        counts = seed(session)

    total = sum(counts.values())
    for k in sorted(counts):
        print(f"  {k:<16} {counts[k]}")
    print(f"total created/merged: {total}")


if __name__ == "__main__":
    main()
