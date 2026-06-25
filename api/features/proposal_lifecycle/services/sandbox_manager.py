"""
Git Worktree 샌드박스 관리 서비스.
proposal/<PRO-NNN> 격리 브랜치 생성/삭제/머지/롤백.

중요: Worktree의 원천은 robo-architect(설계 도구 자신)가 아니라
Claude Code 탭에 설정된 **대상 프로젝트**(`project_root`)이다.
모든 git 명령은 `cwd=project_root`로 실행되며, Worktree는
`<project_root>/.sandbox/proposal/<PRO-NNN>` 에 생성된다. (FR-006)
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from api.platform.observability.smart_logger import SmartLogger


@dataclass
class MergeResult:
    success: bool
    error: str | None = None


class NotAGitRepoError(RuntimeError):
    """대상 프로젝트(project_root)가 아직 Git 저장소가 아님.

    호출자(route)는 이를 잡아 프런트엔드에 다이얼로그로 'git init 후 계속'
    여부를 묻게 하고, 사용자가 동의하면 allow_init=True로 재시도한다. (FR-006)
    """

    def __init__(self, root: str | Path):
        self.root = str(root)
        super().__init__(f"대상 프로젝트가 Git 저장소가 아닙니다: {root}")


class SandboxManager:
    def _denest(self, path: Path) -> Path:
        """경로가 샌드박스 worktree 내부(.../.sandbox/proposal/<id>[/...])를 가리키면
        실제 프로젝트 루트로 끌어올린다.

        오염된 projectRoot(예: 다른 Proposal의 worktree 경로)가 들어와도 Worktree를
        그 안에 중첩 생성하지 않도록 가장 바깥 '.sandbox' 세그먼트의 부모를 실제
        루트로 본다. 정상 루트면 변화 없음(no-op). (FR-006 / 중첩 worktree 방지)
        """
        parts = path.parts
        for i, seg in enumerate(parts):
            if seg == ".sandbox" and i > 0:
                return Path(*parts[:i])
        return path

    def _resolve_root(self, project_root: str | None) -> Path:
        if not project_root:
            raise RuntimeError(
                "projectRoot가 비어 있습니다. Claude Code 탭에서 대상 프로젝트 경로를 먼저 설정하세요."
            )
        path = self._denest(Path(project_root).expanduser())
        if not path.is_dir():
            raise RuntimeError(f"projectRoot가 존재하지 않는 경로입니다: {project_root}")
        return path

    def resolve_root(self, project_root: str | None) -> Path:
        """정규화(de-nest)된 실제 프로젝트 루트. 호출자가 저장·표시에 사용한다."""
        return self._resolve_root(project_root)

    def is_git_repo(self, root: Path) -> bool:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=str(root), capture_output=True, text=True,
        )
        return result.returncode == 0

    def init_git_repo(self, root: Path) -> None:
        """대상 프로젝트에 Git 저장소를 생성하고 초기 커밋을 만든다.

        `git worktree add ... HEAD`는 HEAD가 커밋을 가리켜야 동작하므로,
        init 직후 (파일이 있으면 add 후, 없으면 빈) 초기 커밋을 만든다.
        사용자가 동의(다이얼로그)한 경우에만 호출된다. (FR-006)
        """
        init = subprocess.run(
            ["git", "init"], cwd=str(root), capture_output=True, text=True,
        )
        if init.returncode != 0:
            raise RuntimeError(f"git init 실패: {init.stderr.strip()}")

        # 초기 커밋 — 사용자 git identity가 없을 수 있으므로 -c 로 폴백을 주입한다.
        # 파일이 있으면 모두 스테이징하고, 비어 있으면 --allow-empty 로 커밋한다.
        subprocess.run(["git", "add", "-A"], cwd=str(root), capture_output=True)
        commit = subprocess.run(
            ["git",
             "-c", "user.name=robo-architect",
             "-c", "user.email=robo-architect@localhost",
             "commit", "--allow-empty", "-m", "Initial commit (robo-architect)"],
            cwd=str(root), capture_output=True, text=True,
        )
        if commit.returncode != 0:
            raise RuntimeError(f"초기 커밋 실패: {commit.stderr.strip()}")

        SmartLogger.log("INFO", f"git init done: {root}",
                        category="proposal_lifecycle.sandbox.git_init",
                        params={"projectRoot": str(root)})

    def _ensure_git_repo(self, root: Path, allow_init: bool) -> None:
        if self.is_git_repo(root):
            return
        if not allow_init:
            raise NotAGitRepoError(root)
        self.init_git_repo(root)

    def sandbox_base(self, project_root: str) -> Path:
        return self._resolve_root(project_root) / ".sandbox" / "proposal"

    def worktree_path(self, proposal_id: str, project_root: str) -> Path:
        return self.sandbox_base(project_root) / proposal_id

    def branch_name(self, proposal_id: str) -> str:
        return f"proposal/{proposal_id}"

    def _ensure_excludes(self, root: Path) -> None:
        """대상 repo의 공용 info/exclude에 샌드박스 산출물 제외 규칙을 추가한다.
        (`.git/info/exclude`는 모든 worktree에 적용 — git status/머지 오염 방지)
        커밋되는 파일이 아니므로 사용자 프로젝트의 추적 파일은 건드리지 않는다.
        """
        common = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=str(root), capture_output=True, text=True,
        )
        if common.returncode != 0:
            return
        git_common = Path(common.stdout.strip())
        if not git_common.is_absolute():
            git_common = (root / git_common).resolve()
        exclude_file = git_common / "info" / "exclude"
        try:
            exclude_file.parent.mkdir(parents=True, exist_ok=True)
            existing = exclude_file.read_text(encoding="utf-8") if exclude_file.exists() else ""
            # `.claude/settings.local.json`(I9 MCP 사전신뢰)은 머신 로컬 신뢰 설정이라
            # 커밋/머지 대상에서 제외한다.
            additions = [p for p in (".sandbox/", "PROPOSAL_*.md", ".claude/settings.local.json") if p not in existing]
            if additions:
                with exclude_file.open("a", encoding="utf-8") as f:
                    if existing and not existing.endswith("\n"):
                        f.write("\n")
                    f.write("# robo-architect proposal sandbox\n")
                    f.write("\n".join(additions) + "\n")
        except OSError:
            pass  # exclude는 best-effort — 실패해도 worktree 생성은 계속

    def _worktrees_to_remove(self, root: Path, target_path: Path, branch: str) -> list[str]:
        """target_path와 같은 경로이거나 branch를 체크아웃 중인 worktree 경로 목록.

        `git worktree add -B <branch>`는 그 브랜치가 다른 worktree에 체크아웃돼 있으면
        실패하므로, 재생성 전에 둘 다 정리해야 한다.
        """
        out = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=str(root), capture_output=True, text=True,
        ).stdout
        target = str(target_path)
        branch_ref = f"refs/heads/{branch}"
        to_remove: list[str] = []
        cur_path: str | None = None
        for line in out.splitlines() + [""]:
            if line.startswith("worktree "):
                cur_path = line[len("worktree "):].strip()
            elif line.startswith("branch "):
                if cur_path and line[len("branch "):].strip() == branch_ref:
                    to_remove.append(cur_path)
            elif line == "":
                if cur_path and cur_path == target and cur_path not in to_remove:
                    to_remove.append(cur_path)
                cur_path = None
        return to_remove

    def create_worktree(self, proposal_id: str, project_root: str,
                        allow_init: bool = False) -> Path:
        """대상 프로젝트(project_root)의 HEAD에서 proposal/<id> 브랜치 + worktree 생성.

        대상이 아직 Git 저장소가 아니면 allow_init=False 일 때 NotAGitRepoError 를
        던져 프런트엔드가 'git init 후 계속' 다이얼로그를 띄우게 한다. 사용자가
        동의해 allow_init=True 로 재호출되면 init_git_repo 로 저장소를 생성한다. (FR-006)
        """
        root = self._resolve_root(project_root)
        self._ensure_git_repo(root, allow_init)
        self._ensure_excludes(root)

        # 디스크 공간 체크 (100MB 미만이면 오류)
        usage = shutil.disk_usage(str(root))
        if usage.free < 100 * 1024 * 1024:
            raise RuntimeError(
                f"Insufficient disk space: {usage.free // (1024*1024)}MB free. Need at least 100MB."
            )

        path = self.worktree_path(proposal_id, project_root)
        path.parent.mkdir(parents=True, exist_ok=True)

        SmartLogger.log("INFO", f"sandbox_created: {proposal_id}",
                        category="proposal_lifecycle.sandbox.creating",
                        params={"proposalId": proposal_id, "path": str(path),
                                "projectRoot": str(root)})

        # 충돌하는 기존 worktree 정리: 같은 경로뿐 아니라 같은 브랜치를 체크아웃 중인
        # worktree(중첩/오염으로 생긴 잔존물 포함)도 제거해야 `-B` 재생성이 가능하다.
        subprocess.run(["git", "worktree", "prune"], cwd=str(root), capture_output=True)
        for stale in self._worktrees_to_remove(root, path, self.branch_name(proposal_id)):
            subprocess.run(
                ["git", "worktree", "remove", "--force", stale],
                cwd=str(root), capture_output=True,
            )

        # Use -B to force-reset branch if it already exists
        result = subprocess.run(
            ["git", "worktree", "add", "-B", self.branch_name(proposal_id), str(path), "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git worktree add failed: {result.stderr.strip()}")

        return path

    def remove_worktree(self, proposal_id: str, project_root: str) -> None:
        """Worktree 제거 + 브랜치 삭제."""
        root = self._resolve_root(project_root)
        path = self.worktree_path(proposal_id, project_root)

        if path.exists():
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(path)],
                cwd=str(root),
                capture_output=True,
            )

        # 브랜치 삭제 (없으면 무시)
        subprocess.run(
            ["git", "branch", "-D", self.branch_name(proposal_id)],
            cwd=str(root),
            capture_output=True,
        )

        SmartLogger.log("INFO", f"Worktree removed: {proposal_id}",
                        category="proposal_lifecycle.sandbox.removed",
                        params={"proposalId": proposal_id})

    def merge_to_main(self, proposal_id: str, project_root: str) -> MergeResult:
        """샌드박스 브랜치를 대상 프로젝트의 현재 브랜치에 머지."""
        root = self._resolve_root(project_root)
        result = subprocess.run(
            ["git", "merge", "--no-ff", self.branch_name(proposal_id),
             "-m", f"Accept {proposal_id}"],
            cwd=str(root),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return MergeResult(success=False, error=result.stderr.strip())

        SmartLogger.log("INFO", f"merge_start done: {proposal_id}",
                        category="proposal_lifecycle.merge.git_done",
                        params={"proposalId": proposal_id})
        return MergeResult(success=True)

    def reset_merge(self, proposal_id: str, project_root: str) -> None:
        """머지 롤백 (보상 트랜잭션)."""
        root = self._resolve_root(project_root)
        subprocess.run(
            ["git", "reset", "--merge"],
            cwd=str(root),
            capture_output=True,
        )
        SmartLogger.log("WARN", f"Merge reset (compensating): {proposal_id}",
                        category="proposal_lifecycle.merge.reset",
                        params={"proposalId": proposal_id})

    def revert_merge_commit(self, proposal_id: str, project_root: str) -> MergeResult:
        """수거(revoke) 시 Accept 머지 커밋을 git revert 한다.

        merge_to_main이 남긴 'Accept {proposal_id}' 메시지의 머지 커밋을 찾아
        `git revert -m 1 --no-edit`로 되돌린다. 머지 커밋이 없으면 성공으로 간주.
        """
        root = self._resolve_root(project_root)
        find = subprocess.run(
            ["git", "log", "--grep", f"Accept {proposal_id}", "--format=%H", "-n", "1"],
            cwd=str(root), capture_output=True, text=True,
        )
        sha = (find.stdout or "").strip()
        if not sha:
            return MergeResult(success=True, error="머지 커밋을 찾지 못함 (이미 정리됨)")

        result = subprocess.run(
            ["git", "revert", "-m", "1", "--no-edit", sha],
            cwd=str(root), capture_output=True, text=True,
        )
        if result.returncode != 0:
            # 충돌 시 revert 중단
            subprocess.run(["git", "revert", "--abort"], cwd=str(root), capture_output=True)
            return MergeResult(success=False, error=result.stderr.strip() or "git revert 실패")

        SmartLogger.log("INFO", f"Merge reverted (revoke): {proposal_id} ({sha[:8]})",
                        category="proposal_lifecycle.revoke.git_revert",
                        params={"proposalId": proposal_id, "sha": sha})
        return MergeResult(success=True)

    def cleanup_worktree(self, proposal_id: str, project_root: str) -> None:
        """Accept 완료 후 Worktree 정리 (브랜치는 이력 보존)."""
        root = self._resolve_root(project_root)
        path = self.worktree_path(proposal_id, project_root)
        if path.exists():
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(path)],
                cwd=str(root),
                capture_output=True,
            )
        SmartLogger.log("INFO", f"Worktree cleanup done: {proposal_id}",
                        category="proposal_lifecycle.sandbox.cleanup",
                        params={"proposalId": proposal_id})

    def prune_dead_worktrees(self, project_root: str) -> None:
        """고아 Worktree 정리."""
        root = self._resolve_root(project_root)
        subprocess.run(
            ["git", "worktree", "prune"],
            cwd=str(root),
            capture_output=True,
        )
        SmartLogger.log("INFO", "git worktree prune done",
                        category="proposal_lifecycle.sandbox.prune", params={})
