#!/usr/bin/env python3
"""A minimal read-only MCP server for ops.

Exposes ONE Tool (get_disk_usage) and ONE Resource (a log file). This is the
"agent-to-tool" side of the lab: an agent connects, the host asks the human for
consent before the tool runs, and the tool can only READ. Nothing here can
change state. That is the point — least privilege by construction.

Run:  python disk_mcp_server.py     (stdio transport; connect from Claude Code)
Deps: pip install "mcp[cli]"   (FastMCP ships in the official Python SDK)
"""

import shutil
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ops-readonly")

# A log file the agent may READ as a Resource (not a tool — no side effects).
LOG_PATH = Path(__file__).parent / "sample_incident.log"


@mcp.tool()
def get_disk_usage(path: str = "/") -> dict:
    """Return total/used/free bytes for a filesystem path. READ ONLY."""
    total, used, free = shutil.disk_usage(path)
    pct = round(used / total * 100, 1)
    return {"path": path, "total": total, "used": used, "free": free, "used_pct": pct}


@mcp.resource("file://incident-log")
def incident_log() -> str:
    """The current incident log, offered as a Resource the agent may read."""
    return LOG_PATH.read_text(encoding="utf-8") if LOG_PATH.exists() else ""


if __name__ == "__main__":
    # Per the MCP spec (2025-11-25): the HOST must obtain user consent before
    # invoking any tool, and must treat tool descriptions from untrusted
    # servers as untrusted. This server offers no write path at all.
    mcp.run()
