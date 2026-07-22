#!/usr/bin/env bash
# load-logs.sh — load sample-logs.jsonl into OpenSearch using the _bulk API,
# then verify the document count. Run this AFTER `docker compose ... up -d`.
#
#   ./load-logs.sh
#
# Expected result at the end: "count" : 14
set -euo pipefail

OS_URL="${OS_URL:-http://localhost:9200}"
INDEX="${INDEX:-storefront-logs}"
LOGFILE="${LOGFILE:-sample-logs.jsonl}"

echo ">> Waiting for OpenSearch at ${OS_URL} ..."
until curl -s "${OS_URL}" >/dev/null 2>&1; do sleep 2; done
echo ">> OpenSearch is up."

# Start clean so re-running does not double-count documents.
echo ">> Deleting old index (ignore 'index_not_found' the first time)..."
curl -s -X DELETE "${OS_URL}/${INDEX}" >/dev/null || true

# The _bulk API needs an action line before each document. Prepend
# {"index":{}} to every log line to build a valid NDJSON bulk body.
echo ">> Building bulk body from ${LOGFILE} ..."
awk '{ print "{\"index\":{}}"; print }' "${LOGFILE}" > bulk.ndjson

echo ">> Bulk loading into index '${INDEX}' ..."
curl -s -H 'Content-Type: application/x-ndjson' \
     -X POST "${OS_URL}/${INDEX}/_bulk" \
     --data-binary @bulk.ndjson > /dev/null

# Refresh so the documents are immediately searchable, then count.
curl -s -X POST "${OS_URL}/${INDEX}/_refresh" > /dev/null
echo ">> Document count (should be 14):"
curl -s "${OS_URL}/${INDEX}/_count?pretty"
