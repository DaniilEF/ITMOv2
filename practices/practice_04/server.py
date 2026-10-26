#!/usr/bin/env python3
"""
AGENTS service (MVP)

Implements POST /api/hints per AGENTS.md with:
- API-1: input length limit (20_000 chars) -> 413
- SEC-1: sanitizer masks tokens/passwords/keys in code_bundle/diff/test_output
- REL-1: LLM client stub with 10s timeout and controlled degraded response
- OUT-1: response shape {summary, hints<=3, checks}; QA-1 validator ensures
         evidence appears in provided inputs; hints without evidence removed
- SCOPE-1: advisory only; does not write code or call GitHub

No external dependencies; uses Python stdlib only.
"""

# pylint: disable=line-too-long

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

MAX_INPUT = 20000  # API-1 limit


def _safe_len(s: Optional[str]) -> int:
    return len(s or "")


def sanitize_text(text: str) -> str:
    """SEC-1: Mask common secrets. Idempotent and O(n) overall (patterns linear scans)."""
    if not text:
        return text

    # Basic tokens: Bearer, ghp_, AWS keys, private keys, generic passwords
    patterns = [
        (re.compile(r"Bearer\s+[A-Za-z0-9\-_.]+"), "Bearer [REDACTED]"),
        (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "ghp_[REDACTED]"),
        (re.compile(r"AKIA[0-9A-Z]{16}"), "AKIA[REDACTED]"),
        (
            re.compile(
                r"aws_secret_access_key\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{20,}['\"]?",
                re.I
            ), "aws_secret_access_key: [REDACTED]"
        ),
        (
            re.compile(r"(?i)password\s*[:=]\s*['\"][^'\"]+['\"]"),
            "password: '[REDACTED]'"
        ),
        (
            re.compile(
                r"-----BEGIN (?:RSA|EC|DSA|OPENSSH|PRIVATE) KEY-----[\s\S]*?-----END (?:RSA|EC|DSA|OPENSSH|PRIVATE) KEY-----"
            ), "-----BEGIN KEY-----\n[REDACTED]\n-----END KEY-----"
        ),
    ]

    result = text
    for rx, repl in patterns:
        result = rx.sub(repl, result)
    return result


def sanitize_input(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Apply SEC-1 sanitizer to code_bundle, diff, and test_output."""
    out = dict(payload)
    if "code_bundle" in out and isinstance(out["code_bundle"], list):
        safe_bundle = []
        for item in out["code_bundle"]:
            if not isinstance(item, dict):
                continue
            safe_item = dict(item)
            safe_item["content"] = sanitize_text(
                str(safe_item.get("content", ""))
            )
            safe_bundle.append({
                "path": str(safe_item.get("path", "")),
                "content": safe_item["content"]
            })
        out["code_bundle"] = safe_bundle
    if "diff" in out and out["diff"] is not None:
        out["diff"] = sanitize_text(str(out["diff"]))
    if "test_output" in out and out["test_output"] is not None:
        out["test_output"] = sanitize_text(str(out["test_output"]))
    return out


def input_size(payload: Dict[str, Any]) -> int:
    """Compute approximate total size of input to enforce API-1 limit."""
    size = 0
    diff = payload.get("diff")
    if isinstance(diff, str):
        size += len(diff)
    if isinstance(payload.get("code_bundle"), list):
        for item in payload["code_bundle"]:
            if isinstance(item, dict):
                size += len(str(item.get("path", "")))
                size += len(str(item.get("content", "")))
    test_output = payload.get("test_output")
    if isinstance(test_output, str):
        size += len(test_output)
    return size


def select_relevant_fragments(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Selector: parse test_output for file:line patterns and extract nearby context
    from code_bundle items. Minimal heuristic per MVP.
    """
    # pylint: disable=too-many-locals,too-many-branches
    bundle = payload.get("code_bundle") or []
    test_output = payload.get("test_output") or ""

    # Find mentions like: path/to/file.py:123 or File "path", line 45
    mentions: List[Tuple[str, int]] = []
    for m in re.finditer(r"(?P<file>[\w\-/\\\.]+):(?P<line>\d+)", test_output):
        try:
            mentions.append((m.group("file"), int(m.group("line"))))
        except Exception:  # pylint: disable=broad-exception-caught
            pass
    for m in re.finditer(
        r"File \"(?P<file>.+?)\", line (?P<line>\d+)", test_output
    ):
        try:
            mentions.append((m.group("file"), int(m.group("line"))))
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    # Build a compact bundle with ±20 lines around mentioned locations
    compact_bundle: List[Dict[str, Any]] = []
    for item in bundle:
        path = str(item.get("path", ""))
        content = str(item.get("content", ""))
        if not path or not content:
            continue
        lines = content.splitlines()
        hits = [
            ln for (f, ln) in mentions
            if os.path.normpath(f) == os.path.normpath(path)
        ]
        if not hits:
            # If nothing mentioned, keep small files as-is (<= 400 lines)
            if len(lines) <= 400:
                compact_bundle.append({"path": path, "content": content})
            continue
        kept: List[str] = []
        ranges: List[Tuple[int, int]] = []
        for ln in hits:
            start = max(1, ln - 20)
            end = min(len(lines), ln + 20)
            ranges.append((start, end))
        # Merge overlapping ranges
        ranges.sort()
        merged: List[Tuple[int, int]] = []
        for r in ranges:
            if not merged or r[0] > merged[-1][1] + 1:
                merged.append(list(r))  # type: ignore[arg-type]
            else:
                merged[-1][1] = max(merged[-1][1], r[1])  # type: ignore[index]
        # Extract content with line numbers for reference
        for (start, end) in merged:
            # add a small header to mark the slice
            kept.append(f"@@ {path}:{start}-{end} @@")
            for i in range(start, end + 1):
                kept.append(lines[i - 1])
        compact_bundle.append({"path": path, "content": "\n".join(kept)})

    return {
        "bundle": compact_bundle or bundle,
        "diff": payload.get("diff") or "",
        "test_output": test_output,
    }


def construct_prompt(compact: Dict[str, Any], lang: str) -> str:
    """Build a compact prompt text for the external assistant (LLM)."""
    system = "Ты учебный ассистент. Даёшь короткие подсказки без решения. Каждая подсказка ссылается на строки кода/лога."
    if lang == "en":
        system = "You are a teaching assistant. Give short hints without full solutions. Each hint must cite lines from code/logs."
    # Minimal prompt; in MVP we won't actually call external LLM.
    prompt = [
        system,
        "\nINPUT: test_output:\n",
        compact.get("test_output", ""),
        "\nCODE:\n",
    ]
    for item in compact.get("bundle", []) or []:
        prompt.append(f"### {item.get('path')}\n{item.get('content')[:4000]}")
    if compact.get("diff"):
        prompt.append("\nDIFF:\n" + str(compact.get("diff"))[:4000])
    prompt.append("\nRespond with valid JSON matching OUT-1 schema.\n")
    return "".join(prompt)


def llm_client_with_timeout(
    _prompt: str,
    timeout_sec: int = 10
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    REL-1: External LLM call with 10s timeout. Here we stub it to always degrade.
    Returns (ok, result_json) where ok=False triggers degraded response.
    """
    # Simulate a timeout by sleeping beyond timeout in a separate thread if env says so
    want_timeout = os.environ.get("AGENTS_MVP_SIMULATE_TIMEOUT", "1") == "1"

    result_holder: Dict[str, Any] = {}
    done = threading.Event()

    def _work():
        try:
            if want_timeout:
                time.sleep(timeout_sec + 1)
            else:
                # Provide a trivial well-formed but empty hints response
                result_holder.update({
                    "summary":
                        "No actionable hints detected.",
                    "hints": [],
                    "checks": [
                        "Re-run tests", "Verify file paths in stack trace"
                    ],
                })
        finally:
            done.set()

    t = threading.Thread(target=_work, daemon=True)
    t.start()
    finished = done.wait(timeout=timeout_sec)
    if not finished:
        return False, None
    return True, result_holder


def validate_and_filter_response(
    resp: Dict[str, Any], provided_inputs: Dict[str, str]
) -> Dict[str, Any]:
    """OUT-1/QA-1: enforce schema, ≤3 hints, and evidence appears in inputs."""
    summary = str(resp.get("summary") or "")
    checks = resp.get("checks") or []
    if not isinstance(checks, list):
        checks = []
    checks = [str(c) for c in checks]

    hints_in = resp.get("hints") or []
    if not isinstance(hints_in, list):
        hints_in = []

    # Build concatenated searchable corpus from provided inputs
    corpus = (
        provided_inputs.get("code", "") + "\n" +
        provided_inputs.get("diff", "") + "\n" +
        provided_inputs.get("test_output", "")
    )

    filtered: List[Dict[str, Any]] = []
    for h in hints_in:
        if not isinstance(h, dict):
            continue
        file = str(h.get("file") or "")
        try:
            line = int(h.get("line") or 0)
        except Exception:  # pylint: disable=broad-exception-caught
            line = 0
        hint_text = str(h.get("hint") or "")
        evidence = str(h.get("evidence") or "")
        if not evidence or evidence not in corpus:
            # QA-1: drop hints without verifiable evidence string
            continue
        filtered.append({
            "file": file,
            "line": line,
            "hint": hint_text,
            "evidence": evidence,
        })
        if len(filtered) >= 3:
            break

    return {"summary": summary, "hints": filtered, "checks": checks}


def degraded_response(lang: str) -> Dict[str, Any]:
    """REL-1: Controlled degraded response when LLM is unavailable."""
    if lang == "en":
        return {
            "summary":
                "External assistant is unavailable, please try again later. Hints were not generated.",
            "hints": [],
            "checks": ["Re-run tests and retry the request"],
        }
    return {
        "summary":
            "Внешний ассистент недоступен, попробуйте позже. Подсказки не сгенерированы.",
        "hints": [],
        "checks": ["Перезапустите тесты и повторите запрос"],
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "agents-mvp/1.0"

    def _send_json(self, status: int, data: Dict[str, Any]):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802 (stdlb)
        """POST /api/hints entrypoint implementing API-1, SEC-1, REL-1, OUT-1, QA-1."""
        if self.path != "/api/hints":
            self.send_error(404, "Not Found")
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            raw = self.rfile.read(length)
        except Exception:  # pylint: disable=broad-exception-caught
            self.send_error(400, "Bad Request")
            return
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:  # pylint: disable=broad-exception-caught
            self.send_error(400, "Invalid JSON")
            return

        # Normalize input fields
        diff = payload.get("diff")
        code_bundle = payload.get("code_bundle") or []
        test_output = payload.get("test_output") or ""
        lang = payload.get("lang") or "ru"
        if diff is not None and not isinstance(diff, str):
            diff = str(diff)
        if not isinstance(code_bundle, list):
            code_bundle = []
        if not isinstance(test_output, str):
            test_output = str(test_output)
        if lang not in ("ru", "en"):
            lang = "ru"

        normalized = {
            "diff": diff,
            "code_bundle": code_bundle,
            "test_output": test_output,
            "lang": lang
        }

        # API-1 size limit
        total_size = input_size(normalized)
        if total_size > MAX_INPUT:
            # 413 Payload Too Large
            self.send_response(413)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                json.dumps({
                    "error": "Payload Too Large"
                }).encode("utf-8")
            )
            return

        # SEC-1 sanitize
        sanitized = sanitize_input(normalized)

        # Selector
        compact = select_relevant_fragments(sanitized)

        # Prompt
        prompt = construct_prompt(compact, lang)

        # LLM client with 10s timeout. In MVP, we simulate degraded response by default
        ok, llm_json = llm_client_with_timeout(prompt, timeout_sec=10)
        if not ok or not isinstance(llm_json, dict):
            self._send_json(200, degraded_response(lang))
            return

        # Validator + QA-1
        # Build a corpus to check evidence matches input
        provided_corpus = {
            "code":
                "\n".join([
                    str(it.get("content", ""))
                    for it in (sanitized.get("code_bundle") or [])
                    if isinstance(it, dict)
                ]),
            "diff":
                str(sanitized.get("diff") or ""),
            "test_output":
                str(sanitized.get("test_output") or ""),
        }
        final = validate_and_filter_response(llm_json, provided_corpus)
        # If all hints were dropped by QA-1 and no summary, provide a clear message
        if not final.get("hints") and not final.get("summary"):
            if lang == "en":
                final["summary"
                     ] = "No validated hints remained after checking evidence."
            else:
                final[
                    "summary"
                ] = "После проверки подтверждений не осталось валидных подсказок."

        self._send_json(200, final)

    def log_message(
        self, fmt: str, *args: Any
    ) -> None:  # noqa: A003 (shadow builtin)
        # OBS-1: Log only metadata; avoid raw payloads
        if self.path == "/api/hints":
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except Exception:  # pylint: disable=broad-exception-caught
                length = 0
            # Minimal log: method path size status
            # We can't easily get status here; leave basic info only.
            print(f"[AGENTS] {self.command} {self.path} len={length}")
        else:
            print(f"[HTTP] {self.command} {self.path}")


def main():
    """Start HTTP server and serve forever until interrupted."""
    host = os.environ.get("AGENTS_HOST", "127.0.0.1")
    port = int(os.environ.get("AGENTS_PORT", "8080"))
    httpd = HTTPServer((host, port), Handler)
    print(f"AGENTS MVP listening on http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
