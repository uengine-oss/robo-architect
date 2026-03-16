# Legacy Report Ingestion — 구조 및 처리 절차

> 레거시 EJB 시스템 분석 보고서(`.report.md`)를 입력받아 Event Storming 모델을 자동 생성하는 파이프라인.
> 최종 갱신: 2026-03-13

---

## 1. 전체 흐름 개요

```
*.report.md 업로드
    ↓
① 파일명 감지 → source_type = "legacy_report"
    ↓
② 보고서 파싱 → ParsedReport (구조화된 데이터)
    ↓
③ Phase Chain (11단계)
    US → BC → Aggregate → Command → Event
    → ReadModel → Properties → References → Policy → GWT → UI
    ↓
④ Neo4j 그래프 완성
```

### 핵심 설계 원칙

- **US Phase만 보고서를 주 입력으로 사용** (Session Bean별 개별 처리)
- **나머지 Phase는 이전 Phase 결과가 주 입력**, 보고서 데이터는 **보조 컨텍스트**로 LLM 프롬프트에 주입
- 각 Phase의 보조 컨텍스트는 해당 Phase에 필요한 정보만 선별 제공

### 설계 경위

처음에는 `phases_legacy/` 디렉토리에 별도 추출 Phase들을 만들어 보고서에서 직접 ES 요소를 추출하려 했으나, 레거시 코드에는 DDD 개념(BC, Aggregate Root vs VO/Enum 구분)이 없어 **모든 ES 구성요소에 LLM 판단이 필요**했다. 결과적으로 기존 RFP 파이프라인을 재사용하되 보고서 컨텍스트를 주입하는 현재 구조로 확정.

---

## 2. 진입점 및 감지

### `api/features/ingestion/router.py`

```
POST /api/ingest/upload
  - file: UploadFile (optional)
  - text: str (optional)
  - display_language: "ko" | "en"
```

**자동 감지**: 파일명이 `*.report.md`로 끝나면 `source_type = "legacy_report"` 자동 설정.
프론트엔드에서 별도 탭/선택 없이 파일명만으로 분기됨.

```python
if resolved_source_type == "rfp" and file and file.filename:
    if file.filename.lower().endswith(".report.md"):
        resolved_source_type = "legacy_report"
```

---

## 3. 보고서 파싱

### `api/features/ingestion/legacy_report/report_parser.py`

`parse_legacy_report(content: str) → ParsedReport`

마크다운 보고서를 섹션별로 파싱하여 구조화된 데이터 모델로 변환.

| 섹션 | 파싱 함수 | 출력 모델 |
|:-----|:---------|:---------|
| Section 1. 시스템 개요 | `_parse_overview()` | `SystemOverview` |
| Section 2. 패키지 | `_parse_packages()` | `list[PackageInfo]` |
| Section 3. 클래스 상세 | `_parse_classes()` | `list[ClassDetail]` |
| Section 4. 외부 의존성 | `_parse_external_deps()` | `list[ExternalDep]` |
| Section 5. 설정 블록 | `_parse_config_blocks()` | `list[ConfigBlock]` |
| Section 6. DB 테이블 | `_parse_tables()` | `list[TableSchema]` |
| Section 7. 데이터 흐름 | `_parse_data_flow()` | `DataFlow` |

**포맷 지원**: v1(template: `### 3.N ClassName`), v2(final: `### ClassName`) — `_detect_format_v2()`로 자동 감지.

### `api/features/ingestion/legacy_report/report_models.py`

핵심 데이터 모델:

```
ParsedReport
├── overview: SystemOverview
├── packages: list[PackageInfo]
├── classes: list[ClassDetail]
│   ├── methods: list[MethodInfo]     # role: command|query|lifecycle|getter|setter
│   ├── fields: list[FieldInfo]
│   ├── uml_relations: list[UMLRelation]
│   ├── table_access: list[TableAccessInfo]
│   └── summarized_code: str
├── tables: list[TableSchema]
│   ├── columns: list[ColumnInfo]
│   └── fk_relations: list[FKRelation]
├── data_flow: DataFlow
│   ├── call_chains: list[CallChain]
│   ├── call_relations: list[CallRelation]
│   └── table_access_matrix: list[TableAccessInfo]
└── column_level_fks: list[ColumnLevelFK]
```

**주요 헬퍼 메서드**:
- `get_session_beans()` / `get_entity_beans()` — stereotype 기반 필터
- `get_table_for_entity(entity_name)` — Entity Bean → 테이블 매핑
- `get_class_by_name(name)` — 이름으로 ClassDetail 조회

---

## 4. 워크플로우 실행

### `api/features/ingestion/ingestion_workflow_runner.py`

```python
ctx = IngestionWorkflowContext(session, content, client, llm, ...)
if source_type == "legacy_report":
    ctx.source_report = parse_legacy_report(content)
```

`ctx.source_report`가 설정되면 각 Phase에서 보조 컨텍스트가 활성화됨.

### `api/features/ingestion/workflow/ingestion_workflow_context.py`

```python
@dataclass
class IngestionWorkflowContext:
    source_report: ParsedReport | None = None   # ← 레거시 보고서 파싱 결과
    user_stories: list
    bounded_contexts: list
    aggregates_by_bc: dict[str, list]
    commands_by_agg: dict[str, list]
    events_by_agg: dict[str, list]
    policies: list
    readmodels_by_bc: dict[str, list]
    uis: list
```

---

## 5. Phase별 처리 상세

### 5.1 User Stories Phase — Session Bean별 개별 처리

`api/features/ingestion/workflow/phases/user_stories.py`

일반 RFP와 달리, 레거시 보고서는 **Session Bean 단위로 개별 LLM 호출**을 수행.

```
ctx.source_report 존재?
  ├─ Yes → get_per_session_bean_us_contexts()
  │        → [(SB1_name, SB1_context), (SB2_name, SB2_context), ...]
  │        → 각 SB별 extract_user_stories_from_text() 호출
  │        → 전체 결과 병합 → 정규화 + 중복제거 + EJB 필터
  │        → ctx.user_stories에 저장
  └─ No  → 기존 RFP 경로 (전체 텍스트 청킹)
```

**SB별 컨텍스트 구성** (`get_per_session_bean_us_contexts()`):
- 해당 SB의 비즈니스 Command/Query 메서드 (EJB lifecycle, 유틸리티 제외)
- 관련 Entity Bean 정보 (ASSOCIATION 관계 기반)
- 시스템 개요 + 테이블 FK 정보
- US 생성 가이드라인

**이 설계의 이유**: 전체 보고서를 하나의 컨텍스트로 묶으면 청킹 시 일부 SB 도메인이 누락됨 (cascading data starvation). SB별 개별 처리로 7/7 도메인 100% 커버리지 달성.

### 5.2 이후 Phase — 보조 컨텍스트 주입 패턴

모든 후속 Phase는 동일한 패턴을 따름:

```python
# 주 입력: 이전 Phase 결과 (US → BC → Agg → ...)
prompt = PHASE_PROMPT.format(주_입력_데이터)

# 보조 입력: 보고서 컨텍스트
if ctx.source_report:
    prompt += "\n\n" + get_PHASE_context(ctx.source_report)

# LLM 호출
response = await llm.invoke(prompt)
```

### `api/features/ingestion/workflow/utils/report_context.py`

각 Phase에 필요한 보고서 정보만 선별 추출하는 함수 모음.

| Phase | 컨텍스트 함수 | 제공 정보 | 목적 |
|:------|:------------|:---------|:-----|
| **User Stories** | `get_per_session_bean_us_contexts()` | SB별 메서드 + 관련 Entity + 테이블 | SB 단위 US 생성 |
| **Bounded Contexts** | `get_bounded_contexts_context()` | 패키지 + Entity/Session Bean + FK + 호출 체인 | BC 경계 식별 |
| **Aggregates** | `get_aggregates_context()` | Entity 상세 + 테이블 스키마 + FK 소유권 분석 | Root Aggregate vs VO 판별 |
| **Commands** | `get_commands_context()` | Command 메서드 + Query 메서드(⚠️마커) + 소유권 가이드 | 중복 방지 + Query 오분류 방지 |
| **Events** | `get_events_context()` | Entity 상태 상수 + 상태 전이 메서드 | 상태 변화 기반 Event 추출 |
| **Policies** | `get_policies_context()` | 서비스 호출 체인 + SB 간 의존성 | Cross-BC 연계 패턴 감지 |
| **ReadModels** | `get_readmodels_context()` | Query/Getter 메서드 + 테이블 접근 패턴 + SQL | 조회 요구사항 매핑 |
| **Properties** | `get_properties_context()` | 테이블 컬럼 상세 + FK + Entity 필드(fallback) | 속성 이름/타입 추출 |
| **GWT** | `get_gwt_context()` | 비즈니스 규칙 + 상태 전이 + 유효성 검증 | 테스트 시나리오 생성 |
| **UI** | *(사용하지 않음)* | — | Command/ReadModel의 US ui_description 기반 |

**토큰 제한**: `REPORT_CONTEXT_MAX_TOKENS = 20000` — 각 컨텍스트는 `_truncate_to_tokens()`로 한도 내 잘림.

---

## 6. 주요 방어 메커니즘

### 6.1 EJB Lifecycle 필터링 (3중 방어)

| 계층 | 위치 | 방식 |
|:-----|:-----|:-----|
| 컨텍스트 생성 | `report_context.py` | `_is_business_method()` — lifecycle/기술 메서드를 컨텍스트에서 제외 |
| US 생성 프롬프트 | `requirements_to_user_stories.py` | 시스템 프롬프트에 EJB 제외 규칙 명시 |
| US 후처리 | `user_stories.py` | `_is_ejb_lifecycle_us()` — action 텍스트 패턴 매칭 후 제거 |

### 6.2 Command 중복 방지

`commands.py`에서 `_existing_command_names` 리스트로 이전 Aggregate에서 생성된 Command 이름을 추적.
후속 Aggregate 처리 시 `<already_created_commands>` 태그로 LLM에 주입.

### 6.3 Query → Command 오분류 방지

`get_commands_context()`에서 Query/Getter 메서드에 `⚠️NOT_A_COMMAND` 마커를 부착.
`prompts.py`의 EXTRACT_COMMANDS_PROMPT에 "read-only operations are NOT Commands" 규칙 명시.

---

## 7. 파일 구조

```
api/features/ingestion/
├── router.py                          # API 엔드포인트 (*.report.md 파일명 감지)
├── ingestion_workflow_runner.py        # 워크플로우 오케스트레이션
├── ingestion_sessions.py              # 세션 관리
├── requirements_to_user_stories.py    # US 추출 LLM 호출 (EJB 제외 시스템 프롬프트)
│
├── legacy_report/
│   ├── report_models.py               # ParsedReport 데이터 모델
│   └── report_parser.py               # 마크다운 → ParsedReport 파서
│
├── workflow/
│   ├── ingestion_workflow_context.py   # 워크플로우 컨텍스트 (source_report 필드)
│   ├── utils/
│   │   ├── report_context.py          # Phase별 보조 컨텍스트 생성 (10개 함수)
│   │   └── chunking.py               # 토큰 추정 / 텍스트 분할
│   └── phases/
│       ├── user_stories.py            # ① US — SB별 개별 처리 (레거시 전용 경로)
│       ├── bounded_contexts.py        # ② BC — 보조 컨텍스트 주입 (청킹/비청킹 2곳)
│       ├── aggregates.py              # ③ Aggregate — FK 소유권 가이드 주입
│       ├── commands.py                # ④ Command — 중복 방지 + 소유권 가이드
│       ├── events.py                  # ⑤ Event — 상태 전이 정보 주입
│       ├── readmodels.py              # ⑥ ReadModel — Query/Getter/SQL 정보 주입
│       ├── properties.py              # ⑦ Property — 테이블 컬럼 상세 주입 (2곳)
│       ├── policies.py                # ⑧ Policy — 호출 체인 주입
│       ├── gwt.py                     # ⑨ GWT — 비즈니스 규칙 주입
│       └── ui_wireframes.py           # ⑩ UI — source_report 미사용
│
├── event_storming/
│   ├── prompts.py                     # LLM 프롬프트 템플릿
│   └── neo4j_client.py                # Neo4j 연결
│
frontend/src/features/requirementsIngestion/
└── ui/RequirementsIngestionModal.vue   # 업로드 UI (완료 모달에 RM/UI 카운트 추가)
```

---

## 8. 데이터 흐름 다이어그램

```
                    ┌─────────────────────┐
                    │  *.report.md 업로드   │
                    └──────────┬──────────┘
                               ▼
                    ┌─────────────────────┐
                    │  parse_legacy_report │
                    │  → ParsedReport     │
                    └──────────┬──────────┘
                               ▼
              ┌────────────────────────────────┐
              │  ctx.source_report = ParsedReport  │
              └────────────────┬───────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────┐
│  ① User Stories Phase                                        │
│  ┌──────────────────────────────────────┐                    │
│  │ get_per_session_bean_us_contexts()    │                    │
│  │ → (SB1, ctx1), (SB2, ctx2), ...      │                    │
│  └──────────────┬───────────────────────┘                    │
│                 ▼                                             │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐               │
│  │ SB 1 │ │ SB 2 │ │ SB 3 │ │ SB 4 │ │ ... │  (개별 LLM)    │
│  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘               │
│     └────────┴────────┴────────┴────────┘                    │
│                        ▼                                     │
│              병합 → 정규화 → 중복제거 → EJB 필터                │
│                        ▼                                     │
│              ctx.user_stories                                │
└──────────────────────────┬───────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│  ② ~ ⑩ 후속 Phase                                            │
│                                                              │
│  주 입력: 이전 Phase 결과                                      │
│  보조 입력: get_PHASE_context(ctx.source_report)               │
│                                                              │
│  US → BC → Agg → Cmd → Evt                                   │
│       → RM → Prop → Policy → GWT → UI                        │
└──────────────────────────────────────────────────────────────┘
```

---

## 9. 생성 결과 (analysis_report_final.report.md 기준)

| 구성요소 | 수량 |
|:---------|----:|
| UserStory | 80 |
| BoundedContext | 10 |
| Aggregate | 13 |
| Command | 37 |
| Event | 41 |
| Policy | 7 |
| ReadModel | 27 |
| GWT | 37 |
| UI | 53 |
| Property | 735 |
| **TOTAL** | **1,040** |

- 7/7 Session Bean 도메인 100% 커버
- 6/7 Entity Bean → Aggregate 직접 매핑
- 비즈니스 Command 매핑률 100%
- EJB lifecycle 오염 0건

상세 검증: `VALIDATION_RESULT.md` 참조.

---

## 10. 빠른 시작 (검증 방법)

```bash
# 서버 실행
cd /Users/seongwon/Desktop/robo-architect
.venv/bin/python -m uvicorn api.main:app --reload

# 프론트엔드에서 analysis_report_final.report.md 파일 업로드
# → 파일명 *.report.md 감지 → 레거시 모드 자동 활성화

# 또는 curl로 직접 테스트
curl -X POST http://localhost:8000/api/ingest/upload \
  -F "file=@requirement_sample/analysis_report_final.report.md" \
  -F "display_language=ko"
```
