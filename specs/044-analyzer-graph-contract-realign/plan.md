# Implementation Plan: analyzer↔architect 그래프 계약 정합

**Branch**: `044-analyzer-graph-contract-realign` (main에서 작업, architect 관례) | **Date**: 2026-06-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/044-analyzer-graph-contract-realign/spec.md`

## Summary

architect(소비자)가 analyzer(생산자)의 현행 Neo4j 그래프 계약과 어긋난 채 읽어 **에러 없이 데이터를 NULL로 유실**한다. 두 종류의 어긋남: ① **이름표 불일치**(속성명·대소문자: `local_id→local_rule_id`, `is_boundary` 미존재, `guard_rule_id/branch_from` 폐기, `file_name→file_path`, `fqn/moduleStereotype→id/stereotype`, PascalCase 통계키) — framework·dbms 공통, 단순 치환. ② **구조 불일치**(dbms 깊은 트리): 룰·테이블접근이 프로시저가 아니라 **자식 구문 노드**에 붙어, "한 함수=오너" 가정이 깨짐. 해결 = **전략 무관 단일 규칙**: 룰 오너에서 `PARENT_OF` 상위로 가장 가까운 **루틴(FUNCTION/PROCEDURE/METHOD/TRIGGER)** 을 오퍼레이션 단위로 복원(이름·요약·그룹핑), 테이블 영향은 자식에서 **하향 수집**. framework는 0칸 상승(무변화). 생산자 변경 0, 신규 라벨/관계 0.

## Technical Context

**Language/Version**: Python 3.12 (api), TypeScript + Vue 3 (frontend)
**Primary Dependencies**: FastAPI, neo4j-python-driver (api); Vue 3 + Pinia + NVL (robo-data-frontend, MF 임베드)
**Storage**: Neo4j (analyzer가 적재한 그래프를 **읽기 전용** 소비; named DB `ANALYZER_NEO4J_DATABASE`, 미설정 시 기본 DB 폴백). 본 작업은 analyzer 노드를 **쓰지 않음**.
**Testing**: pytest (`api/.../event_storming_bridge/test_*.py` 등 기존), 실그래프 재인제스천 검증(quickstart). 프론트=수동/Playwright.
**Target Platform**: Electron 데스크톱(architect) + 웹. 백엔드 api(8001) + gateway(9000) 경유.
**Project Type**: web (api + frontend), 그래프 소비자 정합 = 버그픽스/계약정렬 성격.
**Performance Goals**: N/A(읽기 쿼리 정합, 성능 회귀 없음 — PARENT_OF 상승은 노드당 소수 홉).
**Constraints**: ① 생산자(analyzer) 출력 계약 불변 ② 신규 Neo4j 라벨/관계 0 ③ 소비자 자체 세션노드(`:Rule {session_id}` 등) 미변경 ④ framework 동작 무회귀(0칸 상승) ⑤ 조용한 no-op 금지(0-match 표면화).
**Scale/Scope**: api 핵심 4파일(rule_extractor·bpm_context_builder·traceability·prd_model_data) + 하류 2(rule_classifier·decomposer) + 매퍼/오너해석 헬퍼 + module_retriever 폴백 + 프론트 2(architect 모달 통계키, robo-data-frontend 루틴 룰표시). 총 ~12 백엔드 + 2 프론트 접점.

## Constitution Check

*GATE: Phase 0 전 통과 필수, Phase 1 후 재확인.* (architect는 constitution.md 미작성 관례 → CLAUDE.md/기존 spec 게이트로 평가; 043/042와 동일. `.specify/memory/constitution.md`는 부트스트랩 시 analyzer 것이 딸려와 architect 평가엔 미사용.)

| 게이트(원칙) | 평가 | 판정 |
|---|---|---|
| **I. Graph-as-Source-of-Truth** | 그래프를 **정확히** 읽도록 정합 → 원칙 강화(현재는 NULL 유실). | **PASS(강화)** |
| **II. Event Storming Vocabulary** | 룰/예시/질문→ES 분해를 dbms에서도 올바른 단위로 복원 → 어휘 정합 개선. | **PASS** |
| **III. Streaming-First UX** | SSE/스트리밍 변경 없음. | **N/A** |
| **IV. Human-in-the-Loop** | LLM propose→confirm 변경 없음(매칭 입력 데이터 품질만 개선). | **N/A** |
| **V. Feature-Modular Architecture** | 변경이 `ingestion/hybrid`·`canvas_graph`·프론트 인제스천 모달에 국한, 모듈 경계 유지. | **PASS** |
| **VI. Provider-Agnostic LLM** | LLM 런타임 변경 없음. | **N/A** |
| **VII. Observable by Default** | 0-match 조용한 no-op 표면화(FR-005) → 관측성 강화. | **PASS(강화)** |
| **X. Skill-First Deep Agent** | 신규 스킬 불필요(계약정합 버그픽스). | **N/A** |
| **★ 신규 Neo4j 라벨/관계 0** | 읽기 정합 + 기존 PARENT_OF/HAS_RULE 활용 → **신규 0**. | **PASS(강)** |

**결과: PASS.** Complexity Tracking 불필요(신규 스키마 0, 생산자 불변). 위반 없음.

## Project Structure

### Documentation (this feature)
```text
specs/044-analyzer-graph-contract-realign/
├── plan.md              # 본 파일
├── research.md          # Phase 0: 설계 결정(오너복원·guard/branch 도출·is_boundary 폐기·이름표 매핑)
├── data-model.md        # Phase 1: 그래프 계약 데이터모델(라벨/속성/엣지 + 오너복원 규칙)
├── contracts/
│   └── graph-consumer-contract.md   # Phase 1: 권위 소비자 계약(생산자 현행 출력 ↔ 소비자 읽기 매핑)
├── quickstart.md        # Phase 1: 실그래프 재인제스천 검증 시나리오(framework·dbms)
├── checklists/requirements.md
└── tasks.md             # Phase 2: /speckit-tasks (본 명령 산출 아님)
```

### Source Code (repository root) — 변경 대상
```text
api/features/ingestion/hybrid/
├── code_to_rules/rule_extractor.py      # [핵심] local_id→local_rule_id; guard/branch=NEXT/BRANCH 도출;
│                                          #   dbms 오너복원(PARENT_OF↑ 루틴); is_boundary 정리; f.id 식별
├── mapper/owner_resolver.py             # [신규 헬퍼] 룰오너→가장가까운 루틴 해석(라벨∈ROUTINE_LABELS) — 공용
├── mapper/rule_context.py               # :Actor/ROLE 죽은매칭 제거; 오너 id기반; 테이블 자식수집
├── mapper/module_retriever.py           # :FILE 폴백 fqn/moduleStereotype→id/stereotype
├── mapper/glossary_extractor.py         # procedure_name 정리(자가치유 확인)
├── mapper/agent_validator.py            # 동상; 오너요약=루틴요약(FR-015)
├── bpm_context_builder.py               # local_id→local_rule_id; guard/branch 도출; is_boundary 정리
├── event_storming_bridge/rule_classifier.py   # [하류] is_guarded/is_branched = 도출값 구동
├── event_storming_bridge/decomposer.py        # [하류] (source_function, guard/branch, local_id) 인덱스 정합
└── event_storming_bridge/promote_to_es.py     # stale 주석 정정(동작 OK)
api/features/canvas_graph/routes/traceability.py  # local_id→local_rule_id; {is_boundary:false} 제거;
                                                   #   file_name→file_path; READS/WRITES dbms 자식수집
api/features/prd_generation/prd_model_data.py     # ahr.local_id→local_rule_id; is_boundary 정리

frontend (architect host):
└── src/.../RequirementsIngestionModal.vue   # counts.Rule/Example/Question → RULE/EXAMPLE/QUESTION
robo-data-frontend (분석기 프론트, MF):
└── src/.../FunctionCard or getSemanticReport  # 루틴 선택 시 자식 구문 룰을 루틴 단위로 집계 표시
```
**Structure Decision**: web(api+frontend). 백엔드는 **오너해석 공용 헬퍼**(`owner_resolver`)를 신설해 rule_extractor·rule_context·traceability가 동일 규칙 사용(DRY). 프론트는 robo-data-frontend 그래프 렌더(이미 정합)는 불변, 표시 갭 2곳만.

## Phase 0 / Phase 1
- Phase 0 산출: [research.md](research.md) — 모든 NEEDS CLARIFICATION 해소(없음).
- Phase 1 산출: [data-model.md](data-model.md), [contracts/graph-consumer-contract.md](contracts/graph-consumer-contract.md), [quickstart.md](quickstart.md).

## Complexity Tracking
> 신규 라벨/관계 0, 생산자 불변, 신규 스킬 0 → 비움.
