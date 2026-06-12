# Skills Contract: Requirement Change Management (038)

## Constitution X 준수: Skill-First AI 워크플로우

모든 AI 처리는 `skills/robo-changes/` 스킬이 수행. 백엔드는 PTY 실행 + stdout 파싱 + Neo4j 반영만 담당.

---

## 스킬 디렉터리 구조

```text
skills/robo-changes/
├── robo-change-specify/    # Change → EFFECT 분석 (어떤 US/Aggregate 영향받는지)
│   └── SKILL.md            # extends: speckit-specify (Override: 영향 분석 단계 추가)
├── robo-change-plan/       # EFFECT 대상 설계 변경 계획 수립
│   └── SKILL.md            # extends: speckit-plan (Override: Change 컨텍스트 주입)
└── robo-change-tasks/      # 구현 태스크 목록 생성
    └── SKILL.md            # extends: speckit-tasks (Override: CHG-NNN 인수 처리)
```

---

## robo-change-specify

**목적:** Change의 자연어 프롬프트를 분석하여 영향받는 UserStory·Feature·Aggregate 목록 및 EFFECT 이유 결정.

**호출 방식:**
```bash
claude -p skills/robo-changes/robo-change-specify/SKILL.md \
  --change-id CHG-003 \
  --prompt "반품 기간을 7일에서 14일로 연장" \
  --project-path /path/to/project
```

**Expected stdout (파싱 대상):**
```json
{
  "changeId": "CHG-003",
  "effects": [
    {
      "nodeId": "US-012",
      "nodeLabel": "UserStory",
      "reason": "반품 기간 변경으로 인수조건 수정 필요",
      "impactLevel": "HIGH"
    }
  ]
}
```

**Backend parser:** `services/change_specify_parser.py`
- JSON 파싱 → EFFECT 관계 Neo4j 생성

---

## robo-change-plan

**목적:** EFFECT 대상 노드를 기반으로 각 노드별 설계 변경 계획 수립 (Aggregate 수정, Command 추가 등).

**호출 방식:**
```bash
claude -p skills/robo-changes/robo-change-plan/SKILL.md \
  --change-id CHG-003 \
  --project-path /path/to/project
```

**Expected stdout:**
```json
{
  "changeId": "CHG-003",
  "designChanges": [
    {
      "nodeId": "AGG-order",
      "nodeLabel": "Aggregate",
      "changeType": "MODIFY_PROPERTY",
      "description": "returnPeriod 속성을 7에서 14로 변경"
    }
  ]
}
```

**Backend parser:** `services/change_plan_parser.py`

---

## robo-change-tasks

**목적:** 승인된 Change(CHG-NNN)에 대한 구현 태스크 목록 생성 및 실행.

**호출 방식:**
```bash
claude -p skills/robo-changes/robo-change-tasks/SKILL.md \
  --change-id CHG-003 \
  --project-path /path/to/project
```

**Expected stdout (스트리밍):**
```
PHASE:planning
TASK:T-001:주문 Aggregate returnPeriod 속성 변경:PENDING
TASK:T-002:US-012 인수조건 업데이트:PENDING
PHASE:executing
TASK_DONE:T-001
TASK_DONE:T-002
PHASE:done
```

**Backend parser:** `services/change_tasks_parser.py`
- 각 라인 파싱 → SSE event 전송 → 완료 시 Change status → IMPLEMENTED

---

## skill_runner.py 재사용 패턴

```python
# api/features/requirement_changes/services/skill_runner.py
# 기존 api/features/claude_code/ PTY 패턴 재사용

async def run_skill_sse(skill_name: str, args: dict, sse_queue):
    """PTY로 스킬 실행, stdout을 SSE queue로 전달"""
    skill_path = f"skills/robo-changes/{skill_name}/SKILL.md"
    cmd = build_claude_command(skill_path, args)
    await run_pty_and_stream(cmd, sse_queue)
```

---

## SKILL.md extends 패턴

각 SKILL.md는 기존 speckit 스킬을 `extends:`로 상속:

```yaml
---
name: robo-change-tasks
extends: speckit-tasks
description: Change ID를 인수로 받아 구현 태스크를 생성하고 실행
args:
  - name: change-id
    description: CHG-NNN 형식의 Change ID
    required: true
  - name: project-path
    required: true
overrides:
  - step: "load-spec"
    action: "REPLACE"
    content: |
      # Change 컨텍스트 로드
      Neo4j에서 {change-id}의 EFFECT 대상 노드, 설계 변경 계획을 조회하여
      작업 컨텍스트를 구성한다.
---
```
