#!/usr/bin/env python3
"""donor_letters.py -- Project 12 AI workload for Grace & Mercy Relief.

Drafts short thank-you letters for donors using an OpenAI-COMPATIBLE endpoint,
so only base_url + api_key change if we switch providers (anti-lock-in hedge,
per deploy-notes.txt section 1A).

SYNTHETIC PII ONLY. app/synthetic_donors.csv contains invented people. Never
point this at a real donor export.

Every call captures resp.usage (prompt_tokens / completion_tokens) so the actual
token volume can be reconciled against the prediction from token_cost.py.

Usage:
  # dry run, no money spent, no key needed -- proves the harness works
  python3 app/donor_letters.py --requests 5 --mock

  # real run against the provider
  python3 app/donor_letters.py --requests 100
"""
import argparse
import csv
import json
import os
import pathlib
import random
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
DONORS = ROOT / "app" / "synthetic_donors.csv"
OUTDIR = ROOT / "output"

# Cost-allocation tags. These are stamped on the API key / resource at the
# provider AND echoed here so every log line is attributable to a cost centre.
TAGS = {
    "project": "donor-letters",
    "env": "dev",
    "team": "it-ops",
}

SYSTEM_PROMPT = (
    "You write short, warm thank-you letters on behalf of Grace & Mercy Relief, "
    "a Christian relief organization. Be sincere, specific about the fund the "
    "gift supports, and never invent facts about the donor. 90 words maximum."
)


def load_donors():
    with open(DONORS, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def build_prompt(d):
    return (
        f"Donor: {d['first_name']} {d['last_name']} of {d['city']}. "
        f"Gift: ${d['gift_amount_usd']} to the {d['fund']} fund on {d['gift_date']}. "
        f"Write the thank-you letter."
    )


def mock_call(prompt):
    """Simulate a response so the pipeline can be tested with zero spend."""
    time.sleep(0.02)
    words = random.randint(70, 95)
    return {
        "text": "[MOCK] Thank-you letter draft (" + str(words) + " words).",
        "prompt_tokens": len(SYSTEM_PROMPT.split()) + len(prompt.split()) + 12,
        "completion_tokens": int(words * 1.35),
    }


def real_call(client, model, prompt, max_tokens):
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=max_tokens,   # CAP the output: output tokens cost 4-8x input
        temperature=0.7,
    )
    u = resp.usage
    return {
        "text": resp.choices[0].message.content,
        "prompt_tokens": u.prompt_tokens,
        "completion_tokens": u.completion_tokens,
    }


def main():
    p = argparse.ArgumentParser(description="Draft donor thank-you letters.")
    p.add_argument("--requests", type=int, default=100, help="fixed request volume")
    p.add_argument("--max-tokens", type=int, default=300, help="output cap per request")
    p.add_argument("--mock", action="store_true", help="simulate; spend nothing")
    p.add_argument("--model", default=os.getenv("MODEL_ID", "gpt-4o-mini"))
    p.add_argument("--rpm", type=int, default=0,
                   help="throttle to N requests/minute (0 = no throttle). "
                        "Free tiers are rate-limited: Groq free is 30 RPM, "
                        "OpenRouter free is 20 RPM. Use --rpm 25 / --rpm 15.")
    args = p.parse_args()

    # A rate limit is a capacity constraint, not just an annoyance: it caps how
    # much work this design can absorb per day regardless of budget.
    delay = 60.0 / args.rpm if args.rpm > 0 else 0.0

    client = None
    if not args.mock:
        try:
            from openai import OpenAI
        except ImportError:
            sys.exit("openai SDK missing. Run: pip install -r requirements.txt")
        key = os.getenv("PROVIDER_API_KEY")
        if not key:
            sys.exit("PROVIDER_API_KEY is not set. Copy .env.example to .env and export it, "
                     "or re-run with --mock.")
        client = OpenAI(base_url=os.getenv("PROVIDER_BASE_URL") or None, api_key=key)

    donors = load_donors()
    OUTDIR.mkdir(exist_ok=True)
    log_path = OUTDIR / "run-log.jsonl"

    tot_in = tot_out = 0
    started = time.time()
    errors = 0

    with open(log_path, "w", encoding="utf-8") as log:
        for i in range(args.requests):
            d = donors[i % len(donors)]
            prompt = build_prompt(d)
            try:
                if args.mock:
                    r = mock_call(prompt)
                else:
                    r = real_call(client, args.model, prompt, args.max_tokens)
            except Exception as exc:            # keep the run going; count the failure
                errors += 1
                print(f"  request {i+1}: ERROR {exc}", file=sys.stderr)
                if "rate" in str(exc).lower() or "429" in str(exc):
                    print("    (rate limited -- re-run with a lower --rpm)", file=sys.stderr)
                    time.sleep(5)
                continue

            if delay:
                time.sleep(delay)

            tot_in += r["prompt_tokens"]
            tot_out += r["completion_tokens"]
            log.write(json.dumps({
                "n": i + 1,
                "donor_id": d["donor_id"],
                "model": "MOCK" if args.mock else args.model,
                "prompt_tokens": r["prompt_tokens"],
                "completion_tokens": r["completion_tokens"],
                "tags": TAGS,
            }) + "\n")

            if (i + 1) % 25 == 0:
                print(f"  ... {i+1}/{args.requests} requests")

    ok = args.requests - errors
    elapsed = time.time() - started
    summary = f"""RUN SUMMARY -- Project 12 donor-letters workload
mode              : {"MOCK (no spend)" if args.mock else "REAL (billable)"}
provider base_url : {os.getenv("PROVIDER_BASE_URL") or "(default: OpenAI Platform)"}
model             : {"MOCK" if args.mock else args.model}
throttle          : {f"{args.rpm} req/min" if args.rpm else "none"}
tags              : project={TAGS['project']} env={TAGS['env']} team={TAGS['team']}
requests attempted: {args.requests}
requests OK       : {ok}
requests failed   : {errors}
input  tokens     : {tot_in:,}
output tokens     : {tot_out:,}
avg in  / request : {(tot_in / ok) if ok else 0:.1f}
avg out / request : {(tot_out / ok) if ok else 0:.1f}
wall clock        : {elapsed:.1f}s
per-request log   : output/run-log.jsonl
"""
    print("\n" + summary)
    (OUTDIR / "usage-summary.txt").write_text(summary, encoding="utf-8")


if __name__ == "__main__":
    main()
