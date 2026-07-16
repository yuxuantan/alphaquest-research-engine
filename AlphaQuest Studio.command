#!/bin/zsh
set -eu

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [[ -x ".venv/bin/alphaquest" ]]; then
  exec ".venv/bin/alphaquest" studio start --background
fi

if command -v alphaquest >/dev/null 2>&1; then
  exec alphaquest studio start --background
fi

print -u2 "AlphaQuest Studio is not installed. Ask the administrator to run: make studio-setup"
exit 1
