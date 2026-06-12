# Phase 0 Research: Proposal Impact Artifact Preview

**Feature**: `040-proposal-impact-preview` | **Date**: 2026-06-11

본 기능은 신규 외부 기술을 도입하지 않으므로 연구는 **아키텍처 결정**에 집중한다. 핵심 미지수(임시 데이터를 기존 뷰어에 어떻게 공급하는가)는 스펙 Clarification 에서 사용자가 확정했고, 여기서 근거와 기각 대안을 정리한다.

---

## D1. 임시 노드 표현 방식 — 오버레이 투영 채택

**Decision**: 복제 Neo4j 도, 라이브 임시쓰기도 아닌 **오버레이 투영(Overlay Projection)**. 미리보기 시점에 백엔드가 (라이브 그래프 슬라이스 READ) + (Proposal 직렬화 diff 오버레이)를 메모리에서 합성해, 기존 라이브 read 엔드포인트와 동일한 응답 형태로 반환.

**Rationale**:
- 임시 노드는 이미 `Proposal.strategicDiff/tacticalDiff`(039)에 직렬화 JSON 으로 존재 → 추가 영속 상태 0.
- 라이브 그래프에 한 번도 쓰지 않음 → Constitution I(단일 진실 원천) 위반 0, US2(오염 0) 자동 충족.
- 제안 폐기 시 잔존물 0 (투영은 요청 시 합성, 영속 아님).
- 응답 형태를 라이브와 동일하게 미러링하면 4개 뷰어 스토어의 파싱·렌더·포커스 로직을 무수정 재사용.

**Alternatives considered**:
- **복제 Neo4j 인스턴스/DB (제안별)** — 기각. 동기화·정리(GC)·인프라 운용 부담, 라이브와의 2중 진실원천 위험, 제안 수만큼 DB 라이프사이클 관리. 뷰어 호환성은 최고지만 비용 대비 과함.
- **라이브 그래프에 임시 태그 노드 쓰고 렌더 후 삭제** — 기각. 동시성/서버 크래시 시 임시 노드가 라이브에 잔존(오염), Constitution I 직접 위반 위험. 뷰어 수정은 최소지만 안전성 불합격.
- **프런트에서만 diff 를 즉석 머지** — 부분 기각. 라이브 슬라이스 fetch + diff 적용을 클라이언트가 하면 각 뷰어 스토어에 도메인 머지 로직이 흩어짐(중복·드리프트). 합성은 백엔드 1곳(`preview_projection.py`)에 격리하는 편이 응집도·테스트성에서 우월.

---

## D2. 응답 형태 미러링 vs 신규 통합 스키마

**Decision**: preview 엔드포인트는 **대응하는 라이브 read 엔드포인트의 응답 스키마를 그대로** 반환(필드 동일 + per-node `source` 태그만 추가).

**Rationale**: 뷰어 스토어(`aggregateViewer`/`canvas`/`bpmn`/`eventModeling`)는 라이브 엔드포인트 응답을 이미 파싱한다. 동일 형태를 주면 fetch base URL 분기 1줄 외 수정이 거의 없다. `source`(live | live+modified | temporary | conflict)는 옵셔널 필드로 추가하므로 기존 파서 비파괴.

**Alternatives**: 제안 전용 통합 미리보기 스키마 → 기각(뷰어별 어댑터를 다시 작성해야 함, 재사용 이점 상실).

**미러 대상 라이브 엔드포인트**(Explore 확인):
| 뷰어 | 라이브 엔드포인트 | preview 미러 |
|------|------------------|--------------|
| Data | `GET /api/contexts/{bcId}/full-tree`, `GET /api/graph/expand-with-bc/{aggId}` | `GET /api/proposals/{pid}/preview/contexts/{bcId}/full-tree` 등 |
| Design | `GET /api/graph/expand-with-bc/{nodeId}` | preview 미러 |
| Process | `GET /api/graph/bpmn/process-flows`, `/process-flow/{startCmdId}` | preview 미러 |
| Processes | `GET /api/graph/event-modeling` | preview 미러 |

---

## D3. 프런트 주입 방식 — generic preview-source + 앱 레벨 이벤트

**Decision**: 각 뷰어 스토어에 **도메인 중립** `setPreviewSource({baseUrl, proposalId, label, readOnly})` / `clearPreviewSource()` 를 추가하고 fetch base 를 분기. proposals 피처는 스토어를 직접 임포트하지 않고 `robo:open-preview` 커스텀 이벤트를 emit, `App.vue`(앱 셸)가 수신해 탭 전환 + `setPreviewSource` + 노드 포커스를 오케스트레이션.

**Rationale**: Constitution V — viewer(canvas/eventModeling 피처)가 proposals 를 임포트하면 sibling-feature 직접 의존(금지). 기존 코드에 이미 `robo:switch-tab`, `claude-terminal-open`(openClaudeCode) 같은 앱 레벨 이벤트 오케스트레이션 패턴이 있어 이를 그대로 답습.

**Alternatives**:
- 뷰어 스토어가 proposals.store 직접 호출 → 기각(Principle V 위반).
- 전역 fetch 인터셉터로 모든 `/api/graph` 를 가로채 preview 로 리라이트 → 기각(암묵적·광범위, 라이브와 미리보기가 동시에 열릴 때 충돌, 디버깅 난해).

---

## D4. 임시 노드 ID 부여

**Decision**: `changeType=CREATE` & `nodeId=null` 인 항목에 `PREVIEW:<proposalId>:<index>` 결정론적 임시 ID 부여(백엔드 `overlay_apply`). 제안 내 신규 노드 상호 참조는 제목 매칭으로 동일 temp ID 에 연결.

**Rationale**: 뷰어 포커스/엣지는 노드 ID 키 기반. 신규 노드는 라이브 ID 가 없어 안정적 임시 키가 필요. 결정론적(인덱스 기반)이라 같은 제안의 반복 미리보기에서 ID 안정.

---

## D5. 타입별 미리보기 깊이

**Decision**: 인텐트 분해 산출 범위에 따라 차등.
- **Data(Aggregate)** — tacticalDiff 가 신규/변경 Aggregate·VO·Command·Event 를 풍부히 생산 → 풀 오버레이 미리보기(US1 핵심).
- **Process(BPMN)** — strategicDiff.processes 변경을 라이브 process-flow 위에 오버레이; 불가 시 라이브 포커스.
- **Design(UI)·Processes(Journey)** — 인텐트가 신규 생성하는 경우가 드묾 → 대개 임팩트가 참조하는 라이브 노드를 **읽기 전용 포커스**. tacticalDiff 에 UI/이벤트모델 항목이 있으면 오버레이.

**Rationale**: 사용자가 "전 타입, 가용한 대로"를 선택. 동일 "열기" UX 로 두 경로(오버레이 / 라이브 포커스)를 투명하게 처리. 표현 불가 항목은 비활성 + 사유(FR-010).

---

## D6. 라이브 무변경 보장(테스트 전략)

**Decision**: preview 백엔드 경로는 Neo4j **read 트랜잭션 전용**. CI 게이트로 preview 모듈 내 `CREATE|MERGE|SET|DELETE` Cypher 키워드 금지 검사 + 미리보기 전/후 그래프 카운트·체크섬 동일 검증 pytest.

**Rationale**: US2(P1, 안전)와 Constitution I 를 코드가 아닌 테스트로 강제. 회귀 방지.

---

## 미해결 사항

없음. 모든 Technical Context 항목 확정(NEEDS CLARIFICATION 0).
