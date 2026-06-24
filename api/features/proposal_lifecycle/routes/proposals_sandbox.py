from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from starlette.requests import Request

from api.features.proposal_lifecycle.services.implement_runner import prepare_implementation
from api.features.proposal_lifecycle.proposal_contracts import append_status_history
from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


class ImplementRequest(BaseModel):
    # Claude Code 탭의 대상 프로젝트 경로 (localStorage['claude_code_workspace_root']).
    # Worktree 원천이며 robo-architect 자신이 아니다 (FR-006).
    projectRoot: str
    # 대상이 아직 Git 저장소가 아닐 때, 사용자가 다이얼로그로 동의하면 true 로
    # 재요청한다. 그러면 백엔드가 git init + 초기 커밋 후 Worktree를 생성한다. (FR-006)
    initGit: bool = False


class ImplementResponse(BaseModel):
    proposalId: str
    status: str
    worktreePath: str
    branch: str
    command: str


@router.post("/{proposal_id}/implement", response_model=ImplementResponse)
async def implement_proposal(proposal_id: str, body: ImplementRequest, request: Request):
    """
    대상 프로젝트(projectRoot)에 Git Worktree를 만들고 구현 컨텍스트를 준비한 뒤,
    Code 탭의 Claude Code 셀이 실행할 구현 지시(command)를 반환한다 (FR-007).
    실제 구현은 프런트엔드가 openClaudeCode(worktreePath, command)로 셀에 위임한다.
    """
    with get_session() as session:
        result = session.run(
            "MATCH (p:Proposal {id: $id}) RETURN p.status AS status, p.projectRoot AS projectRoot",
            id=proposal_id,
        )
        record = result.single()

    if not record:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")
    # 재구현 허용: SUBMITTED 첫 구현 + IMPLEMENTING/TESTING/PENDING_ACCEPTANCE/MERGE_FAILED
    # 재구현. ACCEPTED(이미 머지)·DESTROYED(폐기)·DRAFT(미제출)는 불가.
    REIMPLEMENTABLE = {"SUBMITTED", "IMPLEMENTING", "TESTING", "PENDING_ACCEPTANCE", "MERGE_FAILED"}
    if record["status"] not in REIMPLEMENTABLE:
        raise HTTPException(
            status_code=400,
            detail=f"이 상태에서는 (재)구현할 수 없습니다 (current: {record['status']})",
        )

    # 042 — Plan 게이트는 구현 단계로 이동: 확정된 비-stale ImplementationPlan 이 있어야 구현 가능.
    # (제출은 Intent 완료로 끝나고, Plan 은 SUBMITTED 상태에서 수립·확정한다.)
    if record["status"] == "SUBMITTED":
        from api.features.proposal_lifecycle.routes.proposals_crud import _get_proposal_row
        from api.features.proposal_lifecycle.proposal_contracts import ProposalResponse
        _gate = ProposalResponse.from_neo4j(_get_proposal_row(proposal_id), [])
        if _gate.implementationPlan is None:
            raise HTTPException(status_code=400, detail={
                "reason": "plan_required",
                "message": "구현 전에 Plan(구현계획)을 확정해야 합니다."})
        if _gate.planStale:
            raise HTTPException(status_code=400, detail={
                "reason": "plan_stale",
                "message": "Constitution/Strategic Diff 변경으로 plan 이 오래되었습니다. Plan 을 다시 실행/확정하세요."})

    if not body.projectRoot or not body.projectRoot.strip():
        raise HTTPException(
            status_code=400,
            detail="projectRoot가 필요합니다. Claude Code 탭에서 대상 프로젝트 경로를 먼저 설정하세요.",
        )

    # 비-SUBMITTED 상태에서의 (재)구현: 기존 워크트리 정리 후 SUBMITTED로 리셋
    if record["status"] != "SUBMITTED":
        from api.features.proposal_lifecycle.services.sandbox_manager import SandboxManager
        sm = SandboxManager()
        prev_root = record.get("projectRoot") or body.projectRoot
        try:
            sm.remove_worktree(proposal_id, prev_root)
        except Exception:
            pass
        with get_session() as session:
            session.run(
                "MATCH (p:Proposal {id: $id}) SET p.status = 'SUBMITTED', p.sandboxStatus = null, "
                "p.sandboxBranch = null, p.sandboxWorktreePath = null, p.testResults = null",
                id=proposal_id,
            )
        SmartLogger.log("INFO", f"{record['status']} → SUBMITTED reset for re-implement: {proposal_id}",
                        category="proposal_lifecycle.implement.reimplement_reset",
                        params={"proposalId": proposal_id, "fromStatus": record["status"]})

    from api.features.proposal_lifecycle.services.sandbox_manager import NotAGitRepoError
    try:
        prepared = prepare_implementation(
            proposal_id, body.projectRoot.strip(), allow_init=body.initGit,
        )
    except NotAGitRepoError as e:
        # 대상이 Git 저장소가 아님 → 상태를 그대로 두고(SUBMITTED) 프런트엔드에
        # 'git init 후 계속' 다이얼로그를 띄우도록 409 + 머신 판독 코드를 반환한다.
        # 사용자가 동의하면 initGit=true 로 재요청한다. (FR-006)
        SmartLogger.log("INFO", f"Not a git repo, prompting init: {proposal_id}",
                        category="proposal_lifecycle.implement.not_git_repo",
                        params={"proposalId": proposal_id, "projectRoot": e.root})
        raise HTTPException(
            status_code=409,
            detail={
                "code": "NOT_A_GIT_REPO",
                "message": (
                    f"대상 프로젝트가 아직 Git 저장소가 아닙니다: {e.root}. "
                    "Git 저장소를 생성(git init)하고 계속할까요?"
                ),
                "projectRoot": e.root,
            },
        )
    except Exception as e:
        # Worktree 생성 실패 → DRAFT 복귀 (FR-006 edge: 디스크 부족 등)
        _transition_status(proposal_id, "SUBMITTED", "DRAFT", "system", f"Worktree 생성 실패: {e}")
        raise HTTPException(status_code=400, detail=f"Worktree 준비 실패: {e}")

    SmartLogger.log("INFO", f"Implement prepared (interactive shell): {proposal_id}",
                    category="proposal_lifecycle.implement.start",
                    params={"proposalId": proposal_id})

    return ImplementResponse(
        proposalId=proposal_id,
        status="IMPLEMENTING",
        worktreePath=prepared["worktreePath"],
        branch=prepared["branch"],
        command=prepared["command"],
    )


@router.get("/{proposal_id}/progress")
async def proposal_progress(proposal_id: str):
    """
    구현 진행 상황 — 워크트리의 `PROPOSAL_<id>_TASKS.md`(speckit tasks 형식)를 읽어
    체크박스 진행률을 반환한다. 구현 탭이 주기적으로 폴링해 진행률/정체 여부를 표시한다.
    헤드리스 완료 신호가 없으므로(FR-007), 파일 기반 추적이 진행 상태 신호가 된다.
    """
    from api.features.proposal_lifecycle.services.tasks_progress import read_progress

    with get_session() as session:
        record = session.run(
            "MATCH (p:Proposal {id: $id}) "
            "RETURN p.status AS status, p.sandboxWorktreePath AS worktreePath",
            id=proposal_id,
        ).single()

    if not record:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")

    progress = read_progress(record.get("worktreePath"), proposal_id)
    progress["proposalId"] = proposal_id
    progress["status"] = record["status"]
    return progress


@router.post("/{proposal_id}/implement/complete")
async def complete_implementation(proposal_id: str, request: Request):
    """
    사용자가 셀에서의 구현을 마쳤다고 표시 → IMPLEMENTING → TESTING 전환 후
    자동 테스트를 백그라운드로 시작한다 (FR-007a). 헤드리스 완료 신호가 없으므로
    이 전환은 사용자 트리거다.
    """
    with get_session() as session:
        result = session.run(
            "MATCH (p:Proposal {id: $id}) RETURN p.status AS status",
            id=proposal_id,
        )
        record = result.single()

    if not record:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")
    if record["status"] != "IMPLEMENTING":
        raise HTTPException(
            status_code=400,
            detail=f"Proposal must be IMPLEMENTING to complete (current: {record['status']})",
        )

    _transition_status(proposal_id, "IMPLEMENTING", "TESTING", "system")
    with get_session() as session:
        session.run(
            "MATCH (p:Proposal {id: $id}) SET p.sandboxStatus = 'DONE', p.testResults = null",
            id=proposal_id,
        )

    # 검증(robo-sync 구조 검증 + GWT)은 사용자가 '검증' 탭을 열 때 트리거한다
    # (POST /{id}/validate). 백그라운드 fire-and-forget로 잃어버리지 않게.
    SmartLogger.log("INFO", f"Implementation marked complete → TESTING: {proposal_id}",
                    category="proposal_lifecycle.implement.complete",
                    params={"proposalId": proposal_id})

    return {"proposalId": proposal_id, "status": "TESTING"}


def _transition_status(proposal_id: str, from_status: str, to_status: str,
                       actor: str, comment: str | None = None) -> None:
    with get_session() as session:
        result = session.run(
            "MATCH (p:Proposal {id: $id}) RETURN p.statusHistory AS history",
            id=proposal_id,
        )
        record = result.single()
        if not record:
            return
        new_history = append_status_history(
            record.get("history") or "[]", from_status, to_status, actor, comment
        )
        session.run(
            "MATCH (p:Proposal {id: $id}) SET p.status = $status, p.statusHistory = $history",
            id=proposal_id, status=to_status, history=new_history,
        )
