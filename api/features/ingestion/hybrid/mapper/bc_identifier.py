"""Phase 2.5: Business Context (BC) pre-tagging for Rules.

Goal (PRD §8.2.1): assign each Rule a `context_cluster` string (domain term)
BEFORE Phase 3 matching runs, so that:
  (a) Phase 3 embedding/lexical signals carry explicit domain labels,
  (b) Phase 5 BoundedContext identification has deterministic input instead of
      collapsing every rule into a single cluster.

Pipeline:
  1. **Prefix clustering** — deterministic seed from `source_function` naming
     convention (a000/b000/b100/...). The convention is project-specific; we
     apply a pragmatic default and let the LLM rename the clusters in step 3.
  2. **Orchestrator BL redistribution** — functions named `*_main_proc` or
     matching orchestrator prefixes hold BL from multiple contexts. Re-slot
     each BL into a finer cluster using keyword match on `then`/`when`/`title`.
  3. **LLM naming (optional)** — one call, given (cluster_id → sample titles),
     return a clean domain term per cluster. On failure, fall back to the
     rule-based seed name.

Output: `dict[rule_id, cluster_name]` — empty string means "unclassified".
"""

from __future__ import annotations

import os
import re
from collections import defaultdict
from typing import Iterable

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from api.features.ingestion.hybrid.contracts import RuleContext, RuleDTO
from api.features.ingestion.ingestion_llm_runtime import get_llm
from api.platform.observability.smart_logger import SmartLogger

# ---------------------------------------------------------------------------
# 1. Deterministic prefix → seed cluster mapping
# ---------------------------------------------------------------------------
# Keys are regex patterns applied to source_function (case-insensitive).
# Values are the seed cluster name (Korean domain term). LLM step 3 may rename.
_PREFIX_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^a\d{3}_.*valid", re.I), "입력검증"),
    (re.compile(r"^a\d{3}_.*input", re.I), "입력검증"),
    (re.compile(r"^a\d{3}_", re.I), "입력검증"),
    # b000 main orchestrator — will be re-distributed in step 2
    (re.compile(r"^b0{2,3}_.*main", re.I), "__orchestrator__"),
    (re.compile(r"^b0{2,3}_", re.I), "__orchestrator__"),
    # b100 family — common code checking
    (re.compile(r"^b1\d{2}_.*comm.*cd", re.I), "공통코드검증"),
    (re.compile(r"^b1\d{2}_", re.I), "공통코드검증"),
    # b200/b205/b210/b400/b410 — history management
    (re.compile(r"^b[24]\d{2}_.*hst", re.I), "이력관리"),
    (re.compile(r"^b[24]\d{2}_.*hist", re.I), "이력관리"),
    (re.compile(r"^b[24]\d{2}_", re.I), "이력관리"),
    # b300 — query/lookup family (account, ledger etc.)
    (re.compile(r"^b3\d{2}_", re.I), "원장조회"),
    # b5/b6 — domain-specific query
    (re.compile(r"^b[56]\d{2}_", re.I), "도메인조회"),
    # b7xx — company type checks (simple pay, card company, etc.)
    (re.compile(r"^b7\d{2}_.*check.*smp", re.I), "간편결제검증"),
    (re.compile(r"^b7\d{2}_.*check.*card", re.I), "카드사검증"),
    (re.compile(r"^b7\d{2}_", re.I), "회사구분검증"),
    # b800+ — error message / formatting
    (re.compile(r"^b[89]\d{2}_.*err.*msg", re.I), "오류메시지"),
    (re.compile(r"^b[89]\d{2}_.*msg", re.I), "오류메시지"),
    (re.compile(r"^b[89]\d{2}_", re.I), "오류메시지"),
    # Top-level entry points (zapamcom*, common entry, etc.) — treat as entry
    (re.compile(r"^z[a-z]+\d+", re.I), "진입점"),
    (re.compile(r"^entry_|^main_|^handler_", re.I), "진입점"),
]


# Keyword → cluster mapping for orchestrator BL redistribution.
# Applied to the rule's `title` (BL.title) + `then` + `when` text, first-match-wins.
# Ordered so the most specific / strongest-signal keywords are tried first.
# Korean particle-interference (를/을/이/가 etc.) is tolerated via `.*?` bridges,
# scoped to a short window so unrelated long sentences don't false-match.
_KEYWORD_REDISTRIBUTE: list[tuple[re.Pattern[str], str]] = [
    # ===== History (highest priority within orchestrator redistribution) =====
    # "인증이력 저장/적재/갱신..." — explicit history action verbs
    (re.compile(r"(이력|history|hst)"), "이력관리"),
    (re.compile(r"(갱신|적재|insert|update).{0,10}(경로|방식|단계)"), "이력관리"),
    # ===== Error message construction =====
    # "오류 메시지", "에러 코드", "실패 사유"
    (re.compile(r"(오류|에러|실패).{0,4}(코드|메시지|문구|사유)"), "오류메시지"),
    # "메시지를 만든다", "문구를 조립", "비인증 메시지로 고정", "메시지로 결정"
    # Korean conjugation variants: 만들/만든/만드 all map to "make"; similarly for others.
    (re.compile(r"(메시지|문구).{0,6}(만들|만든|만드|조립|생성|반환|결정|고정|부여)"), "오류메시지"),
    # Bare 오류/에러 as final fallback for this domain
    (re.compile(r"(오류|에러)"), "오류메시지"),
    # ===== Auth decision =====
    (re.compile(r"(반영여부|반영\s*여부)"), "인증결과판정"),
    (re.compile(r"(반영(?!여부)|미반영)"), "인증결과판정"),
    (re.compile(r"(인증\s*결과|결과코드).{0,6}(판정|결정|보정|검증|확인)"), "인증결과판정"),
    (re.compile(r"(인증|결과코드)"), "인증결과판정"),
    # ===== Input validation =====
    (re.compile(r"(검증|유효성|필수값|누락|거부|거절)"), "입력검증"),
    # ===== Card company code =====
    (re.compile(r"카드사\s*코드"), "카드사검증"),
    # ===== Simple-pay / SMP =====
    (re.compile(r"(간편결제|SMP|smp)"), "간편결제검증"),
]


class _BCNamedCluster(BaseModel):
    cluster_id: str
    name: str = Field(
        description="도메인 용어. 한국어 명사구 (예: '실시간인증', '입력검증', '이력관리'). "
        "함수 prefix 그대로 (예: 'b200') 는 절대 사용 금지."
    )


class _BCNameResult(BaseModel):
    clusters: list[_BCNamedCluster]


_SYSTEM_PROMPT = """당신은 레거시 코드의 비즈니스 로직을 업무 범주(Bounded Context 힌트)로 분류하는 분석가입니다.
입력으로 여러 클러스터가 주어지며, 각 클러스터에는 코드 함수 이름과 BL 제목(한국어) 샘플이 포함됩니다.

각 클러스터에 **도메인 용어**로 된 짧은 이름을 붙이세요.

규칙:
- 한국어 명사구. 예: "실시간인증", "입력검증", "이력관리", "오류메시지 처리"
- 함수 prefix 를 그대로 쓰지 마세요 (예: "b200 함수군" X). 업무가 무엇인지 말해야 합니다
- 기본 후보 이름이 주어집니다 — 이미 적절하면 그대로, 더 정확한 이름이 있으면 교체
- 클러스터의 실제 내용과 맞지 않으면 이름을 바꾸세요
"""


def _seed_cluster_for_function(source_function: str | None) -> str:
    """Apply prefix regex rules; returns '' if no rule matched."""
    if not source_function:
        return ""
    for pattern, label in _PREFIX_RULES:
        if pattern.search(source_function):
            return label
    return ""


def _redistribute_orchestrator(text: str) -> str:
    """For a single BL from an orchestrator function, find the best fine-grained cluster."""
    if not text:
        return ""
    for pattern, label in _KEYWORD_REDISTRIBUTE:
        if pattern.search(text):
            return label
    return ""


def _title_of(ctx: RuleContext | None, rule: RuleDTO) -> str:
    """Pick a short representative text for keyword redistribution.

    Order of preference:
      1. `BL.title` — analyzer's one-line business intent. Cleanest signal.
      2. `then` / `when` — concrete test values or side-effects. Often noisy
         (table names leak in and collapse all BL of one function into the same
         bucket), but better than nothing.

    We deliberately DO NOT mix `ctx.function_summary` in: a summary is identical
    across every BL of the same function, so any trigger word it happens to
    contain would apply to all 14 BL of an orchestrator uniformly, defeating
    the whole point of per-BL redistribution.
    """
    if rule.title:
        return rule.title
    return " ".join(p for p in [rule.when, rule.then] if p)


def _apply_writes_reinforcement(
    seed_by_rule: dict[str, str],
    contexts: list[RuleContext],
    orchestrator_rule_ids: set[str],
) -> dict[str, str]:
    """If two prefix clusters share a WRITES table (e.g. b200+b400 both write
    ZPAY_AP_RLTM_AUTH_HST), merge them under the first cluster seen.

    This only makes sense for rules whose cluster came from PREFIX matching
    (one function = one cluster). Orchestrator BL are excluded: an orchestrator
    writes to many tables across many domains, so its writes would create
    false bridges between unrelated clusters.
    """
    # cluster → set of tables it writes
    writes_by_cluster: dict[str, set[str]] = defaultdict(set)
    for ctx in contexts:
        if ctx.rule_id in orchestrator_rule_ids:
            # Orchestrator BL writes are not attributable to any single cluster.
            continue
        seed = seed_by_rule.get(ctx.rule_id, "")
        if not seed or seed == "__orchestrator__":
            continue
        for tbl in ctx.writes_tables or []:
            if tbl:
                writes_by_cluster[seed].add(tbl.upper())
    if len(writes_by_cluster) < 2:
        return seed_by_rule

    # Union-Find on clusters that share any WRITES table
    parent: dict[str, str] = {c: c for c in writes_by_cluster}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    cluster_list = list(writes_by_cluster.keys())
    for i in range(len(cluster_list)):
        for j in range(i + 1, len(cluster_list)):
            if writes_by_cluster[cluster_list[i]] & writes_by_cluster[cluster_list[j]]:
                ri, rj = find(cluster_list[i]), find(cluster_list[j])
                if ri != rj:
                    parent[rj] = ri

    # Rewrite rule seeds to the canonical cluster name (pick the lexicographic min
    # among the union, so results are deterministic across reruns).
    groups: dict[str, list[str]] = defaultdict(list)
    for c in cluster_list:
        groups[find(c)].append(c)
    rename: dict[str, str] = {}
    for root, members in groups.items():
        if len(members) > 1:
            canonical = sorted(members)[0]
            for m in members:
                if m != canonical:
                    rename[m] = canonical
    if not rename:
        return seed_by_rule
    return {rid: rename.get(c, c) for rid, c in seed_by_rule.items()}


async def _llm_name_clusters(
    cluster_samples: dict[str, list[str]],
    default_names: dict[str, str],
) -> dict[str, str]:
    """Ask LLM to produce a final display name per cluster. Fall back to default on error."""
    if not cluster_samples:
        return dict(default_names)

    payload_lines: list[str] = []
    for cid in sorted(cluster_samples):
        samples = cluster_samples[cid][:6]
        default = default_names.get(cid, cid)
        payload_lines.append(f"[클러스터 {cid}] 기본 후보 이름: {default}")
        for s in samples:
            payload_lines.append(f"  - {s}")
        payload_lines.append("")
    user = "\n".join(payload_lines) + "\n위 각 클러스터에 도메인 용어 이름을 붙이세요."

    try:
        llm = get_llm()
        structured = llm.with_structured_output(_BCNameResult)
        result: _BCNameResult = await structured.ainvoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=user),
        ])
    except Exception as e:
        SmartLogger.log(
            "WARN", "BC LLM naming failed; keeping default names",
            category="ingestion.hybrid.bc_tag",
            params={"error": str(e)},
        )
        return dict(default_names)

    out = dict(default_names)
    for c in result.clusters:
        cid = (c.cluster_id or "").strip()
        name = (c.name or "").strip()
        if cid and name:
            out[cid] = name
    return out


_ORCHESTRATOR_MIN_CALLEES = 3  # fn that dispatches to 3+ other fns is an orchestrator


def _is_orchestrator_by_graph(ctx: RuleContext | None) -> bool:
    """Orchestrator detection via call graph — a function that dispatches to
    many callees is almost always an orchestrator, regardless of name. More
    robust than fn-prefix regex in multi-module codebases where naming
    conventions vary per team."""
    if ctx is None:
        return False
    return len(ctx.callees or []) >= _ORCHESTRATOR_MIN_CALLEES


async def identify_rule_bc_clusters(
    rules: Iterable[RuleDTO],
    contexts: Iterable[RuleContext],
    *,
    use_llm: bool | None = None,
) -> dict[str, str]:
    """Phase 2.5 main entry — returns `rule_id → cluster_name` dict.

    Deterministic on the same input when `use_llm=False`. With LLM enabled the
    cluster *assignments* are still deterministic; only the *display names* may
    vary slightly (and we cache the default as fallback).
    """
    rules = list(rules)
    contexts = list(contexts)
    if not rules:
        return {}

    if use_llm is None:
        use_llm = os.getenv("HYBRID_BC_USE_LLM", "true").strip().lower() not in ("0", "false", "no")

    ctx_by_rule = {c.rule_id: c for c in contexts}

    # Step 1: prefix seeds (+ graph-based orchestrator promotion).
    # If the call graph says "this fn has 3+ callees" we upgrade the seed to
    # orchestrator, even when the naming regex didn't catch it — this covers
    # multi-module projects where prefix conventions differ.
    seed_by_rule: dict[str, str] = {}
    orchestrator_rule_ids: set[str] = set()
    for r in rules:
        ctx = ctx_by_rule.get(r.id)
        seed = _seed_cluster_for_function(r.source_function)
        if _is_orchestrator_by_graph(ctx):
            seed = "__orchestrator__"
        seed_by_rule[r.id] = seed
        if seed == "__orchestrator__":
            orchestrator_rule_ids.add(r.id)

    # Step 2: orchestrator redistribution — per-BL keyword match on title.
    for rid in orchestrator_rule_ids:
        r = next((x for x in rules if x.id == rid), None)
        if r is None:
            continue
        ctx = ctx_by_rule.get(rid)
        text = _title_of(ctx, r)
        finer = _redistribute_orchestrator(text)
        if finer:
            seed_by_rule[rid] = finer
        else:
            # Orchestrator BL that didn't match any keyword: keep it as its own
            # cluster so downstream can still group them. Use a generic label.
            seed_by_rule[rid] = "메인흐름"

    # Step 2.5: subfunction inherits caller's cluster when subfunction itself
    # lacks a prefix-based seed. Example: a dbio helper whose name doesn't
    # match any prefix rule, but whose caller belongs to "이력관리" — the
    # helper almost certainly belongs to "이력관리" too.
    caller_cluster_by_fn: dict[str, str] = {}
    for r in rules:
        fn = r.source_function
        cluster = seed_by_rule.get(r.id, "")
        if fn and cluster and cluster != "__orchestrator__":
            caller_cluster_by_fn.setdefault(fn, cluster)
    for r in rules:
        if seed_by_rule.get(r.id):
            continue  # already has a seed
        ctx = ctx_by_rule.get(r.id)
        if not ctx or not ctx.callers:
            continue
        # Take majority cluster among callers that are themselves seeded.
        caller_votes: dict[str, int] = {}
        for caller_fn in ctx.callers:
            c = caller_cluster_by_fn.get(caller_fn)
            if c:
                caller_votes[c] = caller_votes.get(c, 0) + 1
        if caller_votes:
            winner = max(caller_votes.items(), key=lambda kv: kv[1])[0]
            seed_by_rule[r.id] = winner

    # Step 3: WRITES-table reinforcement (excluding orchestrator BL — their
    # writes_tables reflect the orchestrator's full footprint, not per-BL semantics).
    seed_by_rule = _apply_writes_reinforcement(seed_by_rule, contexts, orchestrator_rule_ids)

    # Step 4: prep LLM input — gather sample titles per cluster
    cluster_samples: dict[str, list[str]] = defaultdict(list)
    default_names: dict[str, str] = {}
    rule_by_id = {r.id: r for r in rules}
    for rid, cid in seed_by_rule.items():
        if not cid:
            continue
        default_names.setdefault(cid, cid)
        r = rule_by_id.get(rid)
        if r is None:
            continue
        title = (r.when or r.then or "").strip()
        if title and len(cluster_samples[cid]) < 6:
            cluster_samples[cid].append(title)

    # Step 5: LLM rename
    if use_llm:
        final_names = await _llm_name_clusters(cluster_samples, default_names)
    else:
        final_names = dict(default_names)

    # Resolve: rule_id → final display name (fall back to seed if lookup fails)
    result: dict[str, str] = {}
    for rid, cid in seed_by_rule.items():
        if not cid:
            continue
        result[rid] = final_names.get(cid, cid)

    SmartLogger.log(
        "INFO", "Phase 2.5 BC tagging complete",
        category="ingestion.hybrid.bc_tag",
        params={
            "rules_in": len(rules),
            "rules_tagged": len(result),
            "cluster_count": len(set(result.values())),
            "clusters": sorted(set(result.values())),
        },
    )
    return result
