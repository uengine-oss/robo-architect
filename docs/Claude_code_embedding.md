# Claude Code Embedding in Robo Architect

## 개요

Robo Architect 플랫폼에 Claude Code CLI를 웹 터미널(TUI)로 임베딩하여, 이벤트 스토밍 → PRD 생성 이후 **플랫폼을 떠나지 않고** 바로 코드 생성 작업을 수행할 수 있도록 한다.

### 사용자 플로우

```
요구사항 문서 업로드
    ↓
이벤트 스토밍 모델 생성 (Neo4j)
    ↓
PRD 생성 (CLAUDE.md, specs/, .claude/agents/ 등)
    ↓
[Claude Code] 버튼 클릭
    ↓
터미널 뷰에서 생성된 PRD를 기반으로 Claude Code 실행
    ↓
플랫폼 내에서 코드 생성 · 수정 · 확인
```

기존 방식(PRD를 ZIP으로 다운로드 → 로컬에서 Cursor/Claude Code로 작업)도 여전히 지원한다. 임베딩은 **대안 경로**로 제공되며, PRD 생성 파이프라인 자체는 변경하지 않는다.

---

## 현재 구현 상태

### 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│  Browser (Vue 3)                                        │
│                                                         │
│  TopBar: [문서 업로드] [PRD 생성] [Claude Code] [설정]    │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │  ClaudeCodeTerminal.vue                           │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │  xterm.js (Terminal Emulator)               │  │  │
│  │  │  - xterm-256color / truecolor               │  │  │
│  │  │  - FitAddon (자동 리사이즈)                   │  │  │
│  │  │  - WebLinksAddon (URL 클릭)                  │  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  └──────────────────────┬────────────────────────────┘  │
│                         │ WebSocket                     │
└─────────────────────────┼───────────────────────────────┘
                          │
┌─────────────────────────┼───────────────────────────────┐
│  Backend (FastAPI)      │                               │
│                         ▼                               │
│  /api/claude-code/terminal (WebSocket endpoint)         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  PTY Bridge                                     │    │
│  │  - pty.openpty() → master/slave FD              │    │
│  │  - os.fork() → child process                    │    │
│  │  - TIOCSWINSZ ioctl (리사이즈)                    │    │
│  │  - Non-blocking async read loop                 │    │
│  └──────────────────────┬──────────────────────────┘    │
│                         │                               │
│                         ▼                               │
│              claude CLI (PTY session)                   │
│              (fallback: $SHELL)                         │
└─────────────────────────────────────────────────────────┘
```

### 프론트엔드 구조

| 파일 | 역할 |
|------|------|
| `frontend/src/app/layout/TopBar.vue` | "Claude Code" 버튼 (PRD 생성 오른쪽) |
| `frontend/src/App.vue` | `'Claude Code'` 탭 — 선택 시 Navigator/Canvas 숨기고 터미널 전체 표시 |
| `frontend/src/features/claudeCode/ui/ClaudeCodeTerminal.vue` | xterm.js 터미널 컴포넌트 |

**탭 전환 방식**: 기존 `activeTab` 상태 관리에 `'Claude Code'`를 추가. Vue의 `<KeepAlive>`로 탭 전환 시에도 터미널 세션 유지.

**UI 동작**:
- Claude Code 탭 활성화 시: Navigator 패널, Resizer, Canvas/BigPicture/Aggregate 패널이 모두 숨겨지고 터미널이 전체 영역을 차지
- 다른 탭으로 전환 시: 터미널 세션은 KeepAlive로 유지되며 기존 UI 복원

### 백엔드 구조

| 파일 | 역할 |
|------|------|
| `api/features/claude_code/__init__.py` | 모듈 초기화 |
| `api/features/claude_code/router.py` | WebSocket PTY 브릿지 + 디렉토리 탐색 + 프로젝트 설정 API |
| `api/main.py` | 라우터 등록 (`/api/claude-code/*`) |

### API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `WS` | `/api/claude-code/terminal?workdir=<path>` | PTY 터미널 세션 (workdir 지정 가능) |
| `GET` | `/api/claude-code/browse-directory?path=<path>` | 서버 디렉토리 탐색 (폴더 피커용) |
| `POST` | `/api/claude-code/setup-project` | PRD 생성 → 지정 경로에 파일 추출 |

---

## 세부 기술 사항

### 1. WebSocket 프로토콜

**클라이언트 → 서버** (JSON):

```json
// 키 입력
{"type": "input", "data": "<keystrokes>"}

// 터미널 리사이즈
{"type": "resize", "cols": 120, "rows": 40}
```

**서버 → 클라이언트**: raw text (터미널 ANSI escape 시퀀스 포함)

### 2. PTY 세션 관리

- Python 표준 라이브러리 `pty.openpty()`로 master/slave FD 생성
- `os.fork()`로 자식 프로세스 생성, slave FD를 stdin/stdout/stderr로 연결
- 자식 프로세스에서 `claude` CLI 실행 (없으면 `$SHELL` fallback)
- master FD를 non-blocking으로 설정하여 asyncio 루프에서 읽기
- 리사이즈: `TIOCSWINSZ` ioctl + `SIGWINCH` 시그널

### 3. 프로세스 라이프사이클

```
WebSocket 연결
    ↓
PTY 생성 + fork
    ↓
claude CLI 실행 (TERM=xterm-256color)
    ↓
양방향 데이터 전달 (input ↔ output)
    ↓
WebSocket 종료 시:
    1. read task 취소
    2. master FD close
    3. SIGTERM → child process
    4. waitpid (좀비 방지)
```

### 4. 터미널 UI 설정

- **테마**: Tokyo Night (dark)
- **폰트**: JetBrains Mono → Fira Code → Cascadia Code → Menlo 순 fallback
- **기능**: 커서 깜빡임, 5000줄 스크롤백, URL 클릭, 자동 리사이즈
- **연결 상태**: 헤더바에 초록/노랑/빨강 상태 표시 + 재연결 버튼

### 5. 의존성

**프론트엔드** (npm):
- `@xterm/xterm` — 터미널 에뮬레이터
- `@xterm/addon-fit` — 컨테이너에 맞춰 자동 리사이즈
- `@xterm/addon-web-links` — URL 감지 및 클릭

**백엔드** (Python 표준 라이브러리만 사용):
- `pty` — PTY 생성
- `fcntl`, `termios`, `struct` — PTY 제어
- `asyncio` — 비동기 I/O
- FastAPI WebSocket — 이미 사용 중

---

## PRD 연동 (구현 완료)

PRD 생성 모달에서 두 가지 경로를 제공한다:

### 경로 A: ZIP 다운로드 (기존)
PRD → Preview → Download ZIP → 로컬에서 Cursor/Claude Code 실행

### 경로 B: Claude Code에서 바로 열기 (신규)
```
PRD → Preview → Download ZIP
                     ↓
           프로젝트 경로 선택 (폴더 브라우저)
                     ↓
           "Claude Code에서 열기" 클릭
                     ↓
           POST /api/claude-code/setup-project
           → PRD 파일을 지정 경로에 추출
                     ↓
           추출 완료 확인 (파일 목록)
                     ↓
           "Claude Code 터미널 열기"
                     ↓
           모달 닫히고 → Claude Code 탭 활성화
           → WS /terminal?workdir=/resolved/path
           → claude CLI가 해당 디렉토리에서 실행
```

**폴더 브라우저**: `GET /api/claude-code/browse-directory` API로 서버 디렉토리를 탐색하여 프로젝트 경로를 시각적으로 선택할 수 있다. 상위 폴더 이동, 하위 폴더 진입, "이 폴더 선택", "여기에 프로젝트명 생성" 기능을 제공한다.

PRD 생성이 만들어내는 파일들(`CLAUDE.md`, `specs/`, `.claude/agents/` 등)은 Claude Code가 자동으로 인식하는 구조이므로, 워크스페이스에 배치하기만 하면 추가 설정 없이 동작한다.

---

## 향후 개선 사항

### 단기
- [ ] 다중 터미널 세션 지원
- [ ] 세션 복구 (새로고침 시 기존 PTY 세션 재연결)

### 중기
- [ ] 샌드박스 격리 환경 (Docker 기반 PTY)
- [ ] 파일 변경 사항 미리보기 / diff 뷰어
- [ ] 터미널 출력에서 생성된 파일 목록 자동 감지

### 장기
- [ ] 이벤트 스토밍 모델 변경 → 영향도 분석 → Claude Code 자동 수정 제안 파이프라인
- [ ] 생성된 코드의 이벤트 스토밍 모델 역추적 (traceability)
