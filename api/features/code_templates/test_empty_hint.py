# -*- coding: utf-8 -*-
"""세트가 0개일 때의 안내는 **읽는 사람에 따라 달라야 한다** (2026-10-01).

## 무엇이 있었나

템플릿 기반 코드 생성이 납품본에서 세트 0개였다. 백엔드는 `<app>/templates` 를
읽는데 굽기가 그 디렉터리를 안 실었다(`build-packaged-runtime.ps1` 이 `api` ·
`skills` · `pyproject.toml` · `uv.lock` 넷만 넣었다).

빈손인 이유를 화면에 말해 주는 것 자체는 잘 돼 있었다. 다만 그 말이
*"scripts/fetch-templates.sh 를 실행해 템플릿을 받으세요"* 였다 — **납품받은
사람에게는 쓸모가 없다.** 사내망에는 GitHub 도 없고, 받는 쪽이 할 수 있는 일도
아니다. 그쪽에는 "덜 구워진 산출물" 이라고 말해야 전달이 된다.

## 여기서 재는 것

  ① 설치본이면 **이 PC 에서 할 수 없는 일**을 시키지 않는다
  ② 개발이면 종전대로 스크립트를 알려 준다
  ③ 표식이 없으면 개발로 본다 — 모르는 상태에서 "담당자에게 알리세요" 는 틀린 말이다
  ④ 세트가 있으면 안내를 아예 안 보낸다
"""

from __future__ import annotations

import pytest

from api.features.code_templates import router


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ROBO_PACKAGED_RUNTIME", raising=False)
    yield


def test_설치본이면_받는_사람이_할_수_있는_말을_한다(monkeypatch):
    monkeypatch.setenv("ROBO_PACKAGED_RUNTIME", "1")
    hint = router._empty_hint()
    assert "fetch-templates" not in hint, "사내망에서 못 하는 일을 시킨다"
    assert "설치본" in hint and "담당자" in hint, hint


def test_개발이면_스크립트를_알려_준다(monkeypatch):
    assert "fetch-templates.sh" in router._empty_hint()


def test_표식이_이상하면_개발로_본다(monkeypatch):
    for value in ("", "0", "false", "no", "weird"):
        monkeypatch.setenv("ROBO_PACKAGED_RUNTIME", value)
        assert "fetch-templates.sh" in router._empty_hint(), value
    for value in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("ROBO_PACKAGED_RUNTIME", value)
        assert "fetch-templates" not in router._empty_hint(), value


def test_세트가_있으면_안내를_안_보낸다(monkeypatch):
    monkeypatch.setattr(router.repository, "list_template_sets",
                        lambda: [{"name": "template-poscodx", "fileCount": 40}])
    import asyncio
    import inspect

    out = router.list_sets()
    if inspect.isawaitable(out):
        out = asyncio.run(out)
    assert out["hint"] is None
    assert out["sets"][0]["fileCount"] == 40


def test_표식을_굽기가_실제로_싣는다():
    """백엔드가 혼자 알 수 없다 — Electron 이 넘겨 줘야 한다."""
    import pathlib

    src = pathlib.Path("desktop/src/main/backend.ts")
    if not src.exists():          # 설치본 안에서는 desktop 소스가 없다
        pytest.skip("desktop 소스가 없는 환경")
    text = src.read_text(encoding="utf-8")
    assert "ROBO_PACKAGED_RUNTIME" in text, "표식을 넘기지 않는다 — 늘 개발로 보인다"


def test_굽기가_templates_를_싣는다():
    """안 실으면 기능이 있는 채로 **세트 0개**가 된다."""
    import pathlib

    ps1 = pathlib.Path("scripts/build-packaged-runtime.ps1")
    if not ps1.exists():
        pytest.skip("굽기 스크립트가 없는 환경")
    text = ps1.read_text(encoding="utf-8")
    assert "'templates'" in text, "templates 를 app 에 안 넣는다"
    assert "fetch-templates.sh" in text, "없을 때 무엇을 하라는 말이 없다"
