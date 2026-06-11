# Quickstart: Proposal Lifecycle Management

**Feature**: `039-proposal-lifecycle`
**Date**: 2026-06-05

---

## 전제 조건

- 038 브랜치 기반 환경 설정 완료 (Neo4j, Python venv, FastAPI 실행 중)
- `.env`에 LLM 설정 완료 (`LLM_PROVIDER`, `LLM_MODEL`, API key)
- Git Worktree를 위한 디스크 공간 (Proposal당 ~50MB 추가)

---

## Step 1: 기존 Change 데이터 초기화

```bash
# 038의 RequirementChange / ChangeSet 노드 전체 삭제
cd /path/to/robo-architect
python -m api.features.proposal_lifecycle.services.migration
# 확인
# "Deleted N RequirementChange nodes, M ChangeSet nodes" 출력
```

---

## Step 2: Neo4j 스키마 업데이트

```bash
# Proposal 노드 유니크 제약 및 인덱스 생성
python -m api.platform.schema_migrator --feature=039
# 또는 직접 실행:
cypher-shell -u neo4j -p <password> -f docs/cypher/schema/03_node_types.cypher
cypher-shell -u neo4j -p <password> -f docs/cypher/schema/04_relationships.cypher
```

---

## Step 3: 백엔드 라우터 등록 확인

`api/main.py`에 proposal_lifecycle 라우터가 등록되었는지 확인:

```python
# api/main.py 에 아래 줄이 있어야 함
from api.features.proposal_lifecycle.router import router as proposal_router
app.include_router(proposal_router)
```

서버 재시작:
```bash
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Swagger 확인: [http://localhost:8000/docs#/proposals](http://localhost:8000/docs)에서 `proposals` 태그 확인.

---

## Step 4: Proposal 생성 테스트 (API)

```bash
# 1. Proposal 생성
curl -X POST http://localhost:8000/api/proposals/ \
  -H "Content-Type: application/json" \
  -d '{"originalPrompt": "결제 시스템에 부분 환불 버튼 추가"}' | jq .

# 기대 응답: {"id": "PRO-001", "status": "DRAFT", ...}

# 2. 인텐트 분해 SSE 스트림 구독
curl -N http://localhost:8000/api/proposals/stream/PRO-001/intent
# strategic_diff, tactical_diff, impact_map 이벤트 순서로 수신 확인
```

---

## Step 5: 샌드박스 구현 테스트

```bash
# 1. submit
curl -X POST http://localhost:8000/api/proposals/PRO-001/submit | jq .

# 2. 구현 SSE (sandbox_creating → task_start → task_done → all_done)
curl -N -X POST http://localhost:8000/api/proposals/PRO-001/implement

# Worktree 확인
ls .sandbox/proposal/PRO-001/
git worktree list  # proposal/PRO-001 브랜치가 목록에 표시됨
```

---

## Step 6: 프런트엔드 확인

```bash
cd frontend
npm run dev
# 브라우저에서 Requirements 탭 → Proposals 메뉴 클릭
# Proposal 목록 표시 및 상태별 필터 동작 확인
```

---

## 주요 파일 위치

| 파일/디렉토리 | 설명 |
|--------------|------|
| `api/features/proposal_lifecycle/` | 백엔드 피처 루트 |
| `api/features/proposal_lifecycle/proposal_contracts.py` | Pydantic 모델 |
| `api/features/proposal_lifecycle/services/sandbox_manager.py` | Git Worktree 관리 |
| `api/features/proposal_lifecycle/services/dual_merge.py` | Dual Merge 서비스 |
| `api/features/proposal_lifecycle/services/skill_runner.py` | 스킬 실행 (038 재사용 확장) |
| `skills/robo-proposals/robo-proposal-intent/SKILL.md` | 인텐트 분해 스킬 |
| `skills/robo-proposals/robo-proposal-context/SKILL.md` | Impact Map 스킬 |
| `skills/robo-proposals/robo-proposal-implement/SKILL.md` | 샌드박스 구현 스킬 |
| `skills/robo-proposals/robo-proposal-test/SKILL.md` | 자동 테스트 스킬 |
| `frontend/src/features/proposals/` | 프런트엔드 피처 루트 |
| `docs/cypher/schema/03_node_types.cypher` | Proposal 노드 스키마 |
| `.sandbox/` | Git Worktree 루트 (.gitignore 추가 필요) |

---

## 트러블슈팅

**Git Worktree 생성 실패**: `git worktree list` 실행해 기존 dead worktree 확인 후 `git worktree prune` 실행.

**인텐트 분해 SSE 없음**: `CLAUDE_CODE_PATH` 환경변수가 정확한 claude CLI 경로를 가리키는지 확인.

**Dual Merge 실패(MERGE_FAILED)**: `git log --oneline main proposal/PRO-NNN`으로 충돌 가능한 커밋 확인 후 `/api/proposals/{id}/retry-merge` 호출.
