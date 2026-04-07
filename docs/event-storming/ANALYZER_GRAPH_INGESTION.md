# Analyzer Graph Ingestion — 구조 및 처리 절차

> robo-data-analyzer가 Neo4j에 저장한 레거시 코드 분석 그래프를 입력받아 Event Storming 모델을 자동 생성하는 파이프라인.
> 최종 갱신: 2026-04-07

---

## 1. 전체 흐름 개요

```
robo-data-analyzer → Neo4j 그래프 (FUNCTION, BusinessLogic, Actor, Table 노드)
    ↓
① source_type = "analyzer_graph"
    ↓
② graph_to_report.py → 함수별 컨텍스트 생성 (Actor + BL + summary + Tables)
    ↓
③ graph_to_user_stories.py → US 생성 (analyzer 전용 프롬프트)
    ↓
④ SOURCED_FROM 관계 생성 (US → BL, sequence 기반 매칭)
    ↓
⑤ Phase Chain (BC → Aggregate → Command → Event → ReadModel → Properties → Policy → GWT → UI)
    ↓
⑥ Neo4j 그래프 완성
```

### 핵심 설계 원칙

- **US 생성은 analyzer_graph 전용 모듈** (`graph_to_user_stories.py`)에서 처리 — rfp/figma 프롬프트와 분리
- **이후 Phase는 공통 파이프라인** 사용 — US 텍스트에 BL 정보를 합쳐서 전달 (`format_us_text`)
- **출처 추적**: US → SOURCED_FROM → BL → FUNCTION 체인으로 모든 DDD 노드 역추적 가능

---

## 2. 모듈 구조

```
api/features/ingestion/
├── figma_to_user_stories.py              ← figma 전용 (독립)
├── requirements_to_user_stories.py       ← rfp 전용 (독립)
├── analyzer_graph/
│   ├── graph_to_report.py                ← Neo4j 조회 → 함수별 컨텍스트 텍스트
│   └── graph_to_user_stories.py          ← analyzer 전용 US 생성 (독립)
├── workflow/
│   ├── utils/
│   │   └── user_story_format.py          ← 공통 US 포맷터 (BL 자동 합침)
│   └── phases/
│       ├── user_stories.py               ← source_type 분기 + BL 캐시 로딩
│       ├── bounded_contexts.py           ← format_us_text 사용
│       ├── aggregates.py                 ← format_us_text 사용
│       ├── commands.py                   ← format_us_text 사용
│       ├── policies.py                   ← format_us_text 사용
│       ├── readmodels.py                 ← format_us_text 사용
│       └── user_story_sequencing.py      ← format_us_text 사용
```

---

## 3. US 생성 (Phase 1)

### graph_to_report.py — 컨텍스트 생성

`build_unit_contexts()` 함수가 Neo4j에서 BL이 있는 함수만 조회하여 텍스트 컨텍스트를 생성:

```
## svc_bill_generate
Actor: 운영자
Tables: READS: SUBSCRIBER, PLAN, BILL | WRITES: BILL

### 비즈니스 규칙 (프로세스 흐름 순서):
  - BL[1]: 가입자 식별값이 없으면 즉시 거부
    Given: ...
    When: ...
    Then: ...
  - BL[2]: 청구연월 없으면 현재 연월로 보정
  ...

### 함수 요약:
가입자의 월별 청구서를 생성하고 할인을 적용하는 처리...
```

전달 정보: **Actor + 테이블(READS/WRITES) + BL(sequence/coupled_domain/title/GWT) + 함수 summary**

### graph_to_user_stories.py — US 추출

analyzer 전용 프롬프트로 US 생성:
- BL을 의미 단위로 묶어 US 변환
- `source_bl` 필드에 출처 BL 번호 태깅
- Actor 정보를 role로 활용

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

## 6. 출처 추적 (Traceability)

기존 관계 체인으로 모든 DDD 노드의 원본 역추적 가능:

```
Command/ReadModel ← US → SOURCED_FROM → BL → function_id → FUNCTION
Aggregate ← Command ← US → source_unit_id → FUNCTION → READS/WRITES → Table
Event ← EMITS ← Command ← US → SOURCED_FROM → BL
Policy → TRIGGERS ← Event + INVOKES → Command (양쪽 함수까지 역추적)
```

별도 관계/속성 추가 불필요. 프론트에서 Cypher 쿼리로 조회.

---

## 7. rfp/figma 영향

| 항목 | rfp/figma 영향 |
|------|---------------|
| graph_to_user_stories.py | 없음 (analyzer 전용 모듈) |
| format_us_text | 없음 (bl_map 빈 dict → 기존과 동일) |
| bl_by_user_story | 없음 (analyzer_graph일 때만 로딩) |
| source_bl | 없음 (기본값 빈 리스트, rfp 프롬프트에 지침 없음) |
