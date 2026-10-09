#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON="${PYTHON:-$ROOT_DIR/.venv/bin/python}"
VENDOR="${ATLAS_DATA_VENDOR:-hybrid}"
MAX_SYMBOLS="${ATLAS_DATA_MAX_SYMBOLS:-8}"
DAYS="${ATLAS_DATA_DAYS:-260}"
SNAPSHOT_FLAG=()
if [[ "${ATLAS_INCLUDE_KR_SNAPSHOTS:-0}" == "1" ]]; then
  SNAPSHOT_FLAG=(--include-kr-snapshots)
fi

"$PYTHON" -m atlas_investment.cli daily-data-refresh --vendor "$VENDOR" "${SNAPSHOT_FLAG[@]}" --max-symbols "$MAX_SYMBOLS" --days "$DAYS"
"$PYTHON" -m atlas_investment.cli dart-event-signals --days 7 --limit 20 || true
"$PYTHON" -m atlas_investment.cli dashboard-html
