#!/usr/bin/env bash
# smoke_test.sh — prove the box actually SERVES, not just STARTS.
# Checks three things and exits non-zero (fails loud) if any one fails:
#   1. the app is alive        (/health returns 200)
#   2. the LLM backend is up   (Ollama lists its models)
#   3. real inference works     (/explain returns an actual answer)
#
# Run after the stack is up:
#   ./smoke_test.sh
#   API=http://localhost:8000 OLLAMA=http://localhost:11434 ./smoke_test.sh
set -euo pipefail

API="${API:-http://localhost:8000}"
OLLAMA="${OLLAMA:-http://localhost:11434}"

echo "== 1. App liveness (/health) =="
code=$(curl -s -o /dev/null -w "%{http_code}" "$API/health")
[ "$code" = "200" ] || { echo "FAIL: /health returned $code"; exit 1; }
echo "ok ($code)"

echo "== 2. Backend reachable (Ollama /api/tags) =="
curl -fs "$OLLAMA/api/tags" >/dev/null || { echo "FAIL: backend unreachable"; exit 1; }
echo "ok"

echo "== 3. End-to-end inference (/explain) =="
body='{"reference":"Matthew 28:19","question":"What is the command given here?"}'
resp=$(curl -fs -X POST "$API/explain" -H "Content-Type: application/json" -d "$body")
echo "$resp" | grep -q '"answer"' || { echo "FAIL: no answer field"; echo "$resp"; exit 1; }
echo "ok — model answered"

echo
echo "ALL CHECKS PASSED. The box serves."
echo "Now read the answer — the model is confident, fast, and sometimes wrong."
echo "The container guarantees delivery; you still verify the truth of what was delivered."
