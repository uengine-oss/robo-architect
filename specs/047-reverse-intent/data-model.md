# Data Model: 코드에서 요구사항 역추출

신규 영속 스키마 없음 — analyzer 그래프는 읽기 전용, 결과는 기존 Proposal 노드 속성 재사용. 아래는 처리 중 사용하는 in-process 엔티티.

## AnalyzedGraphSource (분석 그래프 소스)
분석이 완료된 Neo4j DB 하나. FR-003 목록 항목.
- `db`: Neo4j 데이터베이스 이름 (예: "neo4j", "test")
- `operationCount`: 오퍼레이션 수(FUNCTION/PROCEDURE/…)
- `label`: 표시용(있으면 project/스키마명, 없으면 db명)

## Operation (오퍼레이션) — analyzer 그래프에서 읽음(읽기 전용)
- `name`, `logical_name`, `summary`, `stereotype`, `risk_level`
- `rules`: 자식 구문 rollup한 RULE.statement 목록
- `examples`: GWT(given/when/then) 목록
- `writes` / `reads`: 대상 TABLE 이름 목록

## AggregateGroup (데이터 그룹 = Aggregate 후보) — 파생, 결정론
- `table`: 앵커 테이블 이름(또는 "(로직)")
- `tableLogicalName`, `tableDescription`: 라벨용(폴백 포함)
- `kind`: `write` | `read` | `logic`
- `ops`: 이 그룹에 배정된 Operation 목록 (각 op 정확히 1그룹)
- `dominantStereotype`: 대표 성격(한국어 매핑 전 원값)
- 불변식: 전 op 커버리지 100%, op↔group 중복 0 (SC-004).

## Brief (무손실 브리프) — 파생
- `table`, `part`, `total`: 예산 분할 좌표(1-based)
- `text`: 요약 없는 규칙·GWT 렌더 텍스트
- `opCount`, `ruleCount`
- 불변식: 오퍼레이션 원자(단위 내부 규칙 분할 금지, FR-009).

## ReverseResult / StrategicDiff (기존 재사용)
- 브리프별 intent 결과 → `merge_strategic_diffs` → `StrategicDiff`(epics/features/userStories/processes, 기존 `proposal_contracts.StrategicDiff`).
- Proposal 노드 저장 속성(기존): `strategicDiff`. 신규 옵션 속성: `reverseScope`(입력 스냅샷 = {db}), `originalPrompt`(합성 문자열).
- `decompositionMode = REVERSE_INTENT` (신규 enum 값).
