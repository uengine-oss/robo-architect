# Implementation Plan: 룰 슬림 계약 소비자 정합 (rules-slim-consumer)

**Branch**: `046-rules-slim-consumer` | **Date**: 2026-07-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/046-rules-slim-consumer/spec.md`

## Summary

analyzer spec 039로 그래프 계약에서 소멸한 요소(HAS_RULE.flow_id/local_rule_id·룰 NEXT/BRANCH 엣지·EXAMPLE.description)에 대한 architect 하이브리드 코드-인제스천 소비자의 의존을 걷어낸다. 흐름(flow)을 읽거나 재구성하던 로직을 제거하고, 그 흐름 로직이 존재이유였던 **미배선 데드 이벤트스토밍 결정론 클러스터**를 통째 삭제한다. 044 계약 C2(부분)/C3를 supersede하고 C4(루틴 오너)/C5(테이블 영향)는 불변으로 유지한다. 근본수정 원칙상 이 작업은 **코드가 순증가 아니라 순감소**한다(트리워크 삭제·데드 4파일 삭제·식별자 단순화).

## Technical Context

**Language/Version**: Python 3.11 (api), Vue 3 (frontend)

**Primary Dependencies**: FastAPI, Neo4j (python driver), Pydantic v2, LangChain(promote_to_es LLM 경로 — 본 작업 무변경)

**Storage**: Neo4j — 생산자(analyzer) 그래프 read(`ANALYZER_NEO4J_DATABASE`) + 소비자 세션노드(`:Rule/:Command/... {session_id}`)

**Testing**: pytest (api). 데이터정합은 실제 하이브리드 인제스천 재실행으로 검증(단위테스트 아님).

**Target Platform**: Linux/Windows server (architect api), Electron desktop host(frontend)

**Project Type**: web (backend api + frontend) — 영향은 backend 국소 + frontend 1지점

**Performance Goals**: N/A (동작·정합 보존이 목표, 성능 목표 없음)

**Constraints**: 계약 소멸을 graceful하게 흡수(크래시·silent-fail 0). framework 경로 무회귀.

**Scale/Scope**: 소비자 정합 — backend 4파일 수정 + 4파일 삭제, frontend 1파일, 주석 1파일, 계약 문서 1파일.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

architect `.specify/memory/constitution.md`(analyzer 헌법 I~VIII 기재)의 관련 원칙 대조:

- **I. Determinism-First**: PASS — LLM 추가 0. rule_extractor/dbms_rule_linearizer는 여전히 결정론(그래프 read + 파이썬). 오히려 흐름 재구성(휴리스틱) 삭제로 결정론 순도↑.
- **II. Zero-Branch Strategy**: PASS/개선 — framework/dbms 분기는 `is_dbms_graph` 감지 1지점 유지(신규 분기 0). dbms_rule_linearizer 축소로 분기 본문 대폭 감소.
- **III. Single Source of Truth**: PASS — rel 타입 문자열은 계약(Cypher) 내 최소. 신규 매직넘버 0.
- **IV. No Silent Failure**: PASS(강화) — FR-009. 계약 소멸을 조용히 빈결과로 삼키지 않고 정상 흡수. rule_extractor의 기존 WARN 로그 유지.
- **V. KV-Cache-Friendly Prompts**: N/A — 본 작업은 프롬프트 system 본문 무변경(promote_to_es 무관, bpm_context_builder는 user 컨텍스트 데이터만 정리).
- **VI. Schema Restraint**: PASS/부합 — DTO/그래프 스키마 축소(흐름 필드 제거)는 절제 원칙에 부합.
- **VII. Submit-Tool Wrap**: N/A — 에이전트 출력 무변경.
- **VIII. Cohesion Over Convention**: PASS — 데드 클러스터 삭제는 응집/청소에 부합.

**Cross-Service Contract 영향**: 생산자(analyzer)는 이미 슬림 계약으로 변경 완료(039). 본 작업은 **소비자 단측 정합** — 생산자에 역방향 요구 0. 044 계약 문서만 supersede 갱신.

**게이트 결과**: 위반 0 → Phase 0 진행 가능. Complexity Tracking 불필요.

## Project Structure

### Documentation (this feature)

```text
specs/046-rules-slim-consumer/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (DTO 전후 스키마)
├── quickstart.md        # Phase 1 output (검증 시나리오)
├── contracts/           # Phase 1 output (슬림 그래프 소비 계약 = 044 supersede델타)
├── checklists/
│   └── requirements.md  # spec 품질 체크리스트 (완료)
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root: d:\work\robo\project\robo-architect)

```text
api/features/ingestion/hybrid/
├── contracts.py                          # [수정] RuleDTO 6필드 + ExampleDTO.description 제거
├── bpm_context_builder.py                # [수정] Cypher/dict/render flow 제거
├── code_to_rules/
│   ├── rule_extractor.py                 # [수정] _QUERY·_rule_id·DTO생성 정합
│   └── dbms_rule_linearizer.py           # [대폭축소] flow 트리워크 삭제, 루틴오너만
└── event_storming_bridge/
    ├── rule_classifier.py                # [삭제] 데드
    ├── decomposer.py                     # [삭제] 데드
    ├── naming.py                         # [삭제] 데드
    └── persistence.py                    # [삭제] 데드
                                          # (promote_to_es.py = LIVE, 무변경)
api/features/ingestion/hybrid/mapper/
└── owner_resolver.py                     # [주석수정] stale local_rule_id 주석 정정

frontend/src/features/requirements/ui/
└── UserStoryDetail.vue                   # [수정] rule.local_id 배지 제거

specs/044-analyzer-graph-contract-realign/contracts/
└── graph-consumer-contract.md            # [수정] C2/C3 → 046 supersede 표기
```

**Structure Decision**: 기존 하이브리드 인제스천 레이아웃을 그대로 사용. 신규 디렉토리/모듈 0. 변경은 계약 소비 지점(code_to_rules, bpm_context_builder, contracts)과 데드 삭제(event_storming_bridge 4파일)로 국한.

## Complexity Tracking

> Constitution Check 위반 없음 — 해당 없음.
