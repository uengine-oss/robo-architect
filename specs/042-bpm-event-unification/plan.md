# Implementation Plan: BPM ↔ Event Modeling 구조적 통합 (단일 그래프, 두 투영 뷰)

**Branch**: `042-bpm-event-unification` | **Date**: 2026-06-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/042-bpm-event-unification/spec.md`

## Summary

BPM 뷰와 Event Modeling 뷰를 **단일 Neo4j 그래프의 두 투영**으로 통합한다. 그래프는 이미 그렇게 영속돼 있다 — 하이브리드(A2A→ES) 파이프라인이 `:BpmTask`를 척추로 두고 ES 산출물을 `PROMOTED_FROM`으로 매달며, `(:UI)-[:ATTACHED_TO]->(:Command)-[:PROMOTED_FROM]->(:BpmTask)`로 UI까지 이어진다. 따라서 본 피처는 **신규 스키마 0건의 읽기 전용 투영 + UI 정리** 작업이다:

1. **US2(P1)** — BPM task 인스펙터(`HybridTaskInspector.vue`)에 "포함 요소 / 설계 궤적 보기" 버튼을 추가하고, 누르면 **모달**에 그 task의 `(:BpmTask)<-[:PROMOTED_FROM]-(…)` 서브그래프를 event-modeling 스티커로 보여준다. 백엔드는 기존 `design_trace.py`를 일반화한 **읽기 전용 trace 엔드포인트** 하나, 프런트는 기존 순수 표현 컴포넌트 `DesignTraceCanvas.vue`(이미 `trace` prop 수용)를 그대로 재사용. **캔버스 불변.**
2. **US1(P1)** — 두 뷰가 동일 `BpmTask` 집합/식별자를 공유함을 보장·검증(주로 테스트·정합).
3. **US3(P2)** — A2A task 척추 + task별 추출 정렬이 실파이프라인에서 성립함을 골든 픽스처로 회귀 검증(데이터는 이미 영속, 신규 작업 최소).
4. **US4(P2)** — "Big picture" 탭·패널·스토어·백엔드 엔드포인트 제거 + 비탭 소비자 2곳(`ExportDocumentTemplate.vue`, `TreeNode.vue`) 정리.

## Technical Context

**Language/Version**: Python 3.13 (backend), JavaScript / Vue 3.5 (frontend), Electron (desktop shell)

**Primary Dependencies**: FastAPI · Neo4j(공식 드라이버) · Pydantic / Vue 3 + Pinia 2 + `bpmn-js`(BPM 뷰어) + Vue Flow(설계-궤적 스티커)

**Storage**: Neo4j (단일 그래프, session_id 스코프) — **본 피처는 읽기 전용. 스키마 변경 0건.**

**Testing**: pytest(백엔드 라우트·쿼리) / 프런트 수동 + 골든 픽스처(spec 036의 input_resource PDF 자산 재사용)

**Target Platform**: 데스크톱(Electron) + 웹(api+frontend)

**Project Type**: web(api + frontend) + desktop

**Performance Goals**: trace 모달 응답 — 설계-궤적과 동등(p95 < 1s, bounded depth). 캔버스 렌더 영향 0.

**Constraints**: 신규 노드 라벨/관계 **0건**(헌법 I·II) · 캔버스 변경 0 · 인지 부하 최소(읽기 전용 모달) · 모든 LLM 변경 propose→confirm(본 피처는 LLM 변경 없음)

**Scale/Scope**: 백엔드 라우트 1개 추가 + 프런트 모달/버튼 1쌍 + Big picture 제거(파일 2개 삭제 + 소비자 3곳 정리). 신규 e2e 없음, 회귀 안전망 중심.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

> 프로젝트 `constitution.md`는 템플릿 미작성 상태 → CLAUDE.md에 명문화된 자체 게이트로 평가.

| 게이트 | 평가 | 판정 |
|---|---|---|
| **I·II 신규 노드 라벨/관계 0건** | trace는 기존 `:BpmTask`/`PROMOTED_FROM`/`ATTACHED_TO`/`EMITS` **읽기**만. Big picture 제거는 노드/관계 추가 아님. | **PASS** (신규 0건) |
| **III 스트리밍** | 본 피처에 신규 LLM 생성 없음 → SSE 불필요. trace는 동기 읽기(설계-궤적과 동일). | **PASS** (해당 없음) |
| **IV LLM 변경 propose→confirm** | 본 피처는 LLM 변경 0(읽기 전용 투영 + UI 제거). | **PASS** (해당 없음) |
| **VI in-process LLM = get_llm** | 신규 LLM 호출 0. | **PASS** (해당 없음) |

**결과: PASS (위반 0건, Complexity Tracking 불필요).** Phase 1 재평가에서도 동일(스키마·관계·LLM 불변).

## Project Structure

### Documentation (this feature)

```text
specs/042-bpm-event-unification/
├── plan.md              # This file
├── research.md          # Phase 0 — 5개 결정(D1~D5)
├── data-model.md        # Phase 1 — 스키마 0건, 읽기 쿼리 + DTO
├── quickstart.md        # Phase 1 — Q1~Q6 검증 시나리오
├── contracts/
│   └── bpm-task-trace-contract.md   # GET trace 엔드포인트 + Big picture 제거 계약
└── checklists/requirements.md       # (specify 단계 산출)
```

### Source Code (repository root)

```text
api/features/
├── requirements/routes/design_trace.py        # 재사용 원본 — _node/_attach_properties/expansion
├── canvas_graph/routes/
│   ├── bpmn_process.py                         # 011 BPM 라우트(참조; Command기반 process-flows는 생성원 아님)
│   └── bpm_task_trace.py                        # [신규] GET /bpm-task/{id}/design-trace (읽기 전용)
└── ingestion/hybrid/event_storming_bridge/
    └── persistence.py                          # (참조) PROMOTED_FROM 영속 — 변경 없음

frontend/src/features/
├── canvas/ui/
│   ├── HybridTaskInspector.vue                 # [수정] "포함 요소" 버튼 추가
│   ├── BpmTaskTraceModal.vue                    # [신규] 모달 래퍼(fetch → DesignTraceCanvas)
│   ├── BpmnPanel.vue                           # (참조) selectHybridTask 배선 — 변경 최소
│   └── BigPicturePanel.vue                     # [삭제]
├── canvas/bigpicture.store.js                  # [삭제]
├── requirements/ui/DesignTraceCanvas.vue       # [재사용·무수정] trace prop 수용 순수 컴포넌트
├── exportDocument/ui/ExportDocumentTemplate.vue # [수정] swimlanes 의존 제거(D5)
├── navigator/ui/TreeNode.vue                    # [수정] 'Big picture' 분기 dead-branch 삭제
└── app/{App.vue, layout/TopBar.vue}            # [수정] 탭/상태 배선 제거

api/.../routes/* (bigpicture-timeline 엔드포인트)  # [삭제 또는 비활성]
```

**Structure Decision**: web(api+frontend) 구조. 백엔드 신규 파일 1개(읽기 라우트), 프런트 신규 1개(모달 래퍼)·수정 5곳·삭제 2개. 기존 설계-궤적 자산(`design_trace.py`, `DesignTraceCanvas.vue`)을 최대 재사용해 표면적을 최소화.

## Complexity Tracking

> Constitution Check 위반 0건 → 비움.
