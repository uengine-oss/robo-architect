"""
041 — 프로젝트 루트 헌장 인터뷰 (Design 쪽, 프로포절과 무관).

핵심 게이팅 질문은 **백엔드가 결정적으로** 묻는다(LLM 에 맡기면 한두 개만 묻고 자동
확정해버리는 문제 회피). 질문은 즉시(스킬 호출 없이) 흐른다. 모든 게이팅 결정이
확정되면 그때 한 번 **robo-proposal 스킬의 Constitution phase**로 헌장 Markdown 을 합성하고
프로젝트 루트 Constitution 노드를 만든다. (Claude Code 호출, LLM 키 불필요.)
"""

from __future__ import annotations

import json
from typing import AsyncGenerator, Optional

from api.platform.observability.smart_logger import SmartLogger
from api.platform.skill_runner import run_skill_lines, extract_json
from api.features.constitution.services import constitution_store as store

_SKILL_ROOT = "robo-proposals"
_SKILL_NAME = "robo-proposal"

# field -> answer (게이팅 결정 누적). 단일 프로젝트 인터뷰라 모듈 전역.
_answers: dict[str, str] = {}

# 제안(proposal) 기반 인터뷰 컨텍스트. Plan 게이트에서 진입하면 채워진다.
#   {"id", "prompt", "bc_names": [...]}  — None 이면 Design 측(그래프 기반) 인터뷰.
_proposal_ctx: Optional[dict] = None
# Claude Code 가 제안을 분석해 만든 게이팅 영역별 추천. field -> {recommended, rationale}.
_recs: dict[str, dict] = {}

# 상위 결정이 바뀌면 무효화되는 하위 결정들(뒤로 가서 답을 바꾸면 하위 답 폐기).
_DOWNSTREAM = {
    "architectureStyle": ["repoStrategy", "repoMode", "deploymentTarget", "messaging"],
    "repoStrategy": ["repoMode"],
}


def record_answer(field: str, answer: str) -> int:
    if not field:
        return len(_answers)
    # 상위 결정이 바뀌면 의존 하위 답을 폐기(일관성 유지).
    if _answers.get(field) not in (None, answer):
        for d in _DOWNSTREAM.get(field, []):
            _answers.pop(d, None)
    _answers[field] = answer
    # 모놀리스면 레포 전략은 묻지 않고 MONOREPO 로 자동 확정(레포-퍼-서비스 무의미).
    if field == "architectureStyle":
        if answer == "MONOLITH":
            _answers["repoStrategy"] = "MONOREPO"
            _answers.pop("repoMode", None)
        else:
            # 마이크로서비스로 바꾸면 자동 설정했던 레포 전략을 다시 묻도록 비운다.
            if _answers.get("repoStrategy") == "MONOREPO":
                _answers.pop("repoStrategy", None)
    return len(_answers)


def reset_answers() -> None:
    """새 인터뷰 시작 시 누적 답변 초기화(이전 세션 stale 제거)."""
    _answers.clear()
    _recs.clear()


def set_proposal_context(proposal_id: str) -> dict:
    """Plan 게이트 진입 — 제안의 프롬프트 + strategicDiff 의 BoundedContext 를 적재한다.
    이후 추천/근거/합성이 (빈 라이브 그래프가 아니라) 이 제안 맥락을 기준으로 동작한다."""
    global _proposal_ctx
    _answers.clear()
    _recs.clear()
    ctx = {"id": proposal_id, "prompt": "", "bc_names": []}
    try:
        from api.platform.neo4j import get_session
        with get_session() as session:
            rec = session.run(
                "MATCH (p:Proposal {id: $id}) RETURN p.originalPrompt AS prompt, p.strategicDiff AS sd",
                id=proposal_id,
            ).single()
        if rec:
            ctx["prompt"] = rec["prompt"] or ""
            sd = rec["sd"]
            sd = json.loads(sd) if isinstance(sd, str) else (sd or {})
            ctx["bc_names"] = [
                e.get("entityTitle") for e in (sd.get("epics") or [])
                if isinstance(e, dict) and e.get("entityTitle")
            ]
    except Exception:
        pass
    _proposal_ctx = ctx
    return ctx


def answers_snapshot() -> dict:
    return dict(_answers)


def _bc_names() -> list[str]:
    # 제안 맥락이 있으면 그 strategicDiff 의 BC 를 쓴다(아직 그래프에 머지 전이므로).
    if _proposal_ctx is not None:
        return list(_proposal_ctx.get("bc_names") or [])
    try:
        from api.platform.neo4j_helpers import load_domain_nodes
        nodes = load_domain_nodes() or []
    except Exception:
        nodes = []
    return [n.get("name") for n in nodes if n.get("label") == "BoundedContext" and n.get("name")]


def _bc_count() -> int:
    return len(_bc_names())


def _next_question() -> Optional[dict]:
    """현재 답변 상태에서 다음에 물어야 할 게이팅 질문(없으면 None=합성 단계)."""
    a = _answers
    bc = _bc_count()

    if "architectureStyle" not in a:
        rec = "MONOLITH" if bc <= 3 else "MICROSERVICES"
        return {
            "index": 1, "field": "architectureStyle",
            "question": "아키텍처 스타일은? 단일 배포의 모놀리스로 갈지, 서비스를 독립 배포하는 마이크로서비스로 갈지 정해주세요.",
            "options": ["MONOLITH", "MICROSERVICES"],
            "recommended": rec,
            "rationale": f"현재 BoundedContext {bc}개. " + ("소수·단순 → 단일 배포가 간단(모놀리스 추천)." if bc <= 3 else "다수 컨텍스트 → 독립 배포 이점(마이크로서비스 추천)."),
        }

    if "techStack" not in a:
        return {
            "index": 2, "field": "techStack",
            "question": "기술 스택은? (백엔드 / 프론트엔드 / 데이터스토어) — 보기에서 고르거나 직접 입력하세요.",
            "options": [
                "Spring Boot + JPA + PostgreSQL + Vue 3",
                "Node/NestJS + Prisma + PostgreSQL + React",
                "Python/FastAPI + SQLAlchemy + PostgreSQL + Vue 3",
            ],
            "recommended": "Spring Boot + JPA + PostgreSQL + Vue 3",
            "rationale": "DDD 애그리거트·트랜잭션 일관성에 성숙한 스택. 직접 입력 가능.",
            "allowFree": True,
        }

    # 레포 전략은 **마이크로서비스일 때만** 묻는다. 모놀리스는 MONOREPO 로 자동 확정(record_answer).
    if a.get("architectureStyle") == "MICROSERVICES" and "repoStrategy" not in a:
        return {
            "index": 3, "field": "repoStrategy",
            "question": "레포 전략은? 단일 mono-repo 로 갈지, 서비스별 레포(repo-per-service)로 갈지.",
            "options": ["MONOREPO", "REPO_PER_SERVICE"],
            "recommended": "REPO_PER_SERVICE",
            "rationale": "마이크로서비스 → 서비스별 독립 릴리스에 repo-per-service 적합.",
        }

    # 마이크로서비스 전용 후속 질문
    if a.get("architectureStyle") == "MICROSERVICES":
        if a.get("repoStrategy") == "REPO_PER_SERVICE" and "repoMode" not in a:
            return {
                "index": 4, "field": "repoMode",
                "question": "레포 모드는? 기존 레포를 git 분리할지, 이미 있는 레포를 재사용할지.",
                "options": ["SPLIT_GIT", "REUSE_EXISTING"],
                "recommended": "SPLIT_GIT", "rationale": "신규 서비스 경계가 명확하면 분리가 깔끔.",
            }
        if "deploymentTarget" not in a:
            return {
                "index": 5, "field": "deploymentTarget",
                "question": "배포 대상은? 어디에 배포하나요.",
                "options": ["Kubernetes", "VM / Docker Compose", "Serverless"],
                "recommended": "Kubernetes", "rationale": "다수 서비스의 독립 확장·롤아웃에 표준.",
            }
        if "messaging" not in a:
            return {
                "index": 6, "field": "messaging",
                "question": "서비스 간 연동/메시징은? 기본은 이벤트 드리븐 pub/sub.",
                "options": ["Kafka (이벤트 드리븐 pub/sub)", "RabbitMQ", "REST/gRPC 동기 호출"],
                "recommended": "Kafka (이벤트 드리븐 pub/sub)", "rationale": "느슨한 결합·확장성. 동기는 꼭 필요한 곳만.",
            }
    return None


def _apply_rec(q: Optional[dict]) -> Optional[dict]:
    """Claude 분석 추천(_recs)이 있으면 해당 질문의 recommended/rationale 를 덮어쓴다."""
    if not q:
        return q
    r = _recs.get(q.get("field"))
    if r:
        if r.get("recommended"):
            q["recommended"] = r["recommended"]
        if r.get("rationale"):
            q["rationale"] = r["rationale"]
        q["fromAnalysis"] = True
    return q


def next_question() -> Optional[dict]:
    """현재 답변 상태에서 다음 게이팅 질문(없으면 None=합성 준비 완료).
    제안 분석 추천이 있으면 반영한다."""
    return _apply_rec(_next_question())


def _intent_summary() -> str:
    """제안 의도 요약(BC 제목들). 제안 맥락이 없으면 그래프 BC."""
    return ", ".join(_bc_names()) or "(없음)"


def _analysis_prompt() -> str:
    """Claude Code 가 제안을 분석해 게이팅 영역별 추천을 내도록 하는 프롬프트.
    질문/헌장 작성은 하지 말고 recommendations 만 출력하게 한다."""
    ctx = _proposal_ctx or {}
    bcs = _bc_names()
    return (
        "phase: CONSTITUTION\n"
        f"Proposal ID: {ctx.get('id','')}\n"
        f"원본 프롬프트(자연어 요구사항): {ctx.get('prompt','')}\n\n"
        f"제안이 도입할 BoundedContext({len(bcs)}개): {', '.join(bcs) or '(아직 없음)'}\n\n"
        "이 제안을 분석해, 프로젝트 루트 헌장의 핵심 게이팅 결정 각각에 대한 **추천값과 한 줄 근거**를 제시하라. "
        "프롬프트에 드러난 기술 선호는 seededFrom 으로 인용하라. "
        "질문하거나 헌장 본문을 작성하지 말고, **분석 결과만** 아래 JSON 으로 출력하라:\n"
        "```json\n"
        '{ "action": "analysis",\n'
        '  "recommendations": [\n'
        '    {"area": "architectureStyle", "recommended": "MONOLITH|MICROSERVICES", "rationale": "BoundedContext 개수·결합도 근거"},\n'
        '    {"area": "techStack", "recommended": "<백엔드/프론트엔드/스토어>", "rationale": "..."},\n'
        '    {"area": "repoStrategy", "recommended": "MONOREPO|REPO_PER_SERVICE", "rationale": "..."}\n'
        "  ],\n"
        '  "seededFrom": ["<프롬프트 인용>"] }\n'
        "```\n"
        "근거에는 위 BoundedContext 개수와 도메인 특성을 반드시 반영하라(다수 컨텍스트·높은 fan-out → 마이크로서비스, 소수·CRUD → 모놀리스)."
    )


async def analyze_proposal() -> AsyncGenerator[tuple[str, dict], None]:
    """Plan 게이트 진입 — Claude Code 로 제안을 분석해 추천을 만들고, 첫 질문을 낸다.
    set_proposal_context() 가 선행되어야 한다(없으면 일반 첫 질문만)."""
    bcs = _bc_names()
    yield "phase", {"phase": "constitution_analyze", "message": "제안 분석 중..."}
    yield "log_line", {"text": f"[분석] 제안 {(_proposal_ctx or {}).get('id','')} — BoundedContext {len(bcs)}개: {', '.join(bcs) or '(없음)'}"}

    if _proposal_ctx is None:
        # 컨텍스트가 없으면 분석 없이 결정적 첫 질문만.
        yield "question", next_question()
        yield "done", {"pending": True}
        return

    output_lines: list[str] = []
    suppress_log = False
    try:
        async for line in run_skill_lines(_SKILL_ROOT, _SKILL_NAME, _analysis_prompt()):
            if line.startswith("TOOL:"):
                continue
            output_lines.append(line)
            stripped = line.strip()
            if stripped.startswith("```") or (not suppress_log and stripped in ("{", "[")):
                suppress_log = True
                continue
            if not suppress_log:
                yield "log_line", {"text": line}
    except Exception as e:
        # 분석 실패해도 인터뷰는 진행 가능(추천만 비게 됨).
        yield "log_line", {"text": f"[분석 경고] {e}"}

    data = extract_json("\n".join(output_lines)) or {}
    _recs.clear()
    for r in (data.get("recommendations") or []):
        area = r.get("area")
        if area:
            _recs[area] = {"recommended": r.get("recommended"), "rationale": r.get("rationale")}
            yield "log_line", {"text": f"[추천] {area}: {r.get('recommended','')} — {r.get('rationale','')}"}
    for s in (data.get("seededFrom") or []):
        yield "log_line", {"text": f"[시드] {s}"}

    SmartLogger.log("INFO", "constitution analysis done",
                    category="constitution.interview.analyze",
                    params={"proposalId": (_proposal_ctx or {}).get("id"), "recs": list(_recs.keys())})

    yield "log_line", {"text": "분석 완료 — 추천을 반영해 질문을 제시합니다."}
    yield "question", next_question()
    yield "done", {"pending": True}


def _synthesis_prompt() -> str:
    decided = "\n".join(f"- {k}: {v}" for k, v in _answers.items())
    bcs = ", ".join(_bc_names()) or "(없음)"
    ctx = _proposal_ctx or {}
    proposal_note = ""
    if ctx:
        proposal_note = (
            f"\n참고 — 이 헌장은 다음 제안 맥락에서 작성된다(설계 원칙에 반영):\n"
            f"원본 프롬프트: {ctx.get('prompt','')}\n"
        )
    return (
        "phase: CONSTITUTION\n"
        "프로젝트 루트 헌장(Constitution)을 작성한다. **아래 결정은 사용자가 인터뷰로 확정한 값**이므로 "
        "추가 질문 없이 그대로 반영하라(질문 금지).\n\n"
        f"확정된 결정:\n{decided}\n\n"
        f"도메인 BoundedContext: {bcs}\n"
        f"{proposal_note}\n"
        "위 결정을 바탕으로, spec-kit constitution 형식의 Markdown 본문(`raw`)을 작성하라. "
        "섹션: Core Principles / Technology Constraints / Architecture / Repository Strategy / Governance. "
        "모놀리스면 ingress/mesh/연동/서비스별환경은 'N/A'. "
        '반드시 `action:"done"` 으로, `raw` 와 `fields`(architectureStyle/repoStrategy/repoMode/techStack/designPrinciples)를 JSON 으로 출력하라.'
    )


async def stream_project_constitution() -> AsyncGenerator[tuple[str, dict], None]:
    yield "phase", {"phase": "constitution_interview", "message": "프로젝트 헌장 인터뷰 중..."}

    # 1) 다음 게이팅 질문이 있으면 결정적으로(즉시) 묻는다 — 스킬 호출 없음.
    q = _next_question()
    if q is not None:
        yield "log_line", {"text": f"[질문] {q['question']}"}
        if q.get("rationale"):
            yield "log_line", {"text": f"[추천] {q.get('recommended','')} — {q['rationale']}"}
        yield "question", q
        yield "done", {"pending": True}
        return

    # 2) 모든 게이팅 결정 확정 → 스킬로 헌장 Markdown 합성(한 번).
    yield "log_line", {"text": "모든 핵심 결정이 확정되었습니다. 헌장 본문을 작성합니다…"}
    SmartLogger.log("INFO", "constitution synthesis start",
                    category="constitution.interview.synth", params={"answers": list(_answers.keys())})

    output_lines: list[str] = []
    suppress_log = False
    async for line in run_skill_lines(_SKILL_ROOT, _SKILL_NAME, _synthesis_prompt()):
        if line.startswith("TOOL:"):
            continue
        output_lines.append(line)
        stripped = line.strip()
        if stripped.startswith("```") or (not suppress_log and stripped in ("{", "[")):
            suppress_log = True
            continue
        if not suppress_log:
            yield "log_line", {"text": line}

    data = extract_json("\n".join(output_lines))
    if not data or not isinstance(data, dict) or not data.get("raw"):
        yield "error", {"code": "CONSTITUTION_SYNTH_FAILED", "message": "헌장 본문 생성 실패 — 다시 시도하세요."}
        return

    raw_doc = data["raw"]
    fields = data.get("fields", {})
    h = store.upsert_project_constitution(raw_doc, fields)
    global _proposal_ctx
    _answers.clear()
    _recs.clear()
    _proposal_ctx = None

    yield "draft", {"raw": raw_doc}
    yield "done", {"raw": raw_doc, "fields": fields, "constitutionHash": h}
    SmartLogger.log("INFO", "constitution synthesis done",
                    category="constitution.interview.done", params={"hash": (h or "")[:8]})
