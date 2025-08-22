#!/usr/bin/env bash
set -euo pipefail

# ===================== Config =====================
APP_NAME="OmniPull"
ENTRY="main.py"
ICON_PATH="icons/logo.icns"                  # .icns expected
TRANSLATIONS_DIR="modules/translations"      # folder with *.qm
BG_IMG="icons/logo4.png"                     # optional; PNG/JPG
BUNDLE_ID="com.omnipull.app"
VERSION="${VERSION:-1.0}"                    # set via env: VERSION=1.2.34 ./build-dmg-intel.sh

# Third-party binaries (local, Intel builds)
ARIA2C_SRC_REL="third_party/aria2c/aria2c"
FFMPEG_SRC_REL="third_party/ffmpeg/ffmpeg"

# Optional extra PyInstaller args
PYI_ARGS_EXTRA=()                            # e.g., PYI_ARGS_EXTRA+=(--hidden-import somepkg)

# Variant control (both by default). Use --variant bundled | lite to build one.
VARIANT_FILTER="${1:-}"                      # optional first arg

# ===================== Paths ======================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

DIST_DIR="$SCRIPT_DIR/dist"                  # pyinstaller output dir
DMG_OUT_DIR="$SCRIPT_DIR/dist"               # final dmgs here
BUILD_ROOT="$SCRIPT_DIR/.build-intel"        # temp workspace for assembling .app
mkdir -p "$BUILD_ROOT"

echo "Building on macOS $(sw_vers -productVersion) [$(uname -m)]"

# ===================== Pre-flight =================
command -v pyinstaller >/dev/null 2>&1 || { echo "pyinstaller not found. Install with: python3 -m pip install pyinstaller"; exit 1; }
command -v appdmg     >/dev/null 2>&1 || { echo "appdmg not found. Install with: npm install -g appdmg"; exit 1; }
command -v file       >/dev/null 2>&1 || true

[[ -f "$ENTRY" ]] || { echo "Entry script not found: $ENTRY"; exit 1; }
[[ -f "$ICON_PATH" ]] || { echo "Icon not found: $ICON_PATH (.icns)"; exit 1; }

# Check aria2c (required for both variants)
ARIA2C_SRC="$SCRIPT_DIR/$ARIA2C_SRC_REL"
if [[ ! -f "$ARIA2C_SRC" ]]; then
  echo "ERROR: $ARIA2C_SRC_REL not found. Put your Intel aria2c there (chmod +x)."
  exit 1
fi

# Check ffmpeg only if building the bundled variant
FFMPEG_SRC="$SCRIPT_DIR/$FFMPEG_SRC_REL"
WILL_BUILD_BUNDLED=true
WILL_BUILD_LITE=true
case "$VARIANT_FILTER" in
  "" ) ;;
  --variant)
    echo "Usage: $0 [--variant bundled|lite]"
    exit 1
    ;;
  bundled )
    WILL_BUILD_LITE=false
    ;;
  lite )
    WILL_BUILD_BUNDLED=false
    ;;
  --variant\ bundled )
    WILL_BUILD_LITE=false
    ;;
  --variant\ lite )
    WILL_BUILD_BUNDLED=false
    ;;
  * )
    # Support formats: --variant bundled / --variant lite passed as single arg
    if [[ "$VARIANT_FILTER" == "--variant" ]]; then
      shift || true
    fi
    ;;
esac

if $WILL_BUILD_BUNDLED && [[ ! -f "$FFMPEG_SRC" ]]; then
  echo "ERROR: $FFMPEG_SRC_REL not found, but Bundled variant requested."
  echo "       Place your Intel ffmpeg at that path (chmod +x), or run with: $0 lite"
  exit 1
fi

# Helpful info
if command -v file >/dev/null 2>&1; then
  echo "aria2c source:"
  file "$ARIA2C_SRC" || true
  if $WILL_BUILD_BUNDLED; then
    echo "ffmpeg source:"
    file "$FFMPEG_SRC" || true
  fi
fi

# ===================== Clean ======================
echo "==> Cleaning previous build outputs"
rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"
rm -rf "$BUILD_ROOT"
mkdir -p "$BUILD_ROOT"

# ===================== Build (PyInstaller) ========
echo "==> Building onefile binary with PyInstaller (Intel)"
# If you're on Apple Silicon and want Intel output locally:
#   arch -x86_64 bash -c './build-dmg-intel.sh'
pyinstaller "$ENTRY" \
  --noconfirm \
  --onefile \
  --windowed \
  --name "$APP_NAME" \
  --icon "$ICON_PATH" \
  --add-data "${TRANSLATIONS_DIR}:modules/translations" \
  ${PYI_ARGS_EXTRA[@]+"${PYI_ARGS_EXTRA[@]}"}

# Sanity
if [[ ! -f "$DIST_DIR/$APP_NAME" ]]; then
  echo "ERROR: PyInstaller did not produce $DIST_DIR/$APP_NAME"
  exit 1
fi

if command -v file >/dev/null 2>&1; then
  echo "Main executable info:"
  file "$DIST_DIR/$APP_NAME" || true
fi

# ===================== Function: assemble app =====
assemble_app() {
  local OUT_APP_DIR="$1"          # full path to OmniPull.app to create
  local BUNDLE_FFMPEG="$2"        # "true" or "false"

  echo "==> Assembling .app at: $OUT_APP_DIR (ffmpeg bundled: $BUNDLE_FFMPEG)"
  rm -rf "$OUT_APP_DIR"
  local MACOS_DIR="$OUT_APP_DIR/Contents/MacOS"
  local RES_DIR="$OUT_APP_DIR/Contents/Resources"
  local BIN_DIR="$RES_DIR/bin"
  mkdir -p "$MACOS_DIR" "$BIN_DIR"

  # Main binary + icon
  cp "$DIST_DIR/$APP_NAME" "$MACOS_DIR/$APP_NAME"
  chmod +x "$MACOS_DIR/$APP_NAME"
  cp "$ICON_PATH" "$RES_DIR/logo.icns"

  # Info.plist
  cat > "$OUT_APP_DIR/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>${APP_NAME}</string>
  <key>CFBundleDisplayName</key><string>${APP_NAME}</string>
  <key>CFBundleExecutable</key><string>${APP_NAME}</string>
  <key>CFBundleIdentifier</key><string>${BUNDLE_ID}</string>
  <key>CFBundleShortVersionString</key><string>${VERSION}</string>
  <key>CFBundleVersion</key><string>${VERSION}</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleIconFile</key><string>logo</string>
</dict>
</plist>
EOF

  # Always bundle aria2c
  cp "$ARIA2C_SRC" "$BIN_DIR/aria2c"
  chmod +x "$BIN_DIR/aria2c"

  # Optionally bundle ffmpeg
  if [[ "$BUNDLE_FFMPEG" == "true" ]]; then
    cp "$FFMPEG_SRC" "$BIN_DIR/ffmpeg"
    chmod +x "$BIN_DIR/ffmpeg"
  fi

  # Quick info
  if command -v file >/dev/null 2>&1; then
    echo "App binaries:"
    file "$MACOS_DIR/$APP_NAME" || true
    file "$BIN_DIR/aria2c" || true
    if [[ "$BUNDLE_FFMPEG" == "true" ]]; then
      file "$BIN_DIR/ffmpeg" || true
    fi
  fi
}

# ===================== Function: build dmg ========
build_dmg() {
  local APP_DIR_IN="$1"           # .app folder to package
  local DMG_OUT="$2"              # dmg path
  local TITLE="$3"                # volume title

  echo "==> Packaging DMG: $DMG_OUT"
  local STAGE_DIR
  STAGE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/omnipull-dmg-XXXX")"
  trap 'rm -rf "$STAGE_DIR"' RETURN
  cp -R "$APP_DIR_IN" "$STAGE_DIR/${APP_NAME}.app"

  # Minimal appdmg.json
  local APPDMG_JSON="$STAGE_DIR/appdmg.json"
  {
    echo '{'
    echo '  "title": "'"$TITLE"'",'
    echo '  "icon-size": 100,'
    if [[ -f "$BG_IMG" ]]; then
      cp "$BG_IMG" "$STAGE_DIR/$(basename "$BG_IMG")"
      echo '  "background": "'$(basename "$BG_IMG")'",'
    fi
    echo '  "window": { "size": { "width": 660, "height": 400 } },'
    echo '  "contents": ['
    echo '    { "x": 180, "y": 200, "type": "file", "path": "'${APP_NAME}'.app" },'
    echo '    { "x": 480, "y": 200, "type": "link", "path": "/Applications" }'
    echo '  ]'
    echo '}'
  } > "$APPDMG_JSON"

  mkdir -p "$(dirname "$DMG_OUT")"
  rm -f "$DMG_OUT"
  ( cd "$STAGE_DIR" && appdmg "$APPDMG_JSON" "$DMG_OUT" )
  echo "Created: $DMG_OUT"
}

# ===================== Build BOTH variants =========
# We re-use the PyInstaller binary and only vary the app Resources/bin contents.

if $WILL_BUILD_BUNDLED; then
  BUNDLED_APP="$BUILD_ROOT/${APP_NAME}-Bundled.app"
  assemble_app "$BUNDLED_APP" "true"
  build_dmg "$BUNDLED_APP" "$DMG_OUT_DIR/${APP_NAME}-Intel-Bundled.dmg" "${APP_NAME} (Intel Bundled)"
fi

if $WILL_BUILD_LITE; then
  LITE_APP="$BUILD_ROOT/${APP_NAME}-Lite.app"
  assemble_app "$LITE_APP" "false"
  build_dmg "$LITE_APP" "$DMG_OUT_DIR/${APP_NAME}-Intel-Lite.dmg" "${APP_NAME} (Intel Lite)"
fi

echo
echo "==> Done!"
echo "Artifacts:"
[[ -f "$DMG_OUT_DIR/${APP_NAME}-Intel-Bundled.dmg" ]] && echo "  $DMG_OUT_DIR/${APP_NAME}-Intel-Bundled.dmg"
[[ -f "$DMG_OUT_DIR/${APP_NAME}-Intel-Lite.dmg" ]]    && echo "  $DMG_OUT_DIR/${APP_NAME}-Intel-Lite.dmg"
echo
echo "Note: apps are unsigned. First run may require:"
echo "  xattr -dr com.apple.quarantine \"/Applications/${APP_NAME}.app\""
