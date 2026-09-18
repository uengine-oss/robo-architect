# Quickstart — 058 을 재고 고치는 자리

**Feature**: 058 설치본 런타임 감독과 복구 | **Date**: 2026-09-17

09-17 에 맥에서 실제로 밟은 경로다. **그대로 다시 하면 같은 자리에 선다.**

## 0. 무엇이 어디서 되는지부터

```
맥에서 된다     이미지 빌드 · compose 스택 · 라우팅 · 기능 프로브 · 폴백 분기
맥에서 안 된다  Electron 창 (macOS 15.5 가 미서명 Electron 31.7.7 을 실행 시 지운다)
                NSIS 설치본 · 서명 · Windows 호스트 경로
```

화면(US1·US3·US4 의 UI)과 SC-001 은 **Windows 에서** 잰다.

## 1. 스택을 띄운다 (맥, Electron 없이)

### 1.1 이미지 (8종)

```bash
# 우리가 굽는 것 — fabric·parser·gateway 는 저장소에 Dockerfile 이 있다
docker build -t uengine/robo-data-fabric:local   robo-architect/robo-analyzer/robo-data-fabric
docker build -t uengine/robo-antlr-parser:local  antlr-code-parser
docker build -t uengine/robo-api-gateway:local   robo-api-gateway

# analyzer·catalog 는 **우리 브랜치에 Dockerfile 이 없다** (P1 이 해소한다)
# 그때까지는 origin/main 의 것을 스크래치로 뽑아 -f 로 쓴다. 저장소는 안 건드린다
git -C <catalog>  show origin/main:Dockerfile > /tmp/catalog.Dockerfile
docker build -f /tmp/catalog.Dockerfile -t uengine/robo-data-catalog:local <catalog>
# analyzer 는 main 의 Dockerfile 이 requirements.lock 을 쓰는데 우리 브랜치에 없다
# → requirements.txt 를 쓰는 사본을 스크래치에 만든다 (**릴리스용 아님 — 해시 고정 빠짐**)

# 받는 것
docker pull neo4j:5.26.0
docker pull mindsdb/mindsdb:v26.1.0
docker pull --platform linux/amd64 ghcr.io/uengine-oss/process-gpt-bpmn-extractor:8156f77
```

> **`docker build ... | tail` 로 판정하지 마라.** 종료 코드가 `tail` 의 것이라
> 빌드가 죽어도 0 이다. 09-17 에 넷이 전부 실패인데 "성공"으로 읽을 뻔했다.
> **`docker image inspect` 로 실재를 센다.**

### 1.2 디스크

이미지가 47GB 쌓여 있으면 빌드가 `no space left on device` 로 죽는다.

```bash
docker builder prune -f      # 빌드 캐시 — 데이터 아님
docker image prune -f        # 태그 없는 것만
# **볼륨은 건드리지 마라** — Ontological 데이터가 거기 있다
```

### 1.3 config 와 기동

`config/*.env` 는 `release-environment.json` 의 스코프 규칙대로 `robo-workspace/.env`
에서 갈라 만든다. **스크래치에 만든다** — `desktop/runtime/config/*.env` 는 git 추적
대상이라 거기에 키를 쓰면 커밋된다.

```bash
docker compose --env-file stack.env --project-name robo-mac-measure \
  --file compose.yml up --detach --wait --wait-timeout 300
```

`stack.env` 에 이미지 태그·포트·`ROBO_NEO4J_PASSWORD` 를 넣는다. 포트는 **쓰기 전에
비었는지 확인**한다.

## 2. "healthy" 가 진짜인지 잰다 — 이 스펙의 핵심

```bash
# compose 가 뭐라 하나
docker ps --filter "label=org.uengine.robo.release=<id>" --format "{{.Names}}\t{{.Status}}"

# 실제로 일하나
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:<gw>/api/gateway/robo/health        # 404 = analyzer 도달
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:<gw>/api/gateway/robo/check-data/   # 200 = catalog 도달
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:<gw>/api/gateway/data-fabric/health # 200 = fabric 도달
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:<bpmn>/healthz                       # 200 — **이것만으로는 부족**
```

### 갈리는 자리 (09-17 실측)

```
자격증명 틀림   /healthz 200   POST /api/consulting-bpmn 502 (401)
자격증명 맞음   /healthz 200   POST /api/consulting-bpmn 200 · task 4 · gateway 1 · lane 2
```

```bash
curl -s -X POST http://127.0.0.1:<bpmn>/api/consulting-bpmn -H 'Content-Type: application/json' \
  -d '{"process_name":"휴가신청","consulting_outline":"직원이 휴가를 신청한다. 팀장이 검토한다. 승인되면 인사팀에 통보하고, 반려되면 직원에게 사유를 알린다."}'
```

응답은 **JSON 이 아니라 BPMN XML** 이다.

### 500 을 실패로 읽지 마라

```
/api/gateway/antlr/   게이트웨이 500   parser 직접도 500   → 라우팅 정상
```

판정 기준은 **직접 호출과 같은 코드인가**다(`electron-runtime.md` §3.4).
없는 경로를 지어내 부르면 멀쩡한 것을 결함으로 만든다.

## 3. 폴백을 잰다

facade 를 죽여 놓고(자격증명을 깨거나 컨테이너를 내리고) 분기 지점을 부른다.

```python
os.environ["PDF2BPMN_FACADE_URL"] = "http://127.0.0.1:<bpmn>"
from dotenv import load_dotenv; load_dotenv(".env")          # ← 빠뜨리면 키가 없다
from api.features.ingestion.requirements_document_text import extract_text_from_pdf
content = extract_text_from_pdf(open(PDF, "rb").read())      # ← **앱이 쓰는 그 함수**
r = await extract_bpm_skeleton(content=content, pdf_artifacts=[{"pdf_path": PDF, ...}])
print(r.source, r.error, sum(len(s.tasks) for s in r.bundle.processes))
```

### 여기서 세 번 틀렸다 — 같은 함정을 다시 밟지 마라

```
1  content="" 를 넘겼다                            → task 0
2  pypdf 로 뽑으려 했는데 없다. try/except 가 삼켰다 → task 0 (조용히)
3  앱이 쓰는 extract_text_from_pdf 로 교체          → task 7  ✅
```

**입력을 만들 때는 앱이 쓰는 그 함수를 쓴다.** 새로 만든 추출기는 검사의 결함이 된다.

### 기대값

```
source = "native"
error  = facade 502 + a2a 연결 실패가 **둘 다** 보존
task   = 0 이 아니다. 그럴듯한 BPM 이 나온다  ← 그래서 결과물로는 못 가린다
```

## 4. 이식 (P1) 을 시작하는 자리

```bash
cd robo-architect/robo-analyzer/robo-data-catalog
git branch backup/pre-rebase-<날짜>      # **되돌리기를 먼저 만든다**
git rebase origin/main
```

09-17 에 난 충돌.

```
CONFLICT (modify/delete)  client/neo4j_client.py — main 에서 삭제됨 → 재구현
CONFLICT (content)        main.py
```

**catalog 를 먼저 끝내고 패턴을 확정한 뒤 analyzer(274 커밋)로 간다.** 둘을 동시에
건드리면 어느 쪽 때문에 깨졌는지 못 가린다.

## 5. 정리

```bash
docker compose --project-name robo-mac-measure down     # 볼륨은 남는다
docker compose --project-name robo-mac-measure down -v  # 측정 데이터까지 지운다
```

**`docker restart ontological-dev` 는 하지 마라** — 엔트리포인트가 `sleep infinity`
라서 안에서 손으로 띄운 Postgres 와 Bolt 게이트웨이가 같이 죽는다.

## 6. 잴 때마다 확인할 것

```
포트는 응답으로 잰다        nc -z 와 /dev/tcp 는 IPv6 바인딩에서 거짓 음성
프로세스는 pid 로 안 잰다   낡은 pid 파일이 "실행 중"이라 말한다
빌드는 실재로 잰다          파이프 뒤 종료 코드는 마지막 명령의 것
0건은 이유를 가른다         데이터 없음 / 처리 실패 / 조회 실패 / **프로브가 못 돔**
비교는 같은 자리에서 센다   한쪽은 노드, 한쪽은 XML 태그를 세면 없는 차이가 생긴다
```
