# Phase 1 Data Model: task=UI 통합

## Neo4j 스키마 변경: 신규 라벨/관계 **0건** (속성 1개 선택적)

| 요소 | 변경 | 비고 |
|---|---|---|
| `:UI` 노드 | 라벨 불변. **생성 개수 감소**(Command당 N → task당 1 트리거) | |
| `(:UI)-[:ATTACHED_TO]->(:Command)` | 불변 — 트리거 UI가 task의 트리거 Command에 붙음 | |
| `(:UI)-[:ATTACHED_TO]->(:ReadModel)` | 불변. **선택적 속성** `role` 추가: `display`(소비 표시) / 무속성 또는 `screen`(자체 조회화면) | 신규 관계 아님 — 기존 엣지 속성 |
| `(:BoundedContext)-[:HAS_UI]->(:UI)` | 불변 | |
| `:Command`/`:Event` (`task_id`) | **불변** | task 기반 유지 |
| `(:BpmTask)-[:PROMOTED_TO]->(:UserStory)-[:IMPLEMENTS]->(:Command)` | 불변(기존 브리지) | task↔Command 그룹핑 경로 |

→ **신규 노드 라벨 0, 신규 관계 0.** `ATTACHED_TO.role` 속성만(후방호환: role 무시하면 기존 동작).

## 생성 로직 변경 (ui_wireframes.py)

### 현재 (per-Command / per-ReadModel)
```
for bc → for agg → for cmd:   _create_command_ui(cmd)     # Command당 1 UI
for bc → for rm:              _create_readmodel_ui(rm)     # ReadModel당 1 UI
```

### 변경 (per-task trigger / ReadModel 분기)
```
# 1) task로 Command 그룹핑 (policy-invoked 제외)
tasks = group_commands_by_task(commands, exclude=policy_invoked)
for task, cmds in tasks:
    trigger_cmd = llm_pick_trigger(task, cmds)          # D2: LLM, 폴백 entry
    _create_command_ui(trigger_cmd)                      # task당 1 UI
    # 나머지 cmds: UI 없음 (그 화면이 일으키는 시스템 흐름)

# 2) ReadModel: 무조건 생성 → 판정 분기
for rm:
    verdict = llm_classify_readmodel(rm)                  # D3
    if verdict.is_query_screen:
        _create_readmodel_ui(rm)                          # 자체 화면(=task)
    else:
        attach_display(host_task_ui, rm, role='display')  # 소비 화면에 표시
```

## LLM 판정 DTO (신규 Pydantic, 그래프 영속 아님)

```python
class TriggerPick(BaseModel):       # D2
    trigger_command_id: str
    confidence: float               # < threshold → entry 폴백
    rationale: str

class ReadModelVerdict(BaseModel):  # D3
    is_query_screen: bool
    host_task_id: str | None = None # 표시일 때 소비 task
    rationale: str
```

## 검증 규칙 (테스트 대상)

- **task=UI**: 사람-트리거 task : 트리거 UI = 1:1(SC-002). policy-invoked만 가진 task = UI 0(System).
- **ReadModel**: 무조건 생성 UI 0. 조회화면 판정분만 UI 승격, 나머지는 `ATTACHED_TO {role:'display'}`(SC-003).
- **불변**: Command/Event `task_id` 회귀 0(SC-005). A2A BpmTask/NEXT 불변.
- **멱등**: 재인제스천 시 task당 1 UI 유지(중복 0).

## 상태/전이

- 인제스천 생성 단계 — 1방향(문서→그래프). 트리거/조회 판정 결과는 통합 뷰에서 사용자 수정 가능(D4).
- 기존 세션(재인제스천 전)은 Command당 UI 상태 → 통합 뷰가 오류 없이 표시(FR-011).
