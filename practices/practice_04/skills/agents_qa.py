#!/usr/bin/env python3
"""
Skill 'agents-qa': orchestrates a call to MCP tool agents.hints.call,
validates OUT-1 shape and QA-1 (evidence appears in input).
"""
import argparse
import json
import os
import subprocess
import sys
from typing import Any, Dict, Tuple


def _load_payload(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class MCPClient:

    def __init__(self, proc: subprocess.Popen):
        self.proc = proc
        self._id = 0

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def call(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        req_id = self._next_id()
        req = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params
        }
        self.proc.stdin.write((json.dumps(req) + "\n").encode("utf-8"))
        self.proc.stdin.flush()
        # read lines until we get matching id
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("MCP server terminated unexpectedly")
            obj = json.loads(line.decode("utf-8"))
            if obj.get("id") == req_id and "result" in obj:
                return obj["result"]
            if obj.get("id") == req_id and "error" in obj:
                raise RuntimeError(f"MCP error: {obj['error']}")


def _start_mcp(
    cmd: Tuple[str, ...],
    env: Dict[str, str] | None = None
) -> subprocess.Popen:
    return subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env
    )


def _validate_out1(body: Dict[str, Any], src: Dict[str,
                                                   str]) -> Tuple[bool, str]:
    # Basic OUT-1: summary(str), hints(list<=3 with file,line,hint,evidence), checks(list)
    summary = body.get("summary")
    hints = body.get("hints")
    checks = body.get("checks")
    if not isinstance(summary, str):
        return False, "summary is not a string"
    if not isinstance(checks, list):
        return False, "checks is not a list"
    if not isinstance(hints, list):
        return False, "hints is not a list"
    if len(hints) > 3:
        return False, "more than 3 hints"
    corpus = (
        src.get("code", "") + "\n" + src.get("diff", "") + "\n" +
        src.get("test_output", "")
    )
    for h in hints:
        if not isinstance(h, dict):
            return False, "hint item not dict"
        if "file" not in h or "line" not in h or "hint" not in h or "evidence" not in h:
            return False, "hint missing required fields"
        ev = str(h.get("evidence") or "")
        if not ev or ev not in corpus:
            return False, f"evidence not found in input: {ev!r}"
    return True, "OK"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--payload", required=True, help="Path to JSON payload for /api/hints"
    )
    ap.add_argument(
        "--mcp-cmd",
        default="python3 practices/practice_04/mcp/agents_mcp.py",
        help="Command to start MCP server"
    )
    ap.add_argument(
        "--agents-url",
        default=os.environ.get("AGENTS_URL", "http://127.0.0.1:8080/api/hints")
    )
    args = ap.parse_args()

    payload = _load_payload(args.payload)
    # Build corpus for QA-1 validation
    code = "\n".join([
        str(it.get("content", ""))
        for it in payload.get("code_bundle", [])
        if isinstance(it, dict)
    ])
    corpus = {
        "code": code,
        "diff": str(payload.get("diff") or ""),
        "test_output": str(payload.get("test_output") or "")
    }

    # Start MCP server
    cmd = tuple(args.mcp_cmd.split())
    env = dict(os.environ)
    env["AGENTS_URL"] = args.agents_url
    proc = _start_mcp(cmd, env=env)
    try:
        client = MCPClient(proc)
        client.call(
            "initialize",
            {"clientInfo": {
                "name": "agents-qa",
                "version": "0.1"
            }}
        )
        tools = client.call("tools/list", {})
        names = [t.get("name") for t in tools.get("tools", [])]
        if "agents.hints.call" not in names:
            raise RuntimeError("agents.hints.call not listed by MCP")
        result = client.call(
            "tools/call", {
                "name": "agents.hints.call",
                "arguments": payload
            }
        )
        content = result.get("content") or []
        if not content or content[0].get("type") != "json":
            raise RuntimeError("MCP returned unexpected content")
        data = content[0].get("value") or {}
        # Handle HTTP error statuses explicitly (e.g., 413)
        if isinstance(data, dict) and int(data.get("status", 200)) != 200:
            status = int(data.get("status", 0))
            body = data.get("body") if isinstance(data.get("body"),
                                                  dict) else {}
            err = body.get("error") or ""
            msg = f"HTTP {status} {err}".strip()
            print(
                json.dumps({
                    "ok": False,
                    "message": msg,
                    "response": body,
                    "raw": data
                },
                           ensure_ascii=False)
            )
            return
        body = data.get("body") if isinstance(data, dict) else None
        if not isinstance(body, dict):
            # Fallbacks: some servers may inline OUT-1 or use 'json'
            if isinstance(data, dict) and {"summary", "hints", "checks"
                                          }.issubset(set(data.keys())):
                body = data
            elif isinstance(data, dict) and isinstance(data.get("json"), dict):
                body = data.get("json")
            else:
                body = {}
        ok, msg = _validate_out1(body, corpus)
        print(
            json.dumps({
                "ok": ok,
                "message": msg,
                "response": body,
                "raw": data
            },
                       ensure_ascii=False)
        )
        if not ok:
            sys.exit(2)
    finally:
        try:
            proc.terminate()
        except Exception:
            pass


if __name__ == "__main__":
    main()
