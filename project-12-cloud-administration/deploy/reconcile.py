#!/usr/bin/env python3
"""reconcile.py -- put the PREDICTION and the MEASURED RUN side by side.

Reads output/run-log.jsonl (the token counts the run actually produced) and
prices them at the same rates used for the prediction. The result is the
"measured" column of COST_REPORT.docx. The third column -- the provider's
billed amount -- must be typed in by hand from the billing console, because
that is the only number that is authoritative.

Usage:
  python3 deploy/reconcile.py --in-price 0.15 --out-price 0.60 \
      --predicted-requests 100 --predicted-in 120 --predicted-out 130
"""
import argparse
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG = ROOT / "output" / "run-log.jsonl"


def price(in_tok, out_tok, in_price, out_price):
    return (in_tok / 1e6) * in_price + (out_tok / 1e6) * out_price


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--in-price", type=float, required=True, help="$ per 1M input tokens (from the live console)")
    p.add_argument("--out-price", type=float, required=True, help="$ per 1M output tokens (from the live console)")
    p.add_argument("--predicted-requests", type=int, required=True)
    p.add_argument("--predicted-in", type=int, required=True, help="predicted input tokens/request")
    p.add_argument("--predicted-out", type=int, required=True, help="predicted output tokens/request")
    a = p.parse_args()

    if not LOG.exists():
        raise SystemExit(f"{LOG} not found -- run app/donor_letters.py first.")

    rows = [json.loads(line) for line in LOG.read_text().splitlines() if line.strip()]
    n = len(rows)
    act_in = sum(r["prompt_tokens"] for r in rows)
    act_out = sum(r["completion_tokens"] for r in rows)

    pred_in = a.predicted_requests * a.predicted_in
    pred_out = a.predicted_requests * a.predicted_out
    pred_cost = price(pred_in, pred_out, a.in_price, a.out_price)
    act_cost = price(act_in, act_out, a.in_price, a.out_price)

    def pct(new, old):
        return "n/a" if not old else f"{(new - old) / old * 100:+.1f}%"

    print(f"prices used     : ${a.in_price}/1M in, ${a.out_price}/1M out")
    print(f"{'':16}{'PREDICTED':>14}{'MEASURED':>14}{'DELTA':>12}")
    print("-" * 56)
    print(f"{'requests':16}{a.predicted_requests:>14,}{n:>14,}{pct(n, a.predicted_requests):>12}")
    print(f"{'input tokens':16}{pred_in:>14,}{act_in:>14,}{pct(act_in, pred_in):>12}")
    print(f"{'output tokens':16}{pred_out:>14,}{act_out:>14,}{pct(act_out, pred_out):>12}")
    print(f"{'cost (USD)':16}{pred_cost:>14.4f}{act_cost:>14.4f}{pct(act_cost, pred_cost):>12}")
    print("-" * 56)
    print("MEASURED is priced from my own token counts. It is NOT the bill.")
    print("Type the provider's billed figure into COST_REPORT.docx by hand and")
    print("explain any gap (rounding, minimum billing units, cached input, taxes).")


if __name__ == "__main__":
    main()
