# Quickstart / 검증 가이드: 046 룰 슬림 계약 소비자 정합

정합 완료 후 이 순서로 검증한다(원칙 §6 = 실제 실행 결과 대조).

## 사전 조건

- Neo4j 실행(bolt://127.0.0.1:7687, neo4j/an1021402), `ANALYZER_NEO4J_DATABASE` 세팅.
- architect api venv, robo-architect `.env`([[manual]] §5 함정⑥).
- analyzer는 슬림 계약으로 산출된 상태(spec 039 생산자 완료).

## 1. 정적 검증 — 심볼 전수 grep (SC-001, SC-002)

제거 심볼이 소비자 실코드에 0건인지:

```
grep -rn "flow_id\|guard_rule_id\|branch_from\|next_rule_local_ids\|branch_rule_local_ids" api/features/ingestion/hybrid/
# → contracts.py 및 code_to_rules/bpm_context_builder 잔재 0 (BPMN flow id 등 동명 제외 확인)
grep -rn "local_id" api/features/ingestion/hybrid/code_to_rules/ api/features/ingestion/hybrid/bpm_context_builder.py
# → 룰 local_id 잔재 0
grep -rn "ExampleDTO(" -A8 api/features/ingestion/hybrid/  # description= 인자 없음
```

삭제된 데드 클러스터를 import하는 곳 0건:

```
grep -rn "rule_classifier\|decomposer\|from .*naming import\|event_storming_bridge.persistence" api/ frontend/src/
# → 문서 외 코드 참조 0
```

## 2. import/부팅 검증 (SC-002)

```
python -c "from api.features.ingestion.hybrid.code_to_rules.rule_extractor import extract_rules_from_analyzer_graph"
python -c "from api.features.ingestion.hybrid.event_storming_bridge.promote_to_es import *"  # 삭제 후 import 오류 0
python -m compileall api/features/ingestion/hybrid/  # exit 0
```

## 3. framework 재인제스천 무회귀 (SC-003)

- framework 데이터(예: zapamcom)로 하이브리드 코드-인제스천 실행.
- 기대: Rule 추출·저장·ES 승격이 오류 로그 0으로 완료. Rule/Example/AFFECTS_TABLE/QUESTION 개수·GWT 정합 전 대비 무회귀(LLM 런변동 제외). 각 룰 id가 (function, statement) 기준 안정.

## 4. dbms 재인제스천 루틴 귀속 (SC-004)

- dbms 데이터(예: RWIS)로 인제스천.
- 기대: 룰이 자식 구문이 아니라 상위 루틴(PROCEDURE/FUNCTION)에 귀속되어 추출(source_function=루틴명). AFFECTS_TABLE writes 정상 운반. 오류 0.

## 5. 계약·프론트 (SC-005, FR-008)

- `specs/044-.../contracts/graph-consumer-contract.md` C2/C3에 046 supersede 표기 확인.
- UserStory 상세 화면에 `local_id` 순번 배지 없음, 나머지 룰 표시 정상.

## 통과 기준

SC-001~005 전부 충족 + 오류 로그 0 + framework/dbms 무회귀.
