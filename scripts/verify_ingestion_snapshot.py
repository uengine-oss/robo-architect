"""인제스천 교체와 스냅샷 검사 (ENT-ING-002).

**실데이터를 절대 태우지 않는다.** 임시 graph 를 하나 만들어 그 안에서만 돌고,
끝나면 지운다. 보호 목록에 든 graph 를 만나면 그 자리에서 멈춘다 — 이 저장소는
분석기를 설계 graph 에 겨눠 422건을 날린 적이 있다.

무엇을 재는가.

```
스냅샷 저장소   저장·목록·본문·삭제·보존 한도. 프로젝트끼리 안 섞이는지
살아 있는 판    BpmSession 이 아니라 BoundedContext 로 잡는다
                (표준 경로에는 BpmSession 이 없어서다)
미리보기        지워질 라벨 건수를 실제로 세는지 · 보존 라벨을 안 세는지
                라벨 목록을 소유 모듈에서 가져오는지 (베껴 두면 조용히 어긋난다)
보관            지우기 직전에 현재 판이 산출물로 조립돼 들어가는지
                보관이 실패해도 인제스천을 막지 않는지
```
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from neo4j import GraphDatabase  # noqa: E402

from api.features.ingestion import replacement  # noqa: E402
from api.features.projects import snapshots  # noqa: E402
from api.platform import pg  # noqa: E402
from api.platform.neo4j_context import Neo4jOverride, set_override  # noqa: E402

BOLT = os.environ.get("NEO4J_URI", "bolt://localhost:28687")
USER = os.environ.get("NEO4J_USER", "dev")
PASSWORD = os.environ.get("NEO4J_PASSWORD", "")

# 손대면 안 되는 graph. 임시 이름이 이 중 하나로 계산되면 즉시 멈춘다.
PROTECTED = {"robo", "analyzer_run", "analyzer", "neo4j"}

TMP = "zz_snap_probe"
TMP2 = "zz_snap_probe2"

_fails: list[str] = []
_passes = 0


def check(label: str, got, want) -> None:
    global _passes
    if got == want:
        _passes += 1
        print(f"  ok   {label}")
    else:
        _fails.append(f"{label}: 기대 {want!r} · 실제 {got!r}")
        print(f"  FAIL {label}: 기대 {want!r} · 실제 {got!r}")


def check_true(label: str, got) -> None:
    check(label, bool(got), True)


# ---------------------------------------------------------------------------
# 임시 graph
# ---------------------------------------------------------------------------

def _guard(graph: str) -> None:
    if graph in PROTECTED:
        raise SystemExit(f"보호된 graph 를 대상으로 삼았다: {graph}")


def make_graph(graph: str) -> None:
    _guard(graph)
    try:
        pg.execute("SELECT og_drop_graph(%s)", (graph,))
    except Exception:
        pass
    pg.execute("SELECT og_create_graph(%s)", (graph,))


def drop_graph(graph: str) -> None:
    _guard(graph)
    try:
        pg.execute("SELECT og_drop_graph(%s)", (graph,))
    except Exception:
        pass
    try:
        pg.execute("DELETE FROM public.project_snapshots WHERE graph = %s", (graph,))
    except Exception:
        pass


def use(graph: str) -> None:
    """이후 호출이 이 graph 를 보게 한다 — 요청이 프로젝트를 고르는 것과 같은 길."""
    _guard(graph)
    set_override(Neo4jOverride(uri=BOLT, user=USER, password=PASSWORD, database=graph))


def seed_model(graph: str, sid: str, bcs: int = 2) -> None:
    """최소한의 '살아 있는 판'. BC 가 있어야 산출물이 조립된다."""
    _guard(graph)
    drv = GraphDatabase.driver(BOLT, auth=(USER, PASSWORD))
    with drv.session(database=graph) as s:
        for i in range(bcs):
            s.run(
                "CREATE (:BoundedContext {id: $id, name: $n, displayName: $n, "
                "domainType: 'core', session_id: $sid})",
                id=f"bc_{sid}_{i}", n=f"Ctx{i}", sid=sid,
            ).consume()
        s.run("CREATE (:UserStory {id: $id, role: 'a', action: 'b', session_id: $sid})",
              id=f"us_{sid}", sid=sid).consume()
        # 보존 라벨 — 미리보기가 이걸 세면 안 된다.
        s.run("CREATE (:FigmaBinding {id: 'fb1'})").consume()
    drv.close()


# ---------------------------------------------------------------------------
# 1. 스냅샷 저장소
# ---------------------------------------------------------------------------

def test_store() -> None:
    print("\n[1] 스냅샷 저장소")
    snapshots.ensure_schema()
    pg.execute("DELETE FROM public.project_snapshots WHERE graph IN (%s, %s)", (TMP, TMP2))

    doc = {"sessionId": "s1", "projectInfo": {"projectName": "판1"},
           "boundedContexts": [{"id": "a"}, {"id": "b"}],
           "eventStorming": {"contexts": [{"id": "a"}]}}
    meta = snapshots.save(TMP, "s1", doc, reason="ingest", counts={"BoundedContext": 2})

    check("meta 에 세션이 실린다", meta["sessionId"], "s1")
    check("BC 수를 센다", meta["boundedContexts"], 2)
    check("이름을 산출물에서 가져온다", meta["name"], "판1")
    check("사유가 남는다", meta["reason"], "ingest")

    items = snapshots.list_snapshots(TMP)
    check("목록에 한 건", len(items), 1)
    check_true("목록에 본문이 실리지 않는다", "document" not in items[0])

    body = snapshots.get(TMP, meta["snapshotKey"])
    check("본문을 되찾는다", (body or {}).get("projectInfo", {}).get("projectName"), "판1")

    # 프로젝트끼리 안 섞인다
    snapshots.save(TMP2, "s9", {"projectInfo": {"projectName": "남의 판"}})
    check("남의 프로젝트 것이 안 보인다", len(snapshots.list_snapshots(TMP)), 1)
    check("남의 프로젝트 본문은 못 읽는다", snapshots.get(TMP2, meta["snapshotKey"]), None)

    check("없는 키를 지우면 False", snapshots.delete(TMP, "없는키"), False)
    check("지워진다", snapshots.delete(TMP, meta["snapshotKey"]), True)
    check("지운 뒤 비었다", len(snapshots.list_snapshots(TMP)), 0)


def test_retention() -> None:
    print("\n[2] 보존 한도")
    pg.execute("DELETE FROM public.project_snapshots WHERE graph = %s", (TMP,))
    keys = []
    for i in range(snapshots.RETENTION + 3):
        m = snapshots.save(TMP, f"s{i}", {"projectInfo": {"projectName": f"판{i}"}})
        keys.append(m["snapshotKey"])
    items = snapshots.list_snapshots(TMP)
    check("한도를 넘지 않는다", len(items), snapshots.RETENTION)
    check_true("가장 오래된 것이 밀려났다", snapshots.get(TMP, keys[0]) is None)
    check_true("가장 최근 것은 남았다", snapshots.get(TMP, keys[-1]) is not None)
    pg.execute("DELETE FROM public.project_snapshots WHERE graph = %s", (TMP,))


# ---------------------------------------------------------------------------
# 3. 살아 있는 판 · 미리보기
# ---------------------------------------------------------------------------

def test_preview() -> None:
    print("\n[3] 살아 있는 판과 미리보기")
    make_graph(TMP)
    use(TMP)

    check("첫 인제스천 — 살아 있는 판이 없다", replacement.live_sessions(), [])
    empty = replacement.preview()
    check("첫 인제스천 — 지울 것이 없다", empty["total"], 0)
    check("미리보기가 프로젝트를 밝힌다", empty["graph"], TMP)

    seed_model(TMP, "aaa11111")
    check("BC 로 판을 잡는다 (BpmSession 없이)", replacement.live_sessions(), ["aaa11111"])

    p = replacement.preview()
    check("BC 2개를 센다", p["counts"].get("BoundedContext"), 2)
    check("UserStory 1개를 센다", p["counts"].get("UserStory"), 1)
    check_true("보존 라벨은 세지 않는다", "FigmaBinding" not in p["counts"])
    check("합계가 맞는다", p["total"], sum(p["counts"].values()))
    check_true("보존 목록을 알려준다", "FigmaBinding" in p["preserved"])

    es, hybrid = replacement._wiped_labels()
    from api.features.ingestion.ingestion_workflow_runner import _ES_LABELS
    from api.features.ingestion.hybrid.ontology.schema import ALL_HYBRID_LABELS
    check("ES 라벨을 소유 모듈에서 가져온다", es, list(_ES_LABELS))
    check("하이브리드 라벨도 그렇다", hybrid, list(ALL_HYBRID_LABELS))


# ---------------------------------------------------------------------------
# 4. 보관
# ---------------------------------------------------------------------------

def test_capture() -> None:
    print("\n[4] 지우기 직전 보관")
    pg.execute("DELETE FROM public.project_snapshots WHERE graph = %s", (TMP,))
    use(TMP)

    saved = replacement.capture_before_replace(reason="ingest")
    check("한 판이 보관됐다", len(saved), 1)
    if not saved:
        # 여기서 그냥 진행하면 IndexError 로 죽어 **무엇이 틀렸는지**가 안 보인다.
        # 결함을 심어 확인할 때 실제로 그렇게 됐다.
        print("  ...  보관된 판이 없어 이후 검사를 건너뛴다")
        return

    check("보관된 판의 세션", saved[0]["sessionId"], "aaa11111")
    check("BC 수가 실렸다", saved[0]["boundedContexts"], 2)
    check("사유가 실렸다", saved[0]["reason"], "ingest")

    body = snapshots.get(TMP, saved[0]["snapshotKey"])
    check_true("본문이 산출물 모양이다", isinstance(body, dict) and "sectionKeys" in body)
    check("본문에 BC 가 들어 있다", len(body["boundedContexts"]), 2)

    # 두 번째 판이 추가로 쌓인다 (덮어쓰지 않는다)
    seed_model(TMP, "bbb22222", bcs=1)
    saved2 = replacement.capture_before_replace(reason="ingest")
    check("살아 있는 판 둘을 다 보관한다", len(saved2), 2)
    check("쌓인다 (덮지 않는다)", len(snapshots.list_snapshots(TMP)), 3)


def test_capture_never_blocks() -> None:
    print("\n[5] 보관 실패가 인제스천을 막지 않는다")
    use(TMP)
    original = snapshots.save

    def boom(*a, **k):
        raise RuntimeError("저장소가 죽었다")

    snapshots.save = boom
    try:
        out = replacement.capture_before_replace(reason="ingest")
        check("예외를 올리지 않는다", out, [])
    finally:
        snapshots.save = original


def test_hook_order() -> None:
    """보관이 **지우기보다 먼저** 불리는가.

    순서가 뒤집히면 빈 그래프를 조립해 담는다 — 스냅샷은 생기고, 안이 비어 있고,
    오류는 안 난다. 이 저장소가 반복해 밟은 실패 방식이 정확히 그것이라 소스
    순서로 직접 잰다.
    """
    print("\n[7] 보관이 wipe 보다 먼저 불린다")
    pairs = [
        # 정의가 아니라 **호출**을 찾아야 한다. 처음 이 needle 이 함수 정의에
        # 걸려 멀쩡한 코드를 실패로 보고했다.
        ("api/features/ingestion/ingestion_workflow_runner.py",
         "clear_event_storming_nodes(client, session.id)"),
        ("api/features/ingestion/hybrid/hybrid_workflow_runner.py", "clear_all_hybrid_workspace()"),
        ("api/features/ingestion/router.py", "delete_query"),
    ]
    for rel, wipe in pairs:
        text = (ROOT / rel).read_text(encoding="utf-8")
        cap = text.find("capture_before_replace(reason=")
        wip = text.find(wipe)
        name = rel.rsplit("/", 1)[-1]
        check_true(f"{name} — 보관이 있다", cap != -1)
        check_true(f"{name} — 지우기가 있다", wip != -1)
        check_true(f"{name} — 보관이 먼저다", 0 <= cap < wip)


def test_no_analyzer_ok() -> None:
    """분석 없이 문서만 올린 프로젝트에서도 보관이 된다.

    분석이 선행하지 않는 것이 정상 상태다 — 그 경우 추적성이 비는 것이지
    보관이 실패해서는 안 된다.
    """
    print("\n[6] 분석 없는 프로젝트")
    make_graph(TMP2)
    use(TMP2)
    seed_model(TMP2, "ccc33333", bcs=1)
    saved = replacement.capture_before_replace(reason="ingest")
    check("분석이 없어도 보관된다", len(saved), 1)
    if not saved:
        print("  ...  보관된 판이 없어 이후 검사를 건너뛴다")
        return
    body = snapshots.get(TMP2, saved[0]["snapshotKey"])
    check_true("추적성 섹션 자리는 있다", "traceabilityMatrix" in (body or {}))


def test_analyzer_not_pinned() -> None:
    """분석 짝이 없는 프로젝트가 `.env` 의 남의 분석으로 떨어지지 않는가.

    이것이 이 파일에서 가장 조용한 실패다 — 떨어져도 오류가 안 나고, 추적성에
    **남의 프로젝트 분석**이 자기 것처럼 나온다. 화면으로는 구별할 수 없다.
    """
    print("\n[8] 분석 짝이 없으면 .env 로 떨어지지 않는다")
    from api.platform.neo4j import analyzer_database, analyzer_session
    from api.platform.neo4j import ANALYZER_NEO4J_DATABASE

    set_override(None)
    check("프로젝트가 없으면 .env 를 쓴다", analyzer_database(), ANALYZER_NEO4J_DATABASE)

    # Electron 헤더 경로 — 프로젝트의 결정이 아니므로 .env 폴백이 맞다.
    set_override(Neo4jOverride(uri=BOLT, user=USER, password=PASSWORD, database=TMP))
    check("Electron 경로는 그대로 .env", analyzer_database(), ANALYZER_NEO4J_DATABASE)

    # 프로젝트가 정했는데 짝이 비어 있다 — 여기서 .env 를 보면 안 된다.
    set_override(Neo4jOverride(uri=BOLT, user=USER, password=PASSWORD, database=TMP,
                               analyzer_database=None, analyzer_pinned=True))
    check("짝이 없으면 없음이다", analyzer_database(), None)
    check("세션도 열지 않는다", analyzer_session(), None)

    set_override(Neo4jOverride(uri=BOLT, user=USER, password=PASSWORD, database=TMP,
                               analyzer_database=TMP2, analyzer_pinned=True))
    check("짝이 있으면 그것을 쓴다", analyzer_database(), TMP2)

    # 추적성이 오류가 아니라 빈 결과를 돌려준다
    from api.features.canvas_graph.routes import traceability
    set_override(Neo4jOverride(uri=BOLT, user=USER, password=PASSWORD, database=TMP,
                               analyzer_pinned=True))
    check("추적성은 빈 결과", traceability._analyzer_query("MATCH (n) RETURN n LIMIT 1"), [])
    set_override(None)

    # 연결 바인딩이 실제로 pinned 를 세우는가 — 안 세우면 위 전부가 무의미하다
    src = (ROOT / "api/platform/identity/connection_binding.py").read_text(encoding="utf-8")
    check("연결 바인딩이 두 갈래 모두 pin 한다", src.count("analyzer_pinned=True"), 2)


def main() -> int:
    try:
        test_store()
        test_retention()
        test_preview()
        test_capture()
        test_capture_never_blocks()
        test_hook_order()
        test_no_analyzer_ok()
        test_analyzer_not_pinned()
    finally:
        set_override(None)
        drop_graph(TMP)
        drop_graph(TMP2)

    print()
    if _fails:
        print(f"실패 {len(_fails)}건 / 통과 {_passes}건")
        for f in _fails:
            print(f"  - {f}")
        return 1
    print(f"전부 통과 — {_passes}종")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
