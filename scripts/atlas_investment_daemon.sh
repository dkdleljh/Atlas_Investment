#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

PYTHON="${PYTHON:-$ROOT_DIR/.venv/bin/python}"
INTERVAL="${ATLAS_DAEMON_INTERVAL_SECONDS:-300}"
LOCK_DIR="$ROOT_DIR/data/runtime"
LOCK_FILE="$LOCK_DIR/atlas_investment.lock"
HEARTBEAT_FILE="$LOCK_DIR/heartbeat.json"

mkdir -p "$LOCK_DIR"

status_rank() {
  case "$1" in
    blocked) echo 3 ;;
    degraded) echo 2 ;;
    ok) echo 1 ;;
    *) echo 2 ;;
  esac
}

merge_status() {
  local current="$1"
  local next="$2"
  if [[ "$(status_rank "$next")" -gt "$(status_rank "$current")" ]]; then
    echo "$next"
  else
    echo "$current"
  fi
}

run_status_command() {
  local command="$1"
  local output
  if ! output="$($PYTHON -m atlas_investment.cli $command 2>/tmp/atlas_investment_${command//-/_}.err)"; then
    echo "blocked"
    return
  fi
  printf '%s' "$output" | "$PYTHON" -c 'import json,sys
try:
    payload=json.load(sys.stdin)
except Exception:
    print("degraded")
    raise SystemExit
print(payload.get("overall_status") or payload.get("status") or "degraded")
'
}

if [[ -e "$LOCK_FILE" ]]; then
  existing_pid="$(cat "$LOCK_FILE" 2>/dev/null || true)"
  if [[ "$existing_pid" =~ ^[0-9]+$ ]] && kill -0 "$existing_pid" 2>/dev/null; then
    echo "Atlas Investment daemon lock exists: $LOCK_FILE" >&2
    exit 1
  fi
  rm -f "$LOCK_FILE"
fi

cleanup() {
  rm -f "$LOCK_FILE"
}
trap cleanup EXIT

echo "$$" > "$LOCK_FILE"

while true; do
  started_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  status="ok"

  status="$(merge_status "$status" "$(run_status_command healthcheck)")"
  status="$(merge_status "$status" "$(run_status_command integration-check)")"
  status="$(merge_status "$status" "$(run_status_command dashboard-html)")"

  cat > "$HEARTBEAT_FILE" <<EOF
{"status":"$status","started_at":"$started_at","updated_at":"$(date -u +"%Y-%m-%dT%H:%M:%SZ")","live_orders":"blocked"}
EOF
  "$PYTHON" -m atlas_investment.cli heartbeat-record --status "$status" --source daemon >/dev/null

  sleep "$INTERVAL"
done
