#!/usr/bin/env bash
set -euo pipefail

# ============ Config ============
APP_NAME="OmniPull"
ENTRY="main.py"
ICON_PATH="icons/logo.icns"                      # .icns expected
TRANSLATIONS_DIR="modules/translations"          # folder with *.qm
BG_IMG="icons/logo4.png"                         # optional; PNG/JPG
BUNDLE_ID="com.omnipull.app"

# Optional extra PyInstaller args (hidden imports, hooks, etc.)
PYI_ARGS_EXTRA=()  # e.g., PYI_ARGS_EXTRA+=(--hidden-import somepkg)

# Optional version stamp: export VERSION=1.2.24 or pass inline: VERSION=1.2.24 ./build-dmg.sh
VERSION="${VERSION:-1.0}"

# third-party aria2c (Intel offline build)
ARIA2C_SRC_REL="third_party/aria2c/aria2c"       # <-- your local binary path (Intel)
# =============================================

# ============ Paths ============
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

DIST_DIR="$SCRIPT_DIR/dist"
APP_DIR="$DIST_DIR/${APP_NAME}.app"
MACOS_DIR="$APP_DIR/Contents/MacOS"
RES_DIR="$APP_DIR/Contents/Resources"
BIN_DIR="$RES_DIR/bin"
DMG_PATH="$DIST_DIR/${APP_NAME}.dmg"

echo "Building on: $(sw_vers -productVersion) ($(uname -m))"

# ============ Checks ============
command -v pyinstaller >/dev/null 2>&1 || { echo "pyinstaller not found. Install with: python3 -m pip install pyinstaller"; exit 1; }
command -v appdmg >/dev/null 2>&1 || { echo "appdmg not found. Install with: npm install -g appdmg"; exit 1; }

[[ -f "$ENTRY" ]] || { echo "Entry script not found: $ENTRY"; exit 1; }
[[ -f "$ICON_PATH" ]] || { echo "Icon not found: $ICON_PATH (expected .icns)"; exit 1; }

# aria2c (Intel) presence check
ARIA2C_SRC="$SCRIPT_DIR/$ARIA2C_SRC_REL"
if [[ ! -f "$ARIA2C_SRC" ]]; then
  echo "ERROR: $ARIA2C_SRC_REL not found. Put your Intel aria2c at that path (chmod +x)."
  exit 1
fi
if command -v file >/dev/null 2>&1; then
  echo "aria2c source info:"
  file "$ARIA2C_SRC" || true
fi

# ============ Clean old build ============
echo "==> Cleaning previous build outputs"
rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

# ============ Build with PyInstaller ============
echo "==> Building onefile binary with PyInstaller"
# On Apple Silicon targeting Intel, run via: arch -x86_64 bash -c './build-dmg.sh'
pyinstaller "$ENTRY" \
  --noconfirm \
  --onefile \
  --windowed \
  --name "$APP_NAME" \
  --icon "$ICON_PATH" \
  --add-data "${TRANSLATIONS_DIR}:modules/translations" \
  ${PYI_ARGS_EXTRA[@]+"${PYI_ARGS_EXTRA[@]}"}

# ============ Assemble .app bundle ============
echo "==> Creating .app bundle"
rm -rf "$APP_DIR"
mkdir -p "$MACOS_DIR" "$RES_DIR" "$BIN_DIR"

cp "$DIST_DIR/$APP_NAME" "$MACOS_DIR/$APP_NAME"
chmod +x "$MACOS_DIR/$APP_NAME"
cp "$ICON_PATH" "$RES_DIR/logo.icns"

# Bundle aria2c into Resources/bin (don't preserve xattrs)
cp "$ARIA2C_SRC" "$BIN_DIR/aria2c"
chmod +x "$BIN_DIR/aria2c"

# Write Info.plist
cat > "$APP_DIR/Contents/Info.plist" <<EOF
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

echo "==> Verifying bundle layout"
ls -R "$APP_DIR"
if command -v file >/dev/null 2>&1; then
  echo "Main exec info:"
  file "$MACOS_DIR/$APP_NAME" || true
  echo "aria2c info:"
  file "$BIN_DIR/aria2c" || true
fi

# ============ Stage for appdmg ============
STAGE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/omnipull-dmg-XXXX")"
trap 'rm -rf "$STAGE_DIR"' EXIT
cp -R "$APP_DIR" "$STAGE_DIR/${APP_NAME}.app"

# Create appdmg.json dynamically (uses background if present)
APPDMG_JSON="$STAGE_DIR/appdmg.json"
echo "==> Creating appdmg.json"
{
  echo '{'
  echo '  "title": "'"$APP_NAME"'",'
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

# ============ Build DMG ============
echo "==> Building DMG"
rm -f "$DMG_PATH"
( cd "$STAGE_DIR" && appdmg "$APPDMG_JSON" "$DMG_PATH" )

echo "==> Done!"
echo "DMG created at: $DMG_PATH"
echo
echo "Note: app is unsigned. On first run you may need:"
echo "  xattr -dr com.apple.quarantine \"/Applications/${APP_NAME}.app\""
