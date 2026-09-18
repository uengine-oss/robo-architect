#!/usr/bin/env python3
"""설치본 런타임 디렉터리를 로컬에 만든다 — Electron 없이 스택을 재기 위해.

spec 058 T001. `robo.ps1 release` 가 Windows 에서 하는 일 중 **compose 입력을
만드는 부분만** 떼어 맥에서 재현한다. 이미지 빌드·tar·매니페스트는 T002 와
릴리스의 몫이다.

## 왜 저장소가 아니라 스크래치에 쓰나

`config/*.env` 에는 API 키가 들어간다. 저장소의 `desktop/runtime/config/*.env` 는
**git 추적 대상**(자리표시자가 커밋돼 있다)이라, 거기에 실제 값을 쓰면 다음 커밋에
비밀정보가 딸려 들어간다. 그래서 기본 출력은 저장소 바깥이고, 저장소 안을 가리키면
거부한다.

## 스코프 규칙은 우리가 정하지 않는다

어떤 키가 어느 서비스로 가는지는 `robo-workspace/release-environment.json` 이
정한다. 이 스크립트는 **그 파일을 읽어 그대로 적용**한다. 규칙을 여기 베껴 두면
릴리스와 갈라진다.

사용:
    python3 scripts/build_local_runtime.py --out /tmp/robo-runtime
    python3 scripts/build_local_runtime.py --out /tmp/robo-runtime --check
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SRC = REPO_ROOT / "desktop" / "runtime"
# robo-workspace 는 형제 디렉터리다. 없으면 --workspace 로 지정한다.
DEFAULT_WORKSPACE = REPO_ROOT.parent / "robo-workspace"

# architect 스코프는 컨테이너가 아니라 번들 앱이 읽는다 — 여기서는 안 만든다.
CONTAINER_SCOPES = ("analyzer", "catalog", "fabric", "parser", "gateway", "pdf2bpmn")


class BuildError(Exception):
    """만들지 못한 이유. 조용히 빈 디렉터리를 남기지 않는다."""


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def in_scope(name: str, scope: dict) -> bool:
    """release-environment.json 의 스코프 규칙. robo.ps1 의 Test-ReleaseEnvironmentScopeKey 와 같은 판정."""
    if name in scope.get("excludeNames", []):
        return False
    if name in scope.get("names", []):
        return True
    return any(name.startswith(prefix) for prefix in scope.get("prefixes", []))


def assert_outside_repo(out_dir: Path) -> None:
    """저장소 안에 비밀정보를 쓰지 못하게 막는다."""
    try:
        out_dir.resolve().relative_to(REPO_ROOT)
    except ValueError:
        return  # 저장소 바깥 — 정상
    raise BuildError(
        f"출력 경로가 저장소 안이다: {out_dir}\n"
        f"  config/*.env 에는 키가 들어간다. 저장소 밖(스크래치)을 지정해라."
    )


def build(out_dir: Path, workspace: Path, check_only: bool) -> int:
    assert_outside_repo(out_dir)

    compose_src = RUNTIME_SRC / "compose.yml"
    facade_src = RUNTIME_SRC / "pdf2bpmn" / "facade.py"
    contract_path = workspace / "release-environment.json"
    env_path = workspace / ".env"

    for required in (compose_src, facade_src, contract_path, env_path):
        if not required.exists():
            raise BuildError(f"필요한 입력이 없다: {required}")

    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    env = read_env_file(env_path)

    scopes = contract.get("scopes", {})
    missing = [name for name in CONTAINER_SCOPES if name not in scopes]
    if missing:
        raise BuildError(f"release-environment.json 에 스코프가 없다: {', '.join(missing)}")

    if check_only:
        print(f"입력 확인 — compose·facade·contract·env 전부 있음 ({workspace})")
        return 0

    (out_dir / "config").mkdir(parents=True, exist_ok=True)
    (out_dir / "pdf2bpmn").mkdir(parents=True, exist_ok=True)
    shutil.copy2(compose_src, out_dir / "compose.yml")
    shutil.copy2(facade_src, out_dir / "pdf2bpmn" / "facade.py")

    for name in CONTAINER_SCOPES:
        scope = scopes[name]
        picked = {k: v for k, v in env.items() if in_scope(k, scope)}
        target = out_dir / "config" / f"{name}.env"
        target.write_text(
            "".join(f"{k}={v}\n" for k, v in picked.items()), encoding="utf-8"
        )
        os.chmod(target, 0o600)  # 키가 들어 있다
        # **값은 찍지 않는다.** 개수만.
        print(f"  config/{name}.env  키 {len(picked)}개")

    print(f"\nruntime 디렉터리: {out_dir}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="출력 디렉터리 (저장소 바깥)")
    parser.add_argument(
        "--workspace",
        default=str(DEFAULT_WORKSPACE),
        help="robo-workspace 경로 (기본: 저장소의 형제 디렉터리)",
    )
    parser.add_argument(
        "--check", action="store_true", help="만들지 않고 입력만 확인한다"
    )
    args = parser.parse_args(argv)

    try:
        return build(Path(args.out), Path(args.workspace), args.check)
    except BuildError as exc:
        print(f"실패: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
