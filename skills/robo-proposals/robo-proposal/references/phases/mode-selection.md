# Mode Selection

Runs once, when a **new** Proposal is about to be created. Its job is to fix the
decomposition `mode` passed to `proposal_create`. It never runs on resume.

## 1. Detect an explicit mode

Treat the mode as **explicitly given** when the prompt names it in any of these forms:

- Structured input: `mode: SIMPLIFIED` or `mode: DETAILED_DDD`.
- Natural language naming a mode, e.g. "SIMPLIFIED 모드로", "간소화 모드로", "간단하게",
  "Detailed DDD로", "상세 DDD로", "DDD 단계로 분해해줘", "이벤트 스토밍부터".

If a mode is explicit → skip the question, call `proposal_create` with that mode
immediately, and continue the normal flow. Do not ask.

## 2. Ask when no mode is given

If the user requests a new Proposal without naming a mode, **prefer the host's
structured question tool and wait**:

- Claude Code: `AskUserQuestion`
- Hosts exposing the equivalent as `AskQuestion`: use `AskQuestion`

Do **not** return an `action:"clarify"` JSON envelope. Do not call
`proposal_create` or produce a Strategic Diff draft yet. The lifecycle envelope
contract applies only after a Proposal exists.
Invoke the structured question tool directly; do not use tool discovery/search for
this built-in. If the tool call is unavailable or rejected (notably in Claude Code
`-p`/print mode), fall back to a concise plain-text question that presents the same
two options and asks the user to reply with one. Then wait. Never emit JSON or
assume a default merely because the tool is unavailable.

Submit one single-select question (`multiSelect: false`) with these two options:

- Label: `SIMPLIFIED (간소화)`
  Description: `자연어 요구사항에서 바로 Strategic Diff와 구현계획으로 빠르게 진행합니다. 대부분의 변경/소규모에 적합합니다.`
- Label: `DETAILED DDD (상세 DDD)`
  Description: `6단계 DDD 분해를 거쳐 이벤트 스토밍, 컨텍스트, 애그리거트까지 심층 설계합니다. 복잡하거나 새로운 도메인에 적합합니다.`

Use the question `어떤 분해 모드로 Proposal을 생성할까요?` and a short header
such as `분해 모드`. For the plain-text fallback, render the same question,
labels, and descriptions as a short list. This pre-creation question is **not** recorded via
`proposal_record_question`.

## 3. Resolve the answer

- User picks SIMPLIFIED → create with `mode: SIMPLIFIED`.
- User picks DETAILED DDD → create with `mode: DETAILED_DDD`.
- User says to just proceed / "알아서 해줘" / answers without choosing → create with
  `mode: SIMPLIFIED` (default), and state in the reply that SIMPLIFIED was used.

After the mode is fixed, call `proposal_create` and follow the normal routing
(`references/common/routing.md`). Always pass the user's raw requirement text as the
required `originalPrompt` argument together with `mode` (see
`references/common/mcp-tools.md` → `proposal_create`).
