#!/usr/bin/env bash
# verify.sh — post-install sanity check
# Author: Mourad Soltani — © 2026 Mourad Soltani Technologies™ @MST
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

ok=0; fail=0
chk() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then
    printf '  \033[32mok\033[0m %s\n' "$label"; ok=$((ok+1))
  else
    printf '  \033[31m!!\033[0m %s\n' "$label"; fail=$((fail+1))
  fi
}

echo "Free AI Gateway - verification (2026)"
echo "-------------------------------------"

chk "Python 3.10+"          bash -c 'python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"'
chk "venv present"          test -d venv
chk "litellm on PATH"       bash -c '[[ -x venv/bin/litellm ]]'
chk "config.yaml exists"    test -f config.yaml
chk "tracker imports"       bash -c 'venv/bin/python -c "import tracker"'
chk "client imports"        bash -c 'venv/bin/python -c "import client"'
chk "async_client imports"  bash -c 'venv/bin/python -c "import async_client"'
chk "healthcheck imports"   bash -c 'venv/bin/python -c "import healthcheck"'
chk "quota DB readable"     bash -c 'venv/bin/python -c "from tracker import APIRateTracker; t=APIRateTracker(); t.stats(); t.close()"'
chk ".env present"          test -f .env

echo "-------------------------------------"
echo "Passed: $ok   Failed: $fail"
if [[ $fail -eq 0 ]]; then
  echo "Status: ready"
else
  echo "Status: review failures above"
fi
exit $fail
