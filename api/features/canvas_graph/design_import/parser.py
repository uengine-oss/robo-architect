"""Deterministic parser: EventStorming-canvas Markdown → normalized DesignModel.

Recognised convention (the legend used by the ODA canvases and the project's own
DDD skills):
  🟧 Event · 🟦 Command · 🟪 Policy · 🟩 Read Model · 🟨 Actor · 🟫 External · 🍐 Aggregate

A "BC section" = a heading immediately followed by a `| 종류 | 항목 | … |` table.
Cross-BC reaction spines may be declared in a fenced code block as lines like:
    ProductOrderAccepted ─P─▶ CreateServiceOrder ─▶ ServiceOrderCreated

No LLM. Pure functions → same input yields the same DesignModel.

DesignModel = {
  "boundedContexts": [ {
      "name": str, "display": str, "description": str,
      "aggregates": [ {"name": str, "invariants": [str]} ],
      "commands":   [ {"name": str, "actor": str, "aggregate": str|None,
                       "emits": [ {"name": str, "displayName": str} ] } ],
      "readModels": [ str ],
      "policies":   [ {"name": str, "trigger": str|None, "invoke": str|None} ],
  } ],
  "warnings": [ str ],
}
"""
from __future__ import annotations

import re

# 종류(kind) 셀 → 분류
_KIND = [
    ("aggregate", ("🍐", "aggregate", "애그리거트")),
    ("command", ("🟦", "command", "명령", "커맨드")),
    ("event", ("🟧", "event", "이벤트")),
    ("policy", ("🟪", "policy", "정책")),
    ("readmodel", ("🟩", "read model", "readmodel", "read-model", "리드 모델", "리드모델", "조회")),
    ("actor", ("🟨", "actor", "액터")),
    ("external", ("🟫", "external", "외부")),
]

_SPLIT = re.compile(r"\s*(?:,|/|·|、)\s*")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_BACKTICK = re.compile(r"`([^`]*)`")
_STARS = re.compile(r"[⭐★]")
_PAREN = re.compile(r"\s*[\(（].*?[\)）]\s*")
# camel/Pascal identifier (Command/Event/Aggregate canonical token)
_IDENT = re.compile(r"[A-Za-z][A-Za-z0-9]+")
# Policy chain line:  <Event> ─P─▶ <Command> [─▶ <Event2>]
_CHAIN = re.compile(r"([A-Za-z][A-Za-z0-9]+)\s*[─-]+\s*P\s*[─-]*[▶>]+\s*([A-Za-z][A-Za-z0-9]+)")


def _classify_kind(cell: str) -> str | None:
    low = cell.strip().lower()
    for kind, needles in _KIND:
        for n in needles:
            if n in low:
                return kind
    return None


def _clean(text: str) -> str:
    text = _BOLD.sub(r"\1", text)
    text = _BACKTICK.sub(r"\1", text)
    text = _STARS.sub("", text)
    return text.strip()


def _canonical_name(token: str) -> str:
    """첫 식별자(PascalCase)를 노드 이름으로. 없으면 정리된 텍스트."""
    t = _clean(token)
    t_noparen = _PAREN.sub("", t).strip()
    m = _IDENT.search(t_noparen)
    return m.group(0) if m else t_noparen or t


def _split_items(cell: str) -> list[str]:
    cell = _clean(cell)
    parts = [p.strip() for p in _SPLIT.split(cell) if p.strip()]
    return parts


def _heading_name(heading: str) -> tuple[str, str, str]:
    """'### BC3. Product Order (주문 접수) — `TMF622` · SID:Product 〔Core〕'
    → (name='Product Order', display=full-without-BCn, description=mapping-after-—)."""
    h = heading.lstrip("#").strip()
    h = re.sub(r"^BC\s*\d+\s*[\.\:]?\s*", "", h, flags=re.IGNORECASE)
    h = re.sub(r"^TMFOP\d+\s*[\.\:]?\s*", "", h, flags=re.IGNORECASE)
    display = _clean(h)
    # description = part after an em dash / hyphen separator
    desc = ""
    for sep in ("—", "–", " - ", "·"):
        if sep in display:
            head, _, tail = display.partition(sep)
            display_head = head.strip()
            desc = _clean(display.split(sep, 1)[1]) if False else _clean(h.split(sep, 1)[1])
            display = display_head
            break
    # name = strip parentheticals from the head
    name_token = _PAREN.sub("", display).strip()
    m = _IDENT.findall(name_token.replace(" ", ""))
    name = "".join(w[:1].upper() + w[1:] for w in name_token.split()) if name_token else display
    name = re.sub(r"[^A-Za-z0-9]", "", name) or display
    return name, display, _clean(desc)


def _is_table_row(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") and s.count("|") >= 2


def _row_cells(line: str) -> list[str]:
    s = line.strip().strip("|")
    return [c.strip() for c in s.split("|")]


def parse_design_markdown(text: str) -> dict:
    lines = text.splitlines()
    bcs: list[dict] = []
    warnings: list[str] = []

    # 1) BC 섹션 추출: 헤딩 + 바로 뒤따르는 종류/항목 테이블.
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if line.lstrip().startswith("#"):
            # look ahead (skip blank lines) for a 종류/항목 table header
            j = i + 1
            while j < n and not lines[j].strip():
                j += 1
            # table header + separator
            if (j + 1 < n and _is_table_row(lines[j]) and _is_table_row(lines[j + 1])
                    and ("종류" in lines[j] or "kind" in lines[j].lower())
                    and ("항목" in lines[j] or "item" in lines[j].lower())):
                name, display, desc = _heading_name(line)
                bc = {"name": name, "display": display, "description": desc,
                      "aggregates": [], "commands": [], "readModels": [], "policies": [],
                      "_actors": [], "_events": []}
                # consume rows after the separator
                k = j + 2
                while k < n and _is_table_row(lines[k]):
                    cells = _row_cells(lines[k])
                    k += 1
                    if len(cells) < 2:
                        continue
                    kind = _classify_kind(cells[0])
                    item_cell = cells[1]
                    if kind == "aggregate":
                        for it in _split_items(item_cell):
                            nm = _canonical_name(it)
                            if nm and nm not in [a["name"] for a in bc["aggregates"]]:
                                bc["aggregates"].append({"name": nm, "invariants": []})
                    elif kind == "command":
                        for it in _split_items(item_cell):
                            nm = _canonical_name(it)
                            if nm and nm not in [c["name"] for c in bc["commands"]]:
                                bc["commands"].append({"name": nm, "actor": None,
                                                       "aggregate": None, "emits": []})
                    elif kind == "event":
                        for it in _split_items(item_cell):
                            nm = _canonical_name(it)
                            disp = _PAREN.sub("", _clean(it)).strip() or nm
                            if nm and nm not in [e["name"] for e in bc["_events"]]:
                                bc["_events"].append({"name": nm, "displayName": disp})
                    elif kind == "policy":
                        nm = _clean(item_cell)
                        if nm:
                            bc["policies"].append({"name": nm[:120], "trigger": None, "invoke": None})
                    elif kind == "readmodel":
                        for it in _split_items(item_cell):
                            v = _clean(it)
                            if v:
                                bc["readModels"].append(v)
                    elif kind == "actor":
                        for it in _split_items(item_cell):
                            v = _clean(it)
                            if v:
                                bc["_actors"].append(v)
                bcs.append(bc)
                i = k
                continue
        i += 1

    if not bcs:
        return {"boundedContexts": [], "warnings": ["인식 가능한 Bounded Context 표를 찾지 못했습니다."]}

    # 2) 명령→애그리거트, 이벤트→명령 결선 (결정론적 휴리스틱)
    for bc in bcs:
        default_actor = bc["_actors"][0] if bc["_actors"] else "system"
        # aggregate for commands
        agg_name = bc["aggregates"][0]["name"] if bc["aggregates"] else None
        if not agg_name and (bc["commands"] or bc["_events"]):
            agg_name = bc["name"]
            bc["aggregates"].append({"name": agg_name, "invariants": []})
            warnings.append(f"[{bc['name']}] Aggregate 미표기 → '{agg_name}' 합성")
        for cmd in bc["commands"]:
            cmd["actor"] = cmd["actor"] or default_actor
            cmd["aggregate"] = cmd["aggregate"] or agg_name
        if len(bc["aggregates"]) > 1 and bc["commands"]:
            warnings.append(f"[{bc['name']}] Aggregate 다수 → 모든 Command 를 '{agg_name}' 에 연결(추정)")
        # events → first command
        if not bc["commands"] and bc["_events"]:
            synth = f"Handle{bc['name']}"
            bc["commands"].append({"name": synth, "actor": default_actor,
                                   "aggregate": agg_name, "emits": []})
            warnings.append(f"[{bc['name']}] Command 미표기 → '{synth}' 합성하여 Event 연결")
        if bc["commands"]:
            target = bc["commands"][0]
            target["emits"] = list(bc["_events"])
            if len(bc["commands"]) > 1 and bc["_events"]:
                warnings.append(
                    f"[{bc['name']}] Command 다수 → Event 발행을 '{target['name']}' 로 일괄 연결(추정). "
                    "명시적 명령→이벤트 매핑이 있으면 충실도가 올라갑니다.")

    # 3) 컨텍스트 간 Policy 체인 (fenced block 의 `Event ─P─▶ Command`)
    cmd_owner: dict[str, str] = {}
    event_names: set[str] = set()
    for bc in bcs:
        for c in bc["commands"]:
            cmd_owner.setdefault(c["name"], bc["name"])
        for c in bc["commands"]:
            for e in c["emits"]:
                event_names.add(e["name"])
    spine: list[dict] = []
    for raw in lines:
        m = _CHAIN.search(raw)
        if not m:
            continue
        trig, invoke = m.group(1), m.group(2)
        owner = cmd_owner.get(invoke)
        if not owner:
            warnings.append(f"Policy 체인 '{trig}→{invoke}': 호출 Command '{invoke}' 미해소 → 건너뜀")
            continue
        if trig not in event_names:
            warnings.append(f"Policy 체인 '{trig}→{invoke}': 트리거 Event '{trig}' 미해소 → 연결 없이 정책만 생성")
            trig = None
        spine.append({"bc": owner, "name": f"{trig or '?'} → {invoke}",
                      "trigger": trig, "invoke": invoke})
    # attach spine policies to their owner BC (dedup)
    for pol in spine:
        bc = next((b for b in bcs if b["name"] == pol["bc"]), None)
        if bc is None:
            continue
        if not any(p.get("invoke") == pol["invoke"] and p.get("trigger") == pol["trigger"]
                   for p in bc["policies"]):
            bc["policies"].append({"name": pol["name"][:120], "trigger": pol["trigger"],
                                   "invoke": pol["invoke"]})

    # cleanup private keys
    for bc in bcs:
        bc.pop("_actors", None)
        bc.pop("_events", None)

    return {"boundedContexts": bcs, "warnings": warnings}
