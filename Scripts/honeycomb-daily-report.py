#!/usr/bin/env python3
"""Create a compact daily Honeycomb report from metadata-only request events.

This never contacts an inference provider. With HONEYCOMB_ALERT_WEBHOOK set,
the same concise report can be delivered to a Slack-compatible webhook.
"""

from __future__ import annotations

import collections
import json
import os
import sys
import time
import urllib.request
from pathlib import Path


def events(path: Path, since: float) -> list[dict]:
    rows = []
    try:
        for line in path.read_text().splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if float(row.get("ts") or 0) >= since:
                rows.append(row)
    except FileNotFoundError:
        pass
    return rows


def report(rows: list[dict]) -> str:
    grouped: dict[str, dict[str, int]] = {}
    for row in rows:
        key = " | ".join((str(row.get("agent") or "unknown"), str(row.get("model") or "unknown"), str(row.get("device") or row.get("backend") or "unknown")))
        value = grouped.setdefault(key, {"requests": 0, "input": 0, "output": 0, "errors": 0})
        value["requests"] += 1
        value["input"] += int(row.get("prompt_tokens") or 0)
        value["output"] += int(row.get("completion_tokens") or 0)
        value["errors"] += int(int(row.get("status") or 0) == 0 or int(row.get("status") or 0) >= 400)
    total_requests = sum(v["requests"] for v in grouped.values())
    total_errors = sum(v["errors"] for v in grouped.values())
    lines = [f"Honeycomb daily report: {total_requests} requests, {total_errors} errors."]
    if not grouped:
        return lines[0] + " No routed inference traffic was recorded."
    for name, value in sorted(grouped.items(), key=lambda pair: pair[1]["requests"], reverse=True)[:12]:
        lines.append(f"- {name}: {value['requests']} req, {value['input']} input tok, {value['output']} output tok, {value['errors']} errors")
    return "\n".join(lines)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    config_path = Path(os.environ.get("HONEYCOMB_GATEWAY_CONFIG", "~/Library/Application Support/Honeycomb/gateway-config.json")).expanduser()
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    ledger = Path(config.get("telemetry_events_path") or root / "gateway/telemetry-events.jsonl").expanduser()
    output_dir = Path(config.get("reports_path") or "~/Library/Application Support/Honeycomb/reports").expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    text = report(events(ledger, time.time() - 86400))
    destination = output_dir / f"daily-{time.strftime('%Y-%m-%d')}.txt"
    destination.write_text(text + "\n")
    print(text)
    webhook = os.environ.get("HONEYCOMB_ALERT_WEBHOOK")
    if webhook:
        req = urllib.request.Request(webhook, data=json.dumps({"text": text}).encode(), headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10):
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
