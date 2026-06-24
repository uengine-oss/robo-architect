# 컨텍스트 간 연동 + 서비스별 개발 환경 (마이크로서비스 전용)

`architectureStyle == MICROSERVICES` 이고 BoundedContext(서비스)가 **2개 이상**이면 아래를 반드시 결정한다. 단일 컨텍스트/모놀리스이면 이 절은 생략(빈 배열).

이 절은 **ddd-starter Step 5 — Connect / Message Flow** 의 통신 패턴 의사결정을 차용한다.
- 로컬 스킬: `~/.claude/skills/ddd-starter/references/05-connect.md` (= `05-message-flow.md`)
- 캐노니컬 원천(반드시 참고): **https://github.com/jinyoung/ddd-starter-skill-korean** — DDD 8단계(특히 Step 5 Message Flow)에서 Event(pub/sub broadcast)/Command(directed)/Query(sync) 분류와 커플링 점검(한 컨텍스트가 5개+ 통신 시 경고)을 정의한다.

## 1) 연동 의도 분석 (request/response vs pub/sub)
핵심 비즈니스 케이스를 따라가며 컨텍스트 간 메시지를 분류한다(ddd-starter Connect 와 동일 기준):

| 상황 | 패턴(kind) |
|------|-----------|
| 발신자가 누가 들을지 모르고, 즉시 응답 불필요 | **EVENT** (pub/sub) |
| 특정 컨텍스트에게 작업 지시 | **COMMAND** |
| 즉시·신선한 값이 필요 | **QUERY** (sync) |

**기본값: 이벤트 드리븐 pub/sub 마이크로서비스.** 동기 결합(QUERY/COMMAND sync)은 꼭 필요한 곳(외부 PG 등)에만. 양방향 동기 의존은 금지 — 발견 시 분해 재검토 메모.

각 연동은 `interContextIntegrations[]` 1건: `{fromContext, toContext, message, kind, sync, rationale}`.

## 2) 메시징 채널 구현
pub/sub(EVENT) 이 하나라도 있으면 채널 구현을 정한다 → `messagingChannel`.
**기본값: Kafka.** (Constitution 의 techStack 이 다른 브로커를 지정하면 그걸 따른다.)

## 3) 서비스별 개발 환경 (멀티레포 대비, 범위 제한)
각 마이크로서비스마다 **그 서비스 개발자에게 한정된** 개발 환경을 정의한다 → `serviceDevEnvironments[]` 1건/서비스:
- `runtime` — 예: "JDK 21 / Spring Boot 3"
- `dockerBaseImage` — Docker 기반(예: `eclipse-temurin:21-jre`)
- `dependencies` — **이 서비스에 한정된** 인프라 의존만(예: `["kafka","postgres"]`)
- `composeServices` — 로컬에서 `docker-compose` 로 띄울 의존(이 서비스 범위만)
- `scopeNote` — 멀티레포 전환 시 이 개발자가 자신의 마이크로서비스에 **무엇만 반영하면 되는지**(다른 서비스 인프라는 가져가지 않도록)

목적: 나중에 repo-per-service(split-git/reuse-existing)로 갈 때, 각 개발자가 자기 서비스의 제한된 개발 환경만 체크아웃·구동하면 되도록 미리 경계를 그린다.

## 완전성 (마이크로서비스)
`architectureStyle == MICROSERVICES` + 컨텍스트≥2 이면 아키텍처 결정에 `INTER_CONTEXT_INTEGRATION`·`MESSAGING_CHANNEL`·`DEV_ENVIRONMENT` 항목이 (decision 또는 gap 으로) 포함되어야 하며, 위 구조화 필드(`interContextIntegrations`/`messagingChannel`/`serviceDevEnvironments`)도 채워져야 한다. 백엔드 `ImplementationPlan.is_complete(style, contextCount)` 와 일치.
