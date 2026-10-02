#!/usr/bin/env bash
# run_control_plane.sh — multi-tenant edge on :4100
# Author: Mourad Soltani — © 2026 Mourad Soltani Technologies™ @MST
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [[ -d venv ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

HOST="${CONTROL_PLANE_HOST:-0.0.0.0}"
PORT="${CONTROL_PLANE_PORT:-4100}"

echo "Control plane → http://${HOST}:${PORT}"
echo "Upstream LiteLLM: ${GATEWAY_URL:-http://127.0.0.1:4000}"
echo "Admin token set: $([[ -n "${CONTROL_PLANE_ADMIN_TOKEN:-}" ]] && echo yes || echo NO)"

exec python -m uvicorn control_plane.app:app --host "$HOST" --port "$PORT"
