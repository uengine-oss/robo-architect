# Phase 0 Research: 용어 정규화 주입 설계

모든 결정은 spec의 제약(인지부하 최소화·비용 ≤1.2x·floor/예산 불변·스키마 0건)을 만족하도록 선택.

## D1. 어디에 주입하는가 — 후보 검색 임베딩 단계

- **Decision**: `agentic_retriever._candidates_for_task`의 임베딩 입력 2종(task `query`, rule `_rule_blob`)에 정규화를 적용한다. floor 비교 직전 단계.
- **Rationale**: 어휘갭 탈락이 발생하는 정확한 지점이 이 임베딩 코사인(floor 0.45)이다([agentic_retriever.py:181-195](../../api/features/ingestion/hybrid/mapper/agentic_retriever.py#L181)). 여기서 진짜 매칭의 코사인을 끌어올리면 floor를 낮추지 않고 recall이 오른다. 검증기·표시 단계는 손대지 않으므로 사용자 화면 불변(US2).
- **Alternatives rejected**:
  - floor 인하 → 비용·노이즈 폭증, 인지부하 증가(명시적 범위 외).
  - lexical/structural OR 결합(`lexical_matcher`/`structural_booster` 재활성화) → 후속 스펙(범위 외).
  - 검증기 프롬프트에 glossary 주입 → 후보가 검증기에 도달조차 못 하는 게 문제라 recall 미해결.

## D2. 정규화 방향 — 양방향 canonicalization

- **Decision**: 매칭되는 glossary 항목에 대해 **(a) task query에는 `code_candidates`(영문 약어)를 덧붙이고, (b) rule blob에는 `term`+`aliases`(한국어 평문)를 덧붙인다.** 양쪽 텍스트를 공통 어휘로 수렴.
- **Rationale**: `GlossaryTerm`이 이미 `term`(한국어)·`aliases`(한국어 동의어)·`code_candidates`(영문 식별자) 양방향을 보유([glossary_extractor.py:45-48](../../api/features/ingestion/hybrid/mapper/glossary_extractor.py#L45)). 한쪽만 정규화하면 반대편 어휘는 여전히 갭. 양방향이면 평문 task와 약어 rule이 서로의 어휘를 공유해 코사인이 자연히 상승.
- **매칭 방식**: glossary 항목의 `term`/`aliases` 중 하나라도 task 텍스트에 **부분 문자열로 등장**하면 그 항목의 code_candidates를 query에 추가(`expand_task_tokens`의 매칭 규칙 재사용, [glossary_extractor.py:186-201](../../api/features/ingestion/hybrid/mapper/glossary_extractor.py#L186)). rule blob 쪽은 `code_candidates`가 rule의 source_module/function/title에 등장하면 그 항목의 term/aliases를 추가.
- **Alternatives rejected**: 단방향(query만 또는 rule만) → 반대 어휘 갭 잔존. 토큰 치환(replace) → 원문 의미 손상 위험, 덧붙이기(append)가 안전.

## D3. 과도 정규화 안전장치 — 덧붙이기 + 검증기 흡수

- **Decision**: 원문을 보존하고 정규화 토큰을 **덧붙이기**만 한다. 잘못된 glossary로 무관 룰의 코사인이 올라 후보에 진입해도 **기존 LLM 검증기가 reject**하므로 사용자 화면에 새지 않는다(SC-005).
- **Rationale**: spec의 "검증기=완충재" 원칙. 덧붙이기는 floor를 넘기는 효과만 주고 최종 판정은 검증기 몫.
- **추가 가드**: 항목당 추가 토큰 수 상한(예: code_candidates 상위 N개)으로 query 폭주 방지 → 임베딩 입력 길이·비용 안정(≤1.2x).

## D4. 비용 ≤1.2x — 신규 LLM 호출 0

- **Decision**: glossary는 **이미** `map_tasks_to_rules`에서 매핑 1회당 1번 추출됨(`result.glossary = await extract_glossary(...)`). 본 피처는 그 결과를 retrieval로 전달만 하므로 **신규 LLM 호출 0**. 정규화는 순수 문자열 연산.
- **Rationale**: 추가 비용은 (1) 정규화로 바뀐 임베딩 입력의 재임베딩뿐. 임베딩 호출 횟수(task당 1, rule당 1)는 불변, 입력 길이만 소폭 증가. 검증기 호출 횟수는 후보 예산(`bl_top_k`/`per_task_cap`) 불변이라 그대로. → ≤1.2x 여유.
- **현행 누락 확인**: `run_agentic_retrieval`는 glossary를 파라미터로 받지 않음. `map_tasks_to_rules`가 glossary를 추출해 `result.glossary`에만 저장하고 retrieval엔 미전달 → **glossary가 임베딩에 한 번도 안 쓰이는 상태**. 이 배선만 이어도 핵심 효과 발생.

## D5. 토글·측정 — env 플래그 + 골든 픽스처 A/B

- **Decision**: `HYBRID_GLOSSARY_NORMALIZE`(기본 `"1"`) env 플래그로 정규화 on/off. off면 기존 코드 경로와 바이트 동일(회귀 안전망). 측정은 동일 입력을 off/on 2회 실행해 매핑 diff 산출.
- **Rationale**: SC-001(회귀 0 + 회복 ≥1)·SC-004(폴백 무오류)를 같은 플래그로 검증. 기존 임베딩 floor/예산 env(`HYBRID_EMBED_*`)와 동일한 토글 컨벤션.
- **골든 픽스처**: `/Users/seongwon/Desktop/robo/input_resource` 자동납부 본인확인 PDF 2종(평문) + `zapamcom10060.c`/`zapamcom10140.c`가 분석되어 적재된 neo4j 분석 그래프(개발자 약어). 평문("본인확인")↔코드("zapamcom") 갭 실재 → 회귀/회복 측정 적합.
- **Alternatives rejected**: 코드 상수 토글(런타임 변경 불가), 별도 설정 노드(스키마 0건 위배).

## D6. 폴백 정책

- **Decision**: glossary 빈 목록/추출 실패/플래그 off → 정규화 미적용 원문으로 진행. 임베딩 실패는 기존 "전부 통과" 폴백([agentic_retriever.py:184-188](../../api/features/ingestion/hybrid/mapper/agentic_retriever.py#L184)) 유지.
- **Rationale**: FR-006/SC-004. 어떤 실패 경로에서도 매핑이 끊기지 않고 기존 결과 보존.

## 미해결(NEEDS CLARIFICATION) — 없음

spec clarify에서 recall 기준·비용 상한·평가셋이 모두 확정됨. Phase 1 진행 가능.
