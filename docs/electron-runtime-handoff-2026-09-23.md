# Robo Architect Electron 실행·서비스 인수인계 (2026-09-23)

이 문서는 **현재 저장소와 로컬 산출물에서 확인한 상태**를 기록한다. 과거 대화에서 재현한 증상은 별도로 표시한다. 소스 체크아웃, 서브모듈 pin, 릴리스 manifest, 실행 중 프로세스는 서로 다른 상태이므로 하나를 확인했다고 나머지도 최신이라고 간주하면 안 된다. 이 문서 작성 시점에는 실행 중 프로세스·Docker 상태를 재검증하지 않았다.

## 1. 전체 구조

```text
Robo-Architect.exe (Electron)
  ├─ Vue Architect 화면 + Module Federation Analyzer 화면
  ├─ Windows 호스트의 Architect FastAPI (번들 Python, 127.0.0.1:<동적 포트>)
  │    ├─ 사용자·프로젝트: Ontological PostgreSQL 직접 연결 (OG_PG_*)
  │    ├─ 설계 그래프: Bolt 게이트웨이 (NEO4J_*)
  │    └─ Gateway / Analyzer MCP / pdf2bpmn 호출
  └─ Docker Compose: 9개 서비스
       graph-db (Ontological PostgreSQL) → graph-bolt (Neo4j Bolt 호환)
       mindsdb, fabric, catalog, analyzer, parser, gateway, pdf2bpmn
```

Electron이 Compose를 시작하고 포트를 선택해 `%APPDATA%\robo-architect-desktop\runtime\docker-state.json`에 저장한다. 그래프 PostgreSQL·Bolt, Analyzer, Gateway, pdf2bpmn의 호스트 포트는 `127.0.0.1`에만 게시된다. 컨테이너 간에는 Compose 서비스명으로 통신한다. Architect API는 컨테이너가 아니라 Windows 호스트에서 실행되어 로컬 파일·프로젝트 경로를 사용할 수 있다. 일반 창 종료 시 Compose는 따뜻한 상태로 남을 수 있으므로, 창을 닫았다는 사실만으로 서비스 종료나 볼륨 삭제를 추론하지 않는다.

그래프 저장소는 기존 Neo4j Community가 아니라 **Ontological PostgreSQL + Bolt 호환 게이트웨이**다. `NEO4J_*` 변수명은 클라이언트 프로토콜의 흔적이다. 기본 설계 그래프는 `robo`, 기본 분석 그래프는 `analyzer_run`이며, 프로젝트별 분석은 요청의 `X-Project-Graph`/`X-Neo4j-Database`가 가리키는 별도 그래프로 분리해야 한다. 설계와 분석 graph를 같은 값으로 설정하거나 분석 대상 헤더가 누락되면 다른 프로젝트 결과가 섞이거나 초기화 대상이 잘못될 위험이 있다.

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

표의 SHA는 작성 시점의 로컬 체크아웃이다. 중첩 서브모듈의 `HEAD`는 분리(detached) 상태일 수 있으며, **그 자체가 오류는 아니다**. 독립 저장소의 `main`이 더 앞서도 Architect 프로필은 자동으로 따라가지 않는다. `git pull`만으로 서브모듈 gitlink·Docker 이미지·`app.asar`·번들 Python이 갱신되지 않는다. 상위 저장소가 의도한 서브모듈 commit을 가리키도록 갱신·커밋하고, release를 다시 만들어야 한다.

현재 `dist-figma-pair/win-unpacked/resources/runtime/runtime-manifest.json`은 release `0.1.0-w6046d7f3-aebdb75a6`와 이미지 태그·image ID·source SHA를 고정한다. 이 manifest의 Architect SHA와 frontend SHA는 현재 체크아웃보다 오래되었다. 따라서 이 실행 파일로 새 소스를 검증했다고 주장하려면 **실제 로드된 `app.asar`, frontend, runtime manifest, 이미지 ID를 각각** 확인해야 한다. 임의의 개발용 unpacked 디렉터리를 재사용하면 소스와 번들이 섞일 수 있다. `desktop/resources/runtime/runtime-manifest.json`도 같은 오래된 릴리스 값을 담고 있다. `robo-workspace` 저장소 자체는 현재 `project/` 아래에 없으므로 그 release 설정·pin 파일의 최신 상태는 여기서 확인하지 못했다.

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

## 5. Figma 플러그인 연동 상태

플러그인은 Backend URL(현재 시험값 `http://127.0.0.1:50065`), Figma File Key, **Robo Architect Figma 연동 화면에서 발급한 5분 일회용 연결 코드**가 필요하다. 코드 교환은 `/api/auth/figma-exchange`이고, 발급은 로그인한 사용자의 현재 프로젝트 권한을 검사하는 `/api/auth/figma-pair`다. 교환된 토큰은 Figma API와 지정 프로젝트 graph에만 사용할 수 있다. 화면의 “5분간 유효한 일회용 코드”는 입력된 코드가 아니라 placeholder다.

직전에는 플러그인이 `Connecting to ...`에서 멈추고 백엔드에 요청 자체가 도착하지 않았다. 현재 소스 `e4b4567`은 요청을 Figma 플러그인 메인 스레드의 Fetch API로 전달하고, 코드가 비었을 때 즉시 안내하도록 수정·푸시했으며 플러그인 번들 빌드는 통과했다. **실제 Figma에서 재연결 성공은 아직 확인되지 않았다.** 개발 플러그인을 다시 불러오고 새 코드를 발급해 입력한 뒤 `/api/figma-plugin/status` 도착 여부를 확인해야 한다. Electron 재시작만으로 Figma 개발 플러그인의 로드된 코드가 자동 교체되지는 않는다. `50065`도 고정 계약이 아니므로 다음 실행에서는 `docker-state.json`/백엔드 포트를 다시 확인한다.

## 6. 안전한 재현·릴리스 체크리스트

1. 각 독립 저장소의 브랜치·SHA·dirty 상태, Architect gitlink SHA를 기록한다. 필요한 변경은 각 저장소에 커밋·푸시한 뒤 상위 gitlink를 갱신한다.
2. release 입력 pin과 결과 `runtime-manifest.json`의 `source`, 이미지 태그·ID, 환경 스냅샷 checksum을 대조한다. **브랜치 이름보다 SHA가 실제 실행 근거다.**
3. 새 unpacked 디렉터리에서 실행하고 실제 `.exe` 경로, release ID, `docker-state.json` 포트, 백엔드 로그를 기록한다. 기존 앱/Compose의 무분별한 중복 기동은 피한다.
4. `/api/auth/provider` → 로그인 → 프로젝트 선택 → 프로젝트 graph 확인 → 두 C 파일만 새로 분석해 노드·관계·Navigator 범위 확인 → 문서 BPM/Rule 매핑/승격 순으로 검증한다.
5. Figma는 플러그인 재로드, 새 연결 코드 발급, 교환·status 요청 도착 및 지정 프로젝트 graph 권한을 별도로 검증한다.
6. 첫 Legacy 진입 지연은 Catalog 전체 graph 요청의 구간별 시간을 기록해 성능 이슈로 추적한다. 기능 성공과 성능 개선을 하나의 완료 판정으로 합치지 않는다.

주요 근거: `desktop/src/main/docker-stack.ts`, `desktop/src/main/backend.ts`, `desktop/runtime/compose.yml`, `desktop/out/dist-figma-pair/win-unpacked/resources/runtime/runtime-manifest.json`, `api/platform/identity/auth_guard.py`, `api/features/auth/router.py`, `.gitmodules`, 각 저장소의 2026-09-23 로컬 `HEAD`.
