#!/usr/bin/env bash
# AC Career GT Edition — Linux dev launcher
#
# Usage: bash start.sh
#
# Requirements:
#   - Python 3.12
#   - libwebkit2gtk-4.0 or libwebkit2gtk-4.1 (pywebview GTK backend)
#     Ubuntu/Debian: sudo apt install python3-gi python3-gi-cairo gir1.2-webkit2-4.0
#     Fedora:        sudo dnf install webkit2gtk3 python3-gobject
#     Arch/Manjaro:  sudo pacman -S webkit2gtk python-gobject

set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

echo ""
echo "  =========================================="
echo "    AC CAREER GT EDITION"
echo "  =========================================="
echo ""

# --- Check for libwebkit2gtk (required by pywebview on Linux) ---
if ! ldconfig -p 2>/dev/null | grep -q "libwebkit2gtk-4"; then
    echo "  [!] WARNING: libwebkit2gtk-4.x not detected."
    echo "      The app window requires the GTK WebView library."
    echo "      Ubuntu/Debian: sudo apt install python3-gi gir1.2-webkit2-4.0"
    echo "      Fedora:        sudo dnf install webkit2gtk3"
    echo "      Arch:          sudo pacman -S webkit2gtk"
    echo ""
fi

# --- Stop any existing Flask server on port 5000 ---
echo "  Checking for existing server on port 5000..."
fuser -k 5000/tcp 2>/dev/null && echo "  (killed existing process)" || true

# --- Create venv with Python 3.12 if missing ---
if [ ! -f "venv/bin/python" ]; then
    echo "  Creating Python 3.12 virtual environment..."
    python3.12 -m venv venv
    echo "  Installing dependencies..."
    venv/bin/pip install -r requirements.txt
    echo ""
fi

echo "  Starting app... (Ctrl+C to stop)"
echo ""

venv/bin/python app.py
