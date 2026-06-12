"""Unit tests for §036 term normalization (term_normalizer.py).

순수 함수 — 외부 서비스/LLM 불필요. floor·예산 불변 원칙과 무관하게
정규화 함수 자체의 계약(append-only, 빈 glossary 폴백, 상한, 결정성)을 검증.
"""

from __future__ import annotations

from api.features.ingestion.hybrid.contracts import GlossaryTerm, RuleDTO
from api.features.ingestion.hybrid.mapper.term_normalizer import (
    normalize_query,
    normalize_rule_blob,
)


def _rule(**kw) -> RuleDTO:
    base = dict(id="r1", given="", when="", then="")
    base.update(kw)
    return RuleDTO(**base)


# ---------------------------------------------------------------- normalize_query

def test_query_appends_code_candidates_on_term_match():
    gloss = [GlossaryTerm(term="본인확인", aliases=["실명확인"], code_candidates=["zapamcom", "idverify"])]
    out, applied = normalize_query("본인확인을 처리한다", gloss)
    assert applied is True
    assert "본인확인을 처리한다" in out  # 원문 보존(append-only)
    assert "zapamcom" in out and "idverify" in out


def test_query_matches_via_alias():
    gloss = [GlossaryTerm(term="자동납부", aliases=["정기출금"], code_candidates=["autopay"])]
    out, applied = normalize_query("정기출금 내역 조회", gloss)
    assert applied is True
    assert "autopay" in out


def test_query_no_match_returns_original():
    gloss = [GlossaryTerm(term="배송", aliases=[], code_candidates=["ship"])]
    out, applied = normalize_query("결제를 승인한다", gloss)
    assert applied is False
    assert out == "결제를 승인한다"


def test_query_empty_glossary_returns_original():
    assert normalize_query("아무 텍스트", []) == ("아무 텍스트", False)
    assert normalize_query("아무 텍스트", None) == ("아무 텍스트", False)


def test_query_respects_alias_cap():
    gloss = [GlossaryTerm(
        term="본인확인", aliases=[],
        code_candidates=[f"c{i}" for i in range(10)],
    )]
    out, applied = normalize_query("본인확인", gloss, max_aliases_per_term=3)
    assert applied is True
    appended = out.split("[용어:")[1]
    assert sum(f"c{i}" in appended for i in range(10)) == 3


def test_query_is_deterministic():
    gloss = [
        GlossaryTerm(term="본인확인", aliases=[], code_candidates=["zapamcom"]),
        GlossaryTerm(term="납부", aliases=[], code_candidates=["pay"]),
    ]
    a = normalize_query("본인확인 납부", gloss)
    b = normalize_query("본인확인 납부", gloss)
    assert a == b


def test_query_skips_token_already_present():
    gloss = [GlossaryTerm(term="본인확인", aliases=[], code_candidates=["zapamcom"])]
    # query already contains the code token → nothing fresh to add
    out, applied = normalize_query("본인확인 zapamcom", gloss)
    assert applied is False
    assert out == "본인확인 zapamcom"


# ------------------------------------------------------------ normalize_rule_blob

def test_blob_appends_terms_on_code_match_in_source_module():
    gloss = [GlossaryTerm(term="본인확인", aliases=["실명확인"], code_candidates=["zapamcom"])]
    rule = _rule(source_module="zapamcom10060", title="WD master update")
    out, applied = normalize_rule_blob("GIVEN x\nWHEN y\nTHEN z", rule, None, gloss)
    assert applied is True
    assert "본인확인" in out and "실명확인" in out
    assert "GIVEN x" in out  # 원문 보존


def test_blob_matches_on_title():
    gloss = [GlossaryTerm(term="자동납부", aliases=[], code_candidates=["autopay"])]
    rule = _rule(title="autoPay batch", source_module="batch01")
    out, applied = normalize_rule_blob("blob", rule, None, gloss)
    assert applied is True
    assert "자동납부" in out


def test_blob_no_code_match_returns_original():
    gloss = [GlossaryTerm(term="배송", aliases=[], code_candidates=["ship"])]
    rule = _rule(source_module="zapamcom10060", title="WD master")
    out, applied = normalize_rule_blob("blob", rule, None, gloss)
    assert applied is False
    assert out == "blob"


def test_blob_empty_glossary_returns_original():
    rule = _rule(source_module="zapamcom10060")
    assert normalize_rule_blob("blob", rule, None, []) == ("blob", False)
    assert normalize_rule_blob("blob", rule, None, None) == ("blob", False)


def test_blob_respects_terms_cap():
    gloss = [GlossaryTerm(
        term="t0", aliases=[f"a{i}" for i in range(10)], code_candidates=["zapamcom"],
    )]
    rule = _rule(source_module="zapamcom10060")
    out, applied = normalize_rule_blob("blob", rule, None, gloss, max_terms_per_candidate=2)
    assert applied is True
    appended = out.split("[업무용어:")[1]
    # term t0 + alias a0 (cap 2) → a1.. excluded
    assert "t0" in appended and "a0" in appended
    assert "a5" not in appended
