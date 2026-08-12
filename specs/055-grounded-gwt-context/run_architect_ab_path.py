"""Run one frozen Architect GWT A/B path without accept/apply.

This is an experiment driver, not a product code path.  It uses only public Architect
routes and saves every SSE event plus the resulting Proposal snapshot for adjudication.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

API = "http://127.0.0.1:8501"
STAGES = ["DISCOVER", "DECOMPOSE", "STRATEGIZE", "CONNECT", "DEFINE", "TACTICAL"]
CONTRACT = Path(r"D:\work\robo\project\robo-data-analyzer\_runs\architect-gwt-ab-20260810\contract.json")
CLAUDE_LOGS = Path(r"C:\Users\roede\.claude\projects\D--work-robo-project-robo-architect")
OUT_ROOT = Path(r"D:\work\robo\project\robo-data-analyzer\_runs\architect-gwt-ab-20260810\architect")


def _sessions() -> dict[str, dict]:
    result = {}
    for path in CLAUDE_LOGS.glob("*.jsonl"):
        stat = path.stat()
        result[path.name] = {"bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    return result


def _request(
    client: httpx.Client, api: str, method: str, path: str, body: dict | None = None,
) -> dict:
    response = client.request(method, api + path, json=body)
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {path}: {response.status_code} {response.text}")
    return response.json() if response.content else {}


def _stream(client: httpx.Client, api: str, path: str) -> tuple[list[dict], float]:
    events: list[dict] = []
    event_type = "message"
    started = time.perf_counter()
    with client.stream("GET", api + path) as response:
        if response.status_code >= 400:
            raise RuntimeError(f"GET {path}: {response.status_code} {response.read().decode('utf-8', 'replace')}")
        for raw in response.iter_lines():
            line = raw.strip()
            if not line:
                event_type = "message"
                continue
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                text = line[5:].strip()
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    data = text
                events.append({"event": event_type, "data": data})
    errors = [event for event in events if event["event"] == "error"]
    if errors:
        raise RuntimeError(f"SSE {path} error: {errors[-1]}")
    return events, time.perf_counter() - started


def _artifact(events: list[dict], event_name: str, key: str) -> dict:
    for event in reversed(events):
        if event["event"] == event_name and isinstance(event["data"], dict):
            value = event["data"].get(key)
            if isinstance(value, dict):
                return value
    raise RuntimeError(f"missing {event_name}.{key}")


def _conflict_resolutions(events: list[dict]) -> list[dict]:
    resolutions = []
    for event in events:
        if event["event"] != "conflicts" or not isinstance(event["data"], dict):
            continue
        for conflict in event["data"].get("conflicts", []):
            resolutions.append({
                "bcId": conflict.get("bcId"),
                "field": conflict["field"],
                "resolution": "JUSTIFY_LOCAL",
                "justification": "A/B 격리를 위해 기존 전략 메모리를 변경하지 않음",
            })
    return resolutions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--mode", choices=["SIMPLIFIED", "DETAILED_DDD"], required=True)
    parser.add_argument("--api", default=API)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--out-root", type=Path, default=OUT_ROOT)
    args = parser.parse_args()

    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    out_dir = args.out_root / args.label
    out_dir.mkdir(parents=True, exist_ok=False)
    started_at = datetime.now(timezone.utc).isoformat()
    wall_started = time.perf_counter()
    step_metrics = []
    session_before = _sessions()

    with httpx.Client(timeout=httpx.Timeout(1800.0, connect=10.0)) as client:
        # Both paths require the same Constitution.  The old preserved experiment DB already
        # contained one, which hid this preflight requirement from the Simplified driver.
        # Reset it before every isolated run so neither path inherits ambient DB state.
        _request(client, args.api, "PUT", "/api/constitution", {
            "raw": "# Shopmall GWT 검증 헌장\n\n"
                   "- 봉인된 레거시 근거의 값, 분기, 호출, 읽기/쓰기를 보존한다.\n"
                   "- 근거 없는 업무 의미를 만들지 않는다.\n"
                   "- 모든 GWT와 변경 항목은 legacyRefs로 원본 노드와 좌표에 역추적 가능해야 한다.\n"
                   "- 이 세션은 설계 초안 비교만 수행하며 accept/apply하지 않는다.",
            "fields": {"language": "ko", "evidencePolicy": "sealed-legacy-only"},
            "strategicMemory": {
                "domain": "주문 정산 지원",
                "constraints": ["legacy-grounded", "no-accept-apply"],
            },
        })
        created = _request(client, args.api, "POST", "/api/proposals/", {
            "originalPrompt": contract["proposal_prompt"],
            "title": f"GWT A/B {args.label}",
            "decompositionMode": args.mode,
        })
        proposal_id = created["id"]
        (out_dir / "created.json").write_text(json.dumps(created, ensure_ascii=False, indent=2), encoding="utf-8")

        if args.mode == "SIMPLIFIED":
            events, seconds = _stream(client, args.api, f"/api/proposals/stream/{proposal_id}/intent")
            step_metrics.append({"step": "intent", "seconds": round(seconds, 3)})
            (out_dir / "intent.events.json").write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
            submitted = _request(client, args.api, "POST", f"/api/proposals/{proposal_id}/submit", {})
            (out_dir / "submitted.json").write_text(json.dumps(submitted, ensure_ascii=False, indent=2), encoding="utf-8")
            events, seconds = _stream(client, args.api, f"/api/proposals/{proposal_id}/stream/plan")
            step_metrics.append({"step": "plan", "seconds": round(seconds, 3)})
            (out_dir / "plan.events.json").write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            events, seconds = _stream(client, args.api, f"/api/proposals/{proposal_id}/stream/scope")
            step_metrics.append({"step": "scope", "seconds": round(seconds, 3)})
            (out_dir / "scope.events.json").write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
            stage_plan = _artifact(events, "stage_plan", "stagePlan")
            decisions = [{"stage": stage, "skipped": False} for stage in STAGES]
            confirmed_plan = _request(client, args.api, "POST", f"/api/proposals/{proposal_id}/stage-plan/confirm", {"stages": decisions})
            (out_dir / "stage-plan-confirmed.json").write_text(json.dumps(confirmed_plan, ensure_ascii=False, indent=2), encoding="utf-8")
            (out_dir / "stage-plan-generated.json").write_text(json.dumps(stage_plan, ensure_ascii=False, indent=2), encoding="utf-8")

            for stage in STAGES:
                events, seconds = _stream(client, args.api, f"/api/proposals/{proposal_id}/stream/stage/{stage}")
                step_metrics.append({"step": stage, "seconds": round(seconds, 3)})
                (out_dir / f"{stage.lower()}.events.json").write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
                artifact = _artifact(events, "artifact", "artifact")
                body = {"artifact": artifact, "conflictResolutions": _conflict_resolutions(events)}
                draft = _request(client, args.api, "PUT", f"/api/proposals/{proposal_id}/stage/{stage}/draft", body)
                (out_dir / f"{stage.lower()}.draft.json").write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
                confirmed = _request(client, args.api, "POST", f"/api/proposals/{proposal_id}/stage/{stage}/confirm", body)
                (out_dir / f"{stage.lower()}.confirmed.json").write_text(json.dumps(confirmed, ensure_ascii=False, indent=2), encoding="utf-8")

            consolidated = _request(client, args.api, "POST", f"/api/proposals/{proposal_id}/staged/consolidate")
            (out_dir / "consolidated.json").write_text(json.dumps(consolidated, ensure_ascii=False, indent=2), encoding="utf-8")

        final = _request(client, args.api, "GET", f"/api/proposals/{proposal_id}")
        (out_dir / "proposal-final.json").write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")

    session_after = _sessions()
    changed_sessions = {
        name: after for name, after in session_after.items()
        if name not in session_before or session_before[name] != after
    }
    manifest = {
        "label": args.label,
        "mode": args.mode,
        "api": args.api,
        "contract": str(args.contract.resolve()),
        "output_root": str(args.out_root.resolve()),
        "proposal_id": proposal_id,
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "wall_seconds": round(time.perf_counter() - wall_started, 3),
        "steps": step_metrics,
        "claude_sessions_changed": changed_sessions,
        "accept_called": False,
        "apply_called": False,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
