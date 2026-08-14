#!/bin/bash
# Start the SlimeMold testbed: Python engine (background) + Vite dev server (exposed).
# The Vite dev server proxies /api to the engine on :8642.
set -e

ENGINE_HOST="${ENGINE_HOST:-127.0.0.1}"
ENGINE_PORT="${ENGINE_PORT:-8642}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "$(dirname "$0")"

# Start the engine in the background.
echo "Starting SlimeMold engine on $ENGINE_HOST:$ENGINE_PORT ..."
PYTHONPATH=src "$PYTHON_BIN" -m slime_mold serve --host "$ENGINE_HOST" --port "$ENGINE_PORT" &
ENGINE_PID=$!

cleanup() {
    echo "Stopping engine (pid $ENGINE_PID) ..."
    kill "$ENGINE_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Start the frontend dev server (the exposed port).
cd web
npm run dev
