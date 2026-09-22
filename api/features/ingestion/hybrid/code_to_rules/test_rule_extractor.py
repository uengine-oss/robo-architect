from api.features.ingestion.hybrid.code_to_rules.rule_extractor import _structured_rule


def test_structured_analyzer_rule_becomes_mapping_candidate():
    rule = _structured_rule({
        "function_id": "code:c-src/payment.c:verify_payment",
        "function_name": "verify_payment",
        "module_id": "c-src/payment.c",
        "analyzer_rule_id": "code:c-src/payment.c:verify_payment::R-42",
        "condition_description": "결제수단이 카드이고 인증에 성공함",
        "effect_descriptions": ["승인 상태를 저장", "승인 결과를 반환"],
    })

    assert rule is not None
    assert rule.source_module == "c-src/payment.c"
    assert rule.given == "결제수단이 카드이고 인증에 성공함"
    assert rule.then == "승인 상태를 저장; 승인 결과를 반환"
    assert len(rule.examples) == 1
    assert rule.examples[0].then_ == rule.then


def test_structured_analyzer_rule_without_effects_is_not_promoted():
    assert _structured_rule({
        "function_id": "fn",
        "function_name": "fn",
        "analyzer_rule_id": "rule-1",
        "condition_description": "조건",
        "effect_descriptions": [],
    }) is None


def test_structured_analyzer_rule_ids_use_producer_identity():
    base = {
        "function_id": "fn",
        "function_name": "fn",
        "condition_description": "같은 조건",
        "effect_descriptions": ["같은 효과"],
    }
    first = _structured_rule({**base, "analyzer_rule_id": "rule-1"})
    second = _structured_rule({**base, "analyzer_rule_id": "rule-2"})
    assert first is not None and second is not None
    assert first.id != second.id
