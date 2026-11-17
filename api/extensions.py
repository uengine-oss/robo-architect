# -*- coding: utf-8 -*-
"""고객 확장이 붙는 **자리**(등록부) — 코어는 자리만 만들고, 고객 코드는 모른다.

통합 원칙(2026-11-17 · 단일 브랜치 통합 설계 §1·§3-2):

```
① 브랜치는 저장소마다 하나(main). 고객·판은 브랜치가 아니라 **빌드 입력**이다.
② 고객 차이는 세 곳에만 — 확장 코드(extensions/<고객>/) · 프로필(설정값) · 고객 데이터.
   코어에 `if posco` 를 쓰지 않는다. 코어는 이 등록부의 자리만 읽는다.
```

## 어떻게 붙나

`ROBO_CUSTOMER`(없으면 `default`)가 고른 **한 고객**의 `extensions/<고객>/backend`
패키지를 읽어 `register(app, registry)` 를 부른다. 이미지에는 그 고객 폴더만 들어가므로
(Dockerfile 의 `ARG CUSTOMER`), 다른 고객 코드는 코어와 같은 이미지에 실리지 않는다.
설치된 패키지로 붙이고 싶으면 entry point 그룹 `robo.extensions` 도 읽는다.

## 왜 고객 이름을 잘못 주면 멈추나

`ROBO_CUSTOMER=posco` 인데 폴더가 없으면 **기본 동작으로 조용히 뜬다** — 화면은 멀쩡하고
SSO·파일 이름·표준항목만 빠진 판이 현장에 나간다. 그래서 없는 고객은 기동에서 막는다.
"""

from __future__ import annotations

import importlib
import os
import re
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path
from typing import Any, Callable

__all__ = [
    "DEFAULT_CUSTOMER", "Registry", "customer", "registry", "load_extensions",
    "ExtensionError",
]

DEFAULT_CUSTOMER = "default"
ENTRY_POINT_GROUP = "robo.extensions"

# 저장소 뿌리 — api/ 의 부모. 이미지 안에서도 같은 모양(/app/api, /app/extensions).
_ROOT = Path(__file__).resolve().parent.parent
_EXTENSIONS_DIR = _ROOT / "extensions"
_NAME = re.compile(r"^[a-z][a-z0-9_]{0,31}$")


class ExtensionError(RuntimeError):
    """확장을 고르지 못했거나 읽다가 깨졌다 — 기동을 멈출 일이다."""


@dataclass
class Registry:
    """고객 확장이 채우는 자리들. **비어 있으면 코어 기본 동작**이다.

    자리마다 "누가 읽나" 를 적어 둔다 — 읽는 코드 없이 자리만 있으면 확장이 값을 넣어도
    아무 일도 일어나지 않는다(P5 에서 코어가 하나씩 읽기 시작한다).
    """

    # 인증 공급자 이름 → 만드는 함수. 예: posco 의 SWP SSO. (P5: auth 가 읽는다)
    auth_providers: dict[str, Callable[..., Any]] = field(default_factory=dict)
    # LLM 공급자 덮어쓰기(게이트웨이·기본 모델). (P5: platform/llm 이 읽는다)
    llm_overrides: dict[str, Any] = field(default_factory=dict)
    # 표준항목(데이터 사전) 공급자 이름 → 만드는 함수. (P5: standard_items 가 읽는다)
    standard_item_providers: dict[str, Callable[..., Any]] = field(default_factory=dict)
    # 산출물 정책 — 파일 이름 틀 · 허용 형식 · ECM 검사 같은 값. (P5: exportDocument 가 읽는다)
    deliverable_policies: dict[str, Any] = field(default_factory=dict)
    # 코드 템플릿 세트(고객 데이터). (P5: code_templates 가 읽는다)
    template_sets: list[dict[str, Any]] = field(default_factory=list)
    # 고객 전용 API — 등록하면 **여기서 바로** app 에 붙인다.
    routers: list[Any] = field(default_factory=list)
    # 프로필 기본값 — 환경변수가 **비었거나 없을 때만** 채운다(사람이 .env 에 넣은 값이 늘 이긴다).
    # 예: 포스코 SWP SSO 주소. 코어 코드에 고객 주소를 박지 않기 위한 자리다. (load_extensions 가 적용)
    env_defaults: dict[str, str] = field(default_factory=dict)


_registry = Registry()
_loaded: str | None = None


def customer() -> str:
    """지금 판의 고객 이름. 없으면 `default`."""
    raw = (os.environ.get("ROBO_CUSTOMER") or "").strip().lower()
    return raw or DEFAULT_CUSTOMER


def registry() -> Registry:
    """채워진 등록부. `load_extensions()` 전에는 빈 자리(= 기본 동작)다."""
    return _registry


def _module_for(name: str) -> str | None:
    """`extensions/<고객>/backend` 를 import 경로로. 폴더가 없으면 None.

    기본 고객의 폴더는 `_default` 다 — 고객 이름과 겹치지 않게 밑줄로 시작한다.
    """
    folder = "_default" if name == DEFAULT_CUSTOMER else name
    if not (_EXTENSIONS_DIR / folder / "backend" / "__init__.py").is_file():
        return None
    return f"extensions.{folder}.backend"


def load_extensions(app: Any | None = None) -> Registry:
    """고른 고객의 확장을 한 번 읽어 등록부를 채우고, 확장 라우터를 app 에 붙인다."""
    global _loaded, _registry
    name = customer()
    if _loaded is not None:
        if _loaded != name:
            raise ExtensionError(f"확장은 기동마다 한 고객만 — 이미 {_loaded!r} 를 읽었다")
        return _registry
    if not _NAME.match(name):
        raise ExtensionError(f"ROBO_CUSTOMER 모양이 틀렸다: {name!r}")

    reg = Registry()
    module = _module_for(name)
    if module is None and name != DEFAULT_CUSTOMER:
        raise ExtensionError(
            f"ROBO_CUSTOMER={name!r} 인데 extensions/{name}/backend 가 없다 — "
            "기본 동작으로 뜨면 고객 기능이 조용히 빠진다. 이미지·볼륨을 확인하라."
        )
    registrars: list[Callable[..., Any]] = []
    if module is not None:
        try:
            registrars.append(importlib.import_module(module).register)
        except Exception as exc:  # noqa: BLE001 — 어떤 깨짐이든 기동을 멈춘다
            raise ExtensionError(f"{module} 를 읽지 못했다: {exc}") from exc
    for ep in metadata.entry_points(group=ENTRY_POINT_GROUP):
        if ep.name == name:
            registrars.append(ep.load())

    for register in registrars:
        register(app, reg)
    for key, value in reg.env_defaults.items():
        if not (os.environ.get(key) or "").strip():
            os.environ[key] = value
    if app is not None:
        for router in reg.routers:
            app.include_router(router)

    _registry, _loaded = reg, name
    return reg


def _reset_for_tests() -> None:
    global _registry, _loaded
    _registry, _loaded = Registry(), None
