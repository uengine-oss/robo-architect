# Reference: Invariant(불변식) & UI(화면)

## Invariant — Aggregate 일관성 규칙
Aggregate가 **항상** 지켜야 하는 비즈니스 규칙. Aggregate 항목의 `invariants: [...]`로 출력.
applier가 Invariant 노드 + `Aggregate ─HAS_INVARIANT→ Invariant` + `Invariant ─VERIFIED_BY→ Command`를 만든다.
```json
"invariants": [
  { "declaration": "주문 총액은 항상 0보다 커야 한다",
    "name": "양수 총액",
    "verifyingCommandRefs": ["CMD-place-order"] }
]
```
- `declaration`: 한 문장 선언(필수). `name`/`description` 선택.
- `verifyingCommandRefs`: 이 불변식을 검증하는 Command tempId 목록(→ VERIFIED_BY). 보통 해당 Aggregate의 상태를 바꾸는 명령.
- Aggregate당 **0~6개**, 진짜 규칙만(과잉 생성 금지). 위반 시 던질 예외는 Aggregate.exceptions(semanticDiff)로 정의.

## UI — Command/ReadModel 화면
사용자가 명령을 실행하거나 조회 결과를 보는 화면. Command/ReadModel 항목의 `ui: {...}`로 출력.
applier가 UI 노드 + `BoundedContext ─HAS_UI→ UI` + `UI ─ATTACHED_TO→ (Command|ReadModel)`를 만들고,
UserStory(userStoryRefs 첫 항목)를 `UI.userStoryId`로 추적 연결한다.
```json
"ui": { "name": "메뉴 등록 화면", "description": "이름·가격·카테고리 입력 폼", "template": "<form>...</form>" }
```
- `name`(필수), `description`, `template`(선택, HTML/DSL 스케치).
- 입력형 Command → 입력 폼 화면, 조회형 ReadModel → 목록/상세 화면.
- 모든 Command/ReadModel에 1개 UI를 권장(사용자 접점이 없는 내부 명령은 생략 가능).

## 자가 검증
- [ ] 각 Aggregate가 핵심 불변식을 가졌고, 검증 Command(verifyingCommandRefs)에 연결됐다.
- [ ] 사용자 접점 Command/ReadModel이 UI를 가졌다.
