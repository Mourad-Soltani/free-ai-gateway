#!/usr/bin/env bash
# run.sh — production launcher for the Free AI Gateway
# Author: Mourad Soltani — © 2026 Mourad Soltani Technologies™ @MST
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { log "ERROR: $*" >&2; exit 1; }

cat <<'BANNER'
+------------------------------------------------------------------+
|  Free AI Gateway  .  v1.2.0  .  2026                             |
|  (c) 2026 Mourad Soltani - Mourad Soltani Technologies(TM) @MST  |
+------------------------------------------------------------------+
BANNER

[[ -f .env ]] || die ".env not found. Run: cp .env.example .env && \$EDITOR .env"

set -a
# shellcheck disable=SC1091
source .env
set +a

REQUIRED_VARS=(GROQ_API_KEY GEMINI_API_KEY OPENROUTER_API_KEY LITELLM_MASTER_KEY)
missing=()
for var in "${REQUIRED_VARS[@]}"; do
  [[ -n "${!var:-}" ]] || missing+=("$var")
done
[[ ${#missing[@]} -eq 0 ]] || die "Missing/empty env vars: ${missing[*]}"

[[ -f config.yaml ]] || die "config.yaml not found in $ROOT_DIR"

if [[ -d venv ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
elif [[ -z "${VIRTUAL_ENV:-}" ]]; then
  log "WARN: no ./venv and no active virtualenv — using system Python."
fi

command -v litellm >/dev/null 2>&1 \
  || die "litellm not found on PATH. Run ./install.sh first."

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-4000}"
WORKERS="${WORKERS:-4}"
LOG_LEVEL="${LITELLM_LOG:-INFO}"

log "Starting LiteLLM proxy on http://${HOST}:${PORT} (workers=${WORKERS})"
log "Metrics: http://${HOST}:${PORT}/metrics   Health: /health/liveliness"

exec litellm \
  --config config.yaml \
  --host "$HOST" \
  --port "$PORT" \
  --num_workers "$WORKERS" \
  --log_level "$LOG_LEVEL"
