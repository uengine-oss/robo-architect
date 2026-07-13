"""회귀: 라이프사이클 스텝 테이블(SSOT)의 순서·게이트·가드 스냅샷.

spec Option B / ac.md:
- AC-4/AC-6: SIMPLIFIED·DETAILED_DDD 정규 순서 결정성(스냅샷 고정).
- AC-5: SIMPLIFIED 전술 Diff 게이트가 CONSTITUTION 앞.
- AC-8: 앞으로 건너뛰기 하드 차단(prior_requirement_unmet).
- AC-9: 사용자 명시 되돌리기 대상 목록(rollback_targets).
- AC-7: next_step 확장 명령형 액션 스키마.
- AC-11: 순서 단일 원천(이 테이블) — next_step 이 이를 파생.
"""

from __future__ import annotations

from api.features.proposal_lifecycle.services import lifecycle_steps as ls
from api.features.proposal_lifecycle.services import proposal_state_service


# --- 시뮬레이션 헬퍼 --------------------------------------------------------

def _complete(node: dict, step: ls.StepDef) -> None:
    phase, stage = step.phase, step.stage
    if stage is not None:
        node.setdefault("stageArtifacts", {})[stage] = {"ok": True}
        return
    if phase == "SCOPE":
        node["stagePlan"] = {"stages": [{"stage": s, "applies": True, "skipped": False} for s in ls.DDD_STAGE_ORDER]}
    elif phase == "STRATEGIC_DIFF":
        node["strategicDiff"] = {"epics": [{"op": "CREATE"}]}
    elif phase == "SUBMIT":
        node["status"] = "SUBMITTED"
    elif phase == "TACTICAL_DIFF":
        node["tacticalDiff"] = [{"nodeId": "A-1"}]
    elif phase == "PROJECT_CONSTITUTION":
        node["constitutionConfirmed"] = True
    elif phase == "CONSTITUTION":
        node["implementationPlan"] = {"architectureDecisions": [{"aspect": "DEPLOYMENT_ENV"}]}
    elif phase == "TASKS":
        node["tasksJson"] = [{"id": "T1"}]
    elif phase == "IMPLEMENT":
        node["implementationStatus"] = "DONE"
    elif phase == "TEST":
        node["testResults"] = {"passed": True}
    elif phase == "ACCEPT":
        node["status"] = "ACCEPTED"


def _walk(mode: str) -> list[tuple[str, str | None]]:
    node = {"decompositionMode": mode, "status": "DRAFT"}
    seq: list[tuple[str, str | None]] = []
    guard = 0
    while True:
        step = ls.next_incomplete_step(node)
        if step is None:
            break
        seq.append((step.phase, step.stage))
        _complete(node, step)
        guard += 1
        assert guard < 40, "sequence did not terminate"
    return seq


# --- AC-4: SIMPLIFIED 스냅샷 ------------------------------------------------

def test_simplified_sequence_snapshot():
    assert _walk("SIMPLIFIED") == [
        ("STRATEGIC_DIFF", None),
        ("SUBMIT", None),
        ("TACTICAL_DIFF", None),
        ("PROJECT_CONSTITUTION", None),
        ("CONSTITUTION", None),
        ("TASKS", None),
        ("IMPLEMENT", None),
        ("TEST", None),
        ("ACCEPT", None),
    ]


# --- AC-5: 전술 게이트가 CONSTITUTION 앞 -----------------------------------

def test_simplified_tactical_gate_before_constitution():
    seq = [p for p, _ in _walk("SIMPLIFIED")]
    assert seq.index("TACTICAL_DIFF") < seq.index("CONSTITUTION")
    # submit 직후 첫 게이트가 전술 Diff.
    assert seq[seq.index("SUBMIT") + 1] == "TACTICAL_DIFF"
    # 015-issue3: 전술 Diff 확정 후 구현계획 전에 **프로젝트 헌장 노드** 게이트를 지난다.
    assert seq[seq.index("TACTICAL_DIFF") + 1] == "PROJECT_CONSTITUTION"
    assert seq.index("PROJECT_CONSTITUTION") < seq.index("TASKS")


# --- AC-6: DETAILED_DDD 스냅샷 ----------------------------------------------

def test_detailed_sequence_snapshot():
    assert _walk("DETAILED_DDD") == [
        ("SCOPE", None),
        ("STRATEGIC_DDD", "DISCOVER"),
        ("STRATEGIC_DDD", "DECOMPOSE"),
        ("STRATEGIC_DDD", "STRATEGIZE"),
        ("STRATEGIC_DIFF", None),
        ("SUBMIT", None),
        ("TACTICAL_DDD", "CONNECT"),
        ("TACTICAL_DDD", "DEFINE"),
        ("TACTICAL_DDD", "TACTICAL"),
        ("TACTICAL_DIFF", None),
        ("PROJECT_CONSTITUTION", None),
        ("CONSTITUTION", None),
        ("TASKS", None),
        ("IMPLEMENT", None),
        ("TEST", None),
        ("ACCEPT", None),
    ]


def test_detailed_strategic_diff_between_strategy_and_tactical_stages():
    seq = [(p, s) for p, s in _walk("DETAILED_DDD")]
    phases = [p for p, _ in seq]
    # 전략 3단계 → STRATEGIC_DIFF → 전술 3단계 순.
    assert phases.index("STRATEGIC_DIFF") > phases.index("STRATEGIC_DDD")
    connect_idx = seq.index(("TACTICAL_DDD", "CONNECT"))
    assert phases.index("STRATEGIC_DIFF") < connect_idx


def test_detailed_skipped_tactical_stage_is_omitted():
    node = {
        "decompositionMode": "DETAILED_DDD",
        "status": "DRAFT",
        "stagePlan": {"stages": [
            {"stage": s, "applies": True, "skipped": s == "CONNECT"}
            for s in ls.DDD_STAGE_ORDER
        ]},
    }
    stage_steps = [st.stage for st in ls.active_steps(node) if st.stage]
    assert "CONNECT" not in stage_steps
    assert "DEFINE" in stage_steps


# --- AC-8: 하드 전이 가드 ---------------------------------------------------

def test_guard_blocks_tactical_diff_without_strategic():
    node = {"decompositionMode": "SIMPLIFIED", "status": "DRAFT"}
    assert ls.prior_requirement_unmet(node, "TACTICAL_DIFF", None) is True


def test_guard_blocks_decompose_without_discover():
    node = {
        "decompositionMode": "DETAILED_DDD",
        "status": "DRAFT",
        "stagePlan": {"stages": [{"stage": s, "applies": True, "skipped": False} for s in ls.DDD_STAGE_ORDER]},
        "stageArtifacts": {},
    }
    assert ls.prior_requirement_unmet(node, "STRATEGIC_DDD", "DECOMPOSE") is True


def test_guard_allows_strategic_diff_first_step():
    node = {"decompositionMode": "SIMPLIFIED", "status": "DRAFT"}
    assert ls.prior_requirement_unmet(node, "STRATEGIC_DIFF", None) is False


def test_guard_allows_tactical_diff_after_strategic_and_submit():
    node = {
        "decompositionMode": "SIMPLIFIED",
        "status": "SUBMITTED",
        "strategicDiff": {"epics": [{"op": "CREATE"}]},
    }
    assert ls.prior_requirement_unmet(node, "TACTICAL_DIFF", None) is False


# --- AC-9: 되돌리기 대상 ----------------------------------------------------

def test_rollback_targets_at_constitution():
    node = {
        "decompositionMode": "SIMPLIFIED",
        "status": "SUBMITTED",
        "strategicDiff": {"epics": [{"op": "CREATE"}]},
        "tacticalDiff": [{"nodeId": "A-1"}],
    }
    # 다음 미완료 = CONSTITUTION. 되돌리기 대상 = STRATEGIC_DIFF, TACTICAL_DIFF(완료·rollback_target).
    targets = {(t["phase"], t["stage"]) for t in ls.rollback_targets(node)}
    assert ("STRATEGIC_DIFF", None) in targets
    assert ("TACTICAL_DIFF", None) in targets


def test_downstream_of_lists_later_canonical_steps():
    node = {
        "decompositionMode": "SIMPLIFIED",
        "status": "SUBMITTED",
        "strategicDiff": {"epics": [{"op": "CREATE"}]},
        "tacticalDiff": [{"nodeId": "A-1"}],
        "implementationPlan": {"architectureDecisions": [{"aspect": "DEPLOYMENT_ENV"}]},
    }
    fields = {st.canonical_field for st in ls.downstream_of(node, "STRATEGIC_DIFF", None)}
    assert "tacticalDiff" in fields
    assert "implementationPlan" in fields


# --- AC-7 / AC-11: next_step 확장 스키마 + 테이블 파생 ------------------------

def test_next_step_extended_action_schema(monkeypatch):
    node = {"id": "PRO-x", "decompositionMode": "SIMPLIFIED", "status": "DRAFT"}
    monkeypatch.setattr(proposal_state_service, "get_node", lambda pid: node)
    result = proposal_state_service.next_step("PRO-x")
    assert result["status"] == "ok"
    ns = result["nextStep"]
    for key in ("phase", "stage", "action", "requiresUserApproval", "validationRef",
                "reason", "allowedUserOverrides", "retryContext", "staleArtifacts"):
        assert key in ns, f"missing field {key}"
    assert ns["action"] in ls.ALL_ACTIONS
    assert ns["phase"] == "STRATEGIC_DIFF"


def test_next_step_simplified_tactical_after_submit(monkeypatch):
    node = {
        "id": "PRO-y", "decompositionMode": "SIMPLIFIED", "status": "SUBMITTED",
        "strategicDiff": {"epics": [{"op": "CREATE"}]},
    }
    monkeypatch.setattr(proposal_state_service, "get_node", lambda pid: node)
    result = proposal_state_service.next_step("PRO-y")
    assert result["nextStep"]["phase"] == "TACTICAL_DIFF"
    assert result["nextStep"]["action"] == ls.GENERATE_DRAFT


def test_next_step_pending_draft_awaits_approval(monkeypatch):
    node = {
        "id": "PRO-z", "decompositionMode": "SIMPLIFIED", "status": "DRAFT",
        "pendingDraftId": "PI-1", "currentPhase": "STRATEGIC_DIFF",
    }
    monkeypatch.setattr(proposal_state_service, "get_node", lambda pid: node)
    result = proposal_state_service.next_step("PRO-z")
    assert result["nextStep"]["action"] == ls.AWAIT_APPROVAL
    assert result["nextStep"]["requiresUserApproval"] is True


def test_next_step_forward_jump_blocked(monkeypatch):
    node = {"id": "PRO-j", "decompositionMode": "SIMPLIFIED", "status": "DRAFT"}
    monkeypatch.setattr(proposal_state_service, "get_node", lambda pid: node)
    result = proposal_state_service.next_step("PRO-j", phase="TACTICAL_DIFF")
    assert result["status"] == "blocked"
    assert result["reason"]["reason"] == "invalid-transition"


# --- AC-6 regression: strategicMemory promotion wiring locked -----------------

class _FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def run(self, *a, **k):
        return None


def _patch_stage_save(monkeypatch, stage):
    """Isolate staged_runner.save_stage_artifact from Neo4j and spy on promotion."""
    from api.features.proposal_lifecycle.services import staged_runner, strategic_memory

    monkeypatch.setattr(staged_runner, "load_state",
                        lambda pid: {"stageArtifacts": {}, "stagePlan": None})
    monkeypatch.setattr(staged_runner, "get_session", lambda: _FakeSession())
    monkeypatch.setattr(staged_runner.proposal_state_service, "get_node", lambda pid: {})
    monkeypatch.setattr(staged_runner.proposal_state_service, "refresh_current_phase", lambda pid: None)
    calls = []
    monkeypatch.setattr(strategic_memory, "promote", lambda st, art, *a, **k: calls.append(st))
    return staged_runner, calls


def test_save_stage_artifact_promotes_strategic_stages(monkeypatch):
    for stage in ("STRATEGIZE", "CONNECT", "DEFINE"):
        runner, calls = _patch_stage_save(monkeypatch, stage)
        runner.save_stage_artifact("PRO-mem", stage, {"any": True})
        assert calls == [stage], f"{stage} must promote to strategicMemory"


def test_save_stage_artifact_does_not_promote_non_strategic_stages(monkeypatch):
    for stage in ("DISCOVER", "DECOMPOSE", "TACTICAL"):
        runner, calls = _patch_stage_save(monkeypatch, stage)
        runner.save_stage_artifact("PRO-mem", stage, {"any": True})
        assert calls == [], f"{stage} must NOT promote to strategicMemory"


# --- 015-issue3: TASKS 는 헌장/구현계획 게이트를 우회할 수 없다 -----------------

def test_tasks_blocked_until_project_constitution_and_plan():
    """헌장 노드(PROJECT_CONSTITUTION) 미확정 상태에서 TASKS 로 건너뛰기는 하드 차단된다."""
    node = {"decompositionMode": "SIMPLIFIED", "status": "SUBMITTED",
            "strategicDiff": {"epics": [{"op": "CREATE"}]},
            "tacticalDiff": [{"nodeId": "A-1"}]}
    # 전술 Diff 까지 끝났지만 헌장·구현계획이 없음 → TASKS 차단.
    assert ls.prior_requirement_unmet(node, "TASKS") is True
    assert ls.next_incomplete_step(node).phase == "PROJECT_CONSTITUTION"

    # 헌장만 확정 → 구현계획이 아직 없으므로 여전히 차단.
    node["constitutionConfirmed"] = True
    assert ls.prior_requirement_unmet(node, "TASKS") is True
    assert ls.next_incomplete_step(node).phase == "CONSTITUTION"

    # 구현계획까지 확정 → TASKS 허용.
    node["implementationPlan"] = {"architectureDecisions": [{"aspect": "FRONTEND"}]}
    assert ls.prior_requirement_unmet(node, "TASKS") is False
    assert ls.next_incomplete_step(node).phase == "TASKS"


def test_implement_and_test_flags_cannot_be_preempted():
    """015: 구현/테스트 완료 플래그를 앞 단계 없이 선점하지 못한다(ACCEPT 게이트 무력화 방지)."""
    node = {"decompositionMode": "SIMPLIFIED", "status": "DRAFT"}
    # 아무 산출물도 없는 상태 → IMPLEMENT(완료 표시)·TEST(결과 저장) 모두 차단.
    assert ls.prior_requirement_unmet(node, "IMPLEMENT") is True
    assert ls.prior_requirement_unmet(node, "TEST") is True
    assert ls.prior_requirement_unmet(node, "ACCEPT") is True

    # 태스크 확정까지 마치면 IMPLEMENT 는 허용되지만 TEST 는 여전히 구현 완료를 요구.
    node.update({
        "status": "SUBMITTED",
        "strategicDiff": {"epics": [{"op": "CREATE"}]},
        "tacticalDiff": [{"nodeId": "A-1"}],
        "constitutionConfirmed": True,
        "implementationPlan": {"architectureDecisions": [{"aspect": "FRONTEND"}]},
        "tasksJson": [{"id": "T1"}],
    })
    assert ls.prior_requirement_unmet(node, "IMPLEMENT") is False
    assert ls.prior_requirement_unmet(node, "TEST") is True

    node["implementationStatus"] = "DONE"
    assert ls.prior_requirement_unmet(node, "TEST") is False
