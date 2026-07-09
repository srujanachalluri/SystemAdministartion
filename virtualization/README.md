# Project 6 — Carve the GPU

Partitioning one **NVIDIA H100 80GB** for four tenants at Concordia Lakes University,
using NVIDIA **MIG** (Multi-Instance GPU) plus time-slicing for the bursty tenant.

> **Substrate honesty:** I have no data-center GPU, so every capture here is a **well-reasoned
> simulation** built in the format of the chapter's `sample-nvidia-smi.txt` and validated
> against the H100 MIG profile table (7-slice ceiling). `gpu_partition.sh` is the exact command
> sequence that produces these captures on real hardware. See `REPORT.docx §0`.

## The decision in one line
> The registrar's FERPA classifier runs on a **dedicated 1g.10gb MIG instance** because protected
> data requires **hardware fault isolation**, which time-slicing and MPS only imitate.

## The partition (5 of 7 slices)
| Tenant | Profile | Slices | Why |
|---|---|---:|---|
| **Registrar (FERPA)** | `1g.10gb` dedicated | 1 | hardware isolation — non-negotiable |
| CS 8B chat | `2g.20gb` | 2 | ~18 GB won't fit a 1g.10gb (OOM); ~5% headroom, flagged |
| Library embedding | `1g.10gb` | 1 | ~3 GB, easy |
| Research notebook | `1g.10gb` time-sliced | 1 | bursty, no isolation → cheapest correct mode |
| **Total** | | **5 / 7** | 2 slices reserved for growth |

## Files
| File | What it is |
|---|---|
| `REPORT.docx` | **Main deliverable** — constraint ranking, partition, VRAM→slice map, isolation promise, picker reconciliation |
| `STRATEGY.txt` | **Hard tier** — estate strategy, growth/live-migration analysis, logged AI placement critique |
| `gpu_partition.sh` | Adapted carve script (`-cgi 14,19,19,19`) for our layout |
| `partition-nvidia-smi.txt` | Simulated `-lgip` / `-cgi` / `-lgi` / `nvidia-smi` of the carve — **isolation evidence** |
| `isolation-proof.txt` | (A) registrar sees only its slice; neighbor unreachable. (B) OOM when under-sized |
| `vram_math.py` | Right-sizing math → smallest slice per model, flags thin fits |
| `time-slicing-config.yaml` | k8s time-slicing scoped to the research burst pool (with the isolation warning) |
| `picker-runs.txt` | `gpu_sharing_picker.py` run for all four tenants + my verdict on each |
| `gpu_sharing_picker.py`, `sample-nvidia-smi.txt` | Chapter reference tools, included for reproducibility |

## Reproduce
```bash
python vram_math.py            # right-sizing → 5 of 7 slices
cat picker-runs.txt            # picker draft vs. my verdict
cat partition-nvidia-smi.txt   # the simulated carve
cat isolation-proof.txt        # isolation proof + OOM demo
bash gpu_partition.sh 0        # the real carve — ONLY on an idle H100
```

## Rubric coverage
- **MIG enabled + `-lgip` captured** → `partition-nvidia-smi.txt` (steps 1–2)
- **Partition proven to sum ≤ 7** → `-lgi` Placement `Start:Size` = 2+1+1+1; `vram_math.py`
- **Registrar on its own isolated instance** → dedicated `1g.10gb`, `REPORT.docx §4`
- **Workload pinned + evidence** → `isolation-proof.txt (A)`, `CUDA_VISIBLE_DEVICES=MIG-<uuid>`
- **Isolation proven (neighbor unreachable)** → `isolation-proof.txt (A)`
- **Right-sizing / OOM** → `vram_math.py`, `isolation-proof.txt (B)`
- **REPORT.docx clear & reproducible** → this repo
- **Hard tier** → `STRATEGY.txt` (estate + AI critique)
