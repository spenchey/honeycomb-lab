#!/usr/bin/env python3
"""Send one Honeycomb operational alert through the existing Slack bot.

The Slack credential remains in the Hermes profile .env file. This script
accepts only a channel id and message; it never prints the credential.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path


def dotenv_value(path: Path, key: str) -> str | None:
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            found, value = line.split("=", 1)
            if found.strip() == key:
                return value.strip().strip("\"").strip("'") or None
    except OSError:
        return None
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", required=True)
    parser.add_argument("message")
    args = parser.parse_args()
    if not args.channel.startswith("C"):
        raise SystemExit("Slack channel must be a channel id")
    env_path = Path(os.environ.get("HONEYCOMB_SLACK_ENV", "~/.hermes/profiles/mac/.env")).expanduser()
    token = os.environ.get("SLACK_BOT_TOKEN") or dotenv_value(env_path, "SLACK_BOT_TOKEN")
    if not token:
        raise SystemExit("SLACK_BOT_TOKEN is unavailable")
    body = json.dumps({"channel": args.channel, "text": args.message}).encode()
    request = urllib.request.Request(
        "https://slack.com/api/chat.postMessage", data=body, method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            result = json.loads(response.read().decode())
    except urllib.error.URLError as error:
        raise SystemExit(f"Slack delivery failed: {error.reason}") from error
    if not result.get("ok"):
        raise SystemExit(f"Slack delivery failed: {result.get('error', 'unknown_error')}")
    print("sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
