# PRD: Document + Code 하이브리드 Ingestion

> 상태: Draft v0.1
> 작성일: 2026-04-13
> 기존 ingestion 파이프라인은 건드리지 않고 별도 모듈로 구축한 뒤 병합한다.

---

## 1. 배경 (Background)

### 1.1 문제 정의
- Legacy 코드의 분석 결과는 단위 프로세스 로직과 기대 결과 등 "무엇을(what) / 어떻게 계산(how-to-compute)" 수준만 드러난다.
- 누가(Who), 언제(When), 어떤 흐름(Flow)으로 수행되는가 하는 **비즈니스 프로세스 관점**은 코드만으로는 복원되지 않는다.
- 반면 매뉴얼·절차서·규정 같은 **문서**는 Actor/Task/Sequence 등 상위 흐름은 풍부하지만, 실제 판단 조건과 시스템 규칙은 얕다.

### 1.2 방향
- 기존 문서(프로세스 정의 / 사용자 매뉴얼)에서 **상위 흐름**을 가져오고,
- 코드에서 **상세 로직(조건·분기·판단)**을 뽑아
- 두 축을 하나의 온톨로지로 연결한 뒤, 이를 Event Storming 산출물로 승격한다.

### 1.3 Task의 정의 (중요 보정)
- Task = 단일 함수/단일 트랜잭션이 아니다.
- Task = **문서상 업무 활동(Activity) 단위**이며, 실제 구현에서는 여러 함수/모듈/조건 로직의 집합으로 실현된다.
- 즉, Task가 위, Function/Rule이 아래.

---

## 2. 목표 (Goals / Non-Goals)

### 2.1 Goals
1. 문서 → Actor/Task/Sequence 추출로 BPM 상위 설계도 생성 (기존 PDF-to-BPM 모듈 재활용).
2. 코드 → 핵심 평가/판단/분기 로직을 Given-When-Then(GWT) Rule로 추출.
3. 문서 Activity ↔ 코드 Rule/Function을 벡터 검색 + 의미 매핑으로 연결.
4. Task–Function–Condition–NextFlow를 하나의 지식 그래프(온톨로지)로 통합.
5. 온톨로지를 기반으로 Command/Event/Policy/Aggregate를 도출해 Event Storming 산출물을 자동 확장.

### 2.2 Non-Goals
- 기존 ingestion 경로(`api/features/ingestion/router.py`, `workflow/phases/*`)의 즉시 교체 또는 파괴적 수정.
- 사람이 수행하는 이벤트 스토밍 워크숍 자체를 대체.
- 단순 CRUD, 유틸, 로깅/예외처리 보일러플레이트에 대한 Rule 생성.

---

## 3. 범위 (Scope)

### 3.1 In-scope
- 신규 모듈: `api/features/ingestion/hybrid/` (가칭) — 문서와 코드 분석 결과를 조합하는 파이프라인.
- **외부 의존성**: `uengine-oss/process-gpt-bpmn-extractor` 를 A2A 서비스로 별도 기동 (기본 `http://localhost:9999`). 우리 리포는 A2A 클라이언트 호출 + 결과 어댑터만 포함.
- 신규 API 라우트: `POST /api/ingest/hybrid/upload`, `GET /api/ingest/hybrid/stream/{session_id}`, `GET /api/ingest/hybrid/pdf/{filename}` (A2A 서비스용 PDF 서빙), `GET /api/ingest/hybrid/bpm/{session_id}` (BpmTask cytoscape).
- 신규 Neo4j 노드/관계 스키마 확장 (`BpmTask`, `BpmSequence`, `Rule`, `ActivityMapping`).
- **BPM 렌더링 소스 전환**: BPM 탭을 기존 "이벤트 스토밍(Command/Event/Policy) 역조합 → BPMN XML" 방식에서 벗어나, **Phase 1에서 문서로부터 직접 추출된 `BpmTask` 그래프**를 일차 소스로 사용.
- 기존 `analyzer_graph` 결과(BusinessLogic, FUNCTION, Actor)와 기존 `event_storming` 산출물 재사용(Phase 2/5에서 참조).

### 3.2 Out-of-scope (이번 PRD)
- 기존 workflow runner 내부 phase 재배열.
- 기존 BPMN 합성 라우트(`api/features/canvas_graph/routes/bpmn_process.py`)의 즉시 제거 — Phase E 병합 시점에 deprecate.
- Frontend UI 전면 개편. (파이프라인 산출물을 기존 SSE 포맷·BPMN 패널에 흘리는 수준까지만)

### 3.3 BPM 생성 방향 전환 (핵심)
- **AS-IS**: 이벤트 스토밍 결과(`Command`/`Event`/`Policy`/`UserStory` 등)를 역방향으로 조립해 BPMN XML을 합성 → `BpmnPanel.vue` 렌더링.
- **TO-BE**: 문서 기반 Phase 1에서 **BPM을 먼저 그린다.** 이벤트 스토밍 산출물은 BPM에 종속된 하위 레이어로 위치 이동.
  - Phase 1 → `BpmTask` 그래프 + (선택) BPMN XML 생성 → 바로 렌더링 가능한 1차 소스
  - Phase 5에서 이벤트 스토밍 요소가 생성되면 해당 BpmTask에 **`PROMOTED_TO` 관계로 부착**만 함 (역조합 X)
- BPMN 패널은 새로운 엔드포인트(`GET /api/bpmn/hybrid/{session_id}` 또는 `?source=hybrid` 쿼리)를 통해 BpmTask 기반 XML/요소를 받아 그린다.

---

## 4. 파이프라인 (5 Phases)

> **문서 역할 분담 (2026-04-20)**: 본 §4 는 **설계 의도 중심 high-level 요약**. 실행 순서·신호·임계치·Cypher·튜닝 포인트 같은 *운영 detail* 은 **[`Hybrid_Ingestion_Architecture.md`](Hybrid_Ingestion_Architecture.md) §4** 가 canonical. Phase 5 의 구현 방식 (workflow 재사용) 은 [`Hybrid_Phase5_EventStorming_Promotion.md`](Hybrid_Phase5_EventStorming_Promotion.md) 참조. 동일 Phase 를 두 문서에서 다르게 설명하면 Architecture 를 기준으로 한다.

```
[문서] ──► Phase 1: Document → BPM Skeleton
                         │  (Actor, Task, Sequence)
                         ▼
[코드 분석 그래프] ──► Phase 2: Code → Business Rules (GWT)
                         │  (핵심 판단/분기 로직만)
                         ▼
                   Phase 2.5: Rule → Bounded Context (BC) 태깅
                         │  (prefix + 오케스트레이터 재분배 + LLM 이름 확정)
                         ▼
                   Phase 2.6: Rule → DDD/ES 역할 태깅
                         │  (invariant / validation / decision / policy / query / external)
                         │  결정론적 3-신호 (title > fn > tables) 가중 합산
                         ▼
                   Phase 3: Activity ↔ Rule Mapping
                         │  (벡터 검색 + 의미 매핑 + BC bonus)
                         ▼
                   Phase 4: Unified Ontology
                         │  (Task–Function–Condition–NextFlow)
                         ▼
                   Phase 5: Event Storming 승격
                            (Command / Event / Policy / Aggregate / ReadModel)
```

### 4.1 Phase 1 — Document → BPM Skeleton
- 입력: 매뉴얼/절차서/규정 (PDF, 텍스트).
- 구현 방침: **외부 A2A 서비스 우선 호출 + 내장 네이티브 추출기 fallback** 이중 경로. 레퍼런스 리포(`uengine-oss/process-gpt-bpmn-extractor`)의 A2A 서버/클라이언트를 그대로 외부 서비스로 기동해 호출한다. 서비스 장애·미구성·텍스트 입력 등 A2A가 불가능한 상황에서는 우리 리포의 `entity_extractor.py`(LLM 기반)가 자동으로 대신 수행한다.
  - 레퍼런스 A2A 클라이언트: `src/pdf2bpmn/a2a/client.py` — `A2AClient(server_url)` 사용.
  - 노출되는 엔드포인트 (서버):
    - `GET /discover` — agent capability 조회
    - `POST /execute` — body: `{ input: { pdf_url | pdf_path, pdf_file_name }, task_id? }` → `task_id` 반환
    - `GET /status/{task_id}` — 상태 + 진행률
    - `GET /result/{task_id}` — `{ bpmn_xml, process_count, processes[] }`
    - `GET /events/{task_id}` — SSE 스트림 (progress/message/artifact)
    - `DELETE /task/{task_id}` — 취소
  - 현재 호출 흐름 (구현됨, 2026-04-14 업데이트 — `pdf_url` 기반 전달로 전환):
    1. `router.py` 가 업로드된 PDF를 `PDF2BPMN_SHARED_PDF_DIR`(기본 `/tmp/hybrid_a2a_pdfs`)에 저장하고, 동시에 **`GET /api/ingest/hybrid/pdf/{stored_name}` 엔드포인트로 서빙**. 업로드 시점에 `pdf_url = {HYBRID_PUBLIC_BASE_URL}/api/ingest/hybrid/pdf/{stored_name}` 를 만들어 세션에 stash (`pdf_path` 도 함께 보관).
    2. `hybrid_workflow_runner.py` Phase 1 이 `document_to_bpm.extract_bpm_skeleton(content, pdf_path=..., pdf_url=...)` 디스패처를 호출.
    3. 디스패처는 `HYBRID_USE_A2A` 가 켜져 있고 `pdf_url` 또는 `pdf_path` 가 있으면 `A2AClient.execute(pdf_url=..., pdf_path=...)` → `wait_for_completion(task_id)` → `result.bpmn_xml` 수신. **`pdf_url` 가 우선** (A2A 서버가 httpx 로 다운로드하므로 로컬 `file://` 을 처리 못 함).
    4. `a2a_adapter.adapt_a2a_result_to_skeleton(...)` 가 BPMN XML을 파싱해 `BpmSkeleton(actors=lanes, tasks=*Task 요소, sequences=topo-order)` 로 변환. 원본 BPMN XML 도 `skeleton.bpmn_xml` 에 보존.
    5. A2A 호출/파싱 실패 또는 빈 결과 시 `entity_extractor.extract_bpm_from_document(content)` 네이티브 경로로 자동 fallback. 사용된 소스는 `phase1_source: "a2a" | "native"` 로 SSE 이벤트에 실려 프론트에 노출.
  - **왜 `pdf_url` 로 넘기는가** (중요):
    - extractor 레퍼런스(`process-gpt-bpmn-extractor/src/pdf2bpmn/a2a/server.py`) 의 `MockRequestContext` 는 `pdf_path` 를 받으면 내부적으로 `file://{abs_path}` 로 변환하여 executor 에 전달한다.
    - executor 의 `_download_file` 은 `httpx` 로만 다운로드해서 `file://` 스킴을 처리하지 못한다 → `Request URL is missing an 'http://' or 'https://' protocol` 오류로 실패.
    - 레퍼런스 리포를 건드리지 않기 위해 **우리 쪽에서 PDF 를 HTTP 로 서빙**하고 `pdf_url` 로 호출하도록 선회했다. 같은 호스트 배포 시 `http://localhost:8000/api/ingest/hybrid/pdf/...` 로 바로 붙고, 분리 배포 시에도 `HYBRID_PUBLIC_BASE_URL` 만 실제 도달 가능한 URL 로 교체하면 된다.
  - **A2A 가 "바로 되는" 조건**:
    - **같은 호스트에서 A2A 서버를 그대로 기동** → 추가 설정 없음. robo-architect 가 `localhost:8000` 에 떠 있고, `HYBRID_PUBLIC_BASE_URL` 기본값이면 된다.
    - **A2A 를 별도 컨테이너/호스트로 분리** → `HYBRID_PUBLIC_BASE_URL` 을 A2A 에서 도달 가능한 robo-architect URL (예: `http://host.docker.internal:8000`) 로 설정. `PDF2BPMN_SHARED_PDF_DIR` bind-mount 는 이제 **불필요**.
    - pdf2bpmn 레퍼런스 Neo4j 는 robo-architect Neo4j 와 **동일 인스턴스를 공유 가능**. 라벨(`Document/Section/Process/Task/Role/Skill/DMNDecision/Evidence/ProcessDefFragment/ReferenceChunk` 등)이 우리 스키마와 겹치지 않는다. `NEO4J_PASSWORD` 만 맞춰주면 된다 (extractor 쪽 `.env` 에서).
  - 환경 변수:
    - `PDF2BPMN_A2A_URL` (기본 `http://localhost:9999`)
    - `HYBRID_USE_A2A` (기본 `true`)
    - `PDF2BPMN_A2A_TIMEOUT_S` (기본 `300`)
    - `PDF2BPMN_SHARED_PDF_DIR` (기본 `/tmp/hybrid_a2a_pdfs`) — 로컬 보관용. extractor 는 여기 접근 불필요.
    - `HYBRID_PUBLIC_BASE_URL` (기본 `http://localhost:8000`) — A2A 서버에서 도달 가능한 robo-architect base URL.
  - 실제 구현 위치:
    ```
    api/features/ingestion/hybrid/document_to_bpm/
    ├── __init__.py               # extract_bpm_skeleton 디스패처 (A2A → native fallback)
    ├── a2a_client.py             # httpx 기반 A2A 클라이언트 (execute/stream/result/cancel)
    ├── a2a_adapter.py            # BPMN XML → BpmSkeleton (lane=Actor, *Task, sequenceFlow)
    ├── config.py                 # 위 env 해석
    ├── entity_extractor.py       # 네이티브 LLM 추출기 (fallback 경로)
    └── bpmn_builder.py           # BpmSkeleton → BPMN XML 빌더 (증분 렌더용)
    ```
  - 네이티브 프롬프트/BPMN 빌드 로직은 **fallback 전용으로 유지**. 정상 경로의 프롬프트/스키마 튜닝은 레퍼런스 리포에서 수행하고 이쪽 리포에는 포팅하지 않는다.
  - 공통 런타임 재사용: `api.platform.neo4j`, `api.platform.observability.smart_logger`. LLM 런타임(`ingestion_llm_runtime.get_llm`)은 네이티브 fallback 경로에서만 사용.
- 출력: `(Actor)-[:PERFORMS]->(BpmTask)-[:NEXT]->(BpmTask)` 형태의 상위 흐름 + BPMN XML 아티팩트(A2A 경로는 서비스 응답, 네이티브 경로는 `bpmn_builder` 가 합성).
- 비고: 이 단계 BPM은 최종 정답이 아닌 **상위 설계도**. 상세 조건은 Phase 2에서 코드로부터 보강된다.
- **프론트 영속화**: `bpmn.store.js` 의 hybrid 상태(`hybridBpmnXml`, `hybridActors`, `hybridTasks`)는 `localStorage` 키 `hybrid.bpmn.v1` 로 증분 저장된다. 새로고침 시 store 초기화 직후 자동 rehydrate 되어 BPMN 캔버스가 복원된다. `clear()` 또는 새 Hybrid 세션 시작 시 키는 제거/갱신된다.
- **Navigator UX (2026-04-15 기준, 2차 개정)**: BPMN 탭의 `NavigatorPanel.vue` 좌측 사이드바는 각 `BpmTask` 를 **간단한 플랫 리스트**(순번 + 이름 + enrichment 카운트 배지)로만 렌더링한다. **항목을 더블클릭하면 우측에 `HybridTaskInspector` 패널이 슬라이드-인** 되어 상세 내용을 보여준다. 이 결정은 좌측 트리가 길어지면 스크롤·정보 밀도 모두 나빠진다는 판단에 따른 것(1차 트리 확장식 구현은 2026-04-15 오전에 폐기).
  - Navigator 구현: `frontend/src/features/navigator/ui/NavigatorPanel.vue` (`hybrid-task-item` 블록, 선택 상태는 `bpmnStore.selectedHybridTaskId`).
  - Inspector 구현: `frontend/src/features/canvas/ui/HybridTaskInspector.vue` (`BpmnPanel.vue` 에 `BpmnInspectorPanel` 옆으로 마운트, 동일 `slide-inspector` 트랜지션 공유). 닫기: 패널 ✕ 버튼 또는 `store.clearHybridTaskSelection()`.
  - 노드 내부 섹션 → 채워지는 Phase 매핑:

    | 섹션 | 필드/데이터 | 소스 Phase |
    |---|---|---|
    | Description | `task.description` | Phase 1 |
    | Actors | `task.actor_ids` → `hybridActors` lookup | Phase 1 |
    | Source | `task.source_section`, `task.source_page` | Phase 1 |
    | Rules (GWT) | `task.rules[] = { given, when, then, source_function, source_module, confidence }` | **Phase 2 + 3** (미구현 → "대기 중" empty state) |
    | Mapped Functions | `task.functions[] = { module, name, confidence }` | **Phase 3** (미구현 → "대기 중") |
    | Conditions | `task.conditions[] = { expression \| text }` | **Phase 4** (미구현 → "대기 중") |
    | Event Storming | `task.promoted = { commands, events, policies, aggregates }` (카운트 칩) | **Phase 5** (미구현, 데이터 있으면만 표시) |
  - 스트리밍 계약 확장 방향: Phase 2~5 구현 시 기존 `HybridTask` SSE 이벤트의 `payload.task` 에 위 필드들을 **누적 병합(upsert)** 하여 전송하면 프론트는 추가 작업 없이 해당 섹션이 자동으로 채워진다 (`bpmn.store.js::addHybridTask` 가 이미 upsert 구현). 새로운 이벤트 타입을 늘리는 대신 기존 payload를 확장하는 방식을 기본으로 한다.
  - 빈 섹션의 empty state 는 "— Phase N 대기 중 —" 문구로 명시하여, 데모 시점에도 전체 파이프라인의 완성도를 한 눈에 파악할 수 있도록 한다.

### 4.2 Phase 2 — Code → Business Rules (GWT)
- 입력: 기존 `analyzer_graph`의 `BusinessLogic`, `FUNCTION`, `Actor`, 연관 DB 스키마.
- 필터: EJB 라이프사이클, Finder, CMP/BMP 인프라, getter/setter, 로깅은 제외 (기존 `analyzer_graph/graph_to_user_stories.py`와 동일 원칙).
- 출력: `(Rule {given, when, then, source_function, source_module})`.
- 핵심 기준: 승인 여부 판단, 할인율 산정, 자격 충족, 예외 처리 기준 등 **비즈니스 가치가 있는 판단 로직**만.
- **구현 메모 (2026-04-15)**:
  - **LLM 미사용**: analyzer 단계에서 이미 `(FUNCTION)-[:HAS_BUSINESS_LOGIC]->(BusinessLogic {given, when, then, title, sequence, coupled_domain})` 형태로 GWT가 채워져 있음. Phase 2 는 그대로 읽어 매핑만 하므로 LLM 호출이 필요하지 않다.
  - **DB 분리**: analyzer 그래프는 별도 `ANALYZER_NEO4J_DATABASE` 에 저장됨. `get_session(database=ANALYZER_NEO4J_DATABASE)` 로 읽고, 추출된 Rule 은 기본 DB(hybrid ontology 쪽)에 `L_RULE` 라벨로 쓴다. 세션 격리는 `session_id` 프로퍼티.
  - **필터 모듈**: `code_to_rules/rule_filters.py` — `INFRA_KEYWORDS`(ejb*/find*/getConnection/log.*/System.out 등) + getter/setter 정규식(`^(get|set|is)[A-Z]\w*$`) + GWT 슬롯 2개 이상 채워진 항목만 통과(`is_meaningful_gwt`).
  - **Rule ID**: `rule_{sha1(function_id|sequence|title)[:12]}` — 동일 분석 그래프 재실행 시 멱등.
  - **`analyzer_graph_ref` 현재 위상**: analyzer DB 는 단일 전역 그래프이며 스냅샷 태깅이 없다. 파라미터는 인터페이스에만 남겨두고 필터링에는 사용하지 않는다. 스냅샷별 격리가 필요해지면 analyzer 쓰기 단계에서 프로퍼티 태깅을 추가해야 한다 (추후 Open Question).
  - **SSE 이벤트**:
    - `HybridRule` — Rule 한 건 증분. payload: `{ type, rule: RuleDTO }`. 프론트는 `bpmnStore.addHybridRule` 로 누적.
    - `HybridRulesComplete` — Phase 2 끝. payload: `{ type, rule_count, rules: RuleDTO[] }`. 프론트는 `setHybridRules` 로 일괄 교체(재시도 대비).
  - **프론트**: `NavigatorPanel.vue` 의 BPMN 탭 좌측 사이드바에 **Business Rules (GWT)** 섹션 추가 — 함수명 + W/T 요약 행. 현재는 Task 와 독립된 플랫 리스트이며, Phase 3 에서 `(BpmTask)-[:REALIZED_BY]->(Rule)` 매핑이 생성되면 Task 노드 내부 "Rules" 섹션으로도 승격되어 표시된다.
  - **추출 품질 지표**: `extract_rules_from_analyzer_graph` 가 SmartLogger 로 `{rule_count, raw_records}` 를 남기므로 필터 통과율을 바로 확인할 수 있다. PRD §10 의 "인프라/보일러플레이트 오탐률 < 5%" 는 이 비율을 기준으로 검증한다.

### 4.2.5 Phase 2.5 — Rule → Bounded Context (BC) 태깅

> 구현 완료 (2026-04-20). 기존 "BC 사전 태깅" 개선과제의 실현.

**목적**: Phase 5 BoundedContext 식별 시 LLM이 모든 rule을 단일 컨텍스트로 collapse하는 문제(§8.1 실데이터 BC=1 → Policy=0) 해소. Rule별 `context_cluster` 속성을 선제 부여해 Phase 3 매칭 정합성과 Phase 5 승격 품질을 동시에 개선.

**구현**: `api/features/ingestion/hybrid/mapper/bc_identifier.py`

**4 단계 파이프라인 (LLM 1회만 사용, 2026-04-20 기준)** — 상세 regex·임계치는 Architecture §4.2.5 참조:
1. **Prefix clustering + Graph orchestrator 감지 (결정론)** — `source_function` 명명 규칙 regex 로 1차 시드. **`callees >= 3` 인 함수는 naming 무관하게 orchestrator 로 승격** (CALLS 그래프 기반. 멀티모듈·multi-team 환경 대응).
2. **Orchestrator BL 재분배** — orchestrator의 14 BL이 다양한 도메인을 걸치므로, BL.title 키워드(이력/에러/반영여부/카드사 등)로 각 BL을 finer cluster로 재배치.
3. **Subfunction caller 상속** — prefix regex 가 매칭 안 된 Rule 은 `callers` 의 majority cluster 를 seed 로 상속. dbio 헬퍼가 orchestrator 호출을 받으면서 caller 가 "이력관리" 면 helper 도 "이력관리".
4. **WRITES Table 보강 + LLM naming 1회** — 같은 WRITES 테이블 공유 cluster union (orchestrator BL 제외). LLM 이 도메인 용어명 확정.

**핵심 설계 결정**:
- **BL.title 우선 + function_summary 배제** — summary는 함수 단위로 동일해서 BL 간 차이를 못 냄. title만 순수 per-BL 의미.
- **Orchestrator writes_table 제외** — `b000`이 다중 테이블에 WRITES하므로 table-overlap 기반 cluster union이 모든 BC를 한 덩어리로 병합하는 이슈 발견 후 orchestrator 출신은 `_apply_writes_reinforcement`에서 제외.
- **Call graph orchestrator 우선 (2026-04-20)** — fn-prefix regex 는 project-specific. `callees` 카운트가 멀티모듈에도 robust.

**부모 노드 탐색 (RuleContext 확장, 2026-04-20)**:
- `callers` / `callees` / `parent_module` / `parent_package` 필드 추가 — analyzer DB 의 `CALLS`, `HAS_FUNCTION`, `BELONGS_TO_PACKAGE` 조인
- 멀티모듈 분석 그래프에서 **같은 이름의 함수가 여러 모듈에 있어도 분리** + **호출 체인 내 도메인 일관성 유지** 에 사용

**출력**: `Rule.context_cluster: str` + `HybridBoundedContextTagged` SSE 이벤트.

**Phase 3 연계**:
- Embedding matcher: Rule 텍스트 맨 앞에 `[업무범주: X]` prefix 주입 → 동일 토큰을 쓰더라도 BC 맥락이 달라 코사인 분리.
- Lexical matcher: rule tokens에 BC 이름 토큰 포함 (한글 2음절+ informative).
- Structural booster: `_SAME_CONTEXT_BONUS = 0.08` — Task의 추정 BC(현재까지 매칭된 rule의 majority cluster) == Rule.context_cluster이면 가산.

**검증 (2026-04-20, 52 rules, 실데이터)**:

| Cluster | Count | 함수 출처 |
|---|---|---|
| 인증이력관리 | 18 | b200/b205/b210/b400/b410 + b000 이력 관련 |
| 입력값검증 | 12 | a000 (11) + b000 "거부" (1) |
| 인증결과판정 | 7 | b000 반영/결정 BL |
| 오류메시지처리 | 7 | b800 (4) + b000 메시지 관련 (3) |
| 실시간인증진입 | 3 | zapamcom10060 |
| 공통코드검증 | 2 | b100_dbio_comm_cd_dtl_canyn |
| 간편결제사검증 | 2 | b720_check_smp_co |
| 카드사정보검증 | 1 | b000 카드사 외부 조회 |

> BC=1 collapse 문제 해소. 8 클러스터 분포 확보. "실시간인증이력 생성/갱신" Task는 16 rules 전부가 `인증이력관리` 단일 BC로 들어와 매칭 정합성도 개선됨.

### 4.2.6 Phase 2.6 — Rule → DDD/Event Storming 역할 태깅

> 구현 완료 (2026-04-20). Phase 5 승격 대상 요소를 각 Rule에 사전 지정.

**목적**: 각 Rule이 Phase 5에서 어떤 ES 요소(Aggregate / Command / Policy / ReadModel / External System)로 승격될지 **결정론적으로** 사전 분류. Phase 5 LLM 호출량을 줄이고 오분류 위험을 낮춤.

**구현**: `api/features/ingestion/hybrid/mapper/es_role_tagger.py`

**6 가지 내부 역할 → 5 가지 ES 요소 매핑**:

| 내부 role | ES 승격 대상 | 역할 설명 |
|---|---|---|
| `invariant` | **Aggregate** (불변식) | WRITES 있는 상태 규칙 |
| `decision` | **Aggregate** (도메인 규칙) | 조건→Y/N/값 판정 |
| `validation` | **Command** (사전 가드) | 입력 검증, 거부/거절 |
| `policy` | **Policy** | 반응 규칙 (on Event → Command) |
| `query` | **ReadModel** | READS-only 조회 |
| `external` | **External System** | 외부 어댑터 (ES 승격 제외 후보) |

**결정 기준 — 3 신호 밴크 가중 합산**:

**신호 가중치 (세마틱 우선)**:
- title × **1.0** (최고 — BL.title 의미가 가장 정확한 신호)
- fn × **0.8** (구조적 힌트 — 함수 이름만으로 역할 단정 X)
- tables × **0.55** (READS/WRITES 보조 신호)

> 가중 이유: 함수 *위치*가 역할을 결정하지 않음. `zapam*` entry 함수 안에 validation BL이 있을 수 있고, `check_*` 함수 안에 policy BL이 있을 수 있음. Title semantic이 dominant해야 함.

**각 역할의 signal 판정 기준**:

| 역할 | Title 신호 (semantic) | FN 신호 (구조) | Table 신호 |
|---|---|---|---|
| **invariant** | `이력.{0,10}(저장\|적재\|갱신\|생성\|반영\|삭제)` 0.9 / `(저장\|적재\|갱신\|update\|insert)` 0.75 | `dbio_.*_i\d+` 0.95 / `dbio_.*_u\d+` 0.95 / `dbio_.*_d\d+` 0.9 | WRITES 있음 → 0.6 |
| **validation** | `(거부\|거절\|반려)` 0.9 / `(필수\|누락\|없으면\|비어 ?있)` 0.85 / `(유효성\|valid)` 0.8 | `(?:^\|_)(check\|valid\|verify\|assert)(?:_\|$)` 0.9 / `input_valid` 0.95 | — |
| **decision** | `(반영여부)` 0.88 / `(판정\|결정\|보정\|반영한다\|선택한다)` 0.85 / `반영하지 ?않` 0.85 / `(으로\|이면).{0,10}(본다\|간주한다)` 0.8 / `(일 ?때만).{0,15}반영` 0.9 | — | — |
| **policy** | `(메시지\|문구).{0,6}(만들\|만든\|조립\|생성\|반환\|결정\|고정\|부여\|대체)` 0.92 / `(이면\|시).{0,30}(호출\|요청\|전달\|만든\|생성\|발송)` 0.7 | `(err_msg\|msg_make\|build_msg\|notify)` 0.92 | — |
| **query** | `(조회\|검색\|확인을 ?요청\|존재 ?여부)` 0.85 / `(공통코드\|코드군).{0,10}(조회\|포함)` 0.8 | `dbio_.*_(canyn\|check\|exist\|s\d+\|q\d+)` 0.9 | READS only → 0.6 |
| **external** | `외부\s*(조회\|호출\|API\|연동\|시스템\|전문\|통신\|연계)` 0.9 | `^z[a-z]+\d+` 0.7 / `^(entry\|main_entry\|handler)_` 0.7 | — |

**왜 이런 기준인가**:
- **invariant vs decision**: WRITES 존재는 필요조건이 아님. 순수 계산 로직도 내부 상태 조정이면 decision. WRITES가 있으면 결정적으로 invariant 쪽으로 기움 (0.6 weak bias).
- **validation은 "거부" 동사 중심**: Command 수용 전 guard는 반드시 reject 가능성을 가짐. "거부/거절/반려/누락"이 없고 단지 "검증"만 하는 경우 decision 또는 query로 밀림.
- **policy는 "행위 생성" 중심**: 반응 규칙은 결과로 **다른 Command/Event를 트리거**함. 메시지 생성/조립/고정도 downstream 효과이므로 policy.
- **external은 `외부` + 명시적 동사 필수**: "외부인증"(인증 유형 이름)은 external이 아님. `외부\s*(조회|호출|API|...)` 로 엄격 매칭.

**약한 신뢰도 처리**:
- `confidence < 0.5` → `fallback_no_signal` 딱지를 붙이고 `decision`으로 default (Phase 5에서 검토 대상).
- 현재 데이터에서는 `0.6` 미만 Rule 0건.

**출력**: `Rule.es_role: str`, `Rule.es_role_confidence: float` + `HybridEsRoleTagged` SSE 이벤트.

**검증 (2026-04-20, 52 rules)**:

| Role | Count | Avg conf | ES 승격 시 대상 |
|---|---|---|---|
| validation | 18 | 0.82 | Command |
| decision | 14 | 0.86 | Aggregate |
| invariant | 11 | 0.80 | Aggregate |
| policy | 5 | 0.84 | Policy |
| query | 3 | 0.76 | ReadModel |
| external | 1 | 0.90 | External System |

**BC × Role 교차표** (의미적 정합성 검증):

| Role \\ BC | 이력관리 | 입력값검증 | 인증결과판정 | 오류메시지처리 | 공통코드검증 | 간편결제사검증 | 카드사정보검증 | 진입점 |
|---|---|---|---|---|---|---|---|---|
| invariant | **11** | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| decision | 5 | 0 | **7** | 1 | 0 | 0 | 0 | 1 |
| validation | 2 | **12** | 0 | 1 | 0 | 2 | 0 | 1 |
| policy | 0 | 0 | 0 | **4** | 0 | 0 | 0 | 1 |
| query | 0 | 0 | 0 | 1 | **2** | 0 | 0 | 0 |
| external | 0 | 0 | 0 | 0 | 0 | 0 | **1** | 0 |

> 대각 지배성 양호 — 각 BC의 주력 역할이 명확히 드러남. 이력관리→invariant / 입력값검증→validation / 인증결과판정→decision / 오류메시지처리→policy / 공통코드검증→query / 카드사정보검증→external / 간편결제사검증→validation.

**프론트 표시**:
- `HybridTaskInspector.vue` — Rule 카드 헤더에 ES 요소 라벨 배지. 프로젝트 `--color-*` ES 팔레트 사용:
  - Aggregate 🟨 `--color-aggregate` (yellow, invariant+decision 공유)
  - Command 🟦 `--color-command` (blue)
  - Policy 🟪 `--color-policy` (purple)
  - ReadModel 🟩 `--color-readmodel` (green)
  - External System 🟥 pink
- 내부 role(`invariant` vs `decision`)은 DB에만 보존 — Phase 5 에서 Aggregate 내부의 다른 위치(불변식 리스트 vs 메서드)로 라우팅에 사용.

### 4.3 Phase 3 — Activity ↔ Rule Mapping
- 임베딩 기반 유사도 + 용어집(glossary) 기반 의미 매핑.
- 매핑 산출물: `(Task)-[:REALIZED_BY {confidence}]->(Rule)`, `(Task)-[:USES]->(FUNCTION)`.
- 신뢰도 임계치 이하 항목은 리뷰 큐로 분리 (자동 연결 X).
- **구현 메모 (2026-04-15)** — 3단 파이프라인 (lexical → embedding → structural) + 용어집 전처리:

  **3.0 Glossary Extraction** — `mapper/glossary_extractor.py`
  - 입력: Phase 1 원문 텍스트 (router에서 `{pdf}.txt` 로 로컬 stash + 메모리 `session.content` 로 전달), `BpmTask.name/description`, `BpmActor.name`, analyzer 토큰(FUNCTION 식별자 camelCase 분해 + BusinessLogic.title + BusinessLogic.coupled_domain(한글) + Table.name).
  - 인프라 토큰 제거(`ejb/cmp/log/get/set/impl/...`) 후 상위 200개만 LLM에 투입, 문서 텍스트는 12k자로 잘라 1회 호출.
  - 출력: `GlossaryTerm {term, aliases[], code_candidates[], source}` 리스트 → Neo4j `:GlossaryTerm` 으로 저장.
  - **핵심**: analyzer `coupled_domain` 이 한글로 들어있는 경우가 많아 ko↔en 부트스트랩의 최대 자원.

  **3.1 Lexical Matcher** — `mapper/lexical_matcher.py`
  - Task 텍스트(name + description + actor 이름)를 glossary로 확장 → 영문 코드 토큰 후보 집합 산출.
  - Rule 컨텍스트(함수/모듈/summary/GWT/Actor/Table) 토큰과 교집합 검사, 3글자 이상 토큰만 카운트.
  - 신뢰도: hit 1개 = 0.88, 2개 = 0.93, 3개↑ = 0.97. 여기서 잡힌 Task는 임베딩 단계에서 **제외(locked)**.

  **3.2 Embedding Matcher** — `mapper/embedding_matcher.py` + `mapper/embeddings.py`
  - OpenAI `text-embedding-3-small` (env: `HYBRID_EMBEDDING_MODEL`). 세션 범위 `EmbeddingCache` 로 중복 임베딩 방지.
  - Task 텍스트: `name + description + [Actor: ...]`, Rule 텍스트: `GIVEN/WHEN/THEN + Summary + Function + Tables`.
  - 코사인 유사도 top-k(기본 3) per Task, 임계치 `θ_auto=0.50` / `θ_review=0.40` (env: `HYBRID_EMBED_THETA_AUTO`, `HYBRID_EMBED_THETA_REVIEW`, `HYBRID_EMBED_TOP_K`). 한↔한 GWT 코사인이 0.45~0.55 대에 주로 위치해 보수적으로 설정.
  - `θ_review ≤ score < θ_auto` 구간은 review queue로 분리.

  **임베딩 단위 요약 (한 번 정리)**:
  | 대상 | 1개 객체 = 1개 벡터 | 텍스트 구성 | 쓰는 곳 |
  |---|---|---|---|
  | Task | BpmTask 하나 | `name + description + [Actor: ...]` | Phase 3.2 + 4.1 (공유) |
  | Rule | BusinessLogic(=Rule) 하나 | `GIVEN + WHEN + THEN + Summary + module.fn + reads/writes Tables` | Phase 3.2 인덱스 |
  | Passage | 청크 하나 (헤딩 or 400자 윈도우) | `heading + body` | Phase 4.1 인덱스 |

  - 같은 `when` 을 공유해도 `then` 이 다른 BL은 **별개 벡터** (채널별 분기 보존).
  - 세션 한 번에 약 `Task개수 + Rule개수 + Passage개수` 만큼 OpenAI 호출 (실측: 7 + 52 + 30 = 89 벡터).
  - 영속 벡터 DB(ChromaDB 등) 안 씀. `EmbeddingCache` 는 in-memory, 세션 종료 시 소멸.

  **3.3 Structural Booster** — `mapper/structural_booster.py`
  - Actor alias 보너스(+0.05): BpmActor 이름이 analyzer Actor 수행자 리스트에 포함되면 가산.
  - Sequence cluster 보너스(+0.03): 같은 `BpmSequence` 내에 이미 2건 이상 매칭된 Task의 Rule은 "같은 업무 묶음" 가중.
  - 최대 0.99로 캡 (1.0은 수동 확정 예약).
  - **부수효과**: `(Rule)-[:EVALUATES]->(ExternalTable)` 엣지 후보 수집 — Table은 analyzer DB 에 있으므로 hybrid DB에는 `ExternalTable` shadow 노드로 투영.

  **3.4 Merge & Persist** — `mapper/activity_rule_mapper.py`
  - Precedence: `lexical > structural > embedding` (동일 pair 중복 시 lexical 우선, 동일 method면 score 높은 쪽).
  - 기록:
    - `(BpmTask)-[:REALIZED_BY {confidence, method, reviewed}]->(Rule)`
    - `(ActivityMapping {task_id, rule_id, score, method, reviewed})` — 감사 로그
    - `(Rule)-[:EVALUATES {direction: READS|WRITES}]->(ExternalTable)`
  - `USES` 관계(Task → FUNCTION)는 analyzer DB 의 FUNCTION 노드와 cross-DB 로 직접 엣지 불가 → Task payload에 `functions[]` 배열로 전달, 추후 필요 시 shadow 노드화.

  **SSE 이벤트 (Phase 3)**:
  - `HybridGlossary` — `{ terms: GlossaryTerm[] }` (일괄)
  - `HybridMapping` — `{ mapping: ActivityRuleMapping }` (증분 per match)
  - `HybridTask` (재사용) — 매핑 후 `task.rules[]` / `task.functions[]` 가 채워진 upsert payload. 프론트 `addHybridTask` 가 이미 upsert 구현이라 추가 이벤트 타입 불필요.
  - `HybridReviewQueue` — `{ items: ActivityRuleMapping[] }` (일괄)
  - `HybridOntologyUpdated` — 요약 카운트 (auto_matches, review_matches, table_edges)

  **프론트 확장**:
  - `bpmn.store.js` — `hybridGlossary`, `hybridReviewQueue` state 추가 + localStorage 영속화 확장.
  - `NavigatorPanel.vue` — "Domain Glossary" 섹션(용어 + 코드 후보 칩), "Review Queue" 섹션(점수 + 페어 ID) 추가. Task 트리 내부 Rules/Mapped Functions 섹션은 기존 렌더 그대로 — 채워진 데이터가 자동 노출됨.

  **Cross-DB 전략**:
  - analyzer 그래프(`ANALYZER_NEO4J_DATABASE`)와 hybrid(기본 DB)는 같은 Neo4j 인스턴스 내 별도 database. Cypher `USE` 구문 없이 **세션 2개 병행 + Python join** 으로 처리(`mapper/rule_context.py`).
  - Table 은 analyzer DB 소유이므로 hybrid DB 에 `ExternalTable {name, session_id}` shadow 로 재생성 — 라벨 충돌 방지.

  **환경 변수 요약**:
  | Name | Default | Purpose |
  |---|---|---|
  | `HYBRID_EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI 임베딩 모델 |
  | `HYBRID_EMBED_THETA_AUTO` | `0.50` | 임베딩 자동 수용 임계치 (한↔한 GWT 도 0.45~0.55 대) |
  | `HYBRID_EMBED_THETA_REVIEW` | `0.40` | 리뷰 큐 하한 |
  | `HYBRID_EMBED_TOP_K` | `3` | Task 당 상위 K개 Rule 후보 |
  | `HYBRID_LEXICAL_MIN_HITS` | `2` | lexical 매칭 최소 informative 토큰 수 |
  | `HYBRID_LEXICAL_MAX_TOKEN_DF` | `0.35` | 이 비율 이상 Rule 에 등장하는 토큰은 자동 stopword |
  | (코드 fix) | — | 토크나이저가 한글(Hangul) 토큰을 인식하도록 패치. 한글 2 음절+ / 영문 3자+ 가 informative |

### 4.4 Phase 4 — Unified Ontology + BPM Enrichment
- Neo4j에 Task, Rule, Activity, FUNCTION, Condition, NextFlow를 단일 그래프로 통합.
- 기존 `event_storming/neo4j_client.py` 세션과 동일 DB 사용, 라벨 네임스페이스로 분리.
- **구현 메모 (2026-04-15, Phase 5 보류 · BPM 완성에 집중)**:
  - Phase 4 는 Phase 3 매핑 직후 **각 Task 를 원문 문서 + 코드 근거 양측으로 채우는 보강 단계**. 이벤트스토밍 승격(Phase 5)은 BPM 이 먼저 완성된 뒤 진행한다.

  **4.0 Document Chunking** — `mapper/document_chunker.py`
  - 1차: 헤딩 기반 분할 (`제N조/장/절/항`, `1.` / `1.1` 번호, Roman, Markdown `#`, `■◆▶` 글머리).
  - 2차 fallback: 헤딩 분할 결과가 3개 미만이거나 평균 청크 크기 > 2000자면 슬라이딩 윈도우(400자, 80자 오버랩)로 재분할.
  - 출력: `DocumentPassage {id, heading, text, page, char_start, char_end, chunk_method}`. 페이지는 `\f` (form feed) 마커 기반 추정.

  **4.1 Passage Retrieval** — `mapper/passage_retriever.py`
  - 기존 `EmbeddingCache` 재사용 (`text-embedding-3-small`). Task 텍스트 = name + description + Actor, Passage 텍스트 = heading + body.
  - **항상 top-k 반환** (`HYBRID_PASSAGE_TOP_K=2`). θ(`HYBRID_PASSAGE_THETA=0.5`)는 필터가 아니라 `low_confidence` 플래그 용도 — 한↔영 짧은 쿼리 특성상 필터링하면 대부분 소실되기 때문.
  - 결과: `(BpmTask)-[:SOURCED_FROM {score, rank, low_confidence}]->(DocumentPassage)`.

  **4.2 Condition Extraction** — `mapper/condition_extractor.py`
  - Task 단위 LLM 1회 호출. 입력: Task name/description + Phase 4.1 top-k passages + Phase 3 auto_matches Rule 의 GWT.
  - 출력: 한 줄 60자 이내 한국어 문장 최대 6개. 문서 또는 코드에 근거가 없는 항목은 거부.
  - `BpmTask.conditions` 에 list[str] 로 저장.

  **SSE 이벤트 (Phase 4)**:
  - `HybridPassages` — `{ passage_count, chunk_method }` (일괄, 청크 완료 시)
  - `HybridTask` (재사용) — 매핑 단계와 동일 이벤트로 upsert. `document_passages[]`, `conditions[]` 가 채워진 payload 를 한 번 더 흘림 (프론트 store 가 upsert 하므로 Phase 3 의 rules/functions 와 병합됨).
  - `HybridBpmEnriched` — `{ tasks_with_passages, tasks_with_conditions }` (요약)

  **프론트 확장**:
  - NavigatorPanel Task 트리에 **📄 Document Context** 섹션 추가 (Source 와 Rules 사이). 헤딩/페이지/점수 + 본문 4줄 클램프, `low_confidence` 면 dim 처리.
  - 기존 Conditions 섹션은 문자열 배열도 수용하도록 확장 (`typeof c === 'string' ? c : c.expression`).

  **Neo4j 스키마 추가**:
  - `L_DOCUMENT_PASSAGE = "DocumentPassage"` (속성: id, heading, text, page, char_start, char_end, chunk_method, session_id)
  - `R_SOURCED_FROM` 관계 (속성: score, rank, low_confidence)
  - `BpmTask.conditions: list[str]` 프로퍼티 (inline, 별도 노드 X — 단순한 자연어 문장이므로 관계 그래프로 만들 필요 없음)

  **환경 변수**:
  | Name | Default | Purpose |
  |---|---|---|
  | `HYBRID_PASSAGE_TOP_K` | `2` | Task 당 반환할 passage 개수 (항상 정확히 k개) |
  | `HYBRID_PASSAGE_THETA` | `0.5` | `low_confidence` 플래그 기준 (필터 X) |

  **PRD §3.3 BPM-first 원칙과의 정합성**:
  - Phase 4 종료 시점에 각 `BpmTask` 는 (1) 문서 원문 구절 (2) 코드 Rule/Function (3) 통합 조건 세 축을 모두 보유. Event Storming 승격(Phase 5)은 이 완성된 BPM 을 1차 소스로 보고 **역조합 없이** 추가 관계를 부착한다.

### 4.5 Phase 5 — Event Storming 승격 (새 context 착수 가이드)

> **스코프**: Phase 1~4 로 완성된 BPM(+ Rule / Function / Passage / Condition 이 붙은 각 Task)을 입력으로 받아, 이벤트 스토밍 산출물(Command / Event / Policy / Aggregate / ReadModel) 을 도출하고 **BpmTask 에 `PROMOTED_TO` 관계로 부착**한다.
>
> **핵심 원칙 (PRD §3.3)**: **역조합 금지**. BPM 이 1차 소스이며, 이벤트 스토밍은 BPM 아래 달리는 종속 레이어. "이벤트 스토밍 → BPMN XML" 방향의 합성 경로(`canvas_graph/routes/bpmn_process.py`) 는 이번 작업에서 건드리지 않는다 (Phase E 에서 deprecate).

#### 4.5.1 선결 조건 (Phase 5 시작 시 Neo4j 상태)

hybrid default DB 에 다음이 채워져 있어야 함 (세션 scope, `session_id` 로 필터):

| 라벨 / 관계 | 역할 | Phase 5 에서 쓰임 |
|---|---|---|
| `BpmActor` | 문서 기반 수행자 | **Command 의 actor / 주체** 로 승격 |
| `BpmTask` (+ `actor_ids`, `description`, `conditions`) | 업무 활동 단위 | **Event** 후보 (완료 시), **Command** 후보 (실행 시) |
| `(BpmActor)-[:PERFORMS]->(BpmTask)` | 수행자↔업무 | Command.actor 연결 |
| `(BpmTask)-[:NEXT]->(BpmTask)` | 흐름 | Event 인과 체인 재현 |
| `BpmSequence` + `CONTAINS` | Task 묶음 | 같은 컨텍스트 그룹핑 (BoundedContext 힌트) |
| `Rule` (GWT) | 코드 판단 로직 | **Policy** 본문, **Aggregate** 후보 식별 |
| `(BpmTask)-[:REALIZED_BY {reviewed}]->(Rule)` | 매핑 | Task ↔ Policy 연결 근거 |
| `Rule.source_module`, `source_function` | 함수 위치 | Aggregate 경계 추론 |
| `(Rule)-[:EVALUATES]->(ExternalTable)` | 데이터 영향 | Aggregate root 결정 + ReadModel 후보 |
| `DocumentPassage` + `SOURCED_FROM` | 문서 근거 | Command/Event 명명 시 문서 어휘 차용 |
| `BpmTask.conditions` (list[str]) | 통합 조건 | Policy 기술의 자연어 보강 |
| `HybridSession.bpmn_xml` | 최종 BPMN | 프론트 재렌더 시 참조 (Phase 5 가 쓰지는 않음) |

> **Review queue (ActivityMapping without REALIZED_BY)** 는 Phase 5 **대상 X**. 자동 승격은 auto-accepted Rule 만 사용. 사용자가 나중에 승인하면 snapshot 재조회 후 개별 승격 경로를 재실행해야 함 (또는 단순히 재ingestion).

#### 4.5.2 변환 규칙 — Scope 계층 (Global → Cluster → Per-Task)

**핵심 설계 결정**: Event Storming 요소마다 **필요한 문맥 범위가 다르다**. 한 Task 만 보고 결정할 수 있는 건(Command/Event) 이 있고, 여러 Task 를 함께 봐야 의미 있는 것(Aggregate) 이 있으며, **전체 BPM 을 봐야 잡히는 것(BoundedContext)** 이 있다. 따라서 Phase 5 는 **스코프별 서브단계**로 쪼개 실행한다.

```
        [전체 BPM]
           │
   ┌───────┴──────────┐
   │ 5.A Global        │  ← BoundedContext (업무 범위)
   │   · 모든 Task/Seq │
   │   · 모든 Actor     │
   │   · fn 클러스터   │
   └───────┬──────────┘
           │
   ┌───────┴──────────┐
   │ 5.B Cluster       │  ← Aggregate (데이터/함수 응집 단위)
   │   · Context 내 Task 묶음│
   │   · WRITES Table 공유   │
   │   · source_function 계열│
   └───────┬──────────┘
           │
   ┌───────┴──────────┐
   │ 5.C Per-Task       │  ← Command / Event
   │   · Task 1개        │
   │   · 속한 Aggregate │
   │   · 수행 Actor     │
   └───────┬──────────┘
           │
   ┌───────┴────────────┐
   │ 5.D Per-Rule-Cluster│ ← Policy
   │   · 같은 fn 계열 Rule들│
   │   · 해당 Task 매핑  │
   └───────┬────────────┘
           │
   ┌───────┴──────────┐
   │ 5.E Per-Aggregate │  ← ReadModel
   │   · Aggregate + READS Table│
   └───────┬──────────┘
           │
   ┌───────┴──────────┐
   │ 5.F Per-Task+Actor │  ← UserStory
   └───────┬──────────┘
           │
        [5.G Persist + PROMOTED_TO 부착]
```

#### 4.5.2.A Global Scope — BoundedContext 식별 (전체 BPM 필요)

**왜 전체를 봐야 하는가**: BoundedContext = "하나의 일관된 도메인 언어가 통하는 업무 범위". Task 하나하나 보면 알 수 없고, **Task 들의 클러스터링 + Actor 영역 + 함수 계열 경계**를 종합해야 잡힘.

- **입력 (Global)**:
  - 모든 `BpmTask` (name + description + actor_ids + sequence)
  - 모든 `BpmSequence` (`CONTAINS` 관계로 묶인 Task 그룹)
  - 모든 `BpmActor` (이름 + description)
  - Rule 의 `source_module` / `source_function` 집계 — 함수 prefix 계열로 그룹 (`a000_*`, `b000_*`, `b200_*`...)
  - Rule 의 `WRITES` Table 집계 — 쓰기 공유 그룹
  - (선택) `Domain Glossary` 의 `term` 리스트 — 같은 term 이 등장하는 Task 들은 같은 Context 후보
- **LLM 전략**: 1회 호출, 전체 BPM 요약을 prompt 에 담고 "업무 범위(BoundedContext) 를 N 개로 분할하고 각 Context 에 속할 Task 명 리스트를 반환" 요청. 구조화 출력.
- **출력**: `[ { context_name, description, task_ids[], actor_names[], function_family } ]`
- **휴리스틱 체크**: 각 Task 는 정확히 1 Context 에 속해야 함. Actor 영역/함수 prefix 가 Context 경계와 강하게 상관하면 고신뢰.
- **명명 규칙**: 도메인 용어로 (예: "실시간인증", "이력관리", "오류메시지 처리") — 함수 식별자 prefix 그대로 쓰지 말 것

#### 4.5.2.B Cluster Scope — Aggregate 식별 (Context 내 Task 묶음 필요)

**왜 Cluster 를 봐야 하는가**: Aggregate = "데이터 일관성 경계". **같은 Table 을 WRITES 하는 Task 들**, **같은 source_function 계열에 속하는 Rule 들** 이 묶여야 Aggregate 의 경계가 드러남.

- **입력 (Context 한 개 단위로 반복)**:
  - BoundedContext 에 속한 Task 리스트
  - 각 Task 의 `REALIZED_BY` Rule 집합
  - 각 Rule 의 `source_function`, `WRITES` Tables
- **로직 (결정적 + LLM 보조)**:
  1. **Table WRITES 기반**: 같은 Table 을 쓰는 Rule 의 source_function 들을 묶어 Aggregate 후보로. Table.name 을 Aggregate 이름 시드로 사용
  2. **source_function prefix 기반**: `b200_*`, `b400_*` 처럼 prefix 가 같으면 동일 Aggregate 군으로 묶기
  3. **LLM 최종 판단**: 후보가 여러 개면 LLM 에 "이 Table 과 함수군이 의미하는 Aggregate 이름" 질의 (도메인 용어로)
- **출력**: `[ { aggregate_name, root_table, member_functions[], task_ids[], bounded_context_id } ]`
- **예시 (실측 데이터 기준)**:
  - `AuthHistory` — WRITES `ZPAY_AP_RLTM_AUTH_HST` 공유: b200/b205/b400/b410/b210 (→ Task #4 실시간인증이력 생성/갱신)
  - `InputValidation` — a000 계열 (→ Task #0 입력값 검증)
  - `AuthDecision` — b000 계열 (→ Task #3 실시간인증결과 판정)

#### 4.5.2.C Per-Task Scope — Command + Event (Task 1개씩)

여기서부터는 Task 단위. BoundedContext 와 Aggregate 가 이미 결정돼 있으므로 **명명 일관성 보장 가능**.

- **입력 (Task 1개 단위)**:
  - 해당 Task (name / description / actor_ids / conditions)
  - 속한 BoundedContext (5.A 결정) + Aggregate (5.B 결정)
  - 수행 Actor
- **LLM 전략**: Task 당 1 호출 (또는 배치로 묶어서 1 호출). 구조화 출력으로 `Command.name`, `Event.name` 쌍 반환.
- **명명 규칙**:
  - **Command**: Task 동사구 → imperative 영문 (예: "입력값 검증" → `ValidateInput`). Glossary `code_candidates` 가 있으면 우선 참조
  - **Event**: Command 과거분사형 (`InputValidated`)
- **출력**: `[ { task_id, command: {name, actor, aggregate}, event: {name, aggregate} } ]`

#### 4.5.2.D Per-Rule-Cluster Scope — Policy (같은 fn 계열 Rule 묶음)

**왜 Rule 계열을 묶어야 하는가**: 한 함수의 14개 BL 을 각각 Policy 로 만들면 노이즈. 같은 `source_function` 의 Rule 들은 보통 **하나의 Policy (트리거 조건은 같고 then 분기만 다름)** 로 합치는 게 맞음.

- **입력 (function 계열 단위로 반복)**:
  - 같은 `source_function` 을 가진 Rule 묶음
  - 해당 Rule 이 매핑된 Task (`REALIZED_BY` 역방향)
  - 속한 Aggregate
- **로직**:
  1. Rule 의 `when` 텍스트 유사도 그룹핑 (동일 when = 같은 Policy 의 분기)
  2. LLM 에 "이 Rule 군을 하나의 Policy 로 표현. when = 트리거, then = action" 질의
  3. 분기가 명확히 독립적이면 복수 Policy 로 분할
- **출력**: `[ { policy_name, trigger, actions[], aggregate_id, rule_ids[] } ]`

#### 4.5.2.E Per-Aggregate Scope — ReadModel (선택)

- **입력**: Aggregate + 그 안의 Rule 들이 READS 하는 Table 집합
- **출력**: `[ { readmodel_name, source_aggregate, query_keys } ]`
- v0.1 에선 선택적 — Rule 이 WRITES 없이 READS 만 하는 경우가 명확할 때만 생성

#### 4.5.2.F Per-Task+Actor Scope — UserStory (선택)

- **입력**: Task + 수행 Actor + Task.description + Task.conditions
- **포맷**: "As a {Actor}, I want to {Task 동사구} so that {business goal from conditions}"
- **출력**: `[ { story_id, actor, task_id, narrative } ]`

#### 4.5.2.G 요약표 — 스코프별 필요 입력

| 서브단계 | 생성 요소 | Scope | 필요 입력 | LLM 호출 단위 |
|---|---|---|---|---|
| 5.A | BoundedContext | **Global** | 모든 Task+Seq+Actor+fn prefix+Tables 집계 | **1회** (전체 요약) |
| 5.B | Aggregate | **Cluster** (Context 내) | Context 내 Task+Rule+WRITES Tables+fn 계열 | **Context 당 1회** |
| 5.C | Command+Event | **Per-Task** | Task + Aggregate + Actor | **Task 당 1회** (또는 배치) |
| 5.D | Policy | **Per-Rule-Cluster** (같은 fn) | fn 계열 Rule + Task + Aggregate | **함수 계열 당 1회** |
| 5.E | ReadModel | Per-Aggregate | Aggregate + READS Tables | 선택 |
| 5.F | UserStory | Per-Task+Actor | Task + Actor + conditions | 선택 |

**LLM 호출 총량 추정** (방금 데이터 기준: 7 Task, 52 Rule, 11 fn 계열, 예상 3 BoundedContext):
- 5.A: 1 회
- 5.B: 3 회 (Context 당)
- 5.C: 7 회 (Task 당, 또는 배치 1회)
- 5.D: 11 회 (fn 계열 당, 또는 병합 후 감소)
- 5.E/F: 선택
- **총합: ~20 회** (배치화하면 5~6 회로 축소 가능)

#### 4.5.3 출력 스키마 (기존 event_storming 재사용)

신규 라벨 만들지 말 것. 기존 `api/features/ingestion/event_storming/` 의 노드 재사용:
- `Command`, `Event`, `Policy`, `Aggregate`, `ReadModel`, `UserStory`, `BoundedContext`
- 기존 `event_storming/neo4j_client.py` / `schema` 를 조회해 실제 라벨·속성 확인 후 맞출 것

연결 엣지 (이번 PRD 에서 추가):
```
(BpmTask)-[:PROMOTED_TO]->(Command)
(BpmTask)-[:PROMOTED_TO]->(Event)
(Rule)-[:PROMOTED_TO]->(Policy)
(ExternalTable)-[:PROMOTED_TO]->(Aggregate)   # 또는 Rule 경유
```

`PROMOTED_TO` 속성:
- `method`: `"auto"` | `"manual"` | `"llm"` (기본 `auto`)
- `confidence`: 생성 시 LLM 이 평가한 신뢰도 (0.0~1.0)
- `reviewed`: 사람이 확인했는지 (기본 `false`)

#### 4.5.4 구현 위치 (스텁 이미 존재)

```
api/features/ingestion/hybrid/event_storming_bridge/
└── promote_to_es.py          # 현재 stub (return {"promoted": 0})
```

교체할 함수: `promote_to_event_storming(session_id)` — **§4.5.2 의 스코프 순서를 그대로 따른다**:

1. `fetch_session_snapshot(session_id)` 로 BPM 전체 상태 로드 (이미 구현됨, `neo4j_ops::fetch_session_snapshot`)
2. **5.A Global** — `identify_bounded_contexts(snapshot)` — LLM 1회 → `[BoundedContextCandidate]`
3. **5.B Cluster** — Context 당 `identify_aggregates(context, snapshot)` — LLM 1회씩 (Table WRITES + fn prefix 휴리스틱 → LLM 최종 이름)
4. **5.C Per-Task** — `name_command_event_pairs(tasks, aggregates)` — 배치 LLM 1회 (전체 Task) 또는 Task 당 1회
5. **5.D Per-Rule-Cluster** — source_function 별로 `summarize_policy(rules, task)` — 계열 당 1회
6. **5.E / 5.F** — (선택) ReadModel / UserStory
7. **5.G Persist** — 기존 `event_storming` 쪽 `neo4j_client` 로 노드 저장 + `PROMOTED_TO` 엣지 부착 — **라벨 충돌 주의** (아래 §4.5.6 Open Question #1 참조)
8. 각 서브단계마다 SSE 이벤트 발행 (다음 섹션 §4.5.5)

구현 힌트:
- Task DTO 가 이미 `rules[]` / `functions[]` / `document_passages[]` / `conditions[]` 를 보유한 enriched 상태이므로 snapshot 하나로 모든 서브단계 입력이 해결됨 — 추가 Neo4j 쿼리 거의 불필요
- **중복 제안 병합**: 5.C 에서 다른 Task 가 같은 Aggregate 를 가리키면 이름 정규화 후 dedupe
- **5.A 가 실패하면 폴백**: BoundedContext 를 식별 못 하면 전체를 단일 Context 로 취급하고 5.B~5.F 진행 (퇴행 모드)
- **재실행 멱등성**: 모든 쓰기는 `MERGE` 로. 같은 (session_id, element_name) 은 덮어쓰기
- Command 와 Event 는 **항상 쌍** (BPMN Command-Event 룰)
- Rule 50+ 를 한 번에 LLM 에 넣지 말 것 — 5.D 에서 함수 계열 별로 분할

#### 4.5.5 SSE 이벤트 계약 (신규) — 스코프 진행 상황 노출

각 서브단계 완료 시점에 별도 이벤트를 흘려 프론트가 진행 상태를 표시할 수 있도록:

| Type | 단계 | 의미 | payload |
|---|---|---|---|
| `HybridBoundedContexts` | 5.A 종료 | BoundedContext 후보 식별 | `{ contexts: [{name, description, task_ids[], actor_names[]}] }` |
| `HybridAggregates` | 5.B 진행 | Aggregate 1개 증분 or 일괄 | `{ aggregates: [{name, root_table, member_functions[], task_ids[], bounded_context_id}] }` |
| `HybridPromoted` | 5.C/D 진행 | per-task 또는 per-rule-cluster 승격 | `{ task_id?, promoted: { commands[], events[], policies[], aggregates[] } }` |
| `HybridEventStormingComplete` | 5.G 종료 | 전체 카운트 요약 | `{ bounded_context_count, aggregate_count, command_count, event_count, policy_count, readmodel_count?, userstory_count? }` |
| `HybridTask` (재사용) | 5.C/D 이후 | Task.promoted 필드 upsert | 기존 HybridTask payload 에 `promoted: {commands, events, policies, aggregates}` 추가 → 프론트 Inspector 의 "Event Storming" 섹션 칩 자동 렌더 |

프론트 (이미 준비됨):
- `HybridTaskInspector.vue` 는 `task.promoted` 가 있으면 Cmd/Evt/Pol/Agg 칩을 표시하는 섹션을 이미 보유 (§4.1 노드 내부 섹션 표 참고)
- 추가 UI 없이 payload 만 흘리면 자동 렌더

#### 4.5.6 Open Questions (Phase 5 착수 전 결정 필요)

1. ~~**`Event` 라벨 의미 충돌** ⚠️~~ → **해결 (2026-04-15)**: **pdf2bpmn 측 노드를 `Bpmn*` 로 rename** 하는 선택지로 채택.
   - 구현: `neo4j_ops::relabel_pdf2bpmn_nodes(session_id)` — Phase 1 `save_bpm_skeleton` 직후 호출. pdf2bpmn 만 갖는 프로퍼티(`event_type` / `gateway_type` / `proc_id`) 로 식별해 `:Event → :BpmnEvent`, `:Gateway → :BpmnGateway`, `:Process → :BpmnProcess` 로 relabel + `session_id` 태그.
   - event_storming 의 `:Event` (프로퍼티: `key`/`id`/`displayName`) 는 식별 조건에 걸리지 않아 영향 없음.
   - 이후 Phase 5 에서 도메인 `:Event` 를 생성할 때 **완전한 1:1 의미 일관성** 확보.
   - `ALL_HYBRID_LABELS` 에 `BpmnEvent` / `BpmnGateway` / `BpmnProcess` 추가 → reset 이 이들도 함께 청소.
2. **Aggregate 경계 추론 방식** — `source_function` 계열 기반(`b200_*`, `b400_*`) vs Table 쓰기 기반(`WRITES` 엣지 기반) vs LLM 판단. **하이브리드** 가 현실적 (후보 뽑은 뒤 LLM 이 이름 붙이기).
3. **Review queue 항목의 처리** — 자동 승격 대상 제외 확정. 사용자가 나중에 accept 하면 실시간 승격할지, 재ingestion 요구할지?
4. **멱등성** — 같은 세션 재실행 시 승격 엣지/노드 MERGE 로 동일하게 유지되는지. Phase 5 결과물에도 `session_id` 를 달아 격리 권장.
5. **Reset 정책** — `DELETE /api/ingest/hybrid/reset` 이 이벤트 스토밍 노드도 정리할지. 현재는 **ALL_HYBRID_LABELS 만** wipe → event_storming 라벨은 남음. Hybrid 승격물은 삭제되지 않아 ghost 가 생길 수 있음. `reset` 에 event_storming-session-tagged 노드 추가 청소 필요.
6. **프론트 쪽 event_storming 탭과의 관계** — hybrid 경로로 생성된 ES 산출물이 기존 "Event Modeling" / "Design" 탭에서 보여야 하는지. 보여야 한다면 탭별 필터 로직 검토 필요.

#### 4.5.7 구현 체크리스트 (새 context 기준, §4.5.2 스코프 순서 준수)

**준비**
- [ ] `Event` 라벨 충돌 처리 결정 적용 (§4.5.6 #1) — `session_id` 필터링 전략 확정
- [ ] 기존 `event_storming/neo4j_client.py` 라벨/속성 스펙 파악 (Command/Event/Policy/Aggregate/ReadModel/UserStory/BoundedContext)
- [ ] `pydantic` 출력 스키마 정의 — `_BoundedContextResult`, `_AggregateResult`, `_CommandEventPair`, `_PolicyResult` 등

**스코프별 구현** (`event_storming_bridge/promote_to_es.py` 내부)
- [ ] **5.A** `identify_bounded_contexts(snapshot)` — Global LLM 1회
- [ ] **5.B** `identify_aggregates(context, snapshot)` — Context 당 1회 (Table WRITES + fn prefix 휴리스틱 → LLM 이름 확정)
- [ ] **5.C** `name_command_event_pairs(tasks, aggregates)` — Task 배치 1회 또는 Task 당 1회
- [ ] **5.D** `summarize_policy(rule_cluster, task, aggregate)` — fn 계열 당 1회, `when` 유사도로 분기 그룹핑
- [ ] **5.E** (선택) `derive_readmodels(aggregate, read_tables)`
- [ ] **5.F** (선택) `compose_userstory(task, actor, conditions)`
- [ ] **5.G** `save_promotions(session_id, results)` (`ontology/neo4j_ops.py`) — 노드 저장 + `PROMOTED_TO` 엣지 부착

**파이프라인 연결**
- [ ] `hybrid_workflow_runner.py` Phase 5 블록 실구현 — §4.5.5 SSE 이벤트 5종 발행
- [ ] `fetch_session_snapshot` 응답에 `promoted` 필드 추가 (Bound/Agg/Cmd/Evt/Pol 카운트 + id + 이름 리스트)
- [ ] `ALL_HYBRID_LABELS` 가 event_storming 라벨 추가 wipe 해야 할지 결정 (Open Question #5) → reset 업데이트

**검증**
- [ ] 폴백 경로 확인 — 5.A 실패 시 단일 Context 로 퇴행 진행
- [ ] 실 데이터 1 세션 end-to-end — 7 Task / 52 Rule 입력 → 예상 산출 (§4.5.8) 와 대조
- [ ] 프론트 HybridTaskInspector 의 Event Storming 섹션 실제 데이터로 렌더 확인
- [ ] 멱등성 — 같은 session_id 재실행 시 중복 생성 없음 (MERGE)
- [ ] Phase 5 성공 지표 (PRD §10) 측정 — 사람이 그대로 채택한 비율

#### 4.5.8 참고 — 실제 세션 예 (방금 테스트 데이터)

7 Tasks (입력값 검증 / 원장등록대상 조회 / 카드사코드 추출 / 실시간인증결과 판정 / 실시간인증이력 생성/갱신 / 인증오류메시지 조립 / 결과 반환) + 52 Rules (a000/b000/b200/b205/b400/b410/b210/b800/zapamcom10060 등 11 함수) 를 입력으로 받았을 때 예상 산출물:

- Aggregate 후보: `AuthHistory` (b200/b205/b400/b410/b210 공통 = `ZPAY_AP_RLTM_AUTH_HST` 테이블), `InputValidation` (a000), `MainProcess` (b000)
- Command: `ValidateInput`, `QueryLedgerTargets`, `ExtractCardIssuerCode`, `DetermineAuthResult`, `CreateAuthHistory`, `UpdateAuthHistory`, `BuildErrorMessage`, `ReturnResult`
- Event: 각 Command 에 대응하는 과거분사형
- Policy: Rule 의 GWT 기반, b000 계열 14개 Rule → "인증 결과 판정 Policy" 1~2개로 집약 권장

---

## 5. 데이터 모델 (Neo4j 스키마 확장)

### 5.1 신규 노드
| Label | 주요 속성 | 비고 |
|---|---|---|
| `BpmTask` | id, name, description, sequence_index, actor_ref | 문서 기반 |
| `BpmSequence` | id, name | Task 묶음 |
| `Rule` | id, given, when, then, source_function, source_module, confidence, `title`, `context_cluster`, `es_role`, `es_role_confidence` | 코드 기반. `title`=BL.title, `context_cluster`=Phase 2.5 BC 태그, `es_role`∈{invariant/validation/decision/policy/query/external}=Phase 2.6 역할 |
| `ActivityMapping` | id, task_id, rule_id, score, method | 매핑 메타 |

### 5.2 신규 관계
- `(Actor)-[:PERFORMS]->(BpmTask)`
- `(BpmTask)-[:NEXT]->(BpmTask)`
- `(BpmTask)-[:REALIZED_BY {confidence}]->(Rule)`
- `(BpmTask)-[:USES]->(FUNCTION)`
- `(Rule)-[:EVALUATES]->(Column|Table)`
- `(BpmTask)-[:PROMOTED_TO]->(Command|Event|Policy|Aggregate)` (Phase 5 후)

### 5.3 기존 분석 그래프와의 관계
- 기존 `FUNCTION`, `BusinessLogic`, `Actor`, `Table`, `Column` 노드는 **읽기 전용**으로 참조.
- 신규 파이프라인은 기존 노드를 수정하지 않는다.

---

## 6. 모듈 구조

```
api/features/ingestion/hybrid/
├── __init__.py
├── router.py                      # /api/ingest/hybrid/* 라우트
├── hybrid_workflow_runner.py      # 5 phases 오케스트레이션
├── document_to_bpm/               # 외부 A2A 우선 + 네이티브 fallback
│   ├── __init__.py                # extract_bpm_skeleton 디스패처
│   ├── a2a_client.py              # A2AClient 래퍼 (execute/status/result/events)
│   ├── a2a_adapter.py             # BPMN XML → BpmSkeleton 파서
│   ├── config.py                  # PDF2BPMN_A2A_URL 등 env
│   ├── entity_extractor.py        # 네이티브 LLM 추출기 (fallback)
│   └── bpmn_builder.py            # BpmSkeleton → BPMN XML (증분 렌더용)
├── code_to_rules/
│   ├── rule_extractor.py          # analyzer_graph → GWT Rule
│   └── rule_filters.py            # 인프라/보일러플레이트 제외
├── mapper/
│   ├── embeddings.py
│   ├── activity_rule_mapper.py
│   ├── bc_identifier.py            # Phase 2.5 — BC pre-tagging
│   ├── es_role_tagger.py           # Phase 2.6 — DDD/ES role classification
│   ├── glossary_extractor.py       # Phase 3.0
│   ├── lexical_matcher.py          # Phase 3.1 (BC-aware)
│   ├── embedding_matcher.py        # Phase 3.2 (BC prefix)
│   ├── structural_booster.py       # Phase 3.3 (same-BC bonus)
│   ├── rule_context.py
│   ├── passage_retriever.py        # Phase 4.1
│   ├── document_chunker.py         # Phase 4.0
│   ├── condition_extractor.py      # Phase 4.2
│   └── review_queue.py
├── ontology/
│   ├── schema.py                  # 노드/관계 라벨 상수
│   └── neo4j_ops.py
└── event_storming_bridge/
    └── promote_to_es.py           # Task → Command/Event/Policy/Aggregate
```

기존 파일은 **불변**. 오직 `api/main.py`에 신규 router를 include.

---

## 7. API

### 7.1 `POST /api/ingest/hybrid/upload`
- multipart 필드:
  - `file` (PDF) **또는** `text` (텍스트 직접 입력) — 문서 소스
  - `analyzer_graph_ref` (선택, 현재 informational)
  - `display_language` (`ko`/`en`)
- 응답: `{ session_id, content_length, source_type, preview }`
- **전제**: analyzer 그래프는 **외부(robo-data-analyzer)에서 Neo4j 로 사전 import 된 상태**여야 함. 본 파이프라인은 analyzer DB 를 read-only 로만 참조한다. 덤프 파일을 API 로 로드하는 기능은 제공하지 않는다 — Neo4j 바이너리 `.dump` 는 `neo4j-admin load`(인스턴스 중지 필요)만 지원하고, Cypher 텍스트 replay 는 운영 부담 대비 이득이 작아 범위에서 제외. analyzer 입력 연동은 별도 시스템의 책임.
- 기본 DB(hybrid + event_storming 쪽) 는 이 엔드포인트가 건드리지 않는다 — 프론트가 직전에 `DELETE /api/ingest/clear-all` 로 정리.

### 7.2 `GET /api/ingest/hybrid/stream/{session_id}`
- 기존 ingestion SSE 포맷(`ProgressEvent`) 재사용. Phase ID: `hybrid.document_bpm`, `hybrid.code_rules`, `hybrid.mapping`, `hybrid.ontology`, `hybrid.event_storming`.
- **이벤트 payload type 카탈로그** (payload.data.type 기준, 2026-04-15 기준):

  | Type | 단계 | 의미 | 프론트 처리 |
  |---|---|---|---|
  | `HybridActor` | Phase 1 | Actor 1개 증분 | `bpmnStore.addHybridActor` |
  | `HybridTask` | Phase 1/3/4 | Task upsert (payload 가 성장 — Phase 1 기본 → Phase 3 rules/functions → Phase 4 document_passages/conditions) | `bpmnStore.addHybridTask` (기존 항목 교체) |
  | `HybridBpmnComplete` | Phase 1 종료 | BPMN XML 및 actors/tasks 최종 세트 | `bpmnStore.setHybridBpmn` |
  | `HybridRule` | Phase 2 | Rule 1개 증분 | `bpmnStore.addHybridRule` |
  | `HybridRulesComplete` | Phase 2 종료 | Rule 리스트 전체 | `bpmnStore.setHybridRules` |
  | `HybridBoundedContextTagged` | Phase 2.5 종료 | BC 클러스터 분포 + 태그된 rule 수 | progress only (UI는 Rule.context_cluster 필드로 자동 표시) |
  | `HybridEsRoleTagged` | Phase 2.6 종료 | ES 역할 분포 + 태그된 rule 수 | progress only (UI는 Rule.es_role 필드로 자동 표시) |
  | `HybridGlossary` | Phase 3.0 | 용어집 일괄 | `bpmnStore.setHybridGlossary` |
  | `HybridMapping` | Phase 3 | 매핑 1건 증분 (진행 표시용) | progress only |
  | `HybridReviewQueue` | Phase 3 | 임계치 미달 매핑 리스트 (`θ_review ≤ score < θ_auto`) | `bpmnStore.setHybridReviewQueue`. 클릭 → `HybridReviewModal` → 승인/거부 엔드포인트 호출 |
  | `HybridOntologyUpdated` | Phase 3 종료 | 매핑 카운트 요약 | progress only |
  | `HybridPassages` | Phase 4.0 | 청크 개수 + 방식 | progress only |
  | `HybridBpmEnriched` | Phase 4 종료 | 문서/조건 보강된 Task 카운트 | progress only |

### 7.2.4 `GET /api/ingest/hybrid/session/{session_id}/snapshot` (2026-04-15 추가)
- 세션 한 개의 **전체 하이드레이션 페이로드** 반환: `{ session_id, bpmn_xml, actors, tasks(enriched), sequences, rules, glossary, review_queue }`.
- Task 객체는 이미 `rules[]`, `functions[]`, `document_passages[]`, `conditions[]` 가 채워진 상태 (SSE payload 계약과 동일 shape).
- **프론트 localStorage 제거 배경**: 기존엔 `hybrid.bpmn.v1` 키로 actors/tasks/rules/etc. 전체를 복제 저장했는데, DB 와의 동기화 사각지대 + stale 데이터 위험 + quota 부담이 있어 제거. 이제 localStorage 는 **`hybrid.session_id` (세션 식별자 한 개만)** 보관하고, 실제 데이터는 매 콜드로드 시 이 snapshot 엔드포인트로 DB 에서 가져온다 (`bpmnStore.rehydrateHybrid()`).
- Review queue 구분: `ActivityMapping` 노드 중 `(BpmTask)-[:REALIZED_BY]->(Rule)` 엣지가 **없는** 것들을 필터링해 반환.
- 새로 추가된 노드: `L_HYBRID_SESSION = "HybridSession"` — 세션 마커로 `bpmn_xml` 과 `updated_at` 보유. Phase 1 종료 직후 `save_session_bpmn_xml()` 이 **최종 결정된 BPMN XML** (A2A 결과 또는 native fallback) 을 저장. `save_bpm_skeleton` 시점에는 skeleton.bpmn_xml 이 비어있을 수 있어 별도 update 경로 필요 (2026-04-15 버그 수정 — 새로고침 후 캔버스가 비던 원인).

### 7.2.3 Review Queue 승인/거부 (2026-04-15 추가)
- `POST /api/ingest/hybrid/review/{session_id}/{task_id}/{rule_id}/accept` — 리뷰 큐 매핑을 `(BpmTask)-[:REALIZED_BY {reviewed:true}]->(Rule)` 로 승격. `ActivityMapping.reviewed = true` 로 마크.
- `POST /api/ingest/hybrid/review/{session_id}/{task_id}/{rule_id}/reject` — 해당 `ActivityMapping` 노드를 DETACH DELETE. 다시 제안되지 않음.
- 프론트 트리거: Navigator 의 Review Queue 항목 클릭 → `HybridReviewModal` 열림 → Task 설명 + Rule GWT 표시 → 승인/거부 버튼.
- 승인 시: 로컬 store 도 즉시 업데이트 (`hybridReviewQueue` 에서 제거 + `hybridTasks[idx].rules` 에 추가) → Task Inspector 에 바로 반영.

### 7.2.2 `GET /api/ingest/hybrid/debug/{session_id}` (diagnostic)
- 한 세션에 생성된 모든 hybrid 라벨의 노드 개수 + 상위 3개 샘플 + 주요 관계(`PERFORMS`, `NEXT`, `REALIZED_BY`, `EVALUATES`, `SOURCED_FROM`) 카운트를 반환.
- 생성 결과 검증 / Phase 별 산출물 누락 여부 확인에 사용.
- Cypher 대안(세션 스코프):
  ```cypher
  MATCH (n) WHERE n.session_id = $sid
  RETURN labels(n)[0] AS label, count(n) AS c ORDER BY c DESC
  ```

### 7.2.1 `GET /api/ingest/hybrid/pdf/{filename}`
- 업로드된 PDF 를 외부 A2A 서비스가 httpx 로 다운로드할 수 있도록 서빙.
- `filename` 은 업로드 시 부여된 `{uuid}_{original}` 형태. 경로 탈출 방지를 위해 `Path(name).name` 만 사용.
- `a2a_pdf_tmp_dir()` 안에 실존하는 파일만 `FileResponse(application/pdf)` 로 반환, 없으면 404.

### 7.3 관리
- `POST /api/ingest/hybrid/{session_id}/cancel|pause|resume` — 기존 세션 관리자와 동일 계약.

### 7.3.1 Clear 정책 (중요, 2026-04-15 수정)
- **`DELETE /api/ingest/hybrid/reset`** — 프론트 `startHybridIngestion()` 이 업로드 직전 호출. `ALL_HYBRID_LABELS`(BpmTask / BpmActor / BpmSequence / Rule / GlossaryTerm / DocumentPassage / ActivityMapping / ExternalTable) 만 `DETACH DELETE`. analyzer 노드(`BusinessLogic` / `Actor` / `Table` / FUNCTION 등) 와 event_storming 산출물은 **보존**.
- **왜 바뀌었나**: 기존엔 `DELETE /api/ingest/clear-all` (default DB 전체 wipe) 을 호출했는데, `ANALYZER_NEO4J_DATABASE` 가 설정되지 않아 analyzer 와 hybrid 가 **같은 default DB 를 공유**하는 환경에서는 analyzer 데이터까지 날아가 Phase 2/3 가 빈 결과를 내는 문제가 있었다 (2026-04-15 실제 테스트에서 재현됨).
- **권장 배포 구성**: analyzer 그래프를 `analyzer` 같은 named DB 로 분리하고 `ANALYZER_NEO4J_DATABASE=analyzer` 설정. 같은 DB 공유도 이제 위 reset 엔드포인트로 안전하지만, 격리가 본래 의도된 설계.
- **프론트 스토어**: `bpmnStore.clear()` + `beginHybrid()` 가 localStorage `hybrid.bpmn.v1` 및 관련 ref 를 모두 초기화.

### 7.4 개발용 테스트 진입점 (Dev-only)
- 위치: 프론트 **문서 업로드 모달** (`frontend/src/features/requirementsIngestion/ui/RequirementsIngestionModal.vue`)
  - 현재 입력 모드: `file / text / jira / figma / analyzer`
  - 파일 업로드 영역의 "샘플 사용" 옆에 **`🧪 테스트 실행 (Hybrid)` 버튼** 추가
- 버튼 동작:
  1. 현재 모달에서 선택된 PDF/텍스트(없으면 내장 샘플) + `analyzer_graph_ref`(있으면 현재 세션의 분석 그래프 ID)를 묶어
  2. `POST /api/ingest/hybrid/upload`로 전송
  3. 반환된 `session_id`로 `GET /api/ingest/hybrid/stream/{session_id}` SSE 구독
  4. 진행 상황을 기존 플로팅 패널(`ProgressEvent`)에 그대로 표시
- 목적: 새 파이프라인을 기존 UI/세션 관리자와 **병렬로** 검증. 기본 Ingest 경로에는 영향 없음.
- 노출 제어: 환경 변수 `VITE_HYBRID_INGEST_ENABLED`로 토글 (기본 false, 개발/스테이징에서만 노출).
- 정식 병합 시(Phase E) 이 테스트 버튼은 제거하고 `source_type: "hybrid"` 플래그로 대체.

---

## 8. 롤아웃 / 마일스톤

### 8.1 현재 상태 스냅샷 (2026-04-20)

| Phase | 범위 | 상태 | 완료 기준 | 비고 |
|---|---|---|---|---|
| A | Phase 1 (문서→BPM) | ✅ 완료 | 문서 업로드 → BpmTask 그래프 + BPMN 캔버스 렌더 | A2A + native fallback |
| B | Phase 2 (코드→Rule) | ✅ 완료 | analyzer BL → Rule 52개 추출 + 인프라 필터 | 멱등, `title` 필드 보존 |
| **B'** | **Phase 2.5 (BC 사전 태깅)** | **✅ 완료** | Rule에 `context_cluster` 부여, 8 클러스터 분포 확보 | §4.2.5. BC=1 collapse 해소. CALLS 그래프 기반 orchestrator 감지 + caller 상속 (2026-04-20) |
| **B''** | **Phase 2.6 (DDD/ES 역할 태깅)** | **✅ 완료** | Rule에 `es_role` 부여, 5개 역할 분포(invariant+decision 통합), 저신뢰 0건 | §4.2.6. LLM 미사용 결정론 |
| C | Phase 3 (3단 매핑) | ✅ 완료 | lexical → embedding → structural, context bonus + 부모 노드(모듈/호출자) embedding 라인 | Phase 2.5 연계 context-aware |
| C' | Phase 4 (BPM Enrichment) | ✅ 완료 | Task 당 passage top-k + LLM conditions | DB 가 single source of truth |
| | BL 수동 제어 UI | ✅ 완료 | Inspector 역할 드롭다운·Task 이동/제거 + 통합 "미매핑/Review" 풀 + BC Rules Modal | §6.4, §6.5 of Architecture doc |
| | 부모 노드 탐색 (RuleContext) | ✅ 완료 | callers / callees / parent_module / parent_package. 멀티모듈 대응 | CALLS·HAS_FUNCTION·BELONGS_TO_PACKAGE 조인 |
| D | Phase 5 (Event Storming 승격) | ⚠️ 재실행 필요 | 이전 1차 결과(BC=1, Policy=0)는 BC 태깅 도입 전 기록. 2.5/2.6 태그 반영 후 재실행 필요 | Phase 5 내부 로직이 `context_cluster` + `es_role` 을 primary input으로 쓰도록 수정 필요 (§8.2.3) |
| | 전역 Rule Manager Panel | ⏳ 부분 | Task 단위 + BC 단위 제어는 완료, 세션 전체 조망·배치 수정·exclude/BC 수정은 미구현 | §8.2.2 |
| | 비결정성 | ℹ️ 자연 현상 | LLM 특성 — 필요 시 temperature/캐싱으로 수렴 가능 | §8.2.1 |
| E | 기존 workflow 병합 | ⏳ 미착수 | `source_type="hybrid"` 정식 라우팅, Dev 버튼 제거 |

#### Phase 5 검증 기록 — 개선 전 (2026-04-16, Phase 2.5/2.6 적용 **이전**)

> **아카이브**. 아래는 Phase 2.5(BC 태깅) + 2.6(ES 역할 태깅) 도입 전 1차 실행 결과로, BC=1 collapse 문제를 기록용으로 보존. 현재 DB 상태는 아래 "Phase 2.5/2.6 검증 결과 (2026-04-20)" 를 따름. Phase 5는 새 태그 기반으로 재실행해야 정상 Policy/BC 수 확보 가능.

| 산출물 | 개수 | 상태 |
|---|---|---|
| UserStory | 9 | ✅ (Task × fn_cluster, DF 컷오프 + Top-1 attribution 적용) |
| Event | 기존 phase 생성 | ✅ |
| BoundedContext | **1** | ⚠️ LLM 이 단일 도메인으로 묶음 — Phase 2.5 로 해소 예정 |
| Aggregate | **8** | ✅ |
| Command | **9** + EMITS edges | ✅ |
| ReadModel | 8 | ✅ |
| Policy | **0** | ⚠️ BC 1개 → cross-BC 불가 — Phase 2.5+2.6 으로 해소 예정 |
| PROMOTED_TO 엣지 | **9** (BpmTask → UserStory) | ✅ 역추적 정상 |

#### Phase 2.5 / 2.6 검증 결과 (2026-04-20, 52 rules / 7 Task)

**Phase 2.5 — 8 BC 클러스터 분포** (이전 BC=1 collapse 대비 개선):
- 인증이력관리 18 · 입력값검증 12 · 인증결과판정 7 · 오류메시지처리 7 · 실시간인증진입 3 · 공통코드검증 2 · 간편결제사검증 2 · 카드사정보검증 1

**Phase 2.6 — 역할 분포 (저신뢰 0건)**:
- validation 18 (avg 0.82) · decision 14 (0.86) · invariant 11 (0.80) · policy 5 (0.84) · query 3 (0.76) · external 1 (0.90)

**의미 정합성 (BC × Role 대각 지배성)**:
- 이력관리 → invariant 11/18 ✅  
- 입력값검증 → validation 12/12 ✅  
- 인증결과판정 → decision 7/7 ✅  
- 오류메시지처리 → policy 4/7 ✅  
- 공통코드검증 → query 2/2 ✅  
- 카드사정보검증 → external 1/1 ✅

**Task 매핑 정합성 (Phase 3 연계)**:
- "실시간인증이력 생성/갱신" → invariant 10, decision 4, validation 2 (단일 aggregate behavior에 집중 — 정상)
- "입력값 검증" → validation 13 (dominant) + 타 role 혼재 — Phase 3 과매칭 잔재. 사용자 수동 정리(§6.4) + 장차 전역 Rule Manager(§8.2.2) 로 대응.

> 상세 설계: `Hybrid_Phase5_EventStorming_Promotion.md` 참조. Phase 5 재실행 후 신규 기록 추가 예정.

### 8.2 개선 과제 — 남은 작업만

완료된 개선은 §4 (Phase 별 본문) 에 정식 기술되었으므로 여기서는 **미완 항목만** 남긴다. 완료분은 §8.1 상태 표에서 ✅ 로 추적.

#### 8.2.1 비결정성 — LLM 기반 파이프라인의 자연스러운 특성 (관찰)

같은 (문서 + analyzer 그래프) 입력으로 재실행해도 Task 당 매핑 Rule 수가 매번 다를 수 있다. 이는 Phase 1 (A2A/네이티브 LLM), Phase 3.0 (Glossary LLM), Phase 4.2 (Conditions LLM), Phase 2.5 의 LLM naming 단계가 비결정적인 LLM 호출이기 때문이며, **결함이 아니라 자연스러운 현상**이다.

- Phase 2 Rule 추출(BL 읽기), Phase 2.5 prefix/재분배(LLM 제외), Phase 2.6 역할 분류는 **모두 결정론적**.
- Phase 3.2 임베딩 벡터 자체도 결정적 (같은 입력 = 같은 벡터).
- 변동은 LLM 생성 텍스트(Task 이름, Glossary, BC 이름, Conditions)에서 발생.

필요 시 `temperature=0` / `seed` 전파, 결과 캐싱 등으로 수렴도를 높일 수 있으나 현재는 개선 과제로 분류하지 않는다.

---

#### 8.2.2 전역 Rule Manager Panel — 세션 단위 BL 관리

> **부분 구현**: Task Inspector 내 수동 제어(§6.4)와 통합 "미매핑 / Review" 풀(§6.2)은 완료. 아직 없는 건 **세션 내 전체 Rule 을 한 화면에 펼쳐 필터·검색·배치 수정할 수 있는 전용 패널**.

**현재 가능한 것** (Task / Pool 단위):
- Rule 카드 배지로 역할 변경 (PATCH `/rule/{rid}/es-role`)
- ⋯ 메뉴로 다른 Task 로 이동 / 현 Task 에서 제거
- 통합 풀에서 미매핑 Rule 을 특정 Task 에 연결

**아직 없는 것** (전역 관리자 뷰):

| 기능 | 설명 |
|---|---|
| 전체 Rule 조회 + 다중 필터 | source_function / BC / es_role / 매핑 상태(매핑됨·미매핑·제외됨) 조합 검색 |
| 배치 제어 | 여러 Rule 선택 → 한 번에 Task 이동, 역할 변경, 제외 |
| Rule 제외·복원 | "이 Rule 은 업무 로직이 아님" → `Rule.excluded = true` → 매칭·승격에서 skip. 복원 가능 |
| BC 태그 수동 수정 | Phase 2.5 자동 태깅을 사용자가 드롭다운으로 오버라이드 |

**예상 엔드포인트 (신규)**:
```
POST   /api/ingest/hybrid/rule/{sid}/{rule_id}/exclude
POST   /api/ingest/hybrid/rule/{sid}/{rule_id}/restore
PATCH  /api/ingest/hybrid/rule/{sid}/{rule_id}/context-cluster
GET    /api/ingest/hybrid/rules/{sid}       # 전역 조회 (필터 쿼리 파람)
```

**영향 파일**: `neo4j_ops.py` (exclude/restore/BC patch CRUD), `router.py` (+3 endpoints), `RuleManagerPanel.vue` (신규), `bpmn.store.js` (bulk ops action)

---

#### 8.2.3 Phase 5 — context_cluster + es_role 기반 재설계

**배경**: §4.2.5/§4.2.6 로 모든 Rule이 `context_cluster` + `es_role` 을 보유하게 됨. 기존 Phase 5(§4.5)는 이 태그 없이 LLM에 raw GWT를 던지는 구조였으므로 BC=1 collapse / Policy=0 이슈가 발생. 이제 태그를 **primary input** 으로 받으면 LLM 호출량과 오분류 모두 급감 가능.

**개선 방향 — 각 서브단계에서 태그 소비**:

| Phase 5 서브단계 | 기존 입력 | 신규 입력 (태그 활용) | LLM 호출 변화 |
|---|---|---|---|
| 5.A BoundedContext 식별 | 전체 Task+Rule raw | `distinct(context_cluster)` 8개를 seed로 "이들을 2~3 BC로 묶어라" | 1회 (변함 없음, 입력 품질↑) |
| 5.B Aggregate 식별 | Context × WRITES Table LLM | `es_role=invariant` Rule의 source_function 계열 → 결정론 | **LLM 생략 가능** (이름만 LLM) |
| 5.C Command 명명 | Task × Aggregate LLM | `es_role=validation` Rule을 gating하는 Command로 묶어 배치 | 배치 1회 |
| 5.D Policy 요약 | fn 계열별 LLM | `es_role=policy` Rule만 대상 → source_function별 그룹핑 | 5개 계열 → 5회 |
| 5.E ReadModel | 선택 | `es_role=query` Rule → 결정론 (READS 테이블 기반) | **LLM 생략 가능** |

**기대 효과 (예상)**:
- Phase 5 LLM 총 호출량 ~20회 → ~8회 (~60% 감소)
- BC 개수 1 → 2~3 (정상 범위)
- Policy 개수 0 → 4~5 (오류메시지 클러스터 기반)
- `decision` role은 소속 Aggregate의 method / domain rule로 부착

**구현 위치**: `event_storming_bridge/promote_to_es.py`
- `identify_bounded_contexts()` — snapshot에서 `distinct(r.context_cluster)` 뽑아 LLM seed로
- `identify_aggregates()` — `es_role IN ('invariant','decision')` + WRITES overlap으로 결정론 후 LLM naming
- `name_command_event_pairs()` — `es_role='validation'` Rule을 Command 가드로 attach
- `summarize_policy()` — `es_role='policy'` Rule만 input
- `derive_readmodels()` — `es_role='query'` Rule의 READS 테이블 → 결정론 생성

**선결 작업**:
- [ ] `fetch_session_snapshot` 이 Rule별 `context_cluster`, `es_role`, `es_role_confidence` 포함하는지 재확인
- [ ] Phase 5 재실행 트리거 (기존 산출물 MERGE 멱등성 유지)
- [ ] BC 2~3개 / Policy 4~5개 실제 나오는지 §8.1 표 갱신

---

### 8.3 C'' 단계(테스트 · 보완) 체크리스트

- [ ] 실제 업무편람 PDF 1개로 전 구간 SSE 이벤트 확인
- [ ] Phase 2 인프라 필터 오탐률 측정 (raw BL vs 통과 Rule 비율, 목표 <5%)
- [x] Phase 2.5 BC 분포 다양성 (목표 ≥ 4 클러스터, 실측: **8 클러스터**)
- [x] Phase 2.6 ES 역할 저신뢰(<0.6) 비율 (목표 <10%, 실측: **0%**)
- [x] Phase 2.6 BC × Role 대각 지배성 — 각 BC의 주력 role이 명확히 드러나는지 (실측 교차표 §8.1 참조)
- [ ] Phase 5 재실행 후 BC ≥ 2 / Policy ≥ 1 확보 여부 (§8.2.3)
- [ ] Phase 3.0 용어집 품질 확인 — 한글 coupled_domain ↔ 영문 식별자 연결 정확도
- [ ] Phase 3.1/3.2 매칭 분포 — lexical-lock 비율, embedding θ 분포, review queue 크기
- [ ] Phase 4.1 passage retrieval 상위 구절이 실제로 Task 와 관련 있는지 육안 확인 (low_confidence 비중)
- [ ] Phase 4.2 조건 추출 결과가 "실제 업무 조건" 이지 요약문이 아닌지
- [ ] Navigator 트리 확장/축소, 긴 텍스트 클램프, 새로고침 후 rehydrate 동작
- [ ] Neo4j `Rule` / `DocumentPassage` / `ExternalTable` 잔여 노드 누수 없음 (`clear_hybrid_nodes` 완전 정리 확인)
- [ ] A2A 실패 fallback 경로 (네이티브 추출기) 품질 비교
- [ ] 동일 세션 재실행 시 idempotent (MERGE 기반) 동작

---

## 9. Open Questions

1. ~~**기존 PDF-to-BPM 모듈 위치 / 입출력 계약**~~ → **해결 (2026-04-14, `pdf_url` 전환)**: 외부 A2A 서비스 우선 + 내장 네이티브 fallback 이중 경로로 구현 완료. extractor 의 A2A 서버가 `file://` 스킴을 처리하지 못하는 문제가 확인되어, 우리 쪽에서 `GET /api/ingest/hybrid/pdf/{filename}` 으로 PDF 를 HTTP 서빙하고 `pdf_url` 로 호출하는 방식으로 전환 (extractor 쪽은 불변). 실제 1차 테스트 성공 — 12 tasks / 8 decisions / 31 flows 추출, `phase1_source: "a2a"`. 남은 확인: (a) 분리 배포 시 `HYBRID_PUBLIC_BASE_URL` 을 A2A 에서 도달 가능한 URL 로 설정 & 인증/토큰 부여 여부 (b) A2A SSE 진행률을 네이티브 `ProgressEvent` 로 릴레이할지(현재는 `/status` 폴링 후 완료 시 수신) (c) extractor 가 내부적으로 호출하는 Supabase (proc_def / claude-skills 업로드)는 우리 경로에선 실패해도 무해 — 운영 시 명시적으로 비활성화할지 (d) 장애/타임아웃 임계치 및 세션 상태 전이 규칙 (e) Neo4j 공용 사용 시 `Event` 라벨 의미 충돌 (pdf2bpmn: BPMN event, event_storming: 도메인 이벤트) 정리 필요 여부.
2. **Task 단위 granularity 기준** — "신청 접수 / 자격 검토 / 승인 / 통보" 수준이 기본 가정. 도메인별 조정 규칙?
3. **매핑 신뢰도 임계치** — 자동 채택 vs 리뷰 큐 컷오프 값.
4. **문서 ↔ 코드 충돌 시 우선순위** — 예: 문서엔 있는 Task가 코드엔 없을 때 / 반대의 경우.
5. **기존 event_storming 산출물과의 공존** — 같은 세션에서 이중 산출이 가능한가, 아니면 새 파이프라인만 단독 실행?
6. **멀티 문서 입력** — 매뉴얼 + 규정 + 절차서를 동시에 병합할 때의 충돌 해소.

---

## 10. 성공 지표

- **Task 커버리지**: 문서에서 식별된 Task 중 Rule과 연결된 비율.
- **Rule 품질**: 인프라/보일러플레이트 오탐률 < 5%.
- **매핑 정확도**: 샘플 검증 세트에서 Task↔Rule 매핑 precision/recall.
- **Event Storming 완결성**: 생성된 Command/Event/Policy/Aggregate 중 사람이 그대로 채택한 비율.

---

## 11. 참고 — 자료 요약 (원본 사고 흐름 보존)

1. 기존 PDF-to-BPM 모듈로 문서에서 Actor/Task/Sequence를 추출해 프로세스 상위 흐름을 먼저 설계한다.
2. BPM의 Task는 단일 트랜잭션/함수 호출이 아니라, 문서상 하나의 업무 활동에 해당하는 단위이며 실제 구현에서는 여러 모듈과 함수의 집합으로 구성된다.
3. 각 Task에 대응하는 레거시 코드 영역에서 실제 모듈/함수를 식별하고, 비즈니스적으로 가치 있는 평가·판단·분기 로직을 추출해 GWT Rule로 정제한다.
4. 문서에 기술된 Activity와 코드의 Rule/Function을 벡터 검색·의미 매핑으로 연결해 Task–Function–Condition–NextFlow를 하나의 온톨로지로 통합한다.
5. 완성된 비즈니스 프로세스와 Rule 체계를 기반으로 Command/Event/Policy/Aggregate를 도출해 이벤트 스토밍 산출물로 확장한다.
