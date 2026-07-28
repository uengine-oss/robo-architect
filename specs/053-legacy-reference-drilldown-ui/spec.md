# Feature Specification: 레거시 검색·검토 근거 추적과 UI

**Feature Branch**: `main`  
**Created**: 2026-07-17  
**Status**: In progress  
**Extends**: spec 052 2차분 T101~T104.

## 목적

Architect가 Analyzer의 `cluster_retrieve` 목록에서 무엇을 찾았는지와 `node_detail`로 무엇을 실제 검토했는지를 구분해 Proposal 전 단계에 기록하고, 목록·상세·설계 연결선에서 과장 없이 보여준다.

## 사용자 시나리오

### US1 — 모든 설계 단계의 레거시 참조를 잃지 않는다 (P1)

INTENT, PLAN, 단계형 DDD에서 검색 또는 상세 조회가 일어나면 Proposal에 stage별로 append된다. 검색하지 않은 단계에는 빈 기록을 만들지 않는다.

### US2 — 검색 후보와 실제 검토 대상을 구분한다 (P1)

팝오버와 접이식 상세에서 searched 노드와 inspected 노드를 구분한다. inspected 노드는 원문 파일·시작/끝 줄과 도구 호출 사실을 보여준다.

### US3 — 목록에서 근거 존재를 즉시 안다 (P2)

Proposal 목록 각 행은 중복 제거한 참조 수를 `⛓N`으로 표시한다. 0이면 배지를 렌더링하지 않는다.

### US4 — 생성 결과와 실제 관련된 근거만 연결한다 (P2)

설계 요소 텍스트에 레거시 함수명·테이블명·컬럼명이 실제 포함될 때만 실선을 그린다. 검색만 되었으나 텍스트 근거가 없는 노드는 흐리게 표시하고 선을 그리지 않는다.

## 기능 요구사항

- **FR-001** skill runner는 `cluster_retrieve`와 `node_detail`을 서로 다른 marker kind로 방출하고 tool_use_id로 요청/응답을 짝짓는다.
- **FR-002** collector는 stage, retrieve query, searched nodes, inspected detail calls, timestamp, database를 저장한다.
- **FR-003** INTENT, PLAN, staged DDD가 동일 collector helper를 사용한다. 복사된 파싱 루프를 만들지 않는다.
- **FR-004** 상세 조회 실패도 node_id와 안전한 오류 코드를 기록하며 성공으로 세지 않는다.
- **FR-005** Proposal API 모델은 구형 052 기록을 읽을 수 있지만 새 쓰기는 단일 v2 형상만 사용한다.
- **FR-006** proposal intent skill은 목록→선택→필요한 ID 상세조회 순서를 명시하며 첫 응답에서 원문을 기대하지 않는다.
- **FR-007** 목록 배지는 모든 stage의 searched/inspected ID 합집합 수를 사용한다.
- **FR-008** 연결선은 normalized element text와 node name/physical_name/column names의 실제 포함으로만 결정한다. summary 유사도나 검색 점수만으로 선을 만들지 않는다.
- **FR-009** 접이식 상세는 기본 닫힘이며 키보드/스크린리더로 열 수 있고, 파일·line range·검토 상태·오류를 표시한다.
- **FR-010** 기존 header chip, proposal diff, 목록 선택·삭제·스크롤은 회귀하지 않는다.
- **FR-011** UI 검증 중 선택 기능의 정상 미연결 상태를 HTTP 오류로 표현해 console/network 오류를 만들지 않는다. 실제 실패 상태는 그대로 오류로 남긴다.
- **FR-012** INTENT 스킬은 `legacy-reference.md`를 최종 출력 전 반드시 직접 읽고 목록→상세 완료 게이트를 실행해야 한다. INTENT의 참조 목록·절차·출력 예시는 Strategic Diff 전용 계약과 모순되어서는 안 되며 `tacticalDiff`를 산출하지 않는다.

## 완료 기준

- 실제 MCP 목록 1회와 상세 여러 회가 INTENT/PLAN/DDD 각각 올바른 stage에 저장된다.
- 저장된 ID·이름·라인은 Analyzer/Neo4j 원본과 건별 일치한다.
- Playwright에서 목록 배지, 팝오버, 접이식 상세, 실선/무선/흐림 세 상태와 console/network 오류 0을 확인한다.
- 실제 INTENT 스트림에서 `legacy-reference.md` Read, `cluster_retrieve` 요청·결과, 후보가 있을 때 `node_detail` 요청·결과가 관찰되고 최종 JSON에는 `tacticalDiff`가 없다.
