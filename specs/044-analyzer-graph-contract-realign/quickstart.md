# Quickstart 검증: analyzer↔architect 그래프 계약 정합

목표: 정합 후 **framework·dbms 두 전략 그래프 모두에서** 소비가 NULL 없이 동작함을 실그래프로 확인(FR-010, 단위테스트만으로 단정 금지).

## 전제(풀스택 — [[manual]] §3 레시피)
Neo4j(7687) → analyzer(5502) · catalog(5503) · antlr(8081) · gateway(9000) → architect api(8001, Electron 자체 spawn 또는 `uv run uvicorn api.main:app --port 8001`).

## 시나리오 A — dbms 전략 (핵심: 깊은 구조)
1. dbms 소스(프로시저/패키지) 분석: `cd robo-data-analyzer && python cli_scripts/analyze_data_dir.py <name> --strategy dbms` → 그래프 적재.
2. 그래프에 깊은 구조 존재 확인(Neo4j):
   ```cypher
   MATCH (p:PROCEDURE)-[:PARENT_OF*1..]->(s)-[:HAS_RULE]->(:RULE)
   RETURN p.name, labels(s)[0] AS owner_label, count(*) LIMIT 5
   ```
   → 룰 오너(owner_label)가 `SELECT/IF/...` 구문임을 확인(프로시저 아님).
3. architect 인제스천(문서 업로드→hybrid) 실행.
4. **검증**:
   - **그룹**: 추출된 룰들의 `source_function`이 **빈 문자열 0건**, 같은 프로시저 룰이 **그 프로시저 1개로 묶임**(자식별 분산 0). (SC-009)
   - **흐름**: 룰 `local_id` NULL 0건, NEXT/BRANCH 흐름 배열 비어있음(실재 흐름 있는데) 0건. (SC-001)
   - **테이블**: 한 프로시저 오퍼레이션의 READS/WRITES = 자식 DML의 합집합과 일치(누락 0). (SC-009)
   - **요약**: 매칭에 쓰인 요약이 구문요약이 아니라 **프로시저 요약**. (FR-015)
   - **통계 UI**: 인제스천 모달 Rule/Example/Question 카운트가 실개수로 표시(0 아님). (SC-010)
   - **노드상세 UI**: 프로시저 노드 선택 시 하위 룰이 그 루틴 아래 모여 표시. (SC-010)

## 시나리오 B — framework 전략 (회귀 게이트)
1. framework 소스(자바 등) 분석: `--strategy framework`.
2. architect 인제스천 실행.
3. **검증(무회귀)**: source_function=함수명, 룰묶음=함수단위, 흐름/테이블 = 정합 전과 **동일 결과**(0칸 상승·자식 없음으로 동작 불변). (SC-007)

## 공통 검증
- 소비자 그래프 접점 전수에 PascalCase/옛속성 참조 0건(생산자 노드 한정, 자체 세션노드 제외). (SC-002/SC-008)
- 소비자→생산자 엣지 MERGE 매칭 0건 시 경고 로그 출력(조용한 no-op 0). (SC-004)
- 죽은패턴(`:Actor/:ROLE`, `:HAS_BUSINESS_LOGIC`) 잔존 0. (SC-003)

## 자가검증 메모(내가 직접 — [[principles]]§6)
풀스택 기동 + dbms/framework 각 1회 분석·인제스천 후, 위 Cypher·NDJSON 스트림·인제스천 산출(RuleDTO/source_function/local_id)을 로그·Neo4j 직접쿼리로 대조. 프론트는 Playwright 헤드리스로 모달 카운트·프로시저 노드상세 캡처 후 Read 확인.
