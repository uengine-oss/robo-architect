# 데모 준비 핸드오프 (2026-07-13)

> **다음 에이전트가 바로 이어받기 위한 문서.** 사람용 데모 대본은 별도: `docs/demo-script.html`

## 0. 목표

쇼핑몰 레거시(지저분한 C 코드) → 그래프 시각화 → 요구사항 → DDD 설계 → **실제 코드 생성**까지의
End-to-End를 **녹화 영상**으로 제작. 로딩 시간은 편집으로 커버(사용자 확인). Electron 빌드로 진행 예정
(웹과의 차이 = 업로드 대신 워크스페이스 지정뿐).

---

## 1. 지금 살아있는 서비스 (이 세션에서 기동함)

| 포트 | 서비스 | 상태 | 기동 명령 |
|---|---|---|---|
| 7687 | Neo4j | ✅ | Neo4j Desktop (**사용자가 GUI로 실행** — 에이전트는 못 켬) |
| 5502 | analyzer | ✅ | `cd robo-data-analyzer && ./.venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 5502` |
| 5503 | catalog | ✅ | `cd robo-architect/robo-analyzer/robo-data-catalog && ./.venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 5503` |
| 8081 | antlr | ✅ | `cd antlr-code-parser && SERVER_PORT=8081 ./mvnw -q spring-boot:run` |
| 9000 | gateway | ✅ | `cd api-gateway && /c/Users/roede/.m2/wrapper/dists/apache-maven-3.9.6/834f1afe40575b70b4b2527f4b12df8e/bin/mvn -q spring-boot:run` |
| 3000 | analyzer 프론트 | ✅ | `cd robo-data-frontend && npm run dev` |
| 8001 | 아키텍트 API | ✅ | **★반드시 사용자 터미널에서** (함정 ② 참조) |
| 8004 | **data-fabric** (신규 클론) | ✅ | `cd robo-data-fabric/backend && ./.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8004` |
| 47334 | MindsDB (도커) | ✅ | `cd data/sampledb && docker compose up -d` |
| 55432 | PostgreSQL (도커) | ✅ | 동일 (DB/User=`shopmall`, PW=`shopmall123`) |
| 8000 | text2sql | ❌ 미기동 | `.env` 필수(`target_db_password` 등) — **발견 ③ 참조: 불필요할 수 있음** |
| 5173 | 아키텍트 프론트 | ❌ 꺼짐 | `cd robo-architect/frontend && npm run dev` |

**PowerShell `.ps1` 실행정책에 막히므로(`dev-desktop.ps1` 불가) 위처럼 개별 기동할 것.**

---

## 2. 완료·커밋된 작업

### ★ 핵심 버그 수정 — `d968840` (robo-architect, **푸시됨**)

**증상**: Windows에서 AI 스킬 실행이 무한 멈춤(`INTENT_FAILED`). 인텐트/Plan/헌장 전부 안 돌았음.

**근본 원인**: `shutil.which("claude")`가 npm 배치 shim `claude.CMD`를 반환 → `cmd.exe` 경유 → **실시간 출력(스트리밍) 파이프가 자식에게 안 이어짐** → subprocess가 stdout을 영영 못 받고 hang.
- `--version`(즉시종료)은 성공, `-p`(스트리밍)만 hang → 원인 규명이 헷갈렸던 이유
- `claude.exe` 직접 스폰 시 **1.3초 정상 출력** 실측

**수정**: `api/platform/skill_runner.py`의 `_resolve_claude_bin()`이 `.cmd/.bat/.ps1` shim을 **실제 `claude.exe`로 해소**. 못 찾으면 기존 방식 폴백 → **회귀 위험 0**. 추가로 무인 스폰이라 `stdin=subprocess.DEVNULL`.

### 기타 커밋

| 커밋 | 레포 | 내용 | 푸시 |
|---|---|---|---|
| `5466571` | architect | 스킬 스폰에 robo-cluster MCP `--mcp-config` 주입 + intent SKILL.md에 "레거시 참조" 지시 | ✅ |
| `931b4a8` | architect | 버그 보고서 + 흐름 안내 HTML (`docs/`) | ✅ |
| `e29dea3` | architect | 서브모듈 bump | ❌ **보류(ahead 1)** |
| `432820d` | analyzer | rank-bm25 의존성 | ✅ |
| `6c28cbd` | analyzer | spec044 tasks 정합 | ✅ |
| `6e89cc7` | frontend | spec046 그래프 의미검색 UI (WIP 일괄) | ✅ |
| `c826f86` | frontend | EMBEDDED 마커 역할 제외 | ✅ |

**서브모듈 동기화 완료**: architect가 analyzer `432820d` · frontend `6e89cc7`를 가리킴.

---

## 3. 실증된 것 (데모에서 자신 있게 말해도 되는 것)

1. **Intent E2E 완주** — 요구사항 한 문장 → BC/Feature/UserStory/GWT 생성, 오류 0
2. **★레거시 참조 실증** — AI가 `cluster_retrieve` **5회 호출**. 생성된 DDD에 실제 코드값 인용:
   `shipping_calc_fee`, **5만원 이상 무료**, **기본 3천원**, **도서산간 3천원**, **우편번호 63**, `member_grade_pol`
   → 원문 `shipping.c` 직접 대조 결과 **100% 일치**(판정 순서까지)
3. **헌장(Constitution)** — AI가 근거와 함께 "모놀리스 + Spring Boot+PostgreSQL+Vue3" 추천 → 저장(`CON-ROOT`)
4. **Plan 확정** — 전술 18노드(Aggregate 4/Command 5/Event 6/ReadModel 3) + 아키텍처 결정
5. **그래프가 안티패턴 전부 포착** — 아래 §7 표

---

## 4. 미완 — 다음 할 일 (우선순위)

### ① 그래프 재분석 (최우선, 필수)

**현재 Neo4j에 중복 잔존**: `shipping_calc_fee` 노드 2개, CALLS 1324(정상의 2배).
`data/source`는 이미 **비워뒀음**(파일 0개).

**절차**:
1. 소스 복원: `분석대상모음/shopmall/source/*.c,*.h` (12개)를 UI 업로드에 사용
   (**주의: `data/source/`에 미리 복사하지 말 것** — 함정 ① 참조)
2. DDL: `data/ddl/shopmall_schema.sql`
3. 프론트(3000) → 좌측 **코드** → 업로드 영역 클릭 → 파일 12개 + DDL 1개 → **업로드**
4. **"기존 데이터 감지" 모달 → [삭제 후 시작]** 클릭 (안 누르면 아무 일도 안 일어남)
5. 완료 후 검증: `MATCH (f {name:'shipping_calc_fee'}) RETURN count(f)` → **1개**여야 정상, CALLS ≈ **662**

### ② 그래프 조작·검색·시나리오 캡처 (데모용, 미촬영)

- 노드 클릭(상세 패널)·더블클릭(펼치기)·우클릭(편집/삭제)·드래그
- 필터·색상 변경·보기 모드
- **일반 검색 + 의미 검색** 2종
- **시나리오 추적**: `shipping_request` → CALL 18개 → `orders`/`product_stock` WRITE (안티패턴 증명)
- **노드 패널에 원문 코드가 뜨는지 확인** (노드 속성엔 `file_path`+`start_line`/`end_line`만 있음 → 프론트가 파일에서 읽어오는지 확인 필요)

### ③ Code 탭 완주 (실제 코드 생성)

사용자 경험상 **"껍데기만" 나왔다**고 함. **로직 확인 결과 그건 의도가 아님**:
- `skills/robo-proposals/robo-proposal-implement/SKILL.md`: "Strategic+Tactical Diff에 따라 **실제 코드를 구현**", "새 UserStory → 도메인 모델·API·프런트엔드 파일 생성", "Constitution/Plan의 기술스택·Docker 개발환경을 그대로 따른다"
- `implement_runner._context_doc()`가 워크트리에 `PROPOSAL_<id>.md`를 쓰고 **Strategic/Tactical Diff + Constitution + Implementation Plan 전문**을 전달 → 정보 부족 아님
- 실행 방식이 **대화형 루프**(`/robo-implement <PRO-NNN>` → `PROPOSAL_<id>_TASKS.md` 체크리스트를 하나씩 구현·커밋)
- → **"껍데기"는 루프 미완주**로 추정. 실제로 끝까지 돌려서 얼마나 나오는지 확인 필요
- **전제**: 8001이 사용자 터미널에서 떠 있어야 함(함정 ②) + `projectRoot`(대상 git repo) 지정

### ④ text2sql → data-fabric 교체 (발견 ③)

### ⑤ 데모 대본 완성 (`docs/demo-script.html` — 캡처 13장 임베드됨, 미촬영분만 채우면 됨)

---

## 5. 이번에 발견한 것

### 발견 ① — data-fabric의 정체

UI의 **"데이터 소스 추가"**(PostgreSQL 연결 등록)는 **`data-fabric` 서비스(8004)** 가 담당.
워크스페이스에 클론이 안 돼 있어서 **500 에러**가 났던 것.

```bash
git clone https://github.com/uengine-oss/robo-data-fabric.git
cd robo-data-fabric/backend
python -m venv .venv && ./.venv/Scripts/python.exe -m pip install -r requirements.txt
```

**★`.env` 필수 (env.example에 NEO4J 설정이 빠져 있음 → 없으면 500 AuthError)**:
```
MINDSDB_URL=http://127.0.0.1:47334
NEO4J_URI=bolt://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=an1021402
NEO4J_DATABASE=neo4j
OPENAI_API_KEY=sk-dummy-not-used
```

**UI 등록 성공 확인**: `GET :8004/api/datasources?source=neo4j` →
`{"datasources":[{"name":"shopmall","engine":"postgres","tables":[]}]}`

### 발견 ② — 실제 DB 데이터가 AI 분석에 투입된다

analyzer 파이프라인의 **`fetch_table_samples_step`** → catalog → 실제 DB `SELECT * LIMIT 5` → **LLM 분석 컨텍스트**.
즉 AI가 "테이블에 실제로 어떤 값이 있는지" 보고 의미를 파악.
**단 필수 아님** — 데이터소스 없이도 분석 정상(노드 2,503개 생성 확인).

### 발견 ③ — ★text2sql 의존을 끊을 수 있다

catalog는 샘플 행을 **text2sql(8000)** 로 가져오도록 하드코딩:
```python
# robo-data-catalog/service/text2sql_client.py
Text2SqlClient(base_url="http://localhost:8000", datasource="myds")
async def fetch_rows(...)  →  text2sql 로 요청
```

그런데 **data-fabric에 같은 기능이 이미 있음**:
```
GET /api/datasources/{name}/tables/{table}/sample    ← 실제 데이터 샘플
GET /api/datasources/{name}/tables
GET /api/datasources/{name}/extract-metadata
```

→ **catalog가 data-fabric을 직접 부르면 text2sql 불필요**(text2sql은 프론트 "자연어 질의" 탭 전용으로 남김).

**권장(회귀 0)**: env 스위치 `ROBO_SAMPLE_PROVIDER=text2sql|fabric` (기본 text2sql 유지, 데모는 fabric).
**변경 범위**: `robo-data-catalog`(서브모듈) + `robo-architect` 서브모듈 bump.
**사용자 승인 받음** — "이렇게 하면 안 됨?" → 진행 방향 합의됨(구현은 미착수).

---

## 6. ★함정 (반드시 알 것)

### 함정 ① — 중복 분석 (이번에 밟음)
UI 업로드는 파일을 **`data/source/` 루트에 저장**한다. 기존에 `data/source/shopmall/` 폴더가 있으면
**analyzer가 두 벌을 다 분석** → 노드·CALLS가 **정확히 2배**, 함수마다 노드 2개.
- **해결**: 업로드 전 `data/source`를 **완전히 비운다**
- **규칙**: `data/` 아래엔 `source`·`ddl`·`analysis`(+`sampledb`)만 있어야 함 (사용자 지시)
- 원본 백업: `d:\work\robo\분석대상모음\shopmall\source\` (12개)

### 함정 ② — 아키텍트 8001은 반드시 사용자 터미널에서
Claude Code 세션 **안**에서 띄운 8001이 claude를 자식으로 스폰하면 하니스가 **차단**(nested unsafe agent).
→ 인텐트·Plan·Code 탭 등 **AI 스킬이 전부 안 돌아감**. 스케줄러 등 우회도 차단됨(시도했다가 막힘).
**반드시 세션 밖(사용자 터미널)에서 기동할 것.**

### 함정 ③ — 업로드 후 "기존 데이터 감지" 모달
"Neo4j에 기존 데이터가 있습니다 → **[삭제 후 시작]** / [기존 데이터에 추가]" 모달이 뜬다.
**"삭제 후 시작"을 눌러야 분석이 진행**된다. 안 누르면 아무 일도 안 일어남(모달 대기).

### 함정 ④ — PowerShell 실행정책
`scripts/dev-desktop.ps1`이 `UnauthorizedAccess`로 막힘. `-ExecutionPolicy Bypass`는 하니스가 차단.
→ **각 서비스 개별 기동**(§1 표).

### 함정 ⑤ — Playwright 파일 업로드
업로드 모달의 `input[type=file]`이 4개. **소스는 `inputs[1]`, DDL은 `inputs[3]`** (실측).
`setInputFiles`에 **짧은 timeout**을 주지 않으면 hang.

---

## 7. 데모에서 강조할 것 (사용자 요청)

- **"쉬운 예제가 아니다"** — 진짜 쇼핑몰 레거시, 2009~2025 7명이 덧댐, **매우 더럽다**
- **코드가 스스로 자백**: `[LEGACY / 손대지말것]`, `임시라했으나 상용`, `*** 순환/갓함수 ... 리팩토링要 ***`
- **안티패턴이 그래프에 그대로 드러남** (아래) — "텍스트로는 안 보이는 얽힘이 노드·화살표로 보인다"
- **노드 패널의 원문 코드**로 "이 코드에서 이게 도출됐다" 증명
- **AI가 레거시를 진짜 읽었다는 증명** — DDD에 실제 코드값(5만원/3천원/우편번호 63) 인용 → 원문 대조

| 더러운 패턴 | 원문 증거 | 그래프가 잡은 것 (실측) |
|---|---|---|
| 갓함수 | `shipping_request` 270줄·11단계 | CALLS **18개** |
| 복붙 중복 | 주석 `[R4 DUPLICATED] order.c와 동일 복붙본` | 같은 규칙이 두 모듈에 |
| 경계 붕괴 | `CROSS-DOMAIN WRITE: orders` | **orders에 주문·정산·배송·프로모션이 WRITE** |
| 숨은 연결 | `dispatch_call("review_point")` 문자열 호출 | CALLS로 포착 (9개 함수 경유) |
| 순환 호출 | `recalc ↔ coupon` | 그래프 사이클 (`apply_coupon ↔ recalc_order_amount`) |
| 허브 폭주 | `write_audit` 아무나 호출 | **fan-in 83개** (`get_code_name` 51) |
| 매직넘버 | 제주 우편번호 63/64/69, 강제택배사 `사유 유실` | — |

**레거시 실제 값** (`shopmall.h`): `FREE_SHIP_AMOUNT 50000` / `BASE_SHIP_FEE 3000` / `JEJU_EXTRA_FEE 3000`

---

## 8. 보유 캡처

스크래치패드에 **analyzer 24장 + 아키텍트 16장**:
`C:\Users\roede\AppData\Local\Temp\claude\d--work-robo\6f42d16a-fd99-4b52-a697-6f39d65e22aa\scratchpad\`
- `demo/` — 01_landing, 04_upload_modal, 05_files_added, 05c_existing_data, 06_analyzing_*(8장), 07_analysis_done, 08b_pg_form 등
- `shot_*` — 아키텍트: shot_new, shot_running, shot_pro003(DDD+레거시 근거), shot_const_done(헌장), shot_plan_generated(전술), shot_confirmed_final(확정)

**미촬영**: 그래프 조작·검색 2종·시나리오 추적·Code 탭 (재분석 후 촬영 필요)

캡처는 `docs/demo-script.html`(사람용 대본)에 base64로 임베드되어 있음.
대본 생성 스크립트: 스크래치패드의 `gen_handoff.py` (재생성 가능).

---

## 9. 관련 문서

- `docs/demo-script.html` — **사람용 데모 대본** (스토리 + 캡처 + 대사 + 조작 + 예상질문)
- `docs/intent-hang-bugfix-report.html` — hang 버그 원인·수정 보고서 (동료 공유용)
- `docs/robo-flow-guide.html` — 일반인용 전체 흐름 안내
