# -*- coding: utf-8 -*-
"""코드 생성 템플릿을 **DB 에서 고친다** (TPL-1).

## 왜 옮기나

템플릿은 지금까지 산출물 안의 파일이었다. 한 줄을 고치려면 **전체를 다시 구워
20여 대에 재설치**해야 한다 — 생성 결과가 마음에 안 들 때마다 그 비용이 든다.
DB 로 옮기면 중앙에서 한 번 고치고, PC 들은 다음 조회부터 새 템플릿을 쓴다.

## 파일을 지우지 않는다 — **원본이 있어야 되돌릴 수 있다**

```
파일   산출물에 그대로 둔다. **원본(출고 상태)**이고 기본값이다
DB     고친 것만 한 줄씩 쌓인다. 같은 경로가 있으면 **DB 가 이긴다**
되돌리기  DB 행을 지우면 원본으로 돌아온다 — 복사해 둘 필요가 없다
```

그래서 DB 가 비어 있으면 **지금까지와 똑같이** 동작한다. 중앙 DB 가 없는 단일 PC
구성에서도 마찬가지다 — 읽다 실패하면 파일로 간다(`overrides()` 는 예외를 안 올린다).

## 권한은 **앱이 본다** — Postgres 가 안 막는다

이 표는 `public.*` 이고 `pg.connection()` 은 **소유자 자격**으로 연다. 사용자 role 로
붙는 그래프 읽기와 달리 DB 가 격리를 걸어 주지 않는다. 그러므로 "관리자만 고친다"는
**라우터가** 지킨다(`accounts/guard.py`). 같은 함정을 적재 기록에도 적어 뒀다
(`ingestion/runs.py` 머리말).

## 고치는 것은 **코드를 고치는 것이다**

템플릿 본문 끝의 `<function>` 블록은 JavaScript 이고, 렌더러가 `new Function` 으로
**실제로 실행한다**(`frontend/.../renderer.js`). 즉 이 표에 글을 쓸 수 있는 사람은
앱 화면에서 코드를 돌릴 수 있다. 그래서 —

```
관리자만 쓴다     라우터가 저장된 역할을 다시 읽어서 판정한다
이력을 남긴다     누가·언제·무엇을 — 되돌릴 수 있어야 하고, 추적할 수 있어야 한다
기록을 남긴다     저장마다 WARN 로그. 조용한 변경은 없다
```
"""

from __future__ import annotations

import time
from typing import Any, Optional

from api.platform import pg
from api.platform.observability.smart_logger import SmartLogger

__all__ = [
    "ensure_schema", "overrides", "override_counts", "get", "save", "revert",
    "history", "history_body", "HISTORY_LIMIT", "UNAVAILABLE_BACKOFF_SECONDS",
]

# 한 경로에 남기는 이력 수. 되돌리기용 꼬리이지 영구 보관소가 아니다.
HISTORY_LIMIT = 50

_SCHEMA = """
CREATE TABLE IF NOT EXISTS public.app_code_templates (
    set_name      TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    body          TEXT NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by    TEXT,
    PRIMARY KEY (set_name, relative_path)
);
CREATE TABLE IF NOT EXISTS public.app_code_template_history (
    id            BIGSERIAL PRIMARY KEY,
    set_name      TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    body          TEXT,
    action        TEXT NOT NULL,
    saved_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    saved_by      TEXT
);
CREATE INDEX IF NOT EXISTS idx_code_template_history_path
    ON public.app_code_template_history (set_name, relative_path, saved_at DESC);
"""


# DB 가 안 붙을 때 **읽기 경로가 매번 기다리지 않게** 한다.
#
# 템플릿 목록은 화면이 열릴 때마다 부른다. 중앙 DB 가 꺼져 있으면 그때마다 접속
# 제한시간(5초)을 다시 먹는다 — 묶음마다, 호출마다. 한 번 실패하면 잠시 쉰다.
# 쓰기는 이 쉼을 쓰지 않는다 — 사람이 저장을 눌렀으면 **그 자리에서** 결과를 봐야 한다.
UNAVAILABLE_BACKOFF_SECONDS = 30.0

_schema_ready = False
_unavailable_until = 0.0


def _read_blocked() -> bool:
    return time.monotonic() < _unavailable_until


def _note_unavailable() -> None:
    global _unavailable_until, _schema_ready
    _unavailable_until = time.monotonic() + UNAVAILABLE_BACKOFF_SECONDS
    _schema_ready = False


def ensure_schema() -> None:
    """표를 만든다. **프로세스당 한 번**이면 된다 — 읽기마다 DDL 을 보내지 않는다."""
    global _schema_ready
    if _schema_ready:
        return
    with pg.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_SCHEMA)
    _schema_ready = True


def _warn(what: str, exc: Exception, **params: Any) -> None:
    """읽기 실패가 **코드 생성을 막지 않는다.** 다만 조용히 넘어가지 않는다."""
    SmartLogger.log(
        "WARN", f"템플릿 {what} 실패 (파일 원본으로 간다): {exc}",
        category="code_templates.store.error",
        params={"what": what, "error": str(exc), **params},
    )


def overrides(set_name: str) -> dict[str, dict[str, Any]]:
    """이 묶음에서 **고쳐진 것들**. 경로 → 행. 못 읽으면 빈 사전이다."""
    if not set_name or _read_blocked():
        return {}
    try:
        ensure_schema()
        rows = pg.query(
            "SELECT relative_path, body, updated_at, updated_by "
            "  FROM public.app_code_templates WHERE set_name = %s",
            (set_name,),
        )
    except Exception as exc:  # noqa: BLE001 — DB 가 없어도 템플릿은 돌아야 한다
        _note_unavailable()
        _warn("조회", exc, set=set_name)
        return {}
    return {r["relative_path"]: r for r in rows}


def override_counts() -> dict[str, int]:
    """묶음별로 **몇 장이 고쳐졌는가**. 질의 한 번으로 끝낸다.

    묶음마다 따로 물으면 접속이 묶음 수만큼 열린다 — 목록 화면 한 번에 그 비용을
    치를 이유가 없다.
    """
    if _read_blocked():
        return {}
    try:
        ensure_schema()
        rows = pg.query(
            "SELECT set_name, count(*) AS n FROM public.app_code_templates GROUP BY set_name"
        )
    except Exception as exc:  # noqa: BLE001
        _note_unavailable()
        _warn("묶음별 수 조회", exc)
        return {}
    return {r["set_name"]: int(r["n"]) for r in rows}


def get(set_name: str, relative_path: str) -> Optional[dict[str, Any]]:
    """고쳐진 한 장. 없으면 `None`(= 원본을 쓴다)."""
    if _read_blocked():
        return None
    try:
        ensure_schema()
        rows = pg.query(
            "SELECT relative_path, body, updated_at, updated_by "
            "  FROM public.app_code_templates WHERE set_name = %s AND relative_path = %s",
            (set_name, relative_path),
        )
    except Exception as exc:  # noqa: BLE001
        _note_unavailable()
        _warn("조회", exc, set=set_name, path=relative_path)
        return None
    return rows[0] if rows else None


def save(set_name: str, relative_path: str, body: str, uid: str) -> dict[str, Any]:
    """고친 내용을 쓴다. **이력을 먼저 남긴다** — 쓰다 실패해도 앞판이 남게.

    실패하면 예외를 올린다. 읽기와 달리 **저장은 조용히 실패하면 안 된다** —
    사람이 고쳤다고 믿는데 안 고쳐져 있는 것이 가장 나쁘다. 읽기의 쉼(backoff)도
    쓰지 않는다.
    """
    global _unavailable_until
    _unavailable_until = 0.0
    ensure_schema()
    with pg.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO public.app_code_template_history "
                "(set_name, relative_path, body, action, saved_by) "
                "VALUES (%s, %s, %s, 'save', %s)",
                (set_name, relative_path, body, uid or None),
            )
            cur.execute(
                "INSERT INTO public.app_code_templates "
                "(set_name, relative_path, body, updated_at, updated_by) "
                "VALUES (%s, %s, %s, now(), %s) "
                "ON CONFLICT (set_name, relative_path) DO UPDATE "
                "SET body = EXCLUDED.body, updated_at = now(), updated_by = EXCLUDED.updated_by",
                (set_name, relative_path, body, uid or None),
            )
            cur.execute(
                "DELETE FROM public.app_code_template_history WHERE id IN ("
                " SELECT id FROM public.app_code_template_history"
                "  WHERE set_name = %s AND relative_path = %s"
                "  ORDER BY saved_at DESC OFFSET %s)",
                (set_name, relative_path, HISTORY_LIMIT),
            )
    SmartLogger.log(
        "WARN", "코드 생성 템플릿이 수정됐다",
        category="code_templates.store.saved",
        params={"set": set_name, "path": relative_path, "uid": uid,
                "bytes": len(body or ""), "has_function": "<function>" in (body or "")},
    )
    return {"set": set_name, "path": relative_path, "bytes": len(body or "")}


def revert(set_name: str, relative_path: str, uid: str) -> bool:
    """수정본을 버리고 **원본(산출물 파일)으로 되돌린다.**

    돌려주는 값은 "되돌릴 것이 있었는가" 다. 없으면 `False` — 이미 원본이다.
    """
    global _unavailable_until
    _unavailable_until = 0.0
    ensure_schema()
    with pg.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM public.app_code_templates "
                " WHERE set_name = %s AND relative_path = %s",
                (set_name, relative_path),
            )
            removed = cur.rowcount > 0
            if removed:
                # 되돌린 사실도 이력이다. 본문은 안 남긴다 — 직전 save 가 들고 있다.
                cur.execute(
                    "INSERT INTO public.app_code_template_history "
                    "(set_name, relative_path, body, action, saved_by) "
                    "VALUES (%s, %s, NULL, 'revert', %s)",
                    (set_name, relative_path, uid or None),
                )
    if removed:
        SmartLogger.log(
            "WARN", "코드 생성 템플릿을 원본으로 되돌렸다",
            category="code_templates.store.reverted",
            params={"set": set_name, "path": relative_path, "uid": uid},
        )
    return removed


def history(set_name: str, relative_path: str) -> list[dict[str, Any]]:
    """이 한 장의 이력. 본문은 빼고 준다 — 목록이 무거워진다."""
    if _read_blocked():
        return []
    try:
        ensure_schema()
        rows = pg.query(
            "SELECT id, action, saved_at, saved_by, length(body) AS bytes"
            "  FROM public.app_code_template_history"
            " WHERE set_name = %s AND relative_path = %s"
            " ORDER BY saved_at DESC",
            (set_name, relative_path),
        )
    except Exception as exc:  # noqa: BLE001
        _warn("이력 조회", exc, set=set_name, path=relative_path)
        return []
    return [
        {
            "id": int(r["id"]),
            "action": r["action"],
            "savedAt": r["saved_at"].isoformat() if r.get("saved_at") else None,
            "savedBy": r.get("saved_by"),
            "bytes": int(r["bytes"] or 0),
        }
        for r in rows
    ]


def history_body(set_name: str, relative_path: str, version_id: int) -> Optional[str]:
    """이력 한 판의 본문. 경로까지 **함께 걸러** 남의 판을 못 읽게 한다."""
    try:
        rows = pg.query(
            "SELECT body FROM public.app_code_template_history"
            " WHERE id = %s AND set_name = %s AND relative_path = %s",
            (version_id, set_name, relative_path),
        )
    except Exception as exc:  # noqa: BLE001
        _warn("이력 본문 조회", exc, set=set_name, path=relative_path)
        return None
    return rows[0]["body"] if rows else None
