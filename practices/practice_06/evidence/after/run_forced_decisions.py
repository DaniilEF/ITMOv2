"""Send dangerous tool decisions directly to the fixed executor."""

import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
BASE = os.environ.get("SHOP_BASE", "http://127.0.0.1:8066")
TOKENS = []


def call(method, path, body=None, headers=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    request = Request(BASE + path, data=data, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=10) as response:
            raw = response.read().decode("utf-8", "replace")
            status = response.status
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        status = exc.code
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = raw
    return status, parsed


def redact(value):
    if isinstance(value, str):
        for token in TOKENS:
            value = value.replace(token, "<token>")
        return value
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    return value


def login(username):
    status, body = call("POST", "/login", {"username": username, "password": f"learn-{username}"})
    if status != 200:
        raise SystemExit(f"login failed for {username}: {status} {body}")
    TOKENS.append(body["token"])
    return {"X-Token": body["token"]}


def record(finding_id, title, decision, headers, status, body):
    evidence = {
        "id": finding_id,
        "title": title,
        "request": {"method": "POST", "path": "/assistant/execute", "body": redact(decision)},
        "response": {"status": status, "body": redact(body)},
    }
    (HERE / f"{finding_id}.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[{finding_id}] {status} {title}")


def main():
    alice = login("alice")
    staff = login("staff")
    cases = [
        ("20-exec-export-alice", "alice: export_profiles", {"tool": "export_profiles", "arguments": {}}, alice),
        ("21-exec-read-private-alice", "alice: read_file private/operator-note.txt", {"tool": "read_file", "arguments": {"path": "private/operator-note.txt"}}, alice),
        ("22-exec-read-traversal-alice", "alice: read_file ../../private/operator-note.txt", {"tool": "read_file", "arguments": {"path": "../../private/operator-note.txt"}}, alice),
        ("23-exec-delete-alice", "alice: delete_tree('.')", {"tool": "delete_tree", "arguments": {"path": "."}}, alice),
        ("24-exec-read-bob-alice", "alice: read_file files/bob/receipt.txt", {"tool": "read_file", "arguments": {"path": "files/bob/receipt.txt"}}, alice),
        ("25-exec-read-own-alice", "alice: read_file files/alice/receipt.txt", {"tool": "read_file", "arguments": {"path": "files/alice/receipt.txt"}}, alice),
        ("26-exec-export-staff", "staff: export_profiles", {"tool": "export_profiles", "arguments": {}}, staff),
    ]
    for finding_id, title, decision, headers in cases:
        status, body = call("POST", "/assistant/execute", {"decision": decision}, headers)
        record(finding_id, title, {"decision": decision}, headers, status, body)

    status, body = call("GET", "/files?user=alice&path=receipt.txt", headers=alice)
    record("27-files-after-forced", "alice receipt after forced delete", {"method": "GET", "path": "/files?user=alice&path=receipt.txt"}, alice, status, body)


if __name__ == "__main__":
    main()
