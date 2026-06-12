# Implementation Plan: Proposal Lifecycle Management

**Branch**: `039-proposal-lifecycle` | **Date**: 2026-06-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/039-proposal-lifecycle/spec.md`

---

## Summary

038에서 구현된 `RequirementChange(Change)` 기반 변경 관리 시스템을 **Proposal(제안) 기반 생애주기 관리**로 진화시킨다. 핵심 변경은 세 가지다:

1. **AI 인텐트 분해 파이프라인** — 자연어 → Strategic Diff(Epic/Feature/UserStory) + Tactical Diff(Aggregate/Command/Event/VO) 분리 (`robo-proposal-intent` 스킬)
2. **Git Worktree 샌드박스** — `proposal/<PRO-NNN>` 격리 브랜치에서 Claude Code가 구현, 메인 브랜치 절대 무결
3. **Dual Merge** — PO Accept 시 코드 머지 + Neo4j 그래프 업데이트를 보상 트랜잭션으로 원자 처리

038 인프라(EFFECT 관계, SemanticDiff, SSE 스트리밍, skill_runner)를 최대 재사용하고, 신규 기능은 `api/features/proposal_lifecycle/` 피처 모듈로 격리한다.

---

## Technical Context

**Language/Version**: Python 3.11+ (백엔드), Vue 3 + Vite (프런트엔드)

**Primary Dependencies**: FastAPI, Neo4j (official driver), Vue Flow, EventSource(SSE), subprocess (git worktree)

**Storage**: Neo4j 4.4+ — `Proposal` 노드(신규), `EFFECT` 관계(038 재사용)

**Testing**: pytest (백엔드), Playwright (프런트엔드 E2E)

**Target Platform**: Linux/macOS 서버 + 웹 브라우저

**Project Type**: Full-stack 웹 애플리케이션 (Feature-modular)

**Performance Goals**: 인텐트 분해 60s 이내, Impact Map 30s 이내 SSE, 샌드박스 첫 태스크 시작 10s, Dual Merge 30s

**Constraints**: SSE 스트리밍 필수(Constitution III), Skill-First AI(Constitution X), Neo4j Single Source of Truth(Constitution I)

**Scale/Scope**: Proposal 50건 기준 목록 2s 로딩, 동시 다수 Proposal 병렬 지원(Worktree 디스크 용량 내)

---

## Constitution Check

| 원칙 | 검토 결과 |
|------|----------|
| **I. Graph-as-Source-of-Truth** | ✅ PASS — `Proposal` 노드를 Neo4j에 저장, `EFFECT` 관계 재사용. StrategicDiff/TacticalDiff/ImpactMap을 Proposal 속성(JSON)으로 저장 |
| **II. Event Storming Vocabulary** | ✅ PASS — `UserStory`, `BoundedContext`, `Aggregate`, `Command`, `Event`, `Policy` 용어 유지. PRO-NNN ID 체계 |
| **III. Streaming-First UX** | ✅ PASS — 인텐트 분해, Impact Map, 샌드박스 구현, 테스트 실행 모두 SSE 스트리밍 |
| **IV. Human-in-the-Loop** | ✅ PASS — `DRAFT` 상태에서 AI 제안 검토 후 `submit()`. Accept/Destroy는 PO 명시적 액션 |
| **V. Feature-Modular** | ✅ PASS — `api/features/proposal_lifecycle/`, `frontend/src/features/proposals/`. 038 requirement_changes 피처에서 직접 임포트 금지 |
| **VI. Provider-Agnostic LLM** | ✅ PASS — 기존 LLM 런타임 추상화 재사용 (`LLM_PROVIDER`, `LLM_MODEL` .env) |
| **VII. Observable** | ✅ PASS — 상관 ID, SmartLogger 단계 로깅 (`intent_start`, `sandbox_created`, `merge_start`) |
| **X. Skill-First** | ✅ PASS — 4개 신규 스킬 SKILL.md (`robo-proposal-intent/context/implement/test`). LangChain/LangGraph 신규 코드 없음 |

**Constitution PASS — 모든 원칙 충족**

---

## Project Structure

### Documentation (this feature)

```text
specs/039-proposal-lifecycle/
├── plan.md              # 이 파일
├── research.md          # Phase 0 ✅
├── data-model.md        # Phase 1 ✅
├── quickstart.md        # Phase 1 ✅
├── contracts/
│   └── api.md           # Phase 1 ✅
└── tasks.md             # /speckit-tasks 명령 출력 (미생성)
```

### Source Code (repository root)

```text
# Backend (Python / FastAPI)
api/features/proposal_lifecycle/
├── __init__.py
├── proposal_contracts.py          # Pydantic 모델 (ProposalStatus, StrategicDiff, 등)
├── router.py                      # FastAPI 라우터 집계
└── routes/
│   ├── proposals_crud.py          # GET/POST/LIST
│   ├── proposals_intent.py        # SSE 인텐트 분해 스트림
│   ├── proposals_sandbox.py       # implement (SSE), sandbox 관리
│   ├── proposals_testing.py       # 자동 테스트 결과
│   └── proposals_acceptance.py    # accept, destroy, retry-merge
└── services/
    ├── proposal_id_generator.py   # PRO-NNN MAX+1
    ├── intent_runner.py           # robo-proposal-intent 스킬 호출 (038 skill_runner 패턴)
    ├── impact_builder.py          # robo-proposal-context 스킬 호출 + 038 effect_analyzer 재사용
    ├── sandbox_manager.py         # git worktree add/remove/merge
    ├── implement_runner.py        # robo-proposal-implement 스킬 호출 (SSE)
    ├── test_runner.py             # robo-proposal-test 스킬 호출
    ├── dual_merge.py              # 보상 트랜잭션 Dual Merge
    └── migration.py               # CHG/CS 노드 초기화

# Skills (Constitution X)
skills/robo-proposals/
├── robo-proposal-intent/
│   └── SKILL.md                   # 자연어 → Strategic + Tactical Diff + 명확화 질문
├── robo-proposal-context/
│   └── SKILL.md                   # Impact Map 생성 (그래프 탐색)
├── robo-proposal-implement/
│   └── SKILL.md                   # extends: robo-change-tasks (샌드박스 구현)
└── robo-proposal-test/
    └── SKILL.md                   # GWT 인수 조건 → 자동 검증

# Frontend (Vue 3)
frontend/src/features/proposals/
├── proposals.store.js             # Pinia/Vuex 상태 관리
└── ui/
    ├── ProposalsPanel.vue         # Proposal 목록 + 상태 필터 (038 ChangesPanel 기반)
    ├── ProposalDetail.vue         # Proposal 상세 (Strategic/Tactical Diff, 상태 뱃지)
    ├── ProposalCreate.vue         # 자연어 입력 다이얼로그
    ├── IntentDecompositionView.vue # Strategic/Tactical Diff 편집 UI
    ├── ImpactMapView.vue          # Impact Map (conflictLevel 컬럼 포함)
    ├── SandboxProgressView.vue    # Worktree 상태 + 태스크 목록 (SSE 수신)
    ├── TestResultsView.vue        # GWT 인수 조건 결과
    └── DualMergeView.vue          # Accept/Destroy 확인 다이얼로그

# Neo4j Schema
docs/cypher/schema/
├── 03_node_types.cypher           # Proposal 노드 제약/인덱스 추가
└── 04_relationships.cypher        # Proposal→n EFFECT 관계 주석 추가

# Config
.sandbox/                          # Git Worktree 루트 (.gitignore 추가)
api/main.py                        # proposal_lifecycle 라우터 등록 추가
```

---

## Phase 0: 연구 완료 ✅

[research.md](research.md) 참조. 주요 결정:

- Git Worktree: `subprocess` + `.sandbox/proposal/<PRO-NNN>/`
- Dual Merge: 보상 트랜잭션 (git merge → Neo4j UPDATE → 실패 시 git reset)
- 자동 테스트: `robo-proposal-test` 스킬 (LLM-as-judge, GWT 기반)
- Skill-First: 4개 신규 스킬 (`robo-proposal-intent/context/implement/test`)
- ID 전략: `PRO-NNN` MAX+1 (038 `CHG-NNN` 패턴 동일)
- 038 초기화: `migration.py`로 CHG/CS 노드 수동 삭제

---

## Phase 1: 설계 완료 ✅

| 아티팩트 | 파일 |
|---------|------|
| 데이터 모델 | [data-model.md](data-model.md) |
| API 계약 | [contracts/api.md](contracts/api.md) |
| 개발 퀵스타트 | [quickstart.md](quickstart.md) |

---

## 구현 가이드라인

### 038 재사용 레이어

038 코드를 직접 임포트하는 대신, 다음 항목은 **복사+수정** 또는 **공통 플랫폼으로 승격** 방식 적용:

| 038 서비스 | 039 처리 방법 |
|-----------|-------------|
| `skill_runner.py` | 기본 PTY 실행 로직은 `api/platform/` 또는 공통 유틸로 추출, 양쪽에서 사용 |
| `effect_analyzer.load_domain_nodes()` | `api/platform/neo4j_helpers.py`로 승격 고려 |
| `StatusHistoryEntry`, `ImpactLevel`, `SemanticDiff`, `DiffOp` | `proposal_contracts.py`에서 038 모델을 직접 재정의(복사)하여 독립 유지 |
| `ChangesPanel.vue` 등 UI 컴포넌트 | `proposals/ui/`에 복사 후 Proposal 스키마에 맞게 수정 |

### Git Worktree 안전 수칙

- Worktree 경로는 반드시 `.sandbox/` 아래. 메인 프로젝트 루트에 직접 생성 금지.
- Proposal 삭제/Destroy 시 worktree remove → branch delete 순서 보장.
- 서버 재시작 시 고아 Worktree 감지 (`git worktree prune`) 스타트업 훅 추가.

### Dual Merge 구현 순서

```python
async def execute_dual_merge(proposal_id: str, actor: str) -> None:
    # 1. Git merge (compensating: can revert)
    merge_result = sandbox_manager.merge_to_main(proposal_id)
    if not merge_result.success:
        raise DualMergeFailed(step="git_merge", detail=merge_result.error)

    try:
        # 2. Neo4j transaction
        with neo4j_session.begin_transaction() as tx:
            apply_strategic_diff(tx, proposal_id)
            apply_tactical_diff(tx, proposal_id)
            update_proposal_status(tx, proposal_id, "ACCEPTED", actor)
            tx.commit()
    except Exception as e:
        # Compensate: git reset
        sandbox_manager.reset_merge(proposal_id)
        raise DualMergeFailed(step="graph_update", detail=str(e))

    # 3. Cleanup
    sandbox_manager.cleanup_worktree(proposal_id)
```

### Skill 입출력 JSON 형식

**robo-proposal-intent** 입력:
```json
{
  "proposalId": "PRO-001",
  "originalPrompt": "...",
  "domainNodes": [{"id":"...", "label":"UserStory", "title":"..."}]
}
```

**robo-proposal-intent** 출력 (명확화 필요 시):
```json
{
  "action": "clarify",
  "questions": [{"index": 0, "text": "...", "options": ["..."]}]
}
```

**robo-proposal-intent** 출력 (분해 완료 시):
```json
{
  "action": "done",
  "strategicDiff": { ... },
  "tacticalDiff": [ ... ]
}
```

---

## Complexity Tracking

038 대비 복잡도가 증가하는 항목과 정당성:

| 추가 복잡도 | 필요성 | 단순 대안이 불가한 이유 |
|------------|--------|----------------------|
| Git Worktree 관리 | 샌드박스 격리는 "실패에 대한 두려움" 문제의 유일한 해결책 | 단순 브랜치만으로는 메인 브랜치 오염 위험 존재 |
| Dual Merge 보상 트랜잭션 | 코드·스펙 동기화가 핵심 가치 | 별도 실행 시 Spec Drift 문제 재발 |
| 4개 신규 Skill SKILL.md | Constitution X 준수 + 각 단계 AI 추론이 독립적으로 테스트 가능 | 하나의 거대 스킬로 합치면 재사용·디버깅 불가 |
| StrategicDiff + TacticalDiff 이중 계층 | 038 Change는 전술적 diff만 가짐. 전략적 변경 없이는 Epic/Feature 신규 생성 불가 | 단일 Diff로 통합 시 DDD 계층 구분 손실 |
