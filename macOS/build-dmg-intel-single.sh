#!/usr/bin/env bash
set -euo pipefail

# ===================== Config =====================
APP_NAME="OmniPull"
ENTRY="main.py"
ICON_PATH="icons/logo.icns"                  # .icns expected
TRANSLATIONS_DIR="modules/translations"      # folder with *.qm
BG_IMG="icons/logo4.png"                     # optional; PNG/JPG
BUNDLE_ID="com.omnipull.app"
VERSION="${VERSION:-2.0.0}"                    # usage: VERSION=2.0.0 ./build-dmg-intel.sh

# Native messaging host assets (source locations in repo)
FIREFOX_MANIFEST_SRC_REL="browser_extensions/firefox/com.omnipull.downloader.json"
WATCHER_PY_SRC_REL="omnipull-watcher.py"     # lives next to main.py

# Optional extra PyInstaller args
PYI_ARGS_EXTRA=()                            # e.g., PYI_ARGS_EXTRA+=(--hidden-import somepkg)

# ===== Edge (Chromium) connector config =====
# Set your published Edge extension ID here or export EDGE_EXTENSION_ID=... before running.
EDGE_EXTENSION_ID="${EDGE_EXTENSION_ID:-mkhncokjlhefbbnjlgmnifmgejdclbhj}"

# ===================== Paths ======================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

DIST_DIR="$SCRIPT_DIR/dist"                  # pyinstaller output dir
DMG_OUT_DIR="$SCRIPT_DIR/dist"               # final dmgs here
BUILD_ROOT="$SCRIPT_DIR/.build-intel"        # temp workspace for assembling .app

mkdir -p "$BUILD_ROOT" "$DIST_DIR"

echo "Building on macOS $(sw_vers -productVersion) [$(uname -m)]"

# ===================== Pre-flight =================
command -v pyinstaller >/dev/null 2>&1 || { echo "pyinstaller not found. Install: python3 -m pip install pyinstaller"; exit 1; }
command -v appdmg     >/dev/null 2>&1 || { echo "appdmg not found. Install: npm install -g appdmg"; exit 1; }
command -v hdiutil    >/dev/null 2>&1 || { echo "hdiutil missing"; exit 1; }
command -v ditto      >/dev/null 2>&1 || { echo "ditto missing"; exit 1; }
command -v file       >/dev/null 2>&1 || true

[[ -f "$ENTRY"     ]] || { echo "Entry script not found: $ENTRY"; exit 1; }
[[ -f "$ICON_PATH" ]] || { echo "Icon not found: $ICON_PATH (.icns)"; exit 1; }

# watcher + manifest template
WATCHER_PY_SRC="$SCRIPT_DIR/$WATCHER_PY_SRC_REL"
[[ -f "$WATCHER_PY_SRC" ]] || { echo "ERROR: $WATCHER_PY_SRC_REL not found (should be next to main.py)"; exit 1; }

FIREFOX_MANIFEST_SRC="$SCRIPT_DIR/$FIREFOX_MANIFEST_SRC_REL"
[[ -f "$FIREFOX_MANIFEST_SRC" ]] || { echo "ERROR: $FIREFOX_MANIFEST_SRC_REL not found"; exit 1; }

# ===================== Clean ======================
echo "==> Cleaning previous build outputs"
rm -rf "$DIST_DIR"/* "$BUILD_ROOT"/*
mkdir -p "$DIST_DIR" "$BUILD_ROOT"

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

  # Python watcher (normalize line endings)
  /usr/bin/ditto "$WATCHER_PY_SRC" "$CONN_DIR/omnipull-watcher.py"
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

# ===================== App assembler ==============
assemble_app() {
  local OUT_APP_DIR="$1"          # full path to OmniPull.app to create

  echo "==> Assembling .app at: $OUT_APP_DIR"
  rm -rf "$OUT_APP_DIR"
  local MACOS_DIR="$OUT_APP_DIR/Contents/MacOS"
  local RES_DIR="$OUT_APP_DIR/Contents/Resources"
  mkdir -p "$MACOS_DIR" "$RES_DIR"

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

  # Embed connector (no third‑party binaries bundled)
  embed_firefox_connector_into "$RES_DIR"

  # Quick info
  command -v file >/dev/null 2>&1 && {
    echo "App binary:"
    file "$MACOS_DIR/$APP_NAME" || true
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
  "allowed_extensions": ["{e899b50f-2a29-4bad-ab4d-b192447a10d0}"]
}
JSON

chmod 644 "$MANIFEST"
echo "User connector installed (Firefox):"
echo "  Watcher:  $APP_SUPPORT/omnipull-watcher"
echo "  Manifest: $MANIFEST"
EOSH
  chmod 755 "$STAGE_DIR/Install Firefox Connector (User).command"

  # 3) Install Edge Connector (User) — single helper (removed System variant)
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

EDGE_ID_INPUT="${EDGE_EXTENSION_ID}"
if [[ -z "\${EDGE_ID_INPUT:-}" ]]; then
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
    echo '    { "x": 320, "y": 420, "type": "file", "path": "Install Edge Connector (User).command" }'
    echo '  ]'
    echo '}'
  } > "$APPDMG_JSON"

  mkdir -p "$(dirname "$DMG_OUT")"
  rm -f "$DMG_OUT"
  ( cd "$STAGE_DIR" && appdmg "$APPDMG_JSON" "$DMG_OUT" )
  echo "Created: $DMG_OUT"

  # Optional verification (non-fatal)
  if command -v hdiutil >/dev/null 2>&1; then
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
  fi
}

# ===================== Single Intel build ==========
APP_DIR="$BUILD_ROOT/${APP_NAME}.app"
assemble_app "$APP_DIR"

DMG_PATH="$DMG_OUT_DIR/omnipull-intel-${VERSION}.dmg"
build_dmg "$APP_DIR" "$DMG_PATH" "${APP_NAME} (Intel)"

echo
echo "==> Done!"
echo "Artifact:"
echo "  $DMG_PATH"
echo
echo "Note: app is unsigned. First run may require:"
echo "  xattr -dr com.apple.quarantine \"~/Applications/${APP_NAME}.app\""
