# Project 7 — Ship a Model in a Box

A private **Verse Helper** for Mercy Lutheran: a local LLM (Ollama serving `llama3.2:3b`)
behind the OpenAI-compatible API, a small FastAPI app in front, and an optional chat UI —
packaged so a stranger can `git clone` and `docker compose up -d` and get the exact same
stack on a fresh machine. No student data leaves the building.

## Run it (one command)
```bash
docker compose up -d
docker compose exec ollama ollama pull llama3.2:3b   # one-time model download
./smoke_test.sh                                      # prove it serves
```
Open the chat UI at http://localhost:3000 · API at http://localhost:8000 · model at http://localhost:11434

## Files
| File | What it is |
|---|---|
| `Dockerfile` | **Hand-authored** hardened app image — pinned base, multi-stage, non-root, deps-before-source, HEALTHCHECK |
| `compose.yaml` | The whole stack: `ollama` + `verse-api` + `open-webui`, named volumes, service-name networking |
| `app.py` | The FastAPI Verse Helper (fronts Ollama over `/v1`) |
| `requirements.txt` | Pinned Python dependencies |
| `smoke_test.sh` | Checks liveness + backend + real inference; fails loud |
| `.dockerignore` / `.gitignore` | Keep `.env`, `.git`, caches out of the image and repo |
| `.env.example` | Runtime config (copy to `.env`) — never baked into the image |
| `REPORT.docx` | **Main deliverable** — commands + output placeholders (you paste your run output) |
| `DECISION.docx` | **Hard tier** — Ollama vs vLLM vs NIM memo |
| `REVIEW.docx` | **Hard tier** — line-by-line review of an AI-generated Dockerfile |

## Key design choices (why this image is safe)
- **Pinned base** `python:3.12.7-slim` — no `:latest`, so it builds the same next year.
- **Non-root** `appuser` (uid 10001) — the web-facing app never runs as root.
- **Deps before source** — Docker caches the slow `pip install`; code changes rebuild fast.
- **Multi-stage** — build tools stay in the builder; the runtime image is small.
- **HEALTHCHECK** hits `/health` — "up" means actually serving, not just alive.
- **Named volume** `ollama-models` — weights survive `docker rm` (no re-download).
- **Service-name networking** — `verse-api` reaches the backend at `http://ollama:11434`, never `localhost`.
- **Runtime config** — backend URL/model injected via env, never baked into the image.

## Rubric coverage
- One-command bring-up → `docker compose up -d`
- Model on `/v1` → `curl http://localhost:11434/v1/chat/completions`
- Weights persist → `docker rm` + re-`up`, `ollama list` (REPORT §4)
- Pinned / non-root / deps-first / healthcheck → `Dockerfile`
- Smoke test → `smoke_test.sh`
- No baked secret → `.dockerignore` + `docker history` (REPORT §7)
- Hard tier → `DECISION.docx`, `REVIEW.docx`
