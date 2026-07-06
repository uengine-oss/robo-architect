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

If the user requests a new Proposal without naming a mode, **ask first and wait**.
Do not call `proposal_create`, do not produce a Strategic Diff draft yet.

Present both options with a one-line description each, for example:

> 어떤 모드로 진행할까요?
> - **SIMPLIFIED (간소화)** — 자연어 요구사항에서 바로 Strategic Diff(Epic·Feature·User Story)
>   초안을 만들고 Tactical Diff·구현계획으로 빠르게 진행합니다. 대부분의 변경/소규모에 적합합니다.
> - **DETAILED DDD (상세 DDD)** — ddd-starter 6단계(Discover→Decompose→Strategize→Connect→
>   Define→Tactical)를 거치며 이벤트 스토밍·서브도메인 분류·바운디드 컨텍스트·애그리거트 설계까지
>   심층 분해합니다. 복잡하거나 새로운 도메인을 설계할 때 적합합니다.
>
> 그냥 진행하라고 하시면 **SIMPLIFIED** 모드로 진행합니다.

Return an `action:"clarify"` envelope for this question (no `proposalId` yet — the
Proposal does not exist). This is a pre-creation conversational question, so it is
**not** recorded via `proposal_record_question`.

## 3. Resolve the answer

- User picks SIMPLIFIED → create with `mode: SIMPLIFIED`.
- User picks DETAILED DDD → create with `mode: DETAILED_DDD`.
- User says to just proceed / "알아서 해줘" / answers without choosing → create with
  `mode: SIMPLIFIED` (default), and state in the reply that SIMPLIFIED was used.

After the mode is fixed, call `proposal_create` and follow the normal routing
(`references/common/routing.md`).
