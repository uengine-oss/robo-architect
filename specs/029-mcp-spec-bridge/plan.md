# Implementation Plan: MCP Spec Bridge — 동적 스펙 전달과 구현 진척 동기화

**Branch**: `029-mcp-spec-bridge` | **Date**: 2026-05-19 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/029-mcp-spec-bridge/spec.md`

## Summary

기존 PRD/DDD 산출물 흐름(spec 007·022)은 BC별 마크다운 스펙 파일을 디스크에 생성한다 — 파일이 쌓이고 그래프 모델이 바뀌어도 갱신되지 않는다. 본 기능은 그 정적 파일을 **MCP 서버를 통한 동적 스펙 전달**로 대체한다.

흐름: 아키텍트가 Requirements 탭(또는 Aggregate 탭)에서 Feature·BoundedContext·Aggregate를 선택해 "구현 커맨드 생성"을 실행하면, Robo Architect가 대상 프로젝트에 (1) 범용 슬래시 커맨드 `/robo-implement`를 `.claude/commands/`에 한 번 설치하고 (2) MCP 서버를 `.mcp.json`에 등록하며 (3) 선택 범위의 호출 문자열(`<scopeType> <scopeId>`)을 제시한다. 아키텍트가 Claude Code에서 그 슬래시 커맨드를 실행하면, MCP 서버가 범위 ID로 Robo Architect API를 호출해 **호출 시점의 최신** PRD·DDD 구현 스펙을 동적으로 받아 Claude Code에 전달한다 — 정적 스펙 마크다운 파일은 생성되지 않는다. Claude Code는 SpecKit `tasks.md` 형식 태스크 파일을 `.robo/tasks/<scopeType>-<scopeId>.md`에 펼치고 구현하며 체크박스를 갱신한다. Robo Architect는 프로젝트 홈의 `.robo/tasks/`를 가벼운 폴링으로 읽어 Requirements 탭에 미착수·진행 중·구현 완료 상태(체크박스 비율 기준)를 표시하고, 구현 완료 항목에서 실제 소스코드로 점프할 수 있게 한다.

기술 접근: 신규 feature 모듈 `api/features/mcp_bridge/`(라우터 prefix `/api/mcp-bridge`)에 4개 REST 엔드포인트와 stdio MCP 서버를 둔다. 동적 스펙 묶음은 기존 `api/features/ddd_spec`의 그래프 투영(projection·repository·렌더러)을 **파일 대신 in-memory 마크다운 문자열**로 재사용해 조립한다 — LLM 비관여 결정론적 투영. 진척은 그래프가 아닌 태스크 파일을 단일 진실 원천으로 삼아 폴링한다(신규 Neo4j 노드/관계 0건). 프런트 UI는 Requirements 탭의 일부이므로 `frontend/src/features/requirements/`에 병합 배치한다. 코드 점프는 기존 Claude Code IDE 워크스페이스(spec 021)의 파일 편집기를 재사용한다.

## Technical Context

**Language/Version**: Python 3.11+ (backend + MCP 서버), JavaScript / Vue 3 (frontend)
**Primary Dependencies**: FastAPI, Neo4j 공식 드라이버, 기존 `ddd_spec` 투영 파이프라인; **신규** `mcp` Python SDK(FastMCP, stdio 트랜스포트) + `httpx`(MCP→Robo API 호출); Vue 3 + Vite
**Storage**: Neo4j (도메인 모델 — 단일 진실 원천, `api/platform/neo4j.py` 경유); 대상 프로젝트 파일시스템 `.robo/tasks/*.md`(구현 진척의 단일 진실 원천 — 그래프 외부)
**Testing**: pytest (backend + MCP 도구 + 태스크 파일 파서), Playwright (frontend `frontend/tests/`)
**Target Platform**: Linux/macOS 서버 + 브라우저 SPA; MCP 서버는 Claude Code가 stdio로 기동
**Project Type**: Web application (frontend + backend 미러) + 보조 stdio MCP 프로세스
**Performance Goals**: spec-bundle 투영 응답 2초 이내(LLM·SVG 비관여 그래프 투영); progress 폴링 엔드포인트 500ms 이내; install-command 2초 이내; 태스크 체크 변경 → 탭 진척 반영 30초 이내(SC-004, 폴링 주기 5초로 충족)
**Constraints**: 동적 경로에서 정적 스펙 `.md` 생성 0건(SC-002); spec-bundle는 항상 호출 시점 모델 반영(SC-003, 캐시 금지); 범위 없음·API 불가·태스크 손상 등 모든 실패 경로에서 추측 스펙 전달 금지·탭 비파괴(SC-006); 커맨드/`.mcp.json` 설치는 멱등
**Scale/Scope**: 신규 백엔드 feature 1개(4 REST 엔드포인트 + stdio MCP 서버 1개, MCP 도구 1개), 신규 슬래시 커맨드 템플릿 1개, 프런트 신규 다이얼로그 1개 + 기존 트리/상세 컴포넌트 확장. 신규 Neo4j 노드/관계 0건. 신규 Python 의존성 2개(`mcp`, `httpx`).

## Constitution Check

*GATE: Phase 0 이전 통과 필수, Phase 1 이후 재확인.*

| 원칙 | 평가 | 결과 |
|------|------|------|
| I. Graph-as-Source-of-Truth | 동적 스펙 묶음은 Neo4j 그래프의 **투영**(파일 산출물과 동등, 언제든 재생성 가능). 구현 진척은 도메인 모델 상태가 아니라 *구현 작업 진행도*이며, 대상 프로젝트의 `.robo/tasks/` 파일을 단일 진실 원천으로 폴링한다 — 그래프에 병렬 복제하지 않으므로 두 번째 진실 원천을 만들지 않는다. | ✅ Pass (note) |
| II. Event Storming 어휘 | 범위 종류는 `feature`/`bounded_context`/`aggregate`로 기존 온톨로지 노드 라벨과 일치. MCP 도구·엔드포인트도 DDD 용어 보존. | ✅ Pass |
| III. Streaming-First UX | spec-bundle은 LLM·SVG를 배제한 결정론적 그래프 투영으로 2초 이내 완료 — "즉시 그래프 질의"에 해당하므로 요청/응답 적합. 장시간 구현 작업은 Claude Code **내부**에서 진행되며 진척은 폴링으로 노출(사용자가 의도적으로 선택한 가벼운 방식, Clarifications 기록). 인제스트 SSE 등 기존 스트림 흐름은 변경 없음. | ✅ Pass (note) |
| IV. Human-in-the-Loop on Mutations | MCP는 그래프에 대해 **읽기 전용**(스펙 투영만 반환) — LLM mutation 없음. 커맨드 생성은 그래프가 아닌 대상 프로젝트 파일(`.claude/commands/`·`.mcp.json`)에 쓰며 아키텍트의 명시적 클릭으로만 실행. 태스크 파일은 Claude Code가 작성. | ✅ Pass |
| V. Feature-Modular Architecture | 백엔드 신규 `api/features/mcp_bridge/`. `ddd_spec` 투영 재사용은 sibling 직접 import이나, `ddd_spec/inproc.py`가 이미 "다른 feature가 DDD 산출물을 임베드하는 공식 진입점"으로 설계됨(prd_generation·claude_code 선례). 프런트 UI는 별도 탭이 아니라 Requirements 탭의 일부이므로 `frontend/src/features/requirements/`에 병합 — 미러 규칙의 의도적 예외(아래 명시). | ✅ Pass (note) |
| VI. Provider-Agnostic LLM | 본 기능은 LLM을 호출하지 않음(spec-bundle은 결정론적 그래프 투영). 해당 없음. | ✅ N/A |
| VII. Observable by Default | 신규 로그 카테고리 `mcp_bridge.*`(spec-bundle 조회/커맨드 설치/진척 폴링/코드 위치), 페이즈 경계 로깅 + correlation ID. MCP 서버는 stderr 구조화 로그. | ✅ Pass |
| VIII. Figma SceneGraph Pipeline | 해당 없음(SerializedSceneGraph 생성 없음 — spec-bundle의 와이어프레임은 텍스트 요소 트리만 포함, SVG 렌더 생략). | ✅ N/A |
| IX. Plugin ↔ Backend Dev-Loop | 해당 없음(Figma 플러그인 비관여). MCP 서버 기동/`.mcp.json` 캐시는 quickstart에 별도 런북으로 명시. | ✅ N/A |

**개발 워크플로 게이트**: 신규 Neo4j 노드 라벨/관계 타입 **없음** — 범위는 기존 `Feature`·`BoundedContext`·`Aggregate` 노드를 참조하고 진척은 파일 기반이므로 `docs/cypher/schema/` 변경 불필요. 신규 REST 엔드포인트 4개는 Swagger `/docs`에 노출, README API 요약에 `/api/mcp-bridge` prefix 추가. 신규 Python 의존성(`mcp`, `httpx`)은 `pyproject.toml`/`requirements.txt`에 추가. 프런트 UI는 Requirements 탭 병합(별도 폴더 없음 — 위 표 note).

위반 없음 — Phase 0 진행 가능.

## Project Structure

### Documentation (this feature)

```text
specs/029-mcp-spec-bridge/
├── plan.md              # 이 파일
├── research.md          # Phase 0 산출물 (R1~R8)
├── data-model.md        # Phase 1 산출물
├── quickstart.md        # Phase 1 산출물
├── contracts/           # Phase 1 산출물
│   └── mcp-and-rest.md
├── checklists/
│   └── requirements.md  # /speckit-specify 산출물
└── tasks.md             # /speckit-tasks 산출물 (이 명령에서 생성 안 함)
```

### Source Code (repository root)

```text
api/
├── features/
│   ├── mcp_bridge/                         # 신규 feature 모듈
│   │   ├── __init__.py
│   │   ├── router.py                       # prefix /api/mcp-bridge
│   │   ├── routes/
│   │   │   ├── spec_bundle.py               # GET /spec-bundle   (MCP가 호출)
│   │   │   ├── install_command.py           # POST /install-command
│   │   │   ├── progress.py                  # GET /progress      (Requirements 탭이 폴링)
│   │   │   └── code_location.py             # GET /code-location (코드 점프)
│   │   ├── mcp_bridge_contracts.py          # Pydantic DTO
│   │   ├── spec_bundle_service.py           # ddd_spec 투영 → in-memory Live Spec Bundle 조립
│   │   ├── command_installer.py             # .claude/commands/robo-implement.md + .mcp.json 멱등 설치
│   │   ├── task_file.py                     # .robo/tasks/*.md 파서 (frontmatter + 체크박스 + impl 매핑)
│   │   ├── progress_service.py              # .robo/tasks/ 폴링 → 진척·상태 도출
│   │   ├── server.py                        # stdio MCP 서버 (FastMCP) — `python -m api.features.mcp_bridge.server`
│   │   ├── templates/
│   │   │   └── robo-implement.md             # 프로젝트에 설치되는 슬래시 커맨드 템플릿
│   │   └── tests/
│   │       ├── test_spec_bundle_service.py
│   │       ├── test_command_installer.py
│   │       ├── test_task_file.py
│   │       └── test_progress_service.py
│   ├── ddd_spec/                           # 기존 — 투영/렌더러 재사용 (inproc 공식 진입점)
│   ├── requirements/                       # 기존 — 범위 선택 UI 진입점(트리)
│   └── claude_code/                        # 기존 — 코드 점프가 워크스페이스 파일 편집기 재사용
├── main.py                                 # mcp_bridge_router include
│
frontend/src/features/requirements/         # UI는 Requirements 탭의 일부 — 미러 폴더 병합
├── ui/
│   ├── GenerateCommandDialog.vue            # 신규 — "구현 커맨드 생성" 다이얼로그(설치 + 호출 문자열 복사)
│   ├── RequirementsTree.vue                 # 수정 — 노드별 진척 배지(미착수/진행중/구현완료)
│   └── UserStoryDetail.vue                  # 수정 — 구현 완료 시 "코드로 점프" 액션
└── requirements.store.js                    # 수정 — 커맨드 설치 액션 + 진척 폴링(5초)

pyproject.toml / requirements.txt            # 수정 — mcp, httpx 의존성 추가
README.md                                    # 수정 — /api/mcp-bridge API 요약 추가
```

**Structure Decision**: Web application(미러 구조) + 보조 stdio MCP 프로세스. 백엔드는 신규 feature `api/features/mcp_bridge/`로 REST 4종과 MCP 서버를 모두 소유한다. MCP 서버(`server.py`)는 Claude Code가 `.mcp.json`을 통해 별도 프로세스로 기동하며, `httpx`로 로컬 Robo Architect API(`/api/mcp-bridge/spec-bundle`)를 호출한다 — FastAPI 앱을 직접 import하지 않아 결합을 최소화한다. 동적 스펙 묶음은 `ddd_spec`의 그래프 투영을 in-memory로 재사용한다(`inproc`는 이미 공식 임베드 진입점). 프런트 UI는 별도 탭이 아닌 Requirements 탭의 추가 동작이므로 `frontend/src/features/requirements/`에 병합 배치한다(미러 규칙의 의도적·문서화된 예외).

## Complexity Tracking

> Constitution Check 위반 없음 — 비어 있음.
