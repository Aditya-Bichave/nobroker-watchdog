#!/usr/bin/env bash
set -euo pipefail

# Setup script for NoBroker Watchdog. Installs Poetry and project dependencies.
# Intended for Debian/Ubuntu systems.

# Determine whether sudo is required
if [ "$(id -u)" -ne 0 ]; then
  SUDO="sudo"
else
  SUDO=""
fi

if ! command -v python3.11 >/dev/null 2>&1; then
  echo "Python 3.11 not found. Installing..."
  $SUDO apt-get update
  $SUDO apt-get install -y python3.11 python3.11-venv python3.11-distutils
fi

if ! command -v pipx >/dev/null 2>&1; then
  echo "pipx not found. Installing..."
  $SUDO apt-get update
  $SUDO apt-get install -y pipx
fi

if ! command -v poetry >/dev/null 2>&1; then
  echo "Poetry not found. Installing via pipx..."
  pipx install poetry
fi

echo "Installing project dependencies via Poetry..."
poetry install --no-interaction --no-ansi

echo "Setup complete."
