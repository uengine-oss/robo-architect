"""인제스천 이전 판을 보관한다.

**인제스천은 이미 교체다.** 표준 경로는 `clear_event_storming_nodes`, 하이브리드는
Phase 1 의 `clear_all_hybrid_workspace` 가 그 graph 의 생성물을 통째로 지우고
시작한다. 프로젝트가 graph 하나라서 그 범위는 정확히 프로젝트 하나다 — 남의
프로젝트는 안 건드린다.

문제는 지우는 것이 아니라 **지운 판이 사라진다**는 것이다. 두 번째 인제스천을
하면 첫 판을 되찾을 방법이 없고, 무엇이 없어지는지 묻지도 않는다.

여기서는 그 한 가지만 한다 — 지우기 직전에 현재 판을 조립해 Postgres 에 쌓는다.

```
왜 그래프가 아니라 Postgres 인가
    스냅샷을 같은 graph 에 두면 다음 wipe 가 그것까지 지운다. 라벨을 피해
    숨기는 방법도 있지만, 읽기 682곳이 세션을 안 보므로 언젠가 화면에 샌다.

왜 산출물 조립기를 재사용하는가
    `build_architecture_document` 는 이미 세션 단위로 고정된 스냅샷을 만든다.
    검증된 조립기가 하나 있는데 두 번째를 만들면 둘이 어긋난다.
```
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

from api.platform import pg
from api.platform.observability.smart_logger import SmartLogger

__all__ = [
    "ensure_schema", "save", "list_snapshots", "get", "delete", "prune",
    "RETENTION",
]

# 프로젝트당 남기는 판 수. 넘치면 오래된 것부터 지운다.
RETENTION = 10

_SCHEMA = """
CREATE TABLE IF NOT EXISTS public.project_snapshots (
    graph        TEXT NOT NULL,
    snapshot_key TEXT NOT NULL,
    value        JSONB NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (graph, snapshot_key)
);
CREATE INDEX IF NOT EXISTS idx_project_snapshots_graph
    ON public.project_snapshots (graph, created_at DESC);
"""


def ensure_schema() -> None:
    with pg.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_SCHEMA)


def _key(session_id: str) -> str:
    """`<세션>-<찍은 시각>-<난수>`. 같은 세션을 두 번 보관해도 덮지 않는다.

    난수를 붙이는 이유는 시각만으로는 같은 초 안의 두 보관이 같은 키가 되어
    **앞판을 조용히 덮기** 때문이다. 검사가 실제로 그렇게 잡았다.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{session_id}-{stamp}-{secrets.token_hex(2)}"


def save(graph: str, session_id: str, document: dict[str, Any],
         *, reason: str = "replaced", counts: Optional[dict[str, int]] = None) -> dict[str, Any]:
    """한 판을 통째로 보관한다.

    목록에 쓰이는 값은 `meta` 에 따로 둔다 — 본문이 수 MB 라 목록을 뽑을 때마다
    전부 읽으면 화면이 느려진다. 목록 질의는 `value->'meta'` 만 본다.
    """
    ensure_schema()
    key = _key(session_id)
    contexts = ((document.get("eventStorming") or {}).get("contexts")) or []
    meta = {
        "snapshotKey": key,
        "sessionId": session_id,
        "name": (document.get("projectInfo") or {}).get("projectName") or session_id,
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "boundedContexts": len(document.get("boundedContexts") or []),
        "contexts": len(contexts),
        "nodeCounts": counts or {},
    }
    payload = {"meta": meta, "document": document}
    with pg.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO public.project_snapshots (graph, snapshot_key, value) "
                "VALUES (%s, %s, %s::jsonb) "
                "ON CONFLICT (graph, snapshot_key) DO UPDATE SET value = EXCLUDED.value",
                (graph, key, json.dumps(payload, ensure_ascii=False, default=str)),
            )
    SmartLogger.log(
        "INFO", f"이전 판을 보관했다: {key}",
        category="projects.snapshot.saved",
        params={"graph": graph, "key": key, "reason": reason,
                "boundedContexts": meta["boundedContexts"]},
    )
    prune(graph)
    return meta


def list_snapshots(graph: str) -> list[dict[str, Any]]:
    """본문 없이 목록만. 최신이 앞이다."""
    ensure_schema()
    rows = pg.query(
        "SELECT snapshot_key, value->'meta' AS meta, created_at "
        "FROM public.project_snapshots WHERE graph = %s ORDER BY created_at DESC",
        (graph,),
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        meta = dict(row.get("meta") or {})
        meta.setdefault("snapshotKey", row["snapshot_key"])
        meta["createdAt"] = row["created_at"].isoformat() if row.get("created_at") else None
        out.append(meta)
    return out


def get(graph: str, snapshot_key: str) -> Optional[dict[str, Any]]:
    """보관된 산출물 본문. 없으면 None."""
    ensure_schema()
    rows = pg.query(
        "SELECT value FROM public.project_snapshots WHERE graph = %s AND snapshot_key = %s",
        (graph, snapshot_key),
    )
    if not rows:
        return None
    return (rows[0].get("value") or {}).get("document")


def delete(graph: str, snapshot_key: str) -> bool:
    ensure_schema()
    return pg.execute(
        "DELETE FROM public.project_snapshots WHERE graph = %s AND snapshot_key = %s",
        (graph, snapshot_key),
    ) > 0


def prune(graph: str, keep: int = RETENTION) -> int:
    """넘치는 옛 판을 지운다. 무한히 쌓이면 저장소가 커지기만 한다."""
    return pg.execute(
        "DELETE FROM public.project_snapshots WHERE graph = %s AND snapshot_key NOT IN ("
        "  SELECT snapshot_key FROM public.project_snapshots WHERE graph = %s"
        "  ORDER BY created_at DESC LIMIT %s)",
        (graph, graph, keep),
    )
