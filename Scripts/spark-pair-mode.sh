#!/bin/bash
# Safe control surface for the direct-cabled DeepSeek/Media Spark pair.
# It intentionally does not launch a marketing batch: the normal 21:58
# scheduler remains responsible for that work.
set -euo pipefail

PAIR_A="spenchey@spark-2e61"
PAIR_B="spenchey@spark-cb87"
DS_REPO="/home/spenchey/repos/DeepSeek-v4-Flash-DSpark-1M-NVFP4-KV-2x-DGX-Spark"
PIPELINE="$HOME/clawd/dealership/marketing/emily-pipeline"

status() {
  local ds=false comfy=false
  if ssh -o BatchMode=yes -o ConnectTimeout=8 "$PAIR_A" \
    "curl -fsS --max-time 5 http://127.0.0.1:8888/v1/models >/dev/null" 2>/dev/null; then
    ds=true
  fi
  if ssh -o BatchMode=yes -o ConnectTimeout=8 "$PAIR_B" \
    "curl -fsS --max-time 5 http://127.0.0.1:8189/prompt >/dev/null" 2>/dev/null; then
    comfy=true
  fi
  local mode="idle"
  if [ "$ds" = true ] && [ "$comfy" = false ]; then mode="deepseek"; fi
  if [ "$ds" = false ] && [ "$comfy" = true ]; then mode="media"; fi
  if [ "$ds" = true ] && [ "$comfy" = true ]; then mode="transition"; fi
  printf '{"mode":"%s","deepseek_ready":%s,"media_ready":%s}\n' "$mode" "$ds" "$comfy"
}

switch_day() {
  "$PIPELINE/emily-day-mode.sh"
  status
}

switch_media() {
  ssh -o BatchMode=yes -o ConnectTimeout=15 "$PAIR_A" \
    "cd '$DS_REPO' && ./stop-deepseek-v4-flash-dspark.sh >/dev/null 2>&1"
  sleep 5
  "$PIPELINE/comfy_preflight.sh"
  status
}

case "${1:-}" in
  --status) status ;;
  --mode)
    [ "${3:-}" = "--confirm" ] || { echo "--confirm is required" >&2; exit 2; }
    case "${2:-}" in
      day) switch_day ;;
      media) switch_media ;;
      *) echo "mode must be day or media" >&2; exit 2 ;;
    esac
    ;;
  *) echo "usage: $0 --status | --mode {day|media} --confirm" >&2; exit 2 ;;
esac
