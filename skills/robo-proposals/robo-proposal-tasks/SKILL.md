# Skill: robo-proposal-tasks

## Purpose
Proposal의 **Strategic Diff**(Epic/Feature/UserStory/Process)와 **Tactical Diff**(Aggregate/Command/Event/VO)를 입력받아, 격리된 Git Worktree 샌드박스에서 그대로 구현 가능한 **구현 작업 목록(tasks)** 으로 분해한다. 결과는 speckit tasks 형식의 체크리스트로 워크트리에 기록되고, 구현 탭이 진행률 추적에 사용한다.

이 스킬은 **구현하지 않는다** — 어떤 작업들이 필요한지 분해해 나열만 한다. 실제 구현은 이후 Claude Code 셀이 이 목록을 보고 수행한다.

## Input (Human Prompt)
```
Proposal ID: PRO-NNN
제목: <proposal title>
원본 프롬프트: <user's natural language requirement>

Strategic Diff (JSON):
{ ...epics/features/userStories/processes... }

Tactical Diff (JSON):
[ ...aggregate/command/event/vo 변경... ]
```

## Output Format

먼저 분석 서술(narration)을 스트리밍한 뒤, 빈 줄을 두고 아래 JSON을 출력한다.

```json
{
  "tasks": [
    {
      "id": "T001",
      "phase": "Phase 1: Setup",
      "text": "결제 도메인 디렉터리 구조 생성",
      "files": ["src/payment/"],
      "parallel": false
    },
    {
      "id": "T002",
      "phase": "Phase 2: Domain",
      "text": "PartialRefundAmount VO 추가",
      "files": ["src/payment/PartialRefundAmount.ts"],
      "parallel": true
    },
    {
      "id": "T003",
      "phase": "Phase 3: API",
      "text": "부분 환불 요청 Command 핸들러 구현",
      "files": ["src/payment/RefundCommand.ts"],
      "parallel": false
    }
  ]
}
```

필드:
- `id` — `T001`부터 연속. 의존 순서대로 나열.
- `phase` — `Phase N: <이름>` 형식. 같은 phase끼리 묶인다(Setup → Domain → API → Frontend → Test/Polish 흐름 권장, 프로젝트에 맞게).
- `text` — 한 줄의 실행 가능한 작업 설명.
- `files` — (선택) 생성/수정 예상 파일·디렉터리 경로 목록. 모르면 빈 배열.
- `parallel` — (선택) 다른 파일이라 병렬 수행 가능하면 true.

## 스트리밍 출력 방식 (필수)
JSON을 출력하기 **전에** 반드시 분해 과정을 한국어로 서술하세요. 각 줄이 실시간으로 사용자에게 표시되어, "어떤 작업들이 나오는지" 미리 보게 됩니다.

형식: `[태그] 내용`
- `[검토]` Strategic/Tactical Diff에서 무엇을 바꾸는지 파악
- `[작업]` 도출한 개별 작업 (한 줄에 하나씩)
- `[순서]` 의존/단계 구성 판단

예시:
```
[검토] Tactical: 환불 Aggregate에 PartialRefundAmount VO 추가, 부분환불 Command 신규
[검토] Strategic: "부분 환불 요청" UserStory 1건 신규
[작업] 결제 도메인 VO 파일 생성 (PartialRefundAmount)
[작업] 부분 환불 Command 핸들러 구현
[작업] 부분 환불 금액 검증 규칙 추가
[작업] 프런트 환불 요청 폼에 부분금액 입력 필드 추가
[순서] Setup → Domain(VO) → API(Command/검증) → Frontend
```

이 서술을 먼저 출력한 뒤, 빈 줄을 두고 JSON을 출력하세요.

## Rules
1. **구현하지 말 것** — 코드를 작성하지 말고 작업 목록만 분해한다. (파일을 만들거나 수정하지 않는다.)
2. **Diff 충실** — Tactical Diff의 각 변경(VO append, Command 신규 등)과 Strategic Diff의 각 UserStory/Feature가 적어도 하나의 task로 커버되어야 한다.
3. **의존 순서** — 기반(Setup/도메인 모델) → 행위(Command/Event) → 표면(API/Frontend) → 검증(Test/Polish) 순으로 배열한다.
4. **단위 적절히** — task는 한 번의 논리적 커밋 단위. 너무 잘게(파일 1줄)도, 너무 크게(전체 기능)도 쪼개지 않는다. 통상 4~15개.
5. **JSON 형식 준수** — 응답 끝에 위 스키마의 JSON을 정확히 출력. narration과 JSON 사이에 빈 줄.
6. **DDD 용어 유지** — UserStory, Aggregate, Command, Event, VO 용어를 그대로 사용.
