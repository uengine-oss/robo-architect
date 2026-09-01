from __future__ import annotations

import asyncio

from api.features.ingestion.hybrid.code_to_rules import rule_extractor


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
    )
    monkeypatch.setattr(
        rule_extractor,
        "get_session",
        lambda database=None: _Context(session),
    )

    rules = asyncio.run(rule_extractor.extract_rules_from_analyzer_graph())

    assert len(rules) == 1
    rule = rules[0]
    assert rule.given == "주문 승인을 처리한다."
    assert rule.when == "금액이 승인 한도를 넘으면"
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
    assert "condition_description" in session.query
    assert "effect_descriptions" in session.query
    assert "write.operations" in session.query
