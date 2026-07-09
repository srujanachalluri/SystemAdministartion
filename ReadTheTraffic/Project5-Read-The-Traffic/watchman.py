#!/usr/bin/env python3
"""
watchman.py -- a per-host behavioral baseline detector for NetFlow logs.

WHAT THIS DOES
  1. Ingests baseline_flows.csv (30 days of "normal", distilled) and builds an
     EXPLAINABLE per-host profile: mean + p95 bytes_out, the set of destinations
     the host is known to talk to, and the set of ports it is known to use.
  2. Scores window_flows.csv (one suspicious live hour) against each host's OWN
     baseline -- never a single global threshold.
  3. Emits findings for three anomaly classes, and for EVERY flag prints a
     one-sentence "why" tied to a specific baseline deviation, so a human can
     confirm the call.
  4. Runs a false-positive sweep: it explains why the baseline's legitimate
     periodic public traffic (git pull, package mirror) would NOT trip the
     beaconing rule -- because those destinations are in the host's baseline.
     We suppress false positives by reasoning about BEHAVIOR, not by
     special-casing IP addresses.

ANOMALY CLASSES
  beaconing : same (src -> dst:port) at a near-fixed interval, low byte jitter,
              to a destination the host has NEVER used in its baseline.
  port_scan : one src fans out to many hosts on admin ports (22/3389/445/...)
              that it never touched in its baseline, in a short burst.
  exfil     : a single flow whose bytes_out dwarfs THIS host's own p95 baseline.

This is deliberately small and readable. It is the math under the hood of an
NDR product, not a replacement for one. A human owns every verdict.

USAGE
  python3 watchman.py baseline_flows.csv window_flows.csv
"""

import csv
import sys
import statistics
from collections import defaultdict
from datetime import datetime

# Admin / remote-management ports. A workstation fanning out to these across
# many hosts is the classic port-scan / lateral-movement signature.
ADMIN_PORTS = {22, 3389, 445, 5985, 5986, 23}

# Guardrails so we stay explainable and not noisy.
EXFIL_MULTIPLIER = 10          # bytes_out must exceed 10x the host's own p95
EXFIL_FLOOR = 1_000_000        # ...and clear an absolute 1 MB floor
SCAN_MIN_HOSTS = 4             # >= 4 distinct targets on admin ports = fan-out
BEACON_MIN_HITS = 4            # >= 4 repeats to call something periodic
BEACON_JITTER_BYTES = 50       # near-identical payload size (std dev, bytes)
BEACON_INTERVAL_JITTER = 0.15  # inter-arrival std dev <= 15% of mean = regular


def is_private(ip):
    """True for RFC-1918 / internal campus space. Used only to describe a
    destination in the report -- NOT to decide guilt. Behavior decides guilt."""
    return (ip.startswith("10.") or ip.startswith("192.168.")
            or ip.startswith("172.16.") or ip.startswith("172.31."))


def load(path):
    """Read a flow CSV, skipping comment lines and the distilled-stats footer."""
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            if not r.get("ts") or r["ts"].startswith("#") or not r.get("src_ip"):
                continue
            r["bytes_out"] = int(r["bytes_out"])
            r["bytes_in"] = int(r["bytes_in"])
            r["dst_port"] = int(r["dst_port"])
            r["epoch"] = datetime.fromisoformat(
                r["ts"].replace("Z", "+00:00")).timestamp()
            rows.append(r)
    return rows


def p95(values):
    """p95 of bytes_out. quantiles() needs >= 2 points; fall back to max."""
    if len(values) < 2:
        return max(values) if values else 0
    return statistics.quantiles(values, n=20)[-1]


def build_profile(baseline):
    """Per-host behavioral profile from the baseline window."""
    by_host = defaultdict(list)
    for r in baseline:
        by_host[r["src_ip"]].append(r)
    profile = {}
    for host, rows in by_host.items():
        outs = [r["bytes_out"] for r in rows]
        profile[host] = {
            "mean_out": statistics.mean(outs),
            "p95_out": p95(outs),
            "dsts": {r["dst_ip"] for r in rows},          # known-good destinations
            "ports": {r["dst_port"] for r in rows},        # known-good ports
            "n_flows": len(rows),
        }
    return profile


def human_bytes(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f}{unit}" if unit != "B" else f"{int(n)}B"
        n /= 1024


# --------------------------------------------------------------------------- #
# Detectors. Each returns a list of dicts with an explicit, printable "why".   #
# --------------------------------------------------------------------------- #

def detect_exfil(window, profile):
    findings = []
    for r in window:
        host = r["src_ip"]
        ref = profile.get(host, {}).get("p95_out", 10_000)
        if r["bytes_out"] > EXFIL_MULTIPLIER * ref and r["bytes_out"] > EXFIL_FLOOR:
            ratio = r["bytes_out"] / max(ref, 1)
            findings.append({
                "cls": "exfil",
                "host": host,
                "peer": f'{r["dst_ip"]}:{r["dst_port"]}',
                "why": (f'sent {human_bytes(r["bytes_out"])} outbound in one flow '
                        f'to {r["dst_ip"]} ({"external" if not is_private(r["dst_ip"]) else "internal"}) '
                        f'-- {ratio:,.0f}x this host\'s baseline p95 of '
                        f'{human_bytes(ref)}. No baseline flow from this host '
                        f'ever approached this volume.'),
            })
    return findings


def detect_port_scan(window, profile):
    findings = []
    targets = defaultdict(set)    # src -> set of dst on admin ports
    ports_hit = defaultdict(set)  # src -> set of admin ports used
    times = defaultdict(list)     # src -> timestamps of scan-ish flows
    for r in window:
        if r["dst_port"] in ADMIN_PORTS:
            targets[r["src_ip"]].add(r["dst_ip"])
            ports_hit[r["src_ip"]].add(r["dst_port"])
            times[r["src_ip"]].append(r["epoch"])
    for host, dsts in targets.items():
        if len(dsts) >= SCAN_MIN_HOSTS:
            span = max(times[host]) - min(times[host])
            baseline_ports = profile.get(host, {}).get("ports", set())
            new_ports = sorted(ports_hit[host] - baseline_ports)
            findings.append({
                "cls": "port_scan",
                "host": host,
                "peer": f"{len(dsts)} hosts",
                "why": (f'fanned out to {len(dsts)} distinct hosts on admin ports '
                        f'{sorted(ports_hit[host])} in {span:.0f}s. Baseline shows '
                        f'this host only ever used port(s) {sorted(baseline_ports)} '
                        f'to {len(profile.get(host, {}).get("dsts", []))} destination(s); '
                        f'ports {new_ports} are brand new for it.'),
            })
    return findings


def detect_beaconing(window, profile):
    findings = []
    groups = defaultdict(list)  # (src,dst,port) -> rows
    for r in window:
        groups[(r["src_ip"], r["dst_ip"], r["dst_port"])].append(r)
    for (src, dst, port), rows in groups.items():
        if len(rows) < BEACON_MIN_HITS:
            continue
        outs = [r["bytes_out"] for r in rows]
        stamps = sorted(r["epoch"] for r in rows)
        gaps = [b - a for a, b in zip(stamps, stamps[1:])]
        if not gaps:
            continue
        mean_gap = statistics.mean(gaps)
        gap_jitter = statistics.pstdev(gaps) / mean_gap if mean_gap else 1
        byte_jitter = statistics.pstdev(outs)
        regular = gap_jitter <= BEACON_INTERVAL_JITTER and byte_jitter < BEACON_JITTER_BYTES
        # BEHAVIORAL false-positive control: a periodic connection to a
        # destination the host ALREADY uses in its baseline (git, pkg mirror)
        # is a known-good job, not a beacon. Novelty of the destination is
        # what separates C2 from a cron job.
        known_dst = dst in profile.get(src, {}).get("dsts", set())
        if regular and not known_dst:
            findings.append({
                "cls": "beaconing",
                "host": src,
                "peer": f"{dst}:{port}",
                "why": (f'contacted {dst}:{port} '
                        f'({"external" if not is_private(dst) else "internal"}) '
                        f'{len(rows)} times every ~{mean_gap:.0f}s '
                        f'(interval jitter {gap_jitter*100:.0f}%, payload '
                        f'{human_bytes(statistics.mean(outs))} +/-{byte_jitter:.0f}B). '
                        f'This destination is NOT in the host\'s baseline -- the host '
                        f'normally only talks to {sorted(profile.get(src, {}).get("dsts", set()))}. '
                        f'Fixed-interval, fixed-size traffic to a novel public host '
                        f'is the signature of an automated beacon (C2 check-in).'),
            })
    return findings


def false_positive_sweep(baseline, profile):
    """Show our work: name the baseline's legitimate periodic public jobs and
    explain -- behaviorally -- why they must NOT be flagged as beacons."""
    notes = []
    for r in baseline:
        if not is_private(r["dst_ip"]):
            notes.append(
                f'  - {r["src_ip"]} -> {r["dst_ip"]}:{r["dst_port"]} '
                f'("{r["note"]}"): public + periodic, BUT this destination IS in '
                f'{r["src_ip"]}\'s baseline, so it is known-good business traffic. '
                f'Suppressed by behavior (known destination), not by IP allow-listing.')
    return notes


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    baseline = load(sys.argv[1])
    window = load(sys.argv[2])
    profile = build_profile(baseline)

    print("=" * 78)
    print("PER-HOST BASELINE PROFILE  (anchor to 'normal' before judging anything)")
    print("=" * 78)
    for host, p in sorted(profile.items()):
        print(f"  {host:<13} p95_out={human_bytes(p['p95_out']):<8} "
              f"mean_out={human_bytes(p['mean_out']):<8} "
              f"dsts={sorted(p['dsts'])} ports={sorted(p['ports'])}")

    findings = (detect_beaconing(window, profile)
                + detect_port_scan(window, profile)
                + detect_exfil(window, profile))

    print("\n" + "=" * 78)
    print(f"FINDINGS  ({len(findings)} candidate anomalies -- a human confirms each)")
    print("=" * 78)
    if not findings:
        print("  no anomalies -- but absence of a flag is not proof of safety. Verify.")
    for i, f in enumerate(findings, 1):
        print(f"\n  [{i}] {f['cls'].upper():<10} host={f['host']}  peer={f['peer']}")
        print(f"      WHY: {f['why']}")

    print("\n" + "=" * 78)
    print("FALSE-POSITIVE SWEEP  (why the baseline's periodic public jobs are safe)")
    print("=" * 78)
    for note in false_positive_sweep(baseline, profile):
        print(note)

    print("\n" + "-" * 78)
    print(f"{len(findings)} candidate(s) reported. Every block is a human decision. "
          "-- the watchman")


if __name__ == "__main__":
    main()
