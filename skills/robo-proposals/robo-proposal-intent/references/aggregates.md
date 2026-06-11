# Reference: Aggregate 추출 (이벤트-우선)

## 원칙
1. **트랜잭션 일관성 경계**: 하나의 트랜잭션에서 항상 같이 변경돼야 하는 엔티티 묶음이 한 Aggregate.
2. **이벤트-우선 분할**: 먼저 도메인 이벤트를 떠올리고, 같은 상태를 바꾸는 이벤트들을 한 Aggregate로 묶는다.
3. **단일 BC 소속**: 각 Aggregate는 정확히 하나의 BC(`boundedContextId`)에 속한다.
4. **Aggregate Root**: 외부에서 접근하는 진입 엔티티를 `fields.rootEntity`로 명시.

## 채울 내용 (tacticalDiff 항목, nodeLabel:"Aggregate")
- `fields`: `rootEntity`, `description`
- `properties`: 루트 엔티티의 도메인 속성 전부 (id는 isKey, 타 Aggregate 참조는 isForeignKey + fkTargetHint)
- `semanticDiff.ops`로 **valueObjects / enumerations / exceptions** 추가:
  - ValueObject: `{op:"obj_append", field:"valueObjects", obj_name, obj_data:{name, fields:[{name,type}]}}`
  - Enumeration: `{op:"obj_append", field:"enumerations", obj_name, obj_data:{name, items:[...]}}`
  - Exception(불변식 위반 시): `{op:"obj_append", field:"exceptions", obj_name, obj_data:{name, message, fields:[{name,type}]}}`

## 예
"메뉴 Aggregate": rootEntity=Menu, properties=[menuId(key), name, price(Long), available(Boolean)],
enumerations=[{name:"MenuCategory", items:["MAIN","SIDE","DRINK"]}], valueObjects=[{name:"Money", fields:[{name:"amount",type:"Long"}]}].

각 Aggregate는 1개 이상의 Command를 갖는다(없으면 설계가 불완전).
또한 각 Aggregate의 핵심 **불변식(invariants)**을 채운다 — references/invariants-ui.md 참고.
