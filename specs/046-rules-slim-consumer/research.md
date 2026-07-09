# Phase 0 Research: 룰 슬림 계약 소비자 정합

전수조사(코드 read + import 추적)로 확정된 결정. NEEDS CLARIFICATION 없음.

## D1. 룰 식별자 재정의 — `function_id | statement`

- **Decision**: `rule_extractor._rule_id`의 해시 입력을 `function_id | local_id | statement`에서 `function_id | statement`로 변경.
- **Rationale**: analyzer가 Rule 노드를 `rule_hash`(statement 기반)로 dedup하므로, 한 function 안에서 statement가 곧 룰 정체성이다. `local_id`(HAS_RULE.local_rule_id)는 소멸했고 NULL이 되므로 해시에 넣으면 `"None"` 문자열 오염. `(function, statement)`가 자연·안정 식별자.
- **Alternatives**: (a) local_id 자리에 빈문자열 유지 → 오염·의미없음, 기각. (b) example_id 기반 → 룰 단위 아님, 기각.
- **영향**: `seen` set dedup이 (function, statement)로 수렴 — 동일 statement 중복 룰은 하나로 합쳐짐(analyzer 의도와 일치).

## D2. dbms_rule_linearizer 대폭 축소 — 근본수정=코드 감소

- **Decision**: flow 재구성 전부(트리워크 `_TREE_QUERY`·`_linearize_one`·`_preceding_if_pid`·`_COND_LABELS`·`_BRANCH_LABELS`·P-id/guard/branch/next 계산) 삭제. 루틴 오너 복원(044 C4)만 남긴다.
- **Rationale**: 이 모듈의 목적은 두 가지였다 — ①룰이 자식 구문에 흩어진 dbms에서 **루틴 오너 복원**(C4, 여전히 필수), ②framework 모양의 **flow_id/guard/branch/next 재구성**(039로 소비처가 사라짐 → 불필요). ②를 빼면 트리워크 전체가 불필요. `_RULE_QUERY`(`(root:루틴)-[:PARENT_OF*0..]->(o)-[:HAS_RULE]->(r)`)가 이미 루틴 오너를 직접 귀속하므로, 그룹핑 후 (routine, rule)당 레코드 1개만 방출하면 됨. framework는 여전히 `is_dbms_graph=False`로 기존 `_QUERY` 경로(무회귀).
- **Alternatives**: (a) flow 필드를 빈값으로 유지하며 트리워크 남김 → 데드로직·근본위반(로직 순증), 기각. (b) framework/dbms 쿼리 통합(루틴 상승을 framework에도) → 044가 명시적으로 framework 0칸(무회귀) 유지 결정 → 스코프 밖, 기각.
- **핵심 신호**: 근본수정은 코드가 줄어든다 — 본 모듈 ~207줄 → 약 60~80줄 수준으로 축소 예상.

## D3. 데드 이벤트스토밍 결정론 클러스터 통째 삭제

- **Decision**: `event_storming_bridge/{rule_classifier,decomposer,naming,persistence}.py` 4파일 삭제.
- **Rationale(전수 확인)**: LIVE 승격 경로 = `promote_to_es.py`(LLM 기반). `promote_to_es`는 이 4파일을 **전혀 import하지 않음**(grep 확인). 4파일은 자기들끼리만 참조하는 폐쇄 섬(persistence→decomposer+naming, decomposer→rule_classifier, naming→decomposer). 나머지 참조는 문서(044 spec·CLAUDE.md·legacy-ingestion docs)와 owner_resolver의 stale 주석뿐. 존재이유 대부분이 guard/branch/flow 로직이라 039 계약변경 시 껍데기만 남음. 원칙 §4 "영향0 데드=통째 폐기".
- **Alternatives**: (a) flow 참조만 정합하고 파일 유지 → 껍데기 데드 유지, 원칙 위반, 기각(사용자 결정: 통째 삭제). (b) 그냥 방치 → removed DTO 필드 참조 잔존으로 코드 불일치, 기각.
- **안전장치**: 삭제 직전 4개 모듈명 전수 grep으로 LIVE 참조 0 재확인. promote_to_es의 label 리스트는 **독립 복제본**(주석 "keep in sync", import 아님)이라 삭제 무영향.

## D4. bpm_context_builder 흐름 요소 제거

- **Decision**: Cypher에서 `hr.local_rule_id`/`hr.flow_id`/`guard_derived`/`branch_derived` 제거, 결과 dict에서 `local_id`/`flow_id`/`guard_rule_id`/`branch_from` 키 제거, `render_hybrid_bl_block`에서 룰 태그(`local_id`)·guard_rule_id·branch_from 렌더 라인 및 안내문구 정정.
- **Rationale**: 이들은 LLM 컨텍스트에 흐름 힌트를 넣던 것. 소멸 계약이라 도출 서브쿼리도 무의미(NEXT/BRANCH 룰엣지 없음). 유지 요소(statement·AFFECTS_TABLE writes·coupled_domains·GWT)는 라이브 근거이므로 그대로.
- **룰 태그 대체**: `render_hybrid_bl_block`의 `**{tag}**`(옛 R1/R2)는 열거 인덱스(예: `- **R{i}**` 또는 소스함수명)로 대체하거나 태그 없이 statement만. 결정: 열거 순번(`i`) 사용 — 사람이 US 안 룰을 구분하는 용도로 충분, local_id 의존 제거.

## D5. 유지 계약(044 C4/C5) 불변

- **Decision**: 044 C4(오퍼레이션 단위=루틴 오너 복원)·C5(테이블 영향 하향수집)는 손대지 않음.
- **Rationale**: 이들은 dbms 구조 처리의 핵심이고 039 슬림화와 무관. dbms_rule_linearizer 축소 후에도 C4(루틴 귀속)는 유지, C5(AFFECTS_TABLE 하향수집)는 examples의 writes로 이미 룰에 붙어 운반됨.

## D6. 검증 = 실제 재인제스천 (단위테스트 아님)

- **Decision**: 심볼 전수 grep(잔재 0) + framework/dbms 하이브리드 재인제스천으로 무에러·무회귀 확인.
- **Rationale**: 원칙 §6 — 데이터 정합은 실제 파이프라인 실행 결과를 봐야 함. import/compile 통과는 필요조건일 뿐.
