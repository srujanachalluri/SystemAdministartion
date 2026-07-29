#!/usr/bin/env python3
"""rpo_rto.py - work out the estate's RPO and RTO from the asset register.

RPO, recovery point objective: the most DATA LOSS we accept, in minutes of work.
RTO, recovery time objective: the most DOWNTIME we accept before service is back.

Adapted from the chapter's reference script. I changed two things on purpose, and
both changes make the reported numbers worse rather than better, which is the point.

CHANGE 1 - use the critical path, not the class.
The reference formula adds up the RTO of every irreplaceable asset plus anything
marked rebuild-on-recovery. That misses the base model checkpoint. It is
reproducible and its strategy is cache-not-backup, so the reference formula scores
it as zero minutes - but the assistant cannot answer a single question until those
4.7 GB are back on disk. A register that hides the largest block of downtime in the
estate is a register that lies. So the register carries an explicit critical_path
flag, and this script adds up that instead. It prints BOTH numbers so the difference
is visible rather than quietly corrected.

CHANGE 2 - report the RPO in two tiers.
A single estate RPO of 1440 minutes reads like negligence. It is not. The two assets
with a 1440-minute RPO, the weights and the eval sets, only change during a planned
retrain. What congregants would actually notice losing is the content and the
behaviour. So this reports the worst-case asset RPO and the service-critical RPO
separately, and DR-PLAN.txt defends both.

Run:  python3 code/rpo_rto.py dr-asset-register.yaml
"""
import sys

import yaml


def load(path: str) -> dict:
    with open(path) as fh:
        return yaml.safe_load(fh)


def reference_rto(assets: list[dict]) -> int:
    """The chapter's formula, reproduced exactly, so the gap is auditable."""
    on_path = [a for a in assets
               if a["class"] == "irreplaceable" or a["strategy"] == "rebuild-on-recovery"]
    return sum(a["rto_minutes"] for a in on_path)


def critical_path_rto(assets: list[dict]) -> int:
    """Serial recovery across everything the service genuinely cannot start without."""
    return sum(a["rto_minutes"] for a in assets if a.get("critical_path"))


def worst_case_rpo(assets: list[dict]) -> int:
    """The largest data-loss window across the irreplaceable assets."""
    return max((a["rpo_minutes"] for a in assets if a["class"] == "irreplaceable"), default=0)


def service_rpo(assets: list[dict]) -> int:
    """Data loss a congregant would actually notice: content and behaviour."""
    felt = {"vector-db-source", "prompt-library", "app-configs"}
    return max((a["rpo_minutes"] for a in assets if a["name"] in felt), default=0)


def weakest_link(assets: list[dict]) -> dict:
    """The single biggest contributor to RTO on the critical path."""
    path = [a for a in assets if a.get("critical_path")]
    return max(path, key=lambda a: a["rto_minutes"])


def report(reg: dict) -> None:
    assets = reg["assets"]
    print(f"Estate: {reg['estate']}")
    print(f"Review cadence: {reg['review_cadence']}")
    print(f"Last restore test: {reg.get('last_restore_test', 'NEVER - and that is the finding')}")
    print()

    header = f"{'asset':<24}{'class':<16}{'lock':<12}{'crit':<6}{'RPO min':>9}{'RTO min':>9}"
    print(header)
    print("-" * len(header))
    for a in assets:
        print(f"{a['name']:<24}{a['class']:<16}{str(a.get('lock_mode', 'none')):<12}"
              f"{('yes' if a.get('critical_path') else 'no'):<6}"
              f"{a['rpo_minutes']:>9}{a['rto_minutes']:>9}")
    print("-" * len(header))
    print()

    print("RECOVERY POINT OBJECTIVE")
    print(f"  worst case, any asset   : {worst_case_rpo(assets):>5} min"
          "   (weights and eval sets, which only change on a planned retrain)")
    print(f"  service critical        : {service_rpo(assets):>5} min"
          "   (content and behaviour, what congregants would actually lose)")
    print()

    ref, crit = reference_rto(assets), critical_path_rto(assets)
    print("RECOVERY TIME OBJECTIVE, serial recovery")
    print(f"  chapter formula         : {ref:>5} min")
    print(f"  true critical path      : {crit:>5} min   <-- the number I will defend")
    if crit != ref:
        print()
        print(f"  The two differ by {crit - ref} minutes. The chapter formula scores")
        print("  reproducible cache-not-backup assets at zero, but the base model")
        print("  re-pull is real downtime that congregants would sit through.")
        print("  Reporting the smaller number would be dishonest.")
    print()

    w = weakest_link(assets)
    pct = w["rto_minutes"] * 100 // crit if crit else 0
    print("WEAKEST LINK ON THE CRITICAL PATH")
    print(f"  {w['name']} - {w['rto_minutes']} min, {pct}% of the total RTO")
    print()

    irr = [a["name"] for a in assets if a["class"] == "irreplaceable"]
    rep = [a["name"] for a in assets if a["class"] == "reproducible"]
    print("CLASSIFICATION SUMMARY")
    print(f"  irreplaceable, back these up          : {', '.join(irr)}")
    print(f"  reproducible, rebuild not store       : {', '.join(rep)}")
    worm = [a["name"] for a in assets if a.get("lock_mode") == "COMPLIANCE"]
    gov = [a["name"] for a in assets if a.get("lock_mode") == "GOVERNANCE"]
    print(f"  COMPLIANCE lock, no delete at all     : {', '.join(worm)}")
    print(f"  GOVERNANCE lock, deliberate hatch     : {', '.join(gov)}")


if __name__ == "__main__":
    report(load(sys.argv[1] if len(sys.argv) > 1 else "dr-asset-register.yaml"))
