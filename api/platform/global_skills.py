"""
사용자 홈의 Claude 기본 스킬 폴더(``~/.claude/skills/``)에 이 저장소의
``skills/`` 트리(robo-spec / robo-proposals / robo-changes …)를 설치/점검한다.

대상 프로젝트의 ``.claude/skills`` (claude_code.router._install_robo_spec)와는
별개로, **인터랙티브 Claude Code 셀에서 슬래시 커맨드로 스킬을 쓰려면** 사용자
홈 폴더에 스킬이 깔려 있어야 한다. Code 탭 진입 시 이 모듈로 점검한다.

설치 단위는 "리프 스킬" — ``skills/<group>/<skill>/SKILL.md`` 가 존재하는 디렉터리.
홈 폴더는 평탄(flat) 구조이므로 ``~/.claude/skills/<skill>/`` 로 펼쳐 복사한다.

서버 세션 동안 한 번 점검(모두 설치 확인 or 설치 완료)되면 그 사실을 메모리에
기록(``_verified``)해, 같은 서버 프로세스 생애에서는 디스크 재스캔을 건너뛴다.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from api.platform.observability.smart_logger import SmartLogger

# 같은 서버 세션에서 한 번 모두 설치 확인/완료되면 True. 프로세스 재시작 시 초기화.
_verified = False


def _repo_root() -> Path:
    """``api/`` 와 ``skills/`` 가 함께 있는 디렉터리(저장소 루트)를 위로 걸어 찾는다."""
    here = Path(__file__).resolve()
    for parent in [here] + list(here.parents):
        if (parent / "api").is_dir() and (parent / "skills").is_dir():
            return parent
    # 폴백: 이 파일 기준 두 단계 위(api/platform/ → 저장소 루트).
    return here.parents[2]


def _global_skills_dir() -> Path:
    """``~/.claude/skills`` 절대 경로."""
    return Path.home() / ".claude" / "skills"


def _leaf_skills() -> list[Path]:
    """``skills/**/SKILL.md`` 를 가진 리프 스킬 디렉터리 목록."""
    skills_root = _repo_root() / "skills"
    if not skills_root.is_dir():
        return []
    return sorted(
        {sf.parent for sf in skills_root.rglob("SKILL.md")},
        key=lambda p: p.name,
    )


def status() -> dict:
    """홈 스킬 폴더 설치 상태를 반환한다.

    반환: ``{"verified": bool, "needInstall": bool, "missing": [name…], "total": int}``
    - ``verified``: 이 서버 세션에서 이미 모두 설치 확인/완료됨 → 프론트는 점검 생략.
    - ``needInstall``: 누락 스킬이 있어 설치 프롬프트가 필요함.
    """
    global _verified
    leaves = _leaf_skills()
    total = len(leaves)

    if _verified:
        return {"verified": True, "needInstall": False, "missing": [], "total": total}

    dest_root = _global_skills_dir()
    missing = [
        d.name for d in leaves if not (dest_root / d.name / "SKILL.md").is_file()
    ]

    if not missing:
        # 전부 설치돼 있음 → 이 세션에서는 더 점검하지 않는다.
        _verified = True
        return {"verified": True, "needInstall": False, "missing": [], "total": total}

    return {
        "verified": False,
        "needInstall": True,
        "missing": missing,
        "total": total,
    }


def install() -> dict:
    """리프 스킬을 ``~/.claude/skills/`` 에 평탄 구조로(덮어쓰기) 설치한다.

    반환: ``{"installed": [name…], "skipped": [], "total": int}``
    설치 후 세션 점검 플래그를 세워 재점검을 막는다.
    """
    global _verified
    leaves = _leaf_skills()
    dest_root = _global_skills_dir()
    dest_root.mkdir(parents=True, exist_ok=True)

    installed: list[str] = []
    for src in leaves:
        dest = dest_root / src.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        installed.append(src.name)

    _verified = True
    SmartLogger.log(
        "INFO",
        f"Installed {len(installed)} global skills into {dest_root}",
        category="platform.global_skills.install",
        params={"installed": installed},
    )
    return {"installed": installed, "skipped": [], "total": len(leaves)}
