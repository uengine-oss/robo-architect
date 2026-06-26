> ⚠️ **SUPERSEDED (2026-06-26, spec 044)**: 이 문서의 analyzer-그래프 소비 계약 부분(노드 라벨/식별자/멤버십·흐름 엣지 명세, 특히 §C9)은 **stale** 입니다 — 옛 `:FUNCTION/:MODULE`+`id`·`HAS_FUNCTION/BELONGS_TO_PACKAGE` 기술이 생산자 현행 출력·소비자 실제 코드와 불일치. **권위 단일 계약 = [044/contracts/graph-consumer-contract.md](../../044-analyzer-graph-contract-realign/contracts/graph-consumer-contract.md)** 를 따른다(단일 antlr-타입 UPPER 라벨, 단일 `id`, `HAS_MEMBER/BELONGS_TO`, `local_rule_id`, guard/branch=NEXT/BRANCH 도출, dbms 오퍼레이션=PARENT_OF 상위 루틴 복원). 본 036 문서의 나머지(용어 정규화 term_normalizer 등)는 유효.

# 내부 매퍼 계약 (외부 REST/그래프 스키마 변경 0건)

본 피처는 외부 API·그래프 스키마를 바꾸지 않는다(FR-007). 계약은 **내부 함수 시그니처** 수준이며, 기존 호출자/SSE 이벤트/매핑 산출물 형태는 그대로 유지한다.

## C1. 신규 모듈 `term_normalizer.py` (순수 함수)

```python
def normalize_query(
    query: str,
    glossary: list[GlossaryTerm],
    *,
    max_aliases_per_term: int = 5,
) -> tuple[str, bool]:
    """task query에 매칭 glossary 항목의 code_candidates를 덧붙인다.
    매칭 = 항목의 term/aliases 중 하나가 query에 부분 문자열로 등장.
    반환: (정규화된 query, applied)."""

def normalize_rule_blob(
    blob: str,
    rule: RuleDTO,
    ctx: RuleContext,
    glossary: list[GlossaryTerm],
    *,
    max_terms_per_candidate: int = 3,
) -> tuple[str, bool]:
    """rule blob에 매칭 glossary 항목의 term/aliases를 덧붙인다.
    매칭 = 항목의 code_candidates 중 하나가 rule의 source_module/source_function/title에 등장.
    반환: (정규화된 blob, applied)."""
```

- **불변식**: 원문은 보존하고 토큰을 append만 한다(replace 금지). glossary 빈 목록이면 `(원문, False)`.
- **결정성**: 같은 입력 → 같은 출력(덧붙이는 토큰 순서 고정). 측정 재현성 보장.

## C2. 수정 `agentic_retriever.run_agentic_retrieval`

```python
async def run_agentic_retrieval(
    process, tasks, actors, rules, contexts,
    *,
    glossary: list[GlossaryTerm] | None = None,   # ◄── 신규 (기본 None=정규화 미적용)
    module_top_k=20, min_module_score=..., skip_process_gate=False,
    bl_top_k=20, per_task_cap=20, cache=None, event_sink=None,
) -> RetrievalResult: ...
```

- **하위 호환**: `glossary` 기본 `None` → 기존 호출자(있다면)·테스트는 무변경으로 기존 동작.
- 내부에서 `_candidates_for_task(..., glossary=glossary)`로 전달.

## C3. 수정 `agentic_retriever._candidates_for_task`

- 임베딩 직전 `query`와 각 `_rule_blob(ctx)` 결과에 정규화 적용:
  - `HYBRID_GLOSSARY_NORMALIZE != "0"` AND `glossary` 비어있지 않을 때만.
  - 그 외에는 기존 문자열 그대로(바이트 동일).
- floor(`MIN_BL_INCLUSION`), top_k, in_scope 프리필터, 임베딩 실패 폴백 → **모두 변경 없음**.

## C4. 수정 `activity_rule_mapper.map_tasks_to_rules`

- 이미 추출한 `result.glossary`를 `run_agentic_retrieval(..., glossary=result.glossary)`로 전달하는 한 줄 배선.
- 그 외 오케스트레이션(프로세스 그룹·arbitration·저장)은 변경 없음.

## C5. 환경 변수

| 변수 | 기본 | 의미 |
|---|---|---|
| `HYBRID_GLOSSARY_NORMALIZE` | `"1"` | `"0"`이면 정규화 완전 비활성(기존 경로와 동일). A/B·회귀 안전망. |
| `HYBRID_GLOSSARY_MAX_RECOVERIES` | `"2"` | task당 정규화 회복 후보 상한(인지부하·비용 제어 노브). `0`=회복 없음, ↑=recall↑·비용↑. 공유 어휘 多 도메인은 1~2 권장(과확산 억제). |

## C7. 실경로 배선 — explore_service (중요)

production 매핑은 lazy라 `map_tasks_to_rules`가 아니라 **`explore_service.explore_task`가 `run_agentic_retrieval`을 직접 호출**한다. 따라서 실효 배선 지점은:
- `explore_service._load_glossary(session_id)` — 세션에 저장된(`save_glossary`) GlossaryTerm 로드.
- `explore_task` → `run_agentic_retrieval(..., glossary=glossary)`.
(`map_tasks_to_rules` 배선은 레거시 경로 호환용으로 유지.)

## C8. union-under-cap 후보 선택 (`_candidates_for_task`)

1. baseline 코사인 랭킹(정규화 미적용) 항상 계산 → floor 이상 후보 `base`.
2. 정규화 on이고 `len(base) < top_k`일 때만: 정규화 랭킹 계산 → `base`에 없는 회복 후보를 `min(top_k - len(base), MAX_RECOVERIES)`개 추가.
3. `base`는 **항상 전량 보존**(후보 단계 회귀 0). 검증기 입력 ≤ `top_k`(부하·비용 상한 유지).
4. 회귀가 0이 아닌 잔여분은 검증기(LLM) 비결정성에서 발생(후보 보존과 무관).

## C6. 관찰성 (FR-008)

- `SmartLogger`로 retrieval 종료 시 집계: `normalized_tasks`, `normalized_rules`, `normalize_enabled`. 측정 하니스가 회복/회귀 카운트를 산출하는 근거.
- 신규 SSE 이벤트 타입 없음(프런트 불변).

## C9. analyzer 코드그래프 읽기 계약 (consumer 측 — 2026-06-18 정합)

ingestion 의 hybrid 파이프라인은 analyzer 가 적재한 **코드분석 그래프**(별도 DB `ANALYZER_NEO4J_DATABASE`)를 읽는다. analyzer 산출 노드의 스키마는 다음으로 고정한다(analyzer spec `017-node-id-unification` + UPPER_SNAKE 라벨 통일이 진실 기준):

- **라벨 = UPPER_SNAKE**: `:FUNCTION` · `:MODULE` · `:PACKAGE` · `:TABLE` · `:COLUMN` · `:RULE` · `:EXAMPLE` · `:QUESTION` (+ DBMS 전략의 `:SELECT`/`:IF`/`:PROCEDURE` 등 antlr type). 옛 PascalCase(`:Rule`/`:Example`/`:Question`/`:Table`)는 **폐기** — Neo4j 라벨은 대소문자 구분이라 0-match 가 된다.
- **식별자 = `id` 단일**: 옛 `function_id`/`module_id`/`fqn`/`example_id`/`question_id`/`rule_hash` 전부 폐기. Cypher 의 노드 속성 읽기·MATCH 키는 `id` 로 한다(값은 보존 — Function `id`="owner.name"/"file:proc:line", Module `id`=fqn, Table `id`="db.schema.name", Column `id`="db.schema.table.col", EM 노드 `id`=합성키). 단, ingestion 내부 DTO/dict 필드명(`example_id`·`question_id`·`function_id`)과 함수 인자명은 architect 자산이라 그대로 둔다(그래프 읽기 식만 `id` 로).
- **소속/parent 는 노드속성 아님**: HAS_FUNCTION/BELONGS_TO_PACKAGE/PARENT_OF/HAS_RULE/HAS_EXAMPLE/HAS_QUESTION/AFFECTS_TABLE/READS/WRITES 엣지로 탐색.
- **★ architect 자기 hybrid 노드와의 구분(회귀금지 핵심)**: architect 가 만든 shadow 노드(`:Rule {session_id:$sid}`, `:BpmTask`/`:Event`/`:Policy`/`:UserStory`/`:BoundedContext`/`:Aggregate`/`:Command`/`:ReadModel`)는 **PascalCase + `session_id` 보유**로 그대로 유지한다. analyzer 노드는 `session_id IS NULL`. 같은 `:Rule` 문자열이 두 쿼리에서 shadow(`{session_id:$sid}`, 유지)와 analyzer(HAS_RULE 경유 / `session_id IS NULL`, → `:RULE`)로 갈리므로, analyzer 읽기만 수술적으로 UPPER+id 로 바꾼다.
- 적용 파일(consumer): `code_to_rules/rule_extractor.py` · `bpm_context_builder.py` · `mapper/{glossary_extractor,rule_context,module_retriever}.py` · `event_storming_bridge/{persistence,promote_to_es}.py` · `pipeline_verification.py`. 최종 게이트 = analyzer 재분석 후 ingestion 실행으로 0-match 해소 라이브 검증.
