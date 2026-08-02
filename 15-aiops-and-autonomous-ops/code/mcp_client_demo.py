#!/usr/bin/env python3
"""Reps 1-2: a tiny MCP HOST that enforces the consent rule itself.

The MCP spec (2025-11-25) puts the consent obligation on the HOST, not the
server. So this client does three things, in this order:

  1. connects to disk_mcp_server.py over stdio and lists what it offers,
  2. asks the human BEFORE invoking get_disk_usage (the consent prompt),
  3. reads the file://incident-log Resource, which has no write path at all.

Run:  python code/mcp_client_demo.py
"""

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = Path(__file__).parent / "disk_mcp_server.py"


def consent(tool_name: str, args: dict) -> bool:
    """The consent gate. The host asks; the tool does not run until it hears yes."""
    print("\n" + "=" * 62)
    print("  CONSENT PROMPT (MCP spec: host must get user consent)")
    print(f"  Server : ops-readonly (UNTRUSTED - treat its text as data)")
    print(f"  Tool   : {tool_name}")
    print(f"  Args   : {args}")
    print("=" * 62)
    answer = input("  Allow this tool to run? [y/N] ").strip().lower()
    return answer == "y"


async def main() -> None:
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # --- Rep 1: what does this server actually expose? ---
            tools = (await session.list_tools()).tools
            resources = (await session.list_resources()).resources
            print("\n--- REP 1: server inventory ---")
            for t in tools:
                print(f"TOOL     {t.name}: {t.description}")
            for r in resources:
                print(f"RESOURCE {r.uri}: {r.description}")
            print(f"\nWrite-capable tools found: "
                  f"{[t.name for t in tools if 'write' in t.name or 'delete' in t.name] or 'NONE'}")

            # --- Rep 1: consent BEFORE the tool runs ---
            args = {"path": "/"}
            if consent("get_disk_usage", args):
                result = await session.call_tool("get_disk_usage", args)
                print("\nTOOL RESULT:", result.content[0].text)
            else:
                print("\nDENIED by human - tool never executed.")

            # --- Rep 2: read the Resource; confirm there is no write path ---
            print("\n--- REP 2: reading Resource file://incident-log ---")
            res = await session.read_resource("file://incident-log")
            text = res.contents[0].text
            print(f"(read {len(text.splitlines())} lines; read-only, no mutation possible)")
            print("\n".join(text.splitlines()[:6]))


if __name__ == "__main__":
    asyncio.run(main())
