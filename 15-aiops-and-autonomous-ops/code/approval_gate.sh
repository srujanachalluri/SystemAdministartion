#!/usr/bin/env bash
# approval_gate.sh — the human-in-the-loop gate, as a hook.
#
# Wire this as a PreToolUse hook for an agent (Claude Code / Agent SDK). It reads
# the proposed Bash command on stdin (JSON), and if the command matches a
# DESTRUCTIVE pattern, it BLOCKS and demands an explicit human approval token in
# the environment before the action may proceed. Every decision is appended to
# audit.log. This is the engine behind the Self-Healing Workflow Builder's gate.
#
# Exit 0 = allow. Exit 2 = block (agent must stop and ask the human).

set -euo pipefail
AUDIT_LOG="${AUDIT_LOG:-audit.log}"

# Patterns that must NEVER auto-run. Tune to your blast radius, not ours.
#
# TUNED FOR THIS LAB (my additions, and why):
#   journalctl --vacuum  -> deletes logs; runbook marks it reversible: false.
#                           Irreversible destruction of evidence = gate it.
#   resize-pvc           -> spends money and is hard to undo. This is the exact
#                           command that produced the node-4 +$1840/mo incident.
# Both are 'approve' tier in runbook_disk_pressure.yaml, so the gate and the
# runbook now agree. A tier the gate cannot enforce is only a comment.
DESTRUCTIVE='(\brm\b.*-[rf]|systemctl (stop|disable)|kubectl delete|reboot|shutdown|drop\s+table|dd\s+if=|journalctl\s+--vacuum|resize-pvc)'

payload="$(cat)"
cmd="$(printf '%s' "$payload" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("tool_input",{}).get("command",""))')"
ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if printf '%s' "$cmd" | grep -Eiq "$DESTRUCTIVE"; then
  if [[ "${HUMAN_APPROVAL_TOKEN:-}" == "I-APPROVE" ]]; then
    echo "$ts ALLOW(approved) :: $cmd" >> "$AUDIT_LOG"
    exit 0
  fi
  echo "$ts BLOCK(needs-human) :: $cmd" >> "$AUDIT_LOG"
  echo "BLOCKED: '$cmd' is a state-changing action and requires human approval." >&2
  exit 2
fi

echo "$ts ALLOW(read-only) :: $cmd" >> "$AUDIT_LOG"
exit 0
