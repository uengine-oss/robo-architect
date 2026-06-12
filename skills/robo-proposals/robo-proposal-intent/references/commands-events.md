# Reference: Command & Event (속성·EMITS 포함)

## Command (nodeLabel:"Command", aggregateId 필수)
- 이름: **PascalCase 명령형** (예: PlaceOrder/RegisterMenu) 또는 한글 동사구.
- `fields`:
  - `actor`: 실행 주체(예: 주문자, 점주). 기본 "user".
  - `category`: `Create | Update | Delete | Process | Business Logic | External Integration`.
  - `description`
  - `inputSchema`: 파라미터 JSON 스키마 (예: `{"menuId":"UUID","qty":"int"}`).
- `properties`: 명령 파라미터를 Property로도 나열(이름/type/isRequired). inputSchema와 일관되게.
- `userStoryRefs`: 이 명령이 구현하는 UserStory tempId 목록 → `UserStory ─IMPLEMENTS→ Command` (추적성, **필수**).
- `gwt`: BDD 시나리오(최소 1개). references/gwt.md 참고.
- `ui`: 사용자 접점이면 화면. references/invariants-ui.md 참고.
- 하나의 Command는 **1개 이상의 Event를 emit**한다(아래 Event의 commandId로 연결).

## Event (nodeLabel:"Event", commandId 필수)
- 이름: **과거형** (예: OrderPlaced/MenuRegistered, "주문됨"). 불변 사실.
- `fields`:
  - `version`: semver (예: "1.0.0").
  - `payload`: 이벤트 데이터 JSON 스키마.
  - `description`
- `properties`: 페이로드 필드를 Property로 나열.
- 실패 이벤트도 고려(예: OrderPlacementFailed)할 수 있으나, core 범위에선 성공 경로 위주로 충분.

## Command→Event 매핑 규칙
- 모든 Command는 최소 1개 Event. 하나의 명령이 여러 이벤트를 낼 수 있다(예: PlaceOrder → OrderPlaced(+ StockReserved)).
- Event 이름은 Command 결과를 반영.

## 예 (메뉴 등록)
- Command "메뉴등록"(RegisterMenu): aggregateId=AGG-menu, actor=점주, category=Create,
  inputSchema={name,price,category}, userStoryRefs=[US-menu-manage],
  gwt=[정상 등록 / 가격 0 이하 거부].
- Event "메뉴등록됨"(MenuRegistered): commandId=CMD-register-menu, version=1.0.0,
  payload={menuId,name,price}.
