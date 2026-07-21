# Skill: robo-proposal-plan

## Purpose
**승인된 Strategic Diff** + **Constitution** 을 입력으로 받아, 다음을 생성한다:
1. **Tactical Diff** (Aggregate/Command/Event/ReadModel/Policy/Invariant/UI)
2. **Constitution 기반 구현계획**(아키텍처 결정: 배포환경/ingress/service mesh·프레임워크/프론트엔드/레포매핑)

이 스킬은 `robo-proposal-intent` 의 **전술 분해 규칙을 상속**한다(아래 레퍼런스 재사용). 다만 **전략 분해는 하지 않는다** — 그것은 Intent 단계의 산출물이며 입력으로 주어진다.

## 레퍼런스를 먼저 읽어라 (필수)
`robo-proposal-intent` 의 전술 레퍼런스를 그대로 적용한다 (cwd = 저장소 루트):
- `skills/robo-proposals/robo-proposal-intent/references/output-schema.md`
- `skills/robo-proposals/robo-proposal-intent/references/traceability.md`
- `skills/robo-proposals/robo-proposal-intent/references/aggregates.md`
- `skills/robo-proposals/robo-proposal-intent/references/commands-events.md`
- `skills/robo-proposals/robo-proposal-intent/references/properties.md`
- `skills/robo-proposals/robo-proposal-intent/references/gwt.md`
- `skills/robo-proposals/robo-proposal-intent/references/readmodels-policies.md`
- `skills/robo-proposals/robo-proposal-intent/references/invariants-ui.md`
- `skills/robo-proposals/robo-proposal-intent/references/legacy-reference.md`

그리고 이 스킬 고유:
- `skills/robo-proposals/robo-proposal-plan/references/architecture-plan.md` ← **아키텍처 계획 계약**
- `skills/robo-proposals/robo-proposal-plan/references/inter-context-integration.md` ← **컨텍스트 간 연동 + 서비스별 개발환경(마이크로서비스)**

ddd-starter 의 연동 단계도 참고하라(차용):
- `~/.claude/skills/ddd-starter/references/05-connect.md` ← 통신 패턴(Event/Command/Query) 의사결정 가이드
- 캐노니컬 원천: **https://github.com/jinyoung/ddd-starter-skill-korean** (Step 5 Message Flow)

## Input (Human Prompt)
```
Proposal ID: PRO-NNN
승인된 Strategic Diff(JSON): <epics/features/userStories/processes>
Constitution(fields + raw): <architectureStyle, repoStrategy, repoMode, techStack, designPrinciples, raw>
현재 도메인 구성 요소 목록: <기존 노드 — 전술 참조/임팩트용>
사용자 피드백(재생성): (있을 경우)
```

## Overrides (robo-proposal-intent 대비)
1. **전략 분해 단계 제거** — BC/Feature/UserStory/Process 식별을 하지 않는다(입력으로 받음).
2. **전술 분해 유지** — 상속한 레퍼런스대로 Aggregate/Command/Event/ReadModel/Policy/Invariant/UI 도출.
3. **아키텍처 계획 단계 추가** — `architecture-plan.md` 계약대로 `ArchitectureDecision[]` 생성. 5개 필수 항목은 각각 결정되거나 `constitutionGaps` 에 명시되어야 한다.

## 분해 절차
1. **Strategic Diff·레거시 근거 흡수** — 주어진 UserStory/Feature를 입력으로 삼고,
   `legacy-reference.md`의 목록→선택 ID 상세조회로 전술 판단에 필요한 실제 구현만 확인한다.
   공통 계약의 호출 완료 게이트를 통과하기 전에는 최종 JSON을 출력하지 않는다.
2. **Tactical 도출** — 이벤트-우선, Aggregate→Command→Event→ReadModel→Policy→Invariant→UI.
   모든 tactical 항목에 `legacyRefs`를 기록한다(`output-schema.md` 불변식) — 이 실행에서
   실제 검색·검토한 nodeId만, 근거 없으면 `[]`. 서버가 관찰집합 밖 ID를 제거한다.
3. **아키텍처 계획** — Constitution 의 `architectureStyle`/`repoStrategy`/`techStack` 에 일관되게 5개 항목 결정. 각 결정은 가능하면 Constitution 섹션으로 **추적 가능**(`constitutionRef`)해야 한다. 침묵 영역은 `constitutionGaps` 로.
4. **컨텍스트 간 연동(다수 BC)** — `architectureStyle == MICROSERVICES` 이고 BoundedContext≥2 이면 `inter-context-integration.md` 대로: ① 연동 의도 분석(request/response vs pub/sub) → `interContextIntegrations[]`(EVENT/COMMAND/QUERY 분류, **기본 이벤트 드리븐 pub/sub**), ② 메시징 채널(`messagingChannel`, **기본 Kafka**), ③ 서비스별 Docker 개발환경(`serviceDevEnvironments[]` — 멀티레포에서 각 개발자가 자기 서비스 범위만 가져가도록 `scopeNote`/`dependencies`/`composeServices` 제한).
5. **모놀리스 규칙** — `architectureStyle == MONOLITH` 이면 단일 배포로 반영하고, ingress/mesh/연동/서비스별환경 같은 마이크로서비스 전용 항목을 **지어내지 말 것**(해당 항목은 "N/A (monolith)" 로 표기 가능, 위 배열은 비움).
6. **자가 검증** — traceability + 완전성: 항상 5개 항목 + (마이크로서비스 & 다수 컨텍스트면) `INTER_CONTEXT_INTEGRATION`·`MESSAGING_CHANNEL`·`DEV_ENVIRONMENT` 까지 결정 or gap 통과 확인.

## 스트리밍 출력 (필수)
- `[전술]` 도출한 전술 요소 한 줄씩.
- `[아키텍처]` 각 아키텍처 결정(+근거/refs).
- `[갭]` Constitution 이 침묵한 필수 항목.
그 뒤 빈 줄, 최종 JSON.

## Output Format (최종 JSON)
```json
{
  "tacticalDiff": [ /* robo-proposal-intent 의 tacticalDiff 와 동일 형태 */ ],
  "implementationPlan": {
    "version": 1,
    "architectureDecisions": [
      { "aspect": "DEPLOYMENT_ENV",        "decision": "…", "rationale": "…", "constitutionRef": "Technology Constraints" },
      { "aspect": "INGRESS",               "decision": "…", "rationale": "…", "constitutionRef": "…" },
      { "aspect": "SERVICE_MESH_FRAMEWORK","decision": "…", "rationale": "…", "constitutionRef": "…" },
      { "aspect": "FRONTEND",              "decision": "…", "rationale": "…", "constitutionRef": "…" },
      { "aspect": "REPO_MAPPING",          "decision": "…", "rationale": "…", "constitutionRef": "Repository Strategy" }
    ],
    "constitutionGaps": [],
    "interContextIntegrations": [
      { "fromContext": "Ordering", "toContext": "Payment", "message": "ChargePayment", "kind": "COMMAND", "sync": true, "rationale": "외부 PG 동기 호출" },
      { "fromContext": "Payment", "toContext": "Ordering", "message": "PaymentConfirmed", "kind": "EVENT", "sync": false, "rationale": "비동기 pub/sub" }
    ],
    "messagingChannel": "Kafka",
    "serviceDevEnvironments": [
      { "service": "Ordering", "runtime": "JDK 21 / Spring Boot 3", "dockerBaseImage": "eclipse-temurin:21-jre", "dependencies": ["kafka","postgres"], "composeServices": ["kafka","postgres"], "scopeNote": "Ordering 개발자는 kafka+postgres 만 로컬 구동" }
    ],
    "tacticalSummary": "…"
  }
}
```
모놀리스/단일 컨텍스트이면 `interContextIntegrations`/`serviceDevEnvironments` 는 `[]`, `messagingChannel` 은 null.

## Rules
1. **코드를 작성하지 말 것** — 전술 분해 + 계획만 산출한다.
2. **5개 필수 항목**은 `architectureDecisions` 또는 `constitutionGaps` 에 반드시 등장(조용한 누락은 계약 위반, SC-003).
3. **REPO_MAPPING** 은 `repoStrategy`/`repoMode` 를 존중(mono-repo vs split-git vs reuse-existing).
4. 임팩트 분석(그래프 트래버설)은 백엔드(`impact_builder`)가 전술 diff 이후 수행한다 — 스킬이 재계산할 필요 없음.
5. DDD 용어 유지.
