# Catch the Impostor — Project 3

A self-scoring anomaly-detection pipeline over the Shepherd's Gate Health
Cooperative authentication log. Python 3 standard library only — no
third-party packages required.

## Reproduce the graded run

```bash
python3 catch.py code/auth_events.csv --truth code/ground_truth.csv
```

This prints the alerts and the precision/recall score. The saved output is in
[`run_output.txt`](run_output.txt).

## What it does

Five hand-built detectors over the auth log:

| Detector | Signal |
|----------|--------|
| Impossible travel | successive successful logins whose implied speed (haversine ÷ hours) exceeds the threshold |
| Off-hours admin | `role=admin` activity outside business hours (service accounts allow-listed) |
| Brute force | many failed logins against one account in a window |
| Password spray | one source IP failing against many distinct accounts |
| Privilege escalation | an account granting itself the admin role |

## Files

- `catch.py` — the detector and self-scorer
- `config.json` — tuned thresholds + service-account allow-list
- `code/` — provided starter data (`auth_events.csv`, `ground_truth.csv`, `impossible_travel.py`)
- `run_output.txt` — captured run output (alerts + score)
- `REPORT.docx` — write-up, including the tuning judgment call and AI-usage disclosure

## Configuration

All thresholds are in `config.json`. Notably, the impossible-travel threshold is
tuned to **3000 km/h** (above the 900 km/h default) to absorb GeoIP jitter on
domestic logins while still catching intercontinental account takeovers. The
reasoning is in Section 5 of `REPORT.docx`.

## Result

10 alerts, **precision 1.000, recall 1.000**, zero false positives/negatives.
