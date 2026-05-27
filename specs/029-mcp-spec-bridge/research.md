# Phase 0 Research: MCP Spec Bridge

생성: 2026-05-19 · Plan: [plan.md](plan.md)

Technical Context의 미해결 항목과 의존성·통합 지점을 해소한다. 각 항목은 Decision / Rationale / Alternatives 형식.

## R1 — MCP 서버 트랜스포트 (stdio vs HTTP/SSE)

**Decision**: stdio 트랜스포트. MCP 서버는 Claude Code가 `.mcp.json` 항목으로 서브프로세스 기동하며 stdin/stdout으로 통신한다.

**Rationale**: spec의 가정대로 Robo Architect와 Claude Code는 동일 로컬·단일 사용자 환경에서 동작한다. stdio는 포트 할당·바인딩·생명주기 관리가 불필요하고, Claude Code가 프로세스 수명을 직접 관리하며, `.mcp.json` 한 항목으로 등록이 끝난다. MCP 서버 자체는 상태가 없고 매 호출마다 `httpx`로 로컬 Robo API를 칠 뿐이라 장기 연결이 필요 없다.

**Alternatives considered**: HTTP/SSE MCP 서버 — 원격/다중 클라이언트에 유리하나 포트 관리와 별도 기동 절차가 생기고 단일 사용자 시나리오에서 이득이 없다. 거부.

## R2 — MCP 구현 SDK

**Decision**: Python 공식 `mcp` SDK의 FastMCP API. MCP 도구 1개(`get_spec_bundle`)를 데코레이터로 정의하고 `mcp.run(transport="stdio")`로 기동한다. HTTP 호출은 `httpx`.

**Rationale**: 백엔드가 이미 Python이라 스택 일관성 유지(constitution 기술 제약). FastMCP는 도구 스키마를 타입 힌트에서 자동 생성해 보일러플레이트가 적다. `mcp`·`httpx`만 신규 의존성으로 추가하면 된다.

**Alternatives considered**: TypeScript MCP SDK — 별도 런타임/빌드 체인을 들이게 되어 거부. 저수준 `mcp` 서버 API 직접 사용 — FastMCP 대비 이점 없음.

## R3 — 동적 스펙 묶음(Live Spec Bundle) 조립

**Decision**: 기존 `api/features/ddd_spec` 투영을 **파일 출력 없이 in-memory 마크다운 문자열**로 재사용한다. 범위 종류별 조립:

- `bounded_context`: `ddd_spec`이 BC에 대해 생성하던 산출물 일체(domain-terms / bc-canvas / 각 aggregate-spec / requirements) 를 마크다운 문자열로 반환.
- `feature`: 부모 BC의 domain-terms·bc-canvas + 그 Feature에 속한 User Story만 추린 requirements 슬라이스 + 그 User Story들의 Command가 touch하는 Aggregate의 aggregate-spec.
- `aggregate`: 해당 Aggregate의 aggregate-spec + 소속 BC의 domain-terms(용어 컨텍스트).

`ddd_spec.inproc.build_artifacts_to_basedir`는 디스크에 쓴다. 본 기능은 디스크 출력이 금지(FR-008)이므로, `ddd_spec`의 **렌더러 함수**(BC/aggregate projection → 마크다운 문자열)를 직접 호출하는 얇은 조립 계층 `spec_bundle_service.py`를 둔다. 렌더러는 이미 projection 객체를 받아 템플릿을 렌더하므로 문자열 반환 경로가 존재한다.

**Rationale**: `ddd_spec`은 "이벤트 스토밍 그래프를 DDD 아티팩트로 *전사*"하는 결정론적 투영이며 LLM을 타지 않는다(`smooth_ears=False`, `aliases_to_avoid="omit"`). spec의 Assumptions가 요구한 "기존 DDD 아티팩트와 동등한 정보를 파일 대신 응답으로 전달"에 정확히 부합한다. 두 번째 투영 구현을 만들지 않아 산출물 일관성이 유지된다.

**Alternatives considered**: (a) `build_artifacts_to_basedir`를 임시 디렉터리에 호출 후 파일을 읽어 반환 — 동작하지만 임시 디스크 I/O·정리 부담이 있고 "파일 생성 금지"의 정신에 어긋난다. 거부. (b) PRD 묶음(spec 007) 재사용 — PRD 생성기는 ZIP·tech-stack을 다뤄 범위가 과하다. 거부. SVG 와이어프레임 렌더링은 묶음에서 생략(텍스트 요소 트리만) — Claude Code는 이미지가 불필요하고 응답 크기·지연을 줄인다.

## R4 — 슬래시 커맨드 형태

**Decision**(Clarifications 2026-05-19 반영): `.claude/commands/robo-implement.md` **범용 커맨드 1개**를 프로젝트당 한 번 설치한다. 범위는 호출 인자(`$ARGUMENTS` = `<scopeType> <scopeId>`)로 전달한다. "구현 커맨드 생성"은 범위마다 새 파일을 만들지 않고, 선택 범위에 맞는 호출 문자열(예: `/robo-implement feature feat-1a2b`)을 다이얼로그에서 복사하도록 제시한다.

커맨드 본문은 Claude Code에게 다음을 지시한다: (1) MCP 도구 `get_spec_bundle`을 `$ARGUMENTS`로 호출, (2) 받은 스펙으로 `.robo/tasks/<scopeType>-<scopeId>.md`를 SpecKit `tasks.md` 형식으로 작성, (3) 태스크를 순차 구현하며 완료 시 체크박스와 `impl:` 매핑 갱신, (4) 정적 스펙 `.md`는 생성 금지.

**Rationale**: 사용자 입력("커맨드를 하나")과 직접 일치. 커맨드 파일이 범위마다 누적되지 않아 `.claude/commands/`가 깨끗하게 유지된다. 범위 ID를 인자로 받으면 동일 커맨드가 모든 범위를 처리한다.

**Alternatives considered**: 범위별 커맨드 파일 생성 — Clarification에서 명시적으로 거부됨(파일 누적).

## R5 — 태스크 파일 형식·위치

**Decision**: `.robo/tasks/<scopeType>-<scopeId>.md`. YAML frontmatter로 범위를 식별하고, 본문은 SpecKit `tasks.md` 체크박스 규약을 따른다.

```
---
scopeType: feature
scopeId: feat-1a2b
scopeName: 결제 수단 등록
generatedAt: 2026-05-19T10:00:00Z
roboApiBase: http://127.0.0.1:8000
---
- [ ] T001 PaymentMethod 애그리거트 모델 작성
- [x] T002 등록 커맨드 핸들러 <!-- impl: api/payment/register.py#register_payment_method -->
```

완료 태스크는 줄 끝에 `<!-- impl: <상대경로>[#심볼] -->` 주석으로 구현 위치를 매핑한다(복수면 콤마 구분). 파서 `task_file.py`는 frontmatter·체크박스(`- [ ]`/`- [x]`)·impl 주석을 추출한다.

**Rationale**(Clarifications 2026-05-19): 전용 `.robo/tasks/` 디렉터리는 경로가 예측 가능해 폴링이 단순하고, 손으로 쓴 `specs/` 산출물과 충돌하지 않는다. 동적 경로라 SpecKit `specs/NNN/` 폴더가 디스크에 없으므로 전용 디렉터리가 적절하다. frontmatter는 파일 경로가 손상돼도 범위를 식별할 2차 수단이 된다(FR-014). `<!-- impl: -->` HTML 주석은 마크다운 렌더에 보이지 않으면서 기계 파싱이 쉽다.

**Alternatives considered**: `specs/<scope>/tasks.md` 레이아웃 재사용 — spec.md 없이 tasks.md만 두면 SpecKit 규약과 어긋난다. 거부. 프로젝트 루트 배치 — 여러 범위 시 루트 오염. 거부.

## R6 — 진척 폴링·상태 도출

**Decision**: Robo Architect 백엔드 `GET /api/mcp-bridge/progress`가 대상 프로젝트 홈의 `.robo/tasks/*.md`를 매 호출 시 읽어 파싱한다. Requirements 탭이 탭이 열려 있는 동안 5초 주기로 이 엔드포인트를 폴링한다. 범위 상태는 체크박스 비율로 도출: **체크 0개 = 미착수, 1개 이상이나 일부 = 진행 중, 전부 = 구현 완료**(Clarifications 2026-05-19, FR-018).

대상 프로젝트 홈은 Robo Architect가 이미 아는 값(Claude Code 워크스페이스 디렉터리 선택, spec 015/021)을 재사용한다.

**Rationale**: 폴링은 사용자가 명시적으로 선택한 가벼운 방식이다(spec Assumptions). 5초 주기는 SC-004의 30초 반영 한계를 여유 있게 충족하며 로컬 파일 몇 개를 읽는 비용은 무시할 만하다. 태스크 파일이 단일 진실 원천이라 MCP가 진척을 Robo로 푸시할 책임을 지지 않는다(R 기각: 푸시 방식).

**Alternatives considered**: MCP→Robo 푸시 — Clarification에서 거부. SSE/파일 워처 — 파일 워처는 OS별 차이와 디바운스 복잡도가 있고, 진척 변화 빈도가 낮아 5초 폴링으로 충분. 거부. 상태를 Neo4j에 캐시 — 두 번째 진실 원천이 되어 constitution I 위반 소지. 거부.

## R7 — `.mcp.json` 등록(멱등)

**Decision**: `command_installer.py`가 대상 프로젝트 루트의 `.mcp.json`을 읽어(없으면 생성) `mcpServers` 맵에 `robo-architect` 항목을 멱등 upsert한다:

```json
{
  "mcpServers": {
    "robo-architect": {
      "command": "python",
      "args": ["-m", "api.features.mcp_bridge.server"],
      "env": { "ROBO_API_BASE": "http://127.0.0.1:8000" }
    }
  }
}
```

기존 다른 `mcpServers` 항목은 보존한다. 동일 키 재설치는 덮어쓰기(중복 누적 없음, FR-005). `.claude/commands/robo-implement.md`도 동일하게 멱등 덮어쓰기. MCP 서버 실행 명령은 환경에 맞게 결정(`uv run python -m ...` 또는 `python -m ...`)하며 `ROBO_API_BASE`로 로컬 API 베이스를 주입한다.

**Rationale**: `.mcp.json`은 사용자 소유 파일일 수 있어 전체 덮어쓰기 금지 — 맵 병합만 한다(constitution: 사용자의 진행 중 작업 보존). 멱등성으로 "구현 커맨드 생성"을 여러 번 눌러도 안전하다.

**Alternatives considered**: 프로젝트 루트가 아닌 `.claude/.mcp.json` — Claude Code는 프로젝트 루트의 `.mcp.json`을 표준 위치로 읽으므로 루트 사용. MCP 서버를 Robo가 직접 띄우고 URL만 전달 — Claude Code의 MCP 등록 모델과 어긋남. 거부.

## R8 — 코드 점프

**Decision**: `GET /api/mcp-bridge/code-location?scopeType=&scopeId=`가 해당 범위 태스크 파일의 완료 태스크 `impl:` 매핑을 모아 소스 위치 목록을 반환한다. 프런트는 그 경로를 기존 Claude Code IDE 워크스페이스(spec 021)의 파일 편집기(`GET /api/claude-code/file`)로 연다. 경로가 더 이상 존재하지 않으면 "대상 코드를 찾을 수 없음"을 안내한다(FR-025).

**Rationale**: 구현 위치의 출처는 태스크 파일의 `impl:` 매핑(FR-016)이며, 별도 코드 스캐닝/AST 분석이 불필요하다. 편집기는 spec 021이 이미 제공하므로 신규 UI 없이 재사용한다.

**Alternatives considered**: 코드베이스 정적 분석으로 Aggregate↔파일 추론 — 부정확하고 비용이 크다. 태스크 파일 매핑이 명시적·정확하므로 거부.

## 미해결 항목

없음 — Technical Context의 모든 NEEDS CLARIFICATION이 해소되었다. Phase 1 진행 가능.
