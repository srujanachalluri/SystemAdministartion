#!/usr/bin/env python3
"""vram_math.py — right-size each tenant's model to the smallest MIG slice that holds it.

Project 6 — "Carve the GPU", Medium tier. Real VRAM = weights + KV cache + overhead,
per the Chapter 4 math. The point the assignment hammers: an ~18 GB model does NOT fit a
10 GB slice, and it fits a 20 GB slice only with THIN headroom — so you size to REAL VRAM,
build a buffer, and flag any slice you're squeezing into. The tool reports; the human decides.

Run:  python vram_math.py
"""

# H100 80GB MIG profiles: (name, slices, usable GiB). Slice budget ceiling is 7.
SLICES = [
    ("1g.10gb", 1, 9.75),
    ("2g.20gb", 2, 19.50),
    ("3g.40gb", 3, 39.25),
    ("4g.40gb", 4, 39.25),
    ("7g.80gb", 7, 79.00),
]

def real_vram(weights_gb, kv_gb, overhead_frac):
    """weights + KV cache, then add CUDA-context/fragmentation overhead as a fraction."""
    return (weights_gb + kv_gb) * (1 + overhead_frac)

def smallest_slice(need_gb):
    for name, n, usable in SLICES:
        if usable >= need_gb:
            return name, n, usable
    return None

# name, weights_gb, kv_cache_gb, overhead, isolation/placement note.
# FP16 = 2 bytes/param.  CS is a coursework chat assistant => deliberately MODEST context,
# so its KV cache is small; that is the only reason 16 GB of weights fits a 2g.20gb at all.
TENANTS = [
    ("CS 8B chat",        16.0, 0.1, 0.15, "normal"),
    ("Library embedding",  1.3, 0.1, 0.40, "normal"),
    ("Registrar 1B",       2.0, 0.3, 0.40, "FERPA -> hardware-isolated slice REQUIRED"),
    ("Research notebook",  2.0, 0.3, 0.40, "no isolation -> time-slice onto a shared 1g.10gb"),
]

print(f"{'Tenant':<20}{'weights':>9}{'+KV':>7}{'x(1+ov)':>9}{'= real':>9}{'slice':>10}{'headroom':>11}")
print("-" * 90)
total_slices = 0
for name, w, kv, ov, note in TENANTS:
    need = real_vram(w, kv, ov)
    sname, n, usable = smallest_slice(need)
    headroom = usable - need
    pct = headroom / usable * 100
    flag = "  <-- THIN, flag it" if pct < 15 else ""
    total_slices += n
    extra = "  (its 1g.10gb is time-sliced as a shared burst pool)" if name.startswith("Research") else ""
    print(f"{name:<20}{w:>7.1f}GB{kv:>6.1f}{1+ov:>9.2f}{need:>7.1f}GB{sname:>10}"
          f"{headroom:>7.1f}GB {pct:>3.0f}%{flag}{extra}")
    print(f"{'':<20}-> {note}")

print("-" * 90)
print(f"Slice budget used: {total_slices} of 7  = CS 2g.20gb(2) + Registrar 1g(1) + Library 1g(1)"
      f" + Research 1g time-sliced(1)")
print("2 slices held in reserve for growth (second H100 arrives / a full-card training run).")
print()
print("JUDGMENT CALL flagged by the tool: CS fits 2g.20gb with only ~1 GB (~5%) headroom.")
print("  Accepted 2g.20gb (saves 1 slice vs 3g.40gb) ONLY with a context cap + monitoring.")
print("  Migration trigger: if CS context/concurrency grows, move to 3g.40gb -> covered by reserve.")
print()
print("Naive-error check: CS 8B 'looks like' it fits a 1g.10gb (10 GB). It does NOT —")
print(f"  real VRAM {real_vram(16,0.1,0.15):.1f} GB > 9.75 GB -> OOM at load (see isolation-proof.txt (B)).")
