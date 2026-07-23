# Project 9 — Ask Your Logs

Observability stack (Prometheus + Grafana + OpenSearch) that reproduces the
14:05 checkout incident for Cornerstone Faith Resources and puts a
natural-language query layer over the logs.

**Incident in one line:** checkout aborted for three users (u-4419, u-4420,
u-4422) because the upstream payment provider (stripe) timed out (HTTP 504,
~5s). Checkout was the *symptom*; the payment-provider timeout was the *root
cause*. Proven by shared `trace_id` across the payments and checkout services.

## How to run (GitHub Codespace — recommended)

1. On the repo page: **Code → Codespaces → Create codespace on main**.
2. In the Codespace terminal (Docker is already installed):

```bash
cd Project09-AskYourLogs          # cd into this folder

# 1) Bring up the stack
docker compose -f docker-compose.observability.yml up -d
docker compose -f docker-compose.observability.yml ps

# 2) Load the logs and verify 14 documents
chmod +x load-logs.sh
./load-logs.sh                     # last line should read  "count" : 14

# 3) Health-check all four UIs
curl -s http://localhost:9090/-/healthy
curl -s http://localhost:9200 | head -20
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3001/login
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:5601/api/status
```

3. Open the forwarded ports (Codespaces **PORTS** tab) and screenshot each UI:
   Prometheus `9090`, Grafana `3001` (admin/admin), OpenSearch `9200`,
   OpenSearch Dashboards `5601`.

4. **Grafana panels** — add data source Prometheus (`http://prometheus:9090`),
   then build the two panels from `grafana-queries.md` (p95 latency + error
   ratio). Screenshot with the PromQL visible.

5. **By-hand queries** — run the three curl queries in `queries-by-hand.md`.

6. **AI queries** — install Ollama, pull a model, then run `ask_logs.py`:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve > /tmp/ollama.log 2>&1 &
ollama pull llama3.1:8b            # ~4.7GB; or a faster one: ollama pull llama3.2:3b

export OPENAI_BASE_URL=http://localhost:11434/v1
export OPENAI_API_KEY=not-needed
export MODEL=llama3.1:8b           # or llama3.2:3b if you pulled the smaller one
pip install openai

python3 ask_logs.py sample-logs.jsonl "why did checkout fail at 14:05?"
python3 ask_logs.py sample-logs.jsonl "which users were affected?"
python3 ask_logs.py sample-logs.jsonl "what was the root cause of the 14:05 checkout failures?"
```

7. Fill the pasted-output and screenshot placeholders in `REPORT.docx`.

## Deliverables in this folder

| File | What it is |
|------|-----------|
| `docker-compose.observability.yml` | the four-service stack |
| `prometheus.yml` | scrape config |
| `sample-logs.jsonl` | the 14 storefront log lines |
| `load-logs.sh` | bulk-load + verify 14 docs |
| `ask_logs.py` | NL→filter bridge (AI proposes, you verify) |
| `queries-by-hand.md` | the three by-hand OpenSearch queries + answers |
| `grafana-queries.md` | p95 + error-ratio PromQL |
| `keeping-watch.txt` | incident verdict (AI vs by-hand) — **graded** |
| `agent-log.txt` | AI audit trail — **graded** |
| `alert-rules.yml` | SLO burn-rate alert (Medium tier, extra credit) |
| `HARD-memo.txt` | autonomy memo to IT director (Hard tier, extra credit) |
| `REPORT.docx` | the report tying it together |

## Troubleshooting

- **OpenSearch container exits / red:** run `sudo sysctl -w vm.max_map_count=262144`
  then `docker compose ... up -d` again.
- **Ollama slow:** use the smaller model (`ollama pull llama3.2:3b`,
  `export MODEL=llama3.2:3b`). CPU inference of a few short questions is fine.
- **Stop everything:** `docker compose -f docker-compose.observability.yml down -v`
