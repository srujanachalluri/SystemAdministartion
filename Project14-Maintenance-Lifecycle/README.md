# Project 14 — Maintenance and the Lifecycle of Things

**Course:** System Administration and Maintenance
**Student:** Srujana Challuri
**Date:** 2026-07-30
**Service used throughout:** `ministry-rag-summarizer` — RAG summarization of donor correspondence

This is a **conditioning week**: eleven reps plus a capstone. Each rep is a small
runnable piece of a real model lifecycle and maintenance plan; the capstone
assembles them into **[`LIFECYCLE_PLAN.txt`](LIFECYCLE_PLAN.txt)**.

---

## Start here

| | File |
|---|---|
| **Capstone deliverable** | [`LIFECYCLE_PLAN.txt`](LIFECYCLE_PLAN.txt) |
| **AI honesty log** | [`agent-log.txt`](agent-log.txt) |

## The reps

| Rep | Topic | File |
|---|---|---|
| 1 | Triage a CVE feed deterministically (predict → run → compare) | [`reps/rep01-triage-prediction.md`](reps/rep01-triage-prediction.md) |
| 2 | Triage the same feed with AI, then judge the gap | [`reps/rep02-ai-gap.md`](reps/rep02-ai-gap.md) |
| 3 | Make a change reviewable and reversible (change record) | [`reps/rep03-change-record.md`](reps/rep03-change-record.md) |
| 4 | Detect drift with an Ansible dry run | [`reps/rep04-drift-check.md`](reps/rep04-drift-check.md) |
| 5 | Drift that changes model behavior | [`reps/rep05-ai-drift.md`](reps/rep05-ai-drift.md) |
| 6 | Governance-grade model card | [`reps/rep06-model_card.yaml`](reps/rep06-model_card.yaml) + [notes](reps/rep06-notes.md) |
| 7 | Minimal AIBOM + format diff | [`reps/rep07-aibom.cdx.json`](reps/rep07-aibom.cdx.json) + [notes](reps/rep07-aibom-notes.md) |
| 8 | Deprecation migration runbook + Step-0 inventory grep | [`reps/rep08-migration-runbook.md`](reps/rep08-migration-runbook.md) |
| 9 | One system across NIST RMF / EU AI Act / ISO 42001 | [`reps/rep09-framework-map.md`](reps/rep09-framework-map.md) |
| 10 | Track the moving regulation (dated, cited) | [`reps/rep10-regulation-status.md`](reps/rep10-regulation-status.md) |
| 11 | Capacity and retirement | [`reps/rep11-registry-retirement.md`](reps/rep11-registry-retirement.md) |

## Supporting directories

- `code/` — Chapter 14 starter files (`patch_triage.py`, `cve_feed.json`, `model_card.yaml`, `model-migration-runbook.txt`)
- `ansible/` — five-task baseline playbook for the Rep 4 drift check
The Rep 8 Step-0 inventory grep runs against this repository itself — the model
card, the AIBOM, and the registry are the estate being inventoried.

---

## Reproduce everything

```bash
# Rep 1 — deterministic triage
python3 code/patch_triage.py code/cve_feed.json

# Rep 4 — converge, then detect drift without fixing it
ansible-playbook -i ansible/inventory.ini ansible/site.yml
echo "temperature=1.0" >> /tmp/rep4-demo/inference.conf
chmod 666 /tmp/rep4-demo/inference.conf
touch /tmp/rep4-demo/UNMANAGED_OVERRIDE
ansible-playbook -i ansible/inventory.ini ansible/site.yml --check --diff

# Rep 7 — validate the AIBOM
python3 -m json.tool reps/rep07-aibom.cdx.json > /dev/null && echo "valid JSON"

# Rep 8 — Step-0 inventory grep (scoped, then widened)
grep -rn "claude-opus-4-1\|claude-sonnet-4-0" . \
  --include="*.py" --include="*.yaml" --include="*.tf" --include="*.json"
grep -rl "claude-opus-4-1\|claude-sonnet-4-0" .
```

---

## Live-cited facts (dated, per the ground rules)

All verified **2026-07-30**. Re-verify before relying on them.

- `claude-opus-4-1-20250805` — deprecation notice 2026-06-05, **retires 2026-08-05**.
  Source: <https://docs.anthropic.com/en/docs/resources/model-deprecations>
- EU AI Act high-risk obligations — original statutory date **2026-08-02**;
  Digital Omnibus defers stand-alone Annex III to **2027-12-02**; the Omnibus **has
  been formally adopted** (Parliament 2026-06-16, Council 2026-06-29, in force
  2026-07-27 as Regulation (EU) 2026/1744). Details and sources in
  [`reps/rep10-regulation-status.md`](reps/rep10-regulation-status.md).

## AI use

Phase 2 (agentic) policy. A copilot assisted with drafting; every delegation, every
place it was wrong, and every place I intervened is recorded in
[`agent-log.txt`](agent-log.txt). The risk classifications, gate thresholds,
retirement decisions, and all signature lines are mine — the signature lines are
deliberately left blank for a human.
