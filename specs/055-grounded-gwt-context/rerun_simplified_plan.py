"""Rerun only Simplified Plan on an isolated submitted proposal; never confirm/apply."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposal-id", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--api", default="http://127.0.0.1:8501")
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=False)
    events = []
    event_type = "message"
    started = time.perf_counter()
    path = f"/api/proposals/{args.proposal_id}/stream/plan"
    with httpx.Client(timeout=httpx.Timeout(1800, connect=10)) as client:
        with client.stream("GET", args.api + path) as response:
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
        (args.out_dir / "plan.events.json").write_text(
            json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        errors = [event for event in events if event["event"] == "error"]
        if errors:
            raise RuntimeError(f"SSE {path}: {errors[-1]}")
        response = client.get(args.api + f"/api/proposals/{args.proposal_id}")
        response.raise_for_status()
        (args.out_dir / "proposal-final.json").write_text(
            json.dumps(response.json(), ensure_ascii=False, indent=2), encoding="utf-8",
        )
    manifest = {
        "proposal_id": args.proposal_id,
        "plan_seconds": round(time.perf_counter() - started, 3),
        "accept_called": False, "apply_called": False,
    }
    (args.out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
