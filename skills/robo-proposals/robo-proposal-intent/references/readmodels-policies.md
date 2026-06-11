# Reference: ReadModel & Policy

## ReadModel (CQRS 조회 모델, nodeLabel:"ReadModel", boundedContextId 필수)
조회 전용 UserStory(예: "주문 내역을 조회한다")는 Command가 아니라 ReadModel로 표현한다.
- `fields`: `actor`, `description`, `isMultipleResult`(true=목록, false=단건), `provisioningType`(선택).
- `properties`: 조회 결과 필드.
- `userStoryRefs`: 이 조회를 구현하는 UserStory → `UserStory ─IMPLEMENTS→ ReadModel`.
- 예: "주문내역"(OrderList): boundedContextId=EP-order, isMultipleResult=true,
  properties=[orderId, menuName, totalPrice, status], userStoryRefs=[US-order-track].

## Policy (반응 정책 / BC간 연결, nodeLabel:"Policy", boundedContextId 필수)
"어떤 이벤트가 일어나면 → 다른 명령을 실행한다"는 규칙. BC 간 비동기 협력을 표현.
- `fields`: `description`, `condition`(트리거 조건, 자연어).
- `triggerEventId`: 트리거 Event tempId → `Event ─TRIGGERS→ Policy`.
- `invokeCommandId`: 실행할 Command tempId → `Policy ─INVOKES→ Command`.
- 예: "주문 시 재고 차감": triggerEventId=EVT-order-placed(주문 BC),
  invokeCommandId=CMD-reduce-stock(메뉴/재고 BC), condition="주문이 생성되면".

## 언제 만드나
- ReadModel: 조회/목록/상태확인 성격의 UserStory마다.
- Policy: 한 BC의 이벤트가 다른 BC(또는 같은 BC)의 후속 명령을 유발하는 흐름이 있을 때. 없으면 생략 가능.
