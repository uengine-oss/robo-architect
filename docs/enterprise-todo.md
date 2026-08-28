# 기업 납품 — 남은 작업

> 대상: Robo Architect `enterprise-custom-p`
> 기준 소스: MSAez Platform `release/v1.0.30`, `local-msaez/platform/.../DocumentTemplate.vue`
> 최종 갱신: 2026-08-27
> 완료 항목: `enterprise-done.md`

## 0. 적용 원칙

- MSAez 코드를 그대로 복사하지 않고 Robo Architect의 Electron·Vue·FastAPI·Neo4j 구조에 맞게 구현한다.
- 기업 전용 설정은 환경 변수와 정책 설정으로 분리해 공통 제품 기능을 오염시키지 않는다.
- 인증·보안은 프런트엔드 화면 숨김이 아니라 Backend API에서 강제한다.
- AI 생성 실패가 전체 Workflow와 기존 생성 데이터를 훼손하지 않도록 단계별 실패를 격리한다.
- 근거 없는 값을 지어내지 않는다. "생성 실패"와 "해당 없음"을 구분해 표기한다.
- 모든 작업은 기능 테스트뿐 아니라 권한 우회·데이터 혼합을 방지하는 회귀 테스트를 포함한다.

## 1. 우선순위 요약

| ID | 항목 | 우선순위 | 상태 |
|---|---|---|---|
| ENT-DOC-003 | DOCX 정본화 실변환 검증 | P0 | 구현 완료 / **검증 대기** |
| ENT-AUTH-001 | 사내 SSO 인증 연동 | P0 | **부분 완료** — 설정 구조·SWP 클라이언트 |
| ENT-AUTH-002 | 사용자 승인 및 활성화 관리 | P0 | 미착수 |
| ENT-AUTHZ-001 | 프로젝트·세션·Proposal 접근 제어 | P0 | 미착수 |
| ENT-AUTHZ-002 | CORS와 신뢰 경계 강화 | P0 | **부분 완료** — 콜백 Allowlist |
| ENT-SEC-001 | 코드·소스 노출 정책 | P0 | 미착수 |
| ENT-SEC-002 | 비밀정보와 로그 보호 | P0 | 미착수 |
| ENT-AI-001 | 구조화 응답 잘림·파싱 실패 복구 | P0 | 미착수 |
| ENT-AI-002 | ES 추적성 실패 격리 | P0 | 미착수 |
| ENT-AI-003 | 빈 핵심 요소 완료 Gate | P0 | 미착수 |
| ENT-AI-004 | 저장 결과 복원 안정화 | P0 | 미착수 |
| ENT-AI-005 | 사용자 친화적 오류 전달 | P0 | **부분 완료** |
| ENT-AI-006 | User Story ID 정규화 | P0 | 미착수 |
| ENT-AUDIT-001 | 생성 Job 실행 문맥 기록 | P0 | 미착수 |
| ENT-AUDIT-002 | 중요 행위 감사 로그 | P0 | 미착수 |
| ENT-DOC-002 | 설계 결정 근거 영속화 | P1 | **부분 완료** |
| ENT-DOC-004 | 기업 문서 메타데이터 | P1 | 미착수 |
| ENT-SEC-003 | 의존성 및 SBOM 관리 | P1 | 미착수 |
| ENT-SEC-004 | 동적 실행 및 입력 검증 점검 | P1 | 미착수 |
| ENT-UX-001 | 인증 상태별 화면 처리 | P2 | 미착수 |
| ENT-UX-002 | 프로필 및 관리자 메뉴 | P2 | 미착수 |

## 2. 즉시 처리 — 검증 대기

### ENT-DOC-003 DOCX 정본화 실변환 검증

구현은 끝났고 LibreOffice가 있는 환경에서의 실제 변환만 남았다. 개발 머신에 LibreOffice가 없어 미검증 상태다.

**설치**

```
Debian/Ubuntu: apt-get install libreoffice-writer fonts-nanum
macOS:         brew install --cask libreoffice
```

`fonts-nanum`은 한글 폰트 대체·메트릭 안정화용이다. macOS 앱 번들 경로는 자동 탐지하며, PATH에 없으면 `LIBREOFFICE_BIN`으로 지정한다.

**검증 절차**

1. `GET /api/deliverables/docx-normalization/status` → `available: true` 확인
2. 설계 산출물을 Word로 내보내기 → 정본화 성공 스낵바 확인
3. 산출물을 `POST /api/deliverables/docx-normalization/inspect`에 넣어 `ecmCompatible: true` 확인
4. 응답 헤더 `X-Docx-Lossless`가 `true`인지 확인 (`false`면 `X-Docx-Losses`에 유실 항목)
5. Microsoft Word에서 열어 한글 글꼴·표·머리말·페이지 번호·이미지 유지 확인
6. 고객사 ECM에 실제 업로드 → 등록·미리보기·다운로드 확인

**완료 조건**

- 생성 DOCX가 Word와 ECM에서 오류 없이 열린다.
- 정본화 과정에서 텍스트·표·이미지가 유실되지 않는다.
- 변환 실패가 빈 파일이나 성공 응답으로 반환되지 않는다. *(코드상 보장됨 — 빈 결과는 예외 처리)*

## 3. P0 — 인증·권한·보안

### ENT-AUTH-001 사내 SSO 인증 연동 *(부분 완료)*

**완료:** POSCO SWP SSO 설정 구조와 클라이언트. `AUTH_PROVIDER` provider 전략(기본 `none` = 기존 헤더 동작 유지), SWP redirect/검증 흐름, CSV 응답 파서(현장 필드 드리프트 대응 포함), 콜백 Allowlist. 상세는 `enterprise-done.md` §7.4.

**남은 작업**

- **세션/JWT 발급.** 현재 `/api/auth/sso/valid`는 신원 확인 결과만 반환한다. 토큰 발급과 이후 요청 인증이 없다. 사용자 저장소 설계(ENT-AUTH-002)가 선행돼야 한다.
- **Electron 연동.** Desktop이 SSO 왕복을 어떻게 처리할지(외부 브라우저 vs BrowserWindow, 콜백 수신 방식) 결정이 필요하다.
- **기존 헤더 경로 차단.** 기업 모드에서 `X-User-*` 헤더만으로 접근할 수 없게 막아야 한다. 현재는 `AUTH_PROVIDER=swp`여도 헤더 경로가 살아 있다.
- **현장 첫 연동 시 필드 확인.** `isValidSSO` 실제 응답의 필드 순서를 한 번 확인해 `SWP_IDX_*`를 맞춰야 한다. 이메일·영문성명은 인덱스 비의존이라 대개 손댈 필요 없지만, 부서명은 인덱스에 의존한다.
- 고객사 SSO와 연동할 인증 Adapter를 추가한다. 개발·개인 실행은 기존 Git Identity Provider 전략을 유지한다.
- 기업 모드에서는 신뢰할 수 있는 SSO 토큰 또는 인증 프록시 결과만 사용자 신원으로 인정한다.
- 사용자 식별자는 이메일이 아니라 사번 등 변경 가능성이 낮은 사내 고유 ID를 쓴다.
- 로그인 후 이름·이메일·사번·소속·역할을 정규화된 Session User로 변환한다.

**대상:** `desktop/src/main/launcher/identity.ts`, `desktop/src/main/launcher/ipc-handlers.ts`, `frontend/src/app/http.js`, `api/platform/identity/`, `api/main.py`, 신규 `api/features/auth/`

**검증 기준**

- 정상 SSO 사용자는 Desktop 진입과 Backend 호출에 성공한다.
- 위조한 `X-User-*` 헤더만으로 기업 모드 API에 접근할 수 없다.
- 만료·변조 토큰은 401로 거부된다.
- 동일 이메일의 다른 인증 공급자 정보가 기존 사내 ID를 덮어쓰지 않는다.
- 로그아웃·세션 만료 후 보호 API 호출이 차단된다.

### ENT-AUTH-002 사용자 승인 및 활성화 관리

- 사용자 상태를 `PENDING` / `ACTIVE` / `DISABLED` / `REJECTED`로 관리한다.
- 관리자 목록은 환경 변수 또는 초기 Bootstrap 정책으로 지정한다.
- 승인 전 사용자의 설계·코드·산출물 API 접근을 전면 차단한다.
- 관리자용 사용자 목록 조회·승인·비활성화 화면과 API를 제공한다.
- 사용자가 자신의 역할을 관리자 등급으로 변경할 수 없게 한다. 관리자 역할이 재로그인 시 기본 역할로 덮어써지지 않게 한다.

**검증 기준**

- 승인 대기 사용자는 승인 안내 화면만 볼 수 있다.
- 비활성화된 사용자의 기존 세션도 재검증 시 차단된다.
- 자가 승인·자가 관리자 승격 요청은 403으로 거부된다.
- 최소 한 명의 Bootstrap 관리자를 안전하게 생성할 수 있다.

### ENT-AUTHZ-001 프로젝트·세션·Proposal 접근 제어

- `Project`, Hybrid Ingestion Session, Proposal, Change, ImplementationFile에 소유 프로젝트와 사용자 범위를 부여한다.
- 프로젝트 역할을 `OWNER` / `EDITOR` / `VIEWER`로 구분한다.
- 모든 조회·생성·수정·삭제 API에서 프로젝트 접근 권한을 검증한다.
- Proposal·Sandbox는 원본 Project 권한을, 파생 ES 결과와 산출물은 원본 Session/Project 권한을 상속한다.
- 목록 API는 허용된 프로젝트만 반환한다. Node ID·Proposal ID 조작으로 다른 프로젝트에 접근하는 IDOR를 차단한다.

**대상:** `api/platform/identity/`, `api/features/contexts/`, `api/features/ingestion/`, `api/features/proposal_lifecycle/`, `api/features/requirement_changes/`, `api/features/claude_code/`, `api/features/deliverables/`

**검증 기준**

- 다른 사용자의 ID를 알아도 해당 프로젝트를 조회·변경할 수 없다.
- 파생 모델과 Proposal이 원본 프로젝트보다 넓은 권한을 갖지 않는다.
- Context 전체 목록에서 권한 없는 프로젝트 데이터가 노출되지 않는다.

> **선행 완료:** 산출물 조회는 이미 Session 범위로 고정돼 있다(ENT-DOC-001). 여기에 사용자 권한 검증만 얹으면 된다.

### ENT-AUTHZ-002 CORS와 신뢰 경계 강화 *(부분 완료)*

**완료:** SSO 콜백 URL Allowlist(`AUTH_CALLBACK_ALLOWLIST`). 목록이 비면 loopback만 허용한다.

**남은 작업**

- 현재 Backend의 `allow_origins=["*"]`를 기업 모드에서 허용 도메인 목록으로 제한한다.
- Desktop Loopback, Figma Plugin, 승인된 사내 Frontend Origin을 구분한다.
- 사용자 신원 헤더는 신뢰 가능한 Electron Main 또는 Reverse Proxy가 부여한 경우에만 인정한다.
- 외부 노출 시 TLS 종료 위치와 Proxy Header 신뢰 범위를 설정한다.
- Redirect URL을 Allowlist로 검증해 Open Redirect를 방지한다.

### ENT-SEC-001 코드·소스 노출 정책

- Code 탭과 소스 파일 미리보기 사용 여부를 정책으로 설정할 수 있게 한다.
- 프런트엔드 버튼만 숨기지 않고 파일 읽기 API와 Electron IPC에서 정책을 강제한다.
- Claude Code 터미널·파일 탐색·코드 미리보기·아카이브 다운로드를 별도 권한으로 구분한다.
- 다운로드 허용 시 감사 로그와 워터마크 또는 파일 Manifest를 남긴다.

**검증 기준**

- 제한 사용자는 URL·IPC 직접 호출로 파일 내용을 가져올 수 없다.
- 터미널 제한 정책이 있으면 PTY 세션 생성과 재접속도 차단된다.
- 허용된 다운로드는 사용자·프로젝트·시간·파일 범위와 함께 기록된다.

### ENT-SEC-002 비밀정보와 로그 보호

- `.env`의 API Key, DB Password, SSO Secret을 기업 Secret Manager로 이동한다.
- 요청·응답·예외 로그에서 Token, Password, Cookie, 원문 소스, 개인정보를 마스킹한다.
- AI Prompt 전문 저장 여부를 정책으로 제어한다.
- 빈 `catch` / `except` 블록을 찾아 구조화 로그를 남긴다.
- 로그 보존 기간과 관리자 열람 권한을 설정한다.

## 4. P0 — AI Workflow 안정화

### ENT-AI-001 구조화 응답 잘림·파싱 실패 복구

- JSON 응답의 종료 여부와 필수 필드를 검사한다.
- 출력 토큰 한도 도달 응답을 일반 파싱 오류와 구분한다.
- 대형 결과는 BC·Aggregate·문서 구간 단위로 분할 생성한다.
- 안전한 복구가 가능한 경우에만 복구하고, 의미가 유실된 응답은 재시도한다.
- 재시도 후에도 실패하면 완료된 이전 단계는 유지하고 실패 단계부터 재실행할 수 있게 한다.

**검증 기준**

- 중간에서 잘린 JSON을 성공 결과로 저장하지 않는다.
- 재시도 시 동일 노드가 중복 생성되지 않는다.
- 부분 실패 후 전체 문서 업로드부터 다시 시작하지 않아도 된다.

### ENT-AI-002 ES 추적성 실패 격리

- `traceMap`, `previewAttributes`, 출처 Reference가 없을 때 기본 빈 구조로 정규화한다.
- 추적성 추출 실패를 ES 핵심 노드 생성 실패와 분리한다.
- User Story·BC·Aggregate·Command·Event 생성이 끝났으면 추적성만 `PARTIAL`로 표시한다.
- 추적성만 별도로 재생성할 수 있게 한다.

### ENT-AI-003 빈 핵심 요소 완료 Gate

- Workflow 완료 전 BC별 Aggregate·Command·Event·관계의 최소 조건을 검사한다.
- Aggregate가 없거나 이름만 있고 하위 요소가 비면 경고한다.
- 누락을 `ERROR` / `WARNING` / `INFO`로 구분하고, 보완 생성·직접 수정·예외 승인 중 하나를 선택하게 한다.
- 승인한 예외는 사유와 사용자 정보를 기록한다.

> **참고:** 산출물 준비도 지표는 이미 `verify_pipeline_status()`가 제공한다(ENT-DOC-001 참조). 이 Gate는 그 지표를 생성 완료 시점에 강제하는 작업이다.

### ENT-AI-004 저장 결과 복원 안정화

- 저장된 BC 선택지, 선택 Index, 생성 옵션을 함께 복원한다.
- 일부 선택지가 누락된 이전 데이터도 기본값으로 마이그레이션한다.
- 탭 전환 시 존재하지 않는 선택지를 참조하지 않도록 방어한다.
- Workflow 중간 저장 데이터에 스키마 버전을 추가한다.

### ENT-AI-005 사용자 친화적 오류 전달 *(부분 완료)*

**완료:** 인증 오류(401/403)를 재시도 불가로 분류해 즉시 중단하고 `error_type`과 함께 로깅한다.

**남은 작업**

- AI Provider 오류, 사용량 한도, Timeout, JSON 파싱, 스키마 검증, DB 저장 오류를 분류한다.
- Backend가 `errorCode`, `message`, `retryable`, `stage`, `requestId`를 반환한다.
- Frontend가 원인·영향 범위·재시도 가능 여부·사용자 조치를 표시한다.
- Prompt, 전체 Draft, Stack Trace는 일반 사용자 팝업에 노출하지 않는다.

**검증 기준**

- `Unknown error occurred`만 표시되는 실패 경로가 없다.
- 동일 오류를 Request ID로 Backend 로그에서 찾을 수 있다.
- 재시도 불가능한 오류에는 반복 실행 버튼을 제공하지 않는다.

### ENT-AI-006 User Story ID 정규화

- `US-FR-001`, `US-NFR-001`, 프로젝트 접두사 포함 ID를 모두 지원한다.
- User Story ID 파싱 로직을 공통 모듈로 통합한다.
- 추적성·문서 출력·Text Chunking·설계 연결이 같은 규칙을 쓰게 한다.
- 대소문자·공백·잘못된 형식 처리 기준을 정의한다.

**검증 기준**

- 접두사 유무와 관계없이 추적성이 생성된다.
- 문서 Chunk와 ES 요소가 동일한 User Story ID를 가리킨다.
- 잘못된 ID는 묵시적으로 다른 Story에 연결하지 않고 미매핑으로 남긴다.

> **관측:** 문서 경로는 `US-001`, 청킹 경로는 `US-{chunk}-{n}` 형식을 쓴다. 두 체계가 공존하므로 통합 시 기존 데이터 마이그레이션 여부를 함께 판단해야 한다.

## 5. P0 — AI Job·감사 추적

### ENT-AUDIT-001 생성 Job 실행 문맥 기록

모든 AI 생성 작업에 Job ID, 요청 사용자 ID, Project ID, Session/Proposal ID, Workflow와 Stage, AI Provider와 Model, 시작·종료 시각, 성공·실패·취소 상태, Token 사용량, Request ID와 오류 코드를 기록한다.

- SSE 연결 종료와 실제 Backend Job 종료를 구분한다.
- 관리자가 프로젝트별 실행 내역과 실패율을 조회할 수 있게 한다.

**검증 기준**

- 익명 사용자 또는 프로젝트 없는 기업 모드 Job을 시작할 수 없다.
- 모든 AI 호출을 사용자와 프로젝트까지 역추적할 수 있다.
- 클라이언트가 종료돼도 Backend Job의 최종 상태가 기록된다.

### ENT-AUDIT-002 중요 행위 감사 로그

- 로그인, 승인, 비활성화, 프로젝트 공유, 문서 업로드, ES 승격, Proposal Accept, 코드 다운로드, 산출물 생성을 기록한다.
- Append-only 정책을 적용한다.
- 관리자 조회 API에 기간·사용자·프로젝트·행위 필터를 제공한다.
- 민감 데이터 원문 대신 대상 ID와 변경 요약을 기록한다.

**검증 기준**

- 중요 행위마다 actor, target, action, result, timestamp가 남는다.
- 일반 사용자가 감사 로그를 수정·삭제할 수 없다.
- 실패한 권한 우회 시도도 감사 대상에 포함된다.

## 6. P1 — 산출물 보완

### ENT-DOC-002 설계 결정 근거 영속화 *(부분 완료)*

기준 템플릿 8개 섹션은 모두 출력된다. 남은 것은 **최종 결과가 아니라 그 결정에 이른 근거**다. 현재 데이터 모델에 해당 필드가 없어 새 영속화가 필요하다.

**Bounded Context 정의**

- BC 분해 기준과 선택지, 분해 이유를 별도 데이터로 영속화한다.
- BC별 책임, 핵심 용어, 소유 조직, 중요도(Core/Supporting/Generic), 구현 전략 필드를 추가한다.
- BC 간 관계 유형(Partnership, Customer-Supplier, ACL)과 통신 방식(동기 API, 이벤트, 배치)을 명시한다.
- Cross-BC Policy 유무와 무관한 전체 Context Map을 제공한다. *(현재는 Policy가 있는 관계만 그려진다)*

**Aggregate 설계**

- Aggregate별 책임과 트랜잭션 경계 설명을 추가한다.
- Invariant를 경계 결정 근거와 연결한다.
- 대안이 실제 생성되는 경우 선택·폐기 사유를 영속화한다. 대안 생성이 없다면 기준 템플릿을 "최종 설계 및 결정 근거" 형식으로 조정한다.

**Aggregate 상세**

- 기준 템플릿의 Entity 모델과 Robo Architect의 Aggregate Property 모델이 완전히 같지 않다. 별도 Entity가 필요하면 정규화된 Entity/Property 관계를 추가한다.
- Foreign Key가 어떤 대상 필드를 참조하는지 명시한다. *(현재 `isForeignKey` 플래그만 있고 대상이 없다)*

**API 명세**

- 응답 오류 코드와 인증 정책은 그래프에 근거가 없어 규칙으로 도출할 수 없다. 기준 템플릿이 요구하지 않으므로 커버리지 영향은 없으나, 고객사 API 표준 연계 시 별도로 다룬다.
- OpenAPI 또는 고객사 표준 명세 형식과의 연결도 이때 함께 검토한다.

**산출물 상태 표기**

각 섹션·필드에 다음 상태를 둔다. 빈 문자열이나 `-`로만 표시하면 "해당 없음"과 "생성 실패"를 구별할 수 없다.

| 상태 | 의미 |
|---|---|
| 확정 | 사용자 검토 또는 승인 완료 |
| 자동 생성 | AI가 생성했으나 미승인 |
| 추론 | 상위 구조 또는 간접 근거로 연결 |
| 미매핑 | 연결 근거를 찾지 못함 |
| 미지원 | 현재 파이프라인에서 만들지 않음 |

> API 계약과 추적성에는 `provenance` 필드로 이미 적용돼 있다. 나머지 섹션으로 확대하는 작업이 남았다.

### ENT-DOC-004 기업 문서 메타데이터

- 문서번호, 프로젝트명, 버전, 보안등급, 작성자, 검토자, 승인자를 설정한다.
- 표지·머리말·바닥글·파일명 규칙을 Template 설정으로 분리한다.
- 기업 로고와 명칭은 배포 설정으로 주입하고 공통 소스에 하드코딩하지 않는다.
- 문서 변경 이력과 승인 Snapshot 정보를 포함한다.

**검증 기준**

- 기업 설정을 끄면 공통 Robo Architect 문서 형식으로 돌아간다.
- 서로 다른 고객 설정이 같은 빌드에서 섞이지 않는다.

## 7. P1 — 공급망·취약점 관리

### ENT-SEC-003 의존성 및 SBOM 관리

- Python, npm, Electron, Container Image를 대상으로 취약점 검사를 수행한다.
- 사용하지 않는 패키지·서비스·서브모듈을 식별한다.
- 납품 버전은 Lockfile과 Container Digest로 고정한다.
- CycloneDX 또는 SPDX 형식의 SBOM을 생성한다.
- Critical·High 취약점의 배포 차단 기준과 예외 승인 절차를 정의한다.

### ENT-SEC-004 동적 실행 및 입력 검증 점검

- `eval`, 동적 코드 실행, Shell 조합, URL Redirect 사용 지점을 전체 검색한다.
- 좌표·설정·JSON 문자열은 안전한 Parser와 스키마 검증을 사용한다.
- 파일 경로를 Project Root 범위로 제한한다.
- Shell 명령을 허용된 작업과 인자 구조로 제한한다.

**검증 기준**

- 외부 입력이 코드로 평가되지 않는다.
- Path Traversal과 Command Injection 테스트를 통과한다.
- 잘못된 입력은 4xx와 구조화 오류로 종료된다.

## 8. P2 — 사용자 경험

### ENT-UX-001 인증 상태별 화면 처리

- 401을 일반 네트워크 오류가 아니라 로그인·세션 만료 안내로 처리한다.
- 미로그인 상태에서 보호된 목록 요청을 반복 호출하지 않는다.
- 승인 대기, 비활성화, 권한 부족을 서로 다른 화면으로 제공한다.
- 인증 완료 후 원래 접근하려던 프로젝트로 안전하게 복귀한다.

### ENT-UX-002 프로필 및 관리자 메뉴

- 프로필에 이름, 사번, 소속, 역할, 승인 상태를 정확히 표시한다.
- 관리자에게만 사용자 관리 메뉴를 노출한다.
- 메뉴 클릭·열림·닫힘 동작을 Desktop과 Web 모드에서 검증한다.

## 8.5 P-GPT 전환 시 확인 항목

설정 구조는 완료됐다(`enterprise-done.md` §7.4). 실제 전환 시 확인할 것.

- **임베딩 키 필수.** `OPENAI_BASE_URL`을 P-GPT로 지정하면서 `EMBEDDING_API_KEY`를 빼면 임베딩이 P-GPT로 따라가 깨진다. `GET /api/auth/provider`의 `embeddings.sharesChatEndpoint`가 `true`면 이 상태다.
- **모델명 교체.** `LLM_MODEL`을 P-GPT가 제공하는 모델명으로 바꿔야 한다.
- **컨텍스트 상한.** P-GPT의 컨텍스트가 좁으면 `LLM_MAX_OUTPUT_TOKENS`로 출력 상한을 낮춘다. 기존 코드가 `max_tokens=32768`(GPT-4.1 기준)을 넘기는 지점이 있다.
- **네트워크 도달성.** API 서버가 `aigpt.posco.net` / `taigpt.posco.net`에 접근 가능해야 한다(hosts/DNS).
- **Skill Runner는 별도 설정.** `SKILL_RUNNER_*`는 `LLM_*`와 독립이다. Proposal·DDD 스킬 실행 경로도 함께 전환할지 판단해야 한다.

## 9. 백로그 — 우선순위 미정

- **추적성 추론 매핑 노이즈.** 상위 Aggregate 매핑을 상속하는 요소가 최대 9개 User Story에 붙는다. 기준 템플릿과 동일한 동작이고 별도 섹션으로 분리돼 있으나, 실제 납품 문서에서 노이즈로 판단되면 상속 깊이 제한을 검토한다.
- **PPT 내보내기 섹션 반영.** 현재 DOCX만 쓰므로 주석 처리 상태다. 되살릴 경우 밸류 스트림·추적성·Endpoint 계약 섹션을 PPT 경로에도 추가해야 한다.
- **Skill Runner 환경 전환 편의.** 사내 GPU ↔ 클라우드 전환이 `.env` 4줄 직접 수정이다. Analyzer처럼 config 프로파일 방식으로 정리할지 판단한다.
- **기준 저장소의 노출된 자격증명.** `local-msaez/platform/docker-compose.yml`에 OpenAI API Key, Gitea OAuth client secret, Gitea 토큰이 평문으로 커밋돼 있다. 우리 저장소로 옮기지 않았으나, 해당 키들이 아직 유효하다면 폐기가 필요하다. (ENT-SEC-002 범위)

## 10. 적용하지 않기로 한 항목

- MSAez의 제거된 Java Gateway — Robo Architect에 동일 구성요소가 없다.
- Vue 2·Vuetify 기반 메뉴 수정 — 현재 Vue 3 UI에 그대로 옮기지 않는다.
- Gitea·GitLab 로그인 전용 분기 — 사내 SSO Provider 전략으로 대체한다.
- MSAez의 Acebase·Postgres 사용자 저장 코드 — Robo Architect 사용자 저장소 설계로 대체한다.

## 11. 정책 확인 후 진행할 항목

- 익명 읽기 허용 여부
- 코드 미리보기와 Claude Code 터미널 허용 범위
- 소스 아카이브 다운로드 허용 여부
- 외부 AI 사용 허용 여부
- Figma·Confluence 외부 연결 허용 여부
- 감사 로그와 AI Prompt 보존 기간
- ECM에서 요구하는 DOCX 정본화 규칙

## 12. 권장 구현 순서

1. **ENT-DOC-003 실변환 검증** — LibreOffice 설치 후 즉시 (가장 저비용)
2. 기업 모드 설정과 사용자·프로젝트 데이터 모델 정의
3. SSO 인증과 승인 상태 처리 (ENT-AUTH-001/002)
4. Backend 프로젝트 인가 공통 Dependency 적용 (ENT-AUTHZ-001)
5. CORS·신원 헤더·Redirect 신뢰 경계 강화 (ENT-AUTHZ-002)
6. AI Job 문맥과 감사 로그 추가 (ENT-AUDIT-001/002)
7. JSON 잘림·추적성 실패·빈 모델 Gate 보완 (ENT-AI-001/002/003)
8. User Story ID와 저장 결과 복원 회귀 수정 (ENT-AI-004/006)
9. 코드·터미널·다운로드 정책 적용 (ENT-SEC-001)
10. 설계 결정 근거 영속화 (ENT-DOC-002)
11. 기업 문서 메타데이터 (ENT-DOC-004)
12. SBOM·취약점·침투 테스트 (ENT-SEC-003/004)

## 13. 전체 완료 조건

- 기업 모드에서 미인증·미승인 사용자의 모든 보호 기능 접근이 차단된다.
- 프로젝트와 파생 데이터에 사용자별 권한이 일관되게 적용된다.
- ~~문서 업로드부터 BPM·Event Storming·산출물 생성까지 전체 Workflow가 정상 수행된다.~~ **(완료)**
- AI 응답 잘림과 추적성 실패가 감지되며 복구 또는 부분 완료로 처리된다.
- 모든 AI Job과 중요 사용자 행위를 사용자·프로젝트 기준으로 추적할 수 있다.
- 코드와 민감정보가 설정된 기업 정책보다 넓게 노출되지 않는다.
- ~~Session 또는 Project 단위로 재현 가능한 DOCX 산출물이 생성된다.~~ **(완료 — ECM 실등록 검증만 남음)**
- ~~요구사항부터 설계 요소까지의 추적성 및 미매핑 상태가 산출물에 포함된다.~~ **(완료)**
- 인증·인가·입력 검증·데이터 격리에 대한 자동 회귀 테스트를 통과한다.
- 납품 구성요소의 버전표, SBOM, 설치·운영·장애 대응 문서가 준비된다.

## 14. 원본 변경사항 추적표

| MSAez v1.0.30 변경 | 작업 ID | 상태 |
|---|---|---|
| `e731fb30` User Story 접두사 없는 ID 지원 | ENT-AI-006 | 미착수 |
| `1183fe8a`, `ce9b52e2`, `f86c96b4` ES 추적성 실패 방어 | ENT-AI-002, ENT-AI-005 | 부분 |
| `77f08961` 빈 Aggregate 알림 | ENT-AI-003 | 미착수 |
| `e45de4b6` AI 오류 원인 전달 | ENT-AI-005 | 부분 |
| `66631483` 저장 BC 선택지 복원 | ENT-AI-004 | 미착수 |
| `031314bc`, `035b0b82` 온프레미스 코드 노출 및 인증 | ENT-SEC-001, ENT-AUTH-001 | 미착수 |
| `ff9edb45`, `7e4e9595`, `9c598385`, `035935dc` API 인가 | ENT-AUTHZ-001/002 | 미착수 |
| `d95acc18`, `142a9200`, `33e95c69`, `e21cf08c` SSO·비로그인 처리 | ENT-AUTH-001, ENT-UX-001 | 미착수 |
| `da1f6873`, `376f6366`, `0e3fcdbb` 승인·관리자 관리 | ENT-AUTH-002, ENT-UX-002 | 미착수 |
| `3e5a5b59` AI Job 요청자·프로젝트 기록 | ENT-AUDIT-001 | 미착수 |
| `dcc4c77c` LibreOffice DOCX 정본화 | ENT-DOC-003 | **구현 완료** |
| `70c0b123`, `843543f0`, `a0491a39`, `9381f459` 취약점·안전한 실행·로깅 | ENT-SEC-002~004 | 미착수 |
