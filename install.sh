#!/usr/bin/env bash
# install.sh — bootstrap the Free AI Gateway
# Author: Mourad Soltani — © 2026 Mourad Soltani Technologies™ @MST
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

cat <<'BANNER'
+------------------------------------------------------------------+
|  Free AI Gateway  .  Installer  .  v1.2.0  .  2026               |
|  (c) 2026 Mourad Soltani - Mourad Soltani Technologies(TM) @MST  |
+------------------------------------------------------------------+
BANNER

PYTHON_BIN="${PYTHON_BIN:-python3}"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || { log "python3 not found"; exit 1; }

if ! "$PYTHON_BIN" -c "import venv" 2>/dev/null; then
  log "python3-venv missing. On Termux: pkg install python"
  log "On Debian/Ubuntu: sudo apt install python3-venv"
  exit 1
fi

if [[ ! -d venv ]]; then
  log "Creating virtualenv in ./venv"
  "$PYTHON_BIN" -m venv venv
fi

# shellcheck disable=SC1091
source venv/bin/activate

log "Upgrading pip / wheel / setuptools"
python -m pip install --quiet --upgrade pip wheel setuptools

log "Installing requirements (this may take a few minutes)"
pip install --quiet --upgrade -r requirements.txt

if [[ ! -f .env ]]; then
  cp .env.example .env
  log "Created .env from template — EDIT IT and add your API keys."
else
  log ".env already present — left untouched."
fi

chmod +x run.sh install.sh verify.sh 2>/dev/null || true

log "Running post-install verification"
./verify.sh || log "WARN: verification reported issues — see above"

log "Install complete."
echo
echo "Next steps:"
echo "  1) nano .env            # add keys + LITELLM_MASTER_KEY"
echo "  2) ./run.sh             # start the gateway on :4000"
echo "  3) python client.py     # in another shell, run the test client"
