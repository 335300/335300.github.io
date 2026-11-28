#!/usr/bin/env bash
#
# Open Centwise Final Project from source on a fresh copy of the sample data.
#
#   ./run-sample.sh            copy sample-data/ to a scratch folder and start the app
#   ./run-sample.sh --new      first make the sample data again (same figures every time)
#
# The copy lives in $TMPDIR/centwise-final-sample, so whatever you click in the app
# never changes sample-data/ itself. Run ./setup.sh once before this.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SAMPLE="$ROOT/sample-data"
WORK="${TMPDIR:-/tmp}/centwise-final-sample"

[[ -x "$ROOT/backend/.venv/bin/python" ]] || { echo "ERROR: run ./setup.sh first." >&2; exit 1; }

if [[ "${1:-}" == "--new" || ! -f "$SAMPLE/data.json" ]]; then
  echo "--> Making the sample data"
  (cd "$ROOT/backend" && .venv/bin/python -W ignore scripts/2026-11-28-make-sample-data.py "$SAMPLE" --force)
fi

echo "--> Fresh copy of the sample data in $WORK"
rm -rf "$WORK"
mkdir -p "$WORK"
cp -R "$SAMPLE/." "$WORK/"

echo "--> Starting the app (close the window to stop)"
cd "$ROOT/frontend"
CENTWISE_DATA_DIR="$WORK" npm run dev
