# Research: 코드에서 요구사항 역추출 (Reverse Intent)

모든 NEEDS CLARIFICATION은 전수조사(4개 병렬 에이전트) + 실 Neo4j 실측 + PoC 정독으로 해소됨.

## D1. 그룹핑 알고리즘 = 테이블 쓰기-허브 앵커

- **Decision**: 각 오퍼레이션(FUNCTION/PROCEDURE/METHOD/TRIGGER)을 "쓰기 테이블 중 전역 빈도 최다(허브)" 기준으로 정확히 한 그룹에 배정. 쓰기 없으면 읽기 허브, 그것도 없으면 "(로직)" 그룹. PoC `grouping.py` 이식.
- **Rationale**: 데이터 소유 = DDD Aggregate. 결정론(LLM 0, 헌법 I). PoC 실측으로 응집·무손실 검증(auth_hst 7op→US7).
- **Alternatives rejected**: 호출그래프(CALLS) 클러스터링 = framework 헤어볼/dbms 먼지로 실측 실패. LLM 경계결정 = 비결정론·비용(헌법 I 위반).

## D2. 요구사항 도출 = 기존 intent 스킬 재사용

- **Decision**: `robo-proposal-intent` 스킬을 기존 `skill_runner.run_skill_once`로 호출. PoC의 `intent_runner`/`skill_runner`/`neo4j_client` 복사본은 **폐기**. 신규는 역방향 프롬프트 빌더 `_build_reverse_prompt`(브리프→요구사항 도출 지시)뿐이며 architect `intent_runner.py`에 추가. 저장은 기존 `_save_intent_result` 의미 재사용.
- **Rationale**: DRY·단일 진실(헌법 III). PoC 복사본은 드리프트 추적용이었고 통합 시 불필요.
- **Alternatives rejected**: PoC 복사본 유지 = 중복·드리프트.

## D3. Neo4j 접근 = 기존 이중 세션(신규 설정 0)

- **Decision**: analyzer 그래프 읽기 = `get_session(database=ANALYZER_NEO4J_DATABASE)`(기존 배관, ingestion이 이미 사용). Proposal 쓰기 = 기존 `get_session()`(설계 DB). **무인자 세션으로 analyzer 그래프를 읽지 않는다**(설계 DB엔 FUNCTION/TABLE 없음 → 빈 결과, 헌법 IV 위반 위험).
- **Rationale**: architect에 이미 존재하는 패턴. 신규 env/config 불필요(검증됨).

## D4. 분석 그래프 목록 조회(FR-003) = SHOW DATABASES + 프로브

- **Decision**: `system` DB에 `SHOW DATABASES` → system 제외 각 DB에서 `MATCH (n) WHERE n:FUNCTION OR n:PROCEDURE RETURN count>0` 프로브 → 오퍼레이션 있는 DB만 목록화. 실패/권한없음 시 `[ANALYZER_NEO4J_DATABASE]` 단일 폴백.
- **Rationale**: 실측 확인됨(neo4j·skill·test 3개 자동 식별). 신규 저장소 불필요·결정론.
- **Alternatives rejected**: 분석 이력 레지스트리 신설 = 과설계. 사용자 수기 입력 = 식별자 암기 부담(FR-003 위반).

## D5. 자연어 라벨 = ⑥ 산출 필드 조합 + 폴백

- **Decision**: 그룹 제목 = `TABLE.logical_name`, 부가 = 대표 op `stereotype`(한국어 매핑표) + 그룹 종류(write=핵심데이터/read=조회/logic=로직) + op 수, 본문 = 각 `op.logical_name`(제목 접두어 정리). 폴백 체인: `logical_name` → `description`(DDL) → 기술명. `analyzed_description`은 부제로 미사용(사용자 결정).
- **Rationale**: 실측으로 필드 존재 확인(test DB 완비). 추가 분석 0. stereotype 실측값: FW=Command/Query/Validator/Adapter…, DBMS=BatchProcessor/Aggregator/EventTrigger… + (없음)→"기타".
- **전제**: ⑥ 의미분석 완료 그래프. 미완료 시 폴백(FR-013) + 가독성 저하 경고.

## D6. 다중 브리프 SSE = 순차 N콜 + 누적 병합

- **Decision**: 신규 SSE 라우트가 그룹→브리프 전개 후, 브리프마다 순차로 intent 스킬 호출하며 진행 이벤트(`group`/`log_line`/`brief_result`) emit. 전 브리프 완료 후 `merge_strategic_diffs`로 병합 → `p.strategicDiff` 저장 → `strategic_diff`+`done` emit. 기존 intent의 단일콜 가정을 다중 반복으로 확장(별도 라우트라 기존 intent 무변경).
- **Rationale**: 기존 `stream_intent`는 단일콜 전제 → 재사용 대신 병렬 라우트 신설이 안전(회귀 0).

## D7. 인프라 테이블 필터 = 기본 ON

- **Decision**: `INFRA_TABLE_HINTS`(DEBUG/LOG/TMP/TEMP/_BAK/AUDIT 등) 포함 테이블은 앵커 후보 제외(그 op는 차순위 앵커로). 실측 노이즈(DEBUGMSG_TB·RDIDEBUG_TB2) 제거.
- **Rationale**: 그룹 카드 가독성·정확도. PoC에 이미 있음(켜기).
