"""Authenticated checks for the fixed service."""

import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
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
    return status, parsed, raw


def redact(value):
    if isinstance(value, str):
        for token in TOKENS:
            value = value.replace(token, "<token>")
        return value.replace("learn-alice", "<password>").replace("learn-staff", "<password>")
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    return value


def login(username):
    status, body, _ = call("POST", "/login", {"username": username, "password": f"learn-{username}"})
    if status != 200:
        raise SystemExit(f"login failed for {username}: {status}")
    TOKENS.append(body["token"])
    return {"X-Token": body["token"]}


def main():
    alice = login("alice")
    staff = login("staff")
    payload = "<script>alert('xss')</script>"
    checks = [
        ("28-sqli-profile-alice", "GET", "/profile?" + urlencode({"id": "1 OR 1=1"}), None, alice),
        ("29-idor-profile-alice", "GET", "/profile?id=2", None, alice),
        ("30-search-sqli-alice", "GET", "/search?" + urlencode({"q": "' OR 1=1--"}), None, alice),
        ("31-search-own-alice", "GET", "/search?q=TEST", None, alice),
        ("32-orders-alice", "GET", "/orders", None, alice),
        ("33-admin-forged-alice", "GET", "/admin/export", None, {**alice, "X-Role": "staff"}),
        ("34-admin-staff", "GET", "/admin/export", None, staff),
        ("35-files-bob-alice", "GET", "/files?" + urlencode({"user": "bob", "path": "receipt.txt"}), None, alice),
        ("36-traversal-alice", "GET", "/files?" + urlencode({"user": "alice", "path": "../bob/receipt.txt"}), None, alice),
        ("37-logs-alice", "GET", "/debug/logs", None, alice),
        ("38-logs-staff", "GET", "/debug/logs", None, staff),
        ("39-price-alice", "POST", "/orders", {"product": "lamp", "price": 1}, alice),
        ("40-review-xss-alice", "POST", "/reviews", {"product": "chair", "text": payload}, alice),
        ("41-review-view-alice", "GET", "/reviews/view", None, alice),
        ("42-context-alice", "GET", "/assistant/context?order_id=1", None, alice),
        ("43-context-bob-order-alice", "GET", "/assistant/context?order_id=2", None, alice),
        ("44-context-sqli-alice", "GET", "/assistant/context?" + urlencode({"order_id": "0 OR 1=1"}), None, alice),
    ]
    results = []
    for check_id, method, path, body, headers in checks:
        status, parsed, raw = call(method, path, body, headers)
        result = {
            "id": check_id,
            "request": {"method": method, "path": path, "body": redact(body)},
            "response": {"status": status, "body": redact(parsed)},
        }
        if check_id == "41-review-view-alice":
            result["response"]["escaped"] = payload not in raw and "&lt;script&gt;" in raw
        if check_id == "38-logs-staff":
            result["response"]["leaks_token"] = any(token in raw for token in TOKENS)
            result["response"]["leaks_password"] = "learn-alice" in raw or "learn-staff" in raw
        if check_id == "32-orders-alice" and isinstance(parsed, list):
            result["response"]["owners"] = [row.get("owner") for row in parsed]
        if check_id == "31-search-own-alice" and isinstance(parsed, list):
            result["response"]["names"] = [row.get("name") for row in parsed]
        results.append(result)
        print(f"[{check_id}] {status}")
    (HERE / "28-auth-checks.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
