#!/usr/bin/env bash
#
# Build Centwise Final Project.app.
#
#   ./build-app.sh                    full build, leaves the app in release/
#   ./build-app.sh --install          full build, then install into /Applications
#   ./build-app.sh --fast --install   frontend-only rebuild (reuses the frozen backend)
#
# Stages: 1) draw the icon  2) freeze the Python backend  3) build the React
# page  4) electron-builder wraps it all into a .app.
# Use the full build whenever anything under backend/ changed.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
ASSETS="$ROOT/assets"
APP_NAME="Centwise Final Project.app"

# electron-builder rejects output paths with shell-special characters, and the
# project folder may contain an apostrophe — so build in a clean staging folder
# and copy the finished bundle back into release/.
STAGE="$HOME/Library/Caches/centwise-final-project-build"
STAGED_APP="$STAGE/mac-arm64/$APP_NAME"
BUILT_APP="$ROOT/release/$APP_NAME"
FROZEN="$BACKEND/dist/centwise-final-project-backend/centwise-final-project-backend"

INSTALL=0
FAST=0
for arg in "$@"; do
  case "$arg" in
    --install) INSTALL=1 ;;
    --fast|--frontend-only) FAST=1 ;;
    -h|--help) sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $arg (try --help)" >&2; exit 2 ;;
  esac
done

[[ -x "$BACKEND/.venv/bin/python" ]] || { echo "ERROR: backend/.venv is missing. Run ./setup.sh first." >&2; exit 1; }

# ------------------------------------------------------------------- icon --
if [[ $FAST -eq 1 ]]; then
  echo "--> [1/4] Icon — skipped (--fast)"
else
  echo "--> [1/4] Icon"
  ICON_PY=""
  for candidate in python3 /opt/anaconda3/bin/python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import PIL' 2>/dev/null; then ICON_PY="$candidate"; break; fi
  done
  if [[ -n "$ICON_PY" ]]; then
    "$ICON_PY" "$ASSETS/make_icon.py" "$ASSETS/icon-1024.png"
    rm -rf "$ASSETS/icon.iconset" && mkdir -p "$ASSETS/icon.iconset"
    for size in 16 32 128 256 512; do
      sips -z $size $size "$ASSETS/icon-1024.png" --out "$ASSETS/icon.iconset/icon_${size}x${size}.png" >/dev/null
      double=$((size * 2))
      sips -z $double $double "$ASSETS/icon-1024.png" --out "$ASSETS/icon.iconset/icon_${size}x${size}@2x.png" >/dev/null
    done
    iconutil -c icns "$ASSETS/icon.iconset" -o "$ASSETS/icon.icns"
    rm -rf "$ASSETS/icon.iconset"
  elif [[ ! -f "$ASSETS/icon.icns" ]]; then
    echo "ERROR: Pillow is not available and assets/icon.icns does not exist yet." >&2; exit 1
  else
    echo "    Pillow not available — keeping the existing assets/icon.icns"
  fi
fi

# ---------------------------------------------------------------- backend --
if [[ $FAST -eq 1 ]]; then
  echo "--> [2/4] Python backend — reusing the existing freeze (--fast)"
  [[ -x "$FROZEN" ]] || { echo "ERROR: no frozen backend at $FROZEN — run once without --fast." >&2; exit 1; }
else
  echo "--> [2/4] Freezing the Python backend"
  "$BACKEND/.venv/bin/python" -c 'import PyInstaller' 2>/dev/null || "$BACKEND/.venv/bin/pip" install --quiet pyinstaller
  (cd "$BACKEND" && .venv/bin/pyinstaller centwise.spec --noconfirm --log-level ERROR 2>&1 | grep -v 'conda-meta' || true)
  [[ -x "$FROZEN" ]] || { echo "ERROR: the frozen backend was not produced." >&2; exit 1; }
fi

# --------------------------------------------------------------- frontend --
echo "--> [3/4] Building the page"
(cd "$FRONTEND" && npm run build --silent)

# -------------------------------------------------------------------- app --
echo "--> [4/4] Packaging the app"
rm -rf "$STAGE"
(cd "$FRONTEND" && npx --no-install electron-builder --mac --arm64 --config.directories.output="$STAGE")
[[ -d "$STAGED_APP" ]] || { echo "ERROR: expected the bundle at $STAGED_APP" >&2; exit 1; }

mkdir -p "$ROOT/release"
rm -rf "$BUILT_APP"
cp -R "$STAGED_APP" "$BUILT_APP"
rm -rf "$STAGE"
echo
echo "==> Built: $BUILT_APP  ($(du -sh "$BUILT_APP" | cut -f1))"

if [[ $INSTALL -eq 1 ]]; then
  # Replacing a bundle while it runs can corrupt the copy — quit it first.
  WAS_RUNNING=0
  if pgrep -f "/Applications/$APP_NAME/Contents/MacOS" >/dev/null 2>&1; then
    WAS_RUNNING=1
    echo "--> Quitting the running app"
    osascript -e 'quit app "Centwise Final Project"' 2>/dev/null || true
    for _ in $(seq 1 10); do
      pgrep -f "/Applications/$APP_NAME/Contents/MacOS" >/dev/null 2>&1 || break
      sleep 0.5
    done
    pkill -f "centwise-final-project-backend" 2>/dev/null || true
  fi
  echo "--> Installing to /Applications"
  rm -rf "/Applications/$APP_NAME"
  cp -R "$BUILT_APP" "/Applications/$APP_NAME"
  echo "==> Installed."
  # First install: start with the sample data. Never overwrites existing data.
  DATA="$HOME/Library/Application Support/Centwise Final Project"
  if [[ ! -f "$DATA/data.json" && -f "$ROOT/sample-data/data.json" ]]; then
    echo "--> First install: copying the sample data into the app's data folder"
    mkdir -p "$DATA"
    cp -R "$ROOT/sample-data/." "$DATA/"
  fi
  if [[ $WAS_RUNNING -eq 1 ]]; then open "/Applications/$APP_NAME"; fi
else
  echo "    To install:  ./build-app.sh --install"
fi

cat <<'MSG'

    Your data is untouched and lives outside the app:
      ~/Library/Application Support/Centwise Final Project/

MSG
