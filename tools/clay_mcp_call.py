#!/usr/bin/env python3
"""Call a Clay MCP tool over stdio JSON-RPC.

Works around the Claude Code plugin tool-registration bug by talking to the
plugin's `clay mcp` server directly.

Usage:
  clay_mcp_call.py <tool> '<json_args>'
  clay_mcp_call.py <tool> @args.json
  echo '<json_args>' | clay_mcp_call.py <tool> -

Tools: read, edit_node, validate_workflow, execute_clay_action,
       surfaces_read, surfaces_list, surfaces_edit_trigger, table
"""
import json
import select
import subprocess
import sys

from clay_cli import plugin_clay


def newest_clay() -> str:
    """Resolve the newest plugin-pinned clay launcher (survives plugin updates)."""
    path = plugin_clay()
    if not path:
        sys.exit("no clay launcher found in plugin cache; reinstall the Clay plugin")
    return path


def main() -> None:
    tool = sys.argv[1]
    raw = sys.argv[2] if len(sys.argv) > 2 else "{}"
    if raw == "-":
        raw = sys.stdin.read()
    elif raw.startswith("@"):
        with open(raw[1:]) as f:
            raw = f.read()
    args = json.loads(raw)

    p = subprocess.Popen([newest_clay(), "mcp"], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def send(msg):
        p.stdin.write(json.dumps(msg) + "\n")
        p.stdin.flush()

    def recv(timeout=300):
        r, _, _ = select.select([p.stdout], [], [], timeout)
        if not r:
            print("TIMEOUT", file=sys.stderr)
            sys.exit(1)
        line = p.stdout.readline()
        return json.loads(line) if line.strip() else None

    send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
          "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                     "clientInfo": {"name": "clay-workbench", "version": "1.0"}}})
    recv()
    send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    send({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
          "params": {"name": tool, "arguments": args}})
    resp = recv()
    p.terminate()

    if resp is None or "error" in resp:
        print(json.dumps(resp), file=sys.stderr)
        sys.exit(1)
    result = resp.get("result", {})
    for c in result.get("content", []):
        if c.get("type") == "text":
            print(c.get("text", ""))
    if result.get("isError"):
        sys.exit(1)


if __name__ == "__main__":
    main()
