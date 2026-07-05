#!/usr/bin/env python3
"""estate_sizer.py — napkin math for an AI storage estate.

Sizes the three things that actually fill your disks in 2026:
  1. model weights        (params x bytes-per-weight)
  2. KV cache headroom    (rough, runtime VRAM not disk)
  3. a vector database    (num_vectors x dims x bytes + HNSW graph overhead)

Numbers are sizing estimates, NOT promises. Real deployed VRAM runs
~15-40% above weights-only once KV cache + framework overhead land.
See AI_FACT_BRIEF Ch.4 and chapter.md sections 4.4-4.6. Re-verify at deploy.

Usage:
    python3 estate_sizer.py
"""

GB = 1024 ** 3

# bytes-per-weight by precision (the lever that moves the bill)
BYTES_PER_WEIGHT = {"fp16": 2.0, "int8": 1.0, "int4": 0.5}

# bytes-per-component for a stored vector
VEC_BYTES = {"float32": 4, "halfvec": 2, "int8": 1, "binary": 0.125}


def weight_gb(params_billion: float, precision: str) -> float:
    """Weights-only disk footprint, in GB."""
    bpw = BYTES_PER_WEIGHT[precision]
    return (params_billion * 1e9 * bpw) / GB


def deployed_vram_gb(params_billion: float, precision: str, overhead: float = 0.25) -> float:
    """Rough live VRAM: weights + KV/activation/framework headroom."""
    return weight_gb(params_billion, precision) * (1 + overhead)


def vector_gb(num_vectors: int, dims: int, fmt: str, hnsw_m: int = 32) -> float:
    """Raw vectors + HNSW graph overhead (~8 x M bytes/vector)."""
    raw = num_vectors * dims * VEC_BYTES[fmt]
    graph = num_vectors * 8 * hnsw_m  # OpenSearch-style estimate
    return (raw + graph) / GB


if __name__ == "__main__":
    print("== Model weights (disk, weights-only) ==")
    for p in (7, 13, 70, 405):
        row = "  {:>4}B".format(p)
        for q in ("fp16", "int8", "int4"):
            row += "  {}={:7.1f} GB".format(q, weight_gb(p, q))
        print(row)

    print("\n== A 70B at INT4, deployed VRAM with 25% headroom ==")
    print("  {:.1f} GB  (one 48 GB card is the practical floor)".format(
        deployed_vram_gb(70, "int4")))

    print("\n== Vector DB: 10M vectors x 1536 dims ==")
    for fmt in ("float32", "halfvec", "int8", "binary"):
        print("  {:>8}: {:8.2f} GB".format(fmt, vector_gb(10_000_000, 1536, fmt)))
    print("\n  Lesson: raw vectors dominate. Quantize before you buy disk.")
