#!/usr/bin/env bash
set -euo pipefail

# Master script to run API, driver discovery, and UI dev server together.
# - Activates ./devenv if present
# - Starts uvicorn for API (8000) and driver discovery (8001)
# - Starts Vite dev server for UI (5173) with VITE_API_BASE pointing at the API

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

VENV="$ROOT_DIR/devenv/bin/activate"
if [ -f "$VENV" ]; then
  # shellcheck disable=SC1090
  source "$VENV"
fi

API_HOST=${API_HOST:-127.0.0.1}
API_PORT=${API_PORT:-8000}
DISCOVERY_PORT=${DISCOVERY_PORT:-8001}
UI_PORT=${UI_PORT:-5173}
VITE_API_BASE=${VITE_API_BASE:-"http://$API_HOST:$API_PORT/v1"}

pids=()
cleanup() {
  for pid in "${pids[@]:-}"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
  done
}
trap cleanup EXIT INT TERM

start_api() {
  echo "Starting API on http://$API_HOST:$API_PORT"
  NEW_RELIC_CONFIG_FILE=/home/nikhil/goride/app/newrelic.ini newrelic-admin run-program python3 -m uvicorn app.main:app --host "$API_HOST" --port "$API_PORT" --reload &
  pids+=($!)
}

start_discovery() {
  echo "Starting driver discovery on http://$API_HOST:$DISCOVERY_PORT"
  python3 -m uvicorn app.driver_discovery:app --host "$API_HOST" --port "$DISCOVERY_PORT" --reload &
  pids+=($!)
}

start_ui() {
  echo "Starting UI dev server on http://$API_HOST:$UI_PORT/ui/ (VITE_API_BASE=$VITE_API_BASE)"
  pushd "$ROOT_DIR/ui" >/dev/null
  if [ ! -d node_modules ]; then
    npm install
  fi
  VITE_API_BASE="$VITE_API_BASE" npm run dev -- --host "$API_HOST" --port "$UI_PORT" >/tmp/goride_ui.log 2>&1 &
  pids+=($!)
  popd >/dev/null
}

start_api
start_discovery
start_ui

echo "All services started. Press Ctrl+C to stop."

wait -n "${pids[@]}" || true
cleanup
