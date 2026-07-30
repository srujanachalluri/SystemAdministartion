#!/usr/bin/env bash
# finops_alerts.sh -- reference FinOps daily-spend / per-tag / threshold-alert sketch.
#
# Budgets WARN; hard caps STOP. This script is the WARN half: pull yesterday's
# spend, break it down by cost-allocation tag, and alert if a project is on
# track to blow its monthly budget. Adapt the "fetch" function to your provider's
# cost export (AWS Cost Explorer / Cost & Usage Report, Azure Cost Management
# export, GCP Billing BigQuery export). No real keys -- placeholders only.
#
# Usage:
#   bash finops_alerts.sh --budget 5000 --threshold 0.8 --tag-key project
set -euo pipefail

BUDGET=1000          # monthly budget (USD)
THRESHOLD=0.8        # alert when projected-to-month-end >= THRESHOLD * BUDGET
TAG_KEY="project"    # cost-allocation tag to group by
BILL_CSV="${BILL_CSV:-$(dirname "$0")/sample-bill.csv}"  # swap for a live cost-export pull

while [[ $# -gt 0 ]]; do
  case "$1" in
    --budget)    BUDGET="$2"; shift 2;;
    --threshold) THRESHOLD="$2"; shift 2;;
    --tag-key)   TAG_KEY="$2"; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done

# In production, replace this with a real billing-export query for yesterday.
fetch_spend_csv() {
  # echoes CSV: tag,cost_usd  (already grouped by tag, single day)
  if [[ -f "$BILL_CSV" ]]; then
    awk -F, 'NR>1 {sum[$5]+=$6} END {for (t in sum) printf "%s,%.2f\n", t, sum[t]}' "$BILL_CSV"
  else
    echo "ERROR: no billing source ($BILL_CSV). Wire your provider export." >&2
    exit 1
  fi
}

DAYS_IN_MONTH=30
echo "FinOps check: budget=\$${BUDGET}  threshold=${THRESHOLD}  group-by=${TAG_KEY}"
echo "--------------------------------------------------------------"

# Capture the fetch first so a failure surfaces instead of being swallowed by
# the process substitution below (a subshell whose exit status is ignored).
spend_csv="$(fetch_spend_csv)"

while IFS=, read -r tag day_cost; do
  # crude month-end projection from a single day's spend
  projected=$(awk -v d="$day_cost" -v n="$DAYS_IN_MONTH" 'BEGIN{printf "%.2f", d*n}')
  trip=$(awk -v p="$projected" -v b="$BUDGET" -v t="$THRESHOLD" \
            'BEGIN{print (p >= b*t) ? "ALERT" : "ok"}')
  printf "  %-16s day=\$%-8s projected=\$%-10s  [%s]\n" "$tag" "$day_cost" "$projected" "$trip"
  if [[ "$trip" == "ALERT" ]]; then
    echo "  >> ALERT: '$tag' projected \$$projected >= ${THRESHOLD} x \$$BUDGET budget."
    echo "  >> ACTION: investigate driver; verify idle != insurance before downsizing."
    # hook a real notifier here (Slack/Teams/PagerDuty/email)
  fi
done <<< "$spend_csv"

echo "--------------------------------------------------------------"
echo "Reminder: this WARNS. Pair with a HARD CAP at the provider to STOP runaway spend."
