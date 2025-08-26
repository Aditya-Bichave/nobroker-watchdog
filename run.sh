#!/usr/bin/env bash
set -euo pipefail

# Simple one-command runner
if ! command -v poetry >/dev/null 2>&1; then
  echo "Poetry not found. Please install Poetry or use Docker."
  exit 1
fi

# Install deps if not already
poetry install --no-interaction --no-ansi

# Run once (polling loop is handled by the app using SCAN_INTERVAL_MINUTES)
poetry run python -m nobroker_watchdog.main daemon
