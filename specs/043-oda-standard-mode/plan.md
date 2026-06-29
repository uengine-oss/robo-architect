# Implementation Plan: ODA 표준 분해 모드 (043)

**Branch**: `043-oda-standard-mode` | **Spec**: [spec.md](spec.md)
**Created**: 2026-06-28

## Summary

기존 042 분해 모드 스위치(`SIMPLIFIED` | `DETAILED_DDD`)에 세 번째 값 `ODA_STANDARD` 를
추가한다. ODA 모드 Proposal 은 intent/plan 단계를 ODA/TM Forum 표준 지식 베이스에 근거해 진행한다:
표준 정합성 매핑(UC/SID/TMF/Component) → REUSE/EXTEND/NEW 분류 → 차단형 적합성 게이트 →
SID 데이터 모델·TMF 계약·ODA 아키텍처·BDD `.feature` 산출. 결과는 표준 `strategicDiff`/
`tacticalDiff` 로 수렴해 다운스트림(impact/tasks/implement)을 무분기로 유지한다.

설계 원칙: **스킬=에이전트, 백엔드=파서/시퀀서/게이트**(Principle X), **모든 변이는 사람 확정
게이트**(Principle IV), **SSE 진행 스트림**(Principle III). 042 staged 인프라의 패턴을 그대로 재사용.

## Technical Context

- **Language**: Python 3.14 (FastAPI 백엔드), Vue 3 (frontend, Vite).
- **Storage**: Neo4j (로컬 Desktop, :7687). ODA 산출물은 `Proposal` 노드 속성(JSON 문자열)으로 영속.
- **Skill runtime**: `claude` CLI via `api/platform/skill_runner.py` (PTY/subprocess, SSE 라인 스트림).
- **ODA knowledge base**: `oda-specify`/`oda-plan` 가 참조하는 지식 루트
  (`$ODA_KNOWLEDGE_ROOT` → walk-up(`sid/`+`repo/usecase-library/`) → `/Users/uengine/oda-canvas`).
  스킬 실행 시 `run_skill_*(..., add_dirs=[<root>])` 로 주입.
- **Testing**: pytest (단위, Neo4j/LLM 비의존 — monkeypatch), Vitest/빌드(frontend).

## Constitution Check

- **I (그래프 원천)**: ODA 산출물은 `Proposal` 노드 속성으로 저장, 라이브 그래프 오염 없음. PASS.
- **III (SSE)**: oda intent/plan 진행은 기존 SSE 패턴 재사용. PASS.
- **IV (사람 확정 게이트)**: 정합성 매핑 확정·적합성 게이트·면제(waive)가 모두 명시 확정. PASS.
- **X (스킬 우선)**: 표준 매핑/분류/설계는 신규 스킬 `robo-proposal-oda`(extends oda-specify/
  oda-plan)가 담당, 백엔드는 시퀀싱·파싱·게이트만. PASS.
- 신규 Neo4j 노드/관계 **없음** — `Proposal` 속성만 추가(decompositionMode 값 확장 + odaAlignment/
  odaConformance/odaArtifacts). PASS.

## Architecture

### 신규/변경 백엔드

- `proposal_contracts.py` (변경):
  - `DecompositionMode.ODA_STANDARD = "ODA_STANDARD"`.
  - 신규 모델: `OdaAlignment`, `OdaConformanceItem`, `OdaConformanceReport`(gateResult,
    violations[], waiver), `OdaArtifacts`(dataModel/contracts/architecture/featureFiles).
  - `ProposalResponse` 에 `odaAlignment`/`odaConformance`/`odaArtifacts` (Optional) 추가 +
    `from_neo4j` 파싱(extra="allow", 과거 데이터 None 안전).
  - 요청 모델: `WaiveConformanceRequest{reason}`.
- `services/oda_conformance.py` (신규, 순수 로직 — 단위 테스트 핵심):
  - `evaluate_gate(report) -> {result, blocking, violations}` — 하드 위반(표준 필드 제거/재타이핑,
    표준 계약 파괴, 비인가 확장 메커니즘) 있으면 FAIL.
  - `all_classified(report) -> bool` — 모든 요소가 REUSE/EXTEND/NEW 분류되었는지.
  - `can_proceed(report) -> bool` — PASS 또는 WAIVED.
  - `apply_waiver(proposal_id, reason)` / `ensure_can_proceed(proposal_id)`(차단 시 예외).
- `services/oda_runner.py` (신규, 시퀀서/파서):
  - `resolve_knowledge_root()` — 지식 루트 해석(없으면 None → 게이트로 사용 불가 신호).
  - `stream_oda_intent(pid)` — `robo-proposal-oda`(phase=intent) 실행 → alignment +
    strategicDiff + 1차 conformance 저장, SSE.
  - `stream_oda_plan(pid)` — phase=plan → tacticalDiff + odaArtifacts + 최종 conformance 게이트.
  - `parse_intent_result/parse_plan_result` — 스킬 JSON → 모델(테스트 대상).
- `routes/proposals_oda.py` (신규): `GET stream/oda/intent`, `GET stream/oda/plan`,
  `POST oda/waive`, `GET oda/conformance`. `router.py` 에 include.
- 게이트 강제: `proposals_plan`·`proposals_crud`(submit)에서 ODA 모드면
  `oda_conformance.ensure_can_proceed` 호출 → FAIL+미면제면 409.

### 신규 스킬

- `skills/robo-proposals/robo-proposal-oda/SKILL.md` — `extends` 전역 `oda-specify`+`oda-plan`.
  phase(intent|plan) 입력. 지식 루트(add_dir)에서 UC/SID/TMF/Component 매핑, REUSE/EXTEND/NEW
  분류, 적합성 리포트, SID 데이터모델/TMF 계약/ODA 아키텍처/`.feature` 산출. **표준 strategicDiff/
  tacticalDiff 로 수렴** + `oda` 메타(alignment/conformance/artifacts) 동시 출력(JSON).

### 신규/변경 프런트엔드

- `ProposalCreate.vue`: 세 번째 모드 옵션 `ODA_STANDARD`. 생성 후 detail 위임(DETAILED_DDD 처럼).
- `ui/OdaStandardTrack.vue` (신규): 정합성 매핑 → 적합성 게이트(REUSE/EXTEND/NEW 매트릭스 +
  PASS/FAIL + 위반 목록 + **면제** 버튼/사유) → 산출물 미리보기. ProposalDetail 에서 mode 분기 렌더.
- `proposals.store.js`: `subscribeToOdaIntent/Plan`, `waiveConformance`, `fetchConformance`.
- `app/messages.js`: 신규 i18n 키(ko/en) — modeOda*, oda 패널 라벨. 언어정책 준수.

## Data Model (Proposal 속성 델타)

| 속성 | 타입(JSON) | 의미 |
|------|-----------|------|
| `decompositionMode` | enum | `+ ODA_STANDARD` |
| `odaAlignment` | obj | `{useCases[], sidEntities[], tmfApis[], componentBlock}` |
| `odaConformance` | obj | `{baseline, items[], violations[], gateResult, waiver}` |
| `odaArtifacts` | obj | `{dataModel, contracts[], architecture, featureFiles[]}` |

신규 노드/관계 없음. `strategicDiff`/`tacticalDiff` 는 기존 스키마 재사용(수렴 대상).

## Phasing

- **Phase 0 (research)**: oda-specify/oda-plan 스킬·지식맵 분석 — 완료(본 플랜 근거).
- **Phase 1 (design)**: 위 contracts/services/routes/skill/frontend 설계 — 본 문서.
- **Phase 2 (impl)**: tasks.md 순서대로. 게이트 로직·파서 우선(테스트 가능), 그 다음 SSE/라우트/UI.

## Risks & Mitigations

- **지식 루트 부재**: `resolve_knowledge_root` None → ODA 모드 진입 시 명시적 오류(FR-014), 묵묵
  진행 금지.
- **라이브 LLM 의존**: SSE 실행은 단위 테스트 불가 → 파서/게이트를 순수 함수로 분리해 테스트,
  라이브는 quickstart/manual 로 검증.
- **다운스트림 회귀**: 수렴이 표준 diff 형태를 깨지 않도록 기존 from_neo4j 파싱 무회귀 테스트 유지.

## Out of Scope

배포/BDD 실행(`oda-componentize`), 지식 베이스 관리, 기존 두 모드 동작 변경.
