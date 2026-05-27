# Quickstart: MCP Spec Bridge — manual smoke

생성: 2026-05-19 · Plan: [plan.md](plan.md)

전제: Robo Architect 백엔드 실행 `uvicorn api.main:app --reload --host 127.0.0.1 --port 8000`; Neo4j에 인제스트된 모델(BC·Feature·User Story·Aggregate) 존재; Claude Code CLI 설치; 신규 의존성 설치 `uv sync`(또는 `pip install mcp httpx`).

## S1 — 구현 커맨드 생성·설치 (US1)

1. Requirements 탭에서 Feature 노드를 선택하고 "구현 커맨드 생성"을 실행한다.
2. `GenerateCommandDialog`가 열리고, 대상 프로젝트 홈이 없으면 먼저 지정을 요구한다.
3. 프로젝트 홈 지정 후 → `.claude/commands/robo-implement.md`가 설치되고 `.mcp.json`에 `robo-architect` 항목이 등록된다.
4. 다이얼로그에 호출 문자열 `/robo-implement feature <featureId>`가 복사 가능하게 표시된다.
5. 같은 동작을 다시 실행해도 커맨드 파일·`.mcp.json` 항목이 **중복 누적되지 않는다**(멱등, FR-005).

## S2 — MCP 동적 스펙 전달 (US2)

1. 대상 프로젝트에서 Claude Code를 연다 — 슬래시 커맨드 목록에 `/robo-implement`가 보인다.
2. `/robo-implement feature <featureId>` 실행 → MCP 도구 `get_spec_bundle`이 호출되고, 그 Feature 범위의 PRD·DDD 구현 스펙이 응답으로 전달된다.
3. 프로젝트에 정적 스펙 `.md` 파일이 **생성되지 않았는지** 확인한다(FR-008, SC-002).
4. Robo Architect에서 그 Feature의 User Story를 수정한 뒤 같은 커맨드를 다시 실행 → 수정이 반영된 최신 스펙이 전달된다(SC-003).
5. 존재하지 않는 ID로 실행 → "범위를 찾을 수 없음"이 명확히 보고된다(FR-010).
6. 백엔드를 내린 상태로 실행 → "API에 연결할 수 없음"이 보고되고 추측 구현이 진행되지 않는다(FR-011).

## S3 — 태스크 파일 생성·갱신 (US3)

1. `/robo-implement` 실행 후 `.robo/tasks/feature-<featureId>.md`가 생성되었는지 확인한다.
2. frontmatter에 `scopeType`/`scopeId`/`scopeName`이 들어 있고, 본문이 `- [ ]` 체크박스 목록인지 확인한다.
3. 구현이 진행되면서 항목이 `- [x]`로 바뀌고, 완료 항목 줄 끝에 `<!-- impl: <경로>#<심볼> -->`가 붙는지 확인한다.

## S4 — 진척 가시화 (US4)

1. Requirements 탭을 연 상태로 둔다 — 5초 주기로 `GET /api/mcp-bridge/progress`가 폴링된다.
2. `.robo/tasks/feature-<featureId>.md`의 체크박스를 일부 체크 → 트리의 해당 Feature가 "진행 중"으로 표시된다.
3. 모든 항목 체크 → "구현 완료"로 갱신된다(30초 이내, SC-004).
4. `.robo/tasks/` 디렉터리가 없으면 전 범위가 "미착수"로 표시되고 탭이 깨지지 않는다(FR-020).
5. 태스크 파일을 일부러 손상시켜도 다른 범위 진척은 정상 표시되고 손상 범위만 사유가 표기된다(FR-021).

## S5 — 코드 점프 (US5)

1. "구현 완료"로 표시된 Feature/Aggregate에서 "코드로 점프"를 실행한다.
2. `GET /api/mcp-bridge/code-location` 결과의 소스 파일이 Claude Code IDE 워크스페이스 편집기에 열린다(FR-024).
3. 태스크 파일이 가리키던 파일을 이동/삭제한 뒤 점프 → "대상 코드를 찾을 수 없음"이 안내되고 탭이 깨지지 않는다(FR-025).

## 개발 런북 메모

- **MCP 서버 변경 반영**: `.mcp.json`을 통해 Claude Code가 MCP 서버를 서브프로세스로 기동한다. MCP 서버 소스 변경 후에는 Claude Code 세션을 재시작해야 새 코드가 로드된다.
- **uvicorn reload**: `--reload` 없이 띄운 백엔드는 신규 `/api/mcp-bridge/*` 라우트를 인식하지 못한다 — 런북 명령으로 기동.
- **`ROBO_API_BASE`**: 백엔드 포트가 8000이 아니면 `install-command`의 `roboApiBase`를 맞추고 재설치한다(`.mcp.json` env 갱신).
