# Ingestion Workflow Domain Model - Arrows.app 참조 가이드

이 문서는 ingestion workflow에서 생성되는 모든 노드 타입과 관계를 arrows.app에서 그릴 수 있도록 정리한 참조 가이드입니다.

## 목차

1. [노드 타입 (Node Types)](#노드-타입-node-types)
2. [관계 타입 (Relationship Types)](#관계-타입-relationship-types)
3. [Arrows.app 그리기 가이드](#arrowsapp-그리기-가이드)
4. [생성 순서 (Phase Order)](#생성-순서-phase-order)
5. [참고사항](#참고사항)

---

## 노드 타입 (Node Types)

### 1. UserStory
**설명**: 요구사항에서 추출된 사용자 스토리

**속성**:
- `id`: UUID
- `role`: 사용자 역할 (예: "customer", "admin")
- `action`: 수행할 액션
- `benefit`: 기대 효과
- `priority`: 우선순위 (예: "high", "medium", "low")
- `ui_description`: UI 설명 (선택적)

**생성 페이즈**: Phase 2 (User Stories Phase)

---

### 2. BoundedContext
**설명**: 도메인 경계를 정의하는 컨텍스트

**속성**:
- `id`: UUID
- `key`: 고유 키 (예: "bc-order-management")
- `name`: 이름 (예: "Order Management")
- `description`: 설명
- `domain_type`: 도메인 타입 (예: "Core", "Supporting")
- `userStoryIds[]`: 연결된 User Story ID 배열

**생성 페이즈**: Phase 3 (Bounded Contexts Phase)

---

### 3. Aggregate
**설명**: 일관성 경계를 가진 집합체

**속성**:
- `id`: UUID
- `key`: 고유 키 (예: "agg-order")
- `name`: 이름 (예: "Order")
- `rootEntity`: 루트 엔티티 이름
- `invariants[]`: 불변식 배열
- `enumerations[]`: 열거형 배열
- `valueObjects[]`: 값 객체 배열

**생성 페이즈**: Phase 4 (Aggregates Phase)

---

### 4. Command
**설명**: 상태 변경을 의도하는 명령

**속성**:
- `id`: UUID
- `key`: 고유 키 (예: "cmd-create-order")
- `name`: 이름 (예: "CreateOrder")
- `actor`: 실행 주체 (예: "user", "admin", "system")
- `category`: 카테고리 (예: "Create", "Update", "Delete", "Process")
- `inputSchema`: 입력 스키마 (JSON, 선택적)

**생성 페이즈**: Phase 5 (Commands Phase)

---

### 5. Event
**설명**: 명령 실행 결과로 발생한 이벤트

**속성**:
- `id`: UUID
- `key`: 고유 키 (예: "evt-order-created")
- `name`: 이름 (예: "OrderCreated")
- `version`: 버전 (기본값: "1.0.0")
- `schema`: 스키마 (선택적)
- `payload`: 페이로드 (선택적)
- `isBreaking`: Breaking 변경 여부 (기본값: false)

**생성 페이즈**: Phase 6 (Events Phase)

---

### 6. ReadModel
**설명**: 읽기 최적화를 위한 읽기 모델

**속성**:
- `id`: UUID
- `key`: 고유 키 (예: "rm-order-summary")
- `name`: 이름 (예: "OrderSummary")
- `description`: 설명
- `provisioningType`: 프로비저닝 타입 (기본값: "CQRS")
- `actor`: 액터 (선택적)
- `isMultipleResult`: 다중 결과 여부 (선택적)

**생성 페이즈**: Phase 7 (ReadModels Phase)

---

### 7. Policy
**설명**: 이벤트 기반 정책 (다른 BC 간 통신)

**속성**:
- `id`: UUID
- `key`: 고유 키 (예: "pol-order-cancellation")
- `name`: 이름 (예: "OrderCancellationPolicy")
- `description`: 설명

**생성 페이즈**: Phase 10 (Policies Phase)

---

### 8. Property
**설명**: Aggregate, Command, Event, ReadModel의 속성

**속성**:
- `id`: UUID
- `name`: 속성 이름 (예: "orderId", "amount")
- `type`: 타입 (예: "String", "Integer", "Decimal", "Date")
- `description`: 설명
- `isKey`: 키 여부 (기본값: false)
- `isForeignKey`: 외래키 여부 (기본값: false)
- `isRequired`: 필수 여부 (기본값: false)
- `fkTargetHint`: 외래키 타겟 힌트 (선택적)
- `parentType`: 부모 타입 ("Aggregate" | "Command" | "Event" | "ReadModel")
- `parentId`: 부모 노드의 id

**생성 페이즈**: Phase 8 (Properties Phase)

---

### 9. UI
**설명**: UI 와이어프레임

**속성**:
- `id`: UUID
- `key`: 고유 키 (예: "ui-cmd-create-order")
- `name`: 이름
- `description`: 설명
- `template`: HTML 템플릿
- `attachedToId`: 연결된 노드 ID (Command 또는 ReadModel)
- `attachedToType`: 연결된 노드 타입 ("Command" | "ReadModel")
- `attachedToName`: 연결된 노드 이름
- `userStoryId`: 관련 User Story ID

**생성 페이즈**: Phase 12 (UI Wireframes Phase)

---

### 10. GWT (Given/When/Then)
**설명**: BDD 스타일 테스트 케이스

**속성**:
- `id`: UUID
- `key`: 고유 키
- `parentType`: 부모 타입 ("Command" | "Policy")
- `parentId`: 부모 노드의 id
- `givenRef`: Given 참조 정보 (JSON)
  - `referencedNodeId`: 참조 노드 ID (보통 Aggregate)
  - `referencedNodeType`: 참조 노드 타입 (보통 "Aggregate")
  - `name`: 이름
  - `description`: 설명 (선택적)
- `whenRef`: When 참조 정보 (JSON)
  - `referencedNodeId`: 참조 노드 ID (Command 또는 Event)
  - `referencedNodeType`: 참조 노드 타입 ("Command" | "Event")
  - `name`: 이름
  - `description`: 설명 (선택적)
- `thenRef`: Then 참조 정보 (JSON)
  - `referencedNodeId`: 참조 노드 ID (보통 Event)
  - `referencedNodeType`: 참조 노드 타입 (보통 "Event")
  - `name`: 이름
  - `description`: 설명 (선택적)
- `testCases[]`: 테스트 케이스 배열 (JSON)
  - 각 테스트 케이스는 `scenarioDescription`, `givenFieldValues`, `whenFieldValues`, `thenFieldValues`를 포함

**생성 페이즈**: Phase 11 (GWT Phase)

**참고**: Given/When/Then은 별도 노드가 아니라 GWT 노드의 속성(`givenRef`, `whenRef`, `thenRef`)으로 저장됩니다.

---

## 관계 타입 (Relationship Types)

### 1. UserStory → BoundedContext
**관계**: `IMPLEMENTS`  
**속성**:
- `confidence`: 신뢰도 (기본값: 0.9)
- `createdAt`: 생성 시간

**설명**: User Story가 특정 Bounded Context를 구현함

---

### 2. UserStory → Aggregate
**관계**: `IMPLEMENTS`  
**속성**:
- `confidence`: 신뢰도 (기본값: 0.9)
- `createdAt`: 생성 시간

**설명**: User Story가 특정 Aggregate를 구현함

---

### 3. UserStory → Command
**관계**: `IMPLEMENTS`  
**속성**:
- `confidence`: 신뢰도 (기본값: 0.9)
- `createdAt`: 생성 시간

**설명**: User Story가 특정 Command를 구현함

---

### 4. UserStory → Event
**관계**: `IMPLEMENTS`  
**속성**:
- `confidence`: 신뢰도 (기본값: 0.9)
- `createdAt`: 생성 시간

**설명**: User Story가 특정 Event를 구현함

---

### 5. UserStory → Policy
**관계**: `IMPLEMENTS`  
**속성**:
- `confidence`: 신뢰도 (기본값: 0.9)
- `createdAt`: 생성 시간

**설명**: User Story가 특정 Policy를 구현함

---

### 6. BoundedContext → Aggregate
**관계**: `HAS_AGGREGATE`  
**속성**:
- `isPrimary`: 주요 Aggregate 여부 (기본값: false)

**설명**: Bounded Context가 Aggregate를 포함함

---

### 7. BoundedContext → ReadModel
**관계**: `HAS_READMODEL`  
**설명**: Bounded Context가 ReadModel을 포함함

---

### 8. BoundedContext → Policy
**관계**: `HAS_POLICY`  
**설명**: Bounded Context가 Policy를 포함함

---

### 9. BoundedContext → UI
**관계**: `HAS_UI`  
**설명**: Bounded Context가 UI를 포함함

---

### 10. Aggregate → Command
**관계**: `HAS_COMMAND`  
**설명**: Aggregate가 Command를 처리함

---

### 11. Command → Event
**관계**: `EMITS`  
**속성**:
- `isGuaranteed`: 보장 여부 (기본값: true)

**설명**: Command가 실행되면 Event를 발생시킴

---

### 12. Event → Policy
**관계**: `TRIGGERS`  
**속성**:
- `priority`: 우선순위 (기본값: 1)
- `isEnabled`: 활성화 여부 (기본값: true)

**설명**: Event가 Policy를 트리거함 (다른 BC의 Event일 수 있음)

---

### 13. Policy → Command
**관계**: `INVOKES`  
**속성**:
- `isAsync`: 비동기 여부 (기본값: true)

**설명**: Policy가 Command를 호출함 (다른 BC의 Command일 수 있음)

---

### 14. Aggregate → Property
**관계**: `HAS_PROPERTY`  
**설명**: Aggregate가 Property를 가짐

---

### 15. Command → Property
**관계**: `HAS_PROPERTY`  
**설명**: Command가 Property를 가짐

---

### 16. Event → Property
**관계**: `HAS_PROPERTY`  
**설명**: Event가 Property를 가짐

---

### 17. ReadModel → Property
**관계**: `HAS_PROPERTY`  
**설명**: ReadModel이 Property를 가짐

---

### 18. UI → Command
**관계**: `ATTACHED_TO`  
**조건**: `attachedToType = "Command"`일 때

**설명**: UI가 Command에 연결됨

---

### 19. UI → ReadModel
**관계**: `ATTACHED_TO`  
**조건**: `attachedToType = "ReadModel"`일 때

**설명**: UI가 ReadModel에 연결됨

---

### 20. Command → GWT
**관계**: `HAS_GWT`  
**설명**: Command가 GWT 테스트 케이스를 가짐

---

### 21. Policy → GWT
**관계**: `HAS_GWT`  
**설명**: Policy가 GWT 테스트 케이스를 가짐

---

### 22. GWT → Aggregate
**관계**: `REFERENCES`  
**조건**: `givenRef.referencedNodeType = "Aggregate"`일 때

**설명**: GWT의 Given이 Aggregate를 참조함

---

### 23. GWT → Command
**관계**: `REFERENCES`  
**조건**: `whenRef.referencedNodeType = "Command"`일 때

**설명**: GWT의 When이 Command를 참조함

---

### 24. GWT → Event
**관계**: `REFERENCES`  
**조건**: `whenRef.referencedNodeType = "Event"` 또는 `thenRef.referencedNodeType = "Event"`일 때

**설명**: GWT의 When 또는 Then이 Event를 참조함

---

## Arrows.app 그리기 가이드

### 1. 계층 구조 (Hierarchy)

```
UserStory (최상위 - 요구사항)
    ↓ IMPLEMENTS
BoundedContext (도메인 경계)
    ↓ HAS_AGGREGATE
Aggregate (일관성 경계)
    ↓ HAS_COMMAND
Command (액션)
    ↓ EMITS
Event (결과)
```

### 2. 주요 흐름 (Main Flow)

```
UserStory
    ├─→ BoundedContext (IMPLEMENTS)
    │       ├─→ Aggregate (HAS_AGGREGATE)
    │       │       ├─→ Command (HAS_COMMAND)
    │       │       │       ├─→ Event (EMITS)
    │       │       │       └─→ Property (HAS_PROPERTY)
    │       │       └─→ Property (HAS_PROPERTY)
    │       ├─→ ReadModel (HAS_READMODEL)
    │       │       └─→ Property (HAS_PROPERTY)
    │       ├─→ Policy (HAS_POLICY)
    │       └─→ UI (HAS_UI)
    │
    ├─→ Aggregate (IMPLEMENTS)
    ├─→ Command (IMPLEMENTS)
    ├─→ Event (IMPLEMENTS)
    └─→ Policy (IMPLEMENTS)
```

### 3. Policy 흐름 (Policy Flow)

```
Event (다른 BC에서 발생)
    ↓ TRIGGERS
Policy
    ↓ INVOKES
Command (다른 BC의 Command)
```

**설명**: Policy는 다른 Bounded Context 간의 통신을 담당합니다.  
- Event는 다른 BC에서 발생할 수 있음
- Policy는 해당 Event를 받아 다른 BC의 Command를 호출함

### 4. UI 연결 (UI Connections)

```
UI
    ├─→ BoundedContext (HAS_UI)
    ├─→ Command (ATTACHED_TO)
    └─→ ReadModel (ATTACHED_TO)
```

**설명**: UI는 Bounded Context에 속하며, Command 또는 ReadModel에 연결됩니다.

### 5. GWT 연결 (GWT Connections)

```
Command/Policy
    └─→ GWT (HAS_GWT)
            ├─→ Aggregate (REFERENCES, via givenRef)
            ├─→ Command (REFERENCES, via whenRef)
            └─→ Event (REFERENCES, via whenRef or thenRef)
```

**설명**: 
- **GWT**는 단일 노드로, `givenRef`, `whenRef`, `thenRef` 속성에 참조 정보를 저장합니다.
- **givenRef**: 초기 상태 (보통 Aggregate 참조)
- **whenRef**: 액션 (Command 또는 Event 참조)
- **thenRef**: 결과 상태 (보통 Event 참조)
- **testCases**: 여러 테스트 케이스를 배열로 저장합니다.

### Arrows.app 스타일 가이드

#### 노드 색상 제안

| 노드 타입 | 색상 | HEX 코드 |
|---------|------|----------|
| UserStory | 연한 파란색 | #E3F2FD |
| BoundedContext | 진한 파란색 | #1976D2 |
| Aggregate | 초록색 | #4CAF50 |
| Command | 주황색 | #FF9800 |
| Event | 보라색 | #9C27B0 |
| ReadModel | 청록색 | #00BCD4 |
| Policy | 빨간색 | #F44336 |
| Property | 회색 | #9E9E9E |
| UI | 노란색 | #FFC107 |
| GWT | 분홍색 | #E91E63 |

#### 관계 화살표 스타일

| 관계 타입 | 스타일 | 색상 | 굵기 |
|---------|--------|------|------|
| IMPLEMENTS | 점선 (dashed) | 기본 | 얇게 |
| HAS_* | 실선 (solid) | 기본 | 굵게 |
| EMITS | 실선 (solid) | 기본 | 중간 |
| TRIGGERS | 실선 (solid) | 빨간색 | 중간 |
| INVOKES | 실선 (solid) | 주황색 | 중간 |
| ATTACHED_TO | 점선 (dashed) | 기본 | 얇게 |
| REFERENCES | 점선 (dashed) | 기본 | 매우 얇게 |

---

## 생성 순서 (Phase Order)

### Phase 1: Parsing Phase
- 문서 파싱 및 검증
- 노드 생성 없음

### Phase 2: User Stories Phase
- **생성**: UserStory 노드
- **관계**: 없음

### Phase 3: Bounded Contexts Phase
- **생성**: BoundedContext 노드
- **관계**: 
  - UserStory → BoundedContext (IMPLEMENTS)

### Phase 4: Aggregates Phase
- **생성**: Aggregate 노드
- **관계**: 
  - BoundedContext → Aggregate (HAS_AGGREGATE)
  - UserStory → Aggregate (IMPLEMENTS)

### Phase 5: Commands Phase
- **생성**: Command 노드
- **관계**: 
  - Aggregate → Command (HAS_COMMAND)
  - UserStory → Command (IMPLEMENTS)

### Phase 6: Events Phase
- **생성**: Event 노드
- **관계**: 
  - Command → Event (EMITS)
  - UserStory → Event (IMPLEMENTS)

### Phase 7: ReadModels Phase
- **생성**: ReadModel 노드
- **관계**: 
  - BoundedContext → ReadModel (HAS_READMODEL)

### Phase 8: Properties Phase
- **생성**: Property 노드
- **관계**: 
  - Aggregate → Property (HAS_PROPERTY)
  - Command → Property (HAS_PROPERTY)
  - Event → Property (HAS_PROPERTY)
  - ReadModel → Property (HAS_PROPERTY)

### Phase 9: References Phase
- **생성**: 없음 (Property의 외래키 관계만 설정)
- **관계**: 없음 (Property의 `isForeignKey` 및 `fkTargetHint` 속성만 설정)

### Phase 10: Policies Phase
- **생성**: Policy 노드
- **관계**: 
  - BoundedContext → Policy (HAS_POLICY)
  - Event → Policy (TRIGGERS)
  - Policy → Command (INVOKES)
  - UserStory → Policy (IMPLEMENTS)

### Phase 11: GWT Phase
- **생성**: GWT 노드
- **관계**: 
  - Command → GWT (HAS_GWT)
  - Policy → GWT (HAS_GWT)
  - GWT → Aggregate (REFERENCES, via givenRef)
  - GWT → Command (REFERENCES, via whenRef)
  - GWT → Event (REFERENCES, via whenRef or thenRef)

### Phase 12: UI Wireframes Phase
- **생성**: UI 노드
- **관계**: 
  - BoundedContext → UI (HAS_UI)
  - UI → Command (ATTACHED_TO, attachedToType="Command"일 때)
  - UI → ReadModel (ATTACHED_TO, attachedToType="ReadModel"일 때)

---

## 참고사항

### 1. 다중 관계
- **UserStory**는 여러 노드(BC, Aggregate, Command, Event, Policy)에 `IMPLEMENTS` 관계를 가질 수 있습니다.
- 하나의 User Story가 여러 Aggregate, Command, Event를 구현할 수 있습니다.

### 2. Policy는 Cross-BC 통신
- **Policy**는 다른 Bounded Context의 Event를 받아 다른 Bounded Context의 Command를 호출할 수 있습니다.
- 이는 마이크로서비스 간 통신을 모델링합니다.

### 3. Property는 여러 타입의 부모를 가짐
- **Property**는 Aggregate, Command, Event, ReadModel 중 하나에만 연결됩니다.
- `parentType`과 `parentId`로 부모를 식별합니다.

### 4. UI는 Command 또는 ReadModel에 연결
- **UI**는 Command 또는 ReadModel 중 하나에만 `ATTACHED_TO` 관계로 연결됩니다.
- `attachedToType` 속성으로 연결 타입을 구분합니다.

### 5. GWT는 Command 또는 Policy에 속함
- **GWT** (Given/When/Then)는 Command 또는 Policy에 속하는 단일 노드입니다.
- Given/When/Then은 별도 노드가 아니라 GWT 노드의 속성(`givenRef`, `whenRef`, `thenRef`)으로 저장됩니다.
- `givenRef`는 보통 Aggregate를 참조하고, `whenRef`는 Command 또는 Event를 참조하며, `thenRef`는 Event를 참조합니다.
- `testCases` 배열에 여러 테스트 케이스를 저장할 수 있습니다.

### 6. 관계 속성
- `IMPLEMENTS` 관계는 `confidence` 속성을 가집니다 (기본값: 0.9).
- `HAS_AGGREGATE` 관계는 `isPrimary` 속성을 가집니다 (기본값: false).
- `EMITS` 관계는 `isGuaranteed` 속성을 가집니다 (기본값: true).
- `TRIGGERS` 관계는 `priority` (기본값: 1)와 `isEnabled` (기본값: true) 속성을 가집니다.
- `INVOKES` 관계는 `isAsync` 속성을 가집니다 (기본값: true).

### 7. 키 생성 규칙
- 모든 노드는 `key` 속성을 가지며, 이는 고유 식별자로 사용됩니다.
- 키는 계층 구조를 반영합니다 (예: `bc-order-management`, `agg-order`, `cmd-create-order`).

---

## 예제 다이어그램 구조

### 간단한 예제: 주문 관리 시스템

```
UserStory: "As a customer, I want to place an order"
    ↓ IMPLEMENTS
BoundedContext: "Order Management"
    ↓ HAS_AGGREGATE
Aggregate: "Order"
    ├─→ Property: "orderId" (isKey: true)
    ├─→ Property: "customerId" (isForeignKey: true)
    ├─→ Property: "amount"
    └─→ HAS_COMMAND
        Command: "CreateOrder"
            ├─→ Property: "items"
            ├─→ Property: "shippingAddress"
            ├─→ EMITS
            │   Event: "OrderCreated"
            │       └─→ Property: "orderId"
            └─→ HAS_GWT
                GWT
                    ├─→ Aggregate: "Order" (REFERENCES, via givenRef)
                    ├─→ Command: "CreateOrder" (REFERENCES, via whenRef)
                    └─→ Event: "OrderCreated" (REFERENCES, via thenRef)
```

### Policy 예제: 주문 취소 정책

```
Event: "OrderCancelled" (Order Management BC)
    ↓ TRIGGERS
Policy: "RefundPolicy" (Payment BC)
    ↓ INVOKES
Command: "ProcessRefund" (Payment BC)
```

---

## Arrows.app 사용 팁

1. **레이어별 그룹화**: 같은 레벨의 노드들을 그룹으로 묶어 가독성을 높이세요.
   - 레이어 1: UserStory
   - 레이어 2: BoundedContext
   - 레이어 3: Aggregate, ReadModel
   - 레이어 4: Command, Event
   - 레이어 5: Policy
   - 레이어 6: Property, UI, GWT

2. **색상 코딩**: 위의 색상 가이드를 따라 노드 타입을 시각적으로 구분하세요.

3. **관계 라벨**: 모든 관계에 라벨을 추가하여 관계 타입을 명확히 표시하세요.

4. **크기 조정**: 중요도에 따라 노드 크기를 조정하세요.
   - BoundedContext, Aggregate: 큰 크기
   - Command, Event: 중간 크기
   - Property, GWT: 작은 크기

5. **레이아웃**: 
   - 왼쪽에서 오른쪽으로 흐름을 배치 (UserStory → BC → Aggregate → Command → Event)
   - Policy는 별도 영역에 배치하여 Cross-BC 통신을 명확히 표시

---

## 업데이트 이력

- 2024-01-XX: 초기 문서 작성
