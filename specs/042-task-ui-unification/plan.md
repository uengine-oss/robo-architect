# Implementation Plan: BPM·Event Modeling 단일 Process 탭 + task=UI 일관성

**Branch**: `042-task-ui-unification` | **Date**: 2026-06-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/042-task-ui-unification/spec.md`

## Summary

BPM 뷰와 Event Modeling 뷰를 **UI를 공유 앵커로** 일관화한다. 세 갈래:
1. **US1(P1)** — 분리된 `Process`·`Event Modeling` 탭을 **단일 `Process` 탭 + BPM⇄EM 토글**로 통합(공유 UI 앵커, 접기/펼치기).
2. **US2(P1)** — ES 승격의 UI 생성([ui_wireframes.py](api/features/ingestion/workflow/phases/ui_wireframes.py))을 **"Command당 1 UI" → "task당 1 트리거 UI"** 로. task의 Command 중 사람이 조작하는 것을 **LLM 휴리스틱**으로 골라 그 Command에 UI 부착(나머지 Command는 그 화면이 일으키는 시스템 흐름, UI 없음). Command/Event의 task 기반 귀속은 불변.
3. **US3(P2)** — ReadModel은 "ReadModel당 무조건 UI" 제거. 소비만 하면 소비 task 화면에 **표시**로 부착, **검색/조회 화면**이면 자체 task-UI로 **승격**(LLM 판정).
4. **US4(P2)** — task 포함요소를 **Event Modeling 형식(가로 레인 UI→Command→Event→ReadModel)** 경량 렌더러로(spec-039 trace 데이터 재사용). `DesignTraceCanvas`는 requirements용 유지.

핵심 통찰: **task=UI(트리거)는 신규 스키마 없이 달성 가능** — Command당 N개 UI 만들던 것을 task당 1개로 *줄이는* 것이므로 기존 `:UI`/`ATTACHED_TO`만 사용. ReadModel "표시 vs 자체화면" 구분만 최소 표식이 필요할 수 있다(plan에서 결정).

## Technical Context

**Language/Version**: Python 3.13 (backend·인제스천), JavaScript / Vue 3.5 (frontend)

**Primary Dependencies**: FastAPI · Neo4j · 인제스천 워크플로우(`ui_wireframes.py`) · in-process LLM(`get_llm`) / Vue 3 + Pinia 2 + `bpmn-js`(BPM) + Vue Flow(EM 형식 렌더)

**Storage**: Neo4j 단일 그래프. 인제스천이 `:UI`/`ATTACHED_TO`/`HAS_UI` 영속. **본 피처는 UI granularity 변경 — 신규 라벨/관계 0건 지향**(불가피 시 `ATTACHED_TO`에 `role` 속성 정도).

**Testing**: pytest(UI 생성 단위·정합) + 골든 픽스처 재인제스천(spec 036 input_resource 자산) + Playwright(탭 토글·EM 형식)

**Target Platform**: 데스크톱(Electron) + 웹(api+frontend)

**Project Type**: web(api + frontend)

**Performance Goals**: UI 생성 — task당 1 LLM 판정(트리거 선택). task 수 ≈ 기존 Command 수보다 적어 LLM 호출 **감소**. 탭 토글·EM 렌더 p95 < 1s.

**Constraints**: A2A BPM 생성 불변 · Command/Event task 귀속 불변 · 신규 노드 라벨/관계 0건 지향 · 인제스천 변경이므로 **기존 세션 재인제스천 필요**(소급 아님) · 모든 LLM 변경 propose→confirm.

**Scale/Scope**: 인제스천 1개 phase 수정 + 프런트 탭 통합(ProcessPanel 래퍼) + EM 형식 경량 렌더러 + LLM 판정 프롬프트 2종(트리거/조회).

## Constitution Check

*GATE: Must pass before Phase 0. Re-check after Phase 1.* (constitution.md 템플릿 미작성 → CLAUDE.md 자체 게이트로 평가.)

| 게이트 | 평가 | 판정 |
|---|---|---|
| **I·II 신규 노드 라벨/관계 0건** | task=UI(트리거)는 기존 `:UI`/`ATTACHED_TO`로 달성(UI 수 *감소*). ReadModel 표시/자체화면 구분은 `ATTACHED_TO`에 **속성** `role`(예: `display`/`screen`) 정도로 가능 → 신규 **라벨/관계 0**, 속성만. | **PASS (조건부)** — Phase 1에서 속성 vs 무속성 확정 |
| **III 스트리밍** | UI 생성은 기존 `ProgressEvent` 스트리밍 phase. 신규 LLM 판정도 그 안. | **PASS** |
| **IV LLM 변경 propose→confirm** | 트리거/조회 판정은 **생성 단계 LLM 결정**(기존 와이어프레임 생성과 동급). 사용자는 통합 뷰에서 결과 검토·수정 → **결과를 통합 뷰에서 propose, 사용자 확정** 패턴. | **PASS (작업항목)** — Phase 0에서 propose 지점 정의 |
| **VI in-process LLM = get_llm** | 판정은 `get_llm`. | **PASS** |

**결과: PASS (조건부 — Phase 1에서 ReadModel role 속성, propose 지점 확정).** Complexity Tracking 불필요(신규 라벨/관계 0 유지 시).

## Project Structure

### Documentation (this feature)

```text
specs/042-task-ui-unification/
├── plan.md · research.md · data-model.md · quickstart.md
├── contracts/
│   ├── ingestion-task-ui-contract.md       # task당 1 트리거 UI + ReadModel 규칙
│   └── process-tab-em-view-contract.md      # 단일 탭 토글 + EM 형식 렌더러
└── checklists/requirements.md
```

### Source Code (repository root)

```text
api/features/ingestion/workflow/phases/
└── ui_wireframes.py                         # [핵심 수정] Command당 → task당 1 트리거 UI;
                                             #   ReadModel: 표시 vs 조회화면 분기(LLM 판정)
api/features/ingestion/hybrid/contracts.py   # (참조) CommandDTO.task_id — 그룹핑 키

frontend/src/features/
├── canvas/ui/
│   ├── ProcessPanel.vue                      # [신규] BPM⇄EM 토글 래퍼(BpmnPanel/EventModelingPanel 호스트)
│   ├── BpmnPanel.vue                        # (재사용) BPM 뷰
│   └── EventModelingLane.vue                 # [신규] EM 형식 경량 렌더러(가로 레인, trace 데이터)
├── eventModeling/ui/EventModelingPanel.vue   # (재사용) 전체 EM 뷰
├── requirements/ui/DesignTraceCanvas.vue     # (불변) requirements 설계-궤적
└── app/{App.vue, layout/TopBar.vue}         # [수정] 'Event Modeling' 탭 제거, 'Process' 통합
```

**Structure Decision**: web(api+frontend). 백엔드 변경은 `ui_wireframes.py` 1개 phase에 집중(+ LLM 판정 헬퍼). 프런트는 ProcessPanel 래퍼(탭 토글) + EventModelingLane(EM 형식 렌더러) 신규, 나머지 재사용. spec-039의 bpm-task trace 라우트를 EM 형식 렌더러의 데이터 소스로 재사용.

## Complexity Tracking

> 신규 라벨/관계 0 유지 시 비움. (ReadModel `role` 속성 채택해도 라벨/관계 신설 아님 → 비움 유지.)
