# Plan: HTML 정책서/PRD 템플릿 익스텐션 (회원가입·탈퇴 정책서 스타일)

> Feature 023 — add-on extension. Active feature 022 의 PRD zip 파이프라인 위에 HTML 정책서 출력을 얹는다. 022 의 markdown 산출물에는 손대지 않는다.

## Context

`input/Full Example_회원가입,탈퇴.html` 은 NC 통합채널 정책서 Full v1.0 — 단일 self-contained HTML 로 `문서메타 → 개요 → 용어 → 유즈케이스(액터·UC·다이어그램·상태 전이표) → 프로세스(목록·흐름도·상세) → 기능 → 정책` 까지 풀 정책서를 담는 포맷이다.

현재 robo-architect 의 `POST /api/prd/{generate,download}` 파이프라인은 markdown + DDD 스펙 아티팩트만 zip 으로 묶는다 (`api/features/prd_generation/routes/prd_export.py:60` `build_prd_zip`). 사용자는 동일 파이프라인에 **현재 Neo4j 그래프(BC, Command, Event, Policy, UserStory, UI.sceneGraph)** 를 그 HTML 정책서 포맷으로도 출력하는 익스텐션을 추가하길 원한다.

핵심 요구:

1. **Jinja2 템플릿이 1차 도구** — 그래프 데이터로 결정적으로 채울 수 있는 섹션은 모두 Jinja 치환으로 처리.
2. **LLM 은 결정적 도출이 불가능한 섹션에 한해서만** 사용 (개요·설계원칙·정책 prose 정제 등). 기존 `ddd_spec/llm_assist` 패턴과 동일하게 `Jinja 렌더 직전 단계` 에서 LLM 호출 → context dict 주입.
3. **"스킬처럼" 동작 가능** — 템플릿은 manifest 기반으로 분리/추가 가능 (회원가입·탈퇴 외에 결제·약관 등 다음 템플릿도 동일 폴더에 manifest+jinja 만 추가하면 등록).
4. **DeepAgents 도입 안 함** — 기존 `get_llm()` + LangChain messages 로 충분. langgraph/deepagents 신규 의존성 없음.

출력 포맷은 HTML 단일. PRD zip 안에 `PRD.html` 로 포함하고, 미리보기용 단일 엔드포인트도 제공.

## Architecture

### 신규 모듈 위치

```
api/features/prd_generation/html_templates/
├── __init__.py
├── registry.py             # 템플릿 manifest 디스커버리/로드
├── schema.py               # Pydantic: TemplateManifest, SectionSpec, RenderContext
├── orchestrator.py         # 메인 진입점: 그래프 → derive → LLM-fill → Jinja 렌더
├── data_extractor.py       # BoundedContextProjection → 섹션별 변수 매핑
├── llm_sections.py         # 섹션별 LLM 프롬프트 (get_llm() 호출)
├── diagram_render.py       # 유즈케이스 다이어그램·프로세스 흐름도 SVG (인라인)
└── templates/
    └── policy_doc_full/
        ├── manifest.yaml
        ├── document.html.j2
        ├── partials/
        │   ├── section_glossary.j2
        │   ├── section_usecase.j2
        │   ├── section_process.j2
        │   ├── section_function.j2
        │   └── section_policy.j2
        └── prompts/
            ├── design_principles.md.j2
            ├── state_transitions.md.j2
            └── policy_prose.md.j2
```

기존 `api/features/ddd_spec/` 와 완전 분리. HTML 만의 Jinja2 `Environment` 를 별도로 구성 (autoescape ON).

### Manifest 포맷 (`manifest.yaml`)

```yaml
id: policy-doc-full
name: 정책서 Full
version: v1.0
description: 회원가입·탈퇴 정책서 스타일의 풀 HTML 정책서
master_template: document.html.j2
metadata:
  doc_id_prefix: POL
  author_default: "(미지정)"
sections:
  - id: meta
    kind: derived
  - id: overview.scope
    kind: derived
  - id: overview.principles
    kind: llm
    prompt: prompts/design_principles.md.j2
  - id: glossary
    kind: derived
  - id: usecase.actors
    kind: derived
  - id: usecase.list
    kind: derived
  - id: usecase.diagram
    kind: derived
  - id: usecase.state_table
    kind: hybrid
    prompt: prompts/state_transitions.md.j2
  - id: process.list
    kind: derived
  - id: process.flowchart
    kind: derived
  - id: process.detail
    kind: derived
  - id: function.list
    kind: derived
  - id: function.detail
    kind: hybrid
  - id: policy.list
    kind: derived
  - id: policy.detail
    kind: hybrid
    prompt: prompts/policy_prose.md.j2
```

`kind`:
- `derived`: 그래프 데이터에서 결정적으로 도출 → Jinja partial 만 사용
- `llm`: LLM 출력이 본문
- `hybrid`: 결정적 데이터 기본 + LLM 이 일부 필드 보강

### 그래프 → 섹션 매핑

| HTML 섹션 | Neo4j 소스 | 비고 |
|---|---|---|
| 0. 문서 히스토리 | manifest.version + `datetime.now()` + git HEAD short SHA | derived |
| 1.가. 범위 | `BoundedContextProjection.name` 리스트 | derived |
| 1.나. 설계 원칙 | LLM 합성 (BC purpose + Policy.description 입력) | llm |
| 2. 주요 용어 | `BoundedContextProjection.key_terms` + Aggregate.member_entities | derived |
| 3.가. 액터 | `UserStory.persona` (narrative parse) + `Wireframe.actor` distinct | derived |
| 3.나. 유즈케이스 | `UserStory` → UC 행 (ID = `UC-<bc-slug>-<seq>`) | derived |
| 3.다. UC 다이어그램 | UserStory ↔ Actor 매트릭스 → 인라인 SVG | derived |
| 3.라. 상태 전이표 | `Aggregate.attributes` 중 status 류 + Command→Event 체인 | hybrid |
| 4.가. 프로세스 목록 | `cross_bc_flows` + UserStory.wireframes 시퀀스 | derived |
| 4.나. 전체 업무 흐름도 | 위 DAG 의 인라인 SVG | derived |
| 4.다. 프로세스 상세 | 각 프로세스 = UserStory step 시퀀스 | derived |
| 5.가. 기능 목록 | `Command` 노드, ID 는 `FN-<bc>-<agg>-<seq>` | derived |
| 5.나. 기능 상세 | Command + GWT + Aggregate attrs | hybrid |
| 6.가. 정책 목록 | `Policy` 노드 | derived |
| 6.나. 정책 상세 | Policy + 연관 Event/Command | hybrid |

### Orchestrator 흐름

`orchestrator.render_policy_doc(template_id, bcs, config) -> str`:

1. `registry.load(template_id)` → `TemplateManifest`
2. `data_extractor.build_base_context(bcs)` → 결정적 변수 딕셔너리
3. manifest 의 각 `llm`/`hybrid` 섹션 순회 → `llm_sections.run_section(section, ctx)` 으로 LLM 호출, 결과를 context 에 병합. LLM 실패는 폴백 텍스트로 캡처 — 빌드 자체는 항상 성공
4. `env.get_template(manifest.master_template).render(**ctx)` → HTML 문자열 반환

### `build_prd_zip` 통합

```python
if config.include_html_policy:
    from api.features.prd_generation.html_templates.orchestrator import render_policy_doc
    html_text = render_policy_doc(config.html_template_id, bcs, config)
    zip_file.writestr("PRD.html", html_text)
```

`prd_api_contracts.TechStackConfig` 에 추가:

```python
include_html_policy: bool = Field(default=False, description="Include HTML policy document (POL-* style)")
html_template_id: str = Field(default="policy-doc-full", description="Template id under html_templates/templates/")
```

### 미리보기 엔드포인트

```
POST /api/prd/html-policy
body: { template_id: "policy-doc-full" }
response: text/html (200) | { code: "html_template_not_found" } (404) | { code: "neo4j_unavailable" } (503)
```

zip 빌드 없이 빠른 시각 확인용.

## Critical Files

수정:
- `api/features/prd_generation/prd_api_contracts.py` — `TechStackConfig` 에 2개 필드 추가
- `api/features/prd_generation/routes/prd_export.py` — `build_prd_zip` 말미에 HTML 분기 + `/api/prd/html-policy` 라우트
- (pyproject.toml: PyYAML 은 이미 transitively 설치되어 있음 — 명시 선언만 추가 권장, 필수 아님)

신규:
- `api/features/prd_generation/html_templates/` (위 트리 전체)
- `api/features/prd_generation/tests/test_html_templates.py`

재사용:
- `api/features/ddd_spec/projection.py` — `BoundedContextProjection`, `AggregateProjection`, `UserStoryProjection`, `WireframeProjection`
- `api/features/ddd_spec/repository.py` — `load_all_bounded_contexts()`
- `api/platform/llm.py` — `get_llm()`

## Implementation Steps

1. 데이터 추출기 + manifest 스키마 골격 (`schema.py`, `registry.py`, `data_extractor.py`)
2. 마스터 HTML 템플릿 추출 — `input/Full Example_회원가입,탈퇴.html` 의 CSS + body 골격을 `document.html.j2` 로 옮김
3. derived partial 들 구현
4. SVG 다이어그램 렌더러
5. LLM 섹션 구현 — `get_llm()` + JSON 응답 + 폴백
6. Orchestrator 연결
7. `build_prd_zip` 통합 + `/api/prd/html-policy` 엔드포인트
8. 테스트

## Verification

엔드 투 엔드:

1. `docker compose up -d neo4j` + 멤버십 BC 데이터 seed
2. `curl -X POST http://localhost:8000/api/prd/html-policy -H 'Content-Type: application/json' -d '{"template_id":"policy-doc-full"}' -o out.html`
3. 브라우저로 `out.html` 열어 `input/Full Example_회원가입,탈퇴.html` 와 좌우 비교
4. zip 경로: `curl -X POST http://localhost:8000/api/prd/download -d '{"tech_stack":{"include_html_policy":true,"spec_format":"ddd"}}'`
5. LLM provider 환경변수 없이도 빌드 통과 (폴백 텍스트로 채워짐)
6. `uv run pytest api/features/prd_generation/tests/test_html_templates.py -v`

수동 회귀:

- 기존 `POST /api/prd/download` (HTML 옵션 없이) 가 그대로 동작 — `include_html_policy=false` 시 zip 결과 바이트 동일
- `/api/prd/generate` 의 `files_to_generate` 응답에 `include_html_policy=true` 일 때 `PRD.html` 포함

## Out of Scope

- PDF 변환 (후속 PR)
- Markdown 동시 출력 (후속)
- 추가 템플릿 (결제·약관 등) — 골격만 제공
- DeepAgents 도입 — 명시적 거절
