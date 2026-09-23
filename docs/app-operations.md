# Robo Architect 앱 운영

설치본을 **쓰는 사람**을 위한 문서다. 소스를 받거나 빌드할 필요가 없다.
빌드·릴리스는 [electron-runtime-handoff-2026-09-23.md](electron-runtime-handoff-2026-09-23.md) 를 본다.

---

## 1. 무엇이 무엇과 이야기하는가

```text
Robo-Architect.exe  (Electron)
│
├─ 화면 : Vue Architect + Module Federation 으로 올라오는 Analyzer 화면
│
├─ Architect API  ── Windows 호스트 프로세스 (번들 Python, 127.0.0.1:<동적>)
│    │                 컨테이너가 아니다. 로컬 파일·프로젝트 경로·Claude Code PTY 를
│    │                 써야 하므로 호스트에 있다.
│    ├─ 사용자·프로젝트 → graph-db 에 PostgreSQL 로 직접        (OG_PG_*)
│    ├─ 설계·분석 그래프 → graph-bolt 에 Bolt 로                (NEO4J_*)
│    ├─ 코드 분석·조회  → gateway → analyzer / catalog / parser
│    ├─ 문서→BPMN      → pdf2bpmn
│    └─ 와이어프레임    → wireframe
│
└─ Docker Compose  ── 앱이 소유한다. 앱이 켜면 뜨고, 포트도 앱이 고른다.
     graph-db     Ontological PostgreSQL            ← 모든 그래프·사용자·프로젝트
     graph-bolt   Bolt 프로토콜 게이트웨이            ← 앱은 이쪽으로만 그래프를 본다
     gateway      API 게이트웨이
     analyzer     코드 분석기
     catalog      데이터 카탈로그
     fabric       데이터 패브릭
     parser       ANTLR 코드 파서
     mindsdb      데이터 연결
     pdf2bpmn     문서 → BPMN
     wireframe    open-pencil 렌더러 (JSX → 화면 구조)
```

**그래프 저장소는 Neo4j 가 아니다.** Ontological PostgreSQL 위에 Bolt 호환
게이트웨이를 얹은 것이다. `NEO4J_*` 라는 변수명은 앱이 쓰는 **프로토콜**의
이름이지 엔진 이름이 아니다.

프로젝트마다 그래프가 둘이다 — 설계 `prj_xxx`, 분석 `prj_xxx_a`. **분석은 대상
그래프를 통째로 비우고 다시 쓰므로 둘이 같으면 분석이 설계를 지운다.** 앱이
기동 시점에 같은 값이면 막는다.

포트는 **실행할 때마다 달라진다.** 앱이 빈 포트를 골라
`%APPDATA%\robo-architect-desktop\runtime\docker-state.json` 에 적는다.
전부 `127.0.0.1` 에만 열린다.

---

## 2. 설치

필요한 것은 셋이다.

| | |
|---|---|
| **Docker Desktop** | 켜져 있어야 한다. 앱이 컨테이너를 띄운다 |
| **`Robo-Architect-Setup-<릴리스>.exe`** | 관리자 권한 불필요(per-user 설치) |
| **`robo-images.tar`** | 컨테이너 이미지 전부. 설치 파일과 **함께** 받는다 |

인터넷도, 소스 체크아웃도, `docker pull` 도 필요 없다. 오프라인 설치가 설계
목표다. 다만 **이미지는 설치 파일 안에 들어 있지 않고 옆에 따로 온다** — tar
하나가 2.5GB 라 설치 파일 생성기(`makensis`, 32비트)의 주소공간 한계를 넘는다.

### 순서

**1. 받은 파일이 맞는지 확인한다.** 두 파일 모두 `SHA256SUMS` 에 적혀 있다.

```powershell
Get-FileHash -Algorithm SHA256 `
  .\Robo-Architect-Setup-<릴리스>.exe, .\robo-images.tar
```

**2. 설치 파일을 실행한다.**

**3. 이미지 tar 를 앱이 찾는 자리에 둔다.** 이 단계를 빠뜨리면 앱이 첫 기동에서
`docker.image_archive_missing` 으로 선다(찾아본 자리를 오류에 적어 준다).

```powershell
$dest = Join-Path $env:APPDATA 'robo-architect-desktop\runtime'
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Move-Item .\robo-images.tar (Join-Path $dest 'robo-images.tar')
```

> 다른 자리에 두고 싶으면 `ROBO_IMAGE_ARCHIVE` 에 절대 경로를 지정해도 된다.
> 어디에 두든 앱이 manifest 의 `imageArchiveSha256` 으로 무결성을 검사한다.

첫 기동에서 이미지를 적재하느라 몇 분 걸린다. 한 번 적재하면 그 뒤로는 tar 를
다시 읽지 않는다 — 이미지 ID 가 manifest 와 맞으면 건너뛴다.

---

## 3. 설치 후 한 번 — 비밀을 채운다

**릴리스에는 비밀이 들어 있지 않다.** 설치한 사람이 환경변수로 넣는다.
안 넣으면 앱이 **기동에서 이름을 대고 멈춘다**(`runtime.credentials_missing`)
— 무엇이 비었는지 오류 메시지가 그대로 알려 주므로, 목록을 외울 필요는 없다.

필요한 이름은 릴리스마다 `runtime-manifest.json` 의 `credentialNames` 에 적혀
있다. 보통은 이렇다.

| 변수 | 없으면 생기는 일 |
|---|---|
| `AUTH_JWT_SECRET` | 앱을 다시 열 때마다 **모든 세션이 끊긴다**(임시 비밀로 토큰 발급) |
| `AUTH_ROLE_SECRET` | **프로젝트를 만들 수 없다** — "role 비밀번호를 만들 수 없다" 오류 |
| `PDF2BPMN_FACADE_KEY` | 문서→BPMN 이 **조용히 폴백으로 내려간다**. 화면에는 그대로 BPM 이 나와서 눈치채기 어렵다 |
| `OPENAI_API_KEY` 계열 | 분석·생성이 전부 빈손으로 끝난다 |

> **같은 모델 키를 여러 이름으로 요구한다** — `OPENAI_API_KEY`,
> `LLM_API_KEY`, `ROBO_LLM_API_KEY`, `ROBO_EMBED_API_KEY`,
> `ROBO_SEARCH_LLM_API_KEY`. 서비스마다 읽는 변수 이름이 달라서다. 값은 같은
> 것을 넣으면 된다. 이름을 하나로 모으는 것은 각 서비스 이미지를 건드려야
> 하는 일이라 아직 안 했다.

`PDF2BPMN_FACADE_KEY` 는 **모델 키와 다른 값**으로 정한다. 아무 난수면 된다 —
컨테이너와 백엔드가 서로를 확인하는 용도일 뿐이다. (예전 설치본은 이 값이
모델 키와 글자까지 같았다. 그러면 이 파일을 읽을 수 있는 사람이 모델 키도
읽는다.)

**설치본의 `.env` 를 고치면 안 된다.** 그 파일은 manifest 의 checksum 에 묶여
있어서, 한 글자만 바뀌어도 앱이 `runtime.environment_checksum_mismatch` 로
아예 안 뜬다. **사용자 환경변수로 넣는다.**

```powershell
# 앞의 둘은 아무 난수여도 되지만, 한번 정하면 바꾸지 않는다.
# 바꾸면 기존 사용자 role 의 비밀번호가 어긋나 그래프 연결이 끊긴다.
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
function New-Secret { $b = New-Object byte[] 48; $rng.GetBytes($b); [Convert]::ToBase64String($b) }

[Environment]::SetEnvironmentVariable('AUTH_JWT_SECRET',  (New-Secret), 'User')
[Environment]::SetEnvironmentVariable('AUTH_ROLE_SECRET', (New-Secret), 'User')
# pdf2bpmn 의 공유 시크릿. **모델 키를 재사용하지 마라.**
[Environment]::SetEnvironmentVariable('PDF2BPMN_FACADE_KEY', (New-Secret), 'User')

# 모델 키. 같은 값을 읽는 이름이 여럿이다(위 표의 주석 참고).
$modelKey = '<발급받은 모델 키>'
foreach ($n in 'OPENAI_API_KEY','LLM_API_KEY','ROBO_LLM_API_KEY',
                'ROBO_EMBED_API_KEY','ROBO_SEARCH_LLM_API_KEY') {
  [Environment]::SetEnvironmentVariable($n, $modelKey, 'User')
}
```

> 설정한 뒤 **로그아웃·재로그인하거나 Explorer 를 재시작**해야 아이콘으로 켠
> 앱에 반영된다. 그 전에는 터미널에서 띄워야 한다.

로그인 계정이 없으면 개발용 로그인을 쓸 수 있다. **납품본에서는 꺼 두는 것이
맞다** — 아이디/비밀번호만으로 들어오는 문이다.

```powershell
[Environment]::SetEnvironmentVariable('AUTH_DEV_LOGIN_ENABLED', 'true', 'User')   # test / test
```

---

## 4. 띄우고, 끄고, 보고

**띄우기** — Docker Desktop 을 먼저 켜고 앱 아이콘을 누른다. 앱이 컨테이너
10개를 띄우고, 준비되면 호스트 백엔드를 붙이고, 화면을 연다. 첫 기동은
이미지를 적재하느라 몇 분 걸린다. 두 번째부터는 따뜻한 상태를 재사용한다.

**끄기** — 창을 닫는다. **컨테이너는 일부러 남는다**(다음 기동을 빠르게 하려고).
창을 닫았다는 사실만으로 서비스가 내려갔다고 보면 안 된다.

**상태 보기**

```powershell
# 앱이 소유한 컨테이너만 (라벨로 가른다 — 이름·포트로 가르지 않는다)
docker ps --filter "label=org.uengine.robo.component" --format "{{.Names}}`t{{.Status}}"

# 이번 실행의 포트
Get-Content "$env:APPDATA\robo-architect-desktop\runtime\docker-state.json"

# 앱 로그
Get-Content "$env:APPDATA\robo-architect-desktop\logs\desktop.log" -Tail 50
```

**완전히 내리기** — 앱을 끄고 컨테이너까지 내린다. 볼륨은 건드리지 않는다.

```powershell
docker compose --project-name robo-architect-desktop down
```

> **볼륨을 지우지 마라.** 사용자·프로젝트·설계 그래프가 전부 거기 있고
> 되돌릴 수 없다. 일반적인 재시작 절차에 `down -v` 는 들어가지 않는다.

---

## 5. 안 될 때 보는 곳

증상마다 먼저 볼 곳이 다르다.

| 증상 | 먼저 본다 |
|---|---|
| 앱이 아예 안 뜬다 | `desktop.log` 의 `backend.status`. `runtime.environment_checksum_mismatch` 면 설치본 `.env` 를 누가 고친 것이다 |
| 첫 기동에서 `docker.image_archive_missing` | `robo-images.tar` 를 안 옮겼다. 설치 §3 |
| 기동에서 `runtime.credentials_missing` | 오류가 댄 이름을 환경변수로 넣는다. 설치 §3 |
| 프로젝트 생성이 안 된다 | `AUTH_ROLE_SECRET` |
| 매번 로그인이 풀린다 | `AUTH_JWT_SECRET` |
| 컨테이너는 healthy 인데 화면이 죽어 있다 | **healthcheck 는 준비의 근거가 아니다.** 앱의 서비스 상태 표시를 본다 — 기능 프로브가 따로 잰다 |
| 화면은 멀쩡한데 결과가 이상하다 | 프로젝트가 맞는지, 설계/분석 그래프가 갈려 있는지 |
| 와이어프레임이 안 생긴다 | `wireframe` 컨테이너가 떴는지. 이 서비스가 없으면 **오류 없이 조용히 빈다** |
| 문서→BPMN 이 이상하다 | `PDF2BPMN_FACADE_KEY`. 없으면 폴백으로 내려가는데 화면으로는 구분이 안 된다 |

**Docker 가 물린 경우** — `docker ps` 가 응답하지 않고, 컨테이너 포트는 TCP
연결은 되는데 HTTP 가 무응답이면 WSL/Docker 쪽이다. 앱을 아무리 재시작해도
안 낫는다. Docker Desktop 을 재시작하고, 그래도 안 되면 PC 를 재부팅한다.

**아직 고쳐지지 않은 것** — 싱크 실패가 하나라도 있는 상태에서 Figma 연동의
**History 탭·실패 패널을 열면 백엔드가 멈춘다**(무거운 그래프 조회가 이벤트
루프를 막는다). 실패를 확인해야 하면 그 화면 대신 로그를 본다.

---

## 6. 소스가 필요한 경우

**쓰기만 한다면 필요 없다.** 설치 파일 하나로 끝난다.

소스와 `robo-workspace` 가 필요한 경우는 둘뿐이다.

- **새 릴리스를 만들 때** — `robo.cmd release architect-electron`
- **고친 소스를 확인할 때** — `robo.cmd up architect-electron`

개발 실행은 설치본과 **구성이 다르다**. 서비스를 호스트 프로세스로 띄우고
Docker 스택을 쓰지 않으므로, 설치본에서만 나는 문제가 재현되지 않는다.
자세한 것은 인수인계 문서 §6 을 본다.
