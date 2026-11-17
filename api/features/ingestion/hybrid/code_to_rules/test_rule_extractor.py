from __future__ import annotations

import asyncio

from api.features.ingestion.hybrid.code_to_rules import rule_extractor
from api.features.ingestion.hybrid.code_to_rules.rule_extractor import _structured_rule


class _Session:
    def __init__(self, rows: list[dict]):
        self.rows = rows
        self.query = ""

    def run(self, query: str):
        self.query = query
        return self.rows


class _Context:
    def __init__(self, session: _Session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc, traceback):
        return False


def test_structured_analyzer_rule_becomes_mapping_candidate():
    rule = _structured_rule({
        "function_id": "code:c-src/payment.c:verify_payment",
        "function_name": "verify_payment",
        "source_container_id": "c-src/payment.c",
        "analyzer_rule_id": "code:c-src/payment.c:verify_payment::R-42",
        "condition_description": "결제수단이 카드이고 인증에 성공함",
        "effect_descriptions": ["승인 상태를 저장", "승인 결과를 반환"],
        "function_summary": "결제 승인을 검증한다",
        "source_file_path": "c-src/payment.c",
        "source_start_line": 10,
        "source_end_line": 40,
        "reads_tables": ["PAYMENT", "CUSTOMER", "PAYMENT"],
        "writes_tables": ["PAYMENT"],
    })

    assert rule is not None
    assert rule.source_function_id == "code:c-src/payment.c:verify_payment"
    # 추적성은 source_module 로 루틴을 찾는다 — 루틴 id 와 같아야 한다.
    assert rule.source_module == rule.source_function_id
    assert rule.source_container == "c-src/payment.c"
    assert rule.given == "결제수단이 카드이고 인증에 성공함"
    assert rule.then == "승인 상태를 저장; 승인 결과를 반환"
    assert rule.source_summary == "결제 승인을 검증한다"
    assert rule.source_file_path == "c-src/payment.c"
    assert (rule.source_start_line, rule.source_end_line) == (10, 40)
    assert rule.reads_tables == ["CUSTOMER", "PAYMENT"]
    assert rule.writes_tables == ["PAYMENT"]


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


def test_integer_ids_and_json_string_lists_are_tolerated():
    # Ontological 게이트웨이: id 가 정수로, 목록이 JSON 문자열로 올 수 있다.
    rule = _structured_rule({
        "function_id": 17,
        "function_name": "approve",
        "analyzer_rule_id": 42,
        "condition_description": "금액이 한도를 넘으면",
        "effect_descriptions": '["주문 승인을 거절한다."]',
        "raw_writes": [{"table": "orders", "operations": '["UPDATE"]'}],
    })
    assert rule is not None
    assert (rule.source_function_id, rule.source_rule_id) == ("17", "42")
    assert rule.then == "주문 승인을 거절한다."
    assert [w["op"] for w in rule.writes] == ["UPDATE"]


def test_final_analyzer_rule_contract_is_converted_once(monkeypatch) -> None:
    session = _Session(
        [
            {
                "function_id": "code:orders.py:approve",
                "function_name": "approve",
                "function_summary": "주문 승인을 처리한다.",
                "source_container_id": "code:orders.py",
                "analyzer_rule_id": "code:orders.py:approve::R-10",
                "rule_order": 1,
                "condition": "amount > limit",
                "effects": ["reject()"],
                "condition_description": "금액이 승인 한도를 넘으면",
                "effect_descriptions": ["주문 승인을 거절한다."],
                "raw_writes": [
                    {
                        "table": "orders",
                        "access": "WRITE",
                        "operations": ["UPDATE"],
                        "op_source": "SCANNER",
                    }
                ],
            }
        ]
        * 2  # 같은 RULE 이 두 번 와도 한 번만 바뀐다
    )
    monkeypatch.setattr(rule_extractor, "analyzer_session", lambda: _Context(session))

    rules = asyncio.run(rule_extractor.extract_rules_from_analyzer_graph())

    assert len(rules) == 1
    rule = rules[0]
    assert rule.given == "금액이 승인 한도를 넘으면"
    assert rule.when == "approve 실행"
    assert rule.then == "주문 승인을 거절한다."
    assert rule.source_function_id == "code:orders.py:approve"
    assert rule.source_rule_id == "code:orders.py:approve::R-10"
    assert rule.source_container == "code:orders.py"
    assert rule.writes == [
        {
            "table": "orders",
            "access": "WRITE",
            "op": "UPDATE",
            "op_source": "SCANNER",
        }
    ]
    # 현재 analyzer 계약: product_id 로 읽고 `_id` 는 쓰지 않는다.
    assert "product_id" in session.query
    assert "._id" not in session.query
    assert "condition_description" in session.query
    assert "effect_descriptions" in session.query
    assert "write.operations" in session.query


def test_no_analyzer_graph_means_no_rules(monkeypatch) -> None:
    monkeypatch.setattr(rule_extractor, "analyzer_session", lambda: None)
    assert asyncio.run(rule_extractor.extract_rules_from_analyzer_graph()) == []
