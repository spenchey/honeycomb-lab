#!/usr/bin/env python3
"""Report which Hermes profiles use Honeycomb versus direct providers.

Only reads the small `model:` mapping in each profile config. It never prints
agent credentials and exits nonzero only when a profile points at Honeycomb
with an alias that no longer exists.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def model_fields(path: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    inside = False
    for line in path.read_text(errors="ignore").splitlines():
        if line.startswith("model:"):
            inside = True
            continue
        if inside and line and not line.startswith((" ", "\t")):
            break
        if inside and ":" in line:
            key, value = line.strip().split(":", 1)
            if key in ("default", "provider", "base_url"):
                found[key] = value.strip().strip("'\"")
    return found


def main() -> int:
    config_path = Path(os.environ.get("HONEYCOMB_GATEWAY_CONFIG", "~/Library/Application Support/Honeycomb/gateway-config.json")).expanduser()
    cfg = json.loads(config_path.read_text())
    aliases = set((cfg.get("aliases") or {}).keys())
    root = Path(os.environ.get("HERMES_PROFILES_DIR", "~/.hermes/profiles")).expanduser()
    bad = []
    output = []
    for path in sorted(root.glob("*/config.yaml")):
        fields = model_fields(path)
        base = fields.get("base_url", "")
        model = fields.get("default", "")
        via = "honeycomb" if base.rstrip("/").endswith(":4000/v1") else "direct"
        valid = via != "honeycomb" or model in aliases
        output.append({"agent": path.parent.name, "route": via, "model": model, "provider": fields.get("provider", ""), "valid": valid})
        if not valid:
            bad.append(path.parent.name)
    print(json.dumps({"profiles": output, "invalid_honeycomb_aliases": bad}, indent=2))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
