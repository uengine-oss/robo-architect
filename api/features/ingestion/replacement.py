"""인제스천을 다시 하기 전에 — 무엇이 사라지는지 보여주고, 현재 판을 보관한다.

인제스천은 이미 **교체**다. 표준 경로는 `clear_event_storming_nodes`, 하이브리드는
Phase 1 의 `clear_all_hybrid_workspace` 가 이 graph 의 생성물을 통째로 지우고
시작한다. 프로젝트가 graph 하나이므로 그 범위는 프로젝트 하나로 정확히 맞는다.

빠져 있던 것은 둘이다.

```
보관   지운 판을 되찾을 방법이 없었다      → 지우기 직전에 산출물로 조립해 둔다
고지   무엇이 없어지는지 묻지 않았다       → 미리 세어 보여준다
```

**조용히 실패하지 않게 하는 것이 이 파일의 목적이다.** 보관에 실패해도 인제스천은
막지 않는다 — 사용자가 시작한 작업을 부수효과가 세우면 그것대로 나쁘다. 대신
WARN 을 남기고, 화면이 미리 확인을 받는다.
"""

from __future__ import annotations

from typing import Any, Optional

from api.platform.neo4j import design_database, get_session
from api.platform.observability.smart_logger import SmartLogger

__all__ = ["live_sessions", "preview", "safe_counts", "capture_before_replace",
           "require_replace_ack", "PRESERVED_LABELS"]

# `clear-all` 이 지키는 것과 같은 목록. 인제스천 교체도 같은 것을 남긴다 —
# Figma 연결은 설계가 바뀌어도 살아 있어야 한다(다시 잇는 비용이 크다).
PRESERVED_LABELS = ("FigmaBinding", "StoryboardPageMapping", "BindingHistoryEvent",
                    "FigmaComponent")


def _wiped_labels() -> tuple[list[str], list[str]]:
    """지워지는 라벨 두 벌. **소유 모듈에서 그때그때 가져온다.**

    여기에 베껴 두면 저쪽이 라벨을 하나 늘렸을 때 이 화면만 조용히 옛 목록을
    보여준다 — 사용자는 안 지워진다고 읽고 실제로는 지워진다. 임포트를 함수
    안에 두는 것은 순환을 피하기 위해서다(러너가 이 모듈을 부른다).
    """
    from api.features.ingestion.ingestion_workflow_runner import _ES_LABELS
    from api.features.ingestion.hybrid.ontology.schema import ALL_HYBRID_LABELS
    return list(_ES_LABELS), list(ALL_HYBRID_LABELS)


def live_sessions() -> list[str]:
    """지금 살아 있는 판의 세션 id.

    `BpmSession` 이 아니라 **`BoundedContext` 를 기준으로 잡는다.** 문서 업로드가
    하이브리드를 거치지 않으면 `BpmSession` 노드가 아예 없어, 그걸 기준으로 하면
    표준 경로로 만든 판이 스냅샷에서 통째로 빠진다.
    """
    with get_session() as s:
        rows = s.run(
            "MATCH (bc:BoundedContext) WHERE bc.session_id IS NOT NULL "
            "RETURN DISTINCT bc.session_id AS sid"
        ).data()
    return [r["sid"] for r in rows if r.get("sid")]


def preview() -> dict[str, Any]:
    """다시 인제스천하면 무엇이 사라지는가.

    라벨별 건수와 살아 있는 세션을 함께 돌려준다. 건수가 0 이면 화면은 확인을
    묻지 않아도 된다 — 첫 인제스천이다.
    """
    es_labels, hybrid_labels = _wiped_labels()
    counts: dict[str, int] = {}
    with get_session() as s:
        for label in es_labels:
            rec = s.run(f"MATCH (n:{label}) RETURN count(n) AS c").single()
            if rec and rec["c"]:
                counts[label] = rec["c"]
        for label in hybrid_labels:
            rec = s.run(
                f"MATCH (n:{label}) WHERE n.session_id IS NOT NULL RETURN count(n) AS c"
            ).single()
            if rec and rec["c"]:
                counts[label] = counts.get(label, 0) + rec["c"]
    return {
        "graph": design_database(),
        "sessions": live_sessions(),
        "counts": counts,
        "total": sum(counts.values()),
        "preserved": list(PRESERVED_LABELS),
    }


def require_replace_ack(acknowledged: bool) -> Optional[dict[str, Any]]:
    """지울 것이 있으면 **확인을 받았는지** 본다. 받았으면 미리보기를 돌려준다.

    ## 왜 서버에도 두나

    화면은 이미 묻는다(`RequirementsIngestionModal.handleStartClick` 이
    `/replacement-preview` 를 읽고 확인 대화상자를 띄운다). 그런데 **그 문을 지나지
    않는 길이 있었다** — 업로드 엔드포인트를 직접 부르면 아무것도 묻지 않고
    **지우기부터 시작한다.**

    그리고 이 지우기는 `MATCH (n:Label) DETACH DELETE n` 이다 — WHERE 절이 없고,
    "그 프로젝트만" 이 되는 이유는 **연결이 그 graph 에 묶여 있기 때문**이다.
    즉 범위를 좁히는 것은 쿼리가 아니라 바인딩이고, 공유받은 사람이 재적재하면
    **소유자의 BPM·ES 가 그대로 사라진다.** 되돌릴 길은 지우기 직전의 스냅샷뿐이다.

    그만한 일을 **묻지 않고** 시작하지 않는다.

    ## 돌려주는 값

    `None` 이면 지울 것이 없다(첫 적재). dict 이면 그 판을 지우기로 **확인받았다** —
    부르는 쪽이 그대로 로그에 실어 두면 "무엇을 지우겠다고 했는지" 가 남는다.

    확인이 없으면 409 다. 400 이 아닌 이유는 **요청이 틀린 것이 아니라 상태가
    충돌하는 것**이기 때문이고, 화면이 그 둘을 다르게 다룬다.
    """
    from fastapi import HTTPException

    try:
        data = preview()
    except Exception as exc:  # noqa: BLE001 — 세기 실패가 적재를 막지 않는다
        # 여기서 막으면 **멀쩡한 첫 적재까지** 못 하게 된다. 세지 못한 것은
        # "지울 것이 있다" 의 근거가 아니다. 다만 조용히 넘어가지는 않는다.
        SmartLogger.log(
            "WARN", f"교체 확인용 건수를 세지 못했다 (적재는 계속한다): {exc}",
            category="ingestion.replace.ack.count_error", params={"error": str(exc)},
        )
        return None

    total = int(data.get("total") or 0)
    if total <= 0:
        return None  # 첫 적재 — 확인을 묻지 않는다(확인만 늘리면 사람은 읽지 않는다)
    if acknowledged:
        return data
    raise HTTPException(
        status_code=409,
        detail={
            "code": "INGEST_REPLACE_CONFIRM",
            "message": (
                f"이 프로젝트에 이미 만들어 둔 것이 {total}개 있습니다. 다시 적재하면 "
                "먼저 지워집니다 — 계속하려면 확인 뒤 `replaceAck=1` 로 다시 보내세요."
            ),
            **{k: data.get(k) for k in ("graph", "counts", "total", "sessions", "preserved")},
        },
    )


def safe_counts() -> dict[str, int]:
    """지워질 것들의 라벨별 건수. **세다가 실패해도 적재를 세우지 않는다.**

    이 값은 "무엇이 없어졌는지" 를 말하는 근거다(`ingestion/runs.py` 가 적재 기록에
    박아 둔다). 지운 뒤에는 셀 수 없으니 **지우기 전에** 한 번 센다. 세지 못하는
    것은 적재를 막을 이유가 아니다 — 경고가 조금 덜 친절해질 뿐이다.
    """
    try:
        return {k: int(v) for k, v in (preview().get("counts") or {}).items()}
    except Exception as exc:  # noqa: BLE001 — 세기 실패가 적재를 막지 않는다
        SmartLogger.log(
            "WARN", f"지워질 건수를 세지 못했다 (적재는 계속한다): {exc}",
            category="ingestion.replace.count.error", params={"error": str(exc)},
        )
        return {}


def capture_before_replace(reason: str = "replaced", *,
                           counts: Optional[dict[str, int]] = None) -> list[dict[str, Any]]:
    """지우기 직전에 현재 판을 보관한다. 보관한 판들의 meta 를 돌려준다.

    실패해도 예외를 올리지 않는다 — 인제스천은 사용자가 시작한 일이고, 보관은
    곁다리다. 다만 **조용히 넘어가지는 않는다.**
    """
    try:
        graph = design_database()
        if not graph:
            return []

        # 늦은 임포트 — 산출물 조립기가 무겁고, 스냅샷 없는 첫 인제스천에서는
        # 부를 일이 없다.
        from api.features.deliverables.architecture_document import build_architecture_document
        from api.features.projects import snapshots

        sessions = live_sessions()
        if not sessions:
            SmartLogger.log(
                "INFO", "보관할 이전 판이 없다 (첫 인제스천)",
                category="ingestion.replace.snapshot.skip", params={"graph": graph},
            )
            return []

        # 부르는 쪽이 이미 세 두었으면 다시 세지 않는다 — 라벨마다 질의가 한 번씩 간다.
        counts = counts if counts is not None else safe_counts()
        saved: list[dict[str, Any]] = []
        for sid in sessions:
            document = build_architecture_document(sid)
            if not document:
                continue
            saved.append(snapshots.save(graph, sid, document, reason=reason, counts=counts))
        return saved
    except Exception as exc:  # noqa: BLE001 — 보관 실패가 인제스천을 막지 않는다
        SmartLogger.log(
            "WARN",
            f"이전 판 보관 실패 (인제스천은 계속한다): {exc}",
            category="ingestion.replace.snapshot.error",
            params={"error": str(exc), "reason": reason},
        )
        return []
