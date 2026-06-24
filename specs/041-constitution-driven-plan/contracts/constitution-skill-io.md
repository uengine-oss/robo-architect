# Contract: `robo-project-constitution` skill I/O

**Skill**: `skills/robo-proposals/robo-project-constitution/SKILL.md`
**Extends**: `speckit-constitution` (reuses its template-filling, section structure, governance/versioning conventions and "derive values from user input / repo context" behavior).

## Purpose
Produce or amend the **target project's** Constitution covering four required decision areas — design principles, tech stack, monolith-vs-microservices, repository strategy — by interviewing the architect, **seeded from technical preferences already present in the Proposal's natural-language prompt**, and **recommending fit-for-purpose defaults** based on the project's intent.

## Input (Human Prompt)
```
Proposal ID: PRO-NNN
원본 프롬프트(자연어 요구사항): <originalPrompt — may contain tech preferences>
프로젝트 의도 요약: <intent summary / strategic diff titles, if available>
기존 Constitution: <raw file contents, if one already exists in projectRoot>
projectRoot: <target repo path>
사용자 인터뷰 답변: (있을 경우) Q0: ... → A: ...
```

## Behavior (Overrides on speckit-constitution)
1. **Pre-fill from the prompt** — scan `originalPrompt` for stated technical preferences (languages, frameworks, datastores, "microservices", deployment hints, frontend choices). Pre-populate the corresponding decision areas and **show them as proposed answers** the architect can accept or override (FR-002, user guidance 2026-06-11).
2. **Recommend by fit** — for any area the prompt does not pin down, propose a recommended option **suited to the project's intent** (e.g. a CRUD-light internal tool → monolith; high-fan-out event system → microservices), with a one-line rationale. The architect confirms or changes it.
3. **Interview only the gaps, dependency-aware (FR-002c)** — questions form a tree; a higher answer opens/closes downstream questions. `architectureStyle = MONOLITH` suppresses ingress/gateway, service-mesh, deployment-target, and repo-per-service follow-ups; `MICROSERVICES` unlocks them. `repoStrategy = MONOREPO` suppresses the `SPLIT_GIT` vs `REUSE_EXISTING` follow-up. Ask the **fewest** questions for the complexity the architect is heading toward; skip anything seeded or confidently recommended. (See the skill's `references/interview-questions.md` dependency tree.)
4. **Emit the Constitution** in the spec-kit constitution format. The backend persists the result as the **project-root `Constitution` Neo4j node** (not a repo file, not per-Proposal). Per-BC overrides are authored later from the Design side, not by this interview.

## Output (final `event: done`)
```json
{
  "raw": "<full constitution markdown>",
  "parsedFields": {
    "designPrinciples": "…",
    "techStack": "…",
    "architectureStyle": "MONOLITH | MICROSERVICES",
    "repoStrategy": "MONOREPO | REPO_PER_SERVICE",
    "repoMode": "SPLIT_GIT | REUSE_EXISTING | null"
  },
  "seededFrom": ["<quote(s) from originalPrompt that drove a pre-fill>"],
  "recommendations": [{ "area": "architectureStyle", "recommended": "MONOLITH", "rationale": "…" }]
}
```

## Rules
- Pre-filled and recommended values MUST be clearly marked as such (not silently committed) — Principle IV.
- The skill MUST NOT invent preferences the prompt/intent do not support; unknowns become questions or are flagged.
- Generated language follows the user's gear-icon language setting (see project generation-language policy).
