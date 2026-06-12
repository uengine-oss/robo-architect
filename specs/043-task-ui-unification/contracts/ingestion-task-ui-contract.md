# Contract: 인제스천 task=UI 불변식 (ui_wireframes.py)

ES 승격의 UI 생성 단계를 "Command/ReadModel당 UI" → "task당 1 트리거 UI + ReadModel 분기"로 변경. **신규 노드 라벨/관계 0**(ReadModel `ATTACHED_TO.role` 속성만).

## 1. task당 1 트리거 UI (FR-003, FR-008)

| 항목 | 계약 |
|---|---|
| 그룹핑 | Command를 `task_id`로 그룹. policy-invoked Command 제외(기존 로직 유지) |
| 트리거 선택 | task당 후보 Command 중 LLM(`get_llm`)이 "사람 조작" Command 1개 선택(`TriggerPick`). confidence < 임계 → entry(첫/대표) 폴백 |
| UI 생성 | 트리거 Command에만 `_create_command_ui` → `(:UI)-[:ATTACHED_TO]->(:Command)` 1개 |
| 시스템 task | 사람-트리거 Command가 없는 task(전부 policy-invoked 등) → UI 생성 안 함 |
| 멱등 | 재인제스천 시 task당 1 UI 유지(증식 0) |

**불변 규칙**:
- 사람-트리거 task : 트리거 UI = **1:1**(±0).
- Command/Event의 `task_id` 귀속 **불변**(회귀 0).
- A2A `:BpmTask`/`NEXT`/`PROMOTED_TO` **불변**.

## 2. ReadModel 분기 (FR-004, FR-009)

| 입력 | 판정(`ReadModelVerdict`) | 결과 |
|---|---|---|
| ReadModel(name/desc/trigger_event_keys/query_keys) | `is_query_screen=true` | 자체 UI 승격 `(:UI)-[:ATTACHED_TO]->(:ReadModel)` (role 무/`screen`) |
| | `is_query_screen=false` | 소비 task UI에 표시 `(:UI)-[:ATTACHED_TO {role:'display'}]->(:ReadModel)` |

**불변 규칙**:
- "ReadModel당 무조건 UI 생성" **제거** — 판정 통과분만 UI.
- 표시/화면 구분은 `ATTACHED_TO.role` **속성**(신규 라벨/관계 0). role 무시 시 기존 event_modeling 동작 보존.
- 한 ReadModel이 여러 화면에 표시 가능(N:M).

## 3. 계약 테스트 (pytest, fake/golden)

1. Command 2개 task → 트리거 UI 1개(나머지 Command UI 0).
2. policy-invoked만 가진 task → UI 0.
3. 조회화면 판정 ReadModel → UI 승격 / 비조회 → display 부착.
4. Command/Event `task_id` 호출 전후 동일.
5. 재인제스천 → task당 UI 수 불변(멱등).
6. LLM 판정 폴백: confidence 낮음 → entry Command 선택.

## 4. propose→confirm (FR-012, D4)

- 판정 결과는 생성 단계에서 자동 적용 + 통합 Process 뷰에 노출.
- 사용자 교정 경로: (a) 트리거 UI를 task의 다른 Command로 이동, (b) ReadModel 표시↔조회화면 토글. (구현은 후속 또는 기존 인스펙터 편집 재사용.)
