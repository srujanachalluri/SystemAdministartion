===============================================================================
PROJECT 12 — DEPLOY IN THE CLOUD, READ THE BILL
Grace & Mercy Relief — donor thank-you letter assistant
Normal tier
===============================================================================

WHAT THIS IS
-------------------------------------------------------------------------------
A serverless AI workload that drafts short thank-you letters for donors, wired
with FinOps controls BEFORE any traffic ran, then run at a fixed volume so the
predicted cost could be reconciled against the actual bill.

The point of the project is not that the assistant works. It is that the cost is
visible, attributable, capped, predicted in advance, and explained afterward.

SYNTHETIC DATA ONLY. app/synthetic_donors.csv contains ten invented people. No
real donor data was sent to any third-party API.

NO SECRETS IN THIS REPO. .env is gitignored; .env.example holds placeholders.


REPOSITORY LAYOUT
-------------------------------------------------------------------------------
  app/donor_letters.py        the AI workload (OpenAI-compatible SDK)
  app/synthetic_donors.csv    ten synthetic donor records
  deploy/deploy.sh            reproducible deploy + preflight (refuses to run
                              if FinOps controls are not confirmed)
  deploy/tags.json            cost-allocation tags: project / env / team
  deploy/budget-alert.md      the budget, alert threshold, and hard cap I set
  deploy/finops_alerts_gm.sh  my adaptation of the reference FinOps script
  deploy/reconcile.py         predicted vs measured, side by side
  code/                       the professor's unmodified starter files
  output/                     run-log.jsonl + usage-summary.txt (generated)
  COST_REPORT.docx            prediction, measurement, actual bill, the gap
  agent-log.txt               what I delegated to AI and where it was wrong


HOW TO RUN (GitHub Codespaces)
-------------------------------------------------------------------------------
  cd project-12-cloud-administration

  # 0. credentials (placeholders only in the repo)
  cp .env.example .env
  nano .env                                  # paste your real key here
  set -a && source .env && set +a

  # 1. deploy — installs deps, prints tags, verifies budget/alert, smoke test
  bash deploy/deploy.sh

  # 2. PREDICT FIRST — before any traffic
  python3 code/token_cost.py --in 120 --out 130 \
      --in-price <FROM_CONSOLE> --out-price <FROM_CONSOLE> --requests 40

  # 3. run the fixed volume (--rpm 15 stays under the free tier's 20/min cap)
  python3 app/donor_letters.py --requests 40 --rpm 15

  # 4. reconcile predicted vs measured
  python3 deploy/reconcile.py --in-price <X> --out-price <Y> \
      --predicted-requests 40 --predicted-in 120 --predicted-out 130

  # 5. run the FinOps alert against the real cost export
  bash deploy/finops_alerts_gm.sh --budget 25 --threshold 0.8

To test the whole pipeline without spending anything, add --mock to step 3.


FINOPS CONTROLS (wired BEFORE traffic)
-------------------------------------------------------------------------------
  Cost-allocation tags : project=donor-letters, env=dev, team=it-ops
  Monthly budget       : $25.00
  Alert thresholds     : 50% / 80% / 100%
  Hard cap             : $50.00  (budgets warn; caps STOP)

See deploy/budget-alert.md for the reasoning and the console screenshot.


PROVIDER
-------------------------------------------------------------------------------
  Provider   : OpenRouter (OpenAI-compatible endpoint)
  Model      : openai/gpt-oss-20b:free
  Free tier  : 20 requests/minute, 50 requests/day
  Paid twin  : openai/gpt-oss-20b -- $0.03/1M input, $0.13/1M output

  The free and paid IDs are the SAME model. COST_REPORT reconciles what this
  run actually billed ($0.00) against what it would have billed at the
  published paid rate for the identical workload.


TOTAL REAL SPEND ON THIS PROJECT
-------------------------------------------------------------------------------
  Requests run           : ______
  Actually billed (USD)  : $0.00        <-- free tier
  Cost at paid rate (USD): $______      <-- what this run would have cost
  Date pulled            : ____-__-__

  A subsidy is not a price. The free tier can be withdrawn or throttled, and
  its 50 req/day ceiling caps this workload's capacity regardless of budget.
  See COST_REPORT.docx section 6.


===============================================================================
