# Research: Proposal Lifecycle Management

**Feature**: `039-proposal-lifecycle`
**Branch**: `039-proposal-lifecycle`
**Date**: 2026-06-05

---

## Research Question 1: Git Worktree 관리를 Python 백엔드에서 어떻게 처리할 것인가?

**Decision**: `subprocess`로 `git worktree add/remove/prune` 명령을 직접 호출. 전용 `SandboxManager` 서비스로 캡슐화.

**Rationale**:
- Python의 `subprocess.run()` + `GitPython` 라이브러리 모두 가능하나, 기존 코드베이스(038)에 GitPython 의존성이 없으므로 stdlib `subprocess`로 통일.
- 워크트리 경로는 프로젝트 루트 하위 `.sandbox/proposal/<PRO-NNN>/` 사용. 메인 리포지토리 루트가 고정이므로 상대 경로 계산이 단순하다.
- 브랜치 명: `proposal/PRO-NNN`. 슬래시 접두어로 Proposals 전용 네임스페이스 확보.

**Alternatives considered**:
- GitPython: 직관적이나 설치 필요. stdlib으로 충분하여 기각.
- dulwich: 순수 Python git 구현이나 worktree 지원이 미흡. 기각.

**Implementation sketch**:
```python
# create
subprocess.run(["git", "worktree", "add", "-b", f"proposal/{proposal_id}", worktree_path, "HEAD"], ...)
# destroy
subprocess.run(["git", "worktree", "remove", "--force", worktree_path], ...)
subprocess.run(["git", "branch", "-D", f"proposal/{proposal_id}"], ...)
# merge (accept)
subprocess.run(["git", "-C", PROJECT_ROOT, "merge", "--no-ff", f"proposal/{proposal_id}", "-m", f"Accept {proposal_id}"], ...)
```

---

## Research Question 2: Dual Merge 원자성 — 코드 머지와 그래프 DB 업데이트를 어떻게 원자적으로 처리할 것인가?

**Decision**: **보상 트랜잭션(Compensating Transaction)** 패턴. 코드 머지 → 그래프 DB 업데이트 순서로 진행, 그래프 DB 실패 시 `git reset --merge`로 롤백.

**Rationale**:
- RDBMS 분산 트랜잭션(2PC)은 Neo4j 표준 드라이버에서 직접 지원하지 않으므로 실용적이지 않음.
- 코드 머지는 되돌릴 수 있는 작업(git reset)이나 그래프 DB 업데이트는 Neo4j 트랜잭션으로 묶어 원자 보장.
- 실패 시 `MERGE_FAILED` 상태 + 재시도 엔드포인트 제공으로 운영 유연성 확보.

**Step-by-step**:
```
1. git merge proposal/<PRO-NNN>
   → fail: status=MERGE_FAILED, stop
2. Neo4j BEGIN TRANSACTION
   a. Apply StrategicDiff (UserStory/Feature/Epic updates)
   b. Apply TacticalDiff (Aggregate/Command/Event/VO SemanticDiff ops)
   c. Update Proposal status to ACCEPTED
   COMMIT
   → fail: git reset --merge, status=MERGE_FAILED, stop
3. Cleanup worktree (git worktree remove + branch delete)
4. Return success
```

**Alternatives considered**:
- 그래프 DB 먼저: 그래프 DB 롤백 어렵지 않으나 코드 머지 실패 시 DB만 업데이트된 상태가 됨. 기각.
- 별도 saga 오케스트레이터: 복잡성 과도. v1은 보상 트랜잭션으로 충분. 기각.

---

## Research Question 3: GWT 인수 조건 기반 자동 테스트를 어떻게 실행할 것인가?

**Decision**: Neo4j에서 `UserStory.acceptanceCriteria` 필드의 GWT 텍스트를 파싱하여 **Gherkin-style 시나리오 명세**를 생성하고, `claude -p` 스킬 호출로 샌드박스 환경에서 검증 수행. 결과는 PASS/FAIL/SKIPPED 구조화 JSON.

**Rationale**:
- 그래프 DB에 이미 GWT 형태의 인수 조건이 `UserStory.acceptanceCriteria` 배열로 저장됨(038 인프라).
- 전용 테스트 프레임워크(pytest 시나리오 등)를 새로 작성하는 것이 아니라, `robo-proposal-test` 스킬이 LLM으로 각 시나리오를 해석하고 샌드박스 코드에서 시나리오 실현 가능성을 판단.
- v1에서는 "AI 검증(LLM-as-judge)" 방식. v2에서 실제 pytest 자동 생성으로 진화 가능.

**Alternatives considered**:
- pytest 자동 생성: GWT → Python 코드 변환 복잡도 높음. v1 범위 초과. 기각.
- 사람이 수동 테스트: Proposal 패러다임의 핵심 가치를 훼손. 기각.

---

## Research Question 4: 인텐트 분해 AI 파이프라인을 Constitution X Skill-First 패턴으로 어떻게 구현할 것인가?

**Decision**: `skills/robo-proposals/` 아래 3개 스킬 파일 신규 생성. 038의 `robo-change-specify`/`robo-change-tasks` extends 패턴 참조.

**Skills 목록**:
| 스킬 | 역할 | Extends |
|------|------|---------|
| `robo-proposal-intent` | 자연어 → Strategic Diff + Tactical Diff 분해 + 명확화 질문 | (new) |
| `robo-proposal-context` | 그래프 DB Impact Map 생성 | (new, calls MCP graph tools) |
| `robo-proposal-implement` | 샌드박스 Worktree에서 구현 태스크 실행 | `extends: robo-change-tasks` |
| `robo-proposal-test` | GWT 인수 조건 기반 자동 검증 | (new) |

**Backend 호출 패턴** (038 `skill_runner.py` 재사용):
```python
async def run_intent_skill(proposal_id: str, original_prompt: str, domain_nodes: list[dict]) -> dict | None:
    skill_path = _PROJECT_ROOT / "skills" / "robo-proposals" / "robo-proposal-intent" / "SKILL.md"
    input_data = {"proposalId": proposal_id, "originalPrompt": original_prompt, "domainNodes": domain_nodes}
    # PTY 방식으로 claude 호출, stdout 파싱, Neo4j 저장
```

---

## Research Question 5: PRO-NNN ID 생성 전략

**Decision**: 038의 `CHG-NNN` MAX+1 패턴과 동일하게 `PRO-NNN` 형식 사용. `Proposal` 노드에서 MAX 조회.

**Implementation**:
```python
def next_proposal_id() -> str:
    query = """
    MATCH (n:Proposal)
    WHERE n.id STARTS WITH 'PRO-'
    RETURN max(toInteger(substring(n.id, 4))) AS maxNum
    """
    # MAX+1:3자리 패딩
    return f"PRO-{max_num + 1:03d}"
```

---

## Research Question 6: 038 RequirementChange 노드와의 관계 — 마이그레이션 없이 초기화

**Decision**: spec FR-015 지시대로, 기존 `RequirementChange(CHG-NNN)` 노드와 관련 관계를 모두 삭제하는 마이그레이션 스크립트(`migration.py`)를 새로 작성. 앱 시작 시 자동 실행하지 않고 수동 실행 또는 startup 옵션으로 제공.

```cypher
MATCH (n:RequirementChange) DETACH DELETE n;
MATCH (n:ChangeSet) DETACH DELETE n;
```

---

## Research Question 7: 038 프런트엔드 컴포넌트 재사용 가능성

**Decision**: 기존 `frontend/src/features/requirements/ui/` 하위 `ChangeDetail.vue`, `ChangesPanel.vue`, `ChangeImpactView.vue`, `DesignChangesView.vue` 등을 새 `frontend/src/features/proposals/ui/` 디렉토리로 **복사+수정** (직접 임포트 금지, Constitution V 준수).

**Reuse mapping**:
| 038 컴포넌트 | 039 신규 컴포넌트 | 변경 범위 |
|-------------|-----------------|---------|
| `ChangesPanel.vue` | `ProposalsPanel.vue` | PRO-NNN ID, 상태 표시, 필터 |
| `ChangeDetail.vue` | `ProposalDetail.vue` | Strategic/Tactical Diff 섹션 추가 |
| `ChangeImpactView.vue` | `ImpactMapView.vue` | conflictLevel 컬럼 추가 |
| `ChangeTasksView.vue` | `SandboxProgressView.vue` | 워크트리 상태, 태스크 목록 |
| (new) | `TestResultsView.vue` | GWT 인수 조건 결과 |
| (new) | `DualMergeView.vue` | Accept/Destroy 확인 UI |
| (new) | `IntentDecompositionView.vue` | Strategic/Tactical Diff 편집 |

---

## Research Question 8: 샌드박스 Worktree 경로 전략

**Decision**: 프로젝트 루트 하위 `.sandbox/` 디렉토리에 저장. `.gitignore`에 추가.

```
PROJECT_ROOT/.sandbox/proposal/PRO-001/   ← git worktree
PROJECT_ROOT/.sandbox/proposal/PRO-002/
```

**디스크 정리**: Destroy 시 `git worktree remove --force` + `git branch -D proposal/PRO-NNN`. MERGE_FAILED도 동일하게 정리(재시도 시 재생성).
