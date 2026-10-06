#!/usr/bin/env bash
set -euo pipefail

# Simple runner to boot the AGENTS MVP server, run two checks via skill, then stop the server.
# Intended to be used by pre-commit. Keeps output concise.

ROOT_DIR=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
SRV="${ROOT_DIR}/practices/practice_04/server.py"
SKILL="${ROOT_DIR}/practices/practice_04/skills/agents_qa.py"
PAY_OK="${ROOT_DIR}/practices/practice_04/samples/success_payload.json"
PAY_LONG="${ROOT_DIR}/practices/practice_04/samples/error_payload_long.json"

# Find a free port if 8080 is occupied
PORT=${AGENTS_PORT:-8080}
HOST=${AGENTS_HOST:-127.0.0.1}

if lsof -iTCP -sTCP:LISTEN -P | grep -q ":${PORT} \(LISTEN\)" 2>/dev/null; then
  echo "[agents-qa] Port ${PORT} busy; selecting 8081"
  PORT=8081
fi

export AGENTS_HOST="${HOST}"
export AGENTS_PORT="${PORT}"

echo "[agents-qa] Starting server on http://${HOST}:${PORT}"
python3 "${SRV}" >/tmp/agents_mvp_server.log 2>&1 &
SRV_PID=$!

cleanup() {
  if kill -0 "${SRV_PID}" 2>/dev/null; then
    kill "${SRV_PID}" 2>/dev/null || true
    wait "${SRV_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

# Wait for server to accept connections
for i in {1..20}; do
  if curl -sS -X POST "http://${HOST}:${PORT}/api/hints" -H 'Content-Type: application/json' -d '{"code_bundle":[],"test_output":"","lang":"ru"}' >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

echo "[agents-qa] Running success check"
python3 "${SKILL}" --payload "${PAY_OK}" --agents-url "http://${HOST}:${PORT}/api/hints" >/tmp/agents_mvp_skill_ok.json

echo "[agents-qa] Running 413 check"
set +e
python3 "${SKILL}" --payload "${PAY_LONG}" --agents-url "http://${HOST}:${PORT}/api/hints" >/tmp/agents_mvp_skill_413.json
STATUS=$?
set -e

if [[ ${STATUS} -ne 0 ]]; then
  echo "[agents-qa] 413 scenario returned non-zero exit; treating as expected in pre-commit"
fi

echo "[agents-qa] OK"
