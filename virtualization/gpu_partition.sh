#!/usr/bin/env bash
# gpu_partition.sh — carve Concordia Lakes' single NVIDIA H100 80GB into MIG instances.
# Project 6 — "Carve the GPU". Adapted from the Ch.6 reference script for OUR four-tenant layout.
#
# OUR PARTITION (5 of 7 slices used, 2 held in reserve for growth):
#   2g.20gb  (profile 14)  -> CS 8B chat assistant   (~18 GB real VRAM; will NOT fit a 1g.10gb)
#   1g.10gb  (profile 19)  -> Registrar 1B classifier (FERPA — its OWN hardware-isolated slice)
#   1g.10gb  (profile 19)  -> Library embedding model (~3 GB)
#   1g.10gb  (profile 19)  -> Research student notebook (later time-sliced for burst)
#   Slice math: 2 + 1 + 1 + 1 = 5  (<= 7 ceiling)
#
# SAFETY: enabling/disabling MIG RESETS the GPU. Never run on a card with live work. Drain first.
# Requires: nvidia-smi, root, a MIG-capable GPU (A100/H100/H200/B200). We have no data-center GPU,
# so this script is documented and validated against the simulated -lgip/-lgi layout in
# partition-nvidia-smi.txt. See REPORT.docx for the "simulated substrate" disclosure.
set -euo pipefail

GPU="${1:-0}"   # GPU index to partition (default 0)

echo "==> GPU $GPU before partitioning:"
nvidia-smi -i "$GPU" --query-gpu=name,memory.total,mig.mode.current --format=csv

# 1) Enable MIG mode (idempotent; no-op if already enabled). Resets the GPU.
echo "==> Enabling MIG mode on GPU $GPU (this resets the device)..."
sudo nvidia-smi -i "$GPU" -mig 1

# 2) Confirm the card's profile IDs. On H100 80GB: 14 = 2g.20gb, 19 = 1g.10gb, 9 = 3g.40gb.
echo "==> Available GPU Instance profiles (verify IDs against YOUR card):"
sudo nvidia-smi mig -i "$GPU" -lgip

# 3) Create our mixed partition: one 2g.20gb + three 1g.10gb = 5 slices.
#    -C also creates the matching Compute Instance inside each GPU Instance.
echo "==> Creating GPU Instances (one 2g.20gb + three 1g.10gb = 5 slices)..."
sudo nvidia-smi mig -i "$GPU" -cgi 14,19,19,19 -C

# 4) Show the resulting instances. Each is an isolated, addressable MIG device.
echo "==> Partition result:"
sudo nvidia-smi mig -i "$GPU" -lgi
nvidia-smi -L | grep -i mig || true

cat <<'NOTE'

Done. Each MIG instance now appears as its own MIG-<UUID>.
Pin the FERPA registrar workload to ITS OWN slice (hardware isolation — the whole point):
  CUDA_VISIBLE_DEVICES=MIG-<registrar-UUID>  python serve_registrar_classifier.py

To tear it all down (free the slices, then disable MIG):
  sudo nvidia-smi mig -i 0 -dci && sudo nvidia-smi mig -i 0 -dgi && sudo nvidia-smi -i 0 -mig 0

Remember: the MIG ceiling is 7 instances even on a 180GB B200 — memory grows, slice count does not.
NOTE
