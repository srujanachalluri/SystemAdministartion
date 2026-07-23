# Grafana Dashboard — Panels and PromQL

Normal Tier requires at least a **p95-latency panel** and an **error-ratio
panel**, "with the PromQL shown."

## Which metrics we graph

The `inference` (port 8000) and `gpu` (port 9400) scrape targets in
`prometheus.yml` are external services (a vLLM box and an NVIDIA GPU exporter)
that are not running in this lab, so those targets show as **DOWN** — that is
expected. The one target that is always **UP** is Prometheus scraping itself,
and it exposes real HTTP request metrics (a histogram + a counter). We build
both required panels on those metrics, which lets us demonstrate correct PromQL
against live data.

> In Grafana: log in at `http://localhost:3001` (user `admin`, password
> `admin`) → **Connections → Add data source → Prometheus** → URL
> `http://prometheus:9090` → **Save & test**. Then **Dashboards → New → New
> dashboard → Add visualization** and paste the PromQL below.

## Panel 1 — p95 latency (seconds)

```promql
histogram_quantile(0.95, sum(rate(prometheus_http_request_duration_seconds_bucket[5m])) by (le))
```

`histogram_quantile(0.95, ...)` reads the latency histogram buckets and returns
the value under which 95% of requests fall — the standard "p95" tail-latency
signal. Set the panel unit to **seconds (s)**.

## Panel 2 — error ratio (fraction of requests that are 5xx)

```promql
sum(rate(prometheus_http_requests_total{code=~"5.."}[5m]))
/
sum(rate(prometheus_http_requests_total[5m]))
```

This divides the rate of 5xx responses by the rate of all responses, giving the
error ratio as a value between 0 and 1. Set the panel unit to **percent (0.0–1.0)**.

> Tip: to force a non-zero value onto the error-ratio panel for your screenshot,
> hit a bad Prometheus URL a few times, e.g.
> `for i in $(seq 20); do curl -s http://localhost:9090/nope >/dev/null; done`,
> then watch the panel over the next minute.

Take a screenshot of the dashboard with **both panels and their PromQL visible**
(click a panel → Edit to show the query) and paste it into REPORT.docx.
