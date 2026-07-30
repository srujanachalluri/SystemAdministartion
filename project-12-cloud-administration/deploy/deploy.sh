#!/usr/bin/env bash
# deploy.sh -- reproducible deployment of the Grace & Mercy donor-letters workload.
#
# This is the deployment artifact. Running it twice gives the same environment,
# so the deploy is auditable rather than a sequence of clicks nobody wrote down.
#
# NO SECRETS IN THIS FILE. The key is read from the environment. See .env.example.
#
# Usage:
#   bash deploy/deploy.sh            # provision + preflight, no billable traffic
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo " Project 12 deploy -- donor-letters workload"
echo "=============================================="

# ---- 1. Runtime -------------------------------------------------------------
echo "[1/5] Python runtime"
python3 --version
# Some hosts (Homebrew/Debian) mark the system Python as externally managed;
# fall back to --user, then to --break-system-packages, rather than aborting.
python3 -m pip install --quiet -r requirements.txt 2>/dev/null \
  || python3 -m pip install --quiet --user -r requirements.txt 2>/dev/null \
  || python3 -m pip install --quiet --break-system-packages -r requirements.txt
echo "      dependencies installed"

# ---- 2. Cost-allocation tags ------------------------------------------------
# Tags must exist BEFORE traffic. An untagged dollar is an unattributable dollar.
echo "[2/5] Cost-allocation tags"
python3 - <<'PY'
import json, pathlib
tags = json.loads(pathlib.Path("deploy/tags.json").read_text())
for k, v in tags["tags"].items():
    print(f"      {k:<8} = {v}")
print(f"      applied to: {', '.join(tags['applied_to'])}")
PY

# ---- 3. Budget + alert preflight -------------------------------------------
# The budget and alert are configured in the provider console (they cannot be
# created from this repo without provider credentials). This step FAILS the
# deploy if I have not recorded that I did it -- so I cannot skip the control
# and then claim I wired it.
echo "[3/5] FinOps controls preflight"
if grep -q "CONFIRMED: yes" deploy/budget-alert.md; then
  grep -E "^(Monthly budget|Alert threshold|Hard cap|Configured on)" deploy/budget-alert.md \
    | sed 's/^/      /'
else
  echo "      REFUSING TO DEPLOY: budget/alert not confirmed in deploy/budget-alert.md" >&2
  exit 1
fi

# ---- 4. Credential check (never printed) ------------------------------------
echo "[4/5] Credentials"
if [[ -n "${PROVIDER_API_KEY:-}" ]]; then
  echo "      PROVIDER_API_KEY is set (length ${#PROVIDER_API_KEY}); value not logged"
  echo "      MODEL_ID = ${MODEL_ID:-<unset>}"
else
  echo "      PROVIDER_API_KEY not set -- workload will only run in --mock mode"
fi

# ---- 5. Smoke test (zero spend) --------------------------------------------
echo "[5/5] Smoke test (mock, no billable calls)"
python3 app/donor_letters.py --requests 3 --mock >/dev/null
echo "      workload harness OK"

echo
echo "Deploy complete. Next: predict the cost, THEN generate traffic."
echo "  python3 code/token_cost.py --in 120 --out 130 --in-price <X> --out-price <Y> --requests 100"
