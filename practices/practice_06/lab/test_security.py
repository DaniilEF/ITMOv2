"""Security regressions for the Mini Shop exercise.

These tests encode the expected safe behavior. They fail on the original
vulnerable service and must pass after the fixes in service.py.
"""

import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from service import Shop, make_handler

PASSWORDS = {"alice": "learn-alice", "bob": "learn-bob", "staff": "learn-staff"}


class SecurityTest(unittest.TestCase):
    def setUp(self):
        self.shop = Shop()
        self.addCleanup(self.shop.close)

    def request(self, method, path, body=None, headers=None):
        with self.shop.lock:
            return self.shop.dispatch(method, path, body or {}, headers or {})

    def login(self, username="alice"):
        status, result = self.request(
            "POST", "/login", {"username": username, "password": PASSWORDS[username]}
        )
        self.assertEqual(status, 200)
        return {"X-Token": result["token"]}

    def test_profile_requires_session(self):
        self.assertEqual(self.request("GET", "/profile?id=1")[0], 401)

    def test_profile_foreign_denied(self):
        auth = self.login("alice")
        self.assertEqual(self.request("GET", "/profile?id=2", headers=auth)[0], 403)

    def test_profile_sqli_denied(self):
        auth = self.login("alice")
        status, result = self.request("GET", "/profile?id=1 OR 1=1", headers=auth)
        self.assertIn(status, (400, 403))
        self.assertNotIn("TEST_BOB", json.dumps(result))

    def test_search_sqli_scoped(self):
        auth = self.login("alice")
        status, result = self.request("GET", "/search?q=' OR 1=1--", headers=auth)
        self.assertEqual(status, 200)
        self.assertNotIn("TEST_BOB", json.dumps(result))

    def test_search_returns_only_own_profile(self):
        auth = self.login("alice")
        status, result = self.request("GET", "/search?q=TEST", headers=auth)
        self.assertEqual(status, 200)
        self.assertEqual([row["name"] for row in result], ["TEST_ALICE"])

    def test_orders_require_session_and_are_scoped(self):
        self.assertEqual(self.request("GET", "/orders")[0], 401)
        auth = self.login("alice")
        status, result = self.request("GET", "/orders", headers=auth)
        self.assertEqual(status, 200)
        self.assertEqual({row["owner"] for row in result}, {1})

    def test_forged_role_denied(self):
        self.assertIn(
            self.request("GET", "/admin/export", headers={"X-Role": "staff"})[0],
            (401, 403),
        )
        auth = self.login("alice")
        self.assertEqual(
            self.request("GET", "/admin/export", headers={**auth, "X-Role": "staff"})[0],
            403,
        )

    def test_staff_export_allowed_by_session(self):
        auth = self.login("staff")
        status, rows = self.request("GET", "/admin/export", headers=auth)
        self.assertEqual(status, 200)
        self.assertEqual(len(rows), 2)

    def test_files_require_session(self):
        self.assertEqual(
            self.request("GET", "/files?user=alice&path=receipt.txt")[0], 401
        )

    def test_files_cross_user_denied(self):
        auth = self.login("alice")
        self.assertEqual(
            self.request("GET", "/files?user=bob&path=receipt.txt", headers=auth)[0],
            403,
        )

    def test_files_traversal_denied(self):
        auth = self.login("alice")
        for path in ("../bob/receipt.txt", "../../private/operator-note.txt"):
            with self.subTest(path=path):
                status, result = self.request(
                    "GET", f"/files?user=alice&path={path}", headers=auth
                )
                self.assertIn(status, (400, 403, 404))
                self.assertNotIn("TEST", json.dumps(result))

    def test_staff_can_read_other_user_file(self):
        auth = self.login("staff")
        status, result = self.request(
            "GET", "/files?user=bob&path=receipt.txt", headers=auth
        )
        self.assertEqual(status, 200)
        self.assertIn("TEST_BOB", result["content"])

    def test_price_is_ignored_for_customer(self):
        auth = self.login("alice")
        status, order = self.request(
            "POST", "/orders", {"product": "lamp", "price": 1}, headers=auth
        )
        self.assertEqual(status, 201)
        self.assertEqual(order["price"], 1500)

    def test_xss_is_escaped(self):
        auth = self.login("alice")
        payload = "<script>alert(1)</script>"
        self.assertEqual(
            self.request(
                "POST", "/reviews", {"product": "chair", "text": payload}, headers=auth
            )[0],
            201,
        )
        status, body = self.request("GET", "/reviews/view", headers=auth)
        self.assertEqual(status, 200)
        self.assertNotIn(payload, body)
        self.assertIn("&lt;script&gt;", body)

    def test_reviews_require_session(self):
        self.assertEqual(
            self.request("POST", "/reviews", {"product": "chair", "text": "x"})[0],
            401,
        )

    def test_execute_requires_session(self):
        cases = [
            {"tool": "export_profiles", "arguments": {}},
            {"tool": "read_file", "arguments": {"path": "private/operator-note.txt"}},
            {"tool": "delete_tree", "arguments": {"path": "."}},
        ]
        for decision in cases:
            with self.subTest(tool=decision["tool"]):
                status, _ = self.request(
                    "POST", "/assistant/execute", {"decision": decision}
                )
                self.assertIn(status, (401, 403))

    def test_execute_customer_denied_for_privileged_tools(self):
        auth = self.login("alice")
        cases = [
            {"tool": "export_profiles", "arguments": {}},
            {"tool": "read_file", "arguments": {"path": "private/operator-note.txt"}},
            {"tool": "read_file", "arguments": {"path": "../../private/operator-note.txt"}},
            {"tool": "delete_tree", "arguments": {"path": "."}},
        ]
        for decision in cases:
            with self.subTest(tool=decision["tool"], args=decision["arguments"]):
                status, result = self.request(
                    "POST", "/assistant/execute", {"decision": decision}, headers=auth
                )
                self.assertIn(status, (403, 400))
                self.assertNotIn("TEST_ONLY_OPERATOR_SECRET", json.dumps(result))

    def test_execute_customer_can_read_own_receipt(self):
        auth = self.login("alice")
        status, result = self.request(
            "POST",
            "/assistant/execute",
            {"decision": {"tool": "read_file", "arguments": {"path": "files/alice/receipt.txt"}}},
            headers=auth,
        )
        self.assertEqual(status, 200)
        self.assertIn("TEST_ALICE", result["content"])

    def test_execute_staff_can_export(self):
        auth = self.login("staff")
        status, rows = self.request(
            "POST",
            "/assistant/execute",
            {"decision": {"tool": "export_profiles", "arguments": {}}},
            headers=auth,
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(rows), 2)

    def test_logs_require_staff_and_redact_secrets(self):
        alice = self.login("alice")
        self.request("GET", "/profile?id=1", headers=alice)
        self.assertIn(self.request("GET", "/debug/logs")[0], (401, 403))
        staff = self.login("staff")
        status, logs = self.request("GET", "/debug/logs", headers=staff)
        self.assertEqual(status, 200)
        text = json.dumps(logs)
        self.assertNotIn(alice["X-Token"], text)
        self.assertNotIn("learn-alice", text)
        self.assertIn("<redacted>", text)

    def test_context_sqli_is_rejected_or_scoped(self):
        auth = self.login("alice")
        status, result = self.request(
            "GET", "/assistant/context?order_id=0 OR 1=1", headers=auth
        )
        self.assertIn(status, (400, 403))
        if isinstance(result, dict):
            self.assertNotIn("lamp", result.get("prompt", ""))

    def test_context_contains_own_order_and_not_other(self):
        auth = self.login("alice")
        status, result = self.request("GET", "/assistant/context?order_id=1", headers=auth)
        self.assertEqual(status, 200)
        self.assertIn("chair", result["prompt"])
        self.assertNotIn("lamp", result["prompt"])

    def test_error_response_has_no_internal_details(self):
        auth = self.login("alice")
        try:
            status, result = self.request("GET", "/profile?id=abc", headers=auth)
        except Exception as exc:
            self.fail(f"unhandled exception leaked to caller: {exc}")
        self.assertIn(status, (400, 403))
        text = json.dumps(result)
        self.assertNotIn("OperationalError", text)
        self.assertNotIn("Traceback", text)


class HttpSecurityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shop = Shop()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(cls.shop))
        cls.server.daemon_threads = True
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=5)
        cls.server.server_close()
        cls.shop.close()

    def call(self, method, path, data=None, headers=None):
        request_headers = {"Content-Type": "application/json", **(headers or {})}
        request = Request(self.base + path, data=data, headers=request_headers, method=method)
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as exc:
            response = exc
        with response:
            return response.status, response.headers, response.read().decode()

    def login(self):
        status, _, body = self.call(
            "POST", "/login",
            json.dumps({"username": "alice", "password": PASSWORDS["alice"]}).encode(),
        )
        self.assertEqual(status, 200)
        return {"X-Token": json.loads(body)["token"]}

    def test_invalid_json_returns_generic_error(self):
        status, _, body = self.call("POST", "/login", b"{")
        self.assertEqual(status, 500)
        self.assertNotIn("JSONDecodeError", body)
        self.assertNotIn("Traceback", body)
        self.assertEqual(json.loads(body), {"error": "internal error"})

    def test_reviews_view_has_html_content_type(self):
        auth = self.login()
        self.call(
            "POST", "/reviews",
            json.dumps({"product": "chair", "text": "ok"}).encode(), auth,
        )
        status, headers, body = self.call("GET", "/reviews/view", headers=auth)
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn("ok", body)


if __name__ == "__main__":
    unittest.main()
