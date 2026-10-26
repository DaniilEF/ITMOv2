#!/usr/bin/env python3
"""
Minimal Python MCP server (stdio JSON-RPC) exposing one tool: agents.hints.call
Calls local AGENTS MVP endpoint: POST /api/hints
"""
import json
import os
import sys
import urllib.request
import urllib.error
from typing import Any, Dict


def _write(msg: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _ok(id_, result) -> None:
    _write({"jsonrpc": "2.0", "id": id_, "result": result})


def _err(id_, code: int, message: str, data: Any = None) -> None:
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    _write({"jsonrpc": "2.0", "id": id_, "error": err})


def _agents_url() -> str:
    return os.environ.get("AGENTS_URL", "http://127.0.0.1:8080/api/hints")


TOOL = {
    "name":
        "agents.hints.call",
    "description":
        "Call AGENTS /api/hints (POST) with payload {diff, code_bundle, test_output, lang}",
    "inputSchema": {
        "type": "object",
        "properties": {
            "diff": {
                "type": ["string", "null"]
            },
            "code_bundle": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string"
                        },
                        "content": {
                            "type": "string"
                        },
                    },
                    "required": ["path", "content"],
                    "additionalProperties": False,
                },
            },
            "test_output": {
                "type": "string"
            },
            "lang": {
                "type": "string",
                "enum": ["ru", "en"]
            },
        },
        "required": ["code_bundle", "test_output", "lang"],
        "additionalProperties": False,
    },
}


def _http_post_json(url: str, body: Dict[str, Any]) -> Dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            raw = resp.read().decode(charset, errors="replace")
            return {"status": resp.status, "ok": True, "json": json.loads(raw)}
    except urllib.error.HTTPError as e:
        try:
            raw = e.read().decode("utf-8", errors="replace")
            j = json.loads(raw) if raw else {}
        except Exception:
            j = {}
        return {"status": e.code, "ok": False, "json": j, "error": str(e)}
    except Exception as e:
        return {"status": 0, "ok": False, "json": {}, "error": str(e)}


def _handle_initialize(req):
    caps = {"tools": {}}
    result = {
        "protocolVersion": "1.0",
        "serverInfo": {
            "name": "agents-mcp",
            "version": "0.1"
        },
        "capabilities": caps,
    }
    _ok(req.get("id"), result)


def _handle_tools_list(req):
    _ok(req.get("id"), {"tools": [TOOL]})


def _handle_tools_call(req):
    params = req.get("params") or {}
    name = params.get("name")
    args = params.get("arguments") or {}
    if name != TOOL["name"]:
        _err(req.get("id"), -32601, f"Unknown tool: {name}")
        return
    # Make HTTP call to AGENTS endpoint
    url = _agents_url()
    resp = _http_post_json(url, args)
    # Conform to MCP content result
    content_item = {
        "type": "json",
        "value": {
            "status": resp.get("status"),
            "ok": resp.get("ok"),
            "body": resp.get("json")
        }
    }
    _ok(req.get("id"), {"content": [content_item]})


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            # No id to echo
            _write({
                "jsonrpc": "2.0",
                "error": {
                    "code": -32700,
                    "message": "Parse error"
                }
            })
            continue
        method = req.get("method")
        if method == "initialize":
            _handle_initialize(req)
        elif method == "tools/list":
            _handle_tools_list(req)
        elif method == "tools/call":
            _handle_tools_call(req)
        elif method in ("ping", "shutdown"):
            _ok(req.get("id"), {})
        else:
            _err(req.get("id"), -32601, f"Method not found: {method}")


if __name__ == "__main__":
    main()
