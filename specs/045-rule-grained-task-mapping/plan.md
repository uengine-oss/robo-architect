# Implementation Plan: 코드분석 Task↔Rule 매핑 단위 정합 (045)

**Branch**: `045-rule-grained-task-mapping` | **Date**: 2026-06-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/045-rule-grained-task-mapping/spec.md`

## Summary

코드분석 하이브리드 인제스천의 Phase 3 매칭이 업무 Task ↔ 코드 Rule을 **0건** 잇는 문제를, 비교 단위를 **코드 컨테이너(파일/모듈) 요약 → 개별 Rule(+컨텍스트)** 로 전환해 해결한다. research.md 실측으로 확정된 접근:
1. **모듈 컨테이너 게이트를 하드 차단으로 쓰지 않는다**(제거). 모듈 점수는 약신호/로그만. — 게이트 제거 시 0 → 19/19 task 후보 회복.
2. **Rule 임베딩 묶음 = GWT(title+given/when/then) + 소속 루틴 summary**. (테이블 미채택; 코드의 OpenAI 기준 lean-blob 가정은 현 SGLang 모델에서 뒤집힘 → research에 기록.)
3. **하드 비용 상한 불필요**(91개 3.4s). 단 임베딩 호출은 **≤30 청크**(엔드포인트 배치 상한 32·OOM). soft-cap은 안전망만.

임베딩은 거친 recall 프리필터(+top-K)로 쓰고, 정밀도는 **기존 LLM 검증기/중재**가 담당(불변). 전략(framework/dbms) 분기 0 — 둘 다 "Rule 직접 비교", dbms는 기존 owner_resolver 루틴 복원만 재사용.

## Technical Context

**Language/Version**: Python 3.12 (robo-architect api, `.venv`)

**Primary Dependencies**: FastAPI, neo4j-python-driver 6.x, langchain_openai(OpenAIEmbeddings → 사내 SGLang `OPENAI_BASE_URL`), 기존 하이브리드 매퍼 모듈

**Storage**: Neo4j (소비자 read = `ANALYZER_NEO4J_DATABASE`; 매핑 write = `NEO4J_DATABASE`). 본 작업 검증 DB = `test`(neo4j 복제본).

**Testing**: 직접호출 단위 하니스(스크래치패드 `research_exp.py`/`diag_step12.py` 패턴) — 매퍼 모듈 import → test 세션(eee29044)에 돌려 "후보 0 → N" 회복 입증. (레포 pytest 있으면 회귀.)

**Target Platform**: Windows 데스크톱 백엔드(api), 사내 SGLang LLM/임베딩.

**Project Type**: web-service 백엔드 내부 로직(단일 서비스 변경).

**Performance Goals**: 세션 rule 수십~백 개 전수 임베딩 ≤ 수 초(실측 91개 3.4s). 임베딩 호출 ≤30 청크.

**Constraints**: 임베딩 엔드포인트 배치 상한 32·대배치 GPU OOM → 청킹 필수. 생산자(analyzer) 그래프·신규 Neo4j 라벨/관계·프론트·BPM/ES 생성 로직 불변.

**Scale/Scope**: 변경 파일 = `api/features/ingestion/hybrid/mapper/{agentic_retriever.py, module_retriever.py, 필요시 rule_context.py, embeddings.py(청킹)}`. 매핑 저장/검증기/중재/SSE 인터페이스 재사용.

## Constitution Check

*GATE: Phase 0 전 통과, Phase 1 후 재확인. (헌법 = `.specify/memory/constitution.md`)*

- **I. Determinism-First** ✓ — LLM은 의미 판단(검증기, 기존)만. 매칭 회수는 결정론적 임베딩 코사인. 본 변경은 결정론 영역(어느 단위를 비교) 정리.
- **II. Zero-Branch Strategy (분기 0)** ✓ — "Rule 직접 비교"는 framework/dbms 공통. 전략 `if` 추가 0. dbms 루틴 복원은 기존 owner_resolver 재사용.
- **III. Single Source of Truth** ✓ — blob 구성/floor/청크 크기를 매직넘버 산발 대신 한 곳 상수로. lean-blob의 모델 의존 가정은 research에 명시(드리프트 방지).
- **IV. No Silent Failure** ✓ (개선) — 기존엔 모듈 0개 → 조용히 후보 0 → 매핑 0(silent empty). 게이트 제거 + (계약 C7) 매핑 0 시 경고 로그로 silent no-op 제거.
- **V. KV-Cache** — 해당 없음(프롬프트 system 본문 변경 없음).
- **VI. Schema Restraint / VII. Submit-Tool** — 해당 없음(LLM 출력 스키마/검증기 인터페이스 불변).
- **VIII. Cohesion** — 해당 없음.

**Cross-Service Contracts**: 생산자(analyzer) Neo4j 출력 스키마 **변경 0**. 본 작업은 소비자(architect) 매칭 로직만 정합 → **내부 변경(다운스트림 영향 없음)**. 044 권위 계약 `contracts/graph-consumer-contract.md` C4(매칭 단위=루틴, 모듈≠단위) 정신을 한 단계 더(Rule 단위) 따른다.

**신규 Neo4j 라벨/관계 = 0. 신규 스키마 = 0.** → GATE PASS.

## Project Structure

### Documentation (this feature)

```text
specs/045-rule-grained-task-mapping/
├── plan.md              # 이 파일
├── research.md          # Phase 0 — 3 HOW 실측 결정
├── spec.md              # 요구·왜
├── data-model.md        # Phase 1 — 엔티티(신규 스키마 0)
├── quickstart.md        # Phase 1 — 검증 실행 가이드(후보 0→N)
├── contracts/
│   └── matching-contract.md   # Phase 1 — Task↔Rule 매칭 내부 계약(소비자측)
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks 산출(미생성)
```

### Source Code (repository root: robo-architect)

```text
api/features/ingestion/hybrid/mapper/
├── agentic_retriever.py     # ★ run_agentic_retrieval: 모듈 게이트 하드차단 제거 / _candidates_for_task: 컨테이너 프리필터 제거 + blob=GWT+summary
├── module_retriever.py      # 모듈 검색을 (선택) 약신호/로그로 격하 — 하드 게이트 호출부 정리
├── rule_context.py          # (필요시) blob에 쓰는 컨텍스트(summary) 노출 확인 — 이미 function_summary 제공
└── embeddings.py            # embed_many ≤30 청킹(배치 상한 32 대응)

api/features/ingestion/hybrid/
└── explore_service.py       # 매핑 저장/캐시히트 흐름 — 인터페이스 재사용(무변경 목표)
```

**Structure Decision**: 단일 서비스(robo-architect api) 내부 변경. 신규 디렉토리/모듈 없음. 변경은 하이브리드 매퍼 4파일에 국한, 저장·검증기·중재·SSE는 재사용.

## Complexity Tracking

> Constitution Check 위반 없음 — 비움.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (없음) | — | — |
