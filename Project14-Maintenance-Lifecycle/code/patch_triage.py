#!/usr/bin/env python3
"""patch_triage.py — score a vulnerability feed so humans triage the right CVEs first.

This is a DECISION-SUPPORT tool, not a decision-maker. It sorts; you patch.
AI can draft the rationale column; a human signs off on the schedule.

Usage:
    python3 patch_triage.py cve_feed.json

Input: a JSON list of advisories, each with cvss, kev (CISA known-exploited),
internet_facing, and has_fix. Output: a triage table, highest priority first.
"""
import json
import sys


def priority(adv: dict) -> int:
    """Lower number = patch sooner. Deterministic, auditable, no model in the loop."""
    score = 100
    score -= int(adv.get("cvss", 0) * 5)            # CVSS 9.8 -> -49
    if adv.get("kev"):                               # actively exploited in the wild
        score -= 40
    if adv.get("internet_facing"):
        score -= 20
    if not adv.get("has_fix"):
        score += 30                                  # no fix yet -> mitigate, don't rush
    return score


def tier(p: int) -> str:
    if p <= 10:
        return "EMERGENCY (patch in 24h)"
    if p <= 40:
        return "HIGH (patch this week)"
    if p <= 70:
        return "MEDIUM (next maintenance window)"
    return "LOW (track; defer)"


def main(path: str) -> None:
    with open(path) as fh:
        feed = json.load(fh)
    rows = sorted(feed, key=priority)
    print(f"{'CVE':<18} {'CVSS':>4} {'KEV':>4}  TIER")
    print("-" * 60)
    for adv in rows:
        p = priority(adv)
        kev = "yes" if adv.get("kev") else "no"
        print(f"{adv['id']:<18} {adv.get('cvss', 0):>4} {kev:>4}  {tier(p)}")
    print("\nReminder: this ranks. A human owns the maintenance schedule and the risk acceptance.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python3 patch_triage.py cve_feed.json", file=sys.stderr)
        sys.exit(2)
    main(sys.argv[1])
