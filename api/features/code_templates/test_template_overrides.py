# -*- coding: utf-8 -*-
"""템플릿을 **DB 에서 고친다** — 겹쳐 읽기와 권한 (TPL-1).

## 왜 이 검사가 있나

템플릿은 산출물의 파일이었다. 한 줄을 고치려면 전체를 다시 구워 20여 대에
재설치해야 했다. 이제 고친 것은 중앙 DB 에 쌓이고 **같은 경로는 DB 가 이긴다.**

그 설계가 성립하려면 셋이 지켜져야 한다 —

```
① 겹치기   DB 가 이기되, 없는 것은 **원본 그대로** 간다 (DB 가 비면 지금까지와 같다)
② 되돌리기  원본은 산출물에 그대로 있다 — 복사본이 아니라 **DB 행을 지우면** 돌아온다
③ 권한     `<function>` 블록은 렌더러가 `new Function` 으로 **실행한다**.
           즉 쓰기 권한 = 코드 실행 권한. 관리자만이어야 한다
```
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException

from api.features.code_templates import repository, router


def _set(tmp_path: Path, name: str = "set-a") -> Path:
    root = tmp_path / "templates" / name
    (root / "sub").mkdir(parents=True)
    (root / "A.java").write_text(
        "forEach: Aggregate\npath: p\nfileName: {{name}}.java\n---\nclass A {}\n",
        encoding="utf-8",
    )
    (root / "sub" / "B.java").write_text(
        "forEach: BoundedContext\npath: q\n---\nclass B {}\n", encoding="utf-8",
    )
    return root


@pytest.fixture
def templates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = _set(tmp_path)
    monkeypatch.setattr(repository, "TEMPLATES_ROOT", tmp_path / "templates")
    return root


# ── ① 겹치기 ──────────────────────────────────────────────────────────────

def test_덮어쓰지_않은_것은_원본_그대로다(templates: Path):
    files = {t.relative_path: t for t in repository.load_templates("set-a")}
    assert set(files) == {"A.java", "sub/B.java"}
    assert all(t.source == "file" for t in files.values())
    assert files["A.java"].body == "class A {}\n"


def test_같은_경로는_DB_가_이긴다(templates: Path):
    over = {"A.java": {"body": "forEach: Aggregate\npath: p\n---\nclass FIXED {}\n",
                       "updated_at": None, "updated_by": "admin1"}}
    files = {t.relative_path: t for t in repository.load_templates("set-a", over)}
    assert files["A.java"].body == "class FIXED {}\n"
    assert files["A.java"].source == "db"
    assert files["A.java"].updated_by == "admin1"
    # 손대지 않은 것은 그대로다 — 한 장을 고쳤다고 묶음이 통째로 DB 가 되지 않는다.
    assert files["sub/B.java"].source == "file"


def test_DB_에만_있는_템플릿도_실린다(templates: Path):
    over = {"C.java": {"body": "forEach: Aggregate\npath: r\n---\nclass C {}\n",
                       "updated_at": None, "updated_by": None}}
    files = [t.relative_path for t in repository.load_templates("set-a", over)]
    assert "C.java" in files and len(files) == 3


def test_옵션_폼도_고친_설정을_본다(templates: Path):
    """설정 파일을 고쳤는데 입력 폼만 옛것이면, 고친 보람이 없다."""
    cfg = ("---\n<text-field :value.sync=\"value.serviceId\" label=\"서비스 ID\">"
           "</text-field>\n")
    over = {"_template/configuration.html": {
        "body": cfg, "updated_at": None, "updated_by": None}}
    keys = [f["key"] for f in repository.config_fields_for("set-a", over)]
    assert keys == ["serviceId"]


def test_상대경로는_늘_슬래시다(templates):
    """윈도우의 `a\b` 가 그대로 나가면 화면이 **폴더를 못 만든다**(37장이 한 줄로
    쏟아진다). DB 기본키와 URL 질의값이기도 해서 경계를 넘기 전에 고른다."""
    paths = [t.relative_path for t in repository.load_templates("set-a")]
    assert "sub/B.java" in paths
    assert not any("\\" in p for p in paths)


def test_옛_백슬래시_경로도_같은_파일을_가리킨다(templates):
    assert repository.read_original("set-a", r"sub\B.java") is not None


# ── ② 원본 ────────────────────────────────────────────────────────────────

def test_원본은_산출물에서_그대로_읽는다(templates: Path):
    text = repository.read_original("set-a", "A.java")
    assert text is not None and text.endswith("class A {}\n")


def test_DB_에만_있는_것은_원본이_없다(templates: Path):
    assert repository.read_original("set-a", "C.java") is None


@pytest.mark.parametrize("path", ["../outside.txt", "sub/../../escape.java"])
def test_묶음_밖_경로는_거부한다(templates: Path, path: str):
    """경로는 사용자 입력이다. `..` 로 템플릿 밖을 읽게 두면 안 된다."""
    with pytest.raises(ValueError):
        repository.read_original("set-a", path)


# ── ③ 권한 ────────────────────────────────────────────────────────────────

class _Spy:
    def __init__(self) -> None:
        self.saved: list[tuple] = []
        self.reverted: list[tuple] = []

    def save(self, set_name, path, body, uid, *, original=None):
        self.saved.append((set_name, path, body, uid, original))
        return {"set": set_name, "path": path, "bytes": len(body)}

    def revert(self, set_name, path, uid):
        self.reverted.append((set_name, path, uid))
        return True


@pytest.fixture
def spy(monkeypatch: pytest.MonkeyPatch) -> _Spy:
    s = _Spy()
    monkeypatch.setattr(router.store, "save", s.save)
    monkeypatch.setattr(router.store, "revert", s.revert)
    return s


def _run(coro):
    """라우트는 코루틴이다. 플러그인 없이 그 자리에서 돌린다."""
    return asyncio.run(coro)


def _deny(_request):
    raise HTTPException(status_code=403, detail="관리자만 할 수 있습니다.")


def test_관리자가_아니면_저장이_막힌다(templates: Path, spy: _Spy,
                                             monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(router, "require_admin", _deny)
    with pytest.raises(HTTPException) as e:
        _run(router.save_file(None, "set-a", path="A.java", body="x"))
    assert e.value.status_code == 403
    # **권한을 보기 전에 쓰지 않는다.** 막혔는데 저장되는 것이 최악이다.
    assert spy.saved == []


def test_관리자가_아니면_되돌리기도_막힌다(templates: Path, spy: _Spy,
                                                 monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(router, "require_admin", _deny)
    with pytest.raises(HTTPException) as e:
        _run(router.revert_file(None, "set-a", path="A.java"))
    assert e.value.status_code == 403
    assert spy.reverted == []


def test_관리자는_저장할_수_있다(templates: Path, spy: _Spy,
                                        monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(router, "require_admin", lambda _r: "ADMIN-1")
    out = _run(router.save_file(None, "set-a", path="A.java", body="class EDITED {}\n"))
    assert out["saved"] is True
    assert spy.saved[0][:2] == ("set-a", "A.java")
    assert spy.saved[0][3] == "ADMIN-1"


def test_빈_템플릿은_저장하지_않는다(templates: Path, spy: _Spy,
                                           monkeypatch: pytest.MonkeyPatch):
    """실수로 전체를 지우고 저장하면 생성이 조용히 비어 버린다."""
    monkeypatch.setattr(router, "require_admin", lambda _r: "ADMIN-1")
    with pytest.raises(HTTPException) as e:
        _run(router.save_file(None, "set-a", path="A.java", body="   \n"))
    assert e.value.status_code == 400
    assert spy.saved == []


def test_묶음_밖_경로는_저장도_거부한다(templates: Path, spy: _Spy,
                                               monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(router, "require_admin", lambda _r: "ADMIN-1")
    with pytest.raises(HTTPException) as e:
        _run(router.save_file(None, "set-a", path="../escape.java", body="x"))
    assert e.value.status_code == 400
    assert spy.saved == []
