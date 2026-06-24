# Skill: robo-project-constitution

## Purpose
대상 프로젝트(Proposal 의 `projectRoot`)의 **Constitution**(헌장)을 만들거나 보정한다.
4개 결정 영역을 다룬다: **① 설계 원칙 ② 기술 스택 ③ 모놀리스 vs 마이크로서비스 ④ 레포 전략**(mono-repo vs repo-per-service; 분리 시 split-git vs reuse-existing).

이 스킬은 spec-kit 의 `speckit-constitution` 동작(사용자 입력·레포 컨텍스트로부터 값 도출 + 템플릿 채움)을 **상속/재사용**한다. 새로 발명하지 않는다.

## 핵심 규칙 (이 스킬의 차별점)
1. **프롬프트에서 시드(FR-002a)** — Proposal 의 원본 자연어 프롬프트에 이미 드러난 기술 선호(언어/프레임워크/"마이크로서비스"/배포 힌트/프론트엔드 선택 등)를 스캔해, 해당 결정 영역을 **미리 채운 제안 답변**으로 제시한다. 다시 묻지 않는다. 사용자는 수락/수정할 수 있다.
2. **게이팅 질문은 반드시 묻는다(가장 중요)** — 아래 **핵심 결정**은 사용자가 직접 정해야 한다. 프롬프트에 명시 시드(FR-002a)가 없는 한, **자동 확정하지 말고 `action:"question"` 으로 한 번에 하나씩 물어라.** 추천값(FR-002b)은 질문을 **건너뛰는 수단이 아니라**, 그 질문의 **기본 선택(추천)** 으로 제시한다. 사용자가 확인/변경한다.
   - **반드시 물어야 하는 게이팅 질문**: ① 아키텍처 스타일(MONOLITH/MICROSERVICES) ② 기술 스택(백엔드/프론트엔드/스토어) ③ 레포 전략(MONOREPO/REPO_PER_SERVICE). 그 외 설계 원칙은 추천 후 한 번 확인.
   - 이 세 가지(+조건부 후속)가 **사용자 인터뷰 답변에 모두 들어오기 전에는 `action:"done"` 으로 가지 마라.** 답변이 아직 없으면 다음 미답변 게이팅 질문을 `action:"question"` 으로 내라.
3. **적합성 추천(FR-002b)** — 각 게이팅 질문의 옵션 중 **프로젝트 의도에 적합한** 것을 `recommended` 로 표시하고 한 줄 근거(`rationale`)를 붙인다. (예: CRUD 위주·소수 BC → 모놀리스 추천; 높은 fan-out·독립 배포 → 마이크로서비스 추천.)
4. **명시성** — 미리 채운 값(seed)/추천 값은 반드시 그렇게 **표시**한다(조용히 확정 금지, Principle IV).
5. **언어 정책** — 생성 산출물은 사용자 기어 아이콘 언어 설정을 따른다.
6. **의존성 인지 — 무관한 질문만 생략(최소화 ≠ 자동결정)** — 질문 사이엔 의존이 있어, 한 답이 뒤따르는 질문을 열거나 닫는다. **닫힌(무의미한) 질문만 생략**하고, 게이팅 질문은 생략하지 않는다:
   - `architectureStyle = MONOLITH` → ingress/게이트웨이·service mesh·서비스 간 연동·서비스별 배포환경 질문을 **생략**(모놀리스에 무의미). 단, 기술 스택·레포 전략은 여전히 묻는다.
   - `architectureStyle = MICROSERVICES` → 게이트웨이/ingress, 배포 대상, service mesh/프레임워크, repo-per-service 여부를 **추가로** 묻는다.
   - `repoStrategy = MONOREPO` → repoMode(split-git vs reuse-existing) 질문 **생략**.
   **목표: 핵심 결정은 사용자가 직접, 무의미한 질문은 생략.**

질문 의존 트리는 `references/interview-questions.md` 에 있다 — 반드시 읽어라.

## Input (Human Prompt)
```
Proposal ID: PRO-NNN
원본 프롬프트(자연어 요구사항): <originalPrompt — 기술 선호가 섞여 있을 수 있음>
프로젝트 의도 요약: <intent / strategic diff 제목들, 있으면>
기존 Constitution: <projectRoot 에 이미 있으면 raw 본문>
projectRoot: <대상 레포 경로>
사용자 인터뷰 답변: (있을 경우) Q0: ... → A: ...
```

## 절차 (이 순서로 사고하라)
1. **기존 헌장 확인** — 입력에 기존 Constitution 이 있으면, 인터뷰 대신 보정 모드로 전환(사용자 지시 반영).
2. **프롬프트 스캔** — 명시 시드(FR-002a)만 추출 → `seededFrom` 인용(그 영역만 질문 생략).
3. **미답변 게이팅 질문 판단** — 입력의 "사용자 인터뷰 답변"을 보고, 아직 안 정해진 게이팅 결정(아키텍처 스타일 → 기술 스택 → 레포 전략 → 조건부 후속)을 찾는다.
4. **다음 질문 1개 출력** — 미답변 게이팅 질문이 있으면 `action:"question"` 으로 **그 1개만** 낸다(추천 옵션을 `recommended`+`rationale` 로 표시). 무의미한(닫힌) 질문은 생략.
5. **모두 답변되면 헌장 작성** — 게이팅 결정이 모두 들어오면, spec-kit constitution 형식(섹션: Core Principles / Technology Constraints / Architecture / Repository Strategy / Governance)으로 `raw` 를 작성하고 `action:"done"` 으로 낸다.
6. **출력** — 아래 question 또는 done 페이로드.

## 스트리밍 출력 (필수, Principle III)
- `[질문]` 으로 시작하는 줄: 갭 질문(선택지 포함)을 한 줄씩.
- `[제안]` 미리 채운 값(+근거 인용).
- `[추천]` 적합성 추천(+근거).
그 뒤 빈 줄을 두고 최종 JSON 을 출력한다.

## Output Format (최종 JSON)
```json
{
  "action": "question | done",
  "question": { "index": 1, "question": "아키텍처 스타일은?", "options": ["MONOLITH","MICROSERVICES"], "recommended": "MONOLITH", "rationale": "BC 2개·CRUD 위주 → 단순" },
  "raw": "<full constitution markdown>",
  "fields": {
    "designPrinciples": "…",
    "techStack": "…",
    "architectureStyle": "MONOLITH | MICROSERVICES",
    "repoStrategy": "MONOREPO | REPO_PER_SERVICE",
    "repoMode": "SPLIT_GIT | REUSE_EXISTING | null"
  },
  "seededFrom": ["<프롬프트 인용>"],
  "recommendations": [{ "area": "architectureStyle", "recommended": "MONOLITH", "rationale": "…" }]
}
```
`action:"question"` 이면 `question` 만, `action:"done"` 이면 `raw`+`fields`+`seededFrom`+`recommendations` 를 채운다.

## Rules
1. 프롬프트/의도가 뒷받침하지 않는 선호를 **발명하지 말 것** — 모르면 질문하거나 gap 으로 둔다.
2. `architectureStyle` 와 `repoStrategy` 는 plan 단계 전에 반드시 확정되어야 한다.
3. 코드를 작성하지 말 것 — 헌장 문서만 생성한다.
