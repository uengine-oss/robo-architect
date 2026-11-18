# 셋째 구성 `age-fabric` 실행하기

Robo Architect Lite 의 셋째 런타임 구성이다. 그래프는 Apache AGE 이고, 원천은 별도 패브릭 서비스 og-fabric 이 맡는다.

| | 기본 구성(그대로) | `age-fabric` |
|---|---|---|
| compose | `desktop/runtime/compose.yml` | `desktop/runtime/compose.age-fabric.yml` |
| 그래프 | graph-db(Ontological) + graph-bolt | **age-db**(Supabase Postgres 15.8 + AGE 1.8.0) + **age-bolt**(Bolt 게이트웨이, 꼬리표 `age-bolt`) |
| 원천 | fabric(robo-data-fabric) → 그래프 엔진의 패브릭 문장 | **fabric**(og-fabric 서비스, 8404) + **fabric-db**(PG16 + `og_fabric` + FDW) |
| 원천 SQL | Bolt 위 패브릭 문장 | og-fabric HTTP(PostgreSQL 방언). 패브릭을 묶는 Cypher 는 없다 |
| 원천 암호 | 엔진의 user mapping(평문) | OS 키체인(safeStorage) → og-fabric 의 로컬 채널 → tmpfs 의 커넥터 파일 |
| compose 프로젝트 | `robo-architect-desktop` | `robo-architect-desktop-age`(기본 스택 옆에서 따로 돈다) |

앱은 런타임 매니페스트의 `"deployVariant": "age-fabric"` 하나로 갈라진다. 이 칸이 없으면 지금과 같은 기본 구성이다(`desktop/src/main/runtime-variant.ts`).

## 1. 이미지

| 매니페스트 키 | 기본 참조 | 만드는 법 |
|---|---|---|
| graphDb | `uengine/supabase-postgres-age:15.8.1.060-age1.8.0` | `ontological-fabric` 의 `age-supabase/build.sh` (가지 `age/main`) |
| graphBolt | `uengine/ontological-bolt:age` | 같은 곳 `age-supabase/gateway/build.sh` |
| fabric | `ogfab-service:stage4` | `/Users/uengine/og-fabric` 가지 `stage4`: `docker build -t ogfab-service:stage4 service/` |
| fabricDb | `ogfab-db:stage4` | `/Users/uengine/og-fabric` 가지 `stage4`: `image/build-local.sh --work <dir>`. 서비스와 같은 커밋에서 굽는다(옛 `ogfab-db:dev` 는 `cf57257` · `c9040ae` 이전 판이라 표본이 42501) |
| catalog | `uengine/robo-data-catalog:age-fabric` | `git -C robo-analyzer/robo-data-catalog archive feat/age-fabric \| docker build -t uengine/robo-data-catalog:age-fabric -` — 하위 모듈의 **가지**에서 굽는다. 상위 저장소의 catalog 핀은 `1f1aaa6` 그대로다(아래 「catalog 핀」) |
| analyzer · parser · gateway | `uengine/robo-analyzer` · `robo-antlr-parser` · `robo-api-gateway` `:lite-mac` | 기본 구성과 같다 |

> ⚠ og-fabric 의 이미지는 og-fabric 의 지금 소스로 다시 구워야 한다. 4단계 시험 때 남아 있던 `ogfab-db:dev`(11-18 11:08)는 `cf57257`(읽기 전용 원천 계정의 기본 키) · `c9040ae`(`allow` 이름 찾기) 이전 판이었다. 그 판으로는 `GET …/tables/{t}/sample` 이 42501 이 된다. 시험에서는 확장만 다시 빌드해 `ogfab-db:stage4` 로 얹었다(아래 5절).

## 2. 런타임 폴더

```bash
scripts/build-age-fabric-runtime.sh --out /path/to/runtime \
    [--image fabric=ogfab-service:stage4 --image fabricDb=ogfab-db:stage4]   # 다른 태그를 쓸 때
    [--venv /Users/uengine/robo-architect-lite/.venv --link-app]            # 앱을 이 폴더로 띄울 때
```

- `compose.age-fabric.yml`, `config/*.env`(analyzer · catalog · parser · gateway 는 출시판과 같다. fabric 은 og-fabric 설정), `architect/app/.env`, `runtime-manifest.json` 을 쓴다.
- 매니페스트에는 로컬 이미지의 참조와 ID 가 들어가고 `imagePull: false` 다. 출시용 빌드(레지스트리 · amd64)는 아직 없다(7절).
- 비밀은 폴더에 들어가지 않는다. 앱이 기동할 때 compose 에 넘긴다.

## 3. 앱으로 띄우기 (개발)

```bash
cd desktop && npm run build
env -u ELECTRON_RUN_AS_NODE ROBO_RUNTIME_MODE=docker ROBO_DOCKER_RUNTIME_DIR=/path/to/runtime \
    ROBO_V1_COMPOSE_PROJECT=none npx electron .
```

- **`ELECTRON_RUN_AS_NODE` 를 지운다.** VS Code 의 터미널 · 확장은 이 값을 넣어 둔다. 남아 있으면 Electron 이 Node 로 떠서 `protocol.registerSchemesAsPrivileged` 에서 죽는다.
- **`frontend/dist` 가 있어야 한다.** 출시판과 같게 굽는 법은 `node scripts/build-desktop-frontend.mjs` 다(분석기 원격까지 `dist/analyzer` 에 둔다). 작업 트리에서 그냥 `vite build` 를 하면 둘이 달라진다. 하나는 `../../../open-pencil` 이 있으면 진짜 open-pencil 을 끌어온다는 것이고(출시판은 저장소 안의 대역), 다른 하나는 `ANALYZER_REMOTE_URL` 이 없어 레거시 탭이 localhost:5001 을 찾는다는 것이다.
- `ROBO_V1_COMPOSE_PROJECT=none` 은 설치된 앱의 기본 스택(`robo-architect-desktop`)이 떠 있어도 평문 이전을 건너뛰게 한다. 설치된 앱의 데이터소스를 건드리지 않는다.
- 개발 실행의 데이터 폴더는 `~/Library/Application Support/robo-architect-desktop` 이다. 설치된 앱(`Robo Architect Lite`)과 겹치지 않는다.

**화면에 나오는 구성.** 셸은 `app:getRuntimeState` 의 `profile`(매니페스트의 `deployVariant` → `runtime-variant.ts` 의 `profileOf`)을 보고 이름을 바꾼다. `age-fabric` 이면 첫 화면이 「Docker 로 그래프 DB(Apache AGE) · Bolt 게이트웨이 · 패브릭(og-fabric) …」이 된다. 상태 칸은 「Apache AGE 연결됨」과 「구성 Apache AGE + og-fabric」이고, 홈 머리글과 SPA 왼쪽 레일의 그래프 풍선 도움말도 Apache AGE 로 나온다. 기본 구성(`profile` 이 `ontological` 이거나 null)은 예전 문구 그대로다.

`startDockerStack()` 의 `age-fabric` 갈래(`desktop/src/main/docker-stack.ts` → `age-fabric-stack.ts`)가 하는 일:

1. `age-db` · `fabric-db` 를 올린다.
2. age-db 에 로그인 역할 `robo` 를 만든다. 비밀번호는 SCRAM 검증값으로만 보낸다. 고정 그래프 `robo` · `analyzer_run` 은 `robo` 로 만들어 `robo` 가 주인이 된다. 게이트웨이는 그래프를 만들지 않는다.
3. fabric-db 의 두 역할(`og`, `og_fabric_service`) 비밀번호를 이 설치의 값으로 맞춘다. 다른 설치가 만든 볼륨이어도 맞는다.
4. `fabric` · `age-bolt` 를 올린다. og-fabric 이 알려 주는 `keychain:` 참조마다 키체인의 비밀을 `PUT /internal/secrets/{ref}` 로 넘긴다. 채널 토큰은 기동마다 새로 만든다.
5. 한 번만: 기본 구성의 graph-db(compose 프로젝트 `robo-architect-desktop`)가 떠 있으면 평문 이전을 한다. 그 엔진이 인라인 암호로 가진 데이터소스를 `og-fabric-migrate --keychain` 으로 옮기고, 돌아온 비밀은 키체인에 넣는다. 다 옮기면 `<데이터 폴더>/runtime/age-fabric-migration.json` 에 기록하고 다시 하지 않는다.
6. 나머지(catalog · analyzer · parser · gateway)를 올린다.

| 환경 변수 | 뜻 |
|---|---|
| `ROBO_COMPOSE_PROJECT` | compose 프로젝트 이름을 바꾼다(시험 스택) |
| `ROBO_V1_COMPOSE_PROJECT` | 평문 이전이 찾을 기본 구성의 프로젝트(기본 `robo-architect-desktop`) |
| `ROBO_PG_STATEMENT_TIMEOUT` | age-db · fabric-db 의 `statement_timeout`(기본 0). `temp_file_limit` 은 늘 2GB |
| `ROBO_AGE_DB_MEMORY` · `ROBO_FABRIC_DB_MEMORY` · `ROBO_ANALYZER_MEMORY` | 메모리 상한(기본 1536m · 512m · 2g) |

열리는 호스트 포트는 모두 `127.0.0.1` 이다. age-bolt(Bolt), fabric(채널 · API, 각각 토큰 필요), analyzer, gateway 가 연다. age-db · fabric-db 는 내부망(`graph` · `fabric`, internal)에만 있다. fabric-db 는 원천으로 나가는 망(`sources`)에 하나 더 붙는다. 그 망에는 fabric-db 하나뿐이다.

## 4. 데이터소스 만들기 (데스크톱)

화면은 암호를 패브릭에 보내지 않는다.

1. 화면이 `window.desktop.fabric.keepDatasourceSecret({name, password})` 를 부른다. 메인은 암호를 키체인(safeStorage, 패키지 macOS 의 「파일 모드」와 상관없이)에 `keychain:ds/<name>` 으로 둔다. 그리고 og-fabric 채널로 넘긴다.
2. 화면은 돌려받은 참조만 담아 `POST /api/datasources {name, engine, parameters: {host, port, database, schema, user, credentials: "keychain:ds/<name>"}}` 를 부른다.
3. 지우기는 `fabric.forgetDatasourceSecret({name})` 이다.

인라인 암호는 og-fabric 이 403(`inline_password_refused`)으로 거부한다.

## 5. E2E

```bash
cd desktop && npm run build
node tests/e2e-age-fabric/run.mjs --runtime /path/to/runtime --work /path/to/work [--keep]
```

- 앱의 `startDockerStack()` 을 그대로 부른다. Node 에서 돌고, `electron` 은 대역이다. `app.getPath` 는 작업 폴더, `safeStorage` 는 되돌릴 수 있는 대역이다.
- 버리는 컨테이너 둘을 함께 띄운다. 원천 PG `ral-agefab-src`(127.0.0.1:28881, `tests/e2e-age-fabric/source.sql`: 6 테이블 + 뷰 1, 선언 FK 없음)와 v1 graph-db `ral-agefab-v1`(127.0.0.1:28882, 인라인 암호 데이터소스 1)이다.
- 시험 순서: 스택 검사 → 평문 이전 → 데이터소스(키체인 참조) → 표본 → 분석기 모양의 TABLE · COLUMN + 선언 FK 1 → FK 추론(`persist`) → AGE 의 FK 간선 → 검토(채택) → 두 번째 기동 → 비밀 누출 검사 → 기본 구성 검사.
- 끝나면 스택과 볼륨, 두 컨테이너를 지운다. 결과는 `<work>/result.json` 이다.

확장만 다시 빌드한 og-fabric-db(시험에 쓴 방법):

```bash
W=/path/to/extbuild; mkdir -p $W/cache $W/artifacts/ext
docker run --rm --memory 8g --cpus 8 -v /Users/uengine/og-fabric:/repo:ro -v $W/cache:/cache -v $W/artifacts:/out \
  postgres:16-bookworm bash -euo pipefail -c '
    apt-get update -qq && apt-get install -y -qq --no-install-recommends build-essential ca-certificates curl \
      pkg-config postgresql-server-dev-16 libclang-dev clang >/dev/null
    cp -r /repo/ext /tmp/ext && rm -rf /tmp/ext/target
    CARGO_HOME=/cache/cargo RUSTUP_HOME=/cache/rustup CARGO_TARGET_DIR=/cache/target OUT=/out/ext SRC=/tmp/ext \
      bash /repo/image/scripts/build-ext.sh'
printf 'FROM ogfab-db:dev\nCOPY ext/ /\n' | DOCKER_BUILDKIT=0 docker build -t ogfab-db:stage4 -f - $W/artifacts
rm -rf $W
```

## 6. 시험 결과 (2026-11-18)

- E2E 검사 43개가 모두 통과했다. 첫 기동은 34초, 두 번째 기동은 33초 걸렸다.
- 원천 `shop` 은 7개(테이블 6 + 뷰 1)를 내준다. 분석기 모양의 TABLE 6개와 선언 FK 1개를 넣고 추론했다.
  - 추론 결과: FK 3개(`order_items.order_id → orders.id`, `order_items.product_id → products.id`, `customers.region_code → regions.code`), 검토 후보 1개(`orders.coupon_id → coupons.coupon_id`, 값이 없어 확인 못 함), 이미 아는 것 1개.
  - 모두 AGE 의 간선이 되었다. 검토 후보를 채택하니 `status: accepted` FK 가 되었다. 추론은 117 ms 걸렸다.
- 단위 시험: 데스크톱 13개(기존 18개와 함께 31개), catalog 13개(전체 201개), og-fabric 7개(전체 13개).
- 자세한 것은 `uengine-platform/reports/age-on-supabase/FABRIC-PROGRESS.md` 11절에 있다.

## 7. 남은 것

- **화면(robo-data-frontend).** 그 화면의 데이터소스 호출은 API 게이트웨이의 `/data-fabric` 경로로 간다. 이 경로가 og-fabric 의 서비스 토큰을 붙이지 않아서, 지금은 401 이다. 고치려면 robo-api-gateway 에서 그 경로에 `Authorization` 을 더하거나, og-fabric 의 `/k/<token>/` 앞머리로 다시 쓰게 해야 한다.
  - 그다음 데이터소스 만들기 폼이 `window.desktop.fabric.keepDatasourceSecret` 을 부르고, `credentials` 만 보내게 한다.
  - test-connection 은 og-fabric 이 robo-data-fabric 의 평평한 꼴이 아니라 create 와 같은 꼴을 받는다.
  - 질의 창의 언어 선택(SQL → og-fabric `/api/query`, Cypher → 그래프 게이트웨이)은 이 화면에 아직 질의 창이 없어 하지 않았다.
- **분석기.** 꼬리표 `age-bolt` 판별과 라벨 사슬 쓰기는 AGE 시험 쪽 일이다(`ANALYZER-ON-AGE.md`). 이 구성에서 분석기는 뜨고 healthy 다. 분석 흐름은 돌리지 않았다.
- **catalog `/tables/resolve-context`.** robo-data-fabric 의 `object-resolution-context` 를 부르는데, og-fabric 에는 그 경로가 없다(404).
- **출시 빌드.** 레지스트리 이름, `push-images`, amd64 이미지(og-fabric 둘 · AGE 둘), Windows 판이 없다.
- **패키지 앱의 키체인.** safeStorage 대역으로만 돌렸다. 패키지된 macOS 앱이 판마다 키체인 접근을 묻는 것은 확인하지 않았다.

## catalog 핀

- `feat/age-fabric`(catalog 의 `40dee7a`)은 `feat/relationship-inference`(eaed1e8) 위에 있다. 그 가지에는 다른 사람의 커밋 13개가 있고, 기본 구성의 catalog 동작도 바꾼다(원천을 Bolt 패브릭 문장으로 읽음).
- 「기존 Robo Architect 는 될 수 있으면 고치지 않는다」에 따라 **Lite 의 catalog 핀은 `1f1aaa6` 에 둔다.** `age-fabric` 용 catalog 이미지만 위의 명령으로 가지에서 따로 굽는다.
- catalog 가지 `feat/age-fabric` 은 본 체크아웃(`/Users/uengine/robo-architect-lite/robo-analyzer/robo-data-catalog`)에도 받아 두었다. 이 작업 트리를 걷어도 가지가 남는다.
- 기본 구성이 relinfer 를 받는 때는 `feat/relationship-inference` 를 따로 Lite 에 들일 때다. 이 구성과 묶지 않는다.
