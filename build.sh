#!/usr/bin/env bash
# AC Career GT Edition — Linux AppImage build script
#
# Requirements:
#   - Python 3.12 venv with all dependencies (run start.sh once to create it)
#   - appimagetool in PATH, or set APPIMAGETOOL=/path/to/appimagetool-x86_64.AppImage
#     Download: https://github.com/AppImage/AppImageKit/releases
#
# Usage:
#   bash build.sh
#
# Output:
#   dist/AC_Career_GT_Edition-<VERSION>-x86_64.AppImage  (VERSION defaults to 1.16.0)

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="AC_Career_GT_Edition"
VERSION="${VERSION:-1.16.0}"   # can be overridden by CI: export VERSION=1.17.0
APPDIR="$SCRIPT_DIR/AppDir"
APPIMAGETOOL="${APPIMAGETOOL:-appimagetool}"

echo ""
echo "  =========================================="
echo "    AC CAREER GT EDITION — Linux AppImage"
echo "    Building v${VERSION}"
echo "  =========================================="
echo ""

# --- 0. Check prerequisites ---
command -v "$APPIMAGETOOL" &>/dev/null || {
    echo "  [ERROR] appimagetool not found."
    echo "  Download from: https://github.com/AppImage/AppImageKit/releases"
    echo "  Then: chmod +x appimagetool-x86_64.AppImage"
    echo "  And either: export APPIMAGETOOL=./appimagetool-x86_64.AppImage"
    echo "           or: mv appimagetool-x86_64.AppImage /usr/local/bin/appimagetool"
    exit 1
}

# Use venv if available; fall back to system Python (CI environment)
if [ -f "venv/bin/pyinstaller" ]; then
    PYINSTALLER="venv/bin/pyinstaller"
elif command -v pyinstaller &>/dev/null; then
    PYINSTALLER="pyinstaller"
else
    echo "  [ERROR] pyinstaller not found. Run 'bash start.sh' or 'pip install pyinstaller'."
    exit 1
fi

# --- 1. Clean old artifacts ---
echo "  [1/5] Cleaning old build artifacts..."
rm -rf dist build AppDir "${APP_NAME}.spec"

# --- 2. PyInstaller (onedir — AppImage wraps the directory) ---
# NOTE: --add-data separator is ':' on Linux (not ';' like Windows)
echo "  [2/5] Running PyInstaller..."
"$PYINSTALLER" \
    --onedir \
    --windowed \
    --name "$APP_NAME" \
    --add-data "templates:templates" \
    --add-data "static:static" \
    --add-data "config.json:." \
    --add-data "platform_paths.py:." \
    --collect-all flask \
    --collect-all flask_cors \
    --collect-all webview \
    app.py

# --- 3. Build AppDir structure ---
echo "  [3/5] Building AppDir..."
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$APPDIR/usr/share/applications"

# Copy PyInstaller bundle into AppDir/usr/bin/
cp -r "dist/$APP_NAME/"* "$APPDIR/usr/bin/"

# Icon — use SVG (appimagetool accepts SVG since AppImageKit 13)
cp "static/logo.svg" "$APPDIR/ac-career.svg"
cp "static/logo.svg" "$APPDIR/usr/share/icons/hicolor/256x256/apps/ac-career.svg"

# .desktop file (at AppDir root, required by appimagetool)
cat > "$APPDIR/ac-career.desktop" <<'EOF'
[Desktop Entry]
Version=1.0
Name=AC Career GT Edition
Comment=Professional Racing Career Simulator for Assetto Corsa (Steam Proton)
Exec=AC_Career_GT_Edition
Icon=ac-career
Type=Application
Categories=Game;Simulation;
Keywords=assetto corsa;racing;career;simulator;proton;steam;
StartupWMClass=AC_Career_GT_Edition
EOF

cp "$APPDIR/ac-career.desktop" "$APPDIR/usr/share/applications/"

# AppRun — sets PATH and launches the binary
cat > "$APPDIR/AppRun" <<'EOF'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="$HERE/usr/bin:$PATH"
exec "$HERE/usr/bin/AC_Career_GT_Edition" "$@"
EOF
chmod +x "$APPDIR/AppRun"

# --- 4. Package as AppImage ---
echo "  [4/5] Packaging AppImage..."
mkdir -p dist
ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "dist/${APP_NAME}-${VERSION}-x86_64.AppImage"

# --- 5. Done ---
echo ""
echo "  [5/5] Done!"
echo "  Output: dist/${APP_NAME}-${VERSION}-x86_64.AppImage"
echo ""
echo "  Runtime requirement on target Linux:"
echo "    Ubuntu/Debian: sudo apt install gir1.2-webkit2-4.0 python3-gi"
echo "    Fedora:        sudo dnf install webkit2gtk3"
echo "    Arch/Manjaro:  sudo pacman -S webkit2gtk"
echo ""
echo "  Run: chmod +x dist/${APP_NAME}-${VERSION}-x86_64.AppImage"
echo "       ./dist/${APP_NAME}-${VERSION}-x86_64.AppImage"
echo ""
