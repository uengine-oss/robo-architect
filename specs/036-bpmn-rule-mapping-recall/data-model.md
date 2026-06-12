# Phase 1 Data Model

**신규 영속 엔티티 0건. 신규 Neo4j 노드 라벨/관계 0건(FR-007).** 본 피처는 메모리 내 데이터 흐름만 추가한다.

## 재사용 엔티티 (변경 없음)

### GlossaryTerm (기존 — `contracts.py`)
| 필드 | 의미 | 정규화에서의 역할 |
|---|---|---|
| `term` | 한국어 대표 용어 | rule blob에 덧붙일 평문 |
| `aliases` | 한국어 동의어 | rule blob에 덧붙일 평문(확장) |
| `code_candidates` | 영문 코드 식별자 후보 | task query에 덧붙일 약어 |
| `source` | 출처(llm) | 변경 없음 |

### RuleContext / RuleDTO / BpmTaskDTO (기존)
- 변경 없음. 정규화는 이들의 텍스트를 **읽어** 임베딩 입력 문자열을 만들 때만 관여하고, 엔티티 자체나 그 영속 형태는 수정하지 않는다.

### ActivityRuleMapping (기존 — 최종 산출물)
- 형태 불변. 정규화로 recall이 올라 매핑 수가 늘 수 있으나 스키마/필드는 그대로.

## 신규 (메모리 내, 비영속)

### NormalizationResult (term_normalizer 반환, 순수 함수 산출)
함수 시그니처 수준의 값 객체. 영속화하지 않음.

| 필드 | 타입 | 의미 |
|---|---|---|
| `normalized_query` | str | task query + 매칭된 code_candidates(상한 N) 덧붙인 문자열 |
| `normalized_rule_blob` | str | rule blob + 매칭된 term/aliases 덧붙인 문자열 |
| `applied` | bool | 실제로 정규화 토큰이 덧붙었는지(관찰성/측정용) |

### 측정 산출물 (테스트 하니스, 비영속)
| 필드 | 의미 |
|---|---|
| `recovered` | off→on에서 새로 매핑된 (task, rule) 쌍 (회복) |
| `regressed` | off에서 되던 매핑이 on에서 사라진 쌍 (회귀, 0이어야 함) |
| `user_visible_delta` | 사용자 노출 항목 수 변화 (≤0이어야 함) |
| `wall_clock_ratio` | on/off 소요 시간 비 (≤1.2) |

## 상태/검증 규칙

- **정규화 적용 조건**: glossary 비어있지 않음 AND `HYBRID_GLOSSARY_NORMALIZE != "0"`. 둘 중 하나라도 아니면 `applied=false`, 원문 그대로.
- **토큰 상한**: 항목당 query에 덧붙이는 code_candidates ≤ N(기본 5), rule blob에 덧붙이는 term/aliases ≤ M(기본 3). 입력 폭주·비용 방지.
- **floor/예산 불변식**: 정규화는 `MIN_BL_INCLUSION`·`min_module_score`·`bl_top_k`·`per_task_cap`를 읽지도 바꾸지도 않는다.

## 데이터 흐름

```text
map_tasks_to_rules
  └─ extract_glossary(document, skeleton) ──► glossary: list[GlossaryTerm]   (기존, 이미 호출됨)
  └─ run_agentic_retrieval(..., glossary=glossary)            ◄── [신규 배선]
       └─ _candidates_for_task(..., glossary)                 ◄── [수정]
            ├─ query'      = normalize_query(query, glossary)       ┐ term_normalizer
            ├─ rule_blob'  = normalize_rule_blob(blob, ctx, glossary)┘  (순수 함수)
            ├─ cosine(embed(query'), embed(rule_blob'))   ── floor 0.45 (불변)
            └─ top-k → 검증기(기존) → accept/reject(기존) → 화면(불변)
```
