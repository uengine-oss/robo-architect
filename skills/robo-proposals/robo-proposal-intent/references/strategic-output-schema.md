# Reference: INTENT Strategic Diff 출력 계약

INTENT는 무엇을 만들지 정하는 요구사항 단계다. 전술 설계와 구현 계획은 후속 PLAN이 담당한다.

## 완료 출력

```json
{
  "action": "done",
  "strategicDiff": {
    "version": 1,
    "epics": [
      {
        "op": "CREATE",
        "entityType": "epic",
        "entityId": null,
        "tempId": "EP-shipping",
        "entityTitle": "배송",
        "fields": {
          "description": {"after": "배송 상태와 추적 이력을 관리한다."},
          "classification": {"after": "core"}
        },
        "legacyRefs": [
          {"nodeId": "code:<project>/<file>:<function>",
           "role": "derived-from", "evidence": "배송 상태 전이 검증·갱신 로직"}
        ]
      }
    ],
    "features": [
      {
        "op": "CREATE",
        "entityType": "feature",
        "entityId": null,
        "tempId": "FT-shipping-tracking",
        "entityTitle": "배송 조회",
        "epicId": "EP-shipping",
        "legacyRefs": [{"nodeId": "db:<db>.<table>", "role": "reads"}]
      }
    ],
    "userStories": [
      {
        "op": "CREATE",
        "entityType": "userStory",
        "entityId": null,
        "tempId": "US-shipping-tracking",
        "entityTitle": "고객: 배송 상태를 조회한다",
        "featureId": "FT-shipping-tracking",
        "boundedContextId": "EP-shipping",
        "role": "고객",
        "action": "주문 건의 현재 배송 상태와 추적 이력을 확인한다",
        "benefit": "배송 진행 상황을 알 수 있다",
        "acceptanceCriteria": [
          "Given 배송 중인 주문, When 배송 조회, Then 현재 상태와 시간순 이력을 표시"
        ],
        "legacyRefs": []
      }
    ],
    "processes": [
      {
        "op": "CREATE",
        "entityType": "process",
        "entityId": null,
        "tempId": "PROC-shipping-tracking",
        "entityTitle": "배송 추적",
        "fields": {"steps": {"after": "주문 선택→현재 상태 조회→추적 이력 확인"}},
        "legacyRefs": [{"nodeId": "code:<project>/<file>:<function>"}]
      }
    ]
  },
  "journeys": []
}
```

명확화가 필요하면 다음 형상만 반환한다.

```json
{"action":"clarify","questions":[{"index":0,"text":"...","options":["...","..."]}]}
```

## 요소별 레거시 근거(legacyRefs) 불변식

- **모든 요소(epic/feature/userStory/process)는 `legacyRefs` 배열을 가진다.** 레거시에 대응
  근거가 없는 신규 요소는 빈 배열 `[]`로 정직하게 표기한다 — 생략하지 않는다.
- `nodeId`는 **이 실행에서 `cluster_retrieve` 검색 결과 또는 `node_detail` 성공 응답으로 실제
  확인한 ID만** 사용한다. 기억·추측으로 ID를 만들지 않는다. 서버가 관찰집합 밖 ID를 제거하고
  경고를 남긴다.
- 항목 형상: `{"nodeId": "<확인된 id>", "role"?: "derived-from|refines|reads|writes",
  "evidence"?: "<이 노드가 근거인 이유 한 줄>", "field"?: "<특정 필드 근거일 때만>"}`.
- 같은 요소에 같은 `nodeId`를 중복하지 않는다. 요소당 근거는 판단에 실제 사용한 것만(보통 1~4개).
- **규칙·사례·테이블 단위 정밀 인용**: 요소가 응답에 내장된 업무 규칙/사례/테이블에서
  유래했으면 `rule`(문장 그대로) / `example`(given·when·then 그대로) / `table`(테이블명)
  필드를 함수 `nodeId` 에 첨부하라 — 서버가 실제 노드로 해석해 그 단위로 꼬리표를 찍는다.
  인수조건이 특정 규칙의 반영이면 반드시 그 규칙을 `rule` 로 인용한다.
  상세 계약: `output-schema.md` "내용 단위 인용" 절.

## 연결 불변식

- Epic은 BoundedContext이며 `strategicDiff.epics`로 표현한다.
- 모든 CREATE 항목은 배치 내 고유 `tempId`를 갖는다.
- 모든 Feature의 `epicId`는 같은 출력의 Epic tempId 또는 입력에 있던 실제 BoundedContext id다.
- 모든 UserStory의 `featureId`와 `boundedContextId`는 같은 출력 또는 입력의 실제 id를 가리킨다.
- 기존 노드를 바꾸면 `op:"MODIFY"`, 실제 `entityId`, 변경된 `fields`를 사용한다.
- UserStory의 role, action, benefit, acceptanceCriteria는 비어 있으면 안 된다.
- 전술 설계나 구현 계획을 이 출력에 섞지 않는다.
