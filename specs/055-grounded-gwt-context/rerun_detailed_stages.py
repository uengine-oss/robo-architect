"""Rerun affected Detailed DDD stages on an isolated draft; never accept/apply."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx


def request(client: httpx.Client, api: str, method: str, path: str, body=None):
    response = client.request(method, api + path, json=body)
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {path}: {response.status_code} {response.text}")
    return response.json() if response.content else {}


def stream(client: httpx.Client, api: str, path: str):
    events = []
    event_type = "message"
    started = time.perf_counter()
    with client.stream("GET", api + path) as response:
        if response.status_code >= 400:
            raise RuntimeError(f"GET {path}: {response.status_code} {response.read().decode()}")
        for raw in response.iter_lines():
            line = raw.strip()
            if not line:
                event_type = "message"
            elif line.startswith("event:"):
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
        raise RuntimeError(f"SSE {path}: {errors[-1]}")
    return events, round(time.perf_counter() - started, 3)


def artifact(events):
    for event in reversed(events):
        if event["event"] == "artifact" and isinstance(event["data"], dict):
            return event["data"]["artifact"]
    raise RuntimeError("artifact event missing")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposal-id", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--api", default="http://127.0.0.1:8501")
    parser.add_argument(
        "--feedback",
        help="Targeted regeneration feedback appended to each selected stage request.",
    )
    parser.add_argument(
        "--stages", nargs="+", choices=("DEFINE", "TACTICAL"),
        default=("DEFINE", "TACTICAL"),
    )
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=False)
    metrics = []

    with httpx.Client(timeout=httpx.Timeout(1800, connect=10)) as client:
        for stage in args.stages:
            path = f"/api/proposals/{args.proposal_id}/stream/stage/{stage}"
            if args.feedback:
                path += "?" + urlencode({"feedback": args.feedback})
            events, seconds = stream(
                client, args.api, path,
            )
            metrics.append({"stage": stage, "seconds": seconds})
            (args.out_dir / f"{stage.lower()}.events.json").write_text(
                json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8",
            )
            body = {"artifact": artifact(events), "conflictResolutions": []}
            request(client, args.api, "PUT", f"/api/proposals/{args.proposal_id}/stage/{stage}/draft", body)
            request(client, args.api, "POST", f"/api/proposals/{args.proposal_id}/stage/{stage}/confirm", body)
        consolidated = request(
            client, args.api, "POST", f"/api/proposals/{args.proposal_id}/staged/consolidate",
        )
        (args.out_dir / "proposal-final.json").write_text(
            json.dumps(consolidated, ensure_ascii=False, indent=2), encoding="utf-8",
        )
    manifest = {
        "proposal_id": args.proposal_id, "steps": metrics,
        "feedback": args.feedback,
        "accept_called": False, "apply_called": False,
    }
    (args.out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
