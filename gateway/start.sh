#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Provider credentials stay outside the fleet configuration and agent profiles.
# The file is local-only and must be readable only by this macOS user.
SECRETS_FILE="${HONEYCOMB_GATEWAY_SECRETS_FILE:-$HOME/Library/Application Support/Honeycomb/gateway-secrets.env}"
if [[ -f "$SECRETS_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$SECRETS_FILE"
  set +a
fi

# Ensure LM Studio local API is up (LM Link front door)
if command -v lms >/dev/null 2>&1; then
  if ! lms server status 2>/dev/null | grep -qi "running"; then
    echo "starting LM Studio server on :1234 …"
    lms server start || true
  fi
fi

export HONEYCOMB_GATEWAY_CONFIG="${HONEYCOMB_GATEWAY_CONFIG:-$PWD/config.json}"
exec python3 "$PWD/server.py"
