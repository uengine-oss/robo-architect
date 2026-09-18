---

description: "Task list — 058 설치본 런타임 감독과 복구"
---

# Tasks: 설치본 런타임 감독과 복구

**Input**: Design documents from `/specs/058-app-owned-runtime-supervision/`

**Prerequisites**: [plan.md](plan.md) · [spec.md](spec.md) · [research.md](research.md) ·
[data-model.md](data-model.md) · [contracts/](contracts/) · [quickstart.md](quickstart.md)

**Tests**: 포함한다. 이 스펙의 SC-008 이 **"결함을 심어 검사가 무는 것을 본 뒤에
검증했다고 쓴다"** 를 요구한다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 병렬 가능 (다른 파일, 미완 태스크에 의존 없음)
- **[Story]**: US1~US6
- 설명 끝의 **(맥) · (윈) · (공통)** 은 **어디서 검증할 수 있는가**다
  - **(맥)** 이 장비에서 잰다 — 스택·분기·계약
  - **(윈)** Windows 에서만 잰다 — Electron 창·설치본·오프라인
  - **(공통)** 코드 작성은 어디서나, 검증은 표시된 쪽

## 이 목록을 쓰는 법 — 태스크마다 셋

작업 규칙이다. 빠뜨리면 그 태스크는 **미완**이다.

```
재현    고치기 전에 돌려서 **실패하는 것을 본다**
통과    고친 뒤 통과한다
무는가  결함을 심어 검사가 실패하는 것을 보고, 결함을 되돌린다
```

> **파괴적 결함은 심지 않는다.** 실제 데이터를 지우는 경로에는 절대.
> 검증은 `zz_` graph 에서만. 실 프로젝트를 여는 화면 검사는 **되돌리기를 먼저**
> 만들고, 되돌리기가 실패하면 검사도 실패해야 한다.

---

## Phase 1: Setup (측정 환경)

**Purpose**: 재현 가능한 측정 자리를 만든다. 09-17 에 손으로 한 것을 스크립트로.

- [X] T001 [P] 로컬 런타임 디렉터리 생성 스크립트를 `scripts/build_local_runtime.py` 에 만든다 — `desktop/runtime/compose.yml`·`pdf2bpmn/facade.py` 복사 + `release-environment.json` 스코프 규칙대로 `config/*.env` 생성. **출력은 스크래치 경로에만 쓴다**(저장소의 `desktop/runtime/config/*.env` 는 git 추적 대상이라 키가 커밋된다) (맥)
- [X] T002 [P] 이미지 준비 스크립트를 `scripts/build_local_images.sh` 에 만든다 — 5종 빌드 + 3종 pull. **`docker build | tail` 금지**(종료 코드가 tail 의 것). 각 이미지를 `docker image inspect` 로 실재 확인하고 없으면 실패로 끝낸다 (맥)
- [X] T003 [P] 프로브 실행기를 `scripts/probe_runtime.py` 에 만든다 — `contracts/service-capability-probes.md` 의 서비스별 health/capability 를 돌려 `ProbeResult` 로 출력. **`pass`·`fail`·`error`·`skipped` 네 값을 반드시 구분**한다 (맥)
- [X] T004 T003 의 `error` 갈래가 실제로 나오는지 확인한다 — 프로브가 의존하는 도구를 일부러 없애고 `fail` 이 아니라 `error` 가 나오는 것을 본다. 되돌린다. **이 구분이 없으면 나머지 측정이 전부 "0건" 병에 걸린다** (맥)

---

## Phase 2: Foundational (막고 있는 선행 과제)

**⚠️ CRITICAL**: P1 이 끝나기 전에는 **릴리스가 안 나오고 SC-001 을 시작할 수 없다.**

### P1 — analyzer·catalog 포인터를 main 으로 옮기고 **고유한 것만** 얹는다

> **2026-09-17 정정.** 원래 "main 위로 이식"이라고 적었으나, main 의 내용을 읽어 보니
> **두 저장소 모두 우리 기능을 이미 갖고 있다** — 그것도 더 넓게.
>
> ```
> catalog    우리 1커밋 → main 의 RequestGraphConnection 이 uri·user·password·검증까지
>                          한다. 라우터 7곳에 Depends 로 배선 + 단위 검사 있음
> analyzer   우리 4커밋 → 요청별 graph(set_override)는 main 에 있다. **셋은 없다**
> ```
>
> 그래서 274커밋 이식이 아니라 **포인터를 옮기고 고유한 셋만 새 구조 위로 옮기는**
> 일이다. 충돌·Dockerfile 부재·뒤처짐이 한 번에 풀린다.
>
> **되돌릴 수 있다** — 버리는 게 아니라 포인터만 옮긴다. `backup/pre-rebase-0917` 과
> 원격 `feat/per-project-target-graph` 는 그대로 둔다.

- [X] T005 두 서브모듈의 되돌릴 자리를 확인한다 — catalog `backup/pre-rebase-0917`(있음) · analyzer 도 같은 백업 브랜치를 만든다. 원격 `feat/per-project-target-graph` 는 지우지 않는다 (공통)
- [X] T006 `robo-analyzer/robo-data-catalog` 포인터를 `origin/main` 으로 옮긴다 — 우리 커밋 `5534115` 는 main 이 더 넓게 대체한다. 재구현할 것이 없다 (공통)
- [X] T007 catalog 가 **요청이 정한 graph 를 보는지** 동작으로 확인한다 — 헤더를 실은 요청과 안 실은 요청이 서로 다른 graph 를 보는지. 개수가 아니라 **심어 둔 노드의 내용**으로 판정한다 (맥)
- [X] T008 catalog 이미지가 **저장소의 Dockerfile 로** 구워지는지 확인한다 — 스크래치 `-f` 없이. `scripts/build_local_images.sh` 의 우회 경로가 안 타는 것을 본다 (맥)
- [X] T009 `robo-analyzer/robo-data-analyzer` 에 `origin/main` 기반 브랜치를 만들고 **고유한 셋만** 옮긴다 — 파일 자리가 바뀌었다(`shared/neo4j/` → `graph/`, `llm_configs/` → `llm/configs/`) (공통)
- [X] T010 [P] P-GPT 설정을 옮긴다 — `llm_configs/pgpt.yaml` → `llm/configs/pgpt.yaml`. **사용자가 말한 전환 대상이 이것이다**(현재 OpenAI → 이후 P-GPT). main 의 다른 config 와 같은 형식인지 맞춘다 (맥)
- [X] T011 [P] 프로젝트별 작업 폴더 격리를 옮긴다 — `shared/config/workspace.py` + 검사 82줄. **main 은 `ROBO_DATA_DIR` 하나만 쓰고 프로젝트별로 안 가른다**(확인함). 파서 쪽 짝(`antlr-code-parser` `3160b6c`)과 함께여야 뜻이 있다 (맥)
- [X] T080 [P] external stub 표시를 라벨에서 속성으로 옮긴다(`f308437e`) — main 에 없다. Ontological 의 타입 상속에서 라벨 과매치를 일으키는 부류다 (맥)

> **T009~T011 · T080 실측 (2026-09-17, 맥)** — 브랜치 `feat/per-project-target-graph-on-main`
>
> 옮길 후보는 넷이었는데 **둘만 옮겼다.** 나머지 둘은 main 이 이미 다르게 처리한다.
>
> ```
> 7da9eb30  대상 graph 를 요청이 정한다   →  main + 467c0c0f(09-11) 이 더 넓게 한다
> f308437e  external stub 을 속성으로     →  **main 은 stub 노드를 아예 안 만든다**
>                                            (`graph/edges/call_edges.py`: "They never
>                                            create product stub nodes") — 문제가 없다
> 55c69c1b  P-GPT 설정                   →  옮겼다 (T010)
> 1a9fe39e  프로젝트별 작업 폴더          →  옮겼다 (T011). **main 에 살아 있는 결함이다**
> ```
>
> T080 을 "없어졌다" 로 닫기 전에 **밑에 깔린 걱정을 따로 쟀다** — Ontological 의 단일
> 상속 타입에서 깨지는 다중 라벨(`(:A:B)`)과 조건부 `FOREACH` 가 main 에 남아 있는지.
> **둘 다 0건.**
>
> **T010 에서 형식이 갈렸다.** 옛 파일의 `model_small` 은 main 로더에 **없는 필드**다 —
> 넣어도 오류도 경고도 없이 **조용히 무시된다.** 그대로 옮겼으면 죽은 키가 남았다.
> `structured_output_method` 는 `provider_default` 로 뒀다(게이트웨이가 구조화 출력을
> 지원하는지는 배포마다 다르고, 안 되면 400 이 아니라 형식이 어긋난 응답이 온다).
> main 의 **실제 로더**로 읽혀지는 것과, 값이 틀리면 거부하는 것을 같이 확인했다.
>
> **T011 은 main 에 살아 있는 결함이었다.** `api/analyze_router.py` 가 요청과 무관하게
> `SETTINGS.analysis_data.dir/{source,ddl}` 만 소비한다 — 작업 폴더가 서버에 하나다.
> 대상 graph 는 갈라 놓았으니 결과는 갈리는데 **읽는 쪽이 안 갈린다.**
> 파서(`antlr-code-parser` `3160b6c`)와 **경로 모양·허용 문자가 같은지** 대조했다.
>
> 검사 `tests/config/test_workspace_isolation.py` (12건, main 의 unittest 관용구).
> **고치기 전에 라우터 배선 검사가 실패하는 것을 먼저 봤고**, 결함 넷을 심어 각각
> 무는 것을 확인했다. 원복은 diff.
>
> **main 의 자기 규칙에 한 번 걸렸다** — `tests/structure` 가 "은퇴한 번호 스펙을
> 가리키는 주석"을 막는다. pgpt.yaml 에 적은 `spec 058 T010` 이 걸렸다. 지웠고
> 기준선(실패 1 · 오류 3, 전부 `sqlglot` 미설치 등 기존 것)과 같아졌다.
>
> **안 쟀다**: `tests/api` 는 이 장비에 `sqlglot` 이 없어 못 돌린다(main 그대로도 같다).
> 그래서 라우터 배선은 **소스를 읽어서** 잰다 — 검사 파일에 그 이유를 적었다.
- [X] T081 analyzer 포인터를 새 브랜치로 옮기고 이미지가 **저장소의 Dockerfile 로** 구워지는지 확인한다 — `requirements.lock` 기반 (맥)

> **T081 실측 (2026-09-17, 맥)** — 포인터 `55c69c1b` → `92ecc929`.
>
> **저장소의 Dockerfile 로 구워진다** — 스크래치 `-f` 없이. `build_local_images.sh` 의
> 우회 경로(main 의 Dockerfile 을 빌려 오던 것)가 analyzer 에는 더 이상 필요 없다.
> 이미지 1.46GB arm64. **성공 메시지가 아니라 `docker image inspect` 로 확인했다.**
>
> **그런데 구워진 이미지가 안 떴다.** 릴리스를 막는 결함을 하나 찾았다.
>
> ```
> File "/app/shared/config/app_settings.py", line 329, in _resolve_run_output_dir
>     Path(__file__).resolve().parents[4]
> IndexError: 4
> ```
>
> `ROBO_RUN_OUTPUT_DIR` 기본값이 **개발 체크아웃의 모양**(위로 네 칸)을 가정한다.
> 컨테이너에서는 `/app/shared/config/` 라 세 칸뿐이다. `SETTINGS` 가 모듈 최상위에서
> 만들어지므로 설정 오류가 아니라 **import 실패**고, uvicorn 이 첫 줄에서 죽는다.
> **빌드는 성공한다** — CMD 를 실제로 돌려 보기 전에는 안 드러난다.
>
> 고친 뒤(`92ecc929`) 다시 구워 돌렸다: `Uvicorn running on http://0.0.0.0:5502` ·
> `GET / → 200`. **떴는지와 답하는지를 따로 쟀다.**
>
> 이식분이 이미지 안에 실제로 들어갔는지도 컨테이너 안에서 확인했다
> (`shared/config/workspace.py` · `llm/configs/pgpt.yaml` · 라우터의 `set_workspace` 2건).
- [X] T082 두 브랜치를 각 원격에 올리고 **빈 저장소에서 포인터 커밋을 받아** 확인한다. 푸시 성공 메시지로 판정하지 않는다 (공통)

> **T082 실측 (2026-09-17, 맥)**
>
> ```
> analyzer  feat/per-project-target-graph-on-main  467c0c0f..92ecc929  푸시됨
> catalog   origin/main fe71169                    올릴 것이 없다(이미 main)
> ```
>
> 빈 저장소를 만들어 `fetch --depth 1 origin <SHA>` 로 **받아서** 확인했다 —
> analyzer `92ecc929` · catalog `fe71169` 둘 다 받힌다.
>
> **한 번 헛짚었다.** 처음에 `git ls-tree HEAD` 로 포인터를 읽었는데, 그건 **커밋된**
> 트리라 아직 옛 SHA 였다. 내 변경은 인덱스에만 있었다. 그대로 두었으면 "받았다"를
> **엉뚱한 커밋에** 대고 적을 뻔했다. `git ls-files -s` 로 다시 읽었다.
> 그 과정에서 catalog 포인터가 **스테이지도 안 돼 있던 것**도 같이 드러났다.
- [X] T083 프런트가 `X-Neo4j-URI` 를 싣는지 **잰다** — main 의 `from_headers` 는 URI 가 없으면 통째로 None 을 돌려줘 **`X-Neo4j-Database` 만 보내면 조용히 무시**된다. 안 실으면 `frontend/src/app/http.js` 를 고친다 (맥)
- [X] T084 설치본 compose 의 헤더 override 를 켠다 — `desktop/runtime/compose.yml:60`·`:95` 가 지금 `"false"` 다. false 면 헤더가 오는 순간 **403**. 켜고 나서 T007 을 다시 잰다 (맥)

> **T083·T084 실측 (2026-09-17, 맥)**
>
> **프런트는 `X-Neo4j-URI` 를 안 싣는다 — 그게 맞다.** 브라우저에서 도는 화면은 연결
> 자격을 클라이언트로 내보내면 안 된다. `stores/session.ts` 가 붙이는 헤더는
> `X-Neo4j-Database` 하나뿐이다. 그러니 고칠 곳은 프런트가 아니라 **받는 쪽**이었다.
>
> analyzer 는 이미 받는다(`467c0c0f`). **catalog 와 fabric 은 안 받았다.**
>
> 설치본 스택에서 **내용으로** 쟀다 — `zz_hdr_a` 에 3건, `zz_hdr_b` 에 7건을 심고
> 헤더로 각각 물었다.
>
> ```
> 고치기 전   zz_hdr_a → 0 · zz_hdr_b → 0 · 헤더 없음 → 0      셋이 같다
>             URI 까지 실으면 403 (스위치)
> 고친 뒤     zz_hdr_a → 3 · zz_hdr_b → 7 · 헤더 없음 → 0      심은 대로다
>             system → 400
> ```
>
> **403 도 안 났었다.** `CATALOG_ALLOW_NEO4J_HEADER_OVERRIDE` 검사가
> `connection is not None` 일 때만 도는데, 실제로 오는 갈래는 늘 `None` 이었다 —
> **켜고 끄는 스위치가 있는데 실제 요청은 그 스위치를 안 지나갔다.**
>
> **짝이다.** 한쪽만 들어가면:
> ```
> 고침만 (스위치 off)   화면이 403 — 조용한 무시가 **보이는 실패**가 된다 (실측함)
> 스위치만 (옛 코드)     지금처럼 조용히 무시
> ```
> 그래서 compose 의 두 스위치를 `"true"` 로 켜고 커밋 본문에 짝을 적었다.
>
> 검사: catalog `tests/unit/test_database_only_header.py` · fabric 같은 이름. 각각
> 옛 동작을 되돌려 심어 무는 것을 확인했다. 기존 검사 실패 수는 기준선 그대로
> (catalog 17 · fabric 6 — 전부 `rapidfuzz` 미설치 등 기존 것).
>
> 포인터 셋을 **빈 저장소에서 받아** 확인했다: analyzer `92ecc929` ·
> catalog `fee0191` · fabric `a103855`.
>
> **안 쟀다**: fabric 은 단위 검사까지만. catalog 처럼 스택에 붙여 내용으로는 안 쟀다.

### P2 — 릴리스 환경에서 개발사 내부 주소를 걷어낸다

- [X] T012 [P] `robo-workspace/.env.example` 에서 `ai-server.dream-flow.com`·`frentis-ai-model` 을 걷어낸다. **이 파일은 git 추적 대상**이라 납품 자산에 우리 내부 엔드포인트가 남는다 (공통)
- [X] T013 [P] `robo-workspace/.env` 의 `ROBO_LLM_*`(analyzer 용 `qwen38_sglang_local`·키 `frentis`)을 고객 환경 기준으로 정리한다. 현재는 OpenAI, 이후 P-GPT. **무엇을 쓸지 미정이면 미정이라고 적고 넘긴다** (공통)
- [X] T014 릴리스 환경 검사에 **"값이 맞는가"** 관문을 더한다 — `robo-workspace/scripts/robo.ps1` 의 `Get-ReleaseEnvironmentConfigurationErrors` 가 지금은 비어 있는지와 placeholder 목록만 본다. 개발사 내부 도메인이 남아 있으면 실패하게 한다 — robo-workspace 소유라 브랜치+PR 로 넘긴다 (공통)
- [ ] T015 T014 가 무는지 확인한다 — 내부 도메인을 하나 넣고 `release` 가 던지는 것을 본 뒤 되돌린다 (윈)

> **T012~T014 실측 (2026-09-17, 맥)** — `robo-workspace` PR #2 로 넘겼다
> (브랜치 `fix/release-env-no-internal-endpoints`, 커밋 `1116c71`).
>
> `.env.example` 의 사내 주소 9곳 → 0곳. `.env`(추적 안 됨)도 같이 맞췄고 관문이 0건.
>
> **기존 검사가 못 잡은 이유가 둘이었다.**
> ```
> ① 관문이 "비어 있나 · placeholder 인가" 만 봤다 — 사내 주소는 **둘 다 통과**한다
> ② 검사가 사내 주소를 **기대값으로 박아** 두었다 (ROBO_LLM_CONFIG=qwen38_sglang_local,
>    LLM_API_BASE=http://ai-server.dream-flow.com...). 고객 값으로 바꾸면 검사가 실패했다
> ```
> ②가 더 나쁘다. **검사가 내부 주소를 제자리에 못 박고 있었다** — `environment-contract.ps1`
> 의 `ANALYZER_NEO4J_DATABASE -ne 'neo4j'`(T085)와 같은 부류다.
>
> 관문은 **포장되는 키만** 훑고 **값은 메시지에 안 싣는다**(걸리는 키에 자격증명이 섞인다).
> 결함 셋을 심어 각각 **다른 메시지로** 무는 것을 확인했다. 그 과정에서 값-유출 단언이
> 애초에 잴 수 없는 모양이었던 것(걸리는 키가 자격증명이 아니었다)을 찾아 fixture 를
> 고쳤다 — 심어 보지 않았으면 "확인했다"고 적을 뻔했다.
>
> 템플릿 검사는 **개수 검사보다 앞에** 뒀다. 뒤에 두면 사내 주소가 하나 늘어난 것이
> "자격증명 개수가 안 맞는다" 로 보고돼 원인을 엉뚱한 데서 찾게 된다.
>
> **안 쟀다**: 맥에서는 `Electron release input is missing: desktop\runtime\compose.yml`
> 에서 멈춘다 — 경로 구분자 때문이고 **이 변경 전에도 같았다**(stash 로 확인). 그 앞의
> 단언은 전부 통과한다. T015(Windows `release` 한 번)는 남아 있다.

### 공통 타입과 뼈대

- [ ] T016 [P] `desktop/src/shared/ipc-contract.ts` 에 `ManagedService`·`Capability`·`ProbeResult`·`GraphGuard` 를 더하고 `RuntimeState` 를 확장한다. **기존 필드는 지우지 않는다** — `status` 는 파생값으로 유지 (공통)
- [ ] T017 [P] `desktop/src/main/service-catalog.ts` 를 만든다 — 서비스 9개와 각 서비스가 막는 기능(`Capability`)의 대응표. compose 의 `org.uengine.robo.component` 값과 id 를 일치시킨다 (공통)
- [ ] T018 `desktop/src/main/supervisor.ts` 의 뼈대를 만든다 — 프로브 주기(health 5초 · capability 60초), 상태 전이(`pending→starting→ready/degraded/failed/stopped`), 변경 시에만 푸시 (공통)
- [ ] T019 `desktop/src/main/ipc.ts`·`index.ts`·`preload/index.ts` 에 `runtime:onStatus`·`runtime:retryService`·`runtime:stopEngine`·`runtime:openDiagnostics` 를 등록한다. **`app:getRuntimeState`·`app:onBackendStatus` 는 계속 동작해야 한다** — `ClaudeCodeTerminal.vue`·`workspace.api.js` 가 쓴다 (공통)
- [ ] T020 하위 호환 회귀 검사를 `desktop/tests/` 에 만든다 — 기존 두 채널의 반환 형태가 안 깨지는지. 필드를 하나 지워 검사가 무는 것을 확인한다 (공통)

---

## Phase 2-B: 저장소를 Ontological 로 (승격됨)

**⚠️ 순서를 바꿨다 (2026-09-17).** 원래 US6(Phase 6)에 있던 T046·T047 을 여기로 올린다.

**왜.** Phase 4(US2)가 graph 위에서 판정하는데, 교체 전에 통과시키면 **Neo4j 위에서
초록을 받아 놓고 나중에 엔진을 바꾸게** 된다. Ontological 은 결함 18종 중 절반이
**조용한 오답**이었고 문서 대조로 미리 보인 것은 0종이었다 — Neo4j 초록이 Ontological
초록을 보장하지 않는다.

**규모를 먼저 알린다.** `ontological-db` 에는 **개발용 이미지밖에 없다**.

```
docker/Dockerfile.dev   Rust 툴체인 + cargo-pgrx. 소스를 /work 에 마운트해 쓴다
start.sh                컨테이너 안에서 빌드한 뒤 psql·bolt 를 손으로 띄운다
엔트리포인트            sleep infinity          ← 설치본에 그대로 못 쓴다
```

**런타임 이미지를 새로 만들어야 한다.** 이 작업은 `ontological-db` 소유다(같은 조직 ·
브랜치 `fix/neo4j-bolt-compat` · PR #2).

- [X] T072 `ontological-db` 에 런타임 Dockerfile 을 만든다 — 다단계 빌드. builder 는 지금의 dev 이미지(Rust·pgrx)로 `ontological.so` 와 `ontological-bolt` 를 굽고, runtime 은 **PostgreSQL 16 만 든 얇은 이미지**에 그 둘만 옮긴다. **Rust 툴체인과 소스는 runtime 에 넣지 않는다** (맥)
- [X] T073 엔트리포인트를 만든다 — `sleep infinity` 가 아니라 initdb → Postgres 기동 → `CREATE EXTENSION ontological CASCADE` → graph 생성 → Bolt 게이트웨이 기동까지 **컨테이너가 스스로** 한다. `og-bolt-restart-after-rebuild` 부류(엔진 재설치 후 Bolt 를 안 띄워 psql 은 되는데 앱만 죽는 것)를 구조적으로 막는다 (맥)
- [X] T074 healthcheck 와 기능 프로브를 가른다 — healthcheck 는 Postgres+Bolt 가 떴는지, **기능 프로브는 설정된 graph 에서 값을 읽는지**. bolt 핸드셰이크는 성공하는데 graph 가 없으면 조회에서야 터진다(실측 사례) (맥)
- [X] T075 `desktop/runtime/compose.yml` 의 `neo4j` 서비스를 이 이미지로 바꾼다 — PGDATA 를 named volume 으로 보존하고, 루프백에만 연다. `runtime-manifest.template.json` 의 이미지 항목도 같이 바꾼다 (맥)
  - 2026-09-17: **매니페스트 쪽이 안 돼 있었다.** compose 만 바꾸고 `[X]` 로 적었다 — 템플릿은 `neo4j:5.26.0` 그대로였다. T076 에서 같이 고쳤다(schemaVersion 4).
- [X] T076 Architect 배선을 바꾼다 — `docker-stack.ts` 의 `ensureBundledConnection`·`ROBO_NEO4J_*` 가 Bolt 게이트웨이를 가리키게. **사용자 = Postgres role** 이므로 비밀번호 생성·키체인 보관 경로도 그에 맞춘다 (맥)
- [X] T077 설계 graph 와 분석 graph 를 **따로 만든다** — 엔트리포인트가 둘 다 생성하고, `backend.ts` 가 각각 다른 이름을 넘긴다. US2(T035)의 전제 (맥)

> **T076·T077 실측 (2026-09-17, 맥)**
>
> 고친 것
> ```
> docker-stack.ts   images.neo4j → graphDb+graphBolt · ports.neo4j → ports.graph
>                   manifest.graphs{user,design,analysis} 추가 + 기동 전 검증
>                   (이름 규칙 · design≠analysis) — 엔트리포인트와 **같은 식**
>                   비밀번호 키체인 id 를 graph 로 옮기고 옛 id 를 한 번 이관
>                   ROBO_ANALYZER_NEO4J_DATABASE 를 따로 내보낸다
> backend.ts        ANALYZER_NEO4J_DATABASE 를 ROBO_NEO4J_DATABASE 로 덮지 않는다
> connections.ts    validateDatabase 가 밑줄을 받는다  ← 아래 참고
> runtime-manifest.template.json   schemaVersion 4 · graphs 기본값
> ```
>
> **찾은 결함 하나.** `validateDatabase` 가 `^[a-z0-9][a-z0-9-]{0,62}$` 였다 — **밑줄을
> 거부한다.** 분석 graph 기본값이 `analyzer_run` 이므로, 이대로면 스택을 다 띄운 **뒤**
> `ensureBundledConnection` 에서 터진다. 증상이 "저장소가 안 뜬다" 가 아니라 "연결 저장
> 실패" 로 보인다. 저장소를 바꾸기 전에는 값이 늘 `neo4j` 여서 안 드러났다.
>
> 검사 `desktop/tests/unit/runtime-graph-contract.spec.ts` (7건). **결함 넷을 심어 물게
> 했다**: 옛 정규식 되돌리기 / analysis=design / composeEnvironment 에서
> `ROBO_GRAPH_ANALYSIS` 제거 / backend 가 다시 설계 graph 로 덮기 — 각각 해당 검사
> 하나만 실패했고, 제거 후 7건 통과. 원복은 diff 로 확인.
>
> **안 쟀다**: Electron 창으로 실제 기동하는 경로. 맥이 미서명 Electron 바이너리를
> 지워서 이 장비에서 못 연다. 소스 계약까지만 쟀다.
- [X] T078 `scripts/probe_runtime.py` 의 서비스 id `neo4j` 를 저장소 중립 이름으로 바꾸고, graph 존재 확인을 넣는다(T022 와 합류). **지금 이름이 엔진에 묶여 있다** (맥)

> **T078·T022 실측 (2026-09-17, 맥)**
>
> 서비스 id `neo4j` → **`graph`**. 엔진 이름이 아니라 역할 이름이다. CLI 는 `--bolt`
> 이고 `--neo4j` 는 같은 자리로 계속 받는다 — 조용히 안 먹는 인자가 되면 포트가 없어
> "bolt closed" 로 **잘못** 보인다.
>
> capability 가 이제 **설정된 graph 에 질의를 던진다**. 여섯 갈래를 실측했다:
>
> ```
> 정상                  health=pass · capability=pass  "graph 'robo' 조회됨 (노드 0)"
> 없는 graph            health=pass · capability=fail   ← T022 인수 기준. exit 1
> 비밀번호 틀림          capability=fail  (문구에 비밀번호 안 실림)
> 비밀번호 없음          capability=error  ← **fail 이 아니다.** 못 잰 것이다
> bolt 포트 닫힘         health=fail · capability=skipped
> 옛 이름 --neo4j        그대로 먹는다
> ```
>
> **같은 프로브가 Neo4j 스택에서도 돈다** (`robo-mac-measure`, graph 이름 `neo4j`).
> 엔진에 안 묶였다는 증거다. 그 과정에서 `--compare-health` 가 두 구성에서 컨테이너
> 이름이 다른 것(`graph-bolt` ↔ `neo4j`)을 못 찾는 것을 발견해 후보 목록으로 고쳤다.
> **결함을 심어 확인했다** — 후보에서 `neo4j` 를 빼면 Neo4j 스택이 "컨테이너 없음".
>
> `--compare-health` 는 **대조군이지 판정이 아니다.** 그래서 매핑이 틀려도 프로브는
> 통과한다. 의도한 것이고, 표시 문구가 그 사실을 감추지 않는다.
>
> 비밀번호는 인자가 아니라 `ROBO_NEO4J_PASSWORD` 로 받는다 — `ps` 에 안 남게.
- [X] T046 [US6] 설치본의 graph 저장소를 개발 환경과 같은 구성으로 맞춘다 — `desktop/runtime/compose.yml` 이 지금 `neo4j:5.26.0` 을 쓰고 `NEO4J_DATABASE: neo4j` 로 고정돼 있다. **`grep -rn "ontological" desktop/` 이 0건이다** (공통)
- [X] T047 [US6] 저장소 회귀 검사를 **설치본 구성에서** 돌린다 — `og-verify/` 의 스크립트. 개발 환경 통과를 설치본 통과로 치지 않는다(SC-011) (맥)

> **T046·T047 실측 (2026-09-17, 맥)**
>
> `grep -rn -i ontological desktop/` 가 이제 9건 (전에는 0건). T046 은 T075~T077 로 닫혔다.
>
> og-verify 회귀 검사 3종을 **같은 자리에서** 설치본(`robo-og-measure`, Bolt 38687)과
> 개발(`ontological-dev`, 28687) 양쪽에 돌렸다. 각 검사는 같은 이름의 `zz_` graph 를 쓴다.
>
> ```
> probe_cypher.py            실패 3 / 12   ← 양쪽 **판정 12종 전부 동일**
>                            (EXISTS{} 3종. 알려진 비호환 · og_rewrites.py 가 다룬다)
> probe_analyzer_cypher.py   통과 16 / 16  ← 양쪽 동일
> probe_rule_mapping.py      통과          ← 양쪽 **출력까지 동일**
> ```
>
> 권한 격리는 새 스크립트 `og-verify/authz/installer_isolation.py` 로 **자동 판정**한다.
> 기존 `probe_authz.py` 는 개발 환경 전용이고 사람이 표로 읽는 물건이었다.
>
> ```
> 양쪽에 3건·5건을 심고 (개수를 다르게 — 같으면 착각해도 안 드러난다)
> 심긴 것을 먼저 되읽고 (안 심겼으면 "못 쟀다")
> 자기 graph  = 심은 수 그대로 · 남의 graph = **거부** (0 건은 통과가 아니다)
> 나중에 생긴 라벨(:ZzGamma)도 안 샌다  ← 상류 결함 15 의 자리
> ```
>
> **결함 셋을 심어 물게 했다**: 남의 graph 에 권한 주기 → 실패 / A 를 빈 graph 로 두기
> → **"못 쟀다"** (실패가 아니다) / 치우기 건너뛰기 → "graph 2개 남았다". 제거 후 통과,
> 환경에 남은 `zz_` 는 0건이고 실 graph 는 `analyzer_run, robo` 그대로.
>
> **찾은 것: `DROP ROLE` 이 `og_catalog.grantee` 행을 안 지운다.** 결함 A 를 심었다가
> 치운 뒤에도 다음 실행이 실패했다 — 같은 이름의 role 을 다시 만들자 **예전 권한을
> 물려받았다.** 사용자 = role 이므로 US6 에 그대로 걸린다(T086).
>
> **안 쟀다**: `equivalence.py` 는 Neo4j 대조용이라 설치본에 안 맞는다. amd64.
- [ ] T086 [US6] **role 을 지워도 `og_catalog.grantee` 행이 남는 것을 다룬다** — 같은 이름의 role 이 다시 생기면 예전 graph 권한을 물려받는다(2026-09-17 실측). 사용자 = Postgres role 이므로 탈퇴·재가입·동명이인이 전부 여기에 걸린다. 앱이 사용자를 지울 때 `og_revoke` 를 **그 role 의 모든 graph 에** 돌리고, 지운 뒤 `grantee` 에 0행인지 되읽는다. 상류(`ontological-db`)에서 `DROP ROLE` 을 따라가게 할지도 같이 본다 (맥)
- [ ] T085 **개발 경로도 두 graph 를 가르게 한다 — `robo-workspace` 소유.** T077 로 설치본은 갈라졌는데 개발 경로는 아직 합친다: `scripts/robo.ps1` 이 `ANALYZER_NEO4J_DATABASE` 를 `ROBO_NEO4J_DATABASE` 로 덮고(57~59줄), `tests/environment-contract.ps1` 이 **둘이 같아야 통과하도록** 못 박고 있다(40줄: `ANALYZER_NEO4J_DATABASE -ne 'neo4j'` 이면 실패). `.env` 는 `ROBO_NEO4J_DATABASE=neo4j` 인데 개발 저장소는 Ontological 이다. **브랜치 + PR 로 넘긴다** (공통)
- [X] T079 **Neo4j 구성으로 되돌아갈 길을 남긴다** — 교체가 실패했을 때 이전 정상 상태로 갈 수 있어야 한다(FR-024). 되돌린 뒤 데이터가 온전한지 내용으로 확인 (맥)

> **T079 실측 (2026-09-17, 맥)** — 절차는 `desktop/runtime/rollback-to-neo4j.md`.
>
> 되돌아갈 수 있는 **구조적 근거**: 두 구성이 **볼륨이 다르다**
> (`neo4j_data`/`neo4j_logs` ↔ `graph_data`). 교체해도 Neo4j 데이터가 안 지워진다.
>
> 실측: Neo4j 스택에 `:ZzRollback` 4건을 심고 **컨테이너를 지운 뒤** 같은 볼륨으로
> 새로 띄웠다. 이름 4개가 그대로 돌아왔다 — **개수가 아니라 내용으로** 확인했다.
> 같은 라벨이 Ontological 스택에는 없었다(저장소가 갈려 있다는 증거). 심은 것은 치웠고
> 치운 것도 되읽어 확인했다.
>
> 되돌리기가 **저절로 맞아 들어가는 자리 둘**을 설계에 넣었다:
> ```
> 포트 상태     docker-state.json schemaVersion 3 ↔ 2 — 옛 코드는 못 읽고 새로 뽑는다
> 비밀번호      새 id 로 **복사**하고 옛 id 를 안 지운다. 되돌린 앱이 옛 id 를 읽는다
>               (옮기면서 지웠으면 볼륨 비밀번호와 어긋나 인증만 실패했을 것이다)
> ```
>
> **되돌아가지 않는 것**: 설계·분석 graph 분리. Neo4j Community 는 database 가
> 하나뿐이라 되돌리면 **분석이 설계를 지우는 구성으로 같이 돌아간다.** 그게 교체 전
> 상태다. 문서에 적었다.
>
> **안 쟀다**: 실제 설치본에서의 revert(Windows). 여기서는 측정 스택으로 흉내 냈다.

---

## Phase 3: US1 — 지금 무엇이 준비됐고 무엇이 안 됐는지 보인다 (P1)

**Goal**: 서비스별 준비 상태가 화면에 있고, 실패하면 영향받는 기능과 할 일이 보인다.

**Independent Test**: 서비스 하나를 일부러 못 뜨게 하고 앱을 연다. 그 서비스 이름 ·
못 쓰는 기능 · 다음에 할 일이 보이고, **나머지 기능은 계속 쓸 수 있다.**

- [X] T021 [P] [US1] 기능 프로브를 `desktop/src/main/probes/` 에 서비스별로 구현한다 — `contracts/service-capability-probes.md` 대로. **LLM 을 부르지 않는다.** 없는 경로를 지어내지 않는다 (맥)
- [X] T022 [US1] neo4j/ontological 프로브가 **graph 존재까지** 보는지 확인한다 — 존재하지 않는 graph 를 가리켜 두고, bolt 포트는 열려 있는데 capability 가 `fail` 이 되는 것을 본다 (맥)
- [X] T023 [US1] gateway 프로브를 **"직접 호출과 같은 코드"** 기준으로 구현한다 — 절대 코드로 판정하지 않는다. `/api/gateway/antlr/` 가 500 이어도 parser 직접이 500 이면 `pass` (맥)
- [X] T024 [US1] pdf2bpmn 프로브가 **자격증명 유효성**을 보는지 확인한다 — 키를 깨뜨리면 `/healthz` 는 `pass` 인데 capability 가 `fail` 이 되는 것을 본다. 되돌린다. **이것이 이 스펙 전체의 근거 실험이다** (맥)
- [X] T025 [US1] `supervisor.ts` 가 프로브 결과를 `ManagedService.state` 로 옮기게 한다 — **health 만 통과한 서비스는 `ready` 가 아니다**(`starting`). capability 실패이면서 컨테이너가 살아 있으면 `degraded` (맥)
- [X] T026 [P] [US1] `frontend/src/features/runtime-status/runtime.store.js` 를 만든다 — `runtime:onStatus` 구독. **지금 `frontend/src` 에는 이 구독이 0건이다** (공통)
- [ ] T087 [US1] **설정이 가리키는 LLM config 이 이미지에 실재하는지** 검사하는 관문을 더한다 — 2026-09-18 실측: `ROBO_LLM_CONFIG=qwen38_sglang_local` 인데 이미지에는 `qwen36_sglang_local.yaml` 뿐이었다(한 자리 차이). compose 는 healthy, `GET /` 는 200, 실패는 **첫 LLM 호출**에서 난다. 릴리스 환경 검사(`robo-workspace` PR #2 의 `forbiddenValuePatterns` 자리)가 "값이 맞는가" 는 보지만 "그 이름이 이미지에 있는가" 는 안 본다 (공통)
- [ ] T027 [P] [US1] `frontend/src/features/runtime-status/StartupGate.vue` 를 만든다 — 기동 단계를 이름과 함께 보여주고, **마지막 진전 시각**을 표시해 "오래 걸리는 중"과 "멎었다"를 구분한다. 무한 대기 금지 (윈)
- [ ] T028 [P] [US1] `frontend/src/features/runtime-status/RuntimeStatusPanel.vue` 를 만든다 — 서비스별 상태 · 앱 소유/외부 구분 · 실패 시 영향받는 기능과 복구 동작 (윈)
- [ ] T029 [US1] 준비 안 된 기능의 진입을 막는다 — `capabilities[].state !== 'available'` 이면 그 탭·버튼이 이유를 말하거나 비활성. **조용히 빈 화면을 주지 않는다** (윈)
- [ ] T030 [US1] 컨테이너 실행 환경 자체가 없는 경우를 화면에서 다룬다 — `dockerAvailable: false` 일 때 "무엇을 준비해야 하는가"와 다시 시도하는 길 (윈)
- [ ] T031 [US1] 화면 검사를 `frontend/tests/runtime-status.spec.ts` 에 만든다 — 서비스를 하나씩 죽여 **모든 경우에** 이름·기능·복구 방법이 나오는지(누락 0건, SC-002). 실 프로젝트를 열면 되돌리기를 먼저 만든다 (윈)
- [X] T032 [US1] 서버 쪽 검사를 `scripts/verify_runtime_supervision.py` 에 만든다 — 프로브 판정과 컨테이너 물리 상태가 일치하는지. **비밀정보를 출력에 남기지 않는다** (맥)

> **T021·T023·T024·T025·T026·T032 실측 (2026-09-18, 맥)**
>
> 새로 생긴 것
> ```
> desktop/src/shared/runtime-contract.ts   ManagedService·Capability·파생 규칙
> desktop/src/main/probes/{net,index}.ts   서비스별 health·capability
> desktop/src/main/supervisor.ts           프로브 → 상태 (health 만으로는 ready 아님)
> desktop/src/preload/index.ts             runtime:* 를 렌더러에 연다
> desktop/scripts/probe-runtime.mjs        **앱의 프로브를** 부르는 껍데기
> frontend/src/features/runtime-status/runtime.store.js   구독이 0건이던 자리
> scripts/verify_runtime_supervision.py    물리 ↔ 기능 모순 대조
> ```
>
> **T024 — 이 스펙 전체의 근거 실험을 앱 코드로 다시 쟀다.**
> ```
> 자격증명 깨뜨림   health = pass (200)  ·  capability = fail (401)
> 되돌림            health = pass (200)  ·  capability = pass
> ```
> `health` 는 두 경우에 똑같이 pass 였다. 되돌린 뒤 다시 pass 확인.
>
> **T023 — 같은 코드 비교가 라이브에서 성립한다**: `게이트웨이 500 == 직접 500` → pass.
>
> **뜻밖의 수확.** 라이브 스택을 재다가 이런 것이 나왔다.
> ```
> compose healthcheck   healthy
> GET /                 200
> ROBO_LLM_CONFIG       qwen38_sglang_local   ← 요구
> 이미지에 있는 것        qwen36_sglang_local   ← 있는 것   (38 ≠ 36)
> ```
> 한 자리 차이가 healthy 뒤에 숨어 있었다. 분석은 **첫 LLM 호출에서** 실패하고 그때까지
> 아무도 말해 주지 않는다. capability 프로브가 기동 시점에 잡았다.
>
> 검사: `desktop/tests/unit/runtime-supervision.spec.ts`(21) ·
> `frontend/tests/unit/runtime-store.spec.ts`(13). **결함을 각각 다섯 개 심어 정확히
> 해당 검사만 무는 것을 확인했다.**
>
> **검사 하나가 통과 이유가 틀렸던 것을 찾았다.** `loaded` 관문을 지워도 통과했다 —
> 목록이 비어 있으면 `?.state` 가 undefined 라 관문 없이도 false 가 나오기 때문이다.
> 목록이 남아 있는 상태를 만들어 관문을 실제로 재게 고쳤다.
>
> **`tsc --noEmit -p tsconfig.json` 은 아무것도 안 검사한다** — 그 파일은
> `"files": []` 인 솔루션 파일이다. 이번 회차에 그 명령으로 "통과"를 여러 번 읽었다.
> 실제 검사는 `npm run build`(= `tsc -b`)이고, 그걸 돌리자 바로 세 건이 걸렸다.
> clean 재빌드까지 통과시켰다.
>
> **판정을 두 벌로 두지 않았다.** `scripts/probe_runtime.py` 는 앱에 프로브가 없던
> 동안의 측정 도구다. 검증 스크립트는 그것 대신 **앱의 프로브**를 부른다 — 둘을
> 나란히 두면 재구현이 원본보다 옳아져 결함을 가린다.
>
> **안 쟀다**: T027~T031 은 (윈) — 실제 Electron 창이 필요하다. 맥에서는 못 연다.

---

## Phase 4: US2 — 설치본에서 분석이 설계를 지우지 않는다 (P1)

**Goal**: 설계 graph 와 분석 graph 가 분리돼 있고, 안 되면 분석을 못 열게 막는다.

**Independent Test**: `zz_` 검증 graph 에 설계 데이터를 심고 분석을 완주한 뒤,
**개수가 아니라 내용**을 되읽어 그대로인지 본다. 되돌리기 실패도 검사 실패다.

- [X] T033 [US2] `desktop/src/main/graph-guard.ts` 를 만든다 — 설계 graph 와 분석 graph 이름을 대조. **빈 graph 로 판정하지 않는다**(데이터가 없으면 지워져도 티가 안 난다) (맥)
- [X] T034 [US2] 분리가 깨졌을 때 `legacy-analysis` 기능을 **기동 시점에** 잠근다 — 분석을 누른 뒤 막으면 늦다. `desktop/src/main/supervisor.ts` 에서 `GraphGuard` 를 `RuntimeState` 로 올린다 (맥)
- [X] T035 [US2] 설치본 구성에서 두 graph 가 실제로 갈리는지 확인한다 — `backend.ts:228` 이 `ANALYZER_NEO4J_DATABASE` 를 `ROBO_NEO4J_DATABASE` 로 덮고 있다. 그 배선을 고친다 (맥)
- [X] T036 [US2] 데이터 손실 검사를 `scripts/verify_graph_isolation.py` 에 만든다 — `zz_` graph 에 설계 데이터를 심고 분석을 돌린 뒤 **내용 일치**를 확인. **파괴적 결함은 심지 않는다** — 분리 판정 조건절만 무력화해 검사가 무는 것을 본다 (맥)

> **T033~T036 실측 (2026-09-18, 맥)**
>
> ```
> desktop/src/main/graph-guard.ts        이름 판정 + Bolt 지문 → GraphGuard
> desktop/src/main/runtime-state.ts      RuntimeRegistry — 파생값을 저장하지 않는다
> desktop/src/main/index.ts              buildRuntimeState 가 services·capabilities·
>                                        graphGuard·dockerAvailable 를 싣는다
> desktop/scripts/graph-guard.mjs        **앱의 판정을** 부르는 껍데기
> scripts/verify_graph_isolation.py      내용으로 손실을 확인
> ```
>
> **"분리됐다"와 "분리를 증명했다"를 갈랐다.** `GraphGuard.evidence` 가
> `"content" | "names" | null` 이다. 빈 graph 로는 아무것도 증명 못 한다 — 갓 설치한
> 상태가 정상적으로 `"names"` 이고, 거기서 막으면 아무것도 못 한다. 그렇다고
> `separated: true` 를 "확인했다"로 읽지도 않는다.
>
> **T035 라이브 판정**(설치본 구성):
> ```
> 설계 robo · 분석 analyzer_run · 분리됨 true · 근거 names
> 이유: 두 graph 가 모두 비어 있어 내용으로는 확인하지 못했습니다
> ```
> `backend.ts` 배선은 T077 에서 이미 고쳤다(`ROBO_ANALYZER_NEO4J_DATABASE` 를 따로 낸다).
>
> ### **US2 의 전제가 바뀌었다 — main 은 범위를 잡고 지운다**
>
> `graph/product_writer.py` 의 파괴적 질의를 읽어 보니 `_owner = 'analyzer'` 로 범위가
> 잡혀 있다(`GRAPH_OWNER = "analyzer"`). 범위 없는 삭제는 그 하나뿐이다.
>
> zz_ graph 에서 **원본 질의 그대로** 재서 확인했다:
> ```
> 설계 노드(소유자 표시 없음)   4/4 살아남음
> 분석 노드(_owner=analyzer)    0/2 살아남음 (전멸)
> ```
> **즉 분석이 설계 graph 를 가리켜도 설계 노드는 살아남는다.** 예전의 "설계가 통째로
> 지워진다"와 다르다. 남는 위험은 두 가지다 — 같은 graph 를 쓰는 **다른 프로젝트의
> 분석 결과**가 전멸하고, 설계 graph 에 분석 노드가 섞인다. 가드는 그래서 여전히
> 필요하지만, 문구는 이 사실에 맞춰야 한다.
>
> ### 검사
>
> `graph-guard.spec.ts`(16) · `runtime-registry.spec.ts`(11) — 데스크톱 단위 62건 통과.
> **결함을 여섯·넷 심어 각각 해당 검사만 무는 것을 확인했다.**
>
> `verify_graph_isolation.py` 는 **짝으로** 확인했다.
> ```
> 범위 술어 무력화              → exit 1 "설계 노드까지 죽는다"
> 이름만 바꾸고 개수는 유지      → 내용 비교 exit 1 · 개수 비교는 판정에 못 이른다
> 지우는 쪽만 무동작으로        → 확인 단언 **있으면** exit 3 "실제로 지우지 않았다"
>                                 **없으면** exit 0 — **거짓 통과**
> 원본 대조 단언 제거           → 질의가 원본에서 떨어져도 계속 초록
> ```
> 마지막 줄이 이 검사의 이유다. 파괴적 동작이 **조용히 안 돌았는데** "설계가 온전하다"
> 고 말하면 아무것도 증명하지 못한 것이다.
>
> 검증 graph 는 전부 치웠고 실사용 graph 는 `analyzer_run, robo` 그대로다.
>
> **안 쟀다**: T037(화면) — (윈). 실제 분석 완주는 LLM 비용 때문에 안 돌렸고, 대신
> **파괴적 질의를 원본 그대로** 돌렸다.
- [ ] T088 `desktop` 의 eslint 가 `tests/` 를 타입 검사하지 못한다 — `tsconfig.main.json`·`tsconfig.preload.json` 이 `src/` 만 include 해서, **검사 파일마다 `Parsing error: file was not found in any of the provided project(s)` 가 하나씩 쌓인다**(기존 `settings-migrate.spec.ts`·`smoke.spec.ts`·`desktop-launcher-e2e.spec.ts` 도 같다). 검사용 tsconfig 를 더해 eslint project 에 넣는다. 이 회차에 검사 파일을 넷 더해 같은 오류가 4건 늘었다 — 코드 문제가 아니라 설정 구멍이다 (맥)
- [ ] T037 [US2] 화면에서 잠긴 것이 보이는지 확인한다 — 분석 탭이 왜 막혔는지 말하는가 (윈)

---

## Phase 5: US3 — 껐다 켜도, OS 를 재시작해도 같게 동작한다 (P1)

**Goal**: 중복 실행·남은 프로세스·묵은 포트 때문에 동작이 갈리지 않는다.

**Independent Test**: 정상 종료 · 강제 종료 · OS 재시작 각각 뒤 재실행에서
**중복 실행 0개**이고 전과 같은 데이터에 붙는다.

- [X] T038 [US3] `docker-stack.ts` 에 소유 식별을 넣는다 — `docker ps --filter "label=org.uengine.robo.release=<id>"`. **이름·포트로 고르지 않는다**(사용자가 같은 이미지를 따로 띄운 경우) (맥)
- [X] T039 [US3] 이미 떠 있는 자기 소유 서비스를 **이어받는다** — `restart: unless-stopped` 라서 앱 없이 먼저 떠 있는 것이 정상이다. 중복으로 띄우지 않는다 (맥)
- [X] T040 [US3] 포트 가용성 확인을 `loadPersistedState()` 에 넣는다 — 지금은 범위만 본다. 막혔으면 재확보하고 상태 파일을 갱신하고 **바뀐 사실을 알린다**(조용히 바꾸면 외부 도구가 깨진다) (맥)
- [X] T041 [US3] `runtime:stopEngine` 핸들러를 만든다 — **`stopDockerStack()` 의 호출자가 지금 0건이다.** `054` 계약대로 `docker compose stop` 이고 named volume 을 지우지 않는다 (맥)
- [X] T042 [US3] 데이터 보존을 **내용으로** 확인한다 — stopEngine 전에 심은 값을 다시 띄운 뒤 되읽어 같은지. 개수로 판정하지 않는다 (맥)

> **T038~T042 실측 (2026-09-18, 맥)**
>
> ```
> desktop/src/main/stack-ownership.ts   라벨로 소유를 가리고 이어받기를 계획한다
> desktop/src/main/docker-stack.ts      reclaimBlockedPorts · restartOwnedService
> desktop/src/main/index.ts             runtime:retryService · stopEngine · openDiagnostics
> scripts/verify_stop_preserves_data.py 내용으로 보존을 확인
> ```
>
> ### 이 회차에 **실제로 재부팅을 겪었다** — 그게 근거다
>
> 기계가 재부팅되어 Docker Desktop 이 꺼져 있었다. 켜자
> ```
> 9개 중 8개   restart: unless-stopped 로 **앱보다 먼저** 스스로 돌아왔다
> pdf2bpmn     exit 127 — 사라진 스크래치 경로를 바인드 마운트하고 있었다
> neo4j(mac)   `docker run` 으로 띄운 것 — 재시작 정책이 없어 안 돌아왔다
> ```
> 그래서 **"라벨이 붙은 컨테이너가 있다"와 "그게 돌고 있다"는 다른 사실**이다.
> 이어받기는 running 인 것만 대상으로 하고, 멈춘 것은 compose 가 다시 올린다.
>
> **이름·포트로 고르지 않는다.** 사용자가 같은 이미지를 손으로 띄워 둘 수 있다 —
> 라벨(`org.uengine.robo.release`)로 가린다. 목록을 **못 물어봤으면 빈 배열이 아니라
> `null`** 을 돌려주고, 그 경우 띄우지도 이어받지도 않는다. 빈 배열로 돌려주면
> "우리 것이 하나도 없다"가 되어 전부 새로 띄우고, **중복이 생기는 자리가 정확히
> 거기다.**
>
> ### 포트 (T040)
>
> `loadPersistedState` 는 **범위만** 봤다(1024~65535). 앱이 꺼져 있던 동안 남이 그 포트를
> 잡으면 `compose up` 이 `address already in use` 로 죽는데, 그 메시지는 어느 서비스의
> 어느 포트인지 말해 주지 않는다. `reclaimBlockedPorts` 가
> ```
> 우리가 쥔 포트      막혀 있어도 그대로 쓴다 (이어받는 경우 정상이다)
> 남이 쥔 포트        다시 뽑고 **무엇이 바뀌었는지 돌려준다**
> 새로 뽑은 것끼리    겹치지 않게 모아 둔다
> ```
> 조용히 바꾸면 옛 포트를 쥔 외부 도구가 "갑자기 안 된다"가 된다.
>
> ### stopEngine (T041) — **호출자가 0건이었다**
>
> 내리는 길이 코드에 있는데 화면에서 닿을 수 없었다. 이제 `runtime:stopEngine` 이
> 부른다. `stop` 이고 `down` 이 아니다 — named volume 을 지우지 않는다.
> `confirm: true` 를 요구한다(실수로 부르면 남의 화면에서 서비스가 사라진다).
>
> `restartOwnedService` 는 **스택 전체를 흔들지 않는다.** 하나가 죽었는데 전부
> 재기동하면 멀쩡한 나머지의 연결이 끊긴다. `graph` 는 컨테이너가 둘이라 둘을 같이
> 올린다 — Postgres 만 올리고 Bolt 를 빼면 **psql 은 되는데 앱만 죽는** 상태가 된다.
>
> ### 보존을 내용으로 확인했다 (T042)
>
> ```
> 심음 5건 → 8개 컨테이너 stop → 전부 멈춤 확인 → 볼륨 3개 그대로 → start
> → 되읽기 ['keep_0'..'keep_4']  **이름 목록이 같다**
> ```
>
> **거짓 통과를 짝으로 잡았다.**
> ```
> 멈추는 쪽만 무동작으로   '정말 멈췄나' 단언 **있으면** exit 3 "아직 돌고 있다"
>                          **없으면** exit 0 "내용까지 보존됐다" — **거짓 통과**
> 이름 하나만 바꾸기       내용 비교 exit 1 · 개수 비교는 판정에 못 이른다
> ```
>
> ### 검사
>
> `stack-lifecycle.spec.ts`(13) — 데스크톱 단위 **75건** 통과. **결함 일곱을 심어 각각
> 해당 검사만 무는 것을 확인했다.**
>
> **안 쟀다**: T043(강제 종료)·T044(OS 재시작에서 앱이 이어받기)·T045(단일 인스턴스)는
> (윈). 컨테이너 쪽 재부팅 거동은 위처럼 실제로 봤지만, **앱이 그것을 이어받는 경로는
> 창을 열어야 안다.**
- [ ] T043 [US3] 강제 종료 뒤 재실행을 검사한다 — `browser.close()` 는 강제 종료가 아니다. 프로세스를 실제로 `SIGKILL` 한 뒤 남은 것 때문에 기동이 막히지 않는지 (윈)
- [ ] T044 [US3] OS 재시작을 실제로 겪게 한다 — 컨테이너가 앱 없이 먼저 떠 있는 상태에서 앱을 열어 이어받는지 (윈)
- [ ] T045 [US3] 단일 인스턴스를 확인한다 — 두 번째 실행이 **조용히 사라지지 않고** 기존 창을 올린다 (윈)

---

## Phase 6: US6 — 설치본에서 로그인하고 내 프로젝트로 들어간다 (P1)

**Goal**: 설치본에서 사용자·프로젝트 관리가 성립한다(저장소를 Ontological 로 맞춘 결과).

> **저장소 교체 자체는 Phase 2-B 로 승격됐다**(2026-09-17 결정). 여기는 그 위에서
> 사용자·프로젝트가 성립하는지만 본다.

**Independent Test**: 두 사용자로 각각 로그인해 **상대 프로젝트에 심어 둔 데이터의
라벨을 세어** 안 보이는지 확인한다. 빈 목록으로 판정하지 않는다.

- [ ] T048 [US6] 권한 격리를 데이터로 판정한다 — 좁혀진 role 로 접속해 **심어 둔 라벨을 세어** 0건인지 본다. `MATCH (n)` 은 권한이 없어도 0건이라 증거가 못 된다 (맥)
- [ ] T049 [US6] 기존 구성에 남은 사용자 데이터의 이관 가능 여부를 기동 시 알린다 — 조용히 빈 화면이 되면 안 된다(FR-030) (공통)
- [ ] T050 [US6] 로그인·프로젝트 선택을 화면에서 통과시킨다 — 로그인에 필요한 서비스가 준비 안 됐으면 **무엇이 준비되지 않았는지** 보여준다 (윈)

---

## Phase 7: US4 — 고장 나도 작업을 잃지 않고 돌아온다 (P2)

**Goal**: 실패를 유한 시간에 말하고, 되살리기를 시도하고, 복구 후 중복 반영이 없다.

**Independent Test**: 작업 도중 서비스를 강제로 내린다. 화면이 한계 시간 안에
실패를 말하고, 복구 후 중복 0건·소실 0건.

- [ ] T051 [US4] 비정상 종료 감지를 `supervisor.ts` 에 넣는다 — 컨테이너 exit 과 백엔드 crash 둘 다. `backend.ts` 는 지금 `backend-crashed` 를 쏘지만 **듣는 쪽이 없다** (맥)
- [ ] T052 [US4] 되살리기와 포기 조건을 만든다 — 백오프, 시도 한계, 한계 도달 시 `stopped` 로 두고 사람에게 넘긴다. `runtime:retryService` 는 그 뒤에도 열려 있다 (맥)
- [ ] T053 [US4] 재기동 여부를 **포트로 재지 않는다** — uvicorn `--reload` 의 reloader 가 소켓을 쥐고 있어 끊기지 않는다. 일꾼 pid 로 잰다 (맥)
- [ ] T054 [US4] 긴 작업의 실패를 화면에 이름으로 낸다 — 인제스천·분석 도중 서비스가 죽었을 때 **성공처럼 멈추지 않는다** (윈)
- [ ] T055 [US4] 빈 결과를 네 갈래로 가른다 — 정상적인 데이터 부재 / 처리 실패 / 조회 실패 / **프로브가 못 돔**. 화면과 기록 양쪽에서 (공통)
- [ ] T056 [US4] 복구 후 중복 반영이 없는지 확인한다 — 같은 작업을 이어서 진행하고 **내용으로** 대조 (맥)
- [ ] T057 [US4] 컨테이너 실행 환경을 작업 도중에 내려 본다 — 진행 중 작업의 실패와 영향받는 기능이 화면에 나오는지 (윈)

---

## Phase 8: US5 — BPMN 을 누가 냈는지 나중에도 안다 (P2)

**Goal**: 출처가 결과에 남고 앱을 다시 열어도 보인다.

**Independent Test**: 내부 서비스를 내린 상태와 띄운 상태로 같은 문서를 넣어
출처가 갈리는지 본다. **판정은 결과물 품질이 아니라 처리 서비스가 받은 요청 수**다.

- [ ] T058 [US5] `api/features/ingestion/hybrid/hybrid_workflow_runner.py` 가 `phase1_source`·`phase1_error` 를 영속 경로로 넘기게 한다 — 지금은 SSE 와 로그에만 있다 (맥)
- [ ] T059 [US5] `api/features/ingestion/hybrid/event_storming_bridge/persistence.py` 에서 `BpmProcess` 에 `generatedBy`·`generationFallbackReason`·`generatedAt` 을 저장한다. **신규 라벨·관계 없음** (맥)
- [ ] T060 [US5] 옛 노드의 **없음과 `native` 를 구분**한다 — `generatedBy` 가 비어 있는 것은 "폴백이었다"가 아니라 "모른다"다 (맥)
- [ ] T061 [US5] 대체 경로 결과가 **성공처럼 보이지 않게** 화면을 고친다 — 어느 경로가 냈는지와 사유가 드러난다 (윈)
- [ ] T062 [US5] 대체 경로를 끄는 설정을 만든다 — 켜지 않으면 내부 서비스 실패가 **실패로 끝난다**(FR-027) (맥)
- [ ] T063 [US5] 출처 검사를 `frontend/tests/bpmn-provenance.spec.ts` 에 만든다 — facade 를 죽인 상태와 띄운 상태로 각각 넣고, **컨테이너가 받은 요청 수**로 판정한다. 결과물 task 수로 판정하지 않는다(폴백도 그럴듯한 BPM 을 낸다) (윈)
- [ ] T064 [US5] 앱을 다시 열어도 출처가 보이는지 확인한다 — 진행 스트림이 아니라 그래프에서 읽는지 (윈)

---

## Phase 9: Polish & 인수

- [ ] T065 [P] 버전 조합을 확인할 수 있게 한다 — 앱 버전과 각 서비스 이미지 태그를 화면과 진단 기록에서(FR-022) (공통)
- [ ] T066 [P] 업그레이드 실패 시 되돌아갈 길을 만든다 — 데이터 호환성 확인 후 이전 정상 상태로(FR-024) (윈)
- [ ] T067 비밀정보가 어디에도 안 남는지 훑는다 — `stateReason`·`detail`·로그·진단. **길이나 지문으로도 남기지 않는다**(FR-011) (공통)
- [ ] T068 Windows 에서 `release` 를 끝까지 돌린다 — 이미지 tar·`facade.py`·`config/*.env` 가 실제로 나오는지. **다음 벽이 더 있을 수 있다** (윈)
- [ ] T069 배포 대상 환경에 설치본을 설치하고 **외부 인터넷을 차단한 상태로** 실행한다(SC-001) (윈)
- [ ] T070 사람이 밟는 전 구간을 통과시킨다 — 로그인 → 프로젝트 선택 → 문서 업로드 → 내부 서비스 BPMN 생성 → 레거시 분석·탐색 → 입력을 참조한 이벤트 스토밍. **그린필드(레거시 없음)도 통과해야 한다** (윈)
- [ ] T071 설치 전제조건과 **못 잰 것**을 문서에 남긴다 — `STATUS.md`·`enterprise-todo.md`·`enterprise-done-v2.md` 를 같은 회차에. "안 된다"와 "모른다"를 가른다(SC-009) (공통)

---

## Dependencies

```
Phase 1 (T001~T004)          측정 자리. 다른 모든 것의 전제
Phase 2 P1 (T005~T011)       **릴리스를 막는다.** T068·T069 의 전제
Phase 2 P2 (T012~T015)       납품 자산 정리. T068 전에
Phase 2 공통 (T016~T020)     US1~US6 전부의 전제
Phase 2-B (T072~T079)        **저장소 교체.** US2·US6 의 전제. Phase 3 앞에 온다
                             (2026-09-17 승격 — Neo4j 위에서 US2 를 통과시키면 다시 재야 한다)

US1 (Phase 3)   → US4(Phase 7) 이 보여줄 화면을 만든다. **US4 보다 먼저**
US2 (Phase 4)   독립
US3 (Phase 5)   T016~T019 에만 의존
US6 (Phase 6)   T046 이 저장소 구성을 바꾸므로 US2 와 순서를 맞춘다
US5 (Phase 8)   독립 (백엔드 쪽)
```

**스토리 사이 독립성**: US2 · US3 · US5 는 서로 독립이다. US1 은 US4 의 선행이다
(고장을 보여줄 화면이 없으면 US4 를 검증할 수 없다).

## 병렬 기회

```
Phase 1    T001 · T002 · T003 동시
Phase 2    T012 · T013 (env 정리) ↔ T016 · T017 (타입·카탈로그) 동시
           **T006(catalog)과 T009(analyzer)는 동시에 하지 않는다** — 어느 쪽 때문에
           깨졌는지 못 가린다
Phase 3    T021(프로브) · T026(store) · T027 · T028(화면) 동시
Phase 8    T058~T060(백엔드) ↔ T061(화면) 동시
```

## MVP 범위

**Phase 1 + Phase 2 + Phase 3(US1)** 이 최소 인도 단위다.

그 이유: US1 이 없으면 나머지 모든 고장이 "앱이 안 켜진다" 한 문장으로 합쳐지고,
US2~US6 의 실패를 **보여줄 자리가 없다.** 그리고 Phase 2 없이는 릴리스 자체가
안 나온다.

**MVP 로 잴 수 있는 것**: 서비스 하나를 죽여 그 서비스 이름·못 쓰는 기능·복구 방법이
보이고 나머지는 계속 쓸 수 있다(SC-002).

## 잴 수 없는 것 — 미검증으로 남긴다

```
맥에서 Electron 창    macOS 15.5 가 미서명 Electron 31.7.7 을 실행 시 지운다
                      개발자 도구 권한 + VS Code 재시작으로도 안 됨 (두 번 확인)
mac dmg               서명·notarize 미구현 (US1/T029). 이 스펙의 비목표
P-GPT 연결            규격 미정
```

**(윈) 표시 태스크는 Windows 장비가 있어야 닫힌다.** 그 전까지는 "안 된다"가 아니라
**"모른다"** 로 적는다.
