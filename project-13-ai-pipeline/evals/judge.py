#!/usr/bin/env python3
"""judge.py - the groundedness eval gate. Adapted from code/judge.py.

What it does, in order, for every case in evals/cases.jsonl:
  1. asks the RAG service the case's QUESTION,
  2. scores the answer for GROUNDEDNESS against the context the service used,
  3. checks the answer against the case's EXPECTED string (correctness),
  4. exits 1 - failing the CI build - if either rate falls below threshold.

Two judge backends, same rubric:
  * LLM judge (OPENAI_API_KEY set) - the professor's example-grounded rubric,
    temperature 0, sent to a PINNED model over any OpenAI-compatible endpoint.
  * OFFLINE judge (no key) - deterministic support checking. Every content word
    and, strictly, every number in the answer must appear in the context.
    Slower to be fooled by fluency because it cannot read fluency at all.

The offline judge exists so the gate is reproducible without a paid key. Its
limits are stated honestly in REPORT.docx: it verifies SUPPORT, not meaning.

Usage (this is exactly what ci.yml runs):
    python evals/judge.py evals/cases.jsonl --min-groundedness 0.90 --min-pass-rate 0.90
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import rag_service  # noqa: E402
from app.config import MIN_GROUNDEDNESS, MODEL_ID, USE_LLM  # noqa: E402

RUBRIC = """You are a strict groundedness judge. Given CONTEXT and an ANSWER,
return JSON {"grounded": true|false, "reason": "<one sentence>"}.
Rule: grounded=true ONLY if every factual claim in ANSWER is supported by CONTEXT.
A fluent answer that adds facts not in CONTEXT is grounded=false (a hallucination).
An honest refusal when CONTEXT is empty is grounded=true.
Do not reward confidence. Do not reward style. Support only.
Return ONLY the JSON object, nothing else."""

STOPWORDS = rag_service.STOPWORDS | {
    "please", "contact", "that", "have", "not", "your", "this", "with", "from",
    "by", "after", "before", "all", "any", "must", "should", "will", "no",
}


def _words(text):
    return [w for w in re.findall(r"[a-z0-9:]+", text.lower()) if w not in STOPWORDS]


def judge_offline(context, answer):
    """Deterministic support check. No model, no network, no cost."""
    if not context.strip():
        ok = rag_service.REFUSAL.lower()[:20] in answer.lower()
        return {"grounded": ok,
                "reason": "empty context: refusal is the only grounded answer"}

    ctx = set(_words(context))
    ans = _words(answer)
    if not ans:
        return {"grounded": False, "reason": "empty answer"}

    # Hard rule: every number in the answer must appear in the context.
    for w in ans:
        if any(ch.isdigit() for ch in w) and w not in ctx:
            return {"grounded": False, "reason": f"fabricated number or figure: {w!r}"}

    supported = sum(1 for w in ans if w in ctx)
    ratio = supported / len(ans)
    return {"grounded": ratio >= 0.85,
            "reason": f"{supported}/{len(ans)} content words supported by context"}


def judge_llm(context, answer):
    """LLM-as-a-judge. Pinned model, temperature 0, explicit rubric."""
    from openai import OpenAI

    from app.config import OPENAI_API_KEY, OPENAI_BASE_URL

    client = OpenAI(base_url=OPENAI_BASE_URL, api_key=OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model=MODEL_ID,
        temperature=0,
        messages=[
            {"role": "system", "content": RUBRIC},
            {"role": "user", "content": f"CONTEXT:\n{context}\n\nANSWER:\n{answer}"},
        ],
    )
    raw = resp.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    return json.loads(raw)


def run(eval_file):
    cases = [json.loads(line) for line in open(eval_file, encoding="utf-8") if line.strip()]
    if not cases:
        raise SystemExit(f"no eval cases found in {eval_file}")

    judge = judge_llm if USE_LLM else judge_offline
    grounded = passed = 0

    print(f"model id : {MODEL_ID}  (pinned, never 'latest')")
    print(f"service  : {'LLM' if USE_LLM else 'STUB (extractive)'} mode")
    print(f"judge    : {'LLM-as-a-judge' if USE_LLM else 'offline deterministic'}")
    print("-" * 72)

    for c in cases:
        answer, ctx_used = rag_service.answer(c["question"])
        verdict = judge(ctx_used, answer)
        is_grounded = bool(verdict["grounded"])
        is_correct = all(s.lower() in answer.lower() for s in c["expected_contains"])
        grounded += is_grounded
        passed += is_correct
        flag = "OK  " if (is_grounded and is_correct) else "FAIL"
        print(f"[{flag}] {c['id']} grounded={is_grounded} correct={is_correct}")
        print(f"       Q: {c['question']}")
        print(f"       A: {answer[:110]}")
        if not (is_grounded and is_correct):
            print(f"       WHY: {verdict['reason']}")

    n = len(cases)
    return grounded / n, passed / n, n


def main():
    ap = argparse.ArgumentParser(description="Groundedness eval gate for the RAG support bot.")
    ap.add_argument("eval_file", nargs="?", default="evals/cases.jsonl")
    ap.add_argument("--min-groundedness", type=float, default=MIN_GROUNDEDNESS)
    ap.add_argument("--min-pass-rate", type=float, default=0.90)
    args = ap.parse_args()

    g_rate, p_rate, n = run(args.eval_file)
    print("-" * 72)
    print(f"groundedness = {g_rate:.3f} over {n} cases (threshold {args.min_groundedness:.2f})")
    print(f"pass rate    = {p_rate:.3f} over {n} cases (threshold {args.min_pass_rate:.2f})")

    if g_rate < args.min_groundedness or p_rate < args.min_pass_rate:
        print("FAIL: quality regression. Blocking the build.")
        sys.exit(1)
    print("PASS: quality gate satisfied.")
    sys.exit(0)


if __name__ == "__main__":
    main()
