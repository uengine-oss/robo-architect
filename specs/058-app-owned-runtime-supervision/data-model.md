# Phase 1 — 데이터 모델

**Feature**: 058 설치본 런타임 감독과 복구 | **Date**: 2026-09-17

런타임 상태는 **프로세스 안에 사는 값**이고, BPMN 출처는 **graph 에 남는 값**이다.
둘을 섞지 않는다.

## 1. ManagedService — 앱이 수명을 책임지는 하나

| 필드 | 뜻 | 비고 |
|---|---|---|
| `id` | `graph` \| `mindsdb` \| `analyzer` \| `catalog` \| `fabric` \| `parser` \| `gateway` \| `pdf2bpmn` \| `architect` | compose 의 `org.uengine.robo.component` 와 같은 값. `architect` 만 호스트 프로세스. **`neo4j` 였다가 `graph` 로 바꿨다**(T078) — 엔진 이름이 아니라 역할 이름이어야 한다 |
| `owner` | `app` \| `external` | 화면에서 갈라 보여야 한다 (FR-005) |
| `displayName` | 사람이 읽는 이름 | |
| `state` | `pending` \| `starting` \| `ready` \| `degraded` \| `failed` \| `stopped` | 아래 §1.1 |
| `stateReason` | 왜 그 상태인가 | 실패 시 필수. 비밀정보 금지 (FR-011) |
| `capabilities` | 이 서비스가 없으면 못 쓰는 기능 id 목록 | §2 |
| `lastProbeAt` / `lastProbeMs` | 마지막 기능 프로브 시각·소요 | |
| `probeKind` | `health` \| `capability` | **무엇으로 판정했는지 남긴다** |
| `restartCount` / `restartGaveUpAt` | 되살리기 시도 | FR-018 |
| `version` | 이미지 태그 또는 프로세스 버전 | FR-022 |
| `endpoint` | 루프백 주소 (있을 때) | 포트가 바뀌면 여기도 바뀐다 |

### 1.1 상태 전이

```
pending ──> starting ──> ready
              │            │
              │            ├─> degraded   기능 프로브 실패 (컨테이너는 살아 있음)
              │            └─> failed     프로세스/컨테이너가 죽음
              └─> failed                  기동 실패
failed ──> starting   (되살리기 시도, 한계 전까지)
failed ──> stopped    (한계 도달 → 사람에게 넘김, FR-018)
ready/degraded ──> stopped   (사용자가 명시적으로 내림, FR-015)
```

**`degraded` 가 이 스펙의 핵심이다.** 09-17 실측에서 pdf2bpmn 은 healthy 인데 502 를
냈다. 그 상태를 `ready` 로 부르면 안 되고 `failed` 로도 부를 수 없다 — 컨테이너는
살아 있고 다른 경로는 쓸 수 있다.

**규칙**: `probeKind: "health"` 만 통과한 서비스는 **`ready` 가 아니다.** 기능 프로브가
통과해야 `ready` 다. 그 전까지는 `starting`.

## 2. Capability — 기능 단위

서비스와 화면 기능 사이의 다리. **"analyzer 가 죽었다"를 "코드 분석 탭을 못 쓴다"로
번역하는 표**다(FR-004).

| 필드 | 뜻 |
|---|---|
| `id` | `design` \| `document-ingestion` \| `bpmn-generation` \| `legacy-analysis` \| `code-generation` \| `collaboration` |
| `displayName` | 화면에 쓰는 이름 |
| `requires` | 필요한 `ManagedService.id` 목록 |
| `state` | `available` \| `unavailable` \| `degraded` (파생값 — 저장하지 않는다) |
| `blockedReason` | 왜 못 쓰는가 + **사용자가 할 수 있는 일** |

파생 규칙.

```
requires 가 전부 ready            → available
하나라도 failed/stopped           → unavailable
하나라도 degraded (failed 없음)   → degraded
```

**저장하지 않고 매번 파생한다.** 두 곳에 같은 사실을 두면 어긋난다.

## 3. RuntimeState — 렌더러가 보는 전체 그림

기존 `shared/ipc-contract.ts` 의 `RuntimeState` 를 **확장**한다. 기존 필드는 남긴다.

| 필드 | 상태 | 비고 |
|---|---|---|
| `appVersion` | 유지 | |
| `backendPort` · `backendPid` | 유지 | |
| `status` | **파생값으로 유지** | 하위 호환. `services` 에서 계산 |
| `dataDir` | 유지 | |
| `updateState` | 유지 | 이 스펙에서 안 건드린다 |
| `services` | **신규** — `ManagedService[]` | |
| `capabilities` | **신규** — `Capability[]` | 파생값 |
| `releaseId` | **신규** | 앱·서비스 버전 조합 추적 (FR-022) |
| `dockerAvailable` | **신규** | 컨테이너 실행 환경 자체의 유무 |
| `graphGuard` | **신규** — §4 | |

`status` 파생 규칙(하위 호환).

```
architect 가 ready 이고 나머지에 failed 없음   → "ready"
architect 가 starting                          → "starting-backend"
컨테이너가 starting                            → "starting-db"
architect 가 failed                            → "fatal"
```

## 4. GraphGuard — 설계/분석 영역 분리 판정

| 필드 | 뜻 |
|---|---|
| `designGraph` | Architect 가 쓰는 graph 이름 |
| `analyzerGraph` | analyzer 스택이 쓰는 graph 이름 |
| `separated` | 둘이 다른가 |
| `checkedAt` | |
| `blockedCapabilities` | 분리가 깨졌을 때 잠근 기능 (`legacy-analysis`) |

**분리가 깨지면 `legacy-analysis` 를 열지 않는다**(FR-008). analyzer 는 대상 graph 를
무조건 비우므로, 같으면 설계가 사라진다.

**빈 graph 로 판정하지 않는다** — 이름 비교로 한다. 데이터가 없으면 지워져도 티가 안
나기 때문이다.

## 5. ProbeResult — 프로브 한 번의 결과

| 필드 | 뜻 |
|---|---|
| `serviceId` | |
| `kind` | `health` \| `capability` |
| `outcome` | `pass` \| `fail` \| `skipped` \| `error` |
| `detail` | 실패 사유. **비밀정보 금지** |
| `durationMs` | |

**`outcome` 에 네 값이 있는 이유**가 이 스펙의 성격이다.

```
fail      프로브가 돌았고 조건을 못 맞췄다
error     프로브 자체가 못 돌았다 (의존 도구 없음 등)
skipped   앞 단계가 안 돼서 재지 않았다
```

셋을 뭉쳐 `false` 로 만들면 **"0건"과 같은 병**이 된다. 09-17 에 프로브 안에서
`try/except` 가 import 실패를 삼켜 조용히 빈 값을 낸 사고가 실제로 있었다.

## 6. graph 에 남는 것 — BpmProcess 출처

**이것만 영속된다.** 위의 것들은 전부 프로세스 수명이다.

기존 `BpmProcess` 노드에 속성 셋을 더한다. **신규 라벨·관계 없음.**

| 속성 | 뜻 | 예 |
|---|---|---|
| `generatedBy` | 어느 경로가 냈나 | `facade` \| `a2a` \| `native` |
| `generationFallbackReason` | 폴백이면 왜 | `facade 502 …; a2a All connection attempts failed` |
| `generatedAt` | 시각 | ISO 8601 |

### 왜 노드에 두나

진행 스트림(`🔌 Phase 1 소스: …`)은 **지나가면 사라진다.** 앱을 다시 열면 그 BPMN 을
누가 냈는지 알 길이 없다. 그리고 **결과물로는 못 가린다** — 09-17 에 facade 를 죽여
놓고 native 가 task 7 · gateway 2 를 그럴듯하게 냈다.

### 검증 규칙

- `generatedBy` 가 `facade` 가 아니면 화면은 **성공처럼 보이면 안 된다**(FR-026).
- 대체 경로를 끈 설정에서는 `generatedBy` 가 `facade` 뿐이어야 한다(FR-027).
- 판정은 **결과물 품질이 아니라 처리 서비스가 받은 요청 수**로 한다(SC-007).

> **Ontological 주의.** 속성 추가는 타입 카탈로그에 컬럼을 만든다. 기존 노드에는
> 그 값이 없다 — **없음과 `native` 를 구분해야 한다.** 옛 데이터는 `generatedBy` 가
> 비어 있고, 그것은 "폴백이었다"가 아니라 **"모른다"** 이다.
