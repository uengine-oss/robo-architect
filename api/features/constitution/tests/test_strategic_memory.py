"""042 — Constitution strategicMemory 병합/해시 단위 테스트 (Neo4j 불필요, monkeypatch)."""

from api.features.constitution.services import constitution_store as store


def test_combined_hash_changes_with_memory():
    h_raw = store._combined_hash("raw", None)
    h_mem = store._combined_hash("raw", {"version": 1, "contexts": {"a": {"classification": "CORE"}}})
    assert h_raw != h_mem
    # 동일 입력은 동일 해시(staleness 안정성).
    assert h_mem == store._combined_hash("raw", {"version": 1, "contexts": {"a": {"classification": "CORE"}}})


def test_effective_for_bc_merges_memory(monkeypatch):
    root = {
        "fields": {k: None for k in store._FIELD_KEYS},
        "raw": "root",
        "strategicMemory": {
            "version": 1,
            "differentiation": {"differentiator": "추천 정확도"},
            "couplingPosture": {"default": "PUBSUB"},
            "contexts": {"주문": {"classification": "SUPPORTING"}},
        },
    }
    override = {
        "fields": {k: None for k in store._FIELD_KEYS},
        "raw": None,
        "strategicMemory": {"contexts": {"주문": {"classification": "CORE"}, "결제": {"classification": "GENERIC"}}},
    }
    monkeypatch.setattr(store, "get_project_constitution", lambda: root)
    monkeypatch.setattr(store, "get_bc_override", lambda bc: override)

    eff = store.effective_for_bc("주문")
    mem = eff["strategicMemory"]
    # 루트 전용 섹션은 루트에서.
    assert mem["differentiation"]["differentiator"] == "추천 정확도"
    assert mem["couplingPosture"]["default"] == "PUBSUB"
    # BC 오버라이드가 같은 컨텍스트를 덮어쓴다(SUPPORTING → CORE).
    assert mem["contexts"]["주문"]["classification"] == "CORE"
    # 오버라이드에만 있는 컨텍스트도 병합.
    assert mem["contexts"]["결제"]["classification"] == "GENERIC"


def test_effective_for_bc_no_override(monkeypatch):
    root = {
        "fields": {k: None for k in store._FIELD_KEYS},
        "raw": "root",
        "strategicMemory": {"version": 1, "contexts": {"주문": {"classification": "SUPPORTING"}}},
    }
    monkeypatch.setattr(store, "get_project_constitution", lambda: root)
    monkeypatch.setattr(store, "get_bc_override", lambda bc: None)
    eff = store.effective_for_bc("주문")
    assert eff["strategicMemory"]["contexts"]["주문"]["classification"] == "SUPPORTING"
    assert eff["hasOverride"] is False
