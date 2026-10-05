"""Event simulator — emits synthetic JSON to POST /api/events."""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import httpx

DB_PATH = os.environ.get("DATABASE_PATH", "hospital.db")


def load_scenario(name: str) -> list[dict]:
    path = os.path.join("data/scenarios", f"{name}.json")
    if not os.path.exists(path):
        # try with prefix
        for f in os.listdir("data/scenarios"):
            if f.startswith(name):
                path = os.path.join("data/scenarios", f)
                break
    with open(path) as f:
        return json.load(f)


def run(url: str, scenario: str, delay_ms: int = 50, reset: bool = True) -> None:
    events = load_scenario(scenario)
    print(f"[sim] loaded {len(events)} events from {scenario}")
    if reset:
        try:
            r = httpx.post(f"{url}/api/sim/reset", timeout=5)
            print(f"[sim] reset: {r.status_code}")
        except Exception as e:
            print(f"[sim] reset failed (server down?): {e}")
    for i, ev in enumerate(events):
        try:
            r = httpx.post(f"{url}/api/events", json=ev, timeout=3)
            if r.status_code >= 300:
                print(f"  [{i+1}/{len(events)}] {ev.get('event_type')} -> {r.status_code} {r.text[:120]}")
            else:
                print(f"  [{i+1}/{len(events)}] {ev.get('event_type')} OK")
        except Exception as e:
            print(f"  [{i+1}/{len(events)}] POST failed: {e}")
        if delay_ms:
            time.sleep(delay_ms / 1000.0)
    print("[sim] done")


def main():
    p = argparse.ArgumentParser(description="Emit synthetic events to the API")
    p.add_argument("scenario", choices=["a", "b", "c", "d", "a_radiology", "b_pharmacy", "c_infusion_pump", "d_benign_patching"],
                   help="Which scenario to run")
    p.add_argument("--url", default="http://localhost:8000", help="Base URL of the API")
    p.add_argument("--delay", type=int, default=50, help="Delay between events (ms)")
    p.add_argument("--no-reset", action="store_true", help="Don't call /api/sim/reset first")
    args = p.parse_args()
    run(args.url, args.scenario, args.delay, not args.no_reset)


if __name__ == "__main__":
    main()