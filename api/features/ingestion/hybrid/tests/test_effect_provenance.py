from api.features.ingestion.hybrid.bpm_context_builder import render_hybrid_bl_block
from api.features.ingestion.hybrid.effect_provenance import merge_write_effects


def test_new_contract_filters_reads_but_preserves_unknown_writes() -> None:
    effects = merge_write_effects(
        [
            {
                "table": "orders",
                "access": "READ",
                "op": "READ",
                "op_source": "SCANNER",
            },
            {
                "table": "audit",
                "access": "WRITE",
                "op": "UNKNOWN",
                "op_source": "UNRESOLVED",
            },
        ]
    )
    assert effects == [{
        "table": "audit",
        "access": "WRITE",
        "op": "UNKNOWN",
        "op_source": "UNRESOLVED",
    }]


def test_missing_provenance_is_unresolved() -> None:
    effects = merge_write_effects(
        [
            {"table": "orders", "op": "UPDATE"},
            {"table": "lookup", "op": "READ"},
        ]
    )
    assert effects == [{
        "table": "orders",
        "access": "WRITE",
        "op": "UNKNOWN",
        "op_source": "UNRESOLVED",
    }]


def test_unresolved_source_cannot_smuggle_an_exact_event_verb() -> None:
    effects = merge_write_effects([{
        "table": "orders",
        "access": "WRITE",
        "op": "UPDATE",
        "op_source": "UNRESOLVED",
    }])
    assert effects[0]["op"] == "UNKNOWN"
    assert effects[0]["op_source"] == "UNRESOLVED"


def test_rendering_distinguishes_authoritative_inferred_and_unresolved() -> None:
    block = render_hybrid_bl_block({
        "US-1": [{
            "source_function": "work",
            "title": "상태를 반영한다.",
            "given": "주문 처리 중",
            "when_": "상태 변경 조건을 만족하면",
            "then_": "상태를 반영한다.",
            "writes": [
                    {
                        "table": "orders",
                        "access": "WRITE",
                        "op": "UPDATE",
                        "op_source": "SCANNER",
                    },
                    {
                        "table": "audit",
                        "access": "WRITE",
                        "op": "INSERT",
                        "op_source": "LLM_INFERRED",
                    },
                    {
                        "table": "outbox",
                        "access": "WRITE",
                        "op": "UNKNOWN",
                        "op_source": "UNRESOLVED",
                    },
                ],
        }],
    })
    assert "UPDATE `orders` [SCANNER]" in block
    assert "INSERT `audit` [LLM_INFERRED]" in block
    assert "WRITE `outbox` [op unresolved]" in block
