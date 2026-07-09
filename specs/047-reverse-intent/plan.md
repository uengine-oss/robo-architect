# Implementation Plan: 코드에서 요구사항 역추출 (Reverse Intent)

**Branch**: `047-reverse-intent` | **Date**: 2026-07-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/047-reverse-intent/spec.md`

## Summary

분석된 레거시 코드 그래프(analyzer Neo4j)를 문서 없이 읽어, 오퍼레이션을 "쓰기 허브 테이블"(= Aggregate) 기준으로 **결정론적으로** 그룹핑하고, 각 그룹을 무손실 브리프로 만들어 **기존 `robo-proposal-intent` 스킬**에 태워 Strategic Diff를 생성한 뒤 테이블 기준으로 병합한다. 새 `decompositionMode = REVERSE_INTENT` 진입 모드로 붙이며, 결과는 기존 Proposal 결과와 동일 형태라 이후 Plan/구현 파이프라인을 그대로 재사용한다. 검증된 PoC(`project/reverse-intent-poc`)의 신규 로직(grouping/brief/merge/pipeline)을 architect로 이식하고, PoC의 intent/skill/neo4j 복사본은 폐기해 architect 실물을 재사용한다.

## Technical Context

**Language/Version**: Python 3.12 (backend), Vue 3 + Pinia (frontend)

**Primary Dependencies**: FastAPI, neo4j Python driver, 기존 `api/platform/skill_runner`(claude CLI 하니스), Vite/Vue. 신규 파이썬 의존 없음.

**Storage**: Neo4j 2개 논리 DB — 읽기: analyzer 그래프(`ANALYZER_NEO4J_DATABASE`, 읽기 전용). 쓰기: Proposal 노드(설계 DB, `NEO4J_DATABASE`). 둘 다 기존 `get_session(database=…)`로 접근(신규 설정 0).

**Testing**: pytest(백엔드, `api/features/proposal_lifecycle/tests/`), 실 Neo4j 대조(원칙 §6). 프론트=기존 Playwright 패턴.

**Target Platform**: Electron 데스크톱 + 로컬 FastAPI(8001) + 로컬 Neo4j(7687).

**Project Type**: web application (backend `api/` + frontend `frontend/`).

**Performance Goals**: 그룹 N개 → 브리프 N개 → intent 스킬 N콜(각 수십 초~수 분, 순차). 브리프는 토큰 예산(기본 20K)으로 분할. 진행은 SSE 실시간 표시.

**Constraints**: analyzer 그래프 **읽기 전용**(변경 0). 결정론 단계 LLM 0. intent 스킬은 로컬 구독 세션(API 키 제거). 단일 동시 실행 가정(기존 intent와 동일).

**Scale/Scope**: 레거시 그래프 오퍼레이션 수십~수백, Aggregate당 규칙 최대 수백(예산 분할로 처리). 신규 백엔드 파일 ~6, 수정 ~4 / 신규 프론트 컴포넌트 ~2, 수정 ~3.

## Constitution Check

*GATE: Phase 0 이전 통과 필수. Phase 1 이후 재확인.*

적용 헌법 = `.specify/memory/constitution.md`(ROBO analyzer 원칙; 이 레포군 공통 거버넌스로 준용).

| 원칙 | 준수 | 근거 |
|---|---|---|
| **I. Determinism-First** | ✅ | grouping·brief·merge·labels·budget split = **LLM 0**(순수 그래프/문자열 연산). LLM은 "의미가 필요한" 요구사항 도출 1곳뿐이며 **기존 intent 스킬 재사용**. regex/그래프로 되는 걸 LLM에 맡기지 않음. |
| **III. Single Source of Truth** | ✅ | Neo4j 세션=기존 `get_session`, 스킬 호출=기존 `skill_runner.run_skill_once`, 저장=기존 intent 저장 경로 재사용. `INFRA_TABLE_HINTS`·`TOKEN_BUDGET`는 인라인 매직넘버가 아니라 명명 상수(모듈 1곳). |
| **IV. No Silent Failure** | ✅ | 빈 그래프·라벨 부재·접근 실패는 조용한 빈 결과 금지 → 명시적 에러/경고(FR-013, Edge Cases). |
| **VI. Schema Restraint** | ✅ | 출력은 기존 intent 스킬의 최소 StrategicDiff 스키마 그대로(신규 강제 스키마 0). |
| II·V·VII·VIII | N/A | analyzer 내부 파이프라인(전략분기·KV캐시·submit도구·COMPONENT 응집) 규칙 — 본 기능(architect 소비측)엔 해당 없음. |

**위반 없음** → Complexity Tracking 불필요.

## Project Structure

### Documentation (this feature)

```text
specs/047-reverse-intent/
├── spec.md              # 완료
├── plan.md              # 이 파일
├── research.md          # Phase 0 (설계 결정)
├── data-model.md        # Phase 1 (엔티티)
├── quickstart.md        # Phase 1 (검증 시나리오)
├── contracts/           # Phase 1 (REST/SSE 계약)
│   └── reverse-intent-api.md
└── tasks.md             # /speckit-tasks 산출(별도)
```

### Source Code (repository root)

```text
api/features/proposal_lifecycle/
├── services/
│   ├── reverse_intent/                 # ★신규 패키지 (PoC 이식)
│   │   ├── __init__.py
│   │   ├── grouping.py                 # 테이블 앵커 그룹핑(결정론)
│   │   ├── labels.py                   # 자연어 라벨 조립 + stereotype 한국어맵 + 폴백
│   │   ├── brief.py                    # 무손실 브리프 + 토큰예산 분할
│   │   ├── merge.py                    # 테이블 dedup 병합
│   │   └── pipeline.py                 # async 오케스트레이터(그룹→브리프→intent→merge)
│   ├── intent_runner.py                # ★수정: _build_reverse_prompt 추가(기존 _save_intent_result 재사용)
│   └── reverse_source.py               # ★신규: 분석 그래프 목록 조회(FR-003)
├── routes/
│   └── proposals_reverse.py            # ★신규: create + SSE stream 라우트
├── proposal_contracts.py               # ★수정: REVERSE_INTENT enum + 요청모델
└── router.py                           # ★수정: 신규 라우터 등록

frontend/src/features/proposals/
├── ui/
│   ├── ProposalCreate.vue              # ★수정: 종류 라디오 +1 + 소스 드롭다운 스왑
│   ├── ReverseIntentTrack.vue          # ★신규: 모드 전용 트랙(소스선택→실행→진행)
│   ├── AnchorGroupList.vue             # ★신규: 그룹 카드 목록(StagePlanReview 복제)
│   └── ProposalDetail.vue              # ★수정: isReverse 분기
└── stores/proposals.store.js           # ★수정: subscribeToReverseIntent
```

**Structure Decision**: 기존 `proposal_lifecycle`(백엔드) + `features/proposals`(프론트) 구조에 **추가**한다. 결정론 로직은 `services/reverse_intent/` 하위 패키지로 응집. 결과 표시·Plan·구현 이후는 기존 컴포넌트 100% 재사용(신규 0).

## Complexity Tracking

> Constitution Check 위반 없음 — 해당 없음.
