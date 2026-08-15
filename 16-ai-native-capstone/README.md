# Final Project (Capstone) — Architect the 2030 Organization

**Project 14 · Chapter 16 — The AI-Native Enterprise**
Course: System Administration and Maintenance

Scenario organisation: **Cornerstone Relief International (CRI)** — a 600-person
Christian relief and development organisation, nine-person HQ IT team, field
offices on four continents, operating under a board mandate to become AI-native
after a year that included a US$240,000 deepfake attempt, a ransomware scare, and
three years of beneficiary case notes pasted into a public chatbot.

---

## The design in one sentence

Two serving lanes — a **self-hosted RESTRICTED lane** for beneficiary case notes
(egress deny-all) and a **commercial API lane** for everything else — on one
Kubernetes control plane, with one identity plane above, one OpenTelemetry +
WORM-audit backbone beneath, and a written autonomy ladder deciding what a
machine may do without asking a human.

---

## Deliverables

| File | Document | Owner in the scenario |
|---|---|---|
| `architecture.docx` | **1** — two-lane architecture, the §16.1 organ table with **both halves filled**, request walkthrough, trust boundaries | Daniel Okoro |
| `ai-strategy.txt` | **2** — what CRI uses AI *for* and what it *runs*; model tiers; refused uses; build vs buy vs self-host | Grace Adeyemi |
| `automation-plan.txt` | **3** — AIOps design + autonomy ladder, 10 actions across 4 rungs | Hannah Kim |
| `security-plan.txt` | **4** — traditional controls + OWASP LLM Top 10 → MITRE ATLAS + the indirect prompt-injection kill chain | Priya Raman |
| `cost-analysis.txt` | **5** — VRAM/KV-cache sizing, 3 scenarios, the crossover, a sensitivity table | Ruth Mensah |
| `governance.txt` | **6** — the ten-row control set + EU AI Act Art. 14 / Art. 12 / NIST RMF mapping | Priya Raman |
| `REPORT.docx` | Executive summary the board can read + the Codespaces verification log | — |
| `agent-log.txt` | **Required** — every task delegated, what the agent produced, where it was wrong, where I intervened | — |
| `decision-memo.docx` | **Hard tier** — the architect's judgment to the board, with reversal conditions | — |
| `make_docs.py` | Regenerates the three `.docx` files from source | — |

### Reference configs (adapted, not submitted as-is)

| File | What changed from the chapter reference |
|---|---|
| `code/inference-platform.yaml` | Split into **two lanes**; GPU count derived from the VRAM math, not guessed; trust boundaries B1–B5 wired in; owners named |
| `code/autonomy-ladder.yaml` | 10 CRI actions with named owners, **numeric** blast radii, permanent ceilings, a five-entry `never_automate` floor with no promotion path, automatic demotion |
| `code/governance-checklist.txt` | Every cell filled with a **named human**, an artifact and a gate |
| `code/estate_cost.py` | Added the **KV-cache term** to VRAM sizing, three growth scenarios, a real **crossover** calculation, and a **utilisation sensitivity** table |

---

## Reproduce the results

```bash
# 1. validate the configs
python3 -c "import yaml; yaml.safe_load(open('code/autonomy-ladder.yaml')); print('OK')"
python3 -c "import yaml; yaml.safe_load(open('code/inference-platform.yaml')); print('OK')"

# 2. run the sizing + cost model
python3 code/estate_cost.py

# 3. regenerate the Word documents
pip install python-docx
python3 make_docs.py
```

Saved model output: [`cost-model-output.txt`](cost-model-output.txt)

---

## Headline findings

- **VRAM:** 70.0 GB weights + **64.4 GB KV cache** + 16.1 GB overhead = **150.6 GB → 2 × H100-80GB.**
  The KV cache is 48% of live VRAM and it scales with *load*, not model size.
  Sizing only the weights is wrong by a factor of two.
- **Crossover:** CRI runs 132M tokens/month against a mid-tier API crossover of
  **1,569M tokens/month** — CRI is at **8%** of it.
- **The honest conclusion:** self-hosting **never** wins on cost for CRI, at any
  utilisation. It costs **US$70,320/year more** — about 0.6 of a field post.
  CRI self-hosts anyway, because the premium buys data residency and verifiable
  deletion for special-category data about vulnerable people. That argument is
  `decision-memo.docx`, and the number is put in front of the board rather than
  hidden.

---

## Before submitting

- [ ] Complete the EU AI Act citation block in `governance.txt` §4 — source
      consulted, date checked, adoption status, current high-risk date found.
      **This is the one item that cannot be left as a placeholder.**
- [ ] Fill the command outputs in `REPORT.docx` Part 2.
- [ ] Confirm the repository is **public**.
- [ ] Schedule the 60-minute live session; be ready to defend the two-lane split
      and the self-host decision out loud.

---

> *"Unless the LORD builds the house, those who labor build in vain."* — Psalm 127:1 (ESV)
