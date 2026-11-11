# Robo Architect 서버 배포 (posco-web)

설치를 없애고 브라우저로 쓰게 한다. IT 가 서버에 한 번 올리면 설계자는 사내 주소를
열고 SWP 로 들어가는 것뿐이다. 사내 PC·VDI 에서는 가상화가 안 돼 설치본(Electron +
Docker)이 한 대도 설치되지 못했다(2026-11-09 이슈 6).

msa-ez 가 이미 같은 방식으로 돈다 — 통합 서버 한 대 / AP·DB 두 대 compose 와 SWP SSO.
그 짜임을 따른다.

```text
브라우저 ──► web (nginx :8080) ──/api/**──► architect-api ──► authority (SWP·승인·공유)
               │ 빌드된 자산만                    │  └─/api/gateway/** (로그인·권한을 본 뒤)
               │ /analyzer/ = 분석 화면           │        └──► gateway ─► analyzer·catalog·fabric·parser
               └──────────────────────────────── └──► graph-bolt / graph-db (Ontological)
                                                      wireframe
```

## 파일

| 파일 | 무엇 |
|---|---|
| `docker-compose.yml` | **통합 서버 한 대.** 기준 파일 |
| `docker-compose.split.db.yml` | DB 서버 — graph-db · graph-bolt · authority(+init) |
| `docker-compose.split.ap.yml` | AP 서버 — web · architect-api · 분석 다섯 · wireframe |
| `.env.example` | 사람이 넣는 값 **전부**. 분할이면 두 서버에 같은 파일 |
| `authority-init.py` | 권한 서버 최초 초기화(역할 → migrate → 관리자 → 정책). 다시 돌려도 안전 |
| `check.sh` | 띄우기 전 검사. 아무것도 안 바꾸고 비밀은 이름·길이만 찍는다 |
| `docker-compose.local-test.yml` | **로컬 시험 전용 overlay** — SWP 없이 개발 로그인(admin·user2), web 을 127.0.0.1 에만. 서버에 쓰지 않는다 |
| `init-env.sh` | `.env` 를 만들고 비밀 넷을 채운다(다시 돌려도 안전) |
| `make-split.py` | 분할 두 파일을 통합 파일에서 **만든다**(손으로 안 고친다) |
| `pin-images.sh` | 새로 굽는 두 이미지의 태그를 세 파일에 같이 박는다 |

## 올리기 — 통합 서버

```bash
cp .env.example .env && chmod 600 .env && vi .env   # [고치는 곳] 넷 + 만들어 넣는 값
bash check.sh
docker compose up -d --wait                          # podman: podman compose …
```

브라우저에서 `ROBO_PUBLIC_URL` 을 연다 → SWP 로그인 → `ROBO_ADMIN_EMPNO` 로 들어온 사람이
관리자다. 다른 사람은 들어오면 **승인 대기**가 되고 관리자가 승인한다.

## 올리기 — AP·DB 두 대

```bash
# 두 서버에 같은 .env (ROBO_DB_SERVER_IP = DB 서버의 사내망 IP)
DB 서버:  bash check.sh split.db && docker compose -f docker-compose.split.db.yml up -d --wait
AP 서버:  bash check.sh split.ap && docker compose -f docker-compose.split.ap.yml up -d --wait
```

DB 서버는 5432 · 7687 · 59020 을 `ROBO_DB_SERVER_IP` 에 연다. **AP 서버에서만 닿게**
방화벽을 둔다 — Bolt 는 평문 인증이다. AP 서버는 8080 하나만 연다.

## 값 — 사람이 넣는 것은 `.env` 하나

| 무엇 | 이름 |
|---|---|
| AI 키 · 주소 | `ROBO_AI_API_KEY` · `ROBO_AI_BASE_URL` (P-GPT) |
| 관리자 사번 | `ROBO_ADMIN_EMPNO` |
| DB 비밀번호 | `ROBO_GRAPH_PASSWORD` (+ 권한 서버 역할 둘) |
| SWP 주소 | `SWP_SSO_*` — 비우면 가동계 기본값 · `ROBO_PUBLIC_URL` (콜백 허용 origin) |

### 설치본 가이드의 이름 → 이 판의 이름

`사용자-설치-가이드`(robo-env.ps1) 와 `관리자-DB올리기`(robo-central.sh) 에서 쓰던 값이
어디로 갔는지. **2026-11-10 에 두 가이드의 변수 이름을 전수로 뽑아 대조했다.**

| 가이드 | 이 판 `.env` | 들어가는 곳 |
|---|---|---|
| `$AI_KEY` (다섯 이름에 같은 값) | `ROBO_AI_API_KEY` | OPENAI_API_KEY(api·fabric·catalog) · LLM_API_KEY(catalog) · ROBO_LLM/EMBED/SEARCH_LLM_API_KEY(analyzer) |
| (msa-ez 의 OPENAI_BASE_URL) | `ROBO_AI_BASE_URL` | 모든 AI 주소 칸 |
| `$GRAPH_HOST` · `SERVER_IP` · `ROBO_GRAPH_BIND` · `ROBO_AUTHORITY_BIND` | `ROBO_DB_SERVER_IP` (분할만) | 통합 서버는 서비스 이름으로 붙어 필요 없다 |
| `$GRAPH_PASSWORD` · `GRAPH_PW` | `ROBO_GRAPH_PASSWORD` | 그래프 소유자 |
| `$GRAPH_PG_PORT` · `$GRAPH_BOLT_PORT` | `ROBO_DB_PG_PORT` · `ROBO_DB_BOLT_PORT` (분할만) | |
| `$ROLE_SECRET` · `$JWT_SECRET` | `AUTH_ROLE_SECRET` · `AUTH_JWT_SECRET` | authority **와 architect-api 둘 다**(같은 값) |
| `AUTH_RT_PW` | `ROBO_AUTHORITY_DB_PASSWORD` | robo_authority 역할 |
| `OPER_PW` | — | 운영 DSN 은 소유자로(§결정 ④) |
| `ADMIN_EMPNO` · `APPROVAL_REQUIRED` | `ROBO_ADMIN_EMPNO` · `ROBO_APPROVAL_REQUIRED` | authority-init |
| `SWP_SSO_*` | 같은 이름 | authority |
| `SWP_SSO_LOG_RAW` | — | **코드에 없다**(주석에만 있다). 확인은 authority 로그 `auth.sso.validated` 의 사번·username 으로 |
| `AUTH_CALLBACK_ALLOWLIST` | `ROBO_PUBLIC_URL` | authority |
| `PDF2BPMN_FACADE_KEY` (PC 난수) | — | pdf2bpmn 을 뺐다(§pdf2bpmn) |
| `ROBO_GRAPH_MODE=central` · `ROBO_AUTHORITY_URL` | 고정값(yml) | api |
| `ROBO_IMAGE_*` · `$IMAGE_TAR` | 고정 태그(yml) · `bundle.sh --images` | |
| `$DEV_*` (시험 로그인) | — | **일부러 없다.** 중앙 authority 가 개발 로그인을 거부한다 |
| `ROBO_INGESTION_URL` | — | 가이드대로 **안 둔다** |

컨테이너에는 compose 의 `environment:` 로만 들어간다. **컨테이너에 들어가 파일을 고치지
않는다.** 납품본에서 `config/*.env` · `architect/app/.env` 로 실리던 제품 설정(모델 이름 ·
검색 파라미터 등)은 값 그대로 `environment:` 에 옮겨 적었다.

납품본 설정 중 **일부러 뺀 것** — 첫째, fabric 의 `ROBO_DATASOURCE_REPLACE_LOCALHOST=host.docker.internal`.
설치본에서 사용자가 적은 데이터 소스 주소 `localhost` 를 "**그 사용자의 PC**" 로 바꿔 주던 값이다.
서버에는 그런 PC 가 없고, podman 에서는 그 이름도 다르다(`host.containers.internal`). 서버
판에서는 데이터 소스를 **실제 사내망 주소**로 적는다. 둘째, pdf2bpmn 관련 네 이름(§pdf2bpmn).

⚠ **2026-11-11 에 다시 대조하니 어긋난 값이 하나 있었다** — analyzer 의 `ROBO_SEARCH_LLM_CONFIG`.
납품본은 `pgpt` 인데 이 yml 에 `gpt54_mini_openai` 가 적혀 있었다. 그 설정 파일의 `api_base` 는
**`https://api.openai.com/v1`** 이고, 그 옆에 `ROBO_SEARCH_LLM_API_KEY` 로 사내 키가 들어간다.
돌아가는 분석기에서 그 이름을 읽는 곳은 `tests/eval/gate_eval.py` 하나라(런타임 LLM 은 모두
`SETTINGS.analysis_llm.config`) **실효는 없었지만**, 사내 키가 본점 주소를 가리키는 설정 옆에
놓이는 자리였다. 지금은 `${ROBO_ANALYZER_LLM_CONFIG:-pgpt}` 로 분석용과 같은 갈래를 쓰고,
`check.sh` 가 **yml 에 박힌 모든 `*_LLM_CONFIG`** 를 AI 주소와 짝지어 본다(전에는
`ROBO_ANALYZER_LLM_CONFIG` 만 보아 이 자리를 놓쳤다).

⚠⚠ **그리고 반대 방향도 봐야 했다 — 2026-11-11.** 처음 대조는 "납품에 있는데 compose 에
없는 이름" 과 "값이 다른 이름" 만 봤다. **compose 가 더한 이름**은 보지 않았고, 거기에
하나가 숨어 있었다 — architect-api 의 `EMBEDDING_API_KEY`. 납품 `architect/app/.env` 에는
그 이름이 **없어서** 임베딩이 `OPENAI_BASE_URL`(P-GPT)을 물려받았는데, 이 yml 이 키를
더하면서 `api/platform/embeddings.py` 가 그것을 "전용 endpoint" 로 보고 **OpenAI 본점**으로
보냈다(`dedicated_key` → `embed_base_url or OPENAI_DEFAULT_BASE_URL`). 띄운 컨테이너에서
쟀다: `describe().baseUrl = https://api.openai.com/v1`. 전용 키가 있으니 그 경고
(`sharesChatEndpoint`)도 **안 뜬다.** 사내망에서는 임베딩이 조용히 실패했을 자리다.
⇒ `EMBEDDING_BASE_URL: ${ROBO_AI_BASE_URL:?}` 을 더했다(고친 뒤 같은 컨테이너에서
   `baseUrl` 이 게이트웨이로 바뀌는 것을 다시 쟀다). `check.sh` 가 이제 셋을 본다:
   ① 주석 아닌 자리에 박힌 `api.openai.com` ② AI 주소 칸이 모두 `.env` 를 가리키는지
   ③ **`EMBEDDING_API_KEY` 가 있으면 `EMBEDDING_BASE_URL` 도 있는지**(없는 값을 잡는 검사).
   둘을 가짜로 걸어 확인했다. 반대 방향으로 다시 훑은 결과 그 밖에 위험한 추가는 없었다
   (나머지는 설치본이 프로세스 환경으로 주던 키들과 내부 주소·플래그다).

그 밖의 값은 설치본(`resources/runtime`)의 `config/*.env` · `architect/app/.env` 와
**이름·값 전부를 대조했다**(2026-11-11 다시 — 서비스별 전수. 다른 것은 AI 주소가 `.env` 하나로
모인 것, 위의 셋, 그리고 `AUTH_BIND_CONNECTION`(설치본 `.env` 는 false 였지만 Electron 이
프로세스 환경으로 true 를 넣어 실효값이 true 였다)뿐이다).

msa-ez 는 비밀을 yml 에 바로 적는다. 여기서는 그러지 않는다 — yml 은 저장소에 들어가고,
비밀은 `.env`(600) 에만 둔다. 화면에서 고치는 방식은 같다(파일 하나를 연다).

## 이미지 — 열한 장 전부 GHCR(`robo-posco-*`) · 전부 고정 태그

| 서비스 | 이미지 (`ghcr.io/uengine-oss/…`) | 태그 | 출처 |
|---|---|---|---|
| graph-db | `robo-posco-graph-db` | `0.1.0-wde10ff6c-afff41f36-scda199-rdel-swp` | 납품판 그대로 |
| graph-bolt | `robo-posco-graph-bolt` | 〃 | 〃 |
| authority (+init) | `robo-posco-authority` | 〃 | 〃 |
| analyzer | `robo-posco-analyzer` | 〃 | 〃 |
| catalog | `robo-posco-catalog` | 〃 | 〃 |
| fabric | `robo-posco-fabric` | 〃 | 〃 |
| parser | `robo-posco-parser` | 〃 | 〃 |
| gateway | `robo-posco-gateway` | 〃 | 〃 |
| wireframe | `robo-posco-wireframe` | 〃 | 〃 |
| architect-api | `robo-posco-architect-api` | `posco-web-<sha7>` | CI 가 굽는다 |
| web (nginx) | `robo-posco-web` | `posco-web-<sha7>` | CI 가 굽는다 |

- 납품판 아홉 장은 **다시 굽지 않고** 납품 `robo-images.tar` 의 이미지를 그대로 올렸다
  (2026-11-10). 같은 커밋이라도 다시 구우면 image ID 가 달라져 납품 매니페스트와 대조가 끊긴다.
  올린 뒤 레지스트리의 **최상위(index) digest** 가 매니페스트 `imageIds` 와 같은 것을 확인했다
  (`docker buildx imagetools inspect <ref>` 의 `Digest`). 이 도커는 containerd 저장소라 image ID 가
  그 digest 다 — 받은 쪽에서 `docker image inspect --format '{{.Id}}'` 로 같은 값을 본다.
- 이름을 `robo-posco-*` 로 따로 둔 이유: `robo-analyzer` · `robo-antlr-parser` ·
  `robo-api-gateway` · `robo-data-fabric` 는 GHCR 에 **다른 제품의 공개 패키지**로 이미 있다.
  거기에 태그를 더하면 고객 납품 이미지가 공개 패키지에 섞인다.
- `robo-posco-*` 는 **public** 이다(2026-11-10) — 서버에서 `docker login` 없이 받는다.
  공개 전에 납품 이미지들의 파일을 검사했다: 키·`.env` 0.
  ⓘ `robo-posco-pdf2bpmn:735d135` 도 올라가 있지만 **이제 yml 이 쓰지 않는다**(§pdf2bpmn).
  지우지 않고 둔다 — 되살릴 때 상류와 digest 가 다른 그 이미지가 필요하다. 고객 문자열은 둘 —
  authority 의 SWP 기본 주소(공개 저장소 robo-architect 에 이미 있는 것)와
  **analyzer 의 `llm/configs/pgpt.yaml` 에 든 P-GPT 사내 주소**(소스 저장소는 private).
  analyzer 는 그것을 알고 공개했다.
  GHCR 에 못 닿는 서버는 `bundle.sh <dir> --images` 로 tar 하나에 묶어 옮긴다.

---

## 결정 — 막히던 자리 넷

### ① 프로젝트 파일이 누구 디스크에 있나 → **서버 볼륨. 레거시 분석은 업로드.**

```text
정한 것
  레거시 분석   브라우저에서는 **업로드 모드**로 연다. 이미 코드가 그렇게 되어 있다 —
                AnalysisPanel.vue `readRoot()` 가 Electron 이 아니면 경로를 안 넘긴다
                ("서버에 올린 Architect 에서 로컬 폴더는 사용자 PC 가 아니라 서버의 폴더").
                올린 소스는 공용 `shared_data` 볼륨(/data)에 쌓이고 결과는 팀 그래프에 간다
  코드 생성·    대상 프로젝트는 서버의 `workspace` 볼륨(/workspace)에 둔다.
  제안 구현     `projectRoot` 는 그래프의 Proposal 속성이라 코드를 안 바꾸고 서버 경로를 쓴다
포기한 것
  설계자 PC 의 폴더를 바로 고르는 흐름. 브라우저는 서버에 남의 PC 경로를 줄 수 없다
남은 일
  /workspace 에 저장소를 들이는 길(사내 git 서버 clone 등). msa-ez 는 gitea 를 둔다.
  지금은 관리자가 볼륨에 clone 해 두는 것으로 시작한다
```

### ② Claude Code 터미널 → **끈다.**

```text
정한 것   web 이미지를 `VITE_DISABLE_CLAUDE_TERMINAL=1` 로 굽는다(Dockerfile.web ARG).
          architect-api 이미지에는 claude CLI 를 싣지 않는다
이유      그 터미널은 ConPTY·winpty 로 **그 PC 의** claude CLI 를 띄우는 것이다.
          서버 컨테이너에서 띄우면 모든 설계자가 서버의 셸 하나를 나눠 쓰게 된다 —
          격리도 감사도 없다
포기한 것 Code 탭의 대화형 터미널. 코드 생성·제안 구현의 in-process 엔진은 그대로다
          (i18n: "claude CLI 가 필요합니다. 설치 전까지는 in-process 엔진을 사용")
```

### ③ 문서 내보내기 → **이미 브라우저에서 파일로 떨어진다. 고칠 것 없음.**

```text
잰 것  ExportDocumentDialog.vue `downloadBlob()` — Blob + <a download>. app:// 를 안 쓴다
       `app://` 가 나오는 곳은 ExportDocumentTemplate.vue:60 의 **주석** 하나다
       (Electron 의 origin 에서 localStorage 가 어떻게 되는지 설명하는 글)
```

### ④ 여럿이 같이 쓰면 그래프 격리 → **이미 있는 중앙 구성을 그대로 켠다 + 게이트웨이를 막는다.**

```text
켜 둔 것
  ROBO_GRAPH_MODE=central      이미 있는 사용자 role 비밀번호를 덮지 않는다
  AUTH_BIND_CONNECTION=true    요청마다 **로그인한 사람의 DB role** 로 그래프에 붙는다
  authority                    로그인·승인·프로젝트 공유. 프로젝트 graph 의 권한 원천은
                               og_catalog.grantee 다
  ⇒ 설치본의 "중앙 DB + PC 여럿" 과 같은 격리다. 다른 것은 API 프로세스가 하나라는 것뿐
새로 막은 것 — `/api/gateway/**`
  설치본에서는 Electron 이 이 경로를 gateway 로 **곧장** 보냈다(로그인 검사 없음 · 루프백).
  서버에서 nginx 가 그렇게 하면 analyzer·catalog·fabric(데이터 소스 질의 포함)이
  사내망 전체에 **로그인 없이** 열린다. 그래서 nginx 는 이 경로를 architect-api 로 보내고,
  거기서(api/features/gateway_proxy)
    - 로그인을 본다(AuthGuardMiddleware)
    - 브라우저가 보낸 X-Neo4j-URI/User/Password 를 버린다
    - X-Neo4j-Database 가 **내가 등급을 가진 프로젝트의** 설계·분석 graph 일 때만 넘긴다
      (쓰기 요청은 write 이상)
  덤으로 Electron 이 하던 `/robo/analyze` 본문 좁히기도 여기로 옮겼다 — 없으면 브라우저에서
  레거시 분석이 **422** 로 바로 막힌다(분석기 AnalyzeRequest 가 extra="forbid")
DB 역할 — 런타임만 제한, 프로젝트 운영은 소유자
  authority 런타임   robo_authority (superuser 아님 — authority 가 기동에서 이것을 검사한다)
  프로젝트 운영 DSN   소유자(ROBO_GRAPH_USER). robo-central.sh 의 robo_operator 는 만들지 않는다
  이유  이 배치에서는 architect-api 가 이미 소유자 자격을 들고 있다(설치본 central 의 PC 와
        같다). 운영 역할을 따로 두어도 격리가 늘지 않고, 그 역할에 필요한 최소 권한
        (CREATE ROLE · og_create_graph · og_grant …)은 아직 한 번도 재지 않았다
        (docs/account-authority.md: 중앙 구성은 "아직 한 번도 돌려 본 기록이 없다")
  진짜 최소 권한은 architect-api 에서 소유자 자격을 빼는 일과 **같이** 한다
남은 것
  X-Neo4j-Database 를 안 실은 분석 요청은 각 서비스의 기본 graph(`analyzer_run`)로 간다 —
  설치본과 같은 동작이고, 거기는 **공용**이다. 프로젝트마다 분석 graph 를 고르게 하는 것은
  화면(projectsStore.currentAnalyzerGraph)이 이미 하고 있다
  한 API 프로세스 안의 캐시·진행 중 작업이 사용자별로 갈리는지는 현장에서 두 계정으로 잰다
```

## pdf2bpmn — **빼 두었다** (2026-11-11)

```text
정한 것   compose 에서 서비스를 빼고 `HYBRID_USE_A2A=false` 로 1단계를 **native 추출기**로 보낸다
          고친 자리 넷 — docker-compose.yml(서비스·facade 주소·키·a2a) · .env.example(FACADE_KEY)
          init-env.sh(비밀 다섯 → 넷) · bundle.sh(facade.py 사본). **코드는 한 줄도 안 바꿨다**
근거      `document_to_bpm` 이 이미 facade → a2a → **native** 로 내려간다(`__init__.py`).
          PDF 글자 뽑기는 업로드 때 PyMuPDF 가 따로 한다(`requirements_document_text.py`) —
          pdf2bpmn 과 무관하다. 쟀다: 뜬 스택의 architect-api 에서
          facade_url()='' · a2a_enabled()=False → 1단계 = native
덤으로 사라진 함정
          `pdf2bpmn/facade.py` 는 **바인드 마운트**였고 그 파일은 묶음에만 복사됐다.
          저장소 폴더에서 compose 를 띄우면 도커가 그 자리에 **빈 디렉터리**를 만들어
          서비스가 재시작을 반복했다(2026-11-10). 메시지 대신 `--wait` 가 안 끝나는 모양이었다.
          이제 yml 의 바인드 마운트는 `authority-init.py` 와 `analyzer-llm/openai_gpt41.yaml`
          둘뿐이고 **둘 다 저장소에 있는 파일**이라, 묶음 폴더와 저장소 폴더가 같게 돈다
⚠ "스킬로 만든다" 의 뜻
          서버 판에는 claude CLI 가 **없다**(§결정 ②). 그래서 여기서 스킬화는 claude 가 아니라
          P-GPT 를 쓰는 native 와 **같은 길**이다. claude CLI 로 돌리는 스킬은 lite 쪽 이야기다
          (`SKILL_RUNNER_PROVIDER=claude_cli`)
못 잰 것   native 추출기가 낸 BPM 이 facade 만큼 쓸만한지 — 문서 한 건을 실제로 돌려 봐야 안다
되살리려면 상류 이미지를 그대로 받지 않는다. `process-gpt-bpmn-extractor:735d135` 는 같은
          태그인데 **다른 이미지**다(상류 b2d8c0… / 납품 3b2833…). GHCR 의
          `robo-posco-pdf2bpmn:735d135` 를 쓴다 — 지우지 않고 뒀다
```

## 서버를 지키는 두 가지 — **compose 가 못 하는 일**

```text
① DB 포트는 compose 가 **좁혀 주지 않는다.** 분할 판의 split.db 는 5432 · 7687 · 59020 을
   `${ROBO_DB_SERVER_IP}` 에 **묶기만** 한다 — 같은 사내망의 아무 PC 에서나 닿는다.
   "AP 서버에서만" 은 **호스트 방화벽**이 하는 일이다(가이드 §7 에 적었다).
   Bolt 는 평문 인증이라 그대로 두면 안 된다
② 메모리 상한 손잡이를 두었다 — `ROBO_MEM_{API,ANALYZER,PARSER,GATEWAY}`.
   기본 **0 = 제한 없음**(지금 동작 그대로). 숫자를 안 꾸며 넣은 이유는 **안 재서**다 —
   쉬는 값만 알고(analyzer 228MiB · parser 676MiB · gateway 518MiB, 2026-11-11) 돌 때를 모른다.
   조여서 OOM 으로 죽는 쪽이 더 나쁘다. 현장에서 분석을 돌리며 재고 나서 올린다.
   ⚠ 건 값이 들어갔는지 꼭 본다 — `docker inspect … --format '{{.HostConfig.Memory}}'`.
     0 이면 안 걸린 것이다(조용히 무시하는 compose 구현이 있다).
     이 PC 의 docker compose v2 에서 `mem_limit` 가 먹는 것은 쟀다(gateway 에 4g → 4294967296)
```

## ⚠ 처음 띄워 보고 찾은 것 — 납품판 `robo-central.sh` 에도 있다

```text
증상   authority 가 기동에서 죽는다(재시작 반복)
       psycopg.errors.InsufficientPrivilege: permission denied for table app_auth_policy
원인   제한 역할 robo_authority 는 만들어지지만 **표 권한을 받는 단계가 없다.**
       권한을 주는 자리는 `accounts_admin configure-access` 하나인데,
       그 명령은 납품 DB 이미지에서 **통과할 수 없다**:
         "PC가 실행 가능한 SECURITY DEFINER 함수를 먼저 검토·차단해야 합니다."
       막는 함수 public.og__ensure_view (ontological 확장) — access.py 허용 목록은
       og_build_view 만 안다
이 판   authority-init.py 가 configure() 의 **서버 역할 몫 권한만** 직접 준다(2-b).
        access.py 의 표 목록이 바뀌면 init 이 멈춘다
납품판  desktop/runtime/robo-central.sh 로 중앙 서버를 세우면 같은 자리에서 설 것이다.
        동결 가지는 건드리지 않았다 — 고치려면 사람이 정한다
```

## 되돌릴 길

- 설치본 가지 `enterprise-custom-p` 와 동결된 `delivery/0.1.0-…-rdel-swp` 는 **안 건드렸다.**
  이 판은 `posco-web` 가지에만 있다.
- 서버의 `graph_data` 볼륨이 데이터 전부다. `down -v` · `volume prune` 금지.
  내릴 때는 `docker compose stop`(또는 `down` — 볼륨은 남는다).

## 현장에서 처음 할 확인 (사람)

```text
ⓐ 설계자 PC 에서 아무것도 안 깔고 ROBO_PUBLIC_URL 열기 → SWP 로 들어가진다
   authority 로그의 `auth.sso.validated` 에 찍힌 사번·username 이 본인 것인지로 칸 순서(SWP_IDX_*)를 확인
ⓑ 레거시 분석 한 건을 업로드로 끝까지 → 다른 설계자 계정으로 자기 브라우저에서 결과가 보인다
   (프로젝트를 그 사람에게 공유한 뒤)
⑦ Code 탭이 터미널 없이 뜨고 나머지 탭이 죽지 않는다
```
