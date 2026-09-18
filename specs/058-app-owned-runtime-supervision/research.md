# Phase 0 — 조사와 결정

**Feature**: 058 설치본 런타임 감독과 복구 | **Date**: 2026-09-17

이 문서의 근거는 대부분 **09-17 에 맥에서 직접 잰 것**이다. 문서 대조로 나온 것은
따로 표시했다.

## R1. healthcheck 가 준비를 대변하는가 — **아니다 (실측)**

### 어떻게 쟀나

로컬에서 이미지 8종을 굽거나 받아 `desktop/runtime/compose.yml` 그대로 띄웠다.
`compose up --wait` 가 **8/8 healthy** 를 보고했다. 그 상태에서 같은 서비스를 두 번
불렀다.

```
자격증명 틀림   GET /healthz 200   POST /api/consulting-bpmn  502 (401 Unauthorized)
자격증명 맞음   GET /healthz 200   POST /api/consulting-bpmn  200 · 12.6초 · 9.6KB
                                   task 4 · gateway 1 · lane 2
```

### 결정

**서비스마다 "기능 프로브"를 따로 둔다.** compose healthcheck 는 신호 하나로만 쓰고,
준비 판정의 근거로 삼지 않는다.

### 대안과 기각 이유

| 대안 | 기각 이유 |
|---|---|
| healthcheck 를 더 엄격하게 쓴다 | 이미지 안에 있어 우리가 못 고치는 것이 있다(pdf2bpmn 은 상류 이미지). 그리고 healthcheck 는 **컨테이너 안에서** 돈다 — 호스트에서 안 보이는 실패를 못 잡는다 |
| 첫 실제 작업으로 판정한다 | 실패를 사용자가 먼저 만난다. "준비됐다"고 해 놓고 첫 문서에서 터진다 |
| 기동 때 LLM 을 한 번 부른다 | 매 기동마다 비용·지연. 12.6초짜리 호출을 기동 경로에 둘 수 없다 |

## R2. 기능 프로브를 무엇으로 할 것인가

원칙 셋.

```
싸다        LLM 을 부르지 않는다. 3초 안에 끝난다
진짜다      그 서비스가 실제로 쓰는 의존을 지난다 (자격증명·업스트림·저장소)
부작용 없다 쓰기를 하지 않는다. 남의 데이터를 안 건드린다
```

구체 계약은 `contracts/service-capability-probes.md`. 요지는 이렇다.

| 서비스 | healthcheck 가 보는 것 | 기능 프로브가 더 보는 것 |
|---|---|---|
| neo4j/ontological | bolt 포트 | **그 graph 가 실제로 존재하는가** (`DatabaseNotFound` 는 연결 성공 뒤에 난다) |
| gateway | `/actuator/health` | 업스트림으로 실제 왕복 — **직접 호출과 같은 코드가 오는가** |
| analyzer | `/` 200 | 설정된 LLM 자격증명이 살아 있는가 (모델 목록 조회 등 값싼 호출) |
| catalog·fabric | 자기 health | graph 연결이 실제로 열리는가 |
| parser | `/` 200 | 공유 데이터 루트에 쓸 수 있는가 |
| pdf2bpmn | `/healthz` | **자격증명 유효성** — 이것이 R1 에서 갈린 자리다 |

> **`/robo/health` 같은 경로를 지어내지 않는다.** 09-17 에 그렇게 해서 500 을 보고
> 앱 결함으로 오독했다. 프로브 경로는 **그 서비스가 실제로 가진 것**만 쓴다.

## R3. 게이트웨이 라우팅 판정 기준 — 코드가 같은가

```
/api/gateway/robo/health        404   analyzer 도달 (FastAPI 형식)
/api/gateway/robo/check-data/   200   catalog 도달
/api/gateway/data-fabric/health 200   fabric 도달
/api/gateway/antlr/             500   **parser 직접 호출도 500** → 정상
```

마지막 줄이 중요하다. 500 을 실패로 읽으면 멀쩡한 라우팅을 결함으로 만든다.
`electron-runtime.md` §3.4 가 정한 **"직접 호출과 같은 코드"** 가 옳은 기준이다.

**부수 발견(잠재 결함).** 게이트웨이의 `robo-glossary-service` 가 `/robo/**` 를 잡아
컨테이너 안 `127.0.0.1:5504` 로 보낸다. `${ROBO_...}` 치환이 없어 **compose 로 못
바꾼다.** Architect 는 `/api/gateway/**` 로만 부르므로 지금은 안 탄다. 기록만 해 둔다.

## R4. 소유 식별 — 레이블로 가능한가 (문서·코드 대조)

compose 가 모든 서비스에 심고 있다.

```yaml
labels:
  org.uengine.robo.release: ${ROBO_RELEASE_ID}
  org.uengine.robo.component: <서비스>
```

`docker ps --filter "label=org.uengine.robo.release=<id>"` 로 자기 것만 고를 수 있다
(09-17 에 실제로 이 필터로 상태를 읽었다). **이름·포트로 고르지 않는다** — 사용자가
같은 이미지를 따로 띄워 둔 경우를 남의 것으로 인식해야 한다.

## R5. `restart: unless-stopped` 와 앱 수명의 관계

compose 의 모든 서비스가 `restart: unless-stopped` 다. 그래서:

- 앱을 껐다 켜면 컨테이너는 **이미 떠 있다** → 다시 띄우면 안 되고 **이어받아야** 한다.
- **OS 를 재시작해도 앱 없이 먼저 뜬다** → 그때도 자기 것으로 인지해야 한다.
- 사용자가 완전히 내리려면 **명시적 stop** 이 필요하다 — 그런데 `stopDockerStack()` 의
  호출자가 지금 **0건**이다(grep 확인).

`054` 는 이 warm 재사용을 **의도한 설계**로 정했다. 뒤집지 않고, **내리는 길**과
**다시 붙는 길**을 만든다.

## R6. 포트 재확보 — 지금 무엇이 빠져 있나 (코드 대조)

`docker-stack.ts` 의 `loadPersistedState()` 는 저장된 포트가 **정수이고 범위 안인지만**
본다. 실제로 비어 있는지는 안 본다. `createState()` 는 첫 실행에 `pickFreePort()` 로
뽑아 저장하고 그 뒤로는 그 값을 계속 쓴다.

OS 재시작 뒤 그 포트를 남이 쥐면 `compose up` 이 bind 실패 → `fatal`. 돌아갈 길 없음.

**결정**: 기동 시 각 포트의 가용성을 확인하고, 막혔으면 재확보한 뒤 상태 파일을
갱신하고 **바뀐 사실을 알린다.** 조용히 바꾸면 외부에서 붙던 도구가 깨진다.

## R7. 폴백 출처 — 어디까지 살아 있나 (실측)

facade 를 401 상태로 두고 분기 지점을 직접 불렀다(화면 경로 아님 — 미검증).

```
facade 502 → a2a "All connection attempts failed" → native
Phase1Result.source = "native"
Phase1Result.error  = 두 실패 사유가 둘 다 보존
```

**분기 지점에서는 조용하지 않다.** `hybrid_workflow_runner.py:122` 가 진행 스트림에도
`🔌 Phase 1 소스: …` 를 싣는다.

**그런데 결과물로는 못 가린다.**

```
본문 6796자 · facade 죽은 상태 → source=native · task 7 · gateway 2
task 이름: 결과 데이터 수신 및 검증 / 사전 등록 은행·간편결제사 정보 조회 / …
```

그럴듯하다. 09-16 실측도 같았다(폴백 8·2 / facade 6·2).

**결정**: `phase1_source` 와 `phase1_error` 를 **BpmProcess 노드에 저장**한다.
진행 스트림은 지나가면 사라지므로 증거가 아니다.

### 정정 — "native 는 빈 결과를 낸다"는 틀렸다

`desktop/runtime/compose.yml` 주석이 이것을 일반 사실로 단정하고 있었다. 그 실측은
**본문이 비어 있을 때의 값**이었다. 고쳤다(09-17).

여기까지 오는 데 프로브가 **세 번** 틀렸다.

```
1  content="" 를 넘겼다                                 → task 0
2  pypdf 가 없는데 try/except 가 삼켰다                  → task 0 (조용히)
3  앱이 쓰는 extract_text_from_pdf(PyMuPDF)로 교체       → task 7  ✅
```

**입력을 만들 때는 앱이 쓰는 그 함수를 쓴다.** 내가 새로 만든 추출기는 검사 대상이
아니라 검사의 결함이 된다.

## R8. 맥에서 어디까지 잴 수 있나 — 경계 (실측)

```
잴 수 있다   이미지 빌드 · compose 스택 · 라우팅 · 기능 프로브 · 폴백 분기
             (09-17 에 전부 실제로 했다)
못 잰다      Electron 창 — macOS 15.5 가 서명 안 된 Electron 31.7.7 을 실행 시점에 지운다
             개발자 도구 권한 + VS Code 재시작으로도 안 된다 (두 번 확인)
             NSIS 설치본 · 서명 · Windows 호스트 경로
```

`electron-runtime.md` §7.1 의 처방이 더 이상 안 듣는다 — 문서를 정정했다. 대화상자가
XProtect(맬웨어) 문구이고 그 처방은 Gatekeeper(미서명) 쪽인 것이 갈림길로 보이나
**증명하지 못했다.**

**결정**: 화면(US1·US3·US4 의 UI 부분)과 SC-001 은 **Windows 에서 잰다.** 맥에서는
스택·분기·계약을 잰다. 못 잰 것은 미검증으로 명시한다(FR-034).

## R9. 릴리스를 막는 것 — 남은 것 (실측)

```
서브모듈 포인터 둘     해소 (09-17 푸시 + fetch 확인)
antlr 파서             해소 (푸시 + workspace.json pin)
delivery 브랜치        해소 (893766a 푸시 확인)
Dockerfile 부재        **남음** — analyzer·catalog 우리 브랜치에 없다 (P1 이 해소)
키                     해소 (OpenAI 로 맞춤. P-GPT 전환은 이후)
Windows release 실행   **남음** — 맥에서 못 한다
```

`release` 는 각 저장소가 `workspace.json` 의 브랜치에 있는지 검사하고 아니면 던진다
(`robo.ps1:346`). 그리고 analyzer·catalog 이미지를 **서브모듈 경로에서** 굽는다
(`robo.ps1:640-641`, `Analyzer-Root`/`Catalog-Root`).

## R10. 이식 규모 (실측)

```
robo-data-catalog    main 이 23 커밋 앞
  충돌 1   client/neo4j_client.py — main 에서 **삭제됨** (modify/delete)
  충돌 2   main.py — 내용 충돌
  → 기계적 리베이스가 아니다. 새 구조 위에 재구현

robo-data-analyzer   main 이 274 커밋 앞
  → 별도 이식 작업. catalog 결과를 보고 규모를 다시 잰다
```

리베이스를 실제로 시도했고 되돌렸다. 백업 브랜치 `backup/pre-rebase-0917` 를 남겼다.

**결정**: catalog 를 먼저 이식해 **패턴을 확정**한 뒤 analyzer 로 간다. 두 저장소를
동시에 건드리면 어느 쪽 때문에 깨졌는지 못 가린다.

## 미해결

| 항목 | 왜 미해결인가 |
|---|---|
| P-GPT 연결 규격 | 고객 사내 OpenAI 호환 엔드포인트. 주소·인증 방식 미정 |
| analyzer 의 `ROBO_LLM_*` | 아직 우리 사내 GPU(qwen38_sglang_local)를 가리킨다. 고객 환경에서 무엇을 쓸지 미정 |
| `.specify/memory/constitution.md` | 자리표시자 상태. 이 스펙의 범위 아님 |
| Electron 판올림 | 31.7.7 이 macOS 15.5 에서 막힌다. Windows 회귀까지 봐야 하는 별도 일감 |
