#!/usr/bin/env python3
"""estate_cost.py - AI estate sizing and cost model for Cornerstone Relief International.

ADAPTED AND EXTENDED from the chapter reference model
(16-ai-native-capstone/code/estate_cost.py).

What was added for CRI, and why:
  1. VRAM SIZING WITH A KV-CACHE TERM. The reference model priced tokens but never
     asked whether the box can hold the workload. KV cache is the term people
     forget, and at CRI's context lengths it is LARGER than the weights.
  2. A REAL CROSSOVER CALCULATION. Not "self-host wins at high volume" - the exact
     monthly token volume where the fixed self-host bill equals the variable API
     bill, per model tier.
  3. THREE WORKLOAD SCENARIOS: today, CRI doubles its field offices, CRI adds a
     public-facing chatbot. The decision has to survive growth.
  4. A SENSITIVITY TABLE over utilisation, because a reserved GPU node billed at
     100% and used at 20% is the most common way a small org wastes donor money.

Run:  python3 code/estate_cost.py

All prices are MID-2026 SNAPSHOTS. They drift weekly. Pin model IDs and re-check
the vendor console before quoting a real bill.
Owner of this model: Ruth Mensah (Finance Controller). Reviewed with Daniel Okoro.
"""

# =============================================================================
# SECTION 1 - INPUTS (change these per design)
# =============================================================================

# --- Workload W1: case-note RAG, self-hosted (RESTRICTED data) ---------------
W1_MONTHLY_INPUT_TOKENS = 120_000_000     # RAG stuffs context -> input-heavy
W1_MONTHLY_OUTPUT_TOKENS = 12_000_000

# --- Workload W2: staff productivity assistant, API (INTERNAL data) ----------
W2_MONTHLY_INPUT_TOKENS = 60_000_000
W2_MONTHLY_OUTPUT_TOKENS = 20_000_000

# --- Workload W3: AIOps agent, API (no beneficiary data) ---------------------
W3_MONTHLY_INPUT_TOKENS = 45_000_000      # agents re-send context every step
W3_MONTHLY_OUTPUT_TOKENS = 5_000_000

# --- Per-1M-token API price snapshots, mid-2026 (USD) ------------------------
# Pin the exact model ID in production. "latest" is banned at CRI.
API_PRICES = {
    "small-fast-tier":  {"in": 1.00, "out": 5.00},
    "mid-tier":         {"in": 3.00, "out": 15.00},
    "large-tier":       {"in": 5.00, "out": 30.00},
    "budget-tier":      {"in": 0.50, "out": 3.00},
}

# --- Self-host node: what CRI would actually buy ------------------------------
# One 2xH100-80GB node, reserved 3yr, all-in (hardware amortised + power +
# colo/cloud reservation + the share of Daniel Okoro's time it consumes).
SELFHOST_NODE_USD_PER_MONTH = 6_400
SELFHOST_TOKENS_PER_MONTH_CAPACITY = 900_000_000   # sustained, at ~70% duty cycle

# --- Model shape for VRAM sizing (a ~70B-class open-weight instruct model) ----
MODEL_PARAMS_B = 70            # billions of parameters
BYTES_PER_PARAM = 1.0          # FP8/INT8 quantised. FP16 would be 2.0
N_LAYERS = 80
N_KV_HEADS = 8                 # grouped-query attention - this is why KV fits
HEAD_DIM = 128
KV_BYTES = 2                   # FP16 KV cache

CONTEXT_LEN = 8_192            # tokens of context per request (RAG is long)
CONCURRENCY = 24               # simultaneous in-flight requests at peak
CUDA_OVERHEAD_FRACTION = 0.12  # activations, fragmentation, runtime overhead

GPU_VRAM_GB = 80.0             # per H100-80GB card

# --- Storage --------------------------------------------------------------
CASE_NOTE_CORPUS_GB = 340        # three years of case notes + attachments
EMBED_DIM = 1024
CHUNKS = 2_400_000               # ~2.4M chunks across the corpus
VECTOR_BYTES_PER_DIM = 4         # float32 index (HNSW); halve if quantised


# =============================================================================
# SECTION 2 - VRAM SIZING  (the KV-cache term the reference model omitted)
# =============================================================================

def weights_gb() -> float:
    """VRAM held by the model weights themselves. Fixed, does not scale with load."""
    return MODEL_PARAMS_B * 1e9 * BYTES_PER_PARAM / 1e9


def kv_cache_gb_per_request() -> float:
    """KV cache for ONE request at full context.

    Per token, per layer, we store a key and a value vector:
        2 (K and V) * n_kv_heads * head_dim * bytes_per_element
    Then multiply by layers and by sequence length.
    """
    per_token_per_layer = 2 * N_KV_HEADS * HEAD_DIM * KV_BYTES
    per_request = per_token_per_layer * N_LAYERS * CONTEXT_LEN
    return per_request / 1e9


def kv_cache_gb_total() -> float:
    """KV cache across all concurrent requests. THIS is what scales with load."""
    return kv_cache_gb_per_request() * CONCURRENCY


def total_vram_gb() -> float:
    base = weights_gb() + kv_cache_gb_total()
    return base * (1 + CUDA_OVERHEAD_FRACTION)


def gpus_required() -> int:
    import math
    return math.ceil(total_vram_gb() / GPU_VRAM_GB)


def max_concurrency_on_gpus(n_gpus: int) -> int:
    """How many simultaneous requests fit once the weights are loaded."""
    usable = n_gpus * GPU_VRAM_GB / (1 + CUDA_OVERHEAD_FRACTION)
    room_for_kv = usable - weights_gb()
    if room_for_kv <= 0:
        return 0
    return int(room_for_kv / kv_cache_gb_per_request())


def vector_index_gb() -> float:
    raw = CHUNKS * EMBED_DIM * VECTOR_BYTES_PER_DIM / 1e9
    return raw * 1.5    # HNSW graph overhead, ~1.5x the raw vectors


# =============================================================================
# SECTION 3 - COST MODEL
# =============================================================================

def api_monthly_cost(model: str, in_tokens: float, out_tokens: float) -> float:
    p = API_PRICES[model]
    return (in_tokens / 1e6) * p["in"] + (out_tokens / 1e6) * p["out"]


def blended_price_per_million(model: str, in_tokens: float, out_tokens: float) -> float:
    total = in_tokens + out_tokens
    if total == 0:
        return 0.0
    return api_monthly_cost(model, in_tokens, out_tokens) / (total / 1e6)


def selfhost_effective_price_per_million(total_tokens: float) -> float:
    if total_tokens == 0:
        return float("inf")
    return SELFHOST_NODE_USD_PER_MONTH / (total_tokens / 1e6)


def crossover_tokens(model: str, in_ratio: float, out_ratio: float) -> float:
    """Monthly token volume at which the fixed self-host bill equals the API bill.

    Below this, pay-per-token is cheaper. Above it, the owned node is cheaper.
    in_ratio/out_ratio describe the shape of the workload and must sum to 1.
    """
    p = API_PRICES[model]
    blended_per_token = (in_ratio * p["in"] + out_ratio * p["out"]) / 1e6
    if blended_per_token == 0:
        return float("inf")
    return SELFHOST_NODE_USD_PER_MONTH / blended_per_token


# =============================================================================
# SECTION 4 - SCENARIOS
# =============================================================================
# (name, multiplier on W1, multiplier on W2, multiplier on W3, note)
SCENARIOS = [
    ("S0 baseline (today)",            1.0, 1.0, 1.0,
     "9-person IT team, 600 staff, 4 continents"),
    ("S1 field offices double",        2.1, 1.8, 1.6,
     "8 continents-worth of offices; more case notes, more staff, more alerts"),
    ("S2 public beneficiary chatbot",  1.2, 6.5, 1.2,
     "public-facing intake assistant; W2 volume dominates and becomes bursty"),
]


def scenario_tokens(m1, m2, m3):
    w1_in = W1_MONTHLY_INPUT_TOKENS * m1
    w1_out = W1_MONTHLY_OUTPUT_TOKENS * m1
    w2_in = W2_MONTHLY_INPUT_TOKENS * m2
    w2_out = W2_MONTHLY_OUTPUT_TOKENS * m2
    w3_in = W3_MONTHLY_INPUT_TOKENS * m3
    w3_out = W3_MONTHLY_OUTPUT_TOKENS * m3
    return (w1_in, w1_out), (w2_in, w2_out), (w3_in, w3_out)


# =============================================================================
# SECTION 5 - REPORT
# =============================================================================

def rule(char="=", n=78):
    print(char * n)


def main():
    rule()
    print("CRI AI ESTATE - SIZING AND COST MODEL   (mid-2026 price snapshot)")
    print("Owner: Ruth Mensah, Finance Controller | Platform: Daniel Okoro")
    rule()

    # ---- 5.1 VRAM ----------------------------------------------------------
    print("\n[1] VRAM SIZING - self-hosted case-note lane (W1)")
    print(f"    model shape       : ~{MODEL_PARAMS_B}B params, "
          f"{BYTES_PER_PARAM:.0f} byte/param (FP8/INT8), {N_LAYERS} layers, "
          f"{N_KV_HEADS} KV heads (GQA)")
    print(f"    context / concurrency : {CONTEXT_LEN:,} tokens x {CONCURRENCY} in flight")
    print()
    print(f"    weights                       {weights_gb():>8.1f} GB")
    print(f"    KV cache per request          {kv_cache_gb_per_request():>8.2f} GB")
    print(f"    KV cache x{CONCURRENCY:<3d} concurrent    {kv_cache_gb_total():>8.1f} GB   "
          f"<-- scales with LOAD, not model size")
    print(f"    runtime overhead ({CUDA_OVERHEAD_FRACTION:.0%})         "
          f"{(weights_gb()+kv_cache_gb_total())*CUDA_OVERHEAD_FRACTION:>8.1f} GB")
    print(f"    {'-'*44}")
    print(f"    TOTAL VRAM REQUIRED           {total_vram_gb():>8.1f} GB")
    print(f"    GPUs needed @ {GPU_VRAM_GB:.0f} GB          {gpus_required():>8d}")
    kv_share = kv_cache_gb_total() / (weights_gb() + kv_cache_gb_total())
    print(f"    KV cache is {kv_share:.0%} of live VRAM. Size the CACHE, not just the model.")
    print(f"    Headroom check: 2 GPUs hold ~{max_concurrency_on_gpus(2)} concurrent "
          f"requests at {CONTEXT_LEN:,} ctx.")

    print("\n[2] STORAGE")
    print(f"    {'case-note corpus (source)':<36}{CASE_NOTE_CORPUS_GB:>6.0f} GB")
    print(f"    {f'vector index ({CHUNKS/1e6:.1f}M chunks x {EMBED_DIM}d)':<36}"
          f"{vector_index_gb():>6.0f} GB")
    print(f"    {'immutable backup copy (3-2-1-1-0)':<36}"
          f"{CASE_NOTE_CORPUS_GB*1.3:>6.0f} GB")
    print("    NOTE: the index is REBUILDABLE. We back up sources + embed config,")
    print("          not the index. Cheaper, and it survives an embedding change.")

    # ---- 5.3 Scenario costs ------------------------------------------------
    print("\n[3] MONTHLY COST BY SCENARIO")
    for name, m1, m2, m3, note in SCENARIOS:
        (w1i, w1o), (w2i, w2o), (w3i, w3o) = scenario_tokens(m1, m2, m3)
        w1_tot = w1i + w1o
        api_lane_cost = (api_monthly_cost("small-fast-tier", w2i, w2o)
                         + api_monthly_cost("mid-tier", w3i, w3o))
        # if W1 were served by API instead of self-hosted:
        w1_if_api = api_monthly_cost("mid-tier", w1i, w1o)
        util = w1_tot / SELFHOST_TOKENS_PER_MONTH_CAPACITY

        print(f"\n    {name}")
        print(f"      ({note})")
        print(f"      W1 case-note RAG   {w1_tot/1e6:>8.0f}M tok  "
              f"SELF-HOSTED  ${SELFHOST_NODE_USD_PER_MONTH:>8,.0f}/mo   "
              f"(node at {util:.0%} of capacity)")
        print(f"        effective ${selfhost_effective_price_per_million(w1_tot):.2f}/1M tok"
              f"   |  same volume on mid-tier API would be ${w1_if_api:,.0f}/mo")
        print(f"      W2 staff assistant {(w2i+w2o)/1e6:>8.0f}M tok  small-fast API "
              f"${api_monthly_cost('small-fast-tier', w2i, w2o):>8,.0f}/mo")
        print(f"      W3 AIOps agent     {(w3i+w3o)/1e6:>8.0f}M tok  mid-tier API   "
              f"${api_monthly_cost('mid-tier', w3i, w3o):>8,.0f}/mo")
        print(f"      {'-'*66}")
        print(f"      TOTAL AI ESTATE                            "
              f"${SELFHOST_NODE_USD_PER_MONTH + api_lane_cost:>9,.0f}/mo   "
              f"(${(SELFHOST_NODE_USD_PER_MONTH + api_lane_cost)*12:,.0f}/yr)")

    # ---- 5.4 Crossover -----------------------------------------------------
    print("\n[4] SELF-HOST vs API CROSSOVER")
    print(f"    Fixed self-host bill: ${SELFHOST_NODE_USD_PER_MONTH:,}/mo.")
    print("    Crossover = the monthly token volume where the API bill equals it.")
    print("    Below the crossover, PAY-PER-TOKEN IS CHEAPER.")
    print(f"\n    Workload shape used: RAG-like, 91% input / 9% output tokens\n")
    print(f"      {'API tier':<18} {'blended $/1M':>13} {'crossover (tok/mo)':>22}")
    print(f"      {'-'*18} {'-'*13} {'-'*22}")
    for model in API_PRICES:
        blended = blended_price_per_million(model, 0.91, 0.09)
        xo = crossover_tokens(model, 0.91, 0.09)
        print(f"      {model:<18} ${blended:>12.2f} {xo/1e6:>19,.0f}M")

    w1_today = W1_MONTHLY_INPUT_TOKENS + W1_MONTHLY_OUTPUT_TOKENS
    xo_mid = crossover_tokens("mid-tier", 0.91, 0.09)
    print(f"\n    CRI's W1 volume today: {w1_today/1e6:,.0f}M tokens/month.")
    print(f"    Crossover vs mid-tier API: {xo_mid/1e6:,.0f}M tokens/month.")
    if w1_today < xo_mid:
        gap = SELFHOST_NODE_USD_PER_MONTH - api_monthly_cost(
            "mid-tier", W1_MONTHLY_INPUT_TOKENS, W1_MONTHLY_OUTPUT_TOKENS)
        print(f"    => ON COST ALONE, THE API WINS TODAY by ${gap:,.0f}/month "
              f"(${gap*12:,.0f}/yr).")
        print("    => CRI SELF-HOSTS ANYWAY. That premium is the price of data")
        print("       residency and non-retention for special-category data about")
        print("       vulnerable people. See decision-memo.docx. This number is the")
        print("       cost of the duty, and the board should see it, not be spared it.")
    else:
        print("    => Self-host wins on cost as well as on residency.")

    # ---- 5.5 Sensitivity ---------------------------------------------------
    print("\n[5] SENSITIVITY - what utilisation does to the self-host unit price")
    print("    A reserved node bills the same whether you use it or not.")
    print(f"\n      {'utilisation':>12} {'tokens/mo':>14} {'$/1M tokens':>14} "
          f"{'vs mid-tier API':>18}")
    print(f"      {'-'*12} {'-'*14} {'-'*14} {'-'*18}")
    mid_blended = blended_price_per_million("mid-tier", 0.91, 0.09)
    for util in (0.10, 0.15, 0.25, 0.40, 0.60, 0.80, 1.00):
        toks = SELFHOST_TOKENS_PER_MONTH_CAPACITY * util
        unit = selfhost_effective_price_per_million(toks)
        verdict = "API cheaper" if unit > mid_blended else "SELF-HOST cheaper"
        print(f"      {util:>11.0%} {toks/1e6:>13,.0f}M ${unit:>13.2f} {verdict:>18}")
    print(f"\n    (mid-tier API blended reference: ${mid_blended:.2f}/1M tokens)")
    print("    READ THIS ROW-BY-ROW BEFORE BUYING A GPU. CRI's W1 today sits near")
    print(f"    {w1_today/SELFHOST_TOKENS_PER_MONTH_CAPACITY:.0%} utilisation. The node is "
          f"bought for the duty and for headroom,")
    print("    not because it is the cheap option at today's volume.")

    # ---- 5.6 Guardrails ----------------------------------------------------
    print("\n[6] CONSUMPTION GUARDRAILS (owner: Ruth Mensah)")
    print("    - Hard spend cap US$200/day on the API lane. Hard stop, not an alert.")
    print("    - Per-user and per-agent rate limits; loop detector halts runaway agents.")
    print("    - Self-host cost is FIXED, which is itself a budget control: the")
    print("      case-note lane cannot surprise the board with a bill.")
    print("    - Re-verify every price in this file quarterly. They are snapshots.")
    rule()
    print("Prices: mid-2026 snapshots. Model IDs pinned by digest in production.")
    print("EU AI Act high-risk timeline treated as DEFERRED, PENDING ADOPTION - verify.")
    rule()


if __name__ == "__main__":
    main()
