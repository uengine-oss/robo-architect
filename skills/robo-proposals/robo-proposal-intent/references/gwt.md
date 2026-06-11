# Reference: GWT (Given/When/Then 인수 시나리오)

각 Command는 `gwt: [...]` 로 BDD 시나리오를 갖는다. applier가 Command에
`HAS_GIVEN/HAS_WHEN/HAS_THEN`으로 Given/When/Then 노드를 연결한다.
이것이 UserStory.acceptanceCriteria를 **실행 가능한 테스트 형태**로 구체화한다.

## 구조
```json
{
  "scenario": "정상 주문 생성",
  "given": { "name": "Aggregate: 주문", "description": "메뉴가 등록된 상태",
             "fieldValues": { "status": "NONE" } },
  "when":  { "name": "Command: 음식주문", "description": "메뉴 선택·수량 입력",
             "fieldValues": { "menuId": "m-1", "qty": "2" } },
  "then":  { "name": "Event: 음식주문됨", "description": "주문 생성·총액 계산",
             "fieldValues": { "totalPrice": "20000" } }
}
```
- `given` = 사전 Aggregate 상태, `when` = Command 실행(파라미터 값), `then` = 결과 Event(페이로드 값).
- `fieldValues`는 속성명→테스트값 맵(문자열). properties/inputSchema/payload의 필드명과 일치시킨다.

## 규칙
- Command마다 **2~4개** 시나리오: 정상 경로 1개 + 경계/실패 1개 이상(예: 가격 0 이하 거부, 품절 거부).
- name은 `"Aggregate: X" / "Command: Y" / "Event: Z"` 형식(참조 대상 명시).
- UserStory.acceptanceCriteria와 의미가 일치해야 한다(US의 Given/When/Then을 명령 단위로 구체화).
