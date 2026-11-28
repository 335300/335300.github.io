#!/usr/bin/env bash
#
# One-time setup for Centwise Final Project: a project-local Python environment for the
# backend and the npm packages for the Electron/React frontend.
# Nothing is installed system-wide.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

echo "==> Centwise Final Project — setup"

# Prefer an explicit PYTHON, else the first python3 that is 3.11–3.13
# (PyInstaller lags behind the newest Python releases).
find_python() {
  if [[ -n "${PYTHON:-}" ]]; then echo "$PYTHON"; return; fi
  for candidate in python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1 &&
       "$candidate" -c 'import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] <= (3, 13) else 1)' 2>/dev/null; then
      command -v "$candidate"; return
    fi
  done
  return 1
}

if ! PY="$(find_python)"; then
  echo "ERROR: Python 3.11–3.13 is required but was not found." >&2
  echo "       Install it, or set PYTHON=/path/to/python3 and re-run." >&2
  exit 1
fi
echo "--> Python: $PY ($("$PY" --version 2>&1))"

if [[ ! -x "$BACKEND/.venv/bin/python" ]]; then
  echo "--> Creating backend/.venv"
  "$PY" -m venv "$BACKEND/.venv"
fi
echo "--> Installing Python dependencies"
"$BACKEND/.venv/bin/pip" install --quiet --upgrade pip
"$BACKEND/.venv/bin/pip" install --quiet -r "$BACKEND/requirements.txt"

if ! command -v npm >/dev/null 2>&1; then
  echo "ERROR: npm was not found. Install Node.js 20+ and re-run." >&2
  exit 1
fi
echo "--> Node: $(node --version)"
echo "--> Installing frontend packages (this can take a minute)"
(cd "$FRONTEND" && npm install --silent)

echo "--> Running the backend tests"
(cd "$BACKEND" && .venv/bin/python -m pytest -q)

if [[ ! -f "$ROOT/sample-data/data.json" ]]; then
  echo "--> Making the sample data (sample-data/)"
  (cd "$BACKEND" && .venv/bin/python -W ignore scripts/2026-11-28-make-sample-data.py "$ROOT/sample-data")
fi

cat <<'MSG'

==> Setup complete.

    Try it with the sample data:   ./run-sample.sh
    Run the tests:                 cd backend && .venv/bin/python -m pytest -q
    Build and install the app:     ./build-app.sh --install
                                   (the first install starts with the sample data)

    The installed app keeps its data outside the project, in:
      ~/Library/Application Support/Centwise Final Project/

MSG
