# Reference: BoundedContext 식별 (= Epic)

이 모델에서 **BoundedContext = 요구사항 트리의 Epic**이자 Aggregate 컨테이너다. `strategicDiff.epics`로 표현한다.

## 핵심 원칙
1. **높은 응집·낮은 결합**: 같은 비즈니스 능력(capability)에 속한 UserStory/명령/이벤트를 한 BC로 묶는다.
2. **이벤트 흐름**: 같은 도메인 이벤트 군을 공유하면 같은 BC. 다른 BC와는 이벤트(비동기)로만 통신.
3. **액터·언어 경계**: 용어(유비쿼터스 언어)가 바뀌는 지점이 BC 경계다(예: "주문"의 의미가 결제 맥락과 배송 맥락에서 다르면 분리).
4. **모든 UserStory는 정확히 하나의 BC에 속한다** — 고아 금지.

## 도메인 분류 (`fields.classification`)
- **core**: 사업의 차별화 가치(예: 음식 주문/매칭). 가장 정교하게 설계.
- **supporting**: core를 보조(예: 메뉴 관리, 정산).
- **generic**: 범용(예: 인증, 알림). 외부 솔루션 대체 가능.

각 epic 항목에 `fields: { "classification": {"after": "core|supporting|generic"}, "description": {"after": "..."} }`를 채운다.

## 분해 가이드
- 단일 거대한 BC를 피한다. "음식 배달 플랫폼"은 보통 **메뉴 관리 BC + 주문 BC**(최소)로 나뉜다.
- 각 BC는 1개 이상의 Feature와 1개 이상의 Aggregate를 갖는다.
- BC 이름은 도메인 명사(PascalCase 또는 한글 도메인명). 기술 계층(Service/Controller) 이름 금지.

## 출력
`epics`(=BC) 각 항목: `{op:"CREATE", entityType:"epic", tempId:"EP-<slug>", entityTitle, fields:{classification, description}}`.
모든 feature는 `epicId`로, 모든 aggregate는 `boundedContextId`로 이 tempId를 가리킨다.
