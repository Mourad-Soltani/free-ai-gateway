#!/bin/sh
# Start LiteLLM on :4000 and control plane on :8080 (public)
# Author: Mourad Soltani — © 2026 Mourad Soltani Technologies™ @MST
set -eu

echo "[fly] starting LiteLLM on :4000"
litellm --config /app/config.yaml --host 127.0.0.1 --port 4000 --num_workers 1 --log_level "${LITELLM_LOG:-INFO}" &
LLM_PID=$!

# wait for upstream health
i=0
while [ "$i" -lt 60 ]; do
  if curl -fsS "http://127.0.0.1:4000/health/liveliness" >/dev/null 2>&1; then
    echo "[fly] LiteLLM ready"
    break
  fi
  i=$((i + 1))
  sleep 1
done

echo "[fly] starting control plane on :${CONTROL_PLANE_PORT:-8080}"
exec python -m uvicorn control_plane.app:app --host 0.0.0.0 --port "${CONTROL_PLANE_PORT:-8080}"
