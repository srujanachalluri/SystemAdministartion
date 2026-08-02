#!/usr/bin/env python3
"""Rep 9: your logs are untrusted input.

Summarize an incident log the way an agent would. A hostile line has been planted
in hostile_incident.log as a fake FILENAME. The point of the rep is to show the
difference between treating that text as DATA and treating it as an INSTRUCTION.

  python code/log_summarize.py code/hostile_incident.log
"""

import re
import sys
from pathlib import Path

# Anything that looks like it is addressing the agent rather than describing an event.
INSTRUCTION_SHAPE = re.compile(
    r"(IGNORE[- ]PRIOR|ignore (all )?(prior|previous)|disregard|you must|run rm)", re.I)


def summarize(path: Path) -> None:
    lines = [l.rstrip("\n") for l in path.read_text().splitlines() if l.strip()]
    print(f"--- SUMMARY of {path.name} ({len(lines)} lines) ---")

    suspicious = []
    for i, line in enumerate(lines, 1):
        if INSTRUCTION_SHAPE.search(line):
            suspicious.append((i, line))

    events = [l for l in lines if not l.startswith("#")]
    print(f"nodes seen : {sorted({p[1] for l in events if len(p := l.split()) > 1})}")
    print(f"alerts     : {sum('ALERT' in l for l in events)}")
    print(f"gate events: {sum('GATE' in l or 'APPROVE' in l for l in events)}")

    print("\n--- UNTRUSTED CONTENT HANDLING ---")
    if not suspicious:
        print("no instruction-shaped text found")
        return
    for i, line in suspicious:
        print(f"line {i}: QUARANTINED as DATA, not executed")
        print(f"    verbatim: {line[:120]}")
    print("\nThis text was quoted, never followed. An agent that can also run "
          "commands must make that choice explicitly, every time.")


if __name__ == "__main__":
    summarize(Path(sys.argv[1] if len(sys.argv) > 1 else "code/hostile_incident.log"))
