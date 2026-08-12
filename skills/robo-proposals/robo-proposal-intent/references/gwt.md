# Reference: GWT (Given/When/Then 인수 시나리오)

각 Command는 `gwt: [...]` 로 BDD 시나리오를 갖는다. applier가 Command에
`HAS_GIVEN/HAS_WHEN/HAS_THEN`으로 Given/When/Then 노드를 연결한다.
이것이 UserStory.acceptanceCriteria를 **실행 가능한 테스트 형태**로 구체화한다.

## 구조
```json
{
  "scenario": "정상 주문 생성",
  "evidenceRefs": ["<exact RULE evidence_id>", "<used TABLE evidence_id>"],
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
- `evidenceRefs`는 이 시나리오 판단에 실제 사용한 packet `evidence_id`만 담는다. 최소 한 개는
  RULE이어야 하며 값·호출·sample을 썼다면 대응 SYMBOL/CALL/TABLE evidence도 함께 담는다.

## 규칙
- Command마다 **2~4개** 시나리오: 정상 경로 1개 + 경계/실패 1개 이상(예: 가격 0 이하 거부, 품절 거부).
- name은 `"Aggregate: X" / "Command: Y" / "Event: Z"` 형식(참조 대상 명시).
- UserStory.acceptanceCriteria와 의미가 일치해야 한다(US의 Given/When/Then을 명령 단위로 구체화).
- `node_detail(view="frame")`의 semantic slots와 profile RULE `condition/effects`를 시나리오에 배분하고,
  CALLS와 직접 R/W 테이블·컬럼·샘플 claim을 확인한다. complete source를 정상 생성 입력으로 요구하거나
  Analyzer의 부족 의미를 원문 재독해로 보충하지 않는다.
- `fieldValues`는 컬럼/속성 또는 RULE에 실제로 나타난 필드만 사용한다. 테스트값은 RULE의
  상수나 샘플에 있는 값이면 그대로 쓰고, 근거가 없으면 빈 맵으로 둔다.
- 범위/미정의 분기를 구체화하려고 대표 숫자나 미매핑 코드를 새로 선택하지 않는다. 실제 sample이나
  RULE 상수가 없으면 조건을 scenario/name에 기호로 남기고 해당 `fieldValues`는 비운다.
- 하나의 실제 필드가 여러 값을 가질 때 `field_cancel`/`field_error`처럼 합성 필드로 쪼개지
  않는다. 값별 시나리오를 나누고 원래 필드명을 그대로 쓴다. 이름 없는 함수 반환값에
  `ret`/`result` 같은 필드를 만들지 말고 `then.name`으로 반환 의미를 표현한다.
- `RET_INVALID`/`RET_FAIL` 같은 함수 반환 sentinel을 `cnt`/`status` 등 다른 데이터 필드에
  넣지 않는다. 소스가 동일 필드에 그 값을 직접 대입하지 않으면 `then.name`으로만 표현한다.
- 샘플 한 행을 유일한 정상값·전체 분포·필수 제약으로 일반화하지 않는다.
- RULE의 조건/결과를 뒤집거나, READ를 WRITE로, CALLS가 없는 모듈을 호출 관계로 만들지 않는다.
- `then`은 선택 분기의 중간 대입값이 아니라 그 뒤의 공통 후처리·clamp·rollback/commit까지
  적용한 최종 반환/상태다. 범위 조건만 보고 특정 상수가 항상 최종 반환된다고 일반화하지 않는다.
- 각 시나리오는 exact `evidenceRefs`로 직접 역추적한다. Command `legacyRefs`에도 근거 함수
  `nodeId`와 RULE의 `evidenceId`·`ruleId`·`text`를 보존한다. 여러 RULE을 한 문장으로 합치지 않는다.
