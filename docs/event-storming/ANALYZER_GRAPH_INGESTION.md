# Analyzer Graph Ingestion — 구조 및 처리 절차

> robo-data-analyzer가 Neo4j에 저장한 레거시 코드 분석 그래프를 입력받아 Event Storming 모델을 자동 생성하는 파이프라인.
> 최종 갱신: 2026-04-10

---

## 1. 전체 흐름 개요

```
robo-data-analyzer → Neo4j 그래프 (FUNCTION, BusinessLogic, Actor, Table 노드)
    ↓
① source_type = "analyzer_graph"
    ↓
② graph_context_builder.py → 관련 함수 그룹핑 (Union-Find: 테이블/접두사 기준)
    ↓
③ graph_to_user_stories.py → 그룹 단위 US 생성 (analyzer 전용 프롬프트)
    ↓
④ SOURCED_FROM 관계 생성 (US → BL, sequence 기반 매칭)
    ↓
⑤ Events 배치 추출 (source_unit_id 기준 그룹핑, BL 컨텍스트 주입)
    ↓
⑥ BC 식별 (이벤트 클러스터링 힌트 + 함수 단위 과분리 방지 가이드)
    ↓
⑦ 이후 Phase Chain (Aggregate → Command → ReadModel → Properties → Policy → GWT → UI)
    ↓
⑧ Neo4j 그래프 완성
```

### 핵심 설계 원칙

- **관련 함수 그룹핑**: Union-Find로 같은 테이블/접두사 함수를 묶어 배치 US 생성 (함수 1:1 → 그룹 배치)
- **BL 컨텍스트 전 Phase 전달**: `format_us_text()`로 US 텍스트에 BL Given/When/Then 자동 합침
- **이벤트 배치 추출**: analyzer_graph는 source_unit_id 기준 10개씩 묶어 이벤트 통합 추출
- **출처 추적**: US → SOURCED_FROM → BL → FUNCTION 체인으로 모든 DDD 노드 역추적 가능

---

## 2. 모듈 구조

```
api/features/ingestion/
├── figma_to_user_stories.py              ← figma 전용 (독립)
├── requirements_to_user_stories.py       ← rfp 전용 (독립)
├── analyzer_graph/
│   ├── graph_context_builder.py          ← Neo4j 조회 + 함수 그룹핑 (Union-Find)
│   └── graph_to_user_stories.py          ← analyzer 전용 US 생성 (독립)
├── workflow/
│   ├── utils/
│   │   └── user_story_format.py          ← 공통 US 포맷터 (BL 자동 합침)
│   └── phases/
│       ├── user_stories.py               ← source_type 분기 + BL 캐시 로딩
│       ├── events_from_user_stories.py   ← analyzer: 배치 추출 / rfp: 개별 추출
│       ├── bounded_contexts.py           ← 이벤트 클러스터 힌트 + analyzer 통합 가이드
│       ├── aggregates.py                 ← format_us_text + 테이블 스키마
│       ├── commands.py                   ← format_us_text
│       ├── policies.py                   ← format_us_text + coupled_domain 힌트
│       ├── readmodels.py                 ← format_us_text
│       └── properties.py                 ← 테이블 스키마
```

---

## 3. US 생성 (Phase 1) — 관련 함수 그룹핑 배치 처리

### graph_context_builder.py — 함수 그룹핑

`build_grouped_unit_contexts()` 함수가 관련 함수를 도메인 그룹으로 묶어 컨텍스트 생성:

**그룹핑 알고리즘** (Union-Find):
1. Neo4j에서 BL이 있는 모든 함수 + READS/WRITES 테이블 조회
2. **같은 테이블**을 READS/WRITES하는 함수끼리 연결
3. **같은 접두사**를 가진 함수끼리 연결 (ValidateAutoDebit*, ProcessAutoDebit* → AutoDebit 그룹)
4. 연결된 컴포넌트 = 하나의 도메인 그룹
5. 큰 그룹은 8개 함수씩 서브 배치로 분할

```
기존 (함수 1개씩):
  ValidateAutoDebitInput   → LLM → US 5개
  ProcessAutoDebitApp      → LLM → US 4개  (중복 포함)
  ChangeAutoDebitAccount   → LLM → US 3개  (중복 포함)
  = 12개 US, 3회 LLM 호출

개선 (그룹 배치):
  [ValidateAutoDebitInput + ProcessAutoDebitApp + ChangeAutoDebitAccount]
    → LLM → US 6개 (통합, 중복 없음), 1회 LLM 호출
```

### 그룹 컨텍스트 형식

```
# Domain Group: AutoDebit (3 functions)
Related functions that operate on the SAME business domain.
Shared Tables: AUTOPAY_ACCOUNT, AUTOPAY_HISTORY, SUBSCRIBER

## ValidateAutoDebitInput
Actor: 운영자
Flow: BL[1] → BL[2] → BL[3]*
  - BL[1]: 입력값 필수항목 검증
  - BL[2]: 계좌번호 형식 검증
  - BL[3] [★ AccountValidation]: 계좌 정합성 검증

## ProcessAutoDebitApplication
Actor: 운영자
Flow: BL[1] → BL[2] → BL[3]
  ...

### GROUP-LEVEL GUIDELINES:
- These functions are in the SAME business domain — create UNIFIED User Stories
- Target: 3~10 User Stories for this group of 3 functions
```

### graph_to_user_stories.py — US 추출

analyzer 전용 프롬프트로 US 생성:
- 관련 BL들을 의미 단위로 묶어 US 변환
- `source_bl` 필드에 출처 BL 번호 태깅
- Actor 정보를 role로 활용
- 인프라 코드(EJB lifecycle, getter/setter) 자동 필터

---

## 4. SOURCED_FROM 관계

US 생성 후 `source_bl` 값으로 Neo4j에 정확한 관계 생성:

```cypher
MATCH (us:UserStory {id: $us_id})
MATCH (f:FUNCTION {function_id: $unit_id})-[:HAS_BUSINESS_LOGIC]->(bl:BusinessLogic)
WHERE bl.sequence IN $sequences
MERGE (us)-[:SOURCED_FROM]->(bl)
```

---

## 5. BL 전달 (Phase 2 이후)

`format_us_text()` 함수가 US 텍스트에 BL 정보를 자동으로 합침:

```
[US-005] As a 운영자, I want to 청구서를 생성한다, so that 월별 요금을 정산
    [비즈니스 흐름] BL[1] → BL[2] → BL[3]*
    [도메인 커플링] BL[3]→PaymentDomain (★ = 분리 대상)
    [비즈니스 규칙]
    - BL[1]: 가입자 식별값이 없으면 즉시 거부
      Given: ...
      When: ...
      Then: ...
    - BL[2]: 청구연월 없으면 현재 연월로 보정
```

- `bl_by_user_story` 캐시: Phase 1 완료 후 SOURCED_FROM에서 조회하여 ctx에 저장
- rfp/figma: bl_map 빈 dict → BL 없이 기존과 동일 출력

---

## 6. Phase별 분석 결과 활용 현황

| Phase | BL 컨텍스트 | 테이블 스키마 | analyzer 전용 로직 |
|-------|-----------|-------------|-----------------|
| **US 생성** | ✅ BL → US 변환 | - | ✅ 함수 그룹핑 배치 (Union-Find) |
| US Sequencing | ✅ format_us_text | - | - |
| **Events** | ✅ BL Given/When/Then 주입 | - | ✅ source_unit_id 배치 추출 + 과생성 방지 |
| **BC 식별** | ✅ format_us_text | - | ✅ 이벤트 클러스터 힌트 + 통합 가이드 |
| Aggregates | ✅ format_us_text | ✅ fetch_table_schemas | - |
| Commands | ✅ format_us_text | - | - |
| ReadModels | ✅ format_us_text | - | - |
| Properties | - | ✅ fetch_table_schemas | - |
| **Policies** | ✅ format_us_text | - | ✅ coupled_domain → cross-BC 힌트 |
| GWT | ✅ format_us_text | - | - |

### Phase 간 컨텍스트 전달 체인

```
Phase 1 (US 그룹 배치) ──✅──→ Phase 3 (Sequencing)   ← format_us_text + BL
Phase 1 (US)           ──✅──→ Phase 4 (Events 배치)   ← BL Given/When/Then + accumulated events
Phase 4 (Events)       ──✅──→ Phase 5 (BC)            ← 이벤트 도메인 클러스터링 힌트
Phase 5 (BC)           ──✅──→ Phase 6 (Aggregates)    ← BC 구조 + 이벤트 + 테이블 스키마
Phase 6 (Agg)          ──✅──→ Phase 7 (Commands)      ← Aggregate + scoped events
Phase 7 (Cmd)          ──✅──→ Phase 8 (ReadModels)    ← BC events + cross-BC events
All phases             ──✅──→ Phase 12 (Policies)     ← coupled_domain cross-BC 힌트
```

---

## 7. 개선 이력

### US 생성 — 관련 함수 그룹핑 배치 처리

기존에는 함수 1개당 1회 LLM 호출로 US를 생성했으나, 관련 함수들이 서로를 모르고 중복 US를 생성하는 문제가 있었음.

**개선**: `build_grouped_unit_contexts()`로 Union-Find 기반 도메인 그룹핑:
- 그룹당 최대 8개 함수, 3~10개 통합 US 목표
- LLM 호출 수 대폭 감소 (함수 수 → 그룹 수)

### Events Phase — BL 컨텍스트 + 배치 추출

기존에는 US 1개씩 이벤트를 추출하여 과생성(1280개) 발생.

**개선**:
- analyzer_graph: `source_unit_id` 기준 10개씩 배치 LLM 호출
- BL Given/When/Then을 `<business_rules>` 섹션으로 프롬프트에 주입
- "분기별 검증은 별도 이벤트가 아님, 고수준 비즈니스 결과로 통합" 규칙

### BC 식별 — 이벤트 클러스터 힌트 + 통합 가이드

기존에는 BC가 이벤트 구조를 모르고 US 텍스트만으로 판단하여 과다 생성(82~113개).

**개선**:
- 이벤트 도메인 클러스터링 힌트 (PascalCase 접두사 기반, 전 source_type 공통)
- analyzer_graph 전용 통합 가이드: 함수 접두사 그룹핑, 테이블 기준 그룹핑, 목표 5~15 BC

### Policies — coupled_domain 기반 cross-BC 힌트

기존에는 대량 이벤트/커맨드에서 cross-BC 연결을 추론해야 하여 3개만 생성.

**개선**: BL의 coupled_domain에서 "source BC → target domain" 매핑을 추출하여 Policy 프롬프트에 주입.

---

## 8. 출처 추적 (Traceability)

기존 관계 체인으로 모든 DDD 노드의 원본 역추적 가능:

```
Command/ReadModel ← US → SOURCED_FROM → BL → function_id → FUNCTION
Aggregate ← Command ← US → source_unit_id → FUNCTION → READS/WRITES → Table
Event ← EMITS ← Command ← US → SOURCED_FROM → BL
Policy → TRIGGERS ← Event + INVOKES → Command (양쪽 함수까지 역추적)
```

별도 관계/속성 추가 불필요. 프론트에서 Cypher 쿼리로 조회.

---

## 9. rfp/figma 영향

| 항목 | rfp/figma 영향 |
|------|---------------|
| graph_context_builder.py | 없음 (analyzer 전용 모듈) |
| graph_to_user_stories.py | 없음 (analyzer 전용 모듈) |
| format_us_text | 없음 (bl_map 빈 dict → 기존과 동일) |
| bl_by_user_story | 없음 (analyzer_graph일 때만 로딩) |
| Events 배치 추출 | 없음 (analyzer_graph일 때만 활성화) |
| 이벤트 클러스터 힌트 | **공통 적용** (events_from_us가 있으면 동작) |
| BC 통합 가이드 | 없음 (analyzer_graph일 때만 주입) |
| coupled_domain 힌트 | 없음 (bl_map 비어있으면 스킵) |

---

## 10. 연쇄 개선 효과

```
개선 전:
  함수 1개씩 US (250회 LLM) → US 567개 → Event 1280개 (1개씩)
    → BC 82개 → Policy 12개 → 프로세스 고립

개선 후:
  관련 함수 그룹 배치 US (~30~50회 LLM) → US 대폭 감소
    → Event 배치 추출 (10개씩) → Event 200~400개
      → BC 이벤트 클러스터 + 통합 가이드 → BC 5~15개
        → Policy coupled_domain 힌트 → cross-BC 연결 정확
```
