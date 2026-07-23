#!/usr/bin/env python3
"""defender/detect.py — extends code/triage_logins.py with two new rules.

Baseline (code/triage_logins.py) has 5 rules. Run against code/auth.log,
it misses one real step in the attack chain documented in
attack/scenario.txt: the off-hours bulk export of the donors table
(2026-06-15T13:25:10Z), because that row's geo is "INT" (internal),
which the baseline's Rule 2 treats as trusted and skips.

Run:
    python3 defender/detect.py code/auth.log
"""
import sys
from collections import defaultdict
from datetime import datetime

HOME_GEO = "US-IL"
OFFHOURS = range(0, 6)

# New rule 6 target: sensitive tables/keywords a bulk read of which is
# never routine for this org, regardless of source geo.
SENSITIVE_KEYWORDS = ("donors", "donor", "bulk select")

# New rule 7 target: named social-engineering techniques that should be
# flagged explicitly, even if a coincidental geo match would hide them
# from Rule 2 (e.g. an attacker using a US-exit VPN).
NAMED_TECHNIQUE_KEYWORDS = ("impossible travel", "mfa fatigue", "password spray")


def parse(path):
    rows = []
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 7)
        if len(parts) < 7:
            continue
        ts, host, svc, user, srcip, geo, result = parts[:7]
        note = parts[7] if len(parts) > 7 else ""
        rows.append(dict(ts=ts, host=host, svc=svc, user=user,
                         srcip=srcip, geo=geo, result=result, note=note))
    return rows


def detect(rows):
    findings = []
    fails = defaultdict(int)
    for r in rows:
        when = datetime.fromisoformat(r["ts"].replace("Z", "+00:00"))
        note_l = r["note"].lower()

        # Rule 1 (baseline): failed auth bursts (spray / brute force)
        if r["result"] == "deny":
            fails[r["user"]] += 1
            if fails[r["user"]] >= 3:
                findings.append((r, "burst of denied auths (spray/brute force)"))

        # Rule 2 (baseline): success from outside home geography
        if r["result"] == "ok" and r["geo"] not in (HOME_GEO, "INT"):
            findings.append((r, f"successful login from non-home geo {r['geo']}"))

        # Rule 3 (baseline): off-hours privileged action
        if r["svc"] == "sudo" and when.hour in OFFHOURS:
            findings.append((r, "off-hours privilege escalation"))

        # Rule 4 (baseline): privilege escalation with no change ticket
        if r["svc"] == "sudo" and "NO change ticket" in r["note"]:
            findings.append((r, "sudo without a change ticket"))

        # Rule 5 (baseline): outbound to an external IP we just saw attacking us
        if "exfil" in note_l or "egress to 203.0.113" in note_l:
            findings.append((r, "possible data exfiltration to attacker IP"))

        # Rule 6 (NEW): bulk read of a sensitive table, regardless of geo.
        # This is the rule that catches what the baseline misses: the
        # 13:25:10Z bulk SELECT on db1 has geo=INT, so Rule 2 never fires
        # on it. Sensitive-table reads should never get a free pass just
        # because the source network is "internal" — an already-compromised
        # session is internal by definition.
        if any(k in note_l for k in SENSITIVE_KEYWORDS):
            findings.append((r, "bulk read of a sensitive table (donor data)"))

        # Rule 7 (NEW): name the social-engineering technique explicitly,
        # instead of relying on Rule 2's geo mismatch to catch it by luck.
        # If an attacker used a US-IL exit node, Rule 2 would miss this
        # entirely; naming the technique from the note field is a second,
        # independent signal.
        for kw in NAMED_TECHNIQUE_KEYWORDS:
            if kw in note_l:
                findings.append((r, f"named technique detected: {kw}"))
                break

    return findings


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "code/auth.log"
    hits = detect(parse(path))
    if not hits:
        print("No findings. (Did you point at the right file?)")
    for r, why in hits:
        print(f"[FLAG] {r['ts']} {r['user']}@{r['host']} <{r['srcip']}> -- {why}")
    print(f"\n{len(hits)} finding(s). Now: which are TRUE positives? You decide.")
