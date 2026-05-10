#!/usr/bin/env bash
# install.sh — installs GPU Monitor as a desktop app
# Run once from inside the gpu_dashboard folder:
#   bash install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="gpu-monitor"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
DESKTOP_FILE="$DESKTOP_DIR/$APP_NAME.desktop"

echo "==> GPU Monitor installer"
echo "    App folder: $SCRIPT_DIR"

# ── 1. Install Python dependencies ──
echo ""
echo "==> Installing Python dependencies..."
if [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    echo "    Found existing venv, using it."
    source "$SCRIPT_DIR/venv/bin/activate"
else
    echo "    Creating venv..."
    python3 -m venv "$SCRIPT_DIR/venv"
    source "$SCRIPT_DIR/venv/bin/activate"
fi
pip install -q -r "$SCRIPT_DIR/requirements.txt"
echo "    Dependencies installed."

# ── 2. Make launch.sh executable ──
chmod +x "$SCRIPT_DIR/launch.sh"

# ── 3. Install icon ──
echo ""
echo "==> Installing icon..."
mkdir -p "$ICON_DIR"
cp "$SCRIPT_DIR/icon.png" "$ICON_DIR/$APP_NAME.png"

# ── 4. Write .desktop file ──
echo ""
echo "==> Creating desktop entry..."
mkdir -p "$DESKTOP_DIR"

cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=GPU Monitor
Comment=Real-time NVIDIA GPU dashboard
Exec=bash "$SCRIPT_DIR/launch.sh"
Icon=$APP_NAME
Terminal=false
Categories=System;Monitor;
Keywords=gpu;nvidia;monitor;dashboard;
StartupNotify=true
EOF

chmod +x "$DESKTOP_FILE"

# ── 5. Refresh desktop DB ──
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
fi

# ── 6. Optional: copy shortcut to Desktop ──
if [ -d "$HOME/Desktop" ]; then
    cp "$DESKTOP_FILE" "$HOME/Desktop/$APP_NAME.desktop"
    chmod +x "$HOME/Desktop/$APP_NAME.desktop"
    echo "    Shortcut copied to ~/Desktop"
fi

echo ""
echo "✓ GPU Monitor installed!"
echo "  → Find it in your app menu under 'System' or search 'GPU Monitor'"
echo "  → Or double-click the icon on your Desktop"
echo "  → Or run manually: bash $SCRIPT_DIR/launch.sh"
echo ""
echo "  To uninstall:"
echo "    rm $DESKTOP_FILE"
echo "    rm $ICON_DIR/$APP_NAME.png"
echo "    rm -rf $SCRIPT_DIR/venv"
