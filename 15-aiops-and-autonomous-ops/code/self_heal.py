#!/usr/bin/env python3
"""Reps 10-11: the gated self-healing loop.

  event -> diagnose -> remediate -> verify

Every proposed command is handed to approval_gate.sh (the real hook, same file
from Rep 3) before it is allowed to "run". Nothing destructive is ever executed
for real: remediation effects are simulated against sim_state.json, which is the
stand-in for node_filesystem_avail_bytes. Stay in the sandbox.

  python code/self_heal.py              # gated   -> reproduces node-7 (safe)
  python code/self_heal.py --ungated    # mis-tiered -> reproduces node-4 (expensive)
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).parent
RUNBOOK = HERE / "runbook_disk_pressure.yaml"
GATE = HERE / "approval_gate.sh"
STATE = HERE / "sim_state.json"

# What each remediation does to free space, and what it costs. Simulated.
EFFECTS = {
    "rotate-logs":    {"frees_pct": 29, "cost_per_mo": 0},
    "clear-apt-cache": {"frees_pct": 2, "cost_per_mo": 0},
    "scale-volume":   {"frees_pct": 60, "cost_per_mo": 1840},
}


def read_signal() -> int:
    """VERIFY reads the underlying signal, not a command exit code."""
    return json.loads(STATE.read_text())["avail_pct"]


def write_signal(pct: int) -> None:
    STATE.write_text(json.dumps({"avail_pct": pct}))


def audit(line: str) -> None:
    """Rep 11 writes here directly, because the hook is what we removed."""
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(HERE.parent / "audit.log", "a") as fh:
        fh.write(f"{ts} {line}\n")


def ask_gate(cmd: str, approved: bool) -> int:
    """Feed the proposed command to the PreToolUse hook. 0 = allow, 2 = block."""
    payload = json.dumps({"tool_input": {"command": cmd}})
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin", "AUDIT_LOG": str(HERE.parent / "audit.log")}
    if approved:
        env["HUMAN_APPROVAL_TOKEN"] = "I-APPROVE"
    proc = subprocess.run(["bash", str(GATE)], input=payload, text=True,
                          capture_output=True, env=env)
    if proc.stderr.strip():
        print(f"    gate says: {proc.stderr.strip()}")
    return proc.returncode


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ungated", action="store_true",
                    help="Rep 11: mis-tier scale-volume to 'act' and skip the human")
    args = ap.parse_args()

    rb = yaml.safe_load(RUNBOOK.read_text())
    write_signal(9)  # the incident starts here: 9%% free on /var
    spend = 0

    # ---------------- EVENT ----------------
    print(f"\n[EVENT]   signal={rb['detect']['signal']} mount={rb['detect']['mountpoint']} "
          f"avail_pct={read_signal()} threshold={rb['detect']['threshold_pct']} "
          f"for={rb['detect']['for']}")
    print(f"[MATCH]   runbook={rb['incident']} version={rb['version']} mode="
          f"{'UNGATED (mis-tiered)' if args.ungated else 'GATED'}")

    # ---------------- DIAGNOSE (read-only, tier act) ----------------
    for step in rb["diagnose"]:
        print(f"\n[DIAGNOSE] {step['id']}  autonomy={step['autonomy']}")
        print(f"    cmd: {step['cmd']}")
        rc = ask_gate(step["cmd"], approved=False)
        print(f"    gate exit={rc} -> {'ALLOWED' if rc == 0 else 'BLOCKED'}")
        print("    FINDING /var/log/journal=41G /var/lib/docker=18G /var/cache/apt=6G")

    # ---------------- REMEDIATE ----------------
    steps = rb["remediate"]
    if args.ungated:
        # With no human in the loop, the agent optimises for "clear the alert
        # fastest" and reaches for the biggest lever first. Nobody is there to
        # ask what it costs. This is how node-4 happened.
        steps = sorted(steps, key=lambda s: -EFFECTS[s["id"]]["frees_pct"])

    for step in steps:
        tier = "act" if args.ungated else step["autonomy"]
        cmd = step["cmd"]
        if args.ungated and step["id"] == "scale-volume":
            cmd = "resize-pvc data-var --to 2000Gi"  # the node-4 mistake

        print(f"\n[REMEDIATE] {step['id']}  autonomy={tier}  "
              f"blast_radius={step.get('blast_radius', 'n/a')}  "
              f"reversible={step.get('reversible', 'n/a')}")
        print(f"    proposed: {cmd}")

        approved = False
        if args.ungated:
            # The hook is gone. Nothing consults a human; nothing can say no.
            rc = 0
            audit(f"ACT(ungated,no-approval-on-record) :: {cmd}")
            print("    NO GATE - hook removed, no human consulted")
        elif tier == "approve":
            rc = ask_gate(cmd, approved=False)
            if rc != 0:
                print("    [GATE] paused - waiting for human approval")
                reply = input("    Approve this action? [y/N] ").strip().lower()
                if reply != "y":
                    print("    DENIED by human - skipping step")
                    continue
                approved = True
                rc = ask_gate(cmd, approved=True)
        else:
            rc = ask_gate(cmd, approved=False)
            if rc == 0 and step["autonomy"] == "approve":
                # Policy says approve, the hook says allow. That mismatch is the
                # node-4 failure mode. Refuse rather than trust the looser one.
                print("    [MISMATCH] runbook tier=approve but gate allowed it - "
                      "the gate pattern is too narrow. Refusing.")
                continue

        if rc != 0:
            print(f"    gate exit={rc} -> BLOCKED, step not executed")
            continue

        effect = EFFECTS[step["id"]]
        write_signal(min(100, read_signal() + effect["frees_pct"]))
        spend += effect["cost_per_mo"]
        print(f"    gate exit=0 -> ACT (simulated) approved_by_human={approved}")
        print(f"    effect: avail_pct now {read_signal()}  monthly_cost=+${effect['cost_per_mo']}")

        # ---------------- VERIFY ----------------
        want = rb["verify"]["expect_pct_above"]
        have = read_signal()
        print(f"[VERIFY]  {rb['verify']['signal']}={have} expect_above={want} -> "
              f"{'PASS' if have > want else 'FAIL -> ' + rb['verify']['rollback_if_unmet']}")
        if have > want:
            print(f"[RESOLVE] incident closed  human_in_loop={approved}  "
                  f"unplanned_spend=${spend}/mo")
            return

    print(f"\n[END] loop finished  avail_pct={read_signal()}  unplanned_spend=${spend}/mo")


if __name__ == "__main__":
    sys.exit(main())
