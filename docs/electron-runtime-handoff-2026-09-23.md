# Robo Architect Electron 실행·서비스 인수인계 (2026-09-23)

이 문서는 **현재 저장소와 로컬 산출물에서 확인한 상태**를 기록한다. 과거 대화에서 재현한 증상은 별도로 표시한다. 소스 체크아웃, 서브모듈 pin, 릴리스 manifest, 실행 중 프로세스는 서로 다른 상태이므로 하나를 확인했다고 나머지도 최신이라고 간주하면 안 된다.

> **개정 2026-09-23 (2차)** — 스택을 깨끗이 비우고 hr-sample 을 처음부터 다시 돌려 전 구간을 실측했다. 그 결과 **와이어프레임 렌더러(open-pencil)가 배포 구성에서 통째로 빠져 있었다**는 것이 드러났고, 그것을 Electron 이 소유하는 Docker 스택에 정식 편입했다. 컨테이너가 8개에서 **9개**가 됐다. §1·§1-A·§4·§5·§6 을 고쳤다. 초판에 있던 "`buildApprovalLine` 룰 0건" 은 **집계 오류였다**(§4 에 정정).

## 1. 전체 구조

```text
Robo-Architect.exe (Electron)
  ├─ Vue Architect 화면 + Module Federation Analyzer 화면
  ├─ Windows 호스트의 Architect FastAPI (번들 Python, 127.0.0.1:<동적 포트>)
  │    ├─ 사용자·프로젝트: Ontological PostgreSQL 직접 연결 (OG_PG_*)
  │    ├─ 설계 그래프: Bolt 게이트웨이 (NEO4J_*)
  │    └─ Gateway / Analyzer MCP / pdf2bpmn 호출
  └─ Docker Compose: 9개 컨테이너 (앱이 소유)
       graph-db (Ontological PostgreSQL) → graph-bolt (Neo4j Bolt 호환)
       mindsdb, fabric, catalog, analyzer, parser, gateway, pdf2bpmn,
       wireframe (open-pencil 렌더러)          ← 2026-09-23 추가
```

058 이 세던 "서비스 9개(컨테이너 8 + 호스트 백엔드)"는 이제 **10개(컨테이너 9 + 호스트 백엔드)**다.

Electron이 Compose를 시작하고 포트를 선택해 `%APPDATA%\robo-architect-desktop\runtime\docker-state.json`에 저장한다. 그래프 PostgreSQL·Bolt, Analyzer, Gateway, pdf2bpmn, wireframe의 호스트 포트는 `127.0.0.1`에만 게시된다. **호스트 포트가 필요한 이유는 Architect API 가 컨테이너가 아니라 Windows 호스트에서 돌기 때문이다** — 컨테이너끼리만 쓰는 catalog·fabric·parser·mindsdb 는 호스트에 열지 않는다. 컨테이너 간에는 Compose 서비스명으로 통신한다. Architect API는 컨테이너가 아니라 Windows 호스트에서 실행되어 로컬 파일·프로젝트 경로를 사용할 수 있다. 일반 창 종료 시 Compose는 따뜻한 상태로 남을 수 있으므로, 창을 닫았다는 사실만으로 서비스 종료나 볼륨 삭제를 추론하지 않는다.

그래프 저장소는 기존 Neo4j Community가 아니라 **Ontological PostgreSQL + Bolt 호환 게이트웨이**다. `NEO4J_*` 변수명은 클라이언트 프로토콜의 흔적이다. 기본 설계 그래프는 `robo`, 기본 분석 그래프는 `analyzer_run`이며, 프로젝트별 분석은 요청의 `X-Project-Graph`/`X-Neo4j-Database`가 가리키는 별도 그래프로 분리해야 한다. 설계와 분석 graph를 같은 값으로 설정하거나 분석 대상 헤더가 누락되면 다른 프로젝트 결과가 섞이거나 초기화 대상이 잘못될 위험이 있다.

## 1-A. 서비스 하나가 더 늘었다 — 와이어프레임 렌더러

### 무엇인가

`open-pencil/packages/cli/src/wireframe-service.ts` 의 Bun HTTP 서버다. 컴포넌트 라이브러리(`.fig`)를 읽어 두고 세 경로를 연다.

```text
GET  /health      {"status":"ok","components":7}   카탈로그를 읽은 뒤에만 ok
POST /render      JSX + 컴포넌트 인스턴스 → SerializedSceneGraph
GET  /components  카탈로그 (LLM 프롬프트 주입용)
```

**LLM 은 이 컨테이너에서 돌지 않는다.** 모델 호출은 호스트 Architect 백엔드의 와이어프레임 에이전트가 하고(`bind_tools`: render·calc), 이 서비스는 에이전트가 만든 JSX 를 받아 좌표·레이아웃을 계산해 돌려줄 뿐이다. 그래서 이 컨테이너에는 모델 키가 필요 없다. 실측 렌더 1회 10ms 대.

호출 사슬은 이렇다.

```text
ES 승격 파이프라인
  └─ generating_ui 단계 (ui_generation_mode = html | figma | figma-with-components)
       └─ wireframe_agent.run_render_agent()        호스트 · LLM
            ├─ open_pencil_client.is_available_async()   ← GET /health
            └─ open_pencil_client.render_wireframe_async() ← POST /render
                 └─ UI 노드의 sceneGraph 로 영속
                      └─ figma_binding 이 그 sceneGraph 를 Figma 프레임으로 push
```

### 왜 빠져 있어도 아무도 못 알아챘나

`dev.sh` 는 이 서비스를 Bun 으로 띄운다(`# 2. wireframe  open-pencil (Bun)  http://localhost:7610`). 그런데 **설치본은 안 띄웠다** — compose 에도 없고 Electron 이 spawn 하지도 않았다. `WIREFRAME_SERVICE_URL` 의 기본값 `http://localhost:7610` 은 개발 실행에서만 맞는 주소다.

문제는 그 부재가 **오류로 나타나지 않는다**는 것이다. `run_render_agent` 의 첫 줄이 이렇다.

```python
if not await open_pencil_client.is_available_async():
    if on_event:
        on_event("error", {"message": "Wireframe service (open-pencil)가 실행 중이 아닙니다."})
    return None, None
```

오류 메시지는 `on_event` 이 있을 때만 나간다. 그리고 같은 파일의 주석이 못 박고 있다 — *"the ingestion path passes None"*. 즉 **인제스천 경로에서는 실패가 어디에도 기록되지 않는다.** 화면에는 "UI 와이어프레임 생성 중…" 과 "UI 생성: <이름>" 이 그대로 흐르고, UI 노드만 `sceneGraph=null` 로 남는다.

증상은 한참 뒤 **Figma 에서** 나온다. 싱크가 UI 마다 `"이 UI 노드에는 아직 sceneGraph가 없습니다."` 로 죽는다. **원인과 증상이 파이프라인 양 끝에 떨어져 있다.**

그 실패 목록을 보려고 History 탭을 열면 이번에는 앱이 통째로 멈춘다 — §4 의 `/failures` 항목을 보라.

### 실측 (2026-09-23, 같은 입력 · 렌더러만 추가)

| | 렌더러 없음 | 렌더러 있음 |
|---|---|---|
| UI 노드 | 29 | 29 |
| `sceneGraph` 보유 | **0** | **29** |
| Figma 프레임 | **0** | **28** |

렌더러를 띄운 뒤 28장을 순차 생성하는 데 154초(1장 평균 5.5초), 실패 0건이었다. 남은 Figma 1건은 렌더러와 무관하다 — `실 사용일수 산정 결과` 가 *"어떤 스토리보드(entry command)에도 도달할 수 없는 UI"* 로 거부됐다(그래프 도달성 문제).

### 어떻게 편입했나

| 저장소 | 파일 | 내용 |
|---|---|---|
| open-pencil | `Dockerfile` | `oven/bun:1.4-slim`(로컬 dev 1.4.2 와 같은 계열), `bun install --production`(1127→654 패키지, 1.42GB→1GB), `docs/components.fig` 동봉 |
| open-pencil | `.dockerignore` | `node_modules` 제외(호스트 네이티브 의존성 혼입 방지), `tests` 제외(LFS 포인터 회피) |
| robo-architect | `desktop/runtime/compose.yml` | `wireframe` 서비스. 루프백 게시 `127.0.0.1:${ROBO_WIREFRAME_PORT}:7610` |
| robo-architect | `desktop/runtime/runtime-manifest.template.json` | `images`·`imageIds` 에 `wireframe` 키 |
| robo-architect | `desktop/src/main/docker-stack.ts` | 포트 할당 · `ROBO_IMAGE_WIREFRAME`·`ROBO_WIREFRAME_PORT` · `process.env.WIREFRAME_SERVICE_URL` 주입 · `STATE_SCHEMA_VERSION` 4→5 |
| robo-architect | `desktop/src/main/probes/index.ts` | health + **기능 프로브** |
| robo-architect | `desktop/src/shared/runtime-contract.ts`, `main/runtime-state.ts` | `ManagedServiceId` 에 `wireframe`, 표시명 "와이어프레임 렌더러" |
| robo-workspace | `scripts/robo.ps1` | `$images.wireframe` + `Build-ReleaseImage 'wireframe' … $sources.openPencil` |
| robo-workspace | `workspace.json` | 개발 프로필용 `wireframe` 서비스(Bun, PATH 해석) |

주의한 지점 셋.

- **`STATE_SCHEMA_VERSION` 을 올려야 한다.** 포트가 하나 늘었으므로 옛 `docker-state.json` 을 그대로 읽으면 `ports.wireframe` 이 `undefined` 가 되고, compose 는 빈 `ROBO_WIREFRAME_PORT` 로 포트 매핑을 만들려다 죽는다. 같은 일이 pdf2bpmn 을 더할 때도 있었다(주석에 남아 있다).
- **manifest 템플릿을 먼저 맞춰야 한다.** `robo.ps1` 이 `Assert-ManifestTemplateCovers` 로 `images`·`imageIds` 를 검사하는데, 그 검사는 이미지를 다 구운 뒤가 아니라 앞에 있다 — 그래도 키를 빠뜨리면 릴리스가 중간에 선다. 주석이 *"한 줄 불일치의 대가가 빌드 한 판(1~2시간)"* 이라고 적어둔 자리다.
- **`oven/bun:1.4-slim` 에는 `curl`·`wget`·`nc` 가 하나도 없다**(실측). 도구를 더해 이미지를 키우는 대신 `bun -e` 로 `/health` 를 재고, `status:ok` 인지까지 본다.

### 기능 프로브를 왜 따로 두나

058 의 근거가 여기서도 그대로 성립한다 — **healthcheck 는 준비의 근거가 아니다.** 이 서비스가 "떠 있는데 못 하는" 상태면 와이어프레임 단계가 또 조용히 빈다. 그래서 프로브는 `/health` 200 만 보지 않고 **실제로 한 장 그려서** 노드가 0이 아닌지 확인한다. LLM 을 안 타므로 값싸다.

```text
health      GET  /health   도달 여부
capability  POST /render   3줄짜리 JSX → 노드 수 > 0 이어야 pass
```

"답은 했는데 빈 sceneGraph" 를 pass 로 부르지 않는 것이 요점이다.

## 2. 소스, pin, 릴리스 이미지 — 세 층을 구별

| 구성 | 현재 독립 저장소/브랜치 | Architect 서브모듈 pin | `dist-figma-pair` manifest의 빌드 소스 |
|---|---|---|---|
| Architect | `enterprise-custom-p` `e4b4567` | 본체 | `ebdb75a6` |
| Analyzer | `main` `3039549b` | `d9f863fc` | `d9f863fc` |
| Analyzer frontend | `main` `df07759` | `f40e376` (`feat/per-project-target-graph-on-main`) | `9c17d4fb` |
| Catalog | `main` `cf41148` | `fee0191` | `fee0191` |
| Fabric | `main` `cf8079c` | `585e23f` (`feat/database-only-header`) | `585e23f` |
| Parser | `feat/per-project-workspace` `3160b6c` | 해당 없음 | `3160b6c` |
| Gateway | `main` `abcf0ab` | 해당 없음 | `abcf0ab` |
| Ontological DB | `fix/neo4j-bolt-compat` `d270ddc` | 해당 없음 | `d270ddc` |

**표의 두 열을 "구/신" 으로 읽으면 안 된다.** 2026-09-23 실측으로 analyzer pin `d9f863fc` 는 `origin/main` 보다 **11커밋 앞서고 1커밋 뒤처져** 있다 — 서로 다른 갈래이지 오래된 것이 아니다. 앞선 11커밋은 DB 관련만이 아니라 분석 경로 한복판이다(46파일 +1,193/−166): `java_call_adapter.py` +177, `import_binding.py` 신규, `product_writer.py` 172줄, `regex_table_linker.py`, `search/ranking/*` 4파일. 커밋 제목도 `bind Java imports and receiver calls`·`preserve initializer call evidence`·`recover verified SQL lineage from JDBC sources` 로 **Java + JDBC 를 겨냥한 수정**이다(hr-sample 이 정확히 그 모양이다). catalog·fabric·frontend 도 같은 양상이다.

LLM 구성은 개발 실행과 설치본이 **동일**하다(`ROBO_LLM_CONFIG=gpt54_mini_openai`, OpenAI 임베딩, `ROBO_PIPELINE_EMBED_ENABLED=true`, `ROBO_SEARCH_DENSE_IMPL=index`). 그러므로 개발 실행과 설치본의 분석 품질 차이를 모델 탓으로 돌릴 수 없다. 차이가 난다면 볼 곳은 **Bolt 게이트웨이의 Cypher 방언 격차**다 — 실측으로 `size()` 가 `jsonb_array_length(boolean)` 오류로 죽었고, 라벨 대소문자 불일치는 `NOTICE: label 'RULE' does not exist … matching nothing` 으로 **에러 없이 0건**이 됐다. 조용히 줄어드는 쪽이라 결과만 보고는 못 가린다.

곁가지로, `config/analyzer.env` 의 `ROBO_LLM_MODEL_RUNTIME_CAPABILITIES_REF` 가 `llm/capabilities/qwen38_sglang_2026_09_01.yaml` 을 가리킨다 — 실제 쓰는 모델(`gpt54_mini_openai`)과 다른 개발사 내부 프로파일이다. 동작을 바꾸지는 않지만(형식 검증만 한다) `release-environment.json` 이 `qwen38_sglang_local` 을 금지 패턴으로 잡아둔 것과 같은 계열이 빠져나간 흔적이다.

표의 SHA는 작성 시점의 로컬 체크아웃이다. 중첩 서브모듈의 `HEAD`는 분리(detached) 상태일 수 있으며, **그 자체가 오류는 아니다**. 독립 저장소의 `main`이 더 앞서도 Architect 프로필은 자동으로 따라가지 않는다. `git pull`만으로 서브모듈 gitlink·Docker 이미지·`app.asar`·번들 Python이 갱신되지 않는다. 상위 저장소가 의도한 서브모듈 commit을 가리키도록 갱신·커밋하고, release를 다시 만들어야 한다.

### 다른 브랜치가 영향을 주는 범위

| 대상 | Architect 개발 실행·다음 release가 읽는 기준 | 다른 브랜치의 변경이 반영되는 조건 |
|---|---|---|
| Analyzer·Catalog·Fabric·Analyzer frontend·open-pencil | `robo-architect` 부모 커밋이 기록한 **중첩 서브모듈 SHA** | 필요한 커밋으로 서브모듈 gitlink를 갱신하고 Architect에 커밋·푸시한 뒤 다시 빌드해야 한다. 형제 독립 저장소의 `main`을 푸시하는 것만으로는 반영되지 않는다. |
| Architect 본체·Parser·Gateway·Ontological DB | `robo-workspace/workspace.json`의 지정 URL·브랜치에서 release 준비 시 `pull --ff-only`한 HEAD | 변경을 지정 브랜치에 반영하거나 Workspace의 브랜치 pin을 의도적으로 변경하고 새 release를 만들어야 한다. 임의의 다른 브랜치는 읽지 않는다. |
| Workspace 실행기·환경 계약 | release를 수행하는 `robo-workspace` 체크아웃 | Workspace 변경도 커밋된 실행기·설정 상태로 release해야 한다. |
| 이미 생성된 `win-unpacked`/설치본 | 해당 산출물의 `runtime-manifest.json` source SHA·이미지 ID와 실제 `app.asar`·프런트 번들 | 이후 어느 브랜치에 푸시해도 자동 갱신되지 않는다. 새 산출물을 빌드하고 정확한 실행 파일 경로를 확인해야 한다. |

즉 **다른 브랜치가 무조건 무관한 것은 아니다.** 다음 release의 최상위 저장소에는 Workspace의 지정 브랜치가 중요하고, Analyzer 계열에는 Architect의 서브모듈 SHA가 중요하다. release는 소스 저장소가 깨끗한지, 지정 브랜치인지, 서브모듈이 부모가 기록한 커밋에 있는지를 검사한다. `robo.cmd sync architect-electron` 또는 release 준비로 브랜치·서브모듈을 동기화한 뒤 manifest의 `source`를 대조한다.

현재 `dist-figma-pair/win-unpacked/resources/runtime/runtime-manifest.json`은 release `0.1.0-w6046d7f3-aebdb75a6`와 이미지 태그·image ID·source SHA를 고정한다. 이 manifest의 Architect SHA와 frontend SHA는 현재 체크아웃보다 오래되었다. 따라서 이 실행 파일로 새 소스를 검증했다고 주장하려면 **실제 로드된 `app.asar`, frontend, runtime manifest, 이미지 ID를 각각** 확인해야 한다. 임의의 개발용 unpacked 디렉터리를 재사용하면 소스와 번들이 섞일 수 있다. `desktop/resources/runtime/runtime-manifest.json`도 같은 오래된 릴리스 값을 담고 있다. `robo-workspace`는 `project/` 안이 아닌 `C:\Users\YSW\Desktop\robo-workspace`에 있으며, 이 문서의 pin 표에는 그 저장소의 release 설정·HEAD는 포함하지 않았다.

## 3. 기동과 인증

패키지 경로는 Compose 기동·헬스 확인 → Windows 백엔드 spawn → `/api/health` 준비 확인 → SPA 표시 순서다. 백엔드 준비 타임아웃은 현재 소스에서 **5분**이고, 느리면 중간에 경고를 남긴다. 백엔드는 `127.0.0.1`에 바인딩한다. `docker-state.json`의 포트를 임의로 가정하지 말고 읽어서 확인한다.

백엔드 spawn 환경에는 `OG_PG_HOST/PORT/DATABASE/USER/PASSWORD`가 전달된다. 비밀번호는 앱이 DPAPI 저장 값에서 읽어 프로세스 환경으로 넘기며 설치 파일의 `.env`에 기록하지 않는다. 패키지 기본값은 `AUTH_BIND_CONNECTION=true`다. 이 연결 바인딩이 꺼지면 프로젝트 헤더가 권한 경계로 작동하지 않아 데이터 혼합 위험이 있다. Catalog·Fabric의 프로젝트별 `X-Neo4j-Database` override 허용 설정도 함께 맞아야 한다.

로그인 화면은 프런트의 로그인 게이트와 백엔드 `AUTH_ENFORCE`/`AUTH_PROVIDER` 설정이 함께 결정한다. `AUTH_PROVIDER=none`은 SSO 미사용이지 인증 강제 해제를 뜻하지 않는다. 개발용 `test/test`는 `AUTH_DEV_LOGIN_ENABLED`가 켜진 경우의 기본 계정값일 뿐, 모든 패키지에서 항상 사용 가능한 계정이 아니다. 개발 로그인의 원격 허용은 별도 설정이며 기본적으로 루프백 전용이다. `/api/auth/provider`는 비밀값을 노출하지 않고 `provider`, `enforce`, `devLogin`, `bindConnection`, JWT 설정 여부 등을 진단한다. 단, `/api/auth/me`가 인증 없이 열려 있어도 다른 API는 Bearer 토큰이 필요할 수 있다.

**로그인 화면·프로젝트 선택이 사라질 때 점검 순서:**

1. 실행한 `.exe`의 정확한 경로와 그 폴더의 `runtime-manifest.json` release/source SHA를 기록한다. 이전 `win-unpacked`나 다른 `dist-*`를 실행하지 않았는지 확인한다.
2. `/api/auth/provider`에서 `enforce`, `provider`, `devLogin`, `bindConnection`을 확인한다. 로그인 화면이 없는 현상을 무조건 pin 문제로 단정하지 않는다.
3. 백엔드가 실제로 준비됐는지 `/api/health`와 Electron 로그를 확인한다. 401은 인증, 403은 승인·프로젝트 권한·scope 문제로 구분한다.
4. 프로젝트 선택 후 요청의 `X-Project-Graph`와 서비스로 전달되는 `X-Neo4j-Database`를 확인한다. 프로젝트 없는 과거 데이터의 카운트와 현재 프로젝트 데이터는 따로 검증한다.
5. 수정 소스가 필요하면 서브모듈 pin → release 이미지·frontend·`app.asar` 재빌드 → 새 unpacked 경로 실행 순서로 반영한다. 검사 대상 `.env`를 설치 후 직접 수정하지 않는다.

## 4. 분석·프로세스 흐름과 현재 확인된 문제

소스 업로드 → ANTLR 파싱 → Analyzer 코드/룰 그래프 → Catalog 조회·Navigator 표시 → 문서 BPM/프로세스 생성 → Rule 탐색·매핑 → Event Storming 승격 순서다. Parser와 Analyzer는 공유 `/data` 볼륨을 사용한다. 따라서 “소스가 없습니다: `/data/source`”는 화면 업로드 성공 여부뿐 아니라 **같은 프로젝트·작업 공간의 볼륨 경로**와 parser/analyzer의 실행 이미지·환경을 함께 봐야 한다. 분석 완료 시간이 비정상적으로 짧거나 Navigator 계층이 누락되면 완료 메시지만 믿지 말고 파싱 파일 수, Analyzer 실행 로그, 대상 graph의 노드·관계 수를 대조한다.

과거 대화에서는 프로젝트 간 결과 혼합, 레거시 분석 조기 종료, Rule 매핑 즉시 종료가 반복되었다. 현재 소스에는 프로젝트별 graph 헤더 전달과 분리 설정이 있지만, **현재 릴리스 이미지가 그 소스를 포함하는지는 manifest SHA로 따로 확인**해야 한다. 볼륨 삭제는 저장된 사용자·프로젝트·그래프를 되돌리기 어려우므로 일반적인 재시작 절차에 포함하지 않는다.

Legacy 탭의 Navigator는 Catalog의 전체 그래프 응답을 받은 뒤 채워진다. 직전 관찰 로그에서는 첫 그래프 조회에 약 19초, 이어진 조회에 약 1초가 걸렸다. 이는 관찰값이지 원인 확정이나 성능 수정 완료를 뜻하지 않는다. 첫 요청의 DB 연결·쿼리·직렬화 시간을 분리 측정해야 한다. UI가 이전 프로젝트 데이터를 보이면 느린 조회와 별개로 요청 헤더·프로젝트 전환 시점의 stale 결과 적용 여부를 확인한다.

## 4-A. 2026-09-23 전 구간 재실행 실측

스택을 비우고(설계·분석 graph 0 노드, `/data` 정리) hr-sample 을 처음부터 다시 돌렸다. 앱 UI 가 아니라 게이트웨이·백엔드 API 를 직접 호출해 단계마다 응답을 남겼다 — 그래야 "화면이 요청을 안 보낸 것"과 "보냈는데 실패한 것"이 갈린다.

| 단계 | 엔드포인트 | 결과 |
|---|---|---|
| 소스 업로드 | `POST :50064/antlr/fileUpload` | 200 — source 28 · DDL 1 · 비대상 7 |
| 파싱 | `POST :50064/antlr/parsing` | **28/28 EXACT**, 복구·부분·실패 0, 2,573줄, 5초 |
| 코드 분석 | `POST :50064/robo/analyze` | **1,306 노드 — 1차와 완전 동일**, 55초 |
| 문서 업로드 | `POST :50065/api/ingest/hybrid/upload` | 200 — PDF 3장 개별 인식(`a2a_pdf_passes: 3`) |
| BPM 도출 | (스트림) | 프로세스 3 · Task 29 · Actor 8 · 구절 접지 29/29 |
| 룰 매핑 | `GET …/process/{id}/explore` | **17/68** (1차는 22/68) |
| ES 승격 | `POST …/promote-to-es` | US 29 · BC 5 · Aggregate 5 · Command 19 · Event 104 · ReadModel 15 · UI 29 · Policy 4 |
| 와이어프레임 | `POST :50065/api/ai-design/wireframe/{ui}` | **29/29** (렌더러 투입 후) |
| Figma 싱크 | 플러그인 경유 | **28/29** |

### 코드 분석은 멱등하다

두 판의 노드·관계 수가 하나도 다르지 않았다 — 총 1,306 노드, `RULE 75 / TABLE 15 / COLUMN 101 / FK 12 / METHOD 171 / CLASS 30`, `PARENT_OF 1108 / REFERENCES 329 / CALLS 85 / HAS_RULE 75 / READS 18 / WRITES 15`. DDL 수치는 hr-sample README 가 명시한 정답(표 15·컬럼 101·FK 12)과 일치한다.

### 룰 매핑은 멱등하지 않다

같은 입력·같은 코드·같은 모델인데 **22/68 → 17/68**, 룰 붙은 Task 10 → 9 로 흔들렸다. 에이전트 탐색(`method=agentic`)이라 그렇다. 프로세스별 탐색 시간도 65s / 40s / 191s 로 제각각이었다. **미배정 51건 중 검토 큐로 올라온 것은 0건** — 임계값 아래는 사람에게 묻지 않고 버려진다.

이 흔들림은 하류로 그대로 간다. UserStory 30개 중 룰 출처(`SOURCED_FROM→Rule`)를 가진 것은 11개뿐이었다. 나머지 19개는 출처 패널을 열어도 빈 화면이 맞다 — 백엔드는 정상이다(US-025·US-027 은 룰 반환, US-001 은 `{"rules":[]}`).

### 정정 — 초판의 "`buildApprovalLine` 룰 0건" 은 틀렸다

초판은 `ApprovalLineBuilder.buildApprovalLine` 이 IF 6개를 가졌는데 RULE 0건이라고 적었다. **실제로는 RULE 6건이고, 룰을 가장 많이 가진 메서드다.** 조회를 `ORDER BY rules DESC` 로 정렬해 놓고 출력에 `tail -45` 를 걸었는데 전체가 46행이라 맨 위 한 줄이 잘린 것이었다. 전체 46행의 합이 75 인 것까지 확인했다.

따라서 README 의 12개 규칙 중 **11개**가 잡힌다. 남은 `LeaveGrantDao.isAlreadyGranted` 는 자식이 `TRY` 1 + `ASSIGNMENT` 2 뿐이고 IF 가 없다 — 중복 판정이 Java 분기가 아니라 SQL 안에 있어 조건·효과 쌍으로 뽑을 대상이 아니다.

### 두 판 연속 재현된 결함

- **pdf2bpmn facade 401.** `PDF2BPMN_FACADE_KEY` 가 백엔드 환경에 없어 3건 모두 401 → 네이티브 폴백. **화면에서는 구분되지 않는다.** 컨테이너 쪽 `config/pdf2bpmn.env` 의 `FACADE_API_KEY` 는 값이 **OpenAI 키와 동일**하다(둘 다 `sk-proj-…` 164자) — 공유 시크릿으로 모델 키를 재사용한 것이라 납품 전 정리가 필요하다.
- **`source_pdf_name` 오기.** 프로세스 3개가 내용은 각각 다른 문서인데 출처가 전부 첫 PDF 로 찍힌다. 본문 접지는 문서별로 정확하다(구절 45건, 29/29) — 이름표만 틀린다.
- **`GET /api/figma-binding/failures` 가 백엔드를 통째로 멈춘다.** 실패가 1건이라도 있으면 조기 반환 경로를 안 타고 `fetch_classifier_view` 로 들어가는데, 그 안에 `OPTIONAL MATCH (u:UI {id: uid})<-[*1..30]-(c0:Command)` 가 있다. 관계 타입 제한 없는 30홉 역방향 경로를 실패 UI 마다 도는 것이라 끝나지 않는다. 게다가 `get_failures` 가 `async def` 인데 동기 함수를 스레드풀 없이 직접 부르므로 **uvicorn 이벤트 루프가 통째로 막힌다** — 한 요청이 앱 전체를 세운다. 실패가 0건일 때는 조기 반환해서 드러나지 않았다. **실패가 남아 있는 동안 History 탭·실패 패널을 열지 말 것.**
- **`FigmaBinding.lastSyncAt` 이 갱신되지 않는다.** 프레임 28장이 올라간 뒤에도 `null` 이었다.

### 해소된 결함

- **와이어프레임 미생성 / Figma 싱크 전량 실패** — §1-A. 원인은 코드가 아니라 배포 구성 누락이었다.
- **`EXAMPLE` · `AFFECTS_TABLE` 0건** — 결함이 아니다. 현재 analyzer pin 의 프로덕션 코드에 그 생성 경로가 없다(테스트 파일에만 문자열이 있다). hr-sample README 의 기대치가 이 analyzer 버전과 어긋난 것이다.

## 5. Figma 플러그인 연동 상태

플러그인은 Backend URL(현재 시험값 `http://127.0.0.1:50065`), Figma File Key, **Robo Architect Figma 연동 화면에서 발급한 5분 일회용 연결 코드**가 필요하다. 코드 교환은 `/api/auth/figma-exchange`이고, 발급은 로그인한 사용자의 현재 프로젝트 권한을 검사하는 `/api/auth/figma-pair`다. 교환된 토큰은 Figma API와 지정 프로젝트 graph에만 사용할 수 있다. 화면의 “5분간 유효한 일회용 코드”는 입력된 코드가 아니라 placeholder다.

직전에는 플러그인이 `Connecting to ...`에서 멈추고 백엔드에 요청 자체가 도착하지 않았다. 소스 `e4b4567`은 요청을 Figma 플러그인 메인 스레드의 Fetch API로 전달하고, 코드가 비었을 때 즉시 안내하도록 수정했다. 이후 Figma가 `devAllowedDomains`의 `127.0.0.1` 항목을 manifest 등록 단계에서 거부해 `0e977b6`에서 그 항목을 제거했다. **2026-09-23 사용자가 플러그인 연결 성공을 확인했다.** 재실행할 때는 개발 플러그인을 다시 불러오고 새 연결 코드를 발급해 입력한다. Electron 재시작만으로 Figma 개발 플러그인의 로드된 코드가 자동 교체되지는 않는다. `50065`도 고정 계약이 아니므로 다음 실행에서는 `docker-state.json`/백엔드 포트를 다시 확인한다.


**2026-09-23 재검증.** 그래프를 비우면 `FigmaBinding` 노드도 사라지므로 플러그인을 다시 연결해야 한다(모달의 "바인딩된 Figma 다큐먼트가 없습니다" 가 그때는 정상 상태다). 재연결 후 스토리보드 페이지 생성과 프레임 push 가 동작했다 — 프레임 28/29. 초판이 적어둔 "플러그인이 연결됐는데 UI 가 하나도 안 생긴다" 의 원인은 플러그인이 아니라 **와이어프레임 렌더러 부재**였다(§1-A).

싱크 실패를 조사할 때 `/api/figma-binding/failures` 를 부르면 백엔드가 멈춘다(§4-A). 실패 목록은 그래프에서 직접 읽는 편이 안전하다 — `MATCH (u:UI) WHERE u.figmaSyncStatus = 'failed' RETURN u.displayName, u.figmaSyncLastError`.

## 6. 실행 방법 (Windows PowerShell)

아래 경로는 **현재 장비의 실제 배치**다. 다른 PC에서는 경로를 바꾼다. 개발 프로필과 패키지 앱의 Compose 스택을 동시에 무작정 띄우지 않는다. 실행 전 Docker Desktop이 켜져 있는지 확인하고, 이미 분석이나 업로드 중이면 종료·재시작 전에 작업 상태를 확인한다.

### A. Workspace 개발 실행 — 수정 소스 검증용

```powershell
Set-Location 'C:\Users\YSW\Desktop\robo-workspace'
.\robo.cmd doctor architect-electron
.\robo.cmd up architect-electron -Build
```

### robo-workspace 만으로 전부 뜨는가

**개발 실행과 설치본은 서비스 구성이 다르다.** 이것을 섞으면 "어제는 됐는데" 가 나온다.

```text
robo.cmd up architect-electron          설치본(Robo-Architect.exe)
──────────────────────────────          ────────────────────────────
호스트 프로세스로 직접 기동:              Electron 이 Docker Compose 를 소유:
  antlr      8401                         graph-db · graph-bolt · mindsdb
  gateway    9000                         fabric · catalog · analyzer
  analyzer  15502                         parser · gateway · pdf2bpmn
  catalog   15503                         wireframe          (컨테이너 9)
  fabric     8404                       + 호스트 Architect API (번들 Python)
  wireframe  7610   ← 2026-09-23 추가
  Electron (ROBO_BACKEND_DIR 설정)
  + 백엔드는 uv 로 직접 — Docker 스택은 안 뜬다
```

`architect-electron` 프로필의 Electron 항목은 `ROBO_BACKEND_DIR` 를 설정한다. 그러면 `usePackagedRuntime()` 이 **false** 가 되어 **Electron 이 Docker 스택을 띄우지 않고** 백엔드도 `uv run` 으로 돈다. 즉 개발 실행에서는 `docker-stack.ts` 가 주입하는 `WIREFRAME_SERVICE_URL` 도 설정되지 않고, `open_pencil_client` 의 기본값 `http://localhost:7610` 이 쓰인다.

그래서 **2026-09-23 이전에는 `robo.cmd up architect-electron` 으로도 와이어프레임이 뜨지 않았다** — `dev.sh` 로 띄웠을 때만 됐다. `workspace.json` 에 `wireframe` 서비스(Bun, 7610)를 더해 그 구멍을 막았다. 기본 포트가 같으므로 별도 환경변수 없이 맞물린다.

전제 조건이 둘 있다.

- **`bun` 이 PATH 에 있어야 한다.** `robo.ps1` 은 `file` 에 경로 구분자가 없으면 `Get-Command` 로 찾는다. 없으면 `robo.cmd doctor architect-electron` 이 `bun is not available` 로 세운다.
- **`open-pencil/node_modules` 가 있어야 한다.** 없으면 `cd open-pencil && bun install`. 설치본에는 이 조건이 없다 — 이미지 안에서 `bun install --production` 으로 만든다.

그리고 개발 실행은 **설치본의 이미지·인증 구성을 보증하지 않는다.** 설치본에서만 나는 실패(예: `PDF2BPMN_FACADE_KEY` 누락으로 facade 가 401 을 내는 것)는 개발 실행에서 재현되지 않을 수 있다.

최초 준비 또는 의존성 변경 시에는 먼저 `.\robo.cmd setup architect-electron`을 실행한다. 개발용 환경 설정은 `robo-workspace\.env`를 사용한다. 이미 빌드한 것을 그대로 실행하려면 `-Build`를 빼고 `.\robo.cmd up architect-electron`을 쓴다. 상태 확인과 **이 프로필이 관리하는 프로세스 종료**는 다음 명령이다.

```powershell
.\robo.cmd status architect-electron
.\robo.cmd down architect-electron
```

Architect 저장소의 `scripts\dev-desktop.cmd`는 독립 런처가 아니라 위 Workspace 실행기의 래퍼다. 현재 폴더 배치에서는 Workspace를 자동으로 찾지만, 다른 배치에서는 `ROBO_WORKSPACE_DIR`을 지정한다. 이 개발 실행은 아래 오프라인 패키지의 이미지·인증 구성을 그대로 보증하지 않는다.

### B. 기존 패키지 `win-unpacked` 실행 — 현재 릴리스 재현용

```powershell
Set-Location 'C:\Users\YSW\Desktop\project\robo-architect'
Get-Content '.\desktop\out\dist-figma-pair\win-unpacked\resources\runtime\runtime-manifest.json' |
  ConvertFrom-Json | Select-Object releaseId, source
& '.\desktop\out\dist-figma-pair\win-unpacked\Robo-Architect.exe'
```

이 실행 파일은 작성 시점에 존재하지만 **현재 HEAD를 자동 반영하지 않는다**. 앱은 번들 manifest의 이미지·환경 checksum을 사용하고, 포트는 `%APPDATA%\robo-architect-desktop\runtime\docker-state.json`에 저장한다. 로그인 화면이 다르거나 변경 사항이 안 보이면 앱을 다시 띄우기 전에 **실행 파일 경로와 manifest SHA**부터 확인한다. 로그는 `%APPDATA%\robo-architect-desktop\logs\desktop.log`다. 볼륨을 지우거나 번들 `.env`를 직접 고쳐서 맞추지 않는다.

### C. 새 unpacked/설치본 만들기 — 최신 소스 반영용

```powershell
Set-Location 'C:\Users\YSW\Desktop\robo-workspace'
.\robo.cmd setup architect-electron
.\robo.cmd doctor architect-electron
.\robo.cmd build architect-electron unpacked
# 전달용 전체 오프라인 릴리스가 필요할 때만:
.\robo.cmd release architect-electron
```

`build ... unpacked`와 `release ...`는 목적이 다르다. 전달용 release는 Docker 이미지·Python 런타임·환경 스냅샷을 함께 묶으므로 시간이 오래 걸리고, 결과 manifest의 SHA를 반드시 재확인한다. `robo-architect\scripts\build-desktop-app.cmd`도 Workspace 빌드의 래퍼다. `-SkipFrontend`는 기존 프런트 산출물 재사용이 의도된 경우에만 사용한다. Figma 플러그인은 Electron과 별도 번들이므로 `figma-plugin/build.sh`로 빌드한 다음 Figma 개발 플러그인을 다시 불러와야 한다.

## 7. 안전한 재현·릴리스 체크리스트

1. 각 독립 저장소의 브랜치·SHA·dirty 상태, Architect gitlink SHA를 기록한다. 필요한 변경은 각 저장소에 커밋·푸시한 뒤 상위 gitlink를 갱신한다.
2. release 입력 pin과 결과 `runtime-manifest.json`의 `source`, 이미지 태그·ID, 환경 스냅샷 checksum을 대조한다. **브랜치 이름보다 SHA가 실제 실행 근거다.**
3. 새 unpacked 디렉터리에서 실행하고 실제 `.exe` 경로, release ID, `docker-state.json` 포트, 백엔드 로그를 기록한다. 기존 앱/Compose의 무분별한 중복 기동은 피한다.
4. `/api/auth/provider` → 로그인 → 프로젝트 선택 → 프로젝트 graph 확인 → 두 C 파일만 새로 분석해 노드·관계·Navigator 범위 확인 → 문서 BPM/Rule 매핑/승격 순으로 검증한다.
5. Figma는 플러그인 재로드, 새 연결 코드 발급, 교환·status 요청 도착 및 지정 프로젝트 graph 권한을 별도로 검증한다.
6. 첫 Legacy 진입 지연은 Catalog 전체 graph 요청의 구간별 시간을 기록해 성능 이슈로 추적한다. 기능 성공과 성능 개선을 하나의 완료 판정으로 합치지 않는다.

8. **서비스를 하나 더할 때** 는 순서를 지킨다 — `runtime-manifest.template.json` 의 `images`·`imageIds` 에 키를 먼저 넣고, `docker-stack.ts` 의 `STATE_SCHEMA_VERSION` 을 올리고(포트가 늘면 옛 상태 파일이 `undefined` 를 낸다), `ManagedServiceId`·표시명·프로브를 채운 뒤, `robo.ps1` 에 이미지 빌드를 더한다. 프로브는 healthcheck 로 끝내지 말고 **그 서비스가 실제로 하는 일**을 값싸게 한 번 시킨다.
9. 개발 실행(`robo.cmd up`)과 설치본은 **서비스 구성이 다르다**(§6 A). 한쪽에서 된 것을 다른 쪽의 근거로 쓰지 않는다.

주요 근거: `desktop/src/main/docker-stack.ts`, `desktop/src/main/backend.ts`, `desktop/src/main/probes/index.ts`, `desktop/runtime/compose.yml`, `open-pencil/Dockerfile`, `open-pencil/packages/cli/src/wireframe-service.ts`, `api/features/ai_design/wireframe_agent.py`, `api/platform/open_pencil_client.py`, `api/features/figma_binding/repository.py`, `robo-workspace/workspace.json`, `robo-workspace/scripts/robo.ps1`, `desktop/out/dist-figma-pair/win-unpacked/resources/runtime/runtime-manifest.json`, `api/platform/identity/auth_guard.py`, `api/features/auth/router.py`, `.gitmodules`, 각 저장소의 2026-09-23 로컬 `HEAD`.
