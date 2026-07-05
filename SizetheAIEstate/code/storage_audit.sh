#!/usr/bin/env bash
# storage_audit.sh — read the weight of your data before you reason about it.
# A read-only audit. Nothing here writes or deletes. Linux; needs coreutils.
# Referenced by chapter 4.1-4.3 and Rep 1. Run: bash storage_audit.sh /data/ai
set -euo pipefail

ROOT="${1:-/data/ai}"

echo "== Filesystems, capacity, and headroom =="
# -h human, -T type. Watch %used: past ~85% many filesystems slow down.
df -hT | grep -vE 'tmpfs|devtmpfs'

echo
echo "== Block devices, RAID, and rotational vs SSD =="
# ROTA=1 spinning disk, ROTA=0 SSD/NVMe. The tiering signal (4.3).
lsblk -o NAME,SIZE,TYPE,ROTA,FSTYPE,MOUNTPOINT

echo
echo "== Largest consumers under ${ROOT} (top 15) =="
# This is where model weights and vector DBs hide. du is I/O heavy on
# huge trees -- run it off-peak on production.
du -h --max-depth=2 "${ROOT}" 2>/dev/null | sort -rh | head -15

echo
echo "== Files not read in 180+ days (cold-tier candidates, top 20) =="
# atime-based. The AI-assisted classifier in 4.8 starts from exactly this
# signal -- but YOU decide what is 'a time to cast away' (Ecclesiastes 3:6).
find "${ROOT}" -type f -atime +180 -printf '%s\t%p\n' 2>/dev/null \
    | sort -rn | head -20 \
    | awk -F'\t' '{ printf "%8.1f MB  %s\n", $1/1048576, $2 }'

echo
echo "Audit complete. Numbers, not vibes. Now decide what to keep."
