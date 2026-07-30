#!/usr/bin/env bash
# finops_alerts_gm.sh -- Grace & Mercy Relief adaptation of code/finops_alerts.sh
#
# WHAT I CHANGED FROM THE REFERENCE SCRIPT (and why):
#   1. BILL_CSV now defaults to deploy/actual-bill.csv -- the cost export I
#      downloaded from my provider's billing console, not the synthetic sample.
#   2. Added --csv so I can point it at code/sample-bill.csv to prove the logic
#      works before my real bill has landed.
#   3. Projection now uses the ACTUAL number of days present in the export
#      instead of assuming one day x 30. A 5-day export projected as if it were
#      one day overstates month-end spend by 5x -- that is a false alarm, and
#      false alarms are how alerts get muted.
#   4. Added a HARD CAP reminder line per tag: budgets WARN, caps STOP.
#   5. Added notify() as the single place to wire Slack/Teams/email later.
#
# Usage:
#   bash deploy/finops_alerts_gm.sh --budget 25 --threshold 0.8
#   bash deploy/finops_alerts_gm.sh --budget 5000 --threshold 0.8 --csv code/sample-bill.csv
set -euo pipefail

BUDGET=25            # monthly budget (USD) approved by the board for this project
THRESHOLD=0.8        # alert at 80% of projected month-end spend
TAG_KEY="project"    # cost-allocation tag to group by
HARD_CAP=50          # provider-side hard cap (USD). Budgets warn; caps stop.
BILL_CSV="$(dirname "$0")/actual-bill.csv"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --budget)    BUDGET="$2"; shift 2;;
    --threshold) THRESHOLD="$2"; shift 2;;
    --tag-key)   TAG_KEY="$2"; shift 2;;
    --cap)       HARD_CAP="$2"; shift 2;;
    --csv)       BILL_CSV="$2"; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done

if [[ ! -f "$BILL_CSV" ]]; then
  echo "ERROR: no billing source at '$BILL_CSV'." >&2
  echo "Download your provider cost export to deploy/actual-bill.csv," >&2
  echo "or test the logic with: --csv code/sample-bill.csv" >&2
  exit 1
fi

# Placeholder for a real notifier (Slack webhook / Teams / PagerDuty / email).
notify() { echo "  >> NOTIFY: $*"; }

# Group by tag, and count how many distinct days the export actually covers.
grouped="$(awk -F, 'NR>1 && NF>=6 {sum[$5]+=$6; days[$1]=1}
                    END {n=0; for (d in days) n++;
                         for (t in sum) printf "%s,%.2f,%d\n", t, sum[t], n}' "$BILL_CSV")"

DAYS_IN_MONTH=30
echo "FinOps check -- Grace & Mercy Relief"
echo "source=$BILL_CSV  budget=\$${BUDGET}  threshold=${THRESHOLD}  cap=\$${HARD_CAP}  group-by=${TAG_KEY}"
echo "--------------------------------------------------------------------"

while IFS=, read -r tag total_cost days; do
  [[ -z "$tag" ]] && continue
  daily=$(awk -v c="$total_cost" -v d="$days" 'BEGIN{printf "%.2f", (d>0)? c/d : c}')
  projected=$(awk -v d="$daily" -v n="$DAYS_IN_MONTH" 'BEGIN{printf "%.2f", d*n}')
  trip=$(awk -v p="$projected" -v b="$BUDGET" -v t="$THRESHOLD" \
            'BEGIN{print (p >= b*t) ? "ALERT" : "ok"}')
  printf "  %-18s observed=\$%-8s over %sd  daily=\$%-8s projected=\$%-10s [%s]\n" \
         "$tag" "$total_cost" "$days" "$daily" "$projected" "$trip"
  if [[ "$trip" == "ALERT" ]]; then
    notify "'$tag' projected \$$projected >= ${THRESHOLD} x \$$BUDGET monthly budget."
    echo "  >> ACTION: find the driver before downsizing. Idle is not always waste --"
    echo "     confirm the resource is not deliberate spare capacity first."
    echo "  >> STOP CONTROL: provider hard cap is \$$HARD_CAP for this project."
  fi
done <<< "$grouped"

echo "--------------------------------------------------------------------"
echo "Reminder: this script WARNS. The provider-side hard cap (\$$HARD_CAP) is what STOPS spend."
