"""SandboxManager(대상 프로젝트 git worktree) 단위 테스트 — 임시 디렉터리의 실제 git 저장소 사용.

사용자 git 설정(서명·훅·identity)에 흔들리지 않도록 GIT_CONFIG_GLOBAL 을 테스트 전용 파일로,
시스템 설정은 끄고, 저장소 탐색은 tmp 상위로 못 올라가게 막는다. 네트워크·DB 는 쓰지 않는다.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from api.features.proposal_lifecycle.services import dual_merge, sandbox_manager
from api.features.proposal_lifecycle.services.sandbox_manager import (
    NotAGitRepoError,
    SandboxManager,
)
from api.features.proposal_lifecycle.tests.lifecycle_fakes import (
    FakeGraph,
    capture_logs,
    forbid_real_backends,
)

PID = "PRO-001"

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git 이 필요하다")

_IDENTITY = {
    "GIT_AUTHOR_NAME": "Test Dev", "GIT_AUTHOR_EMAIL": "dev@example.com",
    "GIT_COMMITTER_NAME": "Test Dev", "GIT_COMMITTER_EMAIL": "dev@example.com",
}


@pytest.fixture(autouse=True)
def git_env(tmp_path, monkeypatch):
    forbid_real_backends(monkeypatch)
    capture_logs(monkeypatch)
    cfg = tmp_path / "gitconfig"
    cfg.write_text("[init]\n\tdefaultBranch = main\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
        monkeypatch.delenv(k, raising=False)
    for k, v in _IDENTITY.items():
        monkeypatch.setenv(k, v)


def git(cwd, *args) -> str:
    out = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    assert out.returncode == 0, f"git {' '.join(args)} failed: {out.stderr}"
    return out.stdout.strip()


def commit_file(cwd, rel, content, message):
    f = Path(cwd) / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content, encoding="utf-8")
    git(cwd, "add", rel)
    git(cwd, "commit", "-q", "-m", message)


@pytest.fixture
def repo(tmp_path) -> Path:
    root = tmp_path / "shop"
    root.mkdir()
    git(root, "init", "-q")
    commit_file(root, "README.md", "# shop\n", "init")
    commit_file(root, "src/app.py", "print('shop')\n", "app")
    return root


@pytest.fixture
def sm() -> SandboxManager:
    return SandboxManager()


# ── 이름 규칙 · 루트 해석 ─────────────────────────────────────────────────────

def test_naming(sm, repo):
    assert sm.branch_name(PID) == "proposal/PRO-001"
    assert sm.worktree_path(PID, str(repo)) == repo / ".sandbox" / "proposal" / PID


@pytest.mark.parametrize("bad", [None, ""])
def test_empty_project_root_is_rejected(sm, bad):
    with pytest.raises(RuntimeError, match="projectRoot가 비어"):
        sm.resolve_root(bad)


def test_missing_project_root_is_rejected(sm, tmp_path):
    with pytest.raises(RuntimeError, match="존재하지 않는"):
        sm.resolve_root(str(tmp_path / "nope"))


def test_project_root_inside_a_sandbox_is_denested(sm, repo):
    other = sm.create_worktree("PRO-002", str(repo))
    assert sm.resolve_root(str(other)) == repo
    assert sm.resolve_root(str(other / "src")) == repo
    # 오염된 projectRoot(다른 Proposal 의 worktree)로 만들어도 중첩되지 않는다
    path = sm.create_worktree(PID, str(other))
    assert path == repo / ".sandbox" / "proposal" / PID
    assert not (other / ".sandbox").exists()


# ── worktree 생성 ────────────────────────────────────────────────────────────

def test_create_worktree_branches_from_head(sm, repo):
    path = sm.create_worktree(PID, str(repo))
    assert path == repo / ".sandbox" / "proposal" / PID and path.is_dir()
    assert git(path, "rev-parse", "--abbrev-ref", "HEAD") == "proposal/PRO-001"
    assert git(path, "rev-parse", "HEAD") == git(repo, "rev-parse", "HEAD")
    assert (path / "src" / "app.py").read_text(encoding="utf-8") == "print('shop')\n"
    assert git(repo, "branch", "--list", "proposal/PRO-001")
    # 원본 저장소는 .sandbox/ 때문에 더러워지지 않는다
    assert git(repo, "status", "--porcelain") == ""


def test_recreating_resets_branch_to_current_head(sm, repo):
    path = sm.create_worktree(PID, str(repo))
    commit_file(path, "src/refund.py", "def refund(): ...\n", "wip")
    commit_file(repo, "src/app.py", "print('shop v2')\n", "main moved on")

    again = sm.create_worktree(PID, str(repo))
    assert again == path
    assert git(path, "rev-parse", "HEAD") == git(repo, "rev-parse", "HEAD")
    assert not (path / "src" / "refund.py").exists()
    porcelain = git(repo, "worktree", "list", "--porcelain")
    assert porcelain.count("worktree ") == 2


def test_create_removes_stale_worktree_holding_the_branch(sm, repo, tmp_path):
    git(repo, "branch", "proposal/PRO-001")
    stray = tmp_path / "stray-worktree"
    git(repo, "worktree", "add", "-q", str(stray), "proposal/PRO-001")

    path = sm.create_worktree(PID, str(repo))
    assert not stray.exists()
    assert git(path, "rev-parse", "--abbrev-ref", "HEAD") == "proposal/PRO-001"


def test_insufficient_disk_space_is_rejected(sm, repo, monkeypatch):
    monkeypatch.setattr(sandbox_manager.shutil, "disk_usage",
                        lambda _p: SimpleNamespace(total=1, used=1, free=50 * 1024 * 1024))
    with pytest.raises(RuntimeError, match="Insufficient disk space: 50MB"):
        sm.create_worktree(PID, str(repo))
    assert not sm.worktree_path(PID, str(repo)).exists()


# ── git 저장소가 아닌 폴더 ─────────────────────────────────────────────────────

@pytest.fixture
def plain_folder(tmp_path) -> Path:
    folder = tmp_path / "plain"
    (folder / "src").mkdir(parents=True)
    (folder / "src" / "main.py").write_text("print(1)\n", encoding="utf-8")
    return folder


def test_non_git_folder_requires_consent(sm, plain_folder):
    assert sm.is_git_repo(plain_folder) is False
    with pytest.raises(NotAGitRepoError) as exc:
        sm.create_worktree(PID, str(plain_folder))
    assert exc.value.root == str(plain_folder)
    assert not (plain_folder / ".git").exists()
    assert not (plain_folder / ".sandbox").exists()


def test_non_git_folder_is_initialised_with_consent(sm, plain_folder, monkeypatch):
    # 사용자 git identity 가 없는 환경 — init_git_repo 는 -c 로 대체 identity 를 넣는다
    for k in _IDENTITY:
        monkeypatch.delenv(k, raising=False)
    path = sm.create_worktree(PID, str(plain_folder), allow_init=True)

    assert sm.is_git_repo(plain_folder)
    assert git(plain_folder, "log", "--format=%an <%ae>|%s") == \
        "robo-architect <robo-architect@localhost>|Initial commit (robo-architect)"
    assert git(plain_folder, "ls-files") == "src/main.py"  # 기존 파일이 초기 커밋에 들어간다
    assert (path / "src" / "main.py").exists()
    assert ".sandbox/" in (plain_folder / ".git" / "info" / "exclude").read_text(encoding="utf-8")


def test_init_git_repo_on_empty_folder_makes_empty_commit(sm, tmp_path):
    folder = tmp_path / "empty"
    folder.mkdir()
    sm.init_git_repo(folder)
    assert git(folder, "rev-list", "--count", "HEAD") == "1"
    assert git(folder, "ls-files") == ""


# ── info/exclude ─────────────────────────────────────────────────────────────

_PATTERNS = (".sandbox/", "PROPOSAL_*.md", ".claude/settings.local.json")


def test_ensure_excludes_appends_once_and_keeps_user_rules(sm, repo):
    exclude = repo / ".git" / "info" / "exclude"
    exclude.write_text("# 사용자 규칙\n*.log", encoding="utf-8")  # 끝 개행 없음
    sm._ensure_excludes(repo)
    sm._ensure_excludes(repo)
    text = exclude.read_text(encoding="utf-8")
    assert text.startswith("# 사용자 규칙\n*.log\n# robo-architect proposal sandbox\n")
    assert text.count("# robo-architect proposal sandbox") == 1
    for pat in _PATTERNS:
        assert text.splitlines().count(pat) == 1


def test_ensure_excludes_only_adds_missing_patterns(sm, repo):
    exclude = repo / ".git" / "info" / "exclude"
    exclude.write_text(".sandbox/\n", encoding="utf-8")
    sm._ensure_excludes(repo)
    lines = exclude.read_text(encoding="utf-8").splitlines()
    assert lines.count(".sandbox/") == 1
    assert "PROPOSAL_*.md" in lines and ".claude/settings.local.json" in lines


def test_ensure_excludes_from_worktree_writes_shared_exclude(sm, repo):
    path = sm.create_worktree(PID, str(repo))
    exclude = repo / ".git" / "info" / "exclude"
    exclude.write_text("", encoding="utf-8")
    sm._ensure_excludes(path)
    assert ".sandbox/" in exclude.read_text(encoding="utf-8")
    assert not (path / ".git" / "info").exists()  # worktree 의 .git 은 파일이다


def test_ensure_excludes_outside_git_is_noop(sm, plain_folder):
    sm._ensure_excludes(plain_folder)
    assert not (plain_folder / ".git").exists()


def test_proposal_artifacts_do_not_pollute_status(sm, repo):
    path = sm.create_worktree(PID, str(repo))
    (path / f"PROPOSAL_{PID}_TASKS.md").write_text("- [ ] T001 작업\n", encoding="utf-8")
    (path / ".claude").mkdir(exist_ok=True)
    (path / ".claude" / "settings.local.json").write_text("{}", encoding="utf-8")
    assert git(path, "status", "--porcelain") == ""
    assert git(repo, "status", "--porcelain") == ""


# ── merge · reset · revert ───────────────────────────────────────────────────

def _implement(sm, repo):
    path = sm.create_worktree(PID, str(repo))
    commit_file(path, "src/refund.py", "def refund(amount): ...\n", "feat: 부분 환불")
    (path / f"PROPOSAL_{PID}_TASKS.md").write_text("- [x] T001 작업\n", encoding="utf-8")
    return path


def test_merge_to_main_creates_accept_merge_commit(sm, repo):
    _implement(sm, repo)
    result = sm.merge_to_main(PID, str(repo))
    assert result.success is True and result.error is None
    assert (repo / "src" / "refund.py").exists()
    assert git(repo, "log", "-1", "--format=%s") == f"Accept {PID}"
    assert len(git(repo, "log", "-1", "--format=%P").split()) == 2  # --no-ff 머지 커밋
    assert not (repo / f"PROPOSAL_{PID}_TASKS.md").exists()  # 추적 안 되는 진행 파일은 넘어오지 않는다


def test_merge_again_after_success_is_a_noop_success(sm, repo):
    """graph_update 실패 뒤 retry-merge 는 이미 머지된 브랜치를 다시 머지한다."""
    _implement(sm, repo)
    assert sm.merge_to_main(PID, str(repo)).success
    head = git(repo, "rev-parse", "HEAD")
    assert sm.merge_to_main(PID, str(repo)).success
    assert git(repo, "rev-parse", "HEAD") == head


def test_merge_of_missing_branch_fails_with_git_error(sm, repo):
    result = sm.merge_to_main("PRO-404", str(repo))
    assert result.success is False
    assert "proposal/PRO-404" in result.error


def _conflict(sm, repo):
    path = sm.create_worktree(PID, str(repo))
    commit_file(path, "README.md", "# shop (proposal)\n", "proposal edit")
    commit_file(repo, "README.md", "# shop (main)\n", "main edit")
    return sm.merge_to_main(PID, str(repo))


def test_merge_conflict_reports_failure(sm, repo):
    result = _conflict(sm, repo)
    assert result.success is False


@pytest.mark.xfail(strict=True, reason=(
    "BUG: 충돌 시 git 은 'CONFLICT ...' 를 stdout 에 쓰고 stderr 는 비어 있는데 merge_to_main 은 stderr 만 "
    "담는다 (sandbox_manager.py merge_to_main). error 가 '' → dual_merge 는 'git merge 실패' 로만 기록해 "
    "MERGE_FAILED 화면에 어느 파일이 충돌했는지 보이지 않는다."))
def test_merge_conflict_error_names_conflicting_file(sm, repo):
    result = _conflict(sm, repo)
    assert result.error and "README.md" in result.error


@pytest.mark.xfail(strict=True, reason=(
    "BUG: 충돌 머지를 abort 하지 않아 대상 프로젝트 작업 트리에 충돌 마커와 MERGE_HEAD 가 남는다 "
    "(sandbox_manager.py merge_to_main). 이후 retry-merge 는 'unmerged files' 로 계속 실패한다. "
    "revert_merge_commit 은 충돌 시 git revert --abort 로 정리하는 것과 대조적."))
def test_merge_conflict_leaves_target_repo_clean(sm, repo):
    _conflict(sm, repo)
    assert not (repo / ".git" / "MERGE_HEAD").exists()
    assert git(repo, "status", "--porcelain") == ""


@pytest.mark.xfail(strict=True, reason=(
    "BUG: reset_merge 는 `git reset --merge`(대상 커밋 없음 = HEAD)라, merge_to_main 이 이미 만든 머지 커밋을 "
    "되돌리지 못한다 (sandbox_manager.py reset_merge). dual merge 의 graph_update 실패 보상이 no-op 이 되어 "
    "코드는 main 에 머지된 채 Proposal 만 MERGE_FAILED 가 된다."))
def test_reset_merge_rolls_back_the_accept_merge_commit(sm, repo):
    before = git(repo, "rev-parse", "HEAD")
    _implement(sm, repo)
    assert sm.merge_to_main(PID, str(repo)).success
    sm.reset_merge(PID, str(repo))
    assert git(repo, "rev-parse", "HEAD") == before
    assert not (repo / "src" / "refund.py").exists()


def test_revert_merge_commit_undoes_accept(sm, repo):
    _implement(sm, repo)
    sm.merge_to_main(PID, str(repo))
    result = sm.revert_merge_commit(PID, str(repo))
    assert result.success is True and result.error is None
    assert not (repo / "src" / "refund.py").exists()
    assert git(repo, "log", "-1", "--format=%s") == f'Revert "Accept {PID}"'


def test_revert_without_accept_commit_is_treated_as_done(sm, repo):
    head = git(repo, "rev-parse", "HEAD")
    result = sm.revert_merge_commit(PID, str(repo))
    assert result.success is True and "찾지 못함" in result.error
    assert git(repo, "rev-parse", "HEAD") == head


def test_revert_conflict_is_aborted_and_reported(sm, repo):
    path = sm.create_worktree(PID, str(repo))
    commit_file(path, "README.md", "# shop (proposal)\n", "proposal edit")
    sm.merge_to_main(PID, str(repo))
    commit_file(repo, "README.md", "# shop (edited after accept)\n", "later edit")
    head = git(repo, "rev-parse", "HEAD")

    result = sm.revert_merge_commit(PID, str(repo))
    assert result.success is False and result.error
    assert git(repo, "rev-parse", "HEAD") == head
    assert git(repo, "status", "--porcelain") == ""
    assert not (repo / ".git" / "REVERT_HEAD").exists()


# ── 정리 ──────────────────────────────────────────────────────────────────────

def test_cleanup_worktree_removes_directory_but_keeps_branch(sm, repo):
    path = _implement(sm, repo)
    (path / ".claude").mkdir(exist_ok=True)
    (path / ".claude" / "settings.local.json").write_text("{}", encoding="utf-8")
    sm.merge_to_main(PID, str(repo))

    sm.cleanup_worktree(PID, str(repo))
    assert not path.exists()
    assert str(path) not in git(repo, "worktree", "list", "--porcelain")
    assert git(repo, "branch", "--list", "proposal/PRO-001")  # 이력 보존
    sm.cleanup_worktree(PID, str(repo))  # 이미 없으면 조용히 통과


def test_remove_worktree_deletes_directory_and_branch(sm, repo):
    path = _implement(sm, repo)
    sm.remove_worktree(PID, str(repo))
    assert not path.exists()
    assert git(repo, "branch", "--list", "proposal/PRO-001") == ""
    sm.remove_worktree(PID, str(repo))  # 두 번 불러도 오류 없음


@pytest.mark.xfail(strict=True, reason=(
    "BUG(낮음): worktree 폴더가 git 밖에서 지워졌으면(.sandbox 수동 삭제 등) remove_worktree 는 "
    "`git worktree remove` 를 건너뛰고 prune 없이 `git branch -D` 를 부른다 — git 은 '브랜치가 worktree 에서 "
    "사용 중'이라며 거부하고, 반환 코드를 보지 않아 Destroy 뒤에도 proposal/<id> 브랜치가 남는다 "
    "(sandbox_manager.py remove_worktree)."))
def test_remove_worktree_deletes_branch_even_if_directory_is_gone(sm, repo):
    path = sm.create_worktree(PID, str(repo))
    shutil.rmtree(path)
    sm.remove_worktree(PID, str(repo))  # /destroy 가 부르는 그대로
    assert git(repo, "branch", "--list", "proposal/PRO-001") == ""


def test_prune_dead_worktrees(sm, repo):
    path = sm.create_worktree(PID, str(repo))
    shutil.rmtree(path)
    sm.prune_dead_worktrees(str(repo))
    assert str(path) not in git(repo, "worktree", "list", "--porcelain")


# ── 실제 git + 가짜 그래프로 Accept 한 바퀴 ────────────────────────────────────

def _graph_for(repo):
    strategic = {"epics": [{"op": "CREATE", "tempId": "EP-001", "entityTitle": "환불"}]}
    return FakeGraph({"id": PID, "status": "PENDING_ACCEPTANCE", "projectRoot": str(repo),
                      "strategicDiff": json.dumps(strategic, ensure_ascii=False),
                      "tacticalDiff": "[]", "statusHistory": "[]"})


def test_accept_end_to_end_merges_code_and_cleans_worktree(sm, repo, monkeypatch):
    path = _implement(sm, repo)
    graph = _graph_for(repo)
    monkeypatch.setattr(dual_merge, "get_session", graph.session)
    monkeypatch.setattr(dual_merge, "_sandbox", SandboxManager())
    monkeypatch.setattr(dual_merge, "_update_spec_docs", lambda pid: None)

    asyncio.run(dual_merge.execute_dual_merge(PID, "po@example.com"))
    assert graph.proposal["status"] == "ACCEPTED"
    assert (repo / "src" / "refund.py").exists()
    assert not path.exists()
    assert git(repo, "branch", "--list", "proposal/PRO-001")
    assert len(graph.nodes_of("BoundedContext")) == 1


def test_accept_end_to_end_conflict_keeps_worktree_for_retry(sm, repo, monkeypatch):
    path = sm.create_worktree(PID, str(repo))
    commit_file(path, "README.md", "# shop (proposal)\n", "proposal edit")
    commit_file(repo, "README.md", "# shop (main)\n", "main edit")
    graph = _graph_for(repo)
    monkeypatch.setattr(dual_merge, "get_session", graph.session)
    monkeypatch.setattr(dual_merge, "_sandbox", SandboxManager())
    monkeypatch.setattr(dual_merge, "_update_spec_docs", lambda pid: None)

    with pytest.raises(dual_merge.DualMergeFailed):
        asyncio.run(dual_merge.execute_dual_merge(PID, "po@example.com"))
    assert graph.proposal["status"] == "MERGE_FAILED"
    assert path.is_dir()
    assert graph.nodes == {}
