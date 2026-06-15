"""
Proposal 구현 준비 서비스.

구현은 헤드리스 배치가 아니라 Code 탭의 살아있는 Claude Code 셀(PTY 터미널)을
재사용하여 인터랙티브하게 수행한다 (FR-007). 이 모듈은 셀이 구현을 시작하기
위해 필요한 것 — 대상 프로젝트(project_root)의 Git Worktree 생성, Diff 컨텍스트
파일 작성, IMPLEMENTING 상태 전환 — 만 처리하고, 셀에 보낼 구현 지시(command)를
반환한다. 실제 코드 생성은 셀의 `claude` 세션이 담당한다.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from api.features.proposal_lifecycle.services.sandbox_manager import SandboxManager
from api.features.proposal_lifecycle.proposal_contracts import append_status_history
from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger

_sandbox = SandboxManager()


def _ensure_worktree_mcp(worktree_path: Path) -> None:
    """워크트리에 robo-spec MCP 가용성 + 사전 신뢰를 보장한다(I9).

    첫 실행 시 claude 가 `.mcp.json` 신뢰 프롬프트("use this mcp server?")를 띄워
    대기하면, 셀에 자동주입되는 `/robo-implement` 명령이 그 프롬프트에 먹혀 유실되고
    구현이 시작되지 않는 레이스가 있었다. `.claude/settings.local.json` 에 서버를
    **사전 신뢰**로 적어두면 프롬프트가 안 떠 레이스가 사라진다.

    - `.mcp.json` 이 없으면 robo-spec(backend `/mcp/`)을 기록(있으면 건드리지 않음).
    - settings.local.json 의 enabledMcpjsonServers 에 그 서버들을 병합(사전 신뢰).
    실패는 best-effort(구현 진행은 계속).
    """
    try:
        mcp_file = worktree_path / ".mcp.json"
        if mcp_file.exists():
            try:
                server_names = list((json.loads(mcp_file.read_text(encoding="utf-8") or "{}").get("mcpServers") or {}).keys())
            except ValueError:
                server_names = []
        else:
            port = os.getenv("API_PORT", "8000")
            mcp_file.write_text(
                json.dumps({"mcpServers": {"robo-spec": {"type": "http", "url": f"http://localhost:{port}/mcp/"}}},
                           indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            server_names = ["robo-spec"]
        if not server_names:
            return
        claude_dir = worktree_path / ".claude"
        claude_dir.mkdir(exist_ok=True)
        settings = claude_dir / "settings.local.json"
        cur = {}
        if settings.exists():
            try:
                cur = json.loads(settings.read_text(encoding="utf-8") or "{}")
            except ValueError:
                cur = {}
        enabled = set(cur.get("enabledMcpjsonServers") or [])
        enabled.update(server_names)
        cur["enabledMcpjsonServers"] = sorted(enabled)
        settings.write_text(json.dumps(cur, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as e:
        SmartLogger.log("WARN", f"worktree mcp pretrust failed: {e}",
                        category="proposal_lifecycle.implement.mcp_warn", params={})


def _get_proposal_context(proposal_id: str) -> dict:
    with get_session() as session:
        result = session.run(
            """
            MATCH (p:Proposal {id: $id})
            RETURN p.originalPrompt AS prompt,
                   p.title AS title,
                   p.strategicDiff AS strategicDiff,
                   p.tacticalDiff AS tacticalDiff
            """,
            id=proposal_id,
        )
        record = result.single()
    if not record:
        return {}
    return {
        "prompt": record["prompt"] or "",
        "title": record.get("title") or proposal_id,
        "strategicDiff": record.get("strategicDiff") or "{}",
        "tacticalDiff": record.get("tacticalDiff") or "[]",
    }


def _tasks_filename(proposal_id: str) -> str:
    # `PROPOSAL_*.md`는 대상 repo의 .git/info/exclude에 등록되어 있어(머지·git status
    # 오염 방지) 진행 추적용 체크리스트로 안전하다. 구현 탭이 이 파일을 폴링한다.
    return f"PROPOSAL_{proposal_id}_TASKS.md"


def _context_doc(proposal_id: str, ctx: dict, has_tasks: bool) -> str:
    """워크트리 루트에 기록할 Diff 컨텍스트 문서."""
    tasks_file = _tasks_filename(proposal_id)
    if has_tasks:
        # 작업 목록은 proposal 단계에서 미리 분해되어 워크트리에 기록돼 있다.
        # 셸은 새로 만들지 말고 그 체크리스트를 따라 구현하며 체크만 한다.
        procedure = (
            "## 구현 절차 (진행 추적)\n"
            f"1. **작업 목록 확인** — 워크트리 루트의 `{tasks_file}` 체크리스트를 읽으세요. "
            "이미 분해된 구현 작업이 speckit 형식으로 들어 있습니다.\n"
            f"2. **단계별 구현 + 체크오프** — 위에서부터 순서대로 각 작업을 구현하고, **완료 즉시** "
            f"`{tasks_file}`에서 해당 항목을 `- [ ]` → `- [x]`로 바꾼 뒤 이 워크트리에서 git commit 하세요.\n"
            "3. 목록에 없는 추가 작업이 꼭 필요하면 항목을 새로 더해도 되지만, 체크박스 형식은 유지하세요. "
            "(구현 탭이 이 파일을 읽어 진행률을 표시합니다.)\n\n"
        )
    else:
        procedure = (
            "## 구현 절차 (진행 추적)\n"
            f"1. **현재 상태 파악** — 기존 구조와 위 Diff를 파악하세요.\n"
            f"2. **작업 목록 생성** — 워크트리 루트에 `{tasks_file}` 체크리스트를 speckit 형식"
            "(`## Phase N:` 섹션별 `- [ ] T001 ...`)으로 만드세요.\n"
            f"3. **단계별 구현 + 체크오프** — 각 작업 완료 즉시 `{tasks_file}`에서 `- [x]`로 바꾸고 commit 하세요.\n\n"
        )
    return (
        f"# Proposal {proposal_id} — 구현 컨텍스트\n\n"
        f"## 제목\n{ctx.get('title', proposal_id)}\n\n"
        f"## 원본 요구사항\n{ctx['prompt']}\n\n"
        f"## Strategic Diff (전략적 변경안: Epic/Feature/UserStory)\n"
        f"```json\n{ctx['strategicDiff']}\n```\n\n"
        f"## Tactical Diff (전술적 변경안: Aggregate/Command/Event/VO)\n"
        f"```json\n{ctx['tacticalDiff']}\n```\n\n"
        f"{procedure}"
        "## 구현 지침\n"
        "- 이 워크트리는 위 Proposal 구현 전용 샌드박스입니다. 상위/메인 프로젝트는 절대 수정하지 마세요.\n"
        "- Tactical Diff: MODIFY → 기존 파일 수정, CREATE → 신규 파일 생성.\n"
        "- Strategic Diff: 새 UserStory → 도메인 모델·API·프런트엔드 파일 생성.\n"
        f"- 진행률이 정확히 표시되도록 `{tasks_file}`의 체크박스 상태를 항상 최신으로 유지하세요.\n"
    )


def _build_command(proposal_id: str, doc_filename: str, has_tasks: bool) -> str:
    """Code 탭 셀(claude 세션)에 자동 입력할 구현 시작 명령.

    구현은 robo-implement 스킬의 PRO 모드(`/robo-implement <PRO-NNN>`)로 시작한다.
    이 모드는 워크트리의 `PROPOSAL_<id>.md`(컨텍스트)와 `PROPOSAL_<id>_TASKS.md`
    (체크리스트)를 읽어 미체크 작업을 구현하며 `- [x]`로 체크·커밋한다.
    셀의 'Claude Code 셀로 이동' 버튼을 누르면 프런트엔드가 이 명령을 셀에 주입한다.
    """
    return f"/robo-implement {proposal_id}"


def prepare_implementation(proposal_id: str, project_root: str,
                           allow_init: bool = False) -> dict:
    """
    대상 프로젝트(project_root)에 Worktree 생성 → 컨텍스트 파일 작성 →
    IMPLEMENTING 전환. 셀이 실행할 {worktreePath, branch, command} 반환.

    대상이 Git 저장소가 아니고 allow_init=False 이면 NotAGitRepoError 가 전파되어
    route가 프런트엔드에 git init 다이얼로그를 띄우게 한다. (FR-006)
    """
    worktree_path = _sandbox.create_worktree(proposal_id, project_root, allow_init=allow_init)
    branch = _sandbox.branch_name(proposal_id)
    worktree_str = str(worktree_path)
    # 저장은 정규화(de-nest)된 실제 루트로 — 오염된 입력이 다시 새지 않도록.
    resolved_root = str(_sandbox.resolve_root(project_root))

    # I9: robo-spec MCP 가용성 + 사전 신뢰 → 첫 실행 MCP 신뢰 프롬프트와 자동주입 충돌 제거.
    _ensure_worktree_mcp(worktree_path)

    # 미리 분해된 작업 목록(tasksJson)을 speckit 마크다운으로 렌더해 워크트리에 기록한다.
    # 셸이 만들지 않고, proposal 단계에서 헤드리스로 뽑아둔 체크리스트를 그대로 넣어준다.
    from api.features.proposal_lifecycle.services.tasks_runner import load_tasks
    tasks_file = _tasks_filename(proposal_id)
    loaded = load_tasks(proposal_id)
    has_tasks = bool(loaded.get("exists"))
    if has_tasks:
        try:
            (worktree_path / tasks_file).write_text(loaded["markdown"], encoding="utf-8")
        except OSError as e:
            has_tasks = False
            SmartLogger.log("WARN", f"tasks file write failed: {e}",
                            category="proposal_lifecycle.implement.tasks_warn",
                            params={"proposalId": proposal_id})

    # Diff 컨텍스트 문서를 워크트리 루트에 기록
    ctx = _get_proposal_context(proposal_id)
    doc_filename = f"PROPOSAL_{proposal_id}.md"
    try:
        (worktree_path / doc_filename).write_text(
            _context_doc(proposal_id, ctx, has_tasks), encoding="utf-8"
        )
    except OSError as e:
        SmartLogger.log("WARN", f"context doc write failed: {e}",
                        category="proposal_lifecycle.implement.context_warn",
                        params={"proposalId": proposal_id})

    # SUBMITTED → IMPLEMENTING + 샌드박스 메타데이터(projectRoot 포함) 저장
    _transition_status(proposal_id, "SUBMITTED", "IMPLEMENTING", "system")
    with get_session() as session:
        session.run(
            """
            MATCH (p:Proposal {id: $id})
            SET p.projectRoot = $projectRoot,
                p.sandboxBranch = $branch,
                p.sandboxWorktreePath = $path,
                p.sandboxStatus = 'IMPLEMENTING'
            """,
            id=proposal_id,
            projectRoot=resolved_root,
            branch=branch,
            path=worktree_str,
        )

    command = _build_command(proposal_id, doc_filename, has_tasks)

    SmartLogger.log("INFO", f"implementation prepared: {proposal_id}",
                    category="proposal_lifecycle.implement.prepared",
                    params={"proposalId": proposal_id, "worktreePath": worktree_str,
                            "branch": branch, "projectRoot": str(project_root)})

    return {"worktreePath": worktree_str, "branch": branch, "command": command}


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
