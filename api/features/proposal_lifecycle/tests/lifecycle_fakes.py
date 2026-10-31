"""Proposal 수명주기 단위 테스트용 가짜 객체 (실 Neo4j · git · Claude CLI 미사용).

- ``FakeGraph``: ``session.run(query, **params)`` 를 기록하고, 수명주기 코드가 실제로
  보내는 Cypher 몇 가지를 흉내 낸다(Proposal 상태 갱신, 노드 CREATE/MERGE, 관계 MERGE,
  live projection count, EFFECT 조회·삭제). 테스트는 ``graph.runs`` 로 "그래프에 무엇을
  썼는지"를, ``graph.nodes``/``graph.rels`` 로 "결과적으로 무엇이 남았는지"를 확인한다.
  Neo4j ``session.run`` 은 auto-commit 이므로 이 가짜도 즉시 반영한다. 명시적
  트랜잭션(``begin_transaction``/``execute_write``)을 쓰면 롤백 시 이전 상태로 되돌린다.
- ``FakeSandbox``: ``SandboxManager`` 대역. 호출 순서와 인자를 기록한다.
- ``forbid_real_backends``: 패치를 빠뜨린 경로가 실 DB·Claude CLI 로 새지 않도록 막는다.
- ``capture_logs``: ``SmartLogger.log`` 호출을 수집한다.
"""

from __future__ import annotations

import copy
import re
from contextlib import contextmanager
from dataclasses import dataclass, field


def norm(query: str) -> str:
    """공백·줄바꿈을 한 칸으로 접어 부분 문자열 비교를 쉽게 한다."""
    return " ".join(query.split())


class FakeResult:
    def __init__(self, record=None, rows=None):
        self._record = record
        self._rows = rows if rows is not None else ([] if record is None else [record])

    def single(self):
        return self._record

    def data(self):
        return list(self._rows)


_MATCH_VAR = re.compile(r"\((\w+):(\w+) \{id: \$(\w+)\}\)")
_REL_MERGE = re.compile(r"MERGE \((\w+)\)-\[\w*:(\w+)\]->\((\w+)\)")
_CREATE_NODE = re.compile(r"(?<!ON )CREATE \((\w+):(\w+) \{")
_MERGE_NODE = re.compile(r"MERGE \(n:(\w+) \{id: \$id\}\)")
_SET_STATUS = re.compile(r"SET p\.status = '(\w+)'")
_GET_FIELD = re.compile(r"MATCH \(n:(\w+) \{id: \$id\}\) RETURN n\.(\w+) AS v")
_SET_FIELD = re.compile(r"MATCH \(n:(\w+) \{id: \$id\}\) SET n\.(\w+) = \$v")
_BY_NAME = re.compile(r"MATCH \(n:(\w+)\) WHERE n\.name = \$name OR n\.title = \$name")
_BY_ID_OR_KEY = re.compile(r"MATCH \(n:(\w+)\) WHERE n\.id = \$ref OR n\.key = \$ref")
_COUNT_LABEL = re.compile(r"MATCH \(n:(\w+) \{proposalSource: \$pid\}\) RETURN count\(n\) AS c")
_DETACH_BY_ID = re.compile(r"MATCH \(n:(\w+) \{id: \$id\}\) OPTIONAL MATCH .* DETACH DELETE child, n")

_CHILD_LABELS = {"Property", "Given", "When", "Then", "UI", "Invariant", "Journey", "JourneyStep"}


class FakeGraph:
    """하나의 Proposal 노드 + 설계 그래프를 흉내 내는 세션 겸 저장소."""

    def __init__(self, proposal: dict | None):
        self.proposal = dict(proposal) if proposal is not None else None
        self.nodes: dict[str, dict] = {}
        self.rels: list[dict] = []
        self.runs: list[tuple[str, dict]] = []
        self.fail_when = None  # callable(q, params) -> bool : True 면 RuntimeError
        self.tx_log: list[str] = []

    # --- get_session 대역 ------------------------------------------------
    @contextmanager
    def session(self, *args, **kwargs):
        yield self

    def begin_transaction(self):
        return _FakeTx(self)

    def execute_write(self, fn, *args, **kwargs):
        tx = _FakeTx(self)
        try:
            out = fn(tx, *args, **kwargs)
        except Exception:
            tx.rollback()
            raise
        tx.commit()
        return out

    # --- 조회 도우미 -------------------------------------------------------
    def queries(self, needle: str) -> list[tuple[str, dict]]:
        return [(q, p) for q, p in self.runs if needle in q]

    def nodes_of(self, label: str) -> list[dict]:
        return [n for n in self.nodes.values() if n["label"] == label]

    def rels_of(self, rel_type: str) -> list[dict]:
        return [r for r in self.rels if r["type"] == rel_type]

    def history(self) -> list[dict]:
        import json
        raw = (self.proposal or {}).get("statusHistory") or "[]"
        return json.loads(raw) if isinstance(raw, str) else list(raw)

    # --- Cypher 흉내 --------------------------------------------------------
    def run(self, query: str, **params):
        q = norm(query)
        self.runs.append((q, params))
        if self.fail_when is not None and self.fail_when(q, params):
            raise RuntimeError(f"fake neo4j failure on: {q[:60]}")

        p = self.proposal
        if "MATCH (p:Proposal {id: $id}) RETURN p {.*} AS p" in q:
            if p is None or params.get("id") != p.get("id"):
                return FakeResult(None)
            return FakeResult({"p": dict(p)})
        if "MATCH (p:Proposal {id: $id})" in q and "RETURN" in q and "SET" not in q:
            if p is None or params.get("id") != p.get("id"):
                return FakeResult(None)
            if "p.projectRoot AS root" in q:
                return FakeResult({"root": p.get("projectRoot")})
            if "p.strategicDiff AS sd" in q:
                return FakeResult({
                    "sd": p.get("strategicDiff"), "td": p.get("tacticalDiff"),
                    "jny": p.get("journeys"), "history": p.get("statusHistory"),
                    "status": p.get("status"),
                })
            if "p.statusHistory AS history" in q:
                return FakeResult({"history": p.get("statusHistory")})
            return FakeResult(None)

        m = _SET_STATUS.search(q)
        if m and "MATCH (p:Proposal {id: $id})" in q:
            if p is not None and params.get("id") == p.get("id"):
                p["status"] = m.group(1)
                if "history" in params:
                    p["statusHistory"] = params["history"]
                if "p.acceptedAt = datetime($at)" in q:
                    p["acceptedAt"] = params.get("at")
                if "p.destroyedAt = datetime($at)" in q:
                    p["destroyedAt"] = params.get("at")
                if "p.sandboxStatus = 'DESTROYED'" in q:
                    p["sandboxStatus"] = "DESTROYED"
                if "REMOVE p.acceptedAt" in q:
                    p.pop("acceptedAt", None)
            return FakeResult(None)

        # live projection 검증 쿼리
        m = _COUNT_LABEL.search(q)
        if m:
            pid = params.get("pid")
            c = sum(1 for n in self.nodes.values()
                    if n["label"] == m.group(1) and n.get("proposalSource") == pid)
            return FakeResult({"c": c})
        if "HAS_AGGREGATE]->(:Aggregate {proposalSource: $pid}) RETURN count(*) AS c" in q:
            pid = params.get("pid")
            c = sum(1 for r in self.rels_of("HAS_AGGREGATE")
                    if self.nodes.get(r["from"], {}).get("proposalSource") == pid
                    and self.nodes.get(r["to"], {}).get("proposalSource") == pid)
            return FakeResult({"c": c})

        # revoke: EFFECT 조회/삭제, 생성 노드 삭제
        if "MATCH (p:Proposal {id: $pid})-[e:EFFECT]->(n) RETURN" in q:
            rows = []
            for r in self.rels_of("EFFECT"):
                if r["from"] != params.get("pid"):
                    continue
                node = self.nodes.get(r["to"])
                rows.append({"nodeId": r["to"], "labels": [node["label"]] if node else [],
                             "diff": r["props"].get("diff"), "ct": r["props"].get("changeType")})
            return FakeResult(None, rows)
        m = _DETACH_BY_ID.search(q)
        if m:
            self._delete_node(params.get("id"), with_children=True)
            return FakeResult(None)
        if "MATCH (c {proposalSource: $pid})" in q and "DETACH DELETE c" in q:
            for nid in [i for i, n in self.nodes.items()
                        if n["label"] in _CHILD_LABELS and n.get("proposalSource") == params.get("pid")]:
                self._delete_node(nid)
            return FakeResult(None)
        if "-[e:EFFECT]->() DELETE e" in q:
            self.rels = [r for r in self.rels
                         if not (r["type"] == "EFFECT" and r["from"] == params.get("pid"))]
            return FakeResult(None)

        # 설계 노드 조회/갱신
        m = _BY_NAME.search(q)
        if m:
            for nid, n in self.nodes.items():
                if n["label"] == m.group(1) and params.get("name") in (n.get("name"), n.get("title")):
                    return FakeResult({"id": nid})
            return FakeResult(None)
        m = _BY_ID_OR_KEY.search(q)
        if m:
            ref = params.get("ref")
            for nid, n in self.nodes.items():
                if n["label"] == m.group(1) and ref in (nid, n.get("key")):
                    return FakeResult({"id": nid})
            return FakeResult(None)
        m = _GET_FIELD.search(q)
        if m:
            node = self.nodes.get(params.get("id"))
            return FakeResult({"v": node.get(m.group(2))} if node else None)
        m = _SET_FIELD.search(q)
        if m:
            node = self.nodes.get(params.get("id"))
            if node is not None:
                node[m.group(2)] = params.get("v")
            return FakeResult(None)

        # 노드 생성
        for m in _CREATE_NODE.finditer(q):
            nid = params.get("id")
            if nid:
                self.nodes[nid] = {"label": m.group(2), "id": nid, "name": params.get("name"),
                                   "key": params.get("key"), "proposalSource": params.get("pid")}
        m = _MERGE_NODE.search(q)
        if m:
            nid = params.get("id")
            self.nodes.setdefault(nid, {"label": m.group(1), "id": nid, "key": params.get("key"),
                                        "proposalSource": params.get("pid")})

        # 관계 MERGE
        m = _REL_MERGE.search(q)
        if m:
            var_ids = {v: params.get(pn) for v, _lbl, pn in _MATCH_VAR.findall(q)}
            src, rel_type, dst = var_ids.get(m.group(1)), m.group(2), var_ids.get(m.group(3))
            if src and dst:
                existing = next((r for r in self.rels if (r["type"], r["from"], r["to"]) == (rel_type, src, dst)), None)
                props = {}
                if rel_type == "EFFECT":
                    props = {"changeType": params.get("ct"), "diff": params.get("diff"),
                             "reason": params.get("reason")}
                if existing is None:
                    self.rels.append({"type": rel_type, "from": src, "to": dst, "props": props})
                else:
                    existing["props"].update(props)
        return FakeResult(None)

    def _delete_node(self, nid, with_children: bool = False):
        if not nid:
            return
        if with_children:
            child_ids = [r["to"] for r in self.rels if r["from"] == nid
                         and r["type"] in ("HAS_PROPERTY", "HAS_GIVEN", "HAS_WHEN", "HAS_THEN", "HAS_INVARIANT")]
            for cid in child_ids:
                self._delete_node(cid)
        self.nodes.pop(nid, None)
        self.rels = [r for r in self.rels if nid not in (r["from"], r["to"])]


class _FakeTx:
    def __init__(self, graph: FakeGraph):
        self._g = graph
        self._snap = (copy.deepcopy(graph.nodes), copy.deepcopy(graph.rels), copy.deepcopy(graph.proposal))
        self._open = True
        graph.tx_log.append("begin")

    def run(self, query, **params):
        return self._g.run(query, **params)

    def commit(self):
        self._open = False
        self._g.tx_log.append("commit")

    def rollback(self):
        if self._open:
            self._g.nodes, self._g.rels, self._g.proposal = self._snap
            self._open = False
            self._g.tx_log.append("rollback")

    def close(self):
        if self._open:
            self.rollback()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.rollback()
        else:
            self.close()
        return False


@dataclass
class FakeMergeResult:
    success: bool
    error: str | None = None


@dataclass
class FakeSandbox:
    """SandboxManager 대역 — 호출 기록만 남기고 git 은 건드리지 않는다."""

    merge_ok: bool = True
    merge_error: str | None = None
    revert_ok: bool = True
    revert_error: str | None = None
    cleanup_raises: Exception | None = None
    remove_raises: Exception | None = None
    calls: list = field(default_factory=list)

    def merge_to_main(self, proposal_id, project_root):
        self.calls.append(("merge_to_main", proposal_id, project_root))
        return FakeMergeResult(self.merge_ok, self.merge_error)

    def reset_merge(self, proposal_id, project_root):
        self.calls.append(("reset_merge", proposal_id, project_root))

    def cleanup_worktree(self, proposal_id, project_root):
        self.calls.append(("cleanup_worktree", proposal_id, project_root))
        if self.cleanup_raises:
            raise self.cleanup_raises

    def remove_worktree(self, proposal_id, project_root):
        self.calls.append(("remove_worktree", proposal_id, project_root))
        if self.remove_raises:
            raise self.remove_raises

    def revert_merge_commit(self, proposal_id, project_root):
        self.calls.append(("revert_merge_commit", proposal_id, project_root))
        return FakeMergeResult(self.revert_ok, self.revert_error)

    def names(self) -> list[str]:
        return [c[0] for c in self.calls]


def forbid_real_backends(monkeypatch) -> None:
    """패치를 빠뜨려 실 Neo4j 드라이버나 Claude 스킬 실행으로 새면 즉시 실패시킨다."""
    import api.platform.neo4j as neo4j_mod
    import api.platform.skill_runner as skill_runner_mod

    def _no_db(*_a, **_k):
        raise AssertionError("unit test attempted a real Neo4j connection")

    def _no_skill(*_a, **_k):
        raise AssertionError("unit test attempted to run a real Claude skill")

    monkeypatch.setattr(neo4j_mod, "get_driver", _no_db)
    monkeypatch.setattr(neo4j_mod, "init_neo4j_driver", _no_db)
    monkeypatch.setattr(neo4j_mod, "_driver_for", _no_db)
    monkeypatch.setattr(skill_runner_mod, "skill_path", _no_skill)


def capture_logs(monkeypatch) -> list[dict]:
    """SmartLogger.log 호출을 [{level, message, category, params}] 로 수집한다."""
    from api.platform.observability.smart_logger import SmartLogger

    logs: list[dict] = []

    def _log(cls, level, message, category=None, params=None, max_inline_chars=100):
        logs.append({"level": level, "message": message, "category": category, "params": params or {}})

    monkeypatch.setattr(SmartLogger, "log", classmethod(_log))
    return logs


def fake_skill_lines(lines=None, raises: Exception | None = None, calls: list | None = None):
    """run_skill_lines 대역(async generator). 받은 인자를 calls 에 남긴다."""

    async def _gen(skill_root, skill_name, human_prompt, *args, **kwargs):
        if calls is not None:
            calls.append({"root": skill_root, "name": skill_name, "prompt": human_prompt})
        for line in (lines or []):
            yield line
        if raises is not None:
            raise raises

    return _gen
