#!/usr/bin/env bash
# Build the page and run the end-to-end UI check on a THROWAWAY data folder.
#
#   bash .claude/skills/ui-check/scripts/run_ui_check.sh            # new folders in /tmp
#   bash .claude/skills/ui-check/scripts/run_ui_check.sh --no-build # reuse the last build
#
# Prints where the screenshots are, the PASS/FAIL lines and the console result.
# Never point this at the real data folder: e2e.mjs DELETES its data folder first.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$HERE/../../../.." && pwd)}"
STAMP="$(date +%Y%m%d-%H%M%S)"
SHOTS="/tmp/pc-shots-$STAMP"
DATA="/tmp/pc-test-data-$STAMP"

case "$DATA" in
  /tmp/pc-test-data-*) ;;
  *) echo "Refusing: the data folder must be a fresh /tmp folder." >&2; exit 2 ;;
esac

cd "$ROOT/frontend"
[[ -d node_modules ]] || { echo "frontend/node_modules missing. Run ./setup.sh first." >&2; exit 1; }

if [[ "${1:-}" != "--no-build" ]]; then
  echo "== Building the page (tsc + vite) =="
  npm run build
fi

mkdir -p "$SHOTS"
echo "== Running e2e on throwaway folder $DATA =="
set +e
CENTWISE_DATA_DIR="$DATA" node scripts/e2e.mjs "$SHOTS" "$DATA" 2>&1 | tee "$SHOTS/e2e.log"
CODE=${PIPESTATUS[0]}
set -e

PASS=$(grep -c '^PASS' "$SHOTS/e2e.log" || true)
FAIL=$(grep -c '^FAIL' "$SHOTS/e2e.log" || true)
echo
echo "== Summary =="
echo "Checks: $PASS passed, $FAIL failed"
echo "Console: $(cat "$SHOTS/console.txt" 2>/dev/null || echo 'not written')"
echo "Screenshots: $SHOTS  (open the PNG files to look at them)"
exit "$CODE"
