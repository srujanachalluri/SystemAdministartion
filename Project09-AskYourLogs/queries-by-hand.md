# Incident Questions — Answered By Hand (OpenSearch)

These are the **exact queries** I wrote by hand against the `storefront-logs`
index in OpenSearch, plus the answers I read from the results. Run each one and
paste the JSON output into REPORT.docx. (You can also paste these into
OpenSearch Dashboards → Dev Tools instead of curl — same queries.)

I use `match` on level/service/trace_id and a `range` on `ts` so the queries
work no matter how OpenSearch auto-mapped the fields.

---

## Q1. Why did checkout fail at 14:05?

```bash
curl -s 'http://localhost:9200/storefront-logs/_search?pretty' \
  -H 'Content-Type: application/json' -d '{
  "size": 20,
  "query": { "bool": { "filter": [
    { "match": { "level": "ERROR" } },
    { "range": { "ts": { "gte": "2026-06-12T14:05:00", "lt": "2026-06-12T14:06:00" } } }
  ]}}
}'
```

**Answer:** Checkout did not fail on its own. The `payments` service logged
`authorize failed: upstream timeout` (provider = stripe, `latency_ms` ≈ 5001,
`http_status` = 504). Because the card could not be authorized, the `checkout`
service logged `checkout aborted` with `reason: payment_declined`. So the
checkout failures at 14:05 were **caused by the upstream payment provider
timing out**, not by a bug in checkout itself.

---

## Q2. Which users were affected?

```bash
curl -s 'http://localhost:9200/storefront-logs/_search?pretty' \
  -H 'Content-Type: application/json' -d '{
  "size": 20,
  "_source": ["ts","user","trace_id","reason"],
  "query": { "bool": { "filter": [
    { "match": { "service": "checkout" } },
    { "match": { "level":   "ERROR"    } }
  ]}}
}'
```

**Answer:** Three users were affected during the incident window:

| user   | trace_id | time (Z)          |
|--------|----------|-------------------|
| u-4419 | d4e1     | 14:05:02.901      |
| u-4420 | e2a8     | 14:05:03.210      |
| u-4422 | aa01     | 14:05:09.260      |

(User u-4430 checked out successfully at 14:07 **after** the provider
recovered, so they were not affected.)

---

## Q3. Root cause vs. symptom — correlate by ts and trace_id

Pick one affected transaction and pull **every** service that touched that
`trace_id`, in time order:

```bash
curl -s 'http://localhost:9200/storefront-logs/_search?pretty' \
  -H 'Content-Type: application/json' -d '{
  "size": 20,
  "sort": [ { "ts": { "order": "asc" } } ],
  "query": { "match": { "trace_id": "d4e1" } }
}'
```

**Answer:** For trace_id `d4e1` you see two lines that share the same trace:

1. `14:05:02.778` — **payments**: `authorize failed: upstream timeout` (504, 5001ms) ← **ROOT CAUSE**
2. `14:05:02.901` — **checkout**: `checkout aborted` / `payment_declined` ← **SYMPTOM**

- **Symptom** (what the customer/board saw): checkout aborted, payment declined.
- **Root cause** (why it happened): the upstream payment provider (stripe)
  timed out — a 5-second latency that returned HTTP 504. This was foreshadowed
  at `14:04:01` by a WARN `provider latency high` (`latency_ms` 2710) on the
  same provider. The `trace_id` is what proves the link: the same ID appears on
  both the payments timeout and the checkout abort, so we know the abort was
  downstream of the timeout, not an independent failure.

The same pattern repeats for trace_ids `e2a8` and `aa01`. Three separate
customer-facing "checkout" failures are really **one** incident: the payment
provider timing out.
