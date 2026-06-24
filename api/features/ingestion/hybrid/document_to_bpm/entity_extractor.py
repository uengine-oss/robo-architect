"""Document → BPM entity extraction (native fallback).

References (do NOT call; port only):
- uengine-oss/process-gpt-bpmn-extractor → src/pdf2bpmn/processgpt/process_definition_prompt.py
- uengine-oss/process-gpt-bpmn-extractor → pdf2bpmn_agent_executor.py

Returns a `ProcessBundle` of N `BpmSkeleton`s. A single-process document
produces a bundle of length 1 — unchanged downstream behavior.

HITL, DMN, and Skill.md generation are out of scope for v0.1 (see PRD).
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Optional

from langchain_core.messages import HumanMessage
from api.platform.llm_messages import build_system_message
from pydantic import BaseModel, Field

from api.features.ingestion.hybrid.contracts import (
    BpmActor,
    BpmFlowDTO,
    BpmGatewayDTO,
    BpmProcess,
    BpmSequenceDTO,
    BpmSkeleton,
    BpmTaskDTO,
    ProcessBundle,
)
from api.features.ingestion.ingestion_llm_runtime import get_llm
from api.platform.observability.smart_logger import SmartLogger


SYSTEM_PROMPT = """당신은 업무 프로세스 분석가입니다.
업무편람/매뉴얼/절차서에서 **여러 개의 업무 프로세스**를 추출하세요.

한 문서는 보통 1~N개의 업무 프로세스를 기술합니다. 예:
- "자동이체 계좌 등록", "자동이체 계좌 해지" → 2개 프로세스
- "회원가입", "비밀번호 재설정", "탈퇴" → 3개 프로세스

각 프로세스마다 다음 4가지를 추출하세요.

1) name (프로세스 이름): 한국어 명사구. 예: "자동이체 계좌 등록".
2) domain_keywords (도메인 키워드 3~8개): 이 프로세스를 분류·검색할 업종 용어 + 업무 활동 명사.
   일반 기술 용어(API, DB, transaction) 는 제외.
   예: ["자동이체", "계좌 등록", "실시간 인증", "카드번호"]
3) actors: 이 프로세스에서 업무를 수행하는 주체. 예: 신청자, 담당자, 승인자, 시스템.
4) tasks: 한 Actor가 한 의미 단위로 수행하는 업무 단계 목록 (주 흐름 순서).
   - 코드의 단일 함수가 아니라 "하나의 업무 활동" 단위.
   - 예: "신청 접수", "자격 검토", "승인 처리", "결과 통보".
5) gateways (분기점, 있을 때만): 업무 흐름이 **조건에 따라 갈라지는 지점**.
   - 문서에 "~에 따라", "~인 경우", "~면 …, 아니면 …", "분기", "판단", "결정" 같은
     표현이 있으면 그 분기점을 gateway 로 추출.
   - 예: "결제수단 종류 판단" → 분기: "은행"→[은행 본인확인], "카드"→[카드 본인확인].
   - 각 gateway: name(판단명) + after_task(이 판단 직전 Task 이름) +
     branches(각 갈래의 condition 라벨 + to_task 대상 Task 이름).
   - 분기가 없는 순수 선형 프로세스면 gateways 는 빈 배열로.

규칙:
- 기술 구현 상세(함수명, 라이브러리, SQL) 무시.
- 각 Task에 수행 Actor 를 매핑. Task 이름은 동사구로 짧게.
- 문서에 없는 내용은 만들어내지 마세요. gateway 의 after_task/to_task 는 반드시
  추출한 tasks 의 name 과 정확히 일치해야 합니다.
- 문서가 단일 프로세스만 기술하면 processes 길이 1 로 반환.
"""


_IDENTITY_SYSTEM_PROMPT = """업무 문서에서 프로세스 정체성을 추출합니다.

입력으로 (1) PDF 파일명 (2) 문서 첫 2페이지 텍스트 가 주어집니다.

다음 두 가지를 추출하세요:
- `name`: 이 프로세스의 한국어 대표 이름. 명사구. 파일명에 이미 있으면 그것을
  정제해서 사용 (경로/모듈 접미사 제거, 사람이 읽기 좋은 형태로).
- `domain_keywords`: 이 프로세스를 분류·검색하는 데 쓸 도메인 용어 3~8개.
  업종 용어 + 업무 활동 명사. 일반적인 기술 용어 (API, DB, transaction) 는 제외.
"""


class _ExtractedActor(BaseModel):
    name: str
    description: str = ""


class _ExtractedTask(BaseModel):
    name: str
    description: str = ""
    actor: str = Field(description="Actor name, must match one of the extracted actors for this process")
    source_section: str = ""


class _ExtractedBranch(BaseModel):
    condition: str = Field(description="Branch label / guard, e.g. '은행 자동납부'")
    to_task: str = Field(description="Target task name this branch leads to (must match a task name)")


class _ExtractedGateway(BaseModel):
    name: str = Field(description="Decision point name, e.g. '결제수단 종류 판단'")
    gateway_type: str = Field(
        default="exclusive",
        description="exclusive (배타적 택1) | parallel (동시) | inclusive (다중)",
    )
    after_task: str = Field(description="Name of the task this decision immediately follows")
    branches: list[_ExtractedBranch] = Field(
        default_factory=list, description="2+ alternative paths out of this gateway",
    )


class _ExtractedProcess(BaseModel):
    name: str = Field(description="Human-readable Korean process name (noun phrase)")
    domain_keywords: list[str] = Field(
        default_factory=list, max_length=8,
        description="3~8 domain terms for retrieval; exclude generic tech terms",
    )
    actors: list[_ExtractedActor]
    tasks: list[_ExtractedTask] = Field(description="Ordered along the main flow as they appear")
    gateways: list[_ExtractedGateway] = Field(
        default_factory=list,
        description="Decision/branch points; empty for a purely linear process",
    )


class _ExtractionResult(BaseModel):
    processes: list[_ExtractedProcess] = Field(
        default_factory=list,
        description="One entry per distinct business process in the document",
    )


class _ProcessIdentity(BaseModel):
    """Shape returned by `extract_process_identity` — lightweight name+keywords only."""

    name: str
    domain_keywords: list[str] = Field(default_factory=list, max_length=8)


def _process_id(pdf_name: str, session_id: str, process_name: str) -> str:
    raw = f"{pdf_name}|{session_id}|{process_name}".encode("utf-8")
    return f"proc_{hashlib.sha1(raw).hexdigest()[:12]}"


async def extract_bpm_from_document(
    text: str,
    *,
    session_id: str = "",
    source_pdf_name: Optional[str] = None,
) -> ProcessBundle:
    """Run a single LLM pass to extract N processes' Actor/Task/Sequence."""
    llm = get_llm()
    structured = llm.with_structured_output(_ExtractionResult)

    SmartLogger.log(
        "INFO", "Hybrid document→BPM extraction start",
        category="ingestion.hybrid.document_bpm",
        params={"chars": len(text)},
    )

    result: _ExtractionResult = await structured.ainvoke([
        build_system_message(SYSTEM_PROMPT),
        HumanMessage(content=f"문서:\n\n{text}\n\n추출하세요."),
    ])

    # Legacy safety: if the LLM returned an old-style (actors, tasks) without
    # processes, synthesize a single process so downstream never sees an empty
    # bundle. Shouldn't trigger with the new prompt but cheap insurance.
    processes_raw = result.processes or []
    if not processes_raw:
        return ProcessBundle(processes=[])

    skeletons: list[BpmSkeleton] = []
    for proc in processes_raw:
        actor_id_by_name: dict[str, str] = {}
        actors: list[BpmActor] = []
        for a in proc.actors:
            aid = f"actor_{uuid.uuid4().hex[:8]}"
            actor_id_by_name[a.name] = aid
            actors.append(BpmActor(
                id=aid, name=a.name,
                description=a.description or None,
            ))

        tasks: list[BpmTaskDTO] = []
        task_ids: list[str] = []
        task_id_by_name: dict[str, str] = {}
        for idx, t in enumerate(proc.tasks):
            tid = f"task_{uuid.uuid4().hex[:8]}"
            task_ids.append(tid)
            task_id_by_name[t.name.strip()] = tid
            actor_id = actor_id_by_name.get(t.actor)
            tasks.append(BpmTaskDTO(
                id=tid,
                name=t.name,
                description=t.description or None,
                sequence_index=idx,
                actor_ids=[actor_id] if actor_id else [],
                source_section=t.source_section or None,
            ))

        # Gateways + branch flows. Resolve after_task/to_task names against the
        # extracted tasks; skip a gateway whose anchor task can't be resolved
        # (LLM hallucinated a name) so we never persist a dangling decision.
        actor_of_task = {t.id: (t.actor_ids[0] if t.actor_ids else None) for t in tasks}
        gateways: list[BpmGatewayDTO] = []
        flows: list[BpmFlowDTO] = []
        for g in (proc.gateways or []):
            after_id = task_id_by_name.get((g.after_task or "").strip())
            targets = [(b.condition, task_id_by_name.get((b.to_task or "").strip()))
                       for b in (g.branches or [])]
            targets = [(cond, tid) for cond, tid in targets if tid]
            if not after_id or len(targets) < 2:
                continue  # not a real, resolvable branch point
            gw_id = f"gw_{uuid.uuid4().hex[:8]}"
            gw_actor = actor_of_task.get(after_id)
            gateways.append(BpmGatewayDTO(
                id=gw_id, name=g.name,
                gateway_type=(g.gateway_type or "exclusive").strip().lower(),
                actor_ids=[gw_actor] if gw_actor else [],
            ))
            flows.append(BpmFlowDTO(
                id=f"flow_{uuid.uuid4().hex[:8]}", source_id=after_id, target_id=gw_id,
            ))
            for cond, tid in targets:
                flows.append(BpmFlowDTO(
                    id=f"flow_{uuid.uuid4().hex[:8]}", source_id=gw_id, target_id=tid,
                    name=(cond or "").strip(),
                ))

        pid = _process_id(source_pdf_name or "", session_id, proc.name)
        process_dto = BpmProcess(
            id=pid,
            name=proc.name,
            domain_keywords=list(proc.domain_keywords or []),
            source_pdf_name=source_pdf_name,
            session_id=session_id,
            actor_ids=[a.id for a in actors],
            task_ids=task_ids,
        )
        for a in actors:
            a.process_id = pid
        for t in tasks:
            t.process_id = pid
        for g in gateways:
            g.process_id = pid
        for f in flows:
            f.process_id = pid
        sequence = BpmSequenceDTO(
            id=f"seq_{uuid.uuid4().hex[:8]}", name="Main",
            task_ids=task_ids, process_id=pid,
        )
        skeletons.append(BpmSkeleton(
            actors=actors, tasks=tasks, sequences=[sequence],
            gateways=gateways, flows=flows,
            process=process_dto,
        ))

    return ProcessBundle(processes=skeletons)


async def extract_process_identity(
    pdf_name: Optional[str],
    first_pages_text: str,
) -> _ProcessIdentity:
    """Lightweight LLM call to refine process name + domain_keywords from a
    PDF filename + first few pages. Used when the primary extractor (A2A or
    native) produced an empty/weak `BpmProcess.name` and we need to backfill.
    """
    llm = get_llm()
    structured = llm.with_structured_output(_ProcessIdentity)
    user = (
        f"PDF 파일명: {pdf_name or '(없음)'}\n\n"
        f"문서 첫 부분:\n{first_pages_text[:4000]}\n\n"
        f"이 프로세스의 `name` 과 `domain_keywords` 를 추출하세요."
    )
    return await structured.ainvoke([
        build_system_message(_IDENTITY_SYSTEM_PROMPT),
        HumanMessage(content=user),
    ])
