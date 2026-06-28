# Quickstart / Validation: 045 Rule-grained Task↔Code Mapping

본 가이드는 "후보 0 → N(>0)" 회복을 **실제 데이터로 증명**하는 검증 시나리오다(헌법 §6 실행대조). 구현 세부는 tasks.md/구현 단계.

## 전제
- Neo4j 가동(7687, neo4j/an1021402). 검증 DB = `test`(neo4j 복제본, framework 그래프).
- 매핑 검증용 세션 = `eee29044`(test에 19 BpmTask · 91 Rule 적재됨). 없으면 코드분석 풀런으로 재생성.
- architect `.venv` + `.env`(`ANALYZER_NEO4J_DATABASE=test`).

## 시나리오 A — 단위검증(직접호출, 빠름·결정적)
매퍼 모듈을 import해 변경 전/후 후보 수를 비교한다(스크래치패드 `research_exp.py`/`diag_step12.py` 패턴 재사용).

1. 변경 **전** 기준: 현 `_candidates_for_task`(컨테이너 게이트 有)를 세션 `eee29044`의 각 task에 호출 → **후보 0**(전 task) 확인 = 버그 재현.
2. 변경 **후**: 비교 단위 = Rule blob(GWT+function_summary), 모듈 하드게이트 제거 → 각 task에 호출.
3. **기대 결과**: 19/19 task에서 후보 ≥ 1(0 → N 회복). 샘플 task의 top 후보가 도메인상 타당(예: "자동납부 신청서 접수" → 자동납부/신청 관련 rule).

> 참고 실측(research.md): 게이트 제거 + blob A 기준 19/19 task 후보 생성(총 1330), blob=GWT+summary면 풀이 더 타이트(38/91).

## 시나리오 B — 라이브 풀런(전체탐색→이벤트스토밍)
1. architect api(test DB) + host + 백엔드 기동, 코드분석 모드로 PDF 2개 업로드 → BPM → 전체탐색.
2. **기대**: 전체탐색 후 그래프에 `(:BpmTask)-[:REALIZED_BY]->(:Rule)` 매핑이 다수 생성(현재 0 → 양수). 네비게이터 "전체 탐색" 버튼이 "전체 재탐색"으로 전환(매핑 존재 신호).
3. 이벤트스토밍 생성 시 코드 규칙에 근거한 산출 확인.

### 검증 쿼리(Neo4j, DB=test)
```cypher
MATCH ()-[r:REALIZED_BY]->() RETURN count(r) AS mappings;          // > 0 기대 (현재 0)
MATCH (t:BpmTask {session_id:$sid}) WHERE (t)-[:REALIZED_BY]->()
RETURN count(t) AS tasks_with_rules;                                // 다수 기대 (현재 0)
MATCH (r:Rule {session_id:$sid}) WHERE NOT (r)<-[:REALIZED_BY]-()
RETURN count(r) AS orphan_rules;                                    // 대폭 감소 기대 (현재 91)
```

## 성공 판정 (spec SC 대응)
- **SC-001**: `mappings > 0`, `tasks_with_rules` 다수, `orphan_rules` 대폭 감소.
- **SC-004**: 시나리오 A에서 task별 후보 0 → N.
- **SC-003**: 매핑이 늘어도 검증기/중재가 명백 오매핑을 계속 거름(거짓양성 도배 없음).
- **SC-002(미검증 구간)**: dbms 그래프 확보 시 동일 하니스로 거대 프로시저에서도 매핑 생성 확인. 현재 framework만 검증 가능 → 솔직히 "미검증" 표기.

## 회귀/안전
- 생산자(analyzer)·프론트·신규 Neo4j 스키마 불변(diff로 확인).
- 임베딩 호출 ≤30 청크(배치 상한 32·OOM 회피) 동작 확인.
