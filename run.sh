#!/usr/bin/env bash
# Quick launcher for simpleSave.
# Usage: ./run.sh
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Creating virtualenv..."
  python3 -m venv .venv
fi

source .venv/bin/activate
# Cheap no-op when nothing changed, but picks up new/updated dependencies
# (e.g. Pygments for syntax highlighting) without needing to delete .venv.
pip install --quiet --upgrade -r requirements.txt

python -m simplesave
