#!/usr/bin/env bash
set -euo pipefail

# ===================== Config =====================
APP_NAME="OmniPull"
ENTRY="main.py"
ICON_PATH="icons/logo.icns"                  # .icns expected
TRANSLATIONS_DIR="modules/translations"      # folder with *.qm
BG_IMG="icons/logo4.png"                     # optional; PNG/JPG
BUNDLE_ID="com.omnipull.app"
VERSION="${VERSION:-1.0}"                    # export VERSION=1.2.34 ./build-dmg-intel.sh

# Third-party binaries (local, Intel builds)
ARIA2C_SRC_REL="third_party/aria2c/aria2c"
FFMPEG_SRC_REL="third_party/ffmpeg/ffmpeg"   # only used for Bundled

# Native messaging host assets (source locations in repo)
FIREFOX_MANIFEST_SRC_REL="browser_extensions/firefox/com.omnipull.downloader.json"
WATCHER_PY_SRC_REL="omnipull-watcher.py"     # lives next to main.py

# Optional extra PyInstaller args
PYI_ARGS_EXTRA=()                            # e.g., PYI_ARGS_EXTRA+=(--hidden-import somepkg)

# Variant control (both by default). Use: ./build-dmg-intel.sh bundled | lite
VARIANT_FILTER="${1:-}"

# Toggle DMG verification (mount and check root layout)
VERIFY_DMG="${VERIFY_DMG:-1}"

# ===== Edge (Chromium) connector config =====
# Set your published Edge extension ID here or export EDGE_EXTENSION_ID=... before running.
EDGE_EXTENSION_ID="djeefjpojiflemcgpibklkogmgooidmm"   # e.g. abcdefghijklmnopabcdefghijklmn

# ===================== Paths ======================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

DIST_DIR="$SCRIPT_DIR/dist"                  # pyinstaller output dir
DMG_OUT_DIR="$SCRIPT_DIR/dist"               # final dmgs here
BUILD_ROOT="$SCRIPT_DIR/.build-intel"        # temp workspace for assembling .app
mkdir -p "$BUILD_ROOT"

echo "Building on macOS $(sw_vers -productVersion) [$(uname -m)]"

# ===================== Pre-flight =================
command -v pyinstaller >/dev/null 2>&1 || { echo "pyinstaller not found. Install: python3 -m pip install pyinstaller"; exit 1; }
command -v appdmg     >/dev/null 2>&1 || { echo "appdmg not found. Install: npm install -g appdmg"; exit 1; }
command -v file       >/dev/null 2>&1 || true
command -v hdiutil    >/dev/null 2>&1 || { echo "hdiutil missing"; exit 1; }
command -v ditto      >/dev/null 2>&1 || { echo "ditto missing"; exit 1; }

[[ -f "$ENTRY"     ]] || { echo "Entry script not found: $ENTRY"; exit 1; }
[[ -f "$ICON_PATH" ]] || { echo "Icon not found: $ICON_PATH (.icns)"; exit 1; }

# aria2c required for both variants
ARIA2C_SRC="$SCRIPT_DIR/$ARIA2C_SRC_REL"
[[ -f "$ARIA2C_SRC" ]] || { echo "ERROR: $ARIA2C_SRC_REL missing (chmod +x)"; exit 1; }

# watcher + manifest template
WATCHER_PY_SRC="$SCRIPT_DIR/$WATCHER_PY_SRC_REL"
[[ -f "$WATCHER_PY_SRC" ]] || { echo "ERROR: $WATCHER_PY_SRC_REL not found (should be next to main.py)"; exit 1; }

FIREFOX_MANIFEST_SRC="$SCRIPT_DIR/$FIREFOX_MANIFEST_SRC_REL"
[[ -f "$FIREFOX_MANIFEST_SRC" ]] || { echo "ERROR: $FIREFOX_MANIFEST_SRC_REL not found"; exit 1; }

# ffmpeg only required when building Bundled
FFMPEG_SRC="$SCRIPT_DIR/$FFMPEG_SRC_REL"

WILL_BUILD_BUNDLED=true
WILL_BUILD_LITE=true
case "$VARIANT_FILTER" in
  "" ) ;;
  bundled ) WILL_BUILD_LITE=false ;;
  lite )    WILL_BUILD_BUNDLED=false ;;
  * ) echo "Usage: $0 [bundled|lite]"; exit 1;;
esac

if $WILL_BUILD_BUNDLED && [[ ! -f "$FFMPEG_SRC" ]]; then
  echo "ERROR: $FFMPEG_SRC_REL not found but Bundled requested. Provide ffmpeg or build 'lite'."
  exit 1
fi

if command -v file >/dev/null 2>&1; then
  echo "aria2c source:"; file "$ARIA2C_SRC" || true
  $WILL_BUILD_BUNDLED && { echo "ffmpeg source:"; file "$FFMPEG_SRC" || true; } || true
fi

# ===================== Clean ======================
echo "==> Cleaning previous build outputs"
rm -rf "$DIST_DIR"; mkdir -p "$DIST_DIR"
rm -rf "$BUILD_ROOT"; mkdir -p "$BUILD_ROOT"

# ===================== Build (PyInstaller) ========
echo "==> Building onefile with PyInstaller (Intel)"
pyinstaller "$ENTRY" \
  --noconfirm \
  --onefile \
  --windowed \
  --name "$APP_NAME" \
  --icon "$ICON_PATH" \
  --add-data "${TRANSLATIONS_DIR}:modules/translations" \
  ${PYI_ARGS_EXTRA[@]+"${PYI_ARGS_EXTRA[@]}"}

[[ -f "$DIST_DIR/$APP_NAME" ]] || { echo "ERROR: PyInstaller did not produce $DIST_DIR/$APP_NAME"; exit 1; }
command -v file >/dev/null 2>&1 && { echo "Main exec info:"; file "$DIST_DIR/$APP_NAME" || true; }

# ===================== Embed: Firefox connector ===
embed_firefox_connector_into() {
  local RES_DIR="$1"     # .../Contents/Resources
  local CONN_DIR="$RES_DIR/connector"
  mkdir -p "$CONN_DIR"

  # Python watcher (make sure LF endings)
  /usr/bin/ditto "$WATCHER_PY_SRC" "$CONN_DIR/omnipull-watcher.py"
  # Wrapper script that launches Python (robust against CRLF/shebang issues)
  cat > "$CONN_DIR/omnipull-watcher" <<'EOSH'
#!/usr/bin/env bash
set -euo pipefail
SELF="$(cd "$(dirname "$0")" && pwd)"
PY="$SELF/omnipull-watcher.py"
# Normalize CRLF -> LF (no-op if LF already)
if command -v perl >/dev/null 2>&1; then
  perl -i -pe 's/\r\n?/\n/g' "$PY"
else
  sed -i '' $'s/\r$//' "$PY" || true
fi
exec /usr/bin/env python3 "$PY"
EOSH

  chmod 755 "$CONN_DIR/omnipull-watcher"
  chmod 644 "$CONN_DIR/omnipull-watcher.py"

  # Copy manifest template for reference
  /usr/bin/ditto "$FIREFOX_MANIFEST_SRC" "$CONN_DIR/com.omnipull.downloader.template.json"
  chmod 644 "$CONN_DIR/com.omnipull.downloader.template.json"
}

# ===================== (Optional) Updater embed ===
write_updater_into() {
  local RES_DIR="$1"   # .../Contents/Resources
  local UPD_DIR="$RES_DIR/updater"
  mkdir -p "$UPD_DIR"
  # Placeholder
  echo "Updater placeholder" > "$UPD_DIR/README.txt"
  chmod 644 "$UPD_DIR/README.txt"
}

# ===================== App assembler ==============
assemble_app() {
  local OUT_APP_DIR="$1"          # full path to OmniPull.app to create
  local BUNDLE_FFMPEG="$2"        # "true" or "false"
  local VARIANT_MARK="$3"         # "Bundled" | "Lite"

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

  # Embed connector + (placeholder) updater + variant marker
  embed_firefox_connector_into "$RES_DIR"
  write_updater_into "$RES_DIR"
  echo "$VARIANT_MARK" > "$RES_DIR/.variant"
  chmod 644 "$RES_DIR/.variant"

  # Quick info
  command -v file >/dev/null 2>&1 && {
    echo "App binaries:"
    file "$MACOS_DIR/$APP_NAME" || true
    file "$BIN_DIR/aria2c" || true
    [[ "$BUNDLE_FFMPEG" == "true" ]] && file "$BIN_DIR/ffmpeg" || true
  }
}

# ===================== DMG builder =================
build_dmg() {
  local APP_DIR_IN="$1"           # .app folder to package
  local DMG_OUT="$2"              # dmg path
  local TITLE="$3"                # volume title

  echo "==> Packaging DMG: $DMG_OUT"
  local STAGE_DIR
  STAGE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/omnipull-dmg-XXXX")"
  trap 'rm -rf "$STAGE_DIR"' RETURN

  # Put app in staging (at ROOT)
  cp -R "$APP_DIR_IN" "$STAGE_DIR/${APP_NAME}.app"

  # ---------- Helpers on the DMG ----------
  # 1) Install app to ~/Applications (no sudo)
  cat > "$STAGE_DIR/Install to User Applications.command" <<'EOSH'
#!/usr/bin/env bash
set -euo pipefail
APP_NAME="OmniPull"
THIS_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC_APP="$THIS_DIR/${APP_NAME}.app"
DEST_DIR="$HOME/Applications"
DEST_APP="$DEST_DIR/${APP_NAME}.app"
mkdir -p "$DEST_DIR"
/usr/bin/ditto "$SRC_APP" "$DEST_APP"
xattr -dr com.apple.quarantine "$DEST_APP" || true
open "$DEST_APP"
echo "Installed to: $DEST_APP"
EOSH
  chmod 755 "$STAGE_DIR/Install to User Applications.command"

  # 2) Install Firefox Connector (User)
  cat > "$STAGE_DIR/Install Firefox Connector (User).command" <<'EOSH'
#!/usr/bin/env bash
set -euo pipefail
APP_NAME="OmniPull"

APP_SUPPORT="$HOME/Library/Application Support/$APP_NAME"
NATIVE_DIR="$HOME/Library/Application Support/Mozilla/NativeMessagingHosts"
MANIFEST="$NATIVE_DIR/com.omnipull.downloader.json"

THIS_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC_DIR="$THIS_DIR/${APP_NAME}.app/Contents/Resources/connector"

mkdir -p "$APP_SUPPORT" "$NATIVE_DIR"

/usr/bin/ditto "$SRC_DIR/omnipull-watcher"    "$APP_SUPPORT/omnipull-watcher"
/usr/bin/ditto "$SRC_DIR/omnipull-watcher.py" "$APP_SUPPORT/omnipull-watcher.py"

if command -v perl >/dev/null 2>&1; then
  perl -i -pe 's/\r\n?/\n/g' "$APP_SUPPORT/omnipull-watcher" "$APP_SUPPORT/omnipull-watcher.py"
else
  sed -i '' $'s/\r$//' "$APP_SUPPORT/omnipull-watcher" || true
  sed -i '' $'s/\r$//' "$APP_SUPPORT/omnipull-watcher.py" || true
fi

chmod 755 "$APP_SUPPORT/omnipull-watcher"
chmod 644 "$APP_SUPPORT/omnipull-watcher.py"
xattr -dr com.apple.quarantine "$APP_SUPPORT/omnipull-watcher" "$APP_SUPPORT/omnipull-watcher.py" 2>/dev/null || true

cat > "$MANIFEST" <<JSON
{
  "name": "com.omnipull.downloader",
  "description": "Native messaging host for OmniPull",
  "path": "$APP_SUPPORT/omnipull-watcher",
  "type": "stdio",
  "allowed_extensions": ["omnipull@annorion.dev"]
}
JSON

chmod 644 "$MANIFEST"
echo "User connector installed (Firefox):"
echo "  Watcher:  $APP_SUPPORT/omnipull-watcher"
echo "  Manifest: $MANIFEST"
EOSH
  chmod 755 "$STAGE_DIR/Install Firefox Connector (User).command"

  # 3) Install Firefox Connector (System) — optional (sudo)
  cat > "$STAGE_DIR/Install Firefox Connector (System).command" <<'EOSH'
#!/usr/bin/env bash
set -euo pipefail
APP_NAME="OmniPull"
SYS_NATIVE_DIR="/Library/Application Support/Mozilla/NativeMessagingHosts"
MANIFEST="$SYS_NATIVE_DIR/com.omnipull.downloader.json"

/usr/bin/osascript -e 'display dialog "This installs the Firefox connector for all users. You may be prompted for your password." buttons {"OK"} default button "OK" with icon note' >/dev/null 2>&1 || true

WATCHER_PATH="/Applications/${APP_NAME}.app/Contents/Resources/connector/omnipull-watcher"

sudo mkdir -p "$SYS_NATIVE_DIR"
sudo /bin/sh -c "cat > \"$MANIFEST\" <<JSON
{
  \"name\": \"com.omnipull.downloader\",
  \"description\": \"Native messaging host for OmniPull\",
  \"path\": \"$WATCHER_PATH\",
  \"type\": \"stdio\",
  \"allowed_extensions\": [\"omnipull@annorion.dev\"]
}
JSON"
sudo chmod 644 "$MANIFEST"

echo "System connector installed (Firefox):"
echo "  Manifest: $MANIFEST"
echo "IMPORTANT: Ensure ${WATCHER_PATH} exists (install the app to /Applications)."
EOSH
  chmod 755 "$STAGE_DIR/Install Firefox Connector (System).command"

  # 4) Install Edge Connector (User)
  cat > "$STAGE_DIR/Install Edge Connector (User).command" <<EOSH
#!/usr/bin/env bash
set -euo pipefail
APP_NAME="OmniPull"

NATIVE_DIR="\$HOME/Library/Application Support/Microsoft Edge/NativeMessagingHosts"
MANIFEST="\$NATIVE_DIR/com.omnipull.downloader.json"

THIS_DIR="\$(cd "\$(dirname "\$0")" && pwd)"
SRC_DIR="\$THIS_DIR/\${APP_NAME}.app/Contents/Resources/connector"

APP_SUPPORT="\$HOME/Library/Application Support/\$APP_NAME"
mkdir -p "\$APP_SUPPORT" "\$NATIVE_DIR"
/usr/bin/ditto "\$SRC_DIR/omnipull-watcher"    "\$APP_SUPPORT/omnipull-watcher"
/usr/bin/ditto "\$SRC_DIR/omnipull-watcher.py" "\$APP_SUPPORT/omnipull-watcher.py"

if command -v perl >/dev/null 2>&1; then
  perl -i -pe 's/\\r\\n?/\\n/g' "\$APP_SUPPORT/omnipull-watcher" "\$APP_SUPPORT/omnipull-watcher.py"
else
  sed -i '' \$'s/\\r$//' "\$APP_SUPPORT/omnipull-watcher" || true
  sed -i '' \$'s/\\r$//' "\$APP_SUPPORT/omnipull-watcher.py" || true
fi

chmod 755 "\$APP_SUPPORT/omnipull-watcher"
chmod 644 "\$APP_SUPPORT/omnipull-watcher.py"
xattr -dr com.apple.quarantine "\$APP_SUPPORT/omnipull-watcher" "\$APP_SUPPORT/omnipull-watcher.py" 2>/dev/null || true

EDGE_ID_PLACE="__YOUR_EDGE_EXTENSION_ID__"
EDGE_ID_INPUT="${EDGE_EXTENSION_ID:-$EDGE_ID_PLACE}"
if [[ "\$EDGE_ID_INPUT" == "\$EDGE_ID_PLACE" ]]; then
  echo "Enter your Microsoft Edge extension ID (from edge://extensions):"
  read -r EDGE_ID_INPUT
fi
if [[ -z "\${EDGE_ID_INPUT:-}" ]]; then
  echo "ERROR: Edge extension ID is required." >&2
  exit 1
fi

cat > "\$MANIFEST" <<JSON
{
  "name": "com.omnipull.downloader",
  "description": "Native messaging host for OmniPull",
  "path": "\$APP_SUPPORT/omnipull-watcher",
  "type": "stdio",
  "allowed_origins": [
    "chrome-extension://\$EDGE_ID_INPUT/"
  ]
}
JSON

chmod 644 "\$MANIFEST"
echo "User connector installed (Edge):"
echo "  Watcher : \$APP_SUPPORT/omnipull-watcher"
echo "  Manifest: \$MANIFEST"
echo "  Edge ID : \$EDGE_ID_INPUT"
EOSH
  chmod 755 "$STAGE_DIR/Install Edge Connector (User).command"

  # 5) Install Edge Connector (System) — optional (sudo)
  cat > "$STAGE_DIR/Install Edge Connector (System).command" <<EOSH
#!/usr/bin/env bash
set -euo pipefail
APP_NAME="OmniPull"

SYS_NATIVE_DIR="/Library/Application Support/Microsoft Edge/NativeMessagingHosts"
MANIFEST="\$SYS_NATIVE_DIR/com.omnipull.downloader.json"
WATCHER_PATH="/Applications/\${APP_NAME}.app/Contents/Resources/connector/omnipull-watcher"

/usr/bin/osascript -e 'display dialog "This installs the Microsoft Edge connector for all users. You may be prompted for your password." buttons {"OK"} default button "OK" with icon note' >/dev/null 2>&1 || true

EDGE_ID_PLACE="__YOUR_EDGE_EXTENSION_ID__"
EDGE_ID_INPUT="${EDGE_EXTENSION_ID:-$EDGE_ID_PLACE}"
if [[ "\$EDGE_ID_INPUT" == "\$EDGE_ID_PLACE" ]]; then
  echo "Enter your Microsoft Edge extension ID (from edge://extensions):"
  read -r EDGE_ID_INPUT
fi
if [[ -z "\${EDGE_ID_INPUT:-}" ]]; then
  echo "ERROR: Edge extension ID is required." >&2
  exit 1
fi

sudo mkdir -p "\$SYS_NATIVE_DIR"
sudo /bin/sh -c "cat > \"\$MANIFEST\" <<JSON
{
  \"name\": \"com.omnipull.downloader\",
  \"description\": \"Native messaging host for OmniPull\",
  \"path\": \"\$WATCHER_PATH\",
  \"type\": \"stdio\",
  \"allowed_origins\": [
    \"chrome-extension://\$EDGE_ID_INPUT/\"
  ]
}
JSON"
sudo chmod 644 "\$MANIFEST"

echo "System connector installed (Edge):"
echo "  Manifest: \$MANIFEST"
echo "  Watcher : \$WATCHER_PATH"
echo "IMPORTANT: Ensure \${APP_NAME}.app is installed in /Applications."
EOSH
  chmod 755 "$STAGE_DIR/Install Edge Connector (System).command"
  # ---------- end helpers ----------

  # appdmg.json layout
  local APPDMG_JSON="$STAGE_DIR/appdmg.json"
  {
    echo '{'
    echo '  "title": "'"$TITLE"'",'
    echo '  "icon-size": 100,'
    if [[ -f "$BG_IMG" ]]; then
      cp "$BG_IMG" "$STAGE_DIR/$(basename "$BG_IMG")"
      echo '  "background": "'$(basename "$BG_IMG")'",'
    fi
    echo '  "window": { "size": { "width": 720, "height": 520 } },'
    echo '  "contents": ['
    echo '    { "x": 160, "y": 180, "type": "file", "path": "'${APP_NAME}'.app" },'
    echo '    { "x": 480, "y": 180, "type": "link", "path": "/Applications" },'
    echo '    { "x": 160, "y": 320, "type": "file", "path": "Install to User Applications.command" },'
    echo '    { "x": 480, "y": 320, "type": "file", "path": "Install Firefox Connector (User).command" },'
    echo '    { "x": 160, "y": 420, "type": "file", "path": "Install Edge Connector (User).command" },'
    echo '    { "x": 480, "y": 420, "type": "file", "path": "Install Edge Connector (System).command" }'
    echo '  ]'
    echo '}'
  } > "$APPDMG_JSON"

  mkdir -p "$(dirname "$DMG_OUT")"
  rm -f "$DMG_OUT"
  ( cd "$STAGE_DIR" && appdmg "$APPDMG_JSON" "$DMG_OUT" )
  echo "Created: $DMG_OUT"

  # Optional verification (non-fatal)
  if [[ "$VERIFY_DMG" == "1" ]]; then
    echo "==> Verifying DMG root layout"
    sleep 1
    TMP_MNT="$(mktemp -d "${TMPDIR:-/tmp}/omnipull-verify-XXXX")"
    mounted=false
    for i in 1 2 3 4 5 6; do
      if hdiutil attach "$DMG_OUT" -readonly -noverify -noautoopen -nobrowse -mountpoint "$TMP_MNT" -quiet; then
        mounted=true; break
      fi
      sleep "$i"
    done
    if "$mounted"; then
      if [[ -d "$TMP_MNT/${APP_NAME}.app" ]]; then
        echo "Verification OK: ${APP_NAME}.app at DMG root."
      else
        echo "WARNING: ${APP_NAME}.app NOT found at DMG root ($TMP_MNT)."
      fi
      hdiutil detach "$TMP_MNT" -quiet || hdiutil detach "$TMP_MNT" -force -quiet || true
    else
      echo "WARNING: Could not mount DMG for verification. Skipping."
    fi
    rmdir "$TMP_MNT" 2>/dev/null || true
  else
    echo "==> Skipping DMG verification (VERIFY_DMG=0)"
  fi
}

# ===================== Build variants ==============
if $WILL_BUILD_BUNDLED; then
  BUNDLED_APP="$BUILD_ROOT/${APP_NAME}-Bundled.app"
  assemble_app "$BUNDLED_APP" "true"  "Bundled"
  build_dmg    "$BUNDLED_APP" "$DMG_OUT_DIR/${APP_NAME}-Intel-Bundled.dmg" "${APP_NAME} (Intel Bundled)"
fi

if $WILL_BUILD_LITE; then
  LITE_APP="$BUILD_ROOT/${APP_NAME}-Lite.app"
  assemble_app "$LITE_APP" "false" "Lite"
  build_dmg    "$LITE_APP" "$DMG_OUT_DIR/${APP_NAME}-Intel-Lite.dmg" "${APP_NAME} (Intel Lite)"
fi

echo
echo "==> Done!"
echo "Artifacts:"
[[ -f "$DMG_OUT_DIR/${APP_NAME}-Intel-Bundled.dmg" ]] && echo "  $DMG_OUT_DIR/${APP_NAME}-Intel-Bundled.dmg"
[[ -f "$DMG_OUT_DIR/${APP_NAME}-Intel-Lite.dmg"    ]] && echo "  $DMG_OUT_DIR/${APP_NAME}-Intel-Lite.dmg"
echo
echo "Note: apps are unsigned. First run may require:"
echo "  xattr -dr com.apple.quarantine \"~/Applications/${APP_NAME}.app\""
