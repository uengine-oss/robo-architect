#!/usr/bin/env python3
"""§036 측정 하니스 — 골든 픽스처로 BPMN→룰 매핑을 실행하고 결과를 JSON으로 출력.

`HYBRID_GLOSSARY_NORMALIZE` env(0/1)로 정규화 off/on을 제어해 off→on A/B 측정에 쓴다.
매핑 결과는 영속된 `(BpmTask)-[:REALIZED_BY]->(Rule)`에서 읽는다(진실의 원천=그래프).

전제(라이브 환경): neo4j 구동 + analyzer 분석 그래프 적재(zapamcom*) + LLM 키.

사용:
  HYBRID_GLOSSARY_NORMALIZE=0 python3 run_mapping.py \
    --pdf /Users/seongwon/Desktop/robo/input_resource/...요청처리.pdf \
          /Users/seongwon/Desktop/robo/input_resource/...결과처리.pdf \
    --session-id golden036 --out /tmp/036_baseline.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path


def _read_persisted_mappings(session_id: str) -> dict[str, list[str]]:
    """session의 BpmTask→Rule REALIZED_BY 매핑을 {task_id: [rule_id,...]}로."""
    from api.features.ingestion.hybrid.ontology.schema import (
        L_BPM_TASK,
        L_RULE,
        R_REALIZED_BY,
    )
    from api.platform.neo4j import get_session

    out: dict[str, list[str]] = {}
    with get_session() as s:
        rows = s.run(
            f"MATCH (t:{L_BPM_TASK} {{session_id:$sid}})-[:{R_REALIZED_BY}]->(r:{L_RULE}) "
            f"RETURN t.id AS task_id, collect(r.id) AS rule_ids",
            sid=session_id,
        )
        for rec in rows:
            out[rec["task_id"]] = sorted(rec["rule_ids"])
    return out


async def _ingest(session_id: str, pdfs: list[str]) -> None:
    """BPM 추출 + 룰 + glossary 영속(ingestion). 매핑은 lazy라 여기선 안 함."""
    from api.features.ingestion.hybrid.hybrid_workflow_runner import run_hybrid_workflow
    from api.features.ingestion.requirements_document_text import extract_text_from_pdf

    content = "\n\n".join(
        f"=== {Path(p).name} ===\n{extract_text_from_pdf(Path(p).read_bytes())}" for p in pdfs
    )
    async for _ev in run_hybrid_workflow(session_id=session_id, content=content):
        pass


async def _explore_all(session_id: str) -> None:
    """실제 매핑 경로 — 모든 프로세스의 모든 task를 force 탐색(REALIZED_BY 재생성).

    정규화 on/off는 `HYBRID_GLOSSARY_NORMALIZE` env가 explore 내부 run_agentic_retrieval에
    적용된다. ingestion(BPM/glossary)은 고정한 채 이 단계만 off/on 비교하면 깨끗한 A/B.
    """
    from api.features.ingestion.hybrid.explore_service import explore_process
    from api.features.ingestion.hybrid.ontology.neo4j_ops import fetch_session_snapshot

    async def _sink(_ev):  # 이벤트는 버린다(영속만 필요)
        return None

    snap = fetch_session_snapshot(session_id)
    for p in snap.get("processes", []):
        await explore_process(session_id, p["id"], force=True, sink=_sink)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", nargs="*", default=[])
    ap.add_argument("--session-id", default="golden036")
    ap.add_argument("--out", required=True)
    ap.add_argument("--ingest", action="store_true",
                    help="explore 전에 PDF ingestion(BPM/glossary) 먼저 수행")
    args = ap.parse_args()

    # 앱과 동일하게 .env 로드(neo4j/LLM 키). env로 이미 설정돼 있으면 덮지 않음.
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    normalize_enabled = os.getenv("HYBRID_GLOSSARY_NORMALIZE", "1") != "0"

    if args.ingest:
        if not args.pdf:
            raise SystemExit("--ingest 에는 --pdf 가 필요합니다.")
        asyncio.run(_ingest(args.session_id, args.pdf))

    t0 = time.perf_counter()
    asyncio.run(_explore_all(args.session_id))   # ← 측정 대상은 매핑(explore)만
    wall = time.perf_counter() - t0

    mappings = _read_persisted_mappings(args.session_id)
    accepted = sum(len(v) for v in mappings.values())
    payload = {
        "normalize_enabled": normalize_enabled,
        "session_id": args.session_id,
        "wall_clock_s": round(wall, 3),
        "task_count": len(mappings),
        "accepted_count": accepted,            # 사용자 노출의 주된 항목(매핑된 룰 수)
        "near_miss_cap_per_task": 3,           # REJECT_VISIBLE_CAP — 정규화와 무관한 상수
        "mappings": mappings,                  # {task_id: [rule_id, ...]}
    }
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[036] wrote {args.out} — tasks={len(mappings)} accepted={accepted} "
          f"normalize={'on' if normalize_enabled else 'off'} wall={wall:.1f}s")


if __name__ == "__main__":
    main()
