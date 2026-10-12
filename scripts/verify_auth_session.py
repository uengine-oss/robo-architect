"""중앙 인증 HTTP 검사는 격리 DB에서만 실행한다."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    if not os.environ.get("AUTH_TEST_PG_DSN"):
        print("Run scripts/test_account_authority.ps1 (isolated PostgreSQL required).", file=sys.stderr)
        return 1
    root = Path(__file__).resolve().parents[1]
    return subprocess.call([sys.executable, "-m", "pytest", "api/features/accounts/test_authority.py",
                            "api/features/accounts/test_authority_transport.py", "-q"], cwd=root)


if __name__ == "__main__":
    raise SystemExit(main())
