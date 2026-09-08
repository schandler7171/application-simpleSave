#!/usr/bin/env bash
# build_mac.sh — produce simpleSave.app and simpleSave.dmg.
#
# Run on macOS only. PyInstaller doesn't cross-compile.
#
# Outputs:
#   dist/simpleSave.app   — double-clickable app bundle
#   dist/simpleSave.dmg   — drag-to-Applications installer
#
# Prereqs (script installs what's missing where possible):
#   - macOS 11+
#   - Python 3.11+ on PATH
#   - Xcode Command Line Tools (for iconutil): xcode-select --install
#   - Homebrew (optional; needed only for create-dmg)
#
# Usage:
#   ./scripts/build_mac.sh

set -euo pipefail

# ---- locate project root ----------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

APP_NAME="simpleSave"
DIST="$ROOT/dist"
BUILD="$ROOT/build"

echo "==> Project root: $ROOT"

# ---- sanity ---------------------------------------------------------------
if [[ "$(uname)" != "Darwin" ]]; then
  echo "ERROR: this script must run on macOS." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found on PATH." >&2
  exit 1
fi

# ---- fonts (best-effort) --------------------------------------------------
# Install Work Sans + Space Mono via Homebrew Cask if available. The app
# falls back to system fonts gracefully if these aren't installed.
if command -v brew >/dev/null 2>&1; then
  echo "==> Ensuring fonts are installed (Work Sans, Space Mono)"
  brew tap homebrew/cask-fonts >/dev/null 2>&1 || true
  for cask in font-work-sans font-space-mono; do
    if brew list --cask "$cask" >/dev/null 2>&1; then
      :  # already installed
    else
      brew install --cask "$cask" >/dev/null 2>&1 || \
        echo "    (couldn't install $cask — app will fall back to system fonts)"
    fi
  done
else
  echo "==> Homebrew not found — skipping font install."
  echo "    To get the intended look: brew install --cask font-work-sans font-space-mono"
fi

# ---- venv + deps ----------------------------------------------------------
if [[ ! -d ".venv" ]]; then
  echo "==> Creating virtualenv (.venv)"
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
echo "==> Installing app + build dependencies"
pip install -r requirements.txt
pip install "pyinstaller>=6.4"

# ---- icon: png -> icns ----------------------------------------------------
ICON_PNG="$ROOT/assets/icon.png"
ICON_ICNS="$ROOT/assets/icon.icns"

if [[ -f "$ICON_PNG" ]]; then
  if [[ ! -f "$ICON_ICNS" ]] || [[ "$ICON_PNG" -nt "$ICON_ICNS" ]]; then
    echo "==> Generating $ICON_ICNS from $ICON_PNG"
    ICONSET="$(mktemp -d)/icon.iconset"
    mkdir -p "$ICONSET"
    for SZ in 16 32 64 128 256 512; do
      sips -z $SZ $SZ "$ICON_PNG" --out "$ICONSET/icon_${SZ}x${SZ}.png" >/dev/null
      DOUBLE=$((SZ * 2))
      sips -z $DOUBLE $DOUBLE "$ICON_PNG" --out "$ICONSET/icon_${SZ}x${SZ}@2x.png" >/dev/null
    done
    sips -z 1024 1024 "$ICON_PNG" --out "$ICONSET/icon_512x512@2x.png" >/dev/null
    if command -v iconutil >/dev/null 2>&1; then
      iconutil -c icns "$ICONSET" -o "$ICON_ICNS"
    else
      echo "WARN: iconutil not found (install Xcode Command Line Tools). Skipping .icns."
    fi
  fi
else
  echo "==> No assets/icon.png found — app will use macOS default icon."
fi

# ---- PyInstaller ----------------------------------------------------------
echo "==> Cleaning previous build artifacts"
rm -rf "$BUILD" "$DIST"

echo "==> Running PyInstaller"
pyinstaller simplesave.spec --noconfirm --clean

APP_PATH="$DIST/$APP_NAME.app"
if [[ ! -d "$APP_PATH" ]]; then
  echo "ERROR: expected $APP_PATH but it wasn't built." >&2
  exit 1
fi
echo "==> Built $APP_PATH"

# ---- ad-hoc codesign so Gatekeeper at least recognizes the bundle --------
# (Not a Developer ID signature. Users still see the unidentified-developer
# warning on first launch and need to right-click → Open. Real signing
# requires an Apple Developer Program account.)
echo "==> Ad-hoc signing $APP_PATH"
codesign --force --deep --sign - "$APP_PATH" || \
  echo "WARN: codesign failed; app will still run."

# ---- DMG ------------------------------------------------------------------
DMG_PATH="$DIST/$APP_NAME.dmg"
rm -f "$DMG_PATH"

build_dmg_with_hdiutil() {
  echo "==> Building DMG with hdiutil"
  local STAGE
  STAGE="$(mktemp -d)/dmg-stage"
  mkdir -p "$STAGE"
  cp -R "$APP_PATH" "$STAGE/"
  ln -s /Applications "$STAGE/Applications"
  hdiutil create \
    -volname "$APP_NAME" \
    -srcfolder "$STAGE" \
    -ov \
    -format UDZO \
    "$DMG_PATH"
}

DMG_BUILT=0

if command -v create-dmg >/dev/null 2>&1; then
  echo "==> Building DMG with create-dmg"
  # Don't let create-dmg's non-zero exit (it sometimes returns 2 even on
  # success when AppleScript window positioning has a hiccup) kill the build.
  set +e
  create-dmg \
    --volname "$APP_NAME" \
    --window-pos 200 120 \
    --window-size 600 360 \
    --icon-size 96 \
    --icon "$APP_NAME.app" 160 200 \
    --hide-extension "$APP_NAME.app" \
    --app-drop-link 440 200 \
    --no-internet-enable \
    "$DMG_PATH" \
    "$APP_PATH"
  CREATE_DMG_EXIT=$?
  set -e

  if [[ -f "$DMG_PATH" ]]; then
    DMG_BUILT=1
    echo "==> create-dmg finished (exit $CREATE_DMG_EXIT), DMG present."
  else
    echo "WARN: create-dmg did not produce $DMG_PATH (exit $CREATE_DMG_EXIT)."
    echo "      Falling back to hdiutil."
  fi
fi

if [[ $DMG_BUILT -eq 0 ]]; then
  build_dmg_with_hdiutil
fi

if [[ ! -f "$DMG_PATH" ]]; then
  echo "ERROR: failed to produce $DMG_PATH" >&2
  exit 1
fi

echo
echo "==> Done."
echo "    App:  $APP_PATH"
echo "    DMG:  $DMG_PATH"
echo
echo "Install:"
echo "  1. Open dist/$APP_NAME.dmg"
echo "  2. Drag $APP_NAME.app to Applications"
echo "  3. First launch: right-click the app -> Open -> Open (Gatekeeper warning)"
