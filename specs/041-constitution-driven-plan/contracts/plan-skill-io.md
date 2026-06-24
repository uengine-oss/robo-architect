# Contract: `robo-proposal-plan` skill I/O

**Skill**: `skills/robo-proposals/robo-proposal-plan/SKILL.md`
**Extends**: `robo-proposal-intent` (reuses its tactical-decomposition references: aggregates, commands-events, properties, gwt, readmodels-policies, invariants-ui, traceability).

## Purpose
Take an **approved Strategic Diff** plus the **Constitution** and produce: (1) the Tactical Diff, (2) an impact analysis, and (3) a constitution-grounded implementation plan with concrete microservice architecture decisions.

## Input (Human Prompt)
```
Proposal ID: PRO-NNN
승인된 Strategic Diff(JSON): <epics/features/userStories/processes>
Constitution(parsedFields + raw): <architectureStyle, repoStrategy, repoMode, techStack, designPrinciples, raw>
현재 도메인 구성 요소 목록: <existing nodes for tactical refs / impact>
사용자 피드백(재생성): (있을 경우)
```

## Overrides on robo-proposal-intent
1. **Drop** strategic-decomposition steps (BC/Feature/UserStory/Process identification) — those are now Intent's output and are supplied as input.
2. **Keep** tactical decomposition (Aggregate/Command/Event/ReadModel/Policy/Invariant/UI) per the inherited references.
3. **Add** an architecture-plan step that emits `ArchitectureDecision[]` for the five required aspects, each consistent with the Constitution and traceable to a Constitution section (or listed in `constitutionGaps`).

## Output (final `event: done`)
```json
{
  "tacticalDiff": [ /* same shape as today's intent tacticalDiff */ ],
  "implementationPlan": {
    "version": 1,
    "architectureDecisions": [
      { "aspect": "DEPLOYMENT_ENV",          "decision": "…", "rationale": "…", "constitutionRef": "Tech Stack" },
      { "aspect": "INGRESS",                  "decision": "…", "rationale": "…", "constitutionRef": "…" },
      { "aspect": "SERVICE_MESH_FRAMEWORK",   "decision": "…", "rationale": "…", "constitutionRef": "…" },
      { "aspect": "FRONTEND",                 "decision": "…", "rationale": "…", "constitutionRef": "…" },
      { "aspect": "REPO_MAPPING",             "decision": "…", "rationale": "…", "constitutionRef": "Repo Strategy" }
    ],
    "constitutionGaps": [ "<required aspect the constitution is silent on>" ],
    "interContextIntegrations": [
      { "fromContext": "Ordering", "toContext": "Payment", "message": "ChargePayment", "kind": "COMMAND", "sync": true, "rationale": "…" },
      { "fromContext": "Payment", "toContext": "Ordering", "message": "PaymentConfirmed", "kind": "EVENT", "sync": false, "rationale": "…" }
    ],
    "messagingChannel": "Kafka",
    "serviceDevEnvironments": [
      { "service": "Ordering", "runtime": "JDK 21 / Spring Boot 3", "dockerBaseImage": "eclipse-temurin:21-jre", "dependencies": ["kafka","postgres"], "composeServices": ["kafka","postgres"], "scopeNote": "Ordering 개발자는 kafka+postgres 만 로컬 구동" }
    ],
    "tacticalSummary": "…"
  }
}
```

## Inter-context integration & dev environments (microservices, ≥2 contexts)
- Classify each cross-context interaction as `EVENT` (pub/sub), `COMMAND`, or `QUERY` per ddd-starter Step 5 (Connect / Message Flow — https://github.com/jinyoung/ddd-starter-skill-korean). **Default to event-driven pub/sub**; reserve synchronous `QUERY`/`COMMAND sync` for genuinely synchronous needs (FR-011a).
- Define `messagingChannel` for any pub/sub (default **Kafka**, unless the constitution's tech stack dictates otherwise — FR-011b).
- Define one `serviceDevEnvironment` per service: Docker base, **scoped** infra dependencies, and a `scopeNote` so a future multi-repo split lets each developer run only their service's slice (FR-011c).
- Monolith / single context ⇒ these arrays are empty and `messagingChannel` is null.

## Rules
- If `architectureStyle = MONOLITH`, the plan MUST reflect a single deployable and MUST NOT fabricate `INGRESS`/`SERVICE_MESH_FRAMEWORK` infrastructure that a monolith does not need (FR-012) — such aspects may be marked "N/A (monolith)" rather than invented.
- Every required aspect MUST appear in `architectureDecisions` OR `constitutionGaps` (SC-003); silent omission is a contract violation.
- `REPO_MAPPING` MUST honor `repoStrategy`/`repoMode` (mono-repo vs split-git vs reuse-existing).
- Impact analysis is produced by the backend (`impact_builder`) after this skill returns the tactical diff; the skill need not recompute graph traversal.
