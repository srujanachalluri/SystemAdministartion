#!/usr/bin/env python3
"""psi.py — Population Stability Index, the workhorse drift metric.

PSI compares a *reference* distribution (what production looked like when the
model was last validated) to a *current* window. It answers one question:
"has the input distribution moved?"  Rules of thumb (industry convention):

    PSI < 0.10   -> no significant shift
    0.10 - 0.20  -> moderate shift, investigate
    PSI > 0.20   -> significant shift, the model may be operating off-distribution

WARNING the chapter hammers: PSI detects DATA/FEATURE drift only. It is blind to
CONCEPT drift -- a change in the input->output relationship -- because that needs
labels/outcomes, which arrive late. Watching only PSI is watching one door of two.

Usage:
    python psi.py reference.txt current.txt
where each file is one numeric value per line (e.g. daily request latencies,
or a feature like prompt length). No third-party deps.
"""
import math
import sys


def psi(reference, current, buckets=10):
    """Compute PSI between two lists of floats using quantile bins."""
    ref = sorted(reference)
    # quantile cut points from the reference distribution
    cuts = [ref[int(len(ref) * q / buckets)] for q in range(1, buckets)]
    edges = [-math.inf] + cuts + [math.inf]

    def fractions(data):
        counts = [0] * buckets
        for x in data:
            for i in range(buckets):
                if edges[i] < x <= edges[i + 1]:
                    counts[i] += 1
                    break
        # floor each fraction so we never take log(0)
        return [max(c / len(data), 1e-6) for c in counts]

    r, c = fractions(reference), fractions(current)
    return sum((c[i] - r[i]) * math.log(c[i] / r[i]) for i in range(buckets))


def verdict(value):
    if value < 0.10:
        return "OK        (no significant shift)"
    if value < 0.20:
        return "WATCH     (moderate shift)"
    return "ALERT     (significant shift)"


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: python psi.py reference.txt current.txt")
    ref = [float(line) for line in open(sys.argv[1]) if line.strip()]
    cur = [float(line) for line in open(sys.argv[2]) if line.strip()]
    value = psi(ref, cur)
    print(f"PSI = {value:.4f}  ->  {verdict(value)}")
