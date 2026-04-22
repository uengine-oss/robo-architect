# Hybrid Ingestion — 동작 구조 (Architecture)

> 문서 작성일: 2026-04-21 (**4차 개정 — Hierarchical Agentic Retrieval 도입**)
> 이 문서는 "업무 문서(PDF/텍스트) + 레거시 코드 분석 그래프" 두 입력을 조합해 **비즈니스 프로세스(BPM) 를 그리고, 각 Task 에 실제 코드 근거를 붙이는 파이프라인** 의 동작을 **Phase 순서대로** 설명한다.
> 설계 배경·마일스톤은 `Analyzed_Code_ingestion.md` 를 참고. 2026-04-21 구조 재편의 의도·검증 수치는 `개선&재구조화.md` 참고.

## 주요 변경 (2026-04-21)

- **BpmProcess 노드 도입** — 한 세션이 멀티 프로세스 보유 가능 (A2A extractor 의 multi-`<bpmn:process>` 복원)
- **Phase 2.5 (BC 사전 태깅) + Phase 2.6 (ES 역할 사전 태깅) 폐기** — BPMN 단계에서 확정 불가, Phase 5 가 task+process 맥락으로 최종 판정
- **Phase 3 전면 재설계** — 기존 lexical/embedding/structural/merge 네 단계를 **Hierarchical Agentic Retrieval** 로 교체: Module top-k → BL filter → per-process LLM validator → cross-process LLM arbitrator
- **A2A 어댑터 확장** — pdf2bpmn A2A 서버가 XML 을 응답으로 주지 않고 Neo4j 에 직접 기록하는 구현체를 지원하기 위해 `_harvest_bundle_from_pdf2bpmn_neo4j` 추가
- **Navigator 2계층 트리** — Process → Task (더블클릭/드래그로 per-process 캔버스 렌더)
- **Inspector**: Agent Reasoning 섹션 + `🔄 다시 탐색` 버튼 (task name 옆), 편집 UI 전부 `?debug=1` 뒤로

---

## 0. 핵심 아이디어 한 줄

> **"문서는 상위 흐름(Actor / Task / Sequence)을 주고, 코드는 각 Task 의 실제 판단 로직(Rule / Function / Condition)을 준다. 둘을 하나의 BPM 으로 합친다."**

- 문서만: 업무 흐름은 명확하지만 "왜 / 언제 / 무엇으로 판단" 이 흐림
- 코드만: 판단 로직은 정확하지만 "누가 / 어떤 흐름으로 수행" 이 흐림
- → 둘을 합쳐야 실행 가능한 BPM 이 된다

---

## 1. 입력 (두 개의 축)

### 1.1 문서 (Document)
- **무엇**: 업무편람, 절차서, 규정 PDF 또는 텍스트
- **어디로 들어가는가**: `POST /api/ingest/hybrid/upload` 의 `file` / `text` 필드
- **처리**: PDF → PyMuPDF 로 텍스트 추출 → `session.content` 에 in-memory stash + `{pdf}.txt` 로 로컬 디스크에도 보존 (디버깅용)

### 1.2 분석 코드 그래프 (Analyzer Graph)
- **무엇**: 레거시 C/Java/… 코드를 다른 시스템(`robo-data-analyzer`) 이 분석해 Neo4j 로 적재한 그래프
- **전제**: 본 파이프라인 실행 전에 이미 Neo4j 에 import 되어 있어야 함. 본 서비스는 analyzer DB 를 **read-only** 로만 조회
- **주요 노드/관계**:
  ```
  (FUNCTION {procedure_name, function_id, name, summary})
    ├─[:HAS_BUSINESS_LOGIC]─► (BusinessLogic {title, given, when, then, sequence, coupled_domain})
    ├─[:READS]──► (Table {name})
    ├─[:WRITES]─► (Table {name})
  (Actor {name}) ─[:ROLE]─► (FUNCTION)
  ```
- **핵심 자원**: `BusinessLogic` 노드가 **이미 Given-When-Then 형태로 채워져 있다** — 본 파이프라인이 LLM 으로 다시 추출하지 않는 이유

### 1.3 실전 예 (input_resource)
- PDF: `업무Flow_초안_zapamcom10060.pdf` — 자동납부 계좌/카드번호 실시간인증 모듈 업무 Flow
- Analyzer 덤프: `analyzer-2026-04-10T00-43-42.dump` — 모듈 `zapamcom10060` 의 C 코드 분석 결과 (11 FUNCTION, 52 BusinessLogic, 2 Table)

---

## 2. 출력 — 각 Task 가 갖는 7 축 정보

각 `BpmTask` 는 다음 7 축의 정보를 보유한다. **Phase 진행에 따라 점진적으로 채워진다**:

| 축 | 소스 | 채워지는 시점 |
|---|---|---|
| **① 이름 / 설명** | 문서 | Phase 1 |
| **② 수행 Actor** | 문서 | Phase 1 |
| **③ 문서 위치** (page / section) | 문서 | Phase 1 |
| **④ 관련 문서 구절** (top-k passages) | 문서 | Phase 4.1 |
| **⑤ 실행 규칙** (Given-When-Then) | 코드 | Phase 2 + 3 매핑 |
| **⑥ 실행 함수** (module.function) | 코드 | Phase 3 매핑 부산물 |
| **⑦ 통합 조건** (자연어) | 문서 + 코드 | Phase 4.2 |

프론트 Navigator 에서 Task 를 **더블클릭**하거나 BPMN 캔버스의 Task 노드를 **더블클릭**하면 `HybridTaskInspector` 패널이 열리며 이 7 축이 한 화면에 표시된다.

---

## 3. 동작 타임라인 (한눈에)

```
[사용자] ──► 🧪 테스트 (Hybrid) 버튼 클릭
              │
              ▼
  DELETE /api/ingest/hybrid/reset          ← hybrid 라벨만 wipe, analyzer 보존
              │
              ▼
  POST /api/ingest/hybrid/upload           ← PDF + 텍스트
              │  PDF→text stash, session 생성
              ▼
  GET  /api/ingest/hybrid/stream/{sid}     ← SSE 시작

  ─── Phase 1 ────────────────────────────── 큰 그림 BPM (multi-process)
  · A2A extractor (우선): pdf2bpmn 이 Neo4j 에 직접 side-effect 기록
    → adapter 가 (:Process)-[:HAS_TASK]->(:Task)-[:PERFORMED_BY]->(:Role)
       를 harvest → ProcessBundle
    → domain_keywords 부재 시 per-process LLM backfill 1회
  · Native LLM (A2A 실패 시): _ExtractionResult.processes[] 계층 LLM 추출
  · Neo4j: BpmProcess / BpmActor / BpmTask / BpmSequence
          + HAS_TASK / HAS_ACTOR / PERFORMS / NEXT / CONTAINS

  ─── Phase 2 ────────────────────────────── 코드 → Rule
  · analyzer DB 의 BusinessLogic 읽기 (read-only)
  · 인프라 필터 + GWT 유효성 검사 + BL.title 보존
  · Neo4j: Rule (세션 격리)

  ─── Phase 3.0 Glossary ────────────────── 한↔영 용어 사전
  · 문서 + 코드 토큰 → LLM 1회 → GlossaryTerm
  · Neo4j: GlossaryTerm (Navigator per-process 용어 매칭에 사용)

  ─── Phase 3 Hierarchical Agentic Retrieval ────── (재설계)
  · Step 1 (per process × per task): analyzer MODULE top-k by embedding
      query = process.name + process.domain_keywords + task.name
  · Step 2: Step1 모듈에 속한 BL 을 embedding top-k=8 로 축소
  · Step 3: per-process LLM validator (1 call / task, structured output)
            — 후보 각각에 verdict={accept,reject} + rationale + evidence_refs
            — 부모 체인(Cypher 사전조회)을 프롬프트에 주입
            — accept 상한 3개/task, 80% 확신 미만 reject
  · Step 4 (session-level, 경쟁 rule 만): **Cross-Process Arbitrator**
            — 같은 rule 을 N개 프로세스가 accept 하면 LLM 이 home 선택 or reject
            — cross-cutting utility 는 reject (매핑 0건)
  · Neo4j: REALIZED_BY {confidence, method='agentic', reviewed=false,
                         rationale, evidence_refs, evidence_path,
                         agent_verdict='accept'}
          + ActivityMapping 감사 노드
          + (BpmProcess)-[:IMPLEMENTED_BY {confidence, method}]->MODULE fqns
            (BpmProcess.implemented_by[] 프로퍼티 기록; cross-DB 회피)

  ─── Phase 4.0 Document Chunking ──────── 원문 분할
  · 헤딩 1차 + 400자 슬라이딩 윈도우 fallback
  · Neo4j: DocumentPassage

  ─── Phase 4.1 Passage Retrieval ──────── Task당 top-k=2
  · Task 텍스트 ↔ Passage 텍스트 코사인 (항상 top-k 반환)
  · Neo4j: SOURCED_FROM {score, rank, low_confidence}

  ─── Phase 4.2 Conditions LLM ─────────── 문서+코드 결합 요약
  · Task당 LLM 1회 호출
  · Neo4j: BpmTask.conditions = [ ... ]

              ▼
  [프론트] hybridTasks store 가 단계별 upsert 로 성장
            · BPMN 캔버스: 큰 흐름 실시간 렌더
            · Navigator: 플랫 리스트 (R{N} 배지 = Rule 수)
            · Task 더블클릭 (Nav 또는 캔버스) → HybridTaskInspector
            · Review Queue 클릭 → HybridReviewModal → 승인/거부
```

---

## 4. 각 Phase 의 동작 — 입력·처리·출력·근거 기준

### Phase 1 — 큰 그림 BPM 그리기 (문서만)

> **왜 문서만 보는가**: 코드의 단일 함수 ≠ 업무 활동. 한 Task("자격 검토") 가 여러 함수를 묶을 수도, 한 함수가 여러 Task 를 담당할 수도 있음. 이 대응은 Phase 3 에서 해결. Phase 1 은 문서가 정의하는 **업무 단위를 그대로 존중**.
> **멀티 프로세스 지원 (2026-04-21)**: 한 PDF 가 여러 업무 프로세스를 기술하면 각각이 독립 `BpmProcess` 노드로 보존되고 process 간 task·rule 매핑이 격리된다.

- **입력**: 문서 텍스트 (+ PDF 경로/URL)
- **처리 경로**:
  - **A2A (primary)**: 외부 `process-gpt-bpmn-extractor` 서비스 (`POST /execute`) 에 PDF 전달
    - **두 가지 응답 형태 모두 지원**:
      1. XML 응답 — `adapt_a2a_result_to_skeleton` 이 `<bpmn:process>` 별로 분할 파싱 (`parse_bpmn_xml_per_process`)
      2. Neo4j 직접 기록 — 응답은 status 만, BPMN 구조는 `(:Process)-[:HAS_TASK]->(:Task)-[:PERFORMED_BY]->(:Role)` 로 Neo4j 에 side-effect 로 기록. `_harvest_bundle_from_pdf2bpmn_neo4j` 가 fresh (session_id NULL) 노드를 ProcessBundle 로 변환
    - **domain_keywords backfill**: harvester 가 뽑아낸 process 에 domain_keywords 가 없으면 LLM 1회로 `extract_process_identity` 호출 (Agent Step 1 retrieval query 품질 확보)
  - **Native LLM (fallback)**: A2A 꺼져있거나 실패 시, `_ExtractionResult.processes[]` 스키마로 LLM 이 multi-process 직접 추출
- **출력**: `ProcessBundle { processes: list[BpmSkeleton], bpmn_xml }`
  - 각 `BpmSkeleton { process, actors[], tasks[], sequences[], bpmn_xml }` 은 **하나의 프로세스**
  - `BpmProcess { id, name, description?, domain_keywords[], source_pdf_name, session_id, actor_ids[], task_ids[] }`
- **Neo4j 기록**:
  - `(BpmProcess)-[:HAS_TASK]->(BpmTask)`, `(BpmProcess)-[:HAS_ACTOR]->(BpmActor)`
  - `(BpmActor)-[:PERFORMS]->(BpmTask)`, `(BpmTask)-[:NEXT]->(BpmTask)`
  - `(BpmSequence)-[:CONTAINS]->(BpmTask)`
  - `BpmProcess.bpmn_xml` 에 **per-process XML** 저장 (프론트 드래그/더블클릭 시 해당 프로세스만 캔버스 렌더)
- **Canvas 규칙**:
  - Pool 이름 = 프로세스 이름
  - Lane = **실제 task 를 수행하는 actor 만** (PERFORMED_BY 기반, 빈 lane 미생성)

---

### Phase 2 — 코드 → Rule 생성

- **입력**: analyzer DB 의 모든 `(FUNCTION)-[:HAS_BUSINESS_LOGIC]->(BusinessLogic)` 엣지
- **필터**:
  - `rule_filters.py::is_infra()` — EJB 라이프사이클 / finder / getConnection / getter-setter / 로깅 등 제외
  - `is_meaningful_gwt()` — given/when/then 세 슬롯 중 2개 이상 채워진 것만
- **매핑**: LLM 호출 없이 BL 의 given/when/then 을 그대로 `RuleDTO` 로 옮김. `source_function`, `source_module` 보존
- **결과**: 전역 Rule 리스트 (아직 Task 와 연결되지 않음)
- **Neo4j 기록**: `Rule` 라벨 (세션 격리 위해 `session_id` 속성)

---

### Phase 2.5 / Phase 2.6 — **폐기 (2026-04-21)**

> **왜 폐기**: BC(Rule → 업무범주) 와 ES 역할(Rule → Aggregate/Command/Policy/…) 은 **BPMN 단계에서 확정할 수 없는** 결정이다. BPMN Task ≠ ES Command, BPMN 에는 Aggregate 개념이 없음, Policy 는 Event 선행. rule-level 정적 분석만으로 사전 태깅하면 Phase 5 최종 판정에 편향을 주고 사용자 UI 에도 혼동만 줌.
>
> - 구현 파일 (`mapper/bc_identifier.py`, `mapper/es_role_tagger.py`) 은 보존되어 있지만 **runner 에서 호출 안 됨**
> - `Rule.context_cluster`, `Rule.es_role`, `Rule.es_role_confidence` 필드는 legacy 호환을 위해 스키마에 유지 (값은 비워짐)
> - ES 역할은 **Phase 5 (event storming promotion)** 가 task + process 맥락을 보고 최종 판정

---

### Phase 3.0 — Glossary Extraction (한↔영 용어 사전)

> **왜 필요한가**: Task 이름은 한국어("자격 검토"), Rule 의 `source_function` 은 영문 camelCase(`checkEligibility`). Navigator 의 per-process "용어" 섹션 매칭에 사용. (2026-04-21 이후 Phase 3.1 Lexical 은 폐기됐으므로 glossary 의 주 용도는 UI 용어 연결로 축소)

- **입력 (혼합)**:
  - 문서 쪽: 본문 텍스트(12k자 cap), Task 이름·설명, Actor 이름
  - 코드 쪽: FUNCTION 식별자 토큰(camelCase 분해), BL.title, **BL.coupled_domain (한글)**, Table.name — 상위 200개만
- **처리**: 인프라 토큰 제거 → LLM 1회 구조화 출력
- **출력**: `GlossaryTerm { term, aliases[], code_candidates[] }` 리스트
- **Neo4j 기록**: `GlossaryTerm` 라벨
- **사용처**:
  - Navigator 에서 process 의 `domain_keywords` 와 매칭되는 용어만 해당 process 트리에 표시
  - Agent 프롬프트에는 직접 주입하지 않음 (agent 가 `domain_keywords` + rule context 로 충분)

---

### Phase 3 — Hierarchical Agentic Retrieval (2026-04-21 재설계)

> **왜 재설계**: 기존 Phase 3.1 ~ 3.4 (lexical / embedding / structural / merge) 는 "빠르게 후보 많이 → score 로 거르기" 전략. "입력값 검증" 같은 공통 task 가 어느 **프로세스 맥락** 에 속한 BL 을 잡아야 하는지 구분 못 해 Task 당 13+ 개 over-match. Embedding 은 *유사도* 는 측정해도 *논리적 귀속* 은 측정하지 못함.
>
> 새 설계: **"천천히 도메인 따라 내려가며 소수만 남기기"**. 각 단계에서 candidate 공간을 줄이고 최종은 LLM 의 semantic 판정.

**Step 1 — Module Retrieval** (`mapper/module_retriever.py`)

- 쿼리: `process.name + ' '.join(process.domain_keywords) + task.name (+ task.description)`
- 대상: analyzer DB `(m:MODULE)` (없으면 `(f:FILE)` fallback). `m.summary` 가 비어있지 않은 것만
- 방식: OpenAI `text-embedding-3-small` 코사인 유사도 → 기본 top-k = 5
- 세션 embedding 캐시 (`EmbeddingCache`) 재활용
- Persist: `(BpmProcess).implemented_by / implemented_by_confidence / implemented_by_method` 프로퍼티 (§2.F — cross-DB 엣지 불가)

**Step 2 — BL Filter within Modules**

- 입력: Step 1 의 모듈 fqn 집합
- Rule 중 `source_module` 이 해당 모듈에 속하는 것만 in-scope. `source_module` 미설정 rule 은 통과 (excluding proof 불가)
- in-scope rule 을 embedding 으로 `task query` 와 비교 → **top-k = 15** (2026-04-21 8→15 상향: Step 3 에서 judgment quality 로 필터링할 여지를 확보)
- **LLM 호출 없음** — 순전히 필터링

**Step 3 — Per-process Agentic Validator** (`mapper/agent_validator.py`)

- 입력: Step 2 top-k (≤ 15) + 각 BL 의 **parent chain** (Cypher 사전조회 — `callers`, `parent_module`, `parent_package`)
- LLM 호출: task 당 **1회** (`with_structured_output(_ValidationResult)`). 후보 전체 묶어 일괄 판정
- 출력: 후보마다 `{rule_id, verdict, rationale, evidence_refs}`
  - verdict ∈ {accept, reject}
  - rationale: 1~2 문장 한국어 + 증거(모듈명/함수명/summary 키워드) 포함 필수
- 프롬프트 규칙 (2026-04-21 개정):
  - "BL 은 대개 하나의 Task 에만 속한다. 여러 Task 에 걸쳐 보이면 가장 본질적으로 수행하는 Task 만 accept"
  - **"accept 개수 제한 없음. 정당한 매핑은 모두 accept"** (이전 3개 cap 폐기)
  - **"애매하면 accept"** — embedding 으로 이미 의미적으로 가까운 후보만 들어옴. judgment quality 로만 reject 판단
  - "b000_main_proc 의 여러 인증 유형별 반영여부 결정 분기들이 모두 '실시간 인증결과 판정' task 에 속하는 것이 옳은 매핑" 예시 명시
- 안전장치: `per_task_cap=20` (runaway 방지용, 실무적으론 무제한)
- 프로젝트 LLM 패턴 준수: tool-calling / LangGraph 사용 안 함. Cypher 는 LLM 호출 **이전** 에 수행해 텍스트로 주입.

**Step 4 — Cross-Process Arbitrator** (`mapper/cross_process_arbitrator.py`)

> **스펙에 없던 추가 단계 (2026-04-21)**. Per-process validator 가 서로를 모르기 때문에 한 rule 이 여러 process 에 동시 accept 되는 contamination 발생 (실측: 14 rules × 2~5 processes). 이를 해결하려면 **session 전체를 보는 LLM 판정** 이 필요.

- 실행 조건: 같은 `rule_id` 가 N > 1 개 프로세스에서 accept 됐을 때만
- 입력: rule (GWT + context) + **경쟁 주장 전체** (process.name, process.domain_keywords, task.name, per-process rationale)
- LLM 호출: 경쟁 rule 당 1회 (`arbitrate_rule_home` → `ArbitrationVerdict`)
- 출력:
  - `reject=true` → cross-cutting utility 로 판정, 어느 process 에도 매핑 안 함
  - `reject=false` → `home_process_id`, `home_task_id`, `rationale`
- 방어 로직: LLM 이 claim set 밖의 id 를 반환하면 첫 claim 으로 fallback

**Persist**

- `(BpmTask)-[:REALIZED_BY {confidence, method='agentic', reviewed=false, rationale, evidence_refs[], evidence_path[], agent_verdict='accept'}]->(Rule)`
- `(ActivityMapping {task_id, rule_id, score, method, reviewed, rationale})` 감사 노드
- 재탐색(🔄): `GET /api/ingest/hybrid/task/{sid}/{tid}/retrieve` SSE — 해당 task 의 REALIZED_BY 를 교체 persist

**성능 / 비용**

- Task 당 embedding (Step 1 모듈 ~N번 + Step 2 후보 8번) + LLM 1회 (Step 3)
- Session 전체: 경쟁 rule × 1 (Step 4)
- 실측 (3 processes × 33 tasks): 약 40~50초. `HYBRID_EMBED_*` env 로 top-k 조정 가능

**실측 결과 (3 processes, 52 rules)**

| 지표 | 구 파이프라인 (lexical/embedding/structural/merge) | 1차 agentic (cap=3, bl_top_k=8) | 2차 튜닝 (cap 해제, bl_top_k=15, judgment-based) |
|---|---|---|---|
| 매핑 총수 | ~80+ | 17 (과소) | 재측정 필요 |
| rationale 부착율 | 0% | 100% | 100% |
| 크로스 프로세스 오염 | 14 rules | **0** ✓ | **0** ✓ (유지) |
| 0 매핑 task 비율 | 낮음 | 높음 (14/21 등) | 재측정 필요 |

> 2차 튜닝은 "Task 당 자연스러운 매핑 개수는 구현 분기 수에 따름" 철학 — 3 cap 같은 artificial constraint 제거. 실측은 재 ingestion 후 확보.

---

### Phase 3.x (lexical / embedding / structural / merge) — **폐기 (2026-04-21)**

- `mapper/lexical_matcher.py`, `mapper/embedding_matcher.py` (Phase 3 단독 용도), `mapper/structural_booster.py` — 보존되어 있지만 `map_tasks_to_rules` 에서 호출 안 함
- `_dedupe_best` (precedence merge) — agent 가 이미 rule 당 dedup 을 수행하므로 불필요

---

### Phase 4.0 — Document Chunking

- **1차**: 헤딩 기반 분할
  - 정규식: `제N조/장/절/항`, `1.` / `1.1` 번호, Roman, Markdown `#`, `■◆▶` 글머리
- **2차 fallback**: 헤딩 분할 결과가 3개 미만이거나 평균 청크 크기 > 2000자면 슬라이딩 윈도우(400자, 80자 오버랩)로 재분할
- **페이지 힌트**: `\f` (form feed) 마커 기반 추정
- **출력**: `DocumentPassage {id, heading, text, page, char_start, char_end, chunk_method}`
- **Neo4j 기록**: `DocumentPassage` 라벨

---

### Phase 4.1 — Passage Retrieval (Task 당 top-k=2)

- **대상**: 모든 Task
- **임베딩 캐시**: Phase 3.2 와 동일한 `EmbeddingCache` 공유 (재사용)
- **Task 텍스트**: name + description + Actor (Phase 3.2 와 동일)
- **Passage 텍스트**: heading + body
- **처리**: 코사인 유사도 → **항상 top-k 반환** (필터 X)
- **임계치** (필터가 아니라 표시용 플래그):
  - `HYBRID_PASSAGE_TOP_K = 2` — 항상 정확히 k개
  - `HYBRID_PASSAGE_THETA = 0.5` — 이 미만이면 `low_confidence = true` 플래그 (한↔영 짧은 쿼리는 고유사도가 드물어 필터링 시 대부분 소실됨)
- **Neo4j 기록**: `(BpmTask)-[:SOURCED_FROM {score, rank, low_confidence}]->(DocumentPassage)`

---

### Phase 4.2 — Conditions LLM (문서+코드 결합 요약)

- **입력** (Task 단위, LLM 1회 호출):
  - Task 이름 / 설명
  - Phase 4.1 의 top-k passages (문서 근거)
  - Phase 3.4 에서 auto_matches 로 붙은 Rule 의 GWT (코드 근거)
- **출력**: 한국어 한 줄 문장 리스트 (최대 6개, 각 60자 이내)
- **거부 규칙**: 문서 / 코드 어디에도 근거가 없으면 생성 거부 (환각 방지)
- **저장**: `BpmTask.conditions: list[str]` 속성 (별도 노드 X — 단순 자연어라 관계 그래프 불필요)

---

## 5. 탐색·매칭 매트릭스 (한눈에)

**"무엇을 기준(query)으로, 어디(index)에서, 어떤 방식으로 찾는가"** — 모든 단계를 한 표로.

| 단계 | 쿼리 측 (기준) | 인덱스 측 (탐색 대상) | 방식 | 임계치/규칙 (현행) |
|---|---|---|---|---|
| **3.0 Glossary 생성** | 문서 본문(12k자) + Task 이름·설명 + Actor 이름 | analyzer 코드 토큰 (FUNCTION 식별자, BL.title, **BL.coupled_domain — 한글**, Table.name) — 상위 200개 | LLM 1회 호출 (구조화 출력) | 인프라 토큰 사전 제거 (`ejb`/`util`/`get`/...) |
| **3.1 Lexical 매칭** | Task 이름 + 설명 + Actor → glossary 로 토큰 확장 | Rule 토큰 집합 (fn / module / function_summary / GWT / 연관 Actor / 연관 Table) | **집합 교집합** (Cypher X, 임베딩 X) | min_hits=2 (`HYBRID_LEXICAL_MIN_HITS`), DF 0.35 이상 auto-stopword (`HYBRID_LEXICAL_MAX_TOKEN_DF`), Hangul 2자+/ASCII 3자+ 만 informative |
| **3.2 Embedding 매칭** | Task 이름+설명+Actor (한 텍스트) | **Rule 텍스트** = `GIVEN/WHEN/THEN + function_summary + module.fn + READS/WRITES tables` | **OpenAI 임베딩 코사인** (`text-embedding-3-small`) | top-k=3, θ_auto=0.50, θ_review=0.40 |
| **3.3 Structural 부스터** | 후보 매칭 + Task 의 Actor·Sequence | analyzer DB 의 `(Actor)-[:ROLE]->(FUNCTION)`, `(FUNCTION)-[:READS\|WRITES]->(Table)` | **Cypher 직접 탐색** (임베딩 X) | Actor 일치 +0.05, Sequence 같은 묶음 2건↑ +0.03, cap 0.99 |
| **4.0 Document Chunking** | 문서 본문 | (없음 — 문서 자체를 분할) | 헤딩 정규식 1차 / 슬라이딩 윈도우 fallback | 헤딩 <3개 또는 평균 >2000자면 윈도우 |
| **4.1 Passage Retrieval** | Task 이름+설명+Actor | **DocumentPassage 텍스트** = heading + body | **OpenAI 임베딩 코사인** (3.2 와 같은 캐시) | 항상 top-k=2, score<0.5 면 `low_confidence` |
| **4.2 Conditions LLM** | Task + 4.1 Passages + 3.x 매칭 Rule GWT | (입력만 — 검색 아님) | LLM 1회 (per Task) | 근거 없으면 빈 배열, 최대 6개 |

### 5.1 임베딩 vs 직접 탐색 분담

**임베딩되는 두 종류** (자유 텍스트, 의미 매칭 필요):
- ① **Rule 텍스트** (analyzer BL 의 GWT + 함수 summary) ← Phase 3.2
- ② **DocumentPassage 텍스트** (문서 heading + body) ← Phase 4.1

**임베딩되지 않는 것** (직접 탐색·토큰 매칭):
- analyzer 그래프 **구조** (`HAS_BUSINESS_LOGIC`, `ROLE`, `READS`, `WRITES`) → Cypher 직접 (Phase 3.3)
- 코드 식별자 토큰 → 집합 교집합 (Phase 3.1)
- 글로서리 후보 토큰 → LLM 프롬프트에 텍스트로만 (Phase 3.0)

> **자유 텍스트는 임베딩, 식별자/구조/관계는 직접 탐색.** Rule 과 DocumentPassage 두 종류만 임베딩 인덱스이고, 둘 다 같은 query 텍스트(Task 이름+설명+Actor) 로 검색됨.

### 5.2 Query 텍스트 정확한 구성

세 곳에서 사용되는 Task query 텍스트는 모두 동일한 형식:

```python
def _task_text(task, actor_name_by_id):
    parts = [task.name, task.description or ""]
    actors = ", ".join(actor_name_by_id.get(aid, "") for aid in task.actor_ids or [])
    if actors.strip(", "):
        parts.append(f"[Actor: {actors}]")
    return "\n".join(filter(None, parts))
```

실제 예:
```
입력값 검증
호출 시 전달된 필수 입력값의 존재 여부 및 형식을 검증한다.
[Actor: 자동납부담당기획팀]
```

Rule 텍스트 예 (2026-04-20 기준 — BC 태그 + 부모 노드 컨텍스트 포함):
```
[업무범주: 입력값검증]
[모듈: zapamcom10060]
[호출자: b000_main_proc]
GIVEN: 입력.acnt_num=RC_NRM 또는 ...
WHEN: 청구번호, 업무구분, 납부방법 ... 중 하나가 누락된 상태로 요청한다.
THEN: 누락된 항목에 맞는 오류 메시지로 즉시 RC_ERR를 반환한다 ...
Summary: 입력 파라미터 유효성 검증 함수
Function: apascrt00010t02_20260406.zapamcom10060.a000_input_validation
Tables: reads=[...] writes=[...]
```

→ 같은 토큰을 공유하는 Rule 이어도 다른 모듈·다른 호출 체인이면 코사인이 분리되어 cross-module 혼동 방지.

Passage 텍스트 예: `{heading}\n{body 전문}`

→ **모든 query 측은 Task 한국어 텍스트, 인덱스 측은 코드/문서의 자유 텍스트.**

### 5.3 Glossary 가 매칭 품질에 미치는 영향

```
Task: "카드사코드 추출"
  ──glossary 매칭──► aliases: ["카드사체크", "카드프리픽스체크", ...]
                    code_candidates: ["b300_call_zapamcom10040", "zapamcom10040"]
  ──토큰 분해──────► task tokens: {"카드사코드", "추출", "b300", "call", "zapamcom", "10040"}
                                                          ↓
  Rule "b300_call_zapamcom10040" 의 토큰: {"b300", "call", "zapamcom", "10040", "given/when/then 한글토큰"}
                                                          ↓
                                          교집합 ≥ 2 informative 토큰 → 매칭 성공
```

- **glossary 가 빈약하면**: lexical 매칭 폭락 → embedding 으로 부담 이동 → 한↔영 갭 때문에 review queue 만 쌓임
- **glossary 가 너무 일반적이면** (예: "결과 반환" → `["main"]`): 모든 Rule 과 매칭되는 과매칭 → DF auto-stopword + HARD_STOPWORDS 로 차단 (2026-04-15 패치)

### 5.4 임베딩 단위 (무엇이 몇 개의 벡터로 만들어지는가)

"1개 객체 = 1개 벡터" 원칙. 세 종류만 임베딩되며, 각 단위의 텍스트 구성은 아래와 같다:

| 임베딩 대상 | 1 객체 = 1 벡터 | 텍스트 구성 | 쓰임 |
|---|---|---|---|
| **Task** (쿼리 측) | `BpmTask` 하나 | `name + description + [Actor: ...]` (actor 이름 쉼표로 이어붙임) | Phase 3.2 + 4.1 양쪽에서 **동일 벡터 재사용** (같은 `EmbeddingCache` hit) |
| **Rule** (인덱스 측 — 코드) | `BusinessLogic = Rule` 하나 | `GIVEN + WHEN + THEN + Summary + {module}.{fn} + reads/writes Tables` | Phase 3.2 인덱스 |
| **Passage** (인덱스 측 — 문서) | 청크 하나 (헤딩/윈도우) | `heading + body` | Phase 4.1 인덱스 |

#### 유의점

- **같은 `when` 을 공유하는 BL 분기는 별개 벡터**: "인증결과코드 보정 규칙 적용" 트리거가 EDI/FB/간편결제/기타 4개 채널별 `then` 을 가지면 → **4개 Rule, 4개 벡터**. 하나로 뭉개지 않음 (채널별 로직 보존).
- **청크 크기 편차**: 헤딩 기반 청크는 50~2000자로 가변. 슬라이딩 윈도우 fallback 은 고정 400자. 너무 긴 청크는 임베딩 신호가 희석되므로, retrieval 품질이 나쁘면 `document_chunker.py::_MAX_AVG_CHUNK` 를 낮춰 윈도우 fallback 을 더 자주 타게 조정 가능.
- **Rule 텍스트에 영문 식별자 포함**: `{module}.{fn}` 이 영문이라 한↔한 순수 의미 매칭보다 코사인이 약간 낮아질 수 있음. 필요 시 식별자 제외하고 GWT+Summary 만 임베딩하는 실험 가능.

#### 실측 (방금 세션)

```
Task:    7  개  × 1 vector = 7
Rule:   52  개  × 1 vector = 52
Passage: 30  개  × 1 vector = 30
──────────────────────────────────
합계:                        89 OpenAI 임베딩 호출 (text-embedding-3-small)
```

#### 영속성 — 캐시는 세션 내 in-memory

- `EmbeddingCache` = `dict[text, list[float]]` 단일 프로세스 메모리
- 세션 종료 시 소멸 — **ChromaDB 등 영구 벡터 DB 안 씀** (현 규모에선 과투자로 판단)
- 스케일 커지거나 과거 세션 벡터 재사용이 필요해지면 **Neo4j Vector Index** (`CREATE VECTOR INDEX`, 5.11+) 가 다음 자연스러운 선택지 — 별도 인프라 없이 Rule·DocumentPassage 노드에 vector 속성만 추가

---

## 6. UX / 상호작용

### 6.1 Task Inspector 오픈 경로 (2026-04-15)
- **Navigator 좌측 사이드바** 의 Task 항목 **더블클릭**
- **BPMN 캔버스** 의 Task 노드 **더블클릭** (element.id 를 hybridTasks 에서 찾아 매칭; `Task_` 접두어 있으면 자동 제거 후 재매칭)
- 두 경로 모두 `store.selectHybridTask(taskId)` 호출 → 우측 `HybridTaskInspector` 슬라이드-인
- ✕ 버튼 또는 캔버스 빈 영역 클릭 시 닫힘

### 6.2 통합 "미매핑 / Review" 풀 — 단일 장소에서 관리

> 2026-04-20 개정: 기존 별도 "Review Queue" 섹션을 폐기하고, **pipeline 제안(review)과 완전 미매핑(unassigned) 을 같은 자리에서 관리**하도록 통합. 사용자는 "이 rule 어디 갔지?" 가 review band 이든 unmapped 이든 한 곳만 본다.

Navigator 좌측 BPMN 탭의 "미매핑 / Review" 섹션이 두 종류 항목을 섞어 표시:

| kind | 뜻 | 표시 |
|---|---|---|
| 🔍 **제안 (review)** | 파이프라인이 `θ_review ≤ score < θ_auto` 구간에 park 한 매칭. `ActivityMapping` 노드만 있고 `REALIZED_BY` 엣지 없음 | score + 제안 Task 이름 |
| ❔ **미매핑 (unassigned)** | Rule 자체가 어느 Task 에도 `REALIZED_BY` 되지 않음. Phase 3 매칭이 전혀 걸리지 않았거나 사용자가 모든 Task 에서 해제 | score 없음, 제안 없음 |

**각 항목 표시 요소**: kind 배지 + BC 배지 + `es_role` 텍스트 + `source_function` + BL.title + (review 면) 제안 Task + 점수

**사용자 조작 (단일 UI)**:
- **🔍 review 항목의 제안 Task 를 클릭** → `HybridReviewModal` 오픈 → 승인/거부 (기존 경로 유지)
- **인라인 드롭다운 "다른 Task 연결…" + [연결] 버튼** — 모든 pool 항목에 동일 제공. 선택한 Task 에 즉시 붙임 (`method=manual, confidence=1.0, reviewed=true`)

**승인/거부 엔드포인트**:
- `POST /api/ingest/hybrid/review/{sid}/{tid}/{rid}/accept` — review 만 해당, `REALIZED_BY {reviewed: true}` 엣지 생성 + `ActivityMapping.reviewed = true`
- `POST /api/ingest/hybrid/review/{sid}/{tid}/{rid}/reject` — `ActivityMapping` DETACH DELETE. 프론트는 pool 에서 제거. Rule 자체가 어느 Task 에도 붙지 않은 상태가 되면 `unassigned_rule_ids` 에 surface 되어 pool 에 다시 나타남.

**주의**: 이전 버전에서는 review_matches 가 DB 에 persist 안 되고 SSE 로만 프론트에 흘렀음. 2026-04-20 에 `save_mappings(review_mappings=...)` 로 수정되어 AM 노드가 정상 생성 → accept/reject 엔드포인트가 404 반환하던 버그 해소.

### 6.3 Navigator 배지 + Rules by Context
- Task 항목: `순번 + Task 이름 + R{N}` (매핑 Rule 수). enrichment 전 Task 는 `R` 배지 없음. **이전에 있던 주요 BC 칩은 제거** (Task 이름이 이미 의미를 전달하고, BC 분포는 아래 "Rules by Context" 섹션이 전담).
- **Rules by Context 섹션**: 세션 내 전체 Rule 을 `context_cluster` 별로 그룹핑한 카운트 요약. 각 행 hover → 강조, 클릭 → §6.5 BC Rules Modal 오픈.

### 6.4 BL 수동 제어 — Inspector 에서 Rule 별 조작

각 Rule 카드는 사용자가 BL 을 직접 제어할 수 있는 UI 를 제공 (구현: `HybridTaskInspector.vue`):

**ES 역할 변경 (드롭다운)**:
- ES 요소 배지 자체가 투명 `<select>` 오버레이로 덮여 있어 호버 시 dashed outline
- 5개 옵션 모두 선택 가능 (Aggregate / Command / Policy / ReadModel / External System) — 이모지·괄호 설명은 없는 plain 텍스트
- 변경 시 `PATCH /api/ingest/hybrid/rule/{sid}/{rid}/es-role` → `Rule.es_role` + `es_role_confidence = 1.0`
- 낙관적 업데이트로 즉시 화면 반영 — `hybridRules` flat list 와 모든 task.rules 에서 동시 갱신

**Rule 이동 / 제거 (⋯ 메뉴)**:
- Rule 카드 우측 `⋯` 버튼 클릭 → 팝오버 메뉴
- "다른 Task 로 이동" 섹션: 현 Task 제외 전체 Task 리스트, 클릭 시 `POST /rule/{rid}/move/{from}/{to}` 원자적 실행 (unassign + assign)
- "이 Task 에서 제거" 섹션 (danger red): `POST /rule/{rid}/unassign/{tid}`. 마지막 Task 에서 떨어지면 `unassigned_rule_ids` 에 등재되어 §6.2 pool 로 surface.

**엔드포인트 요약**:
```
POST   /api/ingest/hybrid/rule/{sid}/{rid}/unassign/{tid}
POST   /api/ingest/hybrid/rule/{sid}/{rid}/assign/{tid}
POST   /api/ingest/hybrid/rule/{sid}/{rid}/move/{from_tid}/{to_tid}
PATCH  /api/ingest/hybrid/rule/{sid}/{rid}/es-role           (body: {"es_role": "..."})
```

모든 수동 경로는 `method='manual', reviewed=true, confidence=1.0` 로 기록 — Phase 5 에서 user-confirmed 매핑임을 식별할 수 있도록.

### 6.5 BC Rules Modal — BC 단위 일괄 Rule 관리 (2026-04-20)

> Navigator "Rules by Context" 행 클릭 → 전체 Rule 을 BC 단위로 펼쳐 일괄 정리하는 모달. 구현: `HybridBcRulesModal.vue`

- **트리거**: Navigator 의 "Rules by Context" 행 (e.g., `인증이력관리 18`) 클릭 → `bpmnStore.openBcRulesModal(cluster)` → 모달 오픈
- **표시**: 해당 BC 에 속한 모든 Rule 을 카드 리스트로. 카드 당:
  - 역할 드롭다운 (5 옵션, §6.4 와 동일)
  - `source_function` + `BL.title`
  - **연결된 Task 목록** — 각 Task 옆 [이동…] 드롭다운 + [제거] 버튼
  - **"다른 Task 에 추가…"** 드롭다운 (이미 연결된 Task 는 자동 제외)
- **동작**: §6.4 엔드포인트 재사용. 낙관적 업데이트로 모달·Navigator·Inspector 가 즉시 동기화.
- **용도**: Task 단위 Inspector 에선 보기 어려운 "같은 BC 안의 rule 을 한꺼번에 재분배" 같은 일괄 편집 작업. `입력값 검증` Task 가 34 rule 로 과매칭 됐을 때 "BC 가 아닌 rule 들을 같이 골라 적절한 Task 로 이동" 하는 흐름에 적합.

---

## 7. 매핑 근거 요약 (Task 내부 섹션별)

`HybridTaskInspector` 에서 Task 하나를 열었을 때 각 섹션의 데이터가 어디서 오고 무슨 기준으로 붙었는지:

| 섹션 | 데이터 근거 | 붙는 기준 |
|---|---|---|
| Description | 문서 원문을 LLM 이 Phase 1 에서 요약 | "한 업무 활동" 단위 동사구 |
| Actors | 문서에서 Phase 1 LLM 이 추출 | Task 마다 1개 이상 Actor 매핑 |
| Source | Phase 1 의 `source_section` + Phase 4 의 `page` 힌트 | 문서 상 섹션/페이지 |
| 📄 Document Context | Phase 4.1 top-k=2 passage | Task 이름+설명+Actor 와의 임베딩 코사인 상위 2건 (항상 2건, score<0.5 면 low_confidence) |
| Rules (GWT) | Phase 2 Rule + Phase 3 매핑 | lexical/embedding/structural 증거로 REALIZED_BY. Rule 카드 헤더에 **ES 요소 배지** (Phase 2.6 `es_role`) + **BC 배지** (Phase 2.5 `context_cluster`). Rule 들은 BC 별로 그룹핑되어 표시. 배지 클릭으로 역할 변경, ⋯ 메뉴로 이동/제거 |
| Mapped Functions | Rule 의 `source_function` → analyzer DB FUNCTION 조인 | Rule 이 붙으면 속한 함수 자동 편입. `function_summary` 도 표시 |
| Conditions | Phase 4.2 LLM | 위 Document Context + Rules 를 근거로 LLM 생성 (근거 없으면 빈 배열) |

**ES 요소 배지 색상** (프로젝트 `--color-*` ES 팔레트):
- 🟨 Aggregate · 상태규칙 / Aggregate · 판정규칙 — `--color-aggregate` (같은 노란색, 한정어로 구분)
- 🟦 Command — `--color-command`
- 🟪 Policy — `--color-policy`
- 🟩 ReadModel — `--color-readmodel`
- 🟥 External System — pink

---

## 8. 튜닝 포인트

매핑 품질이 기대에 못 미칠 때 조정할 env / 코드 위치:

| 증상 | 조정 대상 |
|---|---|
| Rule 이 너무 많이/적게 나옴 | `rule_filters.py::INFRA_KEYWORDS`, `is_meaningful_gwt` 슬롯 수 |
| Task 당 rule 이 과매칭 | `HYBRID_LEXICAL_MAX_TOKEN_DF` ↓ (0.35 → 0.3), `HYBRID_LEXICAL_MIN_HITS` ↑ (2 → 3) |
| Rule 이 거의 매칭 안 됨 | `HYBRID_EMBED_THETA_AUTO` ↓ (0.5 → 0.45), `HYBRID_LEXICAL_MIN_HITS` ↓ (2 → 1), glossary 품질 점검 |
| Review queue 가 비어있음 | `HYBRID_EMBED_THETA_REVIEW` ↓ (0.4 → 0.35) |
| Passage 가 엉뚱한 구절을 뽑음 | `document_chunker.py` 헤딩 regex, 윈도우 크기 (400 → 300) |
| 조건 추출이 환각 생성 | `condition_extractor.py` SYSTEM_PROMPT 의 "근거 없으면 거부" 지침 강화 |
| 일반 함수(`main`/`proc`) 가 모든 Task 에 매칭 | `lexical_matcher.py::_HARD_STOPWORDS` 에 토큰 추가 |

---

## 8.1 개선 과제 상태 (상세는 PRD §8.2)

| 과제 | 상태 | 비고 |
|---|---|---|
| **BC 사전 태깅 (Phase 2.5)** | ✅ 완료 (2026-04-20) | `Rule.context_cluster` 부여. BC-aware lexical/embedding/structural 매칭 적용. 8 클러스터 분포 확보. 상세 §4.2.5 of PRD. |
| **DDD/ES 역할 태깅 (Phase 2.6)** | ✅ 완료 (2026-04-20) | `Rule.es_role` 부여. 결정론적 분류 + LLM 미사용. Phase 5 가 승격 대상 요소를 재판단할 필요 없음. 상세 §4.2.6 of PRD. |
| **BL 수동 제어 UI** | ✅ 완료 (2026-04-20) | 통합 "미매핑 / Review" 풀 + Inspector 내 역할 변경·Task 이동·제거. §6.2, §6.4. |
| **Review Queue persist 버그** | ✅ 완료 (2026-04-20) | `save_mappings` 가 review_matches 를 AM 노드로 저장하도록 수정. accept/reject 엔드포인트 정상 동작. |
| **Phase 5 재실행 (새 태그 반영)** | ⏳ | 현재 DB 의 Phase 5 산출물(BC=0~1, Policy=0) 은 태그 도입 이전. 재실행 시 BC 2~3, Policy 4~5 예상. PRD §8.2.5. |
| **전역 BL 관리 패널** | ⏳ | 세션 내 모든 Rule 을 한 화면에서 필터·검색·배치 수정 (PRD §8.2.4). 현재는 Task 별 / 풀 단위만 가능. |
| **Task 과매칭 잔재** | ⏳ | "입력값 검증" 등 일반적 Task 에 31+ rule 붙는 현상. BC 태깅 + 수동 제어로 완화 경로 제공. embedding θ 튜닝 또는 per-Task cap 추가 검토. |

---

## 9. Clear / Reset 정책

- **hybrid 라벨만 정리**: 새 업로드 직전 `DELETE /api/ingest/hybrid/reset` → `ALL_HYBRID_LABELS` (BpmTask / BpmActor / BpmSequence / Rule / GlossaryTerm / DocumentPassage / ActivityMapping / ExternalTable / HybridSession) 만 `DETACH DELETE`. **analyzer 노드는 절대 안 건드림**
- **analyzer DB** 는 외부에서 미리 import 된 상태를 전제. read-only 조회만
- **같은 Neo4j DB 공유 환경 안전**: `ANALYZER_NEO4J_DATABASE` 가 미설정이어도 (= hybrid 와 analyzer 가 default DB 공유) 정상 동작. 라벨로 구분되기 때문

### 9.1 Persistence 정책 — DB 가 Single Source of Truth (2026-04-15)

- **Neo4j 가 유일한 저장소** — hybrid ingestion 이 생성하는 모든 데이터(actors / tasks / rules / passages / glossary / mappings / bpmn_xml) 는 Neo4j 에만 저장.
- **localStorage** 는 **`hybrid.session_id` (세션 식별자 문자열 한 개)** 만 보관. 데이터 복제 X.
- **콜드 로드**: 페이지 새로고침 시 `BpmnPanel.vue::onMounted` 가 `bpmnStore.hybridSessionId` 확인 → 있으면 `rehydrateHybrid()` → `GET /api/ingest/hybrid/session/{sid}/snapshot` 로 전체 상태 복원.
- **세션 마커**: `:HybridSession {id, session_id, bpmn_xml, updated_at}` 노드가 Phase 1 종료 시점에 생성. BPMN XML 을 별도로 DB 에 보존.
  - 주의: `save_bpm_skeleton` 시점에는 A2A 결과 XML 이 전파 안 된 채일 수 있어 **직후** `save_session_bpmn_xml(session_id, final_xml)` 호출이 필요. `final_xml = skeleton.bpmn_xml or build_bpmn_xml(skeleton)` 가 결정된 뒤 저장됨 (2026-04-15 버그 수정).
- **pdf2bpmn 라벨 충돌 해소**: `save_bpm_skeleton` 직후 `relabel_pdf2bpmn_nodes(session_id)` 가 `:Event/:Gateway/:Process` 중 pdf2bpmn 고유 프로퍼티(`event_type/gateway_type/proc_id`) 를 가진 노드를 `:BpmnEvent/:BpmnGateway/:BpmnProcess` 로 rename + session_id 태그. 이후 Phase 5 의 도메인 `:Event` 와 의미·쿼리 둘 다 깔끔히 분리.
- **왜 바꿨나**: 기존 `hybrid.bpmn.v1` 키에 전체 상태를 중복 저장 → DB 리셋 시 ghost 데이터 표시 / mutation 마다 수동 sync 호출로 누락 위험 / 큰 PDF 에서 quota 부담. 1회 DB fetch 로 교체하는 편이 명확하고 안전.

### 9.2 프론트 Rehydrate 경로

```
페이지 로드
  └─ BpmnPanel.vue onMounted
       └─ if (bpmnStore.hybridSessionId)
            └─ bpmnStore.rehydrateHybrid()
                 └─ GET /api/ingest/hybrid/session/{sid}/snapshot
                 └─ store 에 actors/tasks/rules/glossary/review_queue/bpmnXml 채움
                 └─ activeBpmnXml 세팅 → 캔버스 자동 렌더
```

---

## 10. Phase 5 현황 + 남은 작업

### 10.1 Phase 5 — Event Storming 승격 (⚠️ 재실행 필요)

**핵심 결정 (B 구조)**: 별도 모듈로 작성하지 않고, 기존 ingestion workflow 를 `source_type="hybrid"` 분기로 **100% 재사용**. 1500+ 줄 자체 구현을 폐기하고 200줄 글루로 통합. 상세: `Hybrid_Phase5_EventStorming_Promotion.md`

- **트리거**: 이벤트 스토밍 탭 → "모델 생성" 버튼 → `POST /api/ingest/hybrid/{hsid}/promote-to-es`
- **US 도출**: `(BpmTask × source_function 클러스터)` = 1 UserStory. DF 컷오프(>50% Task 매핑 fn 제외) + Top-1 attribution
- **후처리 hook**: ES 노드 session_id 태깅 + PROMOTED_TO 부착 + orphan US 안전망 + cross-BC Policy 자동 탐지

### 10.2 기존 1차 실행 결과 (Phase 2.5/2.6 도입 **이전**)

| 산출물 | 개수 | 평가 |
|---|---|---|
| UserStory | 9 | ✅ |
| Aggregate | 8 | ✅ |
| Command | 9 | ✅ |
| ReadModel | 8 | ✅ |
| PROMOTED_TO 엣지 | 9 | ✅ |
| **BoundedContext** | **1** | ⚠️ LLM collapse |
| **Policy** | **0** | ⚠️ BC 1개 → cross-BC 불가 |

### 10.3 Phase 2.5/2.6 도입 이후 — 재실행 시 기대 효과

- **BC 2~3 개 예상**: 8 `context_cluster` → LLM 이 domain seed 로 받아 "실시간인증 (core)" + "공통코드 / 외부연동 (supporting)" 등 2~3 BC 로 묶을 수 있음.
- **Policy 4~5 개 예상**: `es_role='policy'` 인 5 개 Rule (b800 4 + b000 1) 이 결정론적으로 식별되어 BC 와 무관하게 Policy 노드 생성.
- **LLM 호출량 감소** (§11 참조): BoundedContext/Aggregate/ReadModel 식별에 LLM 불필요. 이름 확정만 LLM. 총 ~20회 → ~8회 예상.
- **결정론적 분류 + manual override 존중**: user 가 `method='manual'` 로 확정한 매핑은 Phase 5 가 재분석 없이 그대로 승격.

### 10.4 남은 작업

| 작업 | 상태 | 설명 |
|---|---|---|
| Phase 5 재실행 (새 태그 소비) | ⏳ | `promote_to_es.py` 내부 로직이 `context_cluster` + `es_role` 을 primary input 으로 사용하도록 수정. PRD §8.2.5. |
| 전역 BL 관리 패널 | ⏳ | 세션 내 모든 Rule 을 한 화면에서 필터·검색·배치 수정 (PRD §8.2.4) |
| Event Modeling 뷰어 session_id 필터 | ⏳ | 동시 세션 시 오염 방지 |
| Phase E 정식 병합 | ⏳ | `source_type="hybrid"` 정식 라우팅, Dev 버튼 제거 |

---

## 11. ES 승격 고려사항 — Phase 5 가 무엇을 가지고 시작하는가

> 2026-04-20 추가. Phase 2.5 (BC 태깅) + Phase 2.6 (역할 태깅) + BL 수동 제어가 도입된 이후, Phase 5 (Event Storming 승격) 가 소비해야 할 **정제된 입력 계약**을 정리한다.

### 11.1 Rule 이 Phase 5 에 도달하는 시점의 상태

각 `Rule` 노드는 이미 다음 3 축으로 분류되어 있음 — Phase 5 가 재분류할 필요 없음:

| 축 | 프로퍼티 | 결정 단계 | 승격 결정에의 기여 |
|---|---|---|---|
| **업무 도메인** | `context_cluster: str` | Phase 2.5 (prefix + 재분배 + LLM naming) | BoundedContext seed |
| **DDD 역할** | `es_role: str` | Phase 2.6 (결정론 3-신호) | 어느 ES 노드로 승격할지 직접 지정 |
| **신뢰도 / 출처** | `es_role_confidence: float`, REALIZED_BY `method` | Phase 2.6 + Phase 3 + 사용자 조작 | manual override 식별 |

### 11.2 역할 → ES 요소 승격 매트릭스

각 `es_role` 의 rule 이 Phase 5 에서 어떤 ES 노드로 번역되는지:

| `es_role` | ES 요소 | 승격 방식 | 개수 추정 (52 rule 기준) |
|---|---|---|---|
| `aggregate` | **Aggregate** | 소속 Task 의 Aggregate 에 부착. Phase 5 내부에서 `rule.writes_tables` 유무로 **불변식 섹션** (WRITES 있음) vs **도메인 규칙 섹션** (WRITES 없음) 재분류. `rule.writes_tables[0]` 가 Aggregate root 후보 | 25 → ~5~8 aggregate (source_function + WRITES Table 공유 합산) |
| `validation` | **Command** | 소속 Task 의 Command 의 precondition / guard. 다수의 validation rule 이 한 Command 에 모여 배치됨 | 18 → ~9 command (Task 당 1~2) |
| `policy` | **Policy** | 독립 Policy 노드 생성. `rule.source_function` 계열로 묶어 하나의 Policy 후보 | 5 → ~3~4 policy (fn 계열 merge) |
| `query` | **ReadModel** | `rule.reads_tables` 로 ReadModel 의 source 결정 | 3 → ~2 readmodel |
| `external` | **승격 제외** | ACL / Gateway 로 문서에만 기록, ES 노드 생성 X | 1 → 0 |

**총합 추정**: Aggregate ~6 + Command ~9 + Policy ~3 + ReadModel ~2 = **~20 ES 노드** (BoundedContext + UserStory 별도)

> 2026-04-20 정리: `invariant` + `decision` 두 역할을 `aggregate` 로 통합. 둘 다 같은 Aggregate 내부에 귀속되고, sub-classification 은 `writes_tables` 속성으로 Phase 5 가 결정론적으로 재도출 가능하므로 별도 태그 유지 불필요.

### 11.3 BoundedContext 식별 — `context_cluster` 를 seed 로

Phase 5.A (BoundedContext 식별) 는 더 이상 전체 Task+Rule 을 raw 로 LLM 에 던지지 않음. 입력이 이미 정제됨:

```
Input:
  - context_cluster 목록 (예: [인증이력관리, 입력값검증, 인증결과판정, 오류메시지처리,
                              실시간인증진입, 공통코드검증, 간편결제사검증, 카드사정보검증])
  - 각 cluster 에 속한 rule 수 + sample titles
  - ExternalTable 공유 관계 (인증이력관리 의 WRITES 테이블)

LLM 지시:
  "이 8 개 cluster 를 2~3 개의 BoundedContext 로 묶어라. Core / Supporting 구분 가능."

Expected output:
  - "실시간인증" (Core) ← 인증결과판정 + 인증이력관리 + 입력값검증 + 오류메시지처리 + 실시간인증진입
  - "공통코드" (Supporting) ← 공통코드검증 + 간편결제사검증
  - "외부연동" (Supporting / ACL) ← 카드사정보검증
```

> 단일 도메인 BPM 이어도 "core vs supporting" 분할은 나올 수 있음. LLM 이 여전히 1개로 묶으면 **폴백**: cluster 를 그대로 BC 로 사용 (상한 = cluster 수).

### 11.4 Aggregate 식별 — `aggregate` + WRITES 로 결정론적

Phase 5.B 는 LLM 을 **이름 확정에만** 사용:

```
결정론 단계 (LLM 불필요):
  1. es_role='aggregate' Rule 을 source_function 으로 그룹
  2. WRITES Table 이 있는 rule 집합을 Aggregate invariant 그룹, 없는 rule 은 해당
     Aggregate 의 도메인 규칙 그룹에 배치
  3. 같은 WRITES Table 을 공유하는 fn 군을 합쳐 Aggregate 후보
  4. Root Table = 그 WRITES Table (예: ZPAY_AP_RLTM_AUTH_HST)
  5. Member functions = fn 군

LLM 단계 (이름만):
  "이 WRITES=ZPAY_AP_RLTM_AUTH_HST, fn=[b200/b205/b210/b400/b410] 의
   Aggregate 이름을 한국어 도메인 용어로 제시." → "AuthHistory" 또는 "실시간인증이력"
```

**Aggregate 내부 배치**:
- `aggregate` role + WRITES 있음 → **불변식 (state invariant)** 섹션
- `aggregate` role + WRITES 없음 → **도메인 규칙 (business rule)** 섹션

UI 에선 단일 Aggregate 배지로 보이지만, Phase 5 가 Aggregate spec 을 쓸 때 이 2 섹션으로 자동 분리. 이는 Event Storming 스티커 표준에서 "Aggregate + business rule" 이 한 덩어리로 다뤄지는 것과 일치.

> **주의 — WRITES 상속 효과**: `EVALUATES{direction:WRITES}` 엣지는 Phase 3.3 에서 **함수 레벨**로 생성됨. 오케스트레이터 함수(`b000_main_proc` 등) 의 모든 BL 은 해당 함수의 WRITES 를 상속받아 표시되므로, 순수 판정 BL(예: "반영여부가 N 이면 …") 도 WRITES 있는 것처럼 보인다. 실측: 25 aggregate rule 중 24 가 WRITES 상속, 1 만 순수. Phase 5 의 sub-classification 은 이를 **approximate 힌트**로 취급하고, 필요 시 LLM 이 title/then 으로 재확인.

### 11.5 Policy 식별 — `policy` role 단독으로 충분

기존 Phase 5.D 는 Rule 50+ 를 함수별로 재그룹해 LLM 에 "policy 인가?" 묻는 구조. 이제:

```
1. es_role='policy' Rule 만 필터 → 5 건
2. source_function 으로 그룹 → b800 4 건 (오류메시지) + b000 1 건
3. 각 그룹 → 하나의 Policy:
   - name: "OnAuthFailedBuildErrorMessage" 같은 트리거 기반 이름
   - trigger_event: 매핑된 Task 의 Event 후보
   - invoke: 메시지 생성 행위
4. LLM 은 이름 + description 만 작성
```

**Cross-BC Policy 탐지**: trigger_event 와 invoke_command 가 다른 BC 에 걸치면 `kind='cross_bc'` 자동 지정.

### 11.6 manual override 의 취급

사용자 수동 조작의 흔적은 3 가지 프로퍼티로 식별됨:

| 흔적 | 의미 | Phase 5 처리 |
|---|---|---|
| `REALIZED_BY.method = 'manual'` | 사용자가 assign/move 로 명시 연결 | 재검증 없이 그대로 승격. 삭제/이동 불가 |
| `REALIZED_BY.reviewed = true` | 사용자가 승인 또는 수동 연결 | 같음 |
| `Rule.es_role_confidence = 1.0` | 사용자가 역할 변경 | 역할 재분석 없이 1.0 confidence 의 선언으로 채택 |

> **원칙**: user-confirmed 매핑은 Phase 5 의 자동 판단보다 우선. 휴리스틱 재실행 시에도 manual 흔적이 있는 rule 은 그대로 유지.

### 11.7 미매핑 / Review 잔존 rule 의 승격 규칙

Phase 5 시작 시 통합 "미매핑 / Review" 풀에 남은 rule 은 다음과 같이 처리:

| 상황 | Phase 5 처리 |
|---|---|
| `unassigned` Rule (REALIZED_BY 없음) | **승격 제외**. UserStory / Command 에 붙지 않으므로 Aggregate invariant 로도 못 감. 남아있으면 "잉여 business logic" 으로 보고서에 별도 기록 |
| `review` Rule (AM 있고 REALIZED_BY 없음) | **승격 제외**. 사용자가 명시 승인하지 않았으므로 비결정적 제안 상태로 간주. Phase 5 후 재실행 시 user 가 accept 하면 재승격 |

> 다시 말해 **Phase 5 는 REALIZED_BY 엣지가 있는 rule 만 소비**. 풀에 남은 것은 session 산출물의 완성도 지표로 surface 될 뿐.

### 11.8 Phase 5 재실행 멱등성 계약

태그 도입으로 같은 session 을 재실행해도 결과가 수렴하는지가 중요해짐:

- **결정론 보장 부분**: Phase 2.5 prefix/재분배 (LLM naming 제외), Phase 2.6 역할 분류, Phase 5.B/D/F 의 결정론 단계
- **비결정론 잔존**: Phase 2.5 LLM naming (cluster 이름만 달라질 수 있음 — cluster 멤버십은 동일), Phase 5.A BoundedContext 그룹핑
- **멱등 대응**: 모든 Phase 5 쓰기는 `MERGE` 사용 + `session_id` 태그 → 재실행 시 중복 노드 생성 없이 덮어쓰기. 사용자 manual override 는 항상 우선.

### 11.9 Phase 5 관점의 미완 영역

| 항목 | 설명 |
|---|---|
| `external` role 의 표현 | Gateway / ACL / Anti-Corruption Layer 로 문서에 기록하는 방법 표준화 필요. 현재 ES 노드는 안 만듦. |
| 여러 Task 공유 rule | 한 rule 이 N Task 에 REALIZED_BY 인 경우(현재 평균 1.79/rule), 어느 Aggregate/Command 에 귀속할지. Top-1 attribution 기준 유지 (기존 설계) |
| 같은 함수 여러 역할 | 드묾 (b800 내부는 모두 policy, a000 내부는 모두 validation) 하지만 발생 가능. 역할이 mix 된 함수 → Aggregate 내 다중 section 또는 Policy 분리 |
| 과매칭 Task 의 rule 정리 | "입력값 검증" 같은 generic-name Task 가 34+ rule 을 흡수하는 현상. Phase 3 임계치 튜닝 vs 사용자 수동 정리(§6.4) 병행. |

---

## 부록 A. 조회 예시 (생성 결과 검증)

```cypher
// 모든 라벨 카운트
MATCH (n) RETURN labels(n)[0] AS label, count(n) AS c ORDER BY c DESC;

// Task 당 enrichment 현황
MATCH (t:BpmTask)
OPTIONAL MATCH (t)-[:REALIZED_BY]->(r:Rule)
OPTIONAL MATCH (t)-[:SOURCED_FROM]->(p:DocumentPassage)
RETURN t.sequence_index, t.name,
       count(DISTINCT r) AS rules,
       count(DISTINCT p) AS passages,
       size(coalesce(t.conditions, [])) AS conditions
ORDER BY t.sequence_index;

// Phase 2.5 — context_cluster 분포
MATCH (r:Rule)
RETURN coalesce(r.context_cluster, '<null>') AS cluster, count(r) AS c
ORDER BY c DESC;

// Phase 2.6 — es_role 분포 + 평균 신뢰도
MATCH (r:Rule)
RETURN coalesce(r.es_role, '<null>') AS role,
       count(r) AS c,
       avg(r.es_role_confidence) AS avg_conf
ORDER BY c DESC;

// BC × Role 교차표 (의미 정합성 검증)
MATCH (r:Rule)
RETURN coalesce(r.es_role, '?') AS role,
       coalesce(r.context_cluster, '?') AS bc,
       count(r) AS c
ORDER BY role, bc;

// ES 승격 예상 — 각 role 별 예상 대상
MATCH (r:Rule)
WITH r.es_role AS role, count(r) AS c
RETURN role,
       CASE role
         WHEN 'invariant'  THEN 'Aggregate'
         WHEN 'decision'   THEN 'Aggregate'
         WHEN 'validation' THEN 'Command'
         WHEN 'policy'     THEN 'Policy'
         WHEN 'query'      THEN 'ReadModel'
         WHEN 'external'   THEN '(승격 제외)'
       END AS promote_to,
       c
ORDER BY c DESC;

// 특정 Task 의 매핑 상세 (BC + 역할 포함)
MATCH (t:BpmTask {name: '입력값 검증'})-[link:REALIZED_BY]->(r:Rule)
RETURN r.source_function, r.context_cluster, r.es_role,
       link.confidence, link.method, r.title LIMIT 20;

// 미매핑 rule 풀 (§6.2 통합 pool)
MATCH (r:Rule)
WHERE NOT EXISTS {
  MATCH (:BpmTask)-[:REALIZED_BY]->(r)
}
RETURN r.id, r.source_function, r.context_cluster, r.es_role, r.title;

// Review band AM (제안만 있고 엣지 없는 것)
MATCH (am:ActivityMapping) WHERE am.reviewed = false
OPTIONAL MATCH (t:BpmTask {id: am.task_id})-[r:REALIZED_BY]->(:Rule {id: am.rule_id})
WHERE r IS NULL
RETURN am.task_id, am.rule_id, am.score, am.method;

// Manual override 흔적 (사용자 확정 매핑)
MATCH (t:BpmTask)-[link:REALIZED_BY]->(r:Rule)
WHERE link.method = 'manual' OR link.reviewed = true
RETURN t.name AS task, r.source_function AS fn, r.es_role AS role,
       link.method, link.reviewed, link.confidence;
```

또는 HTTP:
```bash
curl http://localhost:8000/api/ingest/hybrid/debug/{session_id} | jq
```
