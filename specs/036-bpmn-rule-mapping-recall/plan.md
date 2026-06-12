# Implementation Plan: BPMN 활동–레거시 BL 룰 매핑 Recall 개선 (용어 정규화)

**Branch**: `036-bpmn-rule-mapping-recall` | **Date**: 2026-06-04 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/036-bpmn-rule-mapping-recall/spec.md`

## Summary

평문 요구사항(한국어 GWT)과 레거시 코드 룰(개발자 약어)의 어휘갭으로, 의미상 매핑되어야 할 BL 룰이 후보 검색(retrieval)의 임베딩 유사도 floor(0.45)를 넘지 못해 LLM 검증기에 도달하기도 전에 탈락한다. 이미 추출되지만 **임베딩 단계에서 미사용 상태인 glossary**(`extract_glossary`)를 후보 검색의 임베딩 입력에 주입(용어 정규화)하여, 동일한 floor·후보 예산을 유지한 채 진짜 매칭의 코사인만 끌어올린다. floor를 낮추거나 후보 예산을 늘리지 않으므로 검증기 부하·사용자 화면 노출은 불변(인지부하 최소화). 효과는 env 플래그로 A/B 토글하여 골든 픽스처(자동납부 본인확인 PDF + zapamcom 분석 그래프)에서 회귀 0·회복 ≥1로 검증한다.

## Technical Context

**Language/Version**: Python 3.13 (api), 백엔드 FastAPI 모듈 내부 로직 — 신규 외부 인터페이스 없음

**Primary Dependencies**: 기존 자산 재사용 — `langchain_openai.OpenAIEmbeddings`(text-embedding-3-small), `EmbeddingCache`(`embeddings.py`), `extract_glossary`/`GlossaryTerm`(`glossary_extractor.py`), neo4j(분석 그래프). 신규 의존성 0.

**Storage**: Neo4j(진실의 원천=분석 그래프 + 매핑 산출물). 본 피처는 **신규 노드 라벨/관계 0건**(FR-007). 매핑 산출물 형태(`ActivityRuleMapping`) 불변.

**Testing**: pytest. 기존 `api/features/ingestion/hybrid/mapper/` 테스트 패턴. 신규 단위 테스트(정규화 함수) + 골든 픽스처 측정 하니스.

**Target Platform**: 로컬/데스크톱 백엔드(Electron 동봉 FastAPI). 매핑은 BPMN 탐색 SSE 경로에서 호출.

**Project Type**: web-service(백엔드 단독 변경). 프런트엔드 변경 0 — 사용자 화면 불변이 제약(US2).

**Performance Goals**: 동일 입력 매핑 전체 소요 시간 ≤ 개선 전 1.2x (SC-003). 활동당 검증 후보 수 상한 불변.

**Constraints**: floor(`MIN_BL_INCLUSION=0.45`)·`min_module_score=0.55`·`bl_top_k`·`per_task_cap` 불변. glossary 없거나 정규화 불가 시 무오류 폴백(FR-006). recall은 신호 품질로만 향상.

**Scale/Scope**: 활동당 수십~수백 룰, 문서당 다중 프로세스. 변경 표면은 `agentic_retriever`(주입) + `map_tasks_to_rules`(배선) + 측정 하니스로 국소.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

프로젝트 constitution(`.specify/memory/constitution.md`)은 미작성 템플릿이라 강제 원칙이 없음 → 형식 게이트는 통과(N/A). 대신 본 저장소의 사실상의 설계 원칙으로 자체 점검:

- **신규 그래프 스키마 0건**: ✅ FR-007 — 노드 라벨/관계 추가 없음. 매핑 산출물 형태 불변.
- **기존 자산 재배선 우선**: ✅ glossary/embeddings/validator 모두 기존 모듈 재사용. 신규 모듈 최소(정규화 헬퍼 1개 + 측정 하니스).
- **propose→confirm / HITL 불변**: ✅ 검증기(accept/reject)·사용자 화면 흐름 그대로. 본 피처는 검증기 *앞단*만 수정.
- **degrade gracefully**: ✅ glossary 부재·임베딩 실패 시 기존 동작으로 폴백(FR-006). env 플래그 off면 완전 무변경.
- **관찰성**: ✅ 정규화 적용 여부·회복/회귀 카운트를 SmartLogger로 기록(FR-008).

**판정: PASS** (위반 0건, Complexity Tracking 불필요).

## Project Structure

### Documentation (this feature)

```text
specs/036-bpmn-rule-mapping-recall/
├── plan.md              # This file
├── research.md          # Phase 0 — 주입 방향·플래그·측정 결정
├── data-model.md        # Phase 1 — 정규화 데이터 흐름(신규 영속 엔티티 0)
├── quickstart.md        # Phase 1 — 골든 픽스처 A/B 측정 절차
├── contracts/
│   └── internal-mapper-contract.md   # 내부 함수 시그니처 계약(외부 REST 변경 0)
├── checklists/requirements.md        # (이미 생성)
└── tasks.md             # /speckit-tasks 출력 (이 명령에선 미생성)
```

### Source Code (repository root)

```text
api/features/ingestion/hybrid/mapper/
├── glossary_extractor.py        # [재사용] GlossaryTerm 추출 (이미 존재, LLM 1회)
├── term_normalizer.py           # [신규] glossary로 query/rule-blob 양방향 정규화 (순수 함수)
├── agentic_retriever.py         # [수정] _candidates_for_task 임베딩 입력에 정규화 주입
│                                #        run_agentic_retrieval에 glossary 파라미터 추가
├── activity_rule_mapper.py      # [수정] map_tasks_to_rules → run_agentic_retrieval로 glossary 전달
├── embeddings.py                # [재사용] EmbeddingCache/cosine — 변경 없음
└── tests/
    ├── test_term_normalizer.py          # [신규] 정규화 단위 테스트
    └── test_glossary_recall_fixture.py  # [신규] 골든 픽스처 A/B 회귀·회복 측정

specs/036-bpmn-rule-mapping-recall/manual/   # 측정 스크립트(픽스처 적재·실행)
```

**Structure Decision**: 백엔드 단독, 변경 국소화. 신규 파일은 순수 함수 `term_normalizer.py`와 테스트 2종뿐. 핵심 수정은 `agentic_retriever._candidates_for_task`(주입)와 `activity_rule_mapper.map_tasks_to_rules`(glossary 배선) 2곳. env 플래그 `HYBRID_GLOSSARY_NORMALIZE`로 on/off(기본 on, off=완전 무변경 → 회귀 안전망 + A/B 측정 기반).

## Complexity Tracking

> Constitution 위반 없음 — 비움.
