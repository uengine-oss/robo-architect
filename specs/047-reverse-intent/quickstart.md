# Quickstart: 코드에서 요구사항 역추출 검증

## 전제
- Neo4j(7687, neo4j/an1021402) 실행, ⑥ 의미분석 완료 그래프 존재(예: DB `test`=RWIS DBMS, `neo4j`=zapamcom FW).
- architect api 기동(8001) + gateway/analyzer 등 스택(기동법=메모리 manual §3).

## 백엔드 단위 검증 (US1·US3, LLM 없이 결정론부터)
1. **소스 목록**: `GET /api/proposals/reverse/sources` → `neo4j`·`test`(오퍼레이션>0) 나오는지.
2. **그룹핑(결정론)**: 임시 스크립트로 `reverse_intent.grouping.assign_groups(analyzer_session)` 호출 → 전 op 커버리지 100%·중복 0·인프라 테이블 제외 확인(SC-004). 예상: test DB에서 "일일 용수공급량 집계" 등 업무명 그룹.
3. **라벨/폴백**: 그룹 카드 필드(제목=logical_name, 폴백=description→name) 채워지는지, stereotype 한국어 매핑 동작.
4. **브리프 예산분할**: 큰 그룹이 오퍼레이션 경계로만 분할(규칙 중간 분할 0, FR-009).

## end-to-end (US1·US2)
1. `POST /api/proposals/reverse {db:"test"}` → Proposal 생성(mode=REVERSE_INTENT).
2. `GET /api/proposals/{id}/stream/reverse` 구독 → `groups`(카드) → `brief_result` 진행 → `strategic_diff` → `done`.
3. **대조(SC-002)**: 생성 UserStory ↔ 원본 오퍼레이션 1:1(누락·환각·중복 0)을 원 그래프와 대조.
4. **하류(SC-005)**: 이어서 `POST /stream/plan` 호출 → 기존 파이프라인 무변경 통과.

## 프론트 검증 (UI)
1. 새 Proposal → 종류 라디오에 "코드에서 역추출" 보임(FR-001).
2. 선택 시 자연어 입력창 → 분석 그래프 드롭다운 스왑(FR-002/003).
3. 실행 → 그룹 카드(업무명+작업목록+성격배지) 렌더 + 진행 로그(FR-007/014).
4. 결과가 기존 Intent 탭 렌더로 표시(재사용).

## 회귀 확인
- 기존 3모드(SIMPLIFIED/DETAILED_DDD/ODA) 생성·intent·plan 정상(신규 라우트/enum 추가가 기존 경로 안 건드림).
- analyzer 그래프 노드/관계 수 실행 전후 동일(읽기 전용, FR-015).
