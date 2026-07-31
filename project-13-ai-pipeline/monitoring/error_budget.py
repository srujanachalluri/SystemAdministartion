#!/usr/bin/env python3
"""error_budget.py — turn an SLO into an error budget and tell on-call the truth.

An SLO is a promise: "99.5% of answers will be grounded." The error budget is
the *permitted failure* that promise leaves you: 100% - 99.5% = 0.5%. You get to
spend it. Spend it on shipping. When it's gone, you stop shipping and stabilize.

For a nondeterministic AI service we measure the SLI not as up/down but as a
QUALITY RATE over a window: grounded answers / total answers. Same arithmetic.

    python error_budget.py --slo 0.995 --total 20000 --bad 140
"""
import argparse


def report(slo: float, total: int, bad: int):
    budget = round((1 - slo) * total)        # how many bad answers we may have
    remaining = budget - bad
    burned = bad / budget if budget else float("inf")
    sli = 1 - bad / total if total else 1.0

    print(f"SLO target          : {slo:.3%} grounded")
    print(f"Measured SLI        : {sli:.3%} grounded ({total - bad}/{total})")
    print(f"Error budget (window): {budget} bad answers allowed")
    print(f"Spent               : {bad}  ({burned:.0%} of budget)")
    print(f"Remaining           : {remaining}")
    print("-" * 48)
    if remaining < 0:
        print("VERDICT: BUDGET EXHAUSTED -> freeze releases, stabilize, "
              "consider rollback/retrain. The promise is broken.")
    elif burned >= 0.75:
        print("VERDICT: BURN RATE HIGH -> slow down, no risky deploys.")
    else:
        print("VERDICT: HEALTHY -> you may keep shipping.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--slo", type=float, required=True, help="e.g. 0.995")
    p.add_argument("--total", type=int, required=True)
    p.add_argument("--bad", type=int, required=True)
    a = p.parse_args()
    report(a.slo, a.total, a.bad)
