#!/usr/bin/env python3
"""ask_logs.py — a tiny natural-language-to-query bridge over JSON logs.

The point of this script is NOT to be clever. It is to make the architecture
of "AI-assisted log analysis" visible: an LLM TRANSLATES English into a
deterministic, inspectable filter; your code RUNS the filter; you VERIFY the
result against the raw lines. The model never touches the data directly, and
you can always read the predicate it produced.

Usage:
    export OPENAI_BASE_URL=http://localhost:11434/v1   # Ollama, vLLM, etc.
    export OPENAI_API_KEY=not-needed
    # optional: pin a model; defaults to llama3.1:8b (the one Appendix B pulls)
    export MODEL=llama3.1:8b
    python ask_logs.py code/sample-logs.jsonl "why did checkout fail at 14:05?"

The model returns a JSON predicate. We apply it ourselves and PRINT IT so a
human can audit the query before trusting the answer. AI proposes; you verify.
"""
import json
import os
import sys
from openai import OpenAI  # the universal OpenAI-compatible client (see Ch07)

# The model id Appendix B actually pulls (`ollama pull llama3.1:8b`).
# Override with MODEL=... if you pinned a different local/cloud model.
MODEL = os.environ.get("MODEL", "llama3.1:8b")

SCHEMA_HINT = (
    "Each log line is a JSON object with keys: ts (ISO8601), level "
    "(INFO|WARN|ERROR), service, trace_id, msg, and optional fields. "
    "Translate the user's question into a JSON filter of the form "
    '{"level": "...", "service": "...", "ts_prefix": "...", "contains": "..."} '
    "Use only keys you actually need; omit the rest. Return ONLY the JSON."
)


def build_filter(client, question: str) -> dict:
    resp = client.chat.completions.create(
        model=MODEL,  # default llama3.1:8b (Appendix B); set MODEL=... to override
        messages=[
            {"role": "system", "content": SCHEMA_HINT},
            {"role": "user", "content": question},
        ],
        temperature=0,  # determinism matters for a query translator
    )
    return json.loads(resp.choices[0].message.content)


def matches(line: dict, f: dict) -> bool:
    if "level" in f and line.get("level") != f["level"]:
        return False
    if "service" in f and line.get("service") != f["service"]:
        return False
    if "ts_prefix" in f and not str(line.get("ts", "")).startswith(f["ts_prefix"]):
        return False
    if "contains" in f and f["contains"].lower() not in json.dumps(line).lower():
        return False
    return True


def main() -> None:
    path, question = sys.argv[1], sys.argv[2]
    client = OpenAI()  # reads OPENAI_BASE_URL / OPENAI_API_KEY from the env
    f = build_filter(client, question)
    print(f"# AI-generated filter (AUDIT THIS BEFORE TRUSTING IT):\n# {f}\n")
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = json.loads(raw)
            if matches(line, f):
                print(raw.rstrip())


if __name__ == "__main__":
    main()
