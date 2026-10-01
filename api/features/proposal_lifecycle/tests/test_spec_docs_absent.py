# -*- coding: utf-8 -*-
"""납품 산출물에는 `specs/` 가 없다 — 그것을 결함처럼 보고하지 않는다 (2026-10-01).

## 무엇이 있었나

`execute_dual_merge` 는 Accept 끝에 `specs/proposal-changes.md` 에 한 줄을 붙인다.
그런데 굽기가 `app` 에 넣는 것은 다섯이다 — `api`·`skills`·`templates`·
`pyproject.toml`·`uv.lock`. **`specs/` 는 사내 설계 문서라 일부러 안 싣는다.**

그래서 설치본에서는 Accept 마다 `FileNotFoundError` 가 났고, 호출자가 그것을
WARN 으로 받아 로그에 쌓았다. 기능은 멀쩡한데 **설계대로 없는 것이 경고로 보였다.**

## 여기서 재는 것

  ① `specs/` 가 없으면 **예외 없이** 건너뛴다
  ② 건너뛴 사유가 로그에 남는다 (조용히 삼키지 않는다)
  ③ 있으면 종전대로 이력을 붙인다
"""

from __future__ import annotations

import pathlib

import pytest

from api.features.proposal_lifecycle.services import dual_merge


def _run(monkeypatch: pytest.MonkeyPatch, base: pathlib.Path) -> list[tuple]:
    """`parents[4]` 가 `base` 가 되도록 모듈 파일 위치를 흉내 낸다."""
    fake = base / "api" / "features" / "proposal_lifecycle" / "services" / "dual_merge.py"
    fake.parent.mkdir(parents=True, exist_ok=True)
    fake.write_text("", encoding="utf-8")
    monkeypatch.setattr(dual_merge, "__file__", str(fake))

    logged: list[tuple] = []
    monkeypatch.setattr(dual_merge.SmartLogger, "log",
                        lambda level, msg, **kw: logged.append((level, msg, kw)))
    dual_merge._update_spec_docs("P-1")
    return logged


def test_specs_가_없으면_예외_없이_건너뛴다(tmp_path, monkeypatch):
    logged = _run(monkeypatch, tmp_path)              # specs/ 를 안 만든다
    assert logged, "조용히 삼키면 왜 안 썼는지 알 길이 없다"
    level, msg, kw = logged[-1]
    assert level == "INFO", f"설계대로 없는 것을 {level} 로 보고한다"
    assert "specs" in msg
    assert kw["category"].endswith("spec_update_skip")


def test_specs_가_있으면_이력을_붙인다(tmp_path, monkeypatch):
    (tmp_path / "specs").mkdir()
    _run(monkeypatch, tmp_path)
    body = (tmp_path / "specs" / "proposal-changes.md").read_text(encoding="utf-8")
    assert "P-1" in body and "Accepted at" in body


def test_굽기가_specs_를_싣지_않는다():
    """이 검사의 전제다 — 싣게 되면 위의 동작을 다시 생각해야 한다."""
    ps1 = pathlib.Path("scripts/build-packaged-runtime.ps1")
    if not ps1.exists():
        pytest.skip("굽기 스크립트가 없는 환경")
    text = ps1.read_text(encoding="utf-8")
    assert "'specs'" not in text, "specs 를 싣기 시작했다 — 고객 PC 로 설계 문서가 나간다"
