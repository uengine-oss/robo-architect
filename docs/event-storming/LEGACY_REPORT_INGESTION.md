# Legacy Report Ingestion — 구조 및 처리 절차

> 레거시 EJB 시스템 분석 보고서(`.report.md`)를 입력받아 Event Storming 모델을 자동 생성하는 파이프라인.
> 최종 갱신: 2026-03-19

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
  │        → 전체 결과 병합 → 정규화 + 중복제거 + EJB 필터 + Low Quality 필터
  │        → ctx.user_stories에 저장
  └─ No  → 기존 RFP 경로 (전체 텍스트 청킹)
```

**SB별 컨텍스트 구성** (`get_per_session_bean_us_contexts()`):
- 해당 SB의 비즈니스 Command/Query 메서드 (EJB lifecycle, 유틸리티 제외)
- 관련 Entity Bean 정보 (ASSOCIATION 관계 기반)
- 시스템 개요 + 테이블 FK 정보
- US 생성 가이드라인 (+ Granularity Rules: 구현 단계/에러 처리 분리 금지)

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
| **Bounded Contexts** | `get_bounded_contexts_context()` | 패키지 + Entity/Session Bean + FK + 호출 체인 + SB-Entity 연관 요약 | BC 경계 식별 + 의미적 통합 |
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

### 6.2 US 품질 필터링 (구현 단계 / 에러 처리 제거)

SB별 US 생성 시 메서드 내부 단계나 에러 처리가 개별 US로 과분해되는 문제 방지.

| 계층 | 위치 | 방식 |
|:-----|:-----|:-----|
| US 생성 프롬프트 | `report_context.py` | GRANULARITY RULES — 비즈니스 수준 US만 생성하도록 지시 |
| US 후처리 | `user_stories.py` | `_is_low_quality_us()` — 구현 상세(15패턴) + 에러 처리(11패턴) 텍스트 매칭 후 제거 |

**구현 상세 패턴**: generate id, record timestamp, convert dto, set status to, validate field, initialize variable 등
**에러 처리 패턴**: rollback transaction, handle error, display exception, catch exception 등

### 6.3 BC 과다 분할 방지 (3중 방어)

SB별 독립 BC 형성으로 인한 BC 과다 분할(10개→5-6개 적정) 문제 방지.

| 계층 | 위치 | 방식 |
|:-----|:-----|:-----|
| BC 식별 프롬프트 | `prompts.py` | rule 9(동일 도메인 개념 통합), rule 10(소스 구조 아닌 비즈니스 도메인 기준) |
| BC 컨텍스트 | `report_context.py` | SB-Entity 연관 관계 요약 + "SB 수보다 BC가 적어야 함" 가이드라인 주입 |
| BC 후처리 | `bounded_contexts.py` | **의미적 통합**: BC 7개 초과 시 LLM에 BC 목록 전달 → 유사 그룹 식별 → 병합 지시 수신 → user_story_ids 합산 |

**의미적 통합 동작**: `BCConsolidationResult` (`state.py`) + `CONSOLIDATE_BCS_PROMPT` (`prompts.py`)
```
BC 후보 7개 초과?
  ├─ Yes → LLM에 BC 이름/설명/US 수 전달
  │        → {keep: "LoanApplicationManagement", absorb: ["LoanApplicationProcessing"]} 수신
  │        → 흡수 BC의 user_story_ids를 유지 BC에 합산, 흡수 BC 제거
  └─ No  → 통합 건너뜀
```

### 6.4 청크 간 이전 결과 전달 (Cross-Chunk Context Passing)

대용량 입력으로 청킹이 발생할 때, 이전 청크에서 생성된 요소의 이름/설명을 다음 청크 프롬프트에 주입하여 중복 생성을 방지.

| Phase | 추적 변수 | 전달 내용 | 목적 |
|:------|:---------|:---------|:-----|
| **BC** | `_accumulated_bcs` | 이름 + 설명 + US 수 | 같은 도메인 US를 기존 BC에 할당 유도 |
| **Commands** | `_existing_command_names` | 이름 리스트 (Aggregate 간) | 동일 Command 중복 생성 방지 |
| **ReadModels** | `_existing_readmodel_names` | 이름 리스트 (BC 간) | 동일 ReadModel 중복 생성 방지 |
| **Policies** | `_accumulated_policy_names` | 이름 리스트 | 동일 trigger→command 매핑 중복 방지 |

청킹이 없거나 항목별 독립 처리(GWT, Properties)인 Phase는 전달 불필요.

**대용량 안전장치**: 누적 이름 목록이 과도하게 커져 컨텍스트 한도를 넘지 않도록, 이름 리스트는 최근 N개만 전달하고 전체 수를 표기 (예: `"... and 45 more"`). 현재 기본 한도: 50개.

### 6.5 Cross-BC Aggregate/Command 중복 병합 (2중 방어)

| 계층 | 위치 | 방식 |
|:-----|:-----|:-----|
| 프롬프트 (soft) | `aggregates.py` | 이전 BC의 Aggregate 이름을 프롬프트에 전달 + 동일 도메인 개념 중복 금지 지침 |
| 후처리 (hard) | `aggregates.py` / `commands.py` Phase 끝 | 동일 이름 Aggregate/Command를 **병합** — US를 유지 쪽으로 이관 후 중복 노드 삭제 |

**삭제가 아닌 병합**: 단순 삭제 시 흡수 쪽의 US가 고아가 되어 후속 Phase 정합성이 깨짐. 병합은 US 관계를 유지 노드로 이전한 뒤 중복 노드를 제거하므로 정합성 보장.

예: LoanLedger(여신원장)가 2개 BC에 생성 → US가 적은 쪽의 US를 많은 쪽으로 `IMPLEMENTS` 관계 이전 → 중복 Aggregate + 하위 Command/Event/Property CASCADE 삭제

### 6.6 Cross-Aggregate Command 중복 제거 (Hard Defense)

`commands.py` Phase 끝에서 후처리: 전체 BC/Aggregate에 걸쳐 동일 이름 Command가 존재하면, US가 더 많이 연결된 Aggregate의 것을 유지하고 나머지는 Neo4j에서 삭제.

프롬프트 기반 soft defense(`_existing_command_names`)와 조합하여 2중 방어.

### 6.7 Policy 순환/중복 방지 (3중 방어)

| 계층 | 위치 | 방식 |
|:-----|:-----|:-----|
| 프롬프트 | `prompts.py` | "invoke_command가 trigger_event와 동일한 Event를 emit하면 안 됨" 규칙 |
| 후처리 (direct) | `policies.py` | Command→Event 매핑 구축 후 1-hop self-loop Policy 자동 제거 |
| 후처리 (indirect) | `policies.py` | 2-hop 순환 탐지 (E1→P1→E2→P2→E1) 후 역방향 Policy 제거 |
| 후처리 (중복) | `policies.py` | 동일 trigger→command 매핑을 가진 중복 Policy 제거 |

Self-loop 패턴: `Event_A → Policy → Command → emits Event_A` (1-hop)
Indirect cycle 패턴: `Event_A → P1 → Event_B → P2 → Event_A` (2-hop, 무한 루프)

### 6.7 Query → Command 오분류 방지

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
│   ├── prompts.py                     # LLM 프롬프트 템플릿 (+ CONSOLIDATE_BCS_PROMPT)
│   ├── state.py                       # Pydantic 모델 (+ BCMergeInstruction, BCConsolidationResult)
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
│              병합 → 정규화 → 중복제거 → EJB 필터 → Low Quality 필터 │
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
│  US → BC (+ 의미적 통합) → Agg → Cmd → Evt                     │
│       → RM (+ Cross-BC dedup) → Prop → Policy → GWT → UI      │
└──────────────────────────────────────────────────────────────┘
```

---

## 9. 생성 결과 (analysis_report_final.report.md 기준)

| 구성요소 | 수량 (개선 전) | 예상 (개선 후) | 비고 |
|:---------|----:|----:|:-----|
| UserStory | 80 | ~65 | Low Quality 필터로 구현 단계/에러 US 제거 |
| BoundedContext | 10 | 5-6 | 의미적 통합 + 프롬프트 강화 |
| Aggregate | 13 | ~10 | BC 통합에 따른 자연 감소 |
| Command | 37 | ~30 | BC 통합으로 중복 감소 |
| Event | 41 | ~35 | Command 감소에 비례 |
| Policy | 7 | ~5 | BC 감소로 cross-BC 경로 감소 |
| ReadModel | 27 | ~20 | Cross-BC dedup + BC 통합 |
| GWT | 37 | ~30 | Command 감소에 비례 |
| UI | 53 | ~45 | Command/RM 감소에 비례 |
| Property | 735 | ~600 | 전반적 감소 |

**개선 전 (v1)**: 7/7 SB 도메인 100% 커버, EJB lifecycle 오염 0건, 비즈니스 Command 매핑률 100%
**개선 후 (v2) 목표**:
- BC 수 5-6개 범위 (적정)
- Command/ReadModel 중복 0건
- 비즈니스 US 비율 80%+ (개선 전 71%)

> 위 예상 수치는 재실행 전 추정값. 실제 결과는 재실행 후 업데이트 필요.

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
