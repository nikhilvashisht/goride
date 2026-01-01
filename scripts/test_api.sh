#!/usr/bin/env bash
set -euo pipefail

# Simple smoke-test script for the Goride API
# - Activates virtualenv at ./devenv (if present)
# - Starts uvicorn if the server is not running
# - Exercises key endpoints and prints responses

VEVN_PATH="./devenv/bin/activate"
if [ -f "$VEVN_PATH" ]; then
  # shellcheck disable=SC1090
  source "$VEVN_PATH"
fi

HOST=127.0.0.1
PORT=8000
BASE="http://$HOST:$PORT"
UVICORN_PID=""
STARTED_BY_SCRIPT=0

wait_for() {
  url=$1
  timeout=${2:-10}
  for i in $(seq 1 $((timeout*2))); do
    if curl -sSf "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

# Start server if not responsive
if ! wait_for "$BASE/" 2; then
  echo "Starting uvicorn..."
  python3 -m uvicorn app.main:app --host $HOST --port $PORT --reload > /tmp/goride_uvicorn.log 2>&1 &
  UVICORN_PID=$!
  STARTED_BY_SCRIPT=1
  echo "uvicorn pid $UVICORN_PID"
  if ! wait_for "$BASE/" 15; then
    echo "uvicorn did not start; check /tmp/goride_uvicorn.log"
    exit 1
  fi
fi

run() {
  method=$1
  path=$2
  data=$3
  desc=$4
  url="$BASE$path"
  echo "-- $desc -> $method $url"
  if [ -n "$data" ]; then
    out=$(curl -s -w "\n%{http_code}" -X "$method" -H "Content-Type: application/json" -d "$data" "$url")
  else
    out=$(curl -s -w "\n%{http_code}" -X "$method" "$url")
  fi
  body=$(echo "$out" | sed '$d')
  code=$(echo "$out" | tail -n1)
  echo "HTTP $code"
  if [ -n "$body" ]; then
    echo "$body"
  fi
  echo
  echo "$code"
}

# Run tests (non-fatal checks — we print results and continue)

# Root
run GET "/" "" "Root"

# Create driver location
DRIVER_LOC_PAYLOAD='{"lat":12.9716,"lon":77.5946}'
run POST "/v1/drivers/1/location" "$DRIVER_LOC_PAYLOAD" "Driver location (driver_id=1)"

# Create a ride
RIDE_PAYLOAD='{"rider_id":1,"pickup":{"lat":12.9716,"lon":77.5946},"destination":{"lat":12.9750,"lon":77.6000},"tier":"standard","payment_method":"card"}'
resp=$(curl -s -w "\n%{http_code}" -X POST -H "Content-Type: application/json" -d "$RIDE_PAYLOAD" "$BASE/v1/rides") || true
ride_body=$(echo "$resp" | sed '$d')
ride_code=$(echo "$resp" | tail -n1)
echo "Create ride -> HTTP $ride_code"
if [ -n "$ride_body" ]; then echo "$ride_body"; fi

ride_id=""
if command -v python3 >/dev/null 2>&1; then
  ride_id=$(echo "$ride_body" | python3 -c 'import sys,json
try:
  j=json.load(sys.stdin)
  print(j.get("id",""))
except Exception:
  pass') || true
fi

echo "ride_id=$ride_id"

if [ -n "$ride_id" ] && [ "$ride_id" != "None" ]; then
  run GET "/v1/rides/$ride_id" "" "Get ride $ride_id"
else
  echo "No ride id returned; skipping GET /v1/rides/{id}"
fi

# Try accept (likely will fail if no assignment)
ACCEPT_PAYLOAD='{"assignment_id":1}'
run POST "/v1/drivers/1/accept" "$ACCEPT_PAYLOAD" "Driver accept (driver_id=1)"

# Trigger payment (likely will fail if no payment exists)
PAY_PAYLOAD='{ "trip_id": 1 }'
run POST "/v1/payments" "$PAY_PAYLOAD" "Trigger payment for trip_id=1"

# Cleanup: stop uvicorn if we started it
if [ "$STARTED_BY_SCRIPT" -eq 1 ] && [ -n "$UVICORN_PID" ]; then
  echo "Stopping uvicorn pid $UVICORN_PID"
  kill "$UVICORN_PID" || true
fi

echo "Smoke tests completed."
exit 0
