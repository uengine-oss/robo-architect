# Implementation Plan: 설치본 런타임 감독과 복구

**Branch**: `enterprise-custom-p` | **Date**: 2026-09-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/058-app-owned-runtime-supervision/spec.md`

## Summary

`054` 가 정한 배포 구성 위에, **무엇이 돌고 있는지 사람이 알 수 있게** 하고 **안 돌 때
돌아올 수 있게** 한다. 핵심은 세 가지다.

1. **준비 판정을 healthcheck 에서 떼어낸다.** 09-17 실측에서 같은 `/healthz 200` 이
   한쪽은 502, 한쪽은 진짜 BPMN 을 냈다. healthcheck 는 자격증명·의존성을 안 본다.
2. **서비스별 상태를 화면까지 올린다.** 지금 `frontend/src` 에는 `app:onBackendStatus`
   구독이 **0건**이다. 8개 컨테이너가 백엔드 상태값 하나로 접혀 있다.
3. **출처를 결과에 남긴다.** 폴백은 `source`/`error` 를 보존하지만 **그래프에 저장되지
   않아** 앱을 다시 열면 증거가 사라진다. 그리고 폴백 결과물은 진짜와 구분되지 않는다
   (실측: facade 죽은 상태에서 native 가 task 7 · gateway 2 를 냈다).

선행 이식 과제 둘을 계획 안에 포함한다 — 그것 없이는 릴리스 자체가 안 나온다.

## Technical Context

**Language/Version**: TypeScript 5.x (Electron 31 main/preload) · Vue 3 (renderer) ·
Python 3.13 (FastAPI) · Python 3.12 (컨테이너 서비스) · Java 17 (parser·gateway)

**Primary Dependencies**: Electron · Docker Compose v2 · FastAPI/uvicorn ·
Spring Cloud Gateway · Ontological(PostgreSQL 확장, Bolt 게이트웨이)

**Storage**: graph = Ontological (프로젝트별 graph) · 사용자 데이터 =
`app.getPath('userData')` + Docker named volume · 비밀 = OS 키체인

**Testing**: Playwright(화면·창 둘) · pytest(백엔드 계약) · `scripts/verify_*.py`
(서버 쪽 물리 검증) · `og-verify/`(저장소 회귀)

**Target Platform**: Windows x64 (납품) · macOS 는 측정 전용, 배포 미검증

**Project Type**: Desktop app (Electron main + Vue renderer + host FastAPI +
app-owned Compose stack)

**Performance Goals**: 첫 실행 기동 10분 이내(2GB tar 적재 포함) · 재실행 60초 이내 ·
서비스 상태 갱신 5초 주기 · 기능 프로브는 LLM 호출 없이 3초 이내

**Constraints**: 외부 인터넷 차단 상태에서 동작 · 루프백 바인딩만 · 비밀정보는
로그·화면·진단에 남기지 않음 · 사용자 데이터는 실행 파일·이미지 교체와 독립

**Scale/Scope**: 앱이 소유하는 서비스 9개(컨테이너 8 + 호스트 백엔드 1) ·
동시 사용자 수 명 · 프로젝트당 graph 1개

## Constitution Check

*GATE: Phase 0 전에 통과해야 한다. Phase 1 설계 후 재확인.*

`.specify/memory/constitution.md` 는 **자리표시자 상태다**(`[PRINCIPLE_1_NAME]` 등).
그래서 강제할 원칙이 파일에 없다. 대신 **이 저장소가 실제로 지켜 온 규칙**을 게이트로
쓴다(`robo-enterprise` 스킬 · `STATUS.md` · `enterprise-done*.md` 에 반복해 기록된 것).

| 게이트 | 이 계획의 판정 |
|---|---|
| 사람이 밟는 경로로 검증한다 | **통과** — 모든 US 가 화면 경로 인수 시나리오를 가진다 |
| 고치기 전에 실패를 먼저 본다 | **통과** — 각 태스크에 재현 단계를 둔다 |
| 결함을 심어 검사가 무는 것을 본다 | **통과** — SC-008. 파괴적 결함은 심지 않는다 |
| "0건"을 결과로 받지 않는다 | **통과** — FR-021 이 요구사항으로 들어가 있다 |
| 개수 말고 내용으로 검증한다 | **통과** — SC-003·SC-010 이 내용 기준이다 |
| 실 데이터를 건드리면 되돌리기를 먼저 만든다 | **통과** — 검증은 `zz_` graph 에서만 |
| 남의 저장소는 브랜치로 넘긴다 | **통과** — 이식 태스크가 전용 브랜치 유지 |

**위반 없음.** 다만 헌장 파일이 비어 있다는 사실 자체는 위험이다 — 별도 과제로 남긴다
(이 스펙의 범위 아님).

## Project Structure

### Documentation (this feature)

```text
specs/058-app-owned-runtime-supervision/
├── plan.md              # 이 파일
├── spec.md
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/           # Phase 1
│   ├── runtime-status-ipc.md
│   └── service-capability-probes.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks 가 만든다 (여기서는 안 만든다)
```

### Source Code (repository root)

```text
desktop/src/
├── main/
│   ├── docker-stack.ts          수정 — 소유 식별·이어받기·명시적 stop·포트 재확보
│   ├── supervisor.ts            신규 — 서비스별 감독·기능 프로브·재기동·백오프
│   ├── service-catalog.ts       신규 — 서비스 ↔ 기능 매핑 (무엇이 못 쓰게 되나)
│   ├── graph-guard.ts           신규 — 설계/분석 graph 분리 검사 (FR-007·008)
│   ├── backend.ts               수정 — 감독 대상으로 편입, 크래시 재기동
│   └── index.ts                 수정 — 상태 푸시 채널, 명시적 stop IPC
├── preload/index.ts             수정 — runtime:* 채널 노출
└── shared/ipc-contract.ts       수정 — RuntimeState 를 서비스 배열로 확장

frontend/src/
├── features/runtime-status/     신규 — 상태 패널·기동 화면·실패 안내
│   ├── RuntimeStatusPanel.vue
│   ├── StartupGate.vue
│   └── runtime.store.js
└── app/                         수정 — 준비 안 된 기능의 진입 차단 (FR-006)

api/features/ingestion/hybrid/
├── document_to_bpm/__init__.py  수정 — 출처를 결과에 실어 보낸다
├── hybrid_workflow_runner.py    수정 — phase1_source 를 영속 대상으로 넘긴다
└── event_storming_bridge/persistence.py  수정 — BpmProcess 에 출처 저장 (FR-025)

frontend/tests/                  신규 — 화면 경로 검사 (창 둘·서비스 강제 종료)
scripts/verify_runtime_supervision.py  신규 — 서버·컨테이너 물리 검증
```

**Structure Decision**: `054` 가 정한 위상(호스트 Architect API + 앱 소유 Compose
스택)을 그대로 둔다. **새 프로세스나 새 서비스를 만들지 않는다** — 감독 로직은
Electron main 에 두고, 화면은 기존 Vue 앱에 패널로 붙인다. 이유는 둘이다.

- 감독자가 별도 프로세스면 **감독자를 감독할 것**이 또 필요해진다.
- Electron main 은 이미 컨테이너 수명과 백엔드 자식 프로세스를 **둘 다** 쥐고 있는
  유일한 자리다(`docker-stack.ts` · `backend.ts`).

## 선행 이식 과제 (이 계획 안의 태스크)

릴리스가 안 나오면 SC-001 을 시작할 수 없다. 09-17 에 실측한 두 가지.

### P1. analyzer·catalog 브랜치를 현재 main 위로 이식

```
robo-data-catalog    feat/per-project-target-graph   main 이 23 커밋 앞
                     충돌: client/neo4j_client.py 가 main 에서 **삭제됨** → 재구현
                          main.py 내용 충돌
robo-data-analyzer   feat/per-project-target-graph   main 이 274 커밋 앞
```

**Dockerfile 부재가 이 이식으로 같이 해소된다** — 두 저장소의 Dockerfile 은 main 에만
있고, 우리 브랜치는 그 이전에서 갈라졌다. `release` 는 그 두 자리에서
`docker build <repo root>` 를 하므로 지금 구성으로는 이미지를 못 굽는다.

**기본 브랜치는 건드리지 않는다** — 원본 robo(Neo4j)가 같은 코드를 쓴다. 이식 후에도
전용 브랜치에 둔다.

### P1-B. 저장소를 Ontological 로 — **순서를 올렸다 (2026-09-17)**

원래 US6(Phase 6)에 있던 교체를 **Phase 2 직후로 승격**했다. Phase 4(US2)가 graph
위에서 판정하므로, 교체 전에 통과시키면 **Neo4j 위에서 초록을 받아 놓고 나중에 엔진을
바꾸게** 된다. Ontological 은 결함 18종 중 절반이 조용한 오답이었고 문서 대조로 미리
보인 것은 0종이다 — Neo4j 초록이 Ontological 초록을 보장하지 않는다.

**규모.** `ontological-db` 에는 개발용 이미지밖에 없다.

```
docker/Dockerfile.dev   Rust 툴체인 + cargo-pgrx. 소스를 /work 에 마운트
start.sh                컨테이너 안에서 빌드한 뒤 psql·bolt 를 손으로 띄운다
엔트리포인트            sleep infinity        ← 설치본에 그대로 못 쓴다
```

**런타임 이미지를 새로 만들어야 한다** — 다단계 빌드로 `ontological.so` 와
`ontological-bolt` 만 얇은 Postgres 16 이미지에 옮기고, 엔트리포인트가 initdb →
확장 설치 → graph 생성 → Bolt 기동까지 스스로 한다. 그 작업은 `ontological-db`
소유다(같은 조직 · PR #2 브랜치).

**되돌아갈 길을 같이 만든다**(T079) — 교체가 실패했을 때 이전 구성으로 갈 수 있어야
한다(FR-024).

### P2. 릴리스 환경에서 개발사 내부 모델 주소를 걷어낸다

```
robo-workspace/.env          OPENAI_* · LLM_* 는 09-17 에 OpenAI 로 바꿨다
                             **ROBO_LLM_* 는 아직 우리 사내 GPU 를 가리킨다**
                             (qwen38_sglang_local · 키 "frentis" · dream-flow 주소)
robo-workspace/.env.example  **git 추적 대상인데 같은 주소가 박혀 있다**
```

`release` 검사는 이걸 못 잡는다 — `required` 가 다 차 있고 placeholder 목록에도 안
걸린다. **"값이 있다"와 "맞는 값이다"는 다르다.** 모델 제공자는 현재 OpenAI, 이후
P-GPT 로 바뀐다.

## 설계 결정 — 왜 그렇게 하나

### D1. 준비 판정은 **기능 프로브**로 한다. healthcheck 는 신호 하나일 뿐이다

09-17 실측이 근거다.

```
자격증명 틀림   /healthz 200   POST /api/consulting-bpmn 502
자격증명 맞음   /healthz 200   POST /api/consulting-bpmn 200 (task 4 · gateway 1)
```

`compose up --wait` 는 양쪽 다 "준비됨"으로 보고한다. 그래서 서비스마다 **그 서비스가
실제로 하는 일의 가장 싼 부분**을 프로브로 둔다(계약: `contracts/service-capability-probes.md`).

**LLM 을 실제로 부르지 않는다.** 매 기동마다 돈이 나가고 느리다. 대신 자격증명이
살아 있는지만 확인하는 값싼 호출을 쓴다.

### D2. 상태는 **서비스 배열**이다. 단일 문자열을 확장하지 않는다

지금 `RuntimeState.status` 는 `RuntimeStatus` 하나다. 여기에 값을 더하면 조합이
폭발한다(analyzer 만 죽고 나머지는 정상인 경우를 한 문자열로 못 쓴다). 배열로 바꾸고,
**기존 단일 필드는 파생값으로 남긴다**(하위 호환).

### D3. 소유 판정은 **레이블**로 한다. 이름이나 포트가 아니라

compose 가 이미 심고 있다.

```
org.uengine.robo.release: ${ROBO_RELEASE_ID}
org.uengine.robo.component: <서비스>
```

`docker ps --filter label=...` 로 자기 것만 고른다. 남의 컨테이너는 이름이 비슷해도
안 건드린다(FR-012).

### D4. 명시적 stop 은 `down` 이 아니라 `stop` 이다

`054` 가 "컨테이너는 warm 으로 재사용, 명시적 engine stop 만 `docker compose stop`"
이라고 정했고 named volume 은 보존한다. 이 계획은 그 계약을 **뒤집지 않고 호출자를
만든다** — 지금 `stopDockerStack()` 은 **호출자가 0건**이다.

### D5. 포트는 **쓸 수 있는지 확인한 뒤** 상태 파일에 쓴다

지금 `loadPersistedState` 는 범위만 본다(1024~65535). OS 재시작 뒤 그 포트를 남이
쥐고 있으면 `compose up` 이 bind 실패로 죽고 돌아갈 길이 없다. 재확보하고 **바뀐 것을
사용자에게 알린다**(FR-016).

### D6. graph 분리는 **기동 시 막는다**. 분석 시작 시점이 아니라

analyzer 는 대상 graph 를 무조건 비운다. 분석을 누른 뒤에 막으면 이미 늦을 수 있고,
사용자는 "왜 여기까지 왔는데" 가 된다. 기동 시 설계 graph와 분석 graph 를 대조해
같으면 **분석 기능을 열지 않는다**(FR-008).

### D7. 출처는 **BpmProcess 노드에 저장**한다. 진행 스트림은 증거가 아니다

`hybrid_workflow_runner.py` 가 `phase1_source` 를 SSE 로 내보내지만 영속되지 않는다.
앱을 다시 열면 사라진다. 그리고 **폴백 결과물은 진짜와 구분되지 않는다** — 09-17 에
facade 를 죽여 놓고 native 가 task 7 · gateway 2 를 냈다. 기록이 유일한 증거다.

## Complexity Tracking

| 결정 | 왜 필요한가 | 더 단순한 대안을 버린 이유 |
|---|---|---|
| 서비스별 기능 프로브 | healthcheck 가 자격증명·의존성을 못 본다 (실측) | `compose up --wait` 만 믿으면 502 나는 서비스를 "준비됨"이라 부른다 |
| 상태를 배열로 확장 | 한 서비스만 죽은 상태를 표현해야 한다 | 단일 문자열은 조합 폭발 |
| 이식 과제를 이 계획에 포함 | 그것 없이 릴리스가 안 나오고 SC-001 을 시작 못 한다 | 별도 일감으로 빼면 "계획은 있는데 잴 수가 없다"가 된다 |

**추가하지 않은 것** — 감독자 별도 프로세스(감독자를 감독해야 한다) · 자동
업데이트(별도 스펙) · SSO(ENT-AUTH-001) · 강제 이어받기(057 의 명시적 비목표).
