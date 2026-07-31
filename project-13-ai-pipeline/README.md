# Project 13 — A Pipeline for an AI Application

A CI/CD pipeline, eval gate, SLO/error budget, and drift monitoring for a school
help-desk **RAG support bot**.

## Why this exists

The bot was up 100% of the time and confidently told a teacher the wrong
lockdown procedure. Every alarm was watching whether the service was *up*. None
was watching whether it was *right*. This repo is the reliability apparatus that
should have existed on day one.

## Layout

| Path | What it is |
|---|---|
| `app/rag_service.py` | The RAG bot: fixed corpus → retrieval → answer |
| `app/corpus/` | The fixed policy corpus (4 documents) |
| `app/config.py` | Pinned `MODEL_ID` and thresholds — **never** `latest` |
| `evals/cases.jsonl` | 10 adversarial CONTEXT/QUESTION/expected cases |
| `evals/judge.py` | The groundedness eval gate CI calls |
| `monitoring/psi.py` | Data-drift monitoring (PSI) |
| `monitoring/error_budget.py` | SLO → error budget → ship/freeze verdict |
| `slo.yml` | The SLO, the budget, the drift config, rollback-vs-retrain |
| `../.github/workflows/ci.yml` | The pipeline (at repo root) |
| `REPORT.docx` | Threshold justification + regression evidence |
| `agent-log.txt` | What I delegated, what was wrong, where I intervened |

## Pipeline order (this is the lesson)

```
install → lint → unit tests → secret scan → LLM EVAL GATE
   free      free      free         free        slow, paid
```

The expensive nondeterministic gate runs **last**, only on a change that already
passed everything a human could have caught for free.

## Run it locally

```bash
pip install -r requirements.txt
ruff check .
pytest tests/unit -q
python evals/judge.py evals/cases.jsonl --min-groundedness 0.90 --min-pass-rate 0.90
python monitoring/psi.py monitoring/data/reference.txt monitoring/data/current.txt
python monitoring/error_budget.py --slo 0.99 --total 20000 --bad 140
```

## Model configuration

The judge and the service talk to any **OpenAI-compatible** endpoint. Set in
**Settings → Secrets and variables → Actions**:

- `OPENAI_API_KEY` — a **secret**
- `MODEL_ID`, `OPENAI_BASE_URL` — **variables**

With no key set, the service runs extractive and the judge runs its
deterministic offline backend. The gate still blocks regressions and costs $0.

## Least privilege

The CI job declares `permissions: contents: read`. It cannot push to `main`,
cannot merge a PR, cannot edit its own workflow. That matters *because* a coding
agent writes the code that runs here — an agent with write access to a protected
branch could green its own gate.
