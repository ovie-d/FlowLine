#!/usr/bin/env bash
# Adds Flowline to the desktop menu for this user (no sudo): copies the AppImage to
# ~/Applications and writes ~/.local/share/applications/flowline.desktop.
#   desktop/install-linux.sh            install
#   desktop/install-linux.sh --remove   remove the menu entry and the copied AppImage
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPS="$HOME/Applications"
ENTRY="$HOME/.local/share/applications/flowline.desktop"
ICON="$HOME/.local/share/icons/hicolor/512x512/apps/flowline.png"

if [[ "${1:-}" == "--remove" ]]; then
  rm -f "$ENTRY" "$ICON" "$APPS"/Flowline-*.AppImage
  echo "Removed the Flowline menu entry."
  exit 0
fi

IMG="$(ls -t "$HERE"/dist/Flowline-*.AppImage 2>/dev/null | head -1 || true)"
[[ -n "$IMG" ]] || { echo "No AppImage found. Build it first: (cd desktop && npm ci && npm run dist)"; exit 1; }
mkdir -p "$APPS" "$(dirname "$ENTRY")" "$(dirname "$ICON")"
cp "$IMG" "$APPS/"
cp "$HERE/build/icon.png" "$ICON"
TARGET="$APPS/$(basename "$IMG")"

# AppImages need FUSE 2 (libfuse2). Without it, run them in extract mode instead.
EXEC="\"$TARGET\""
if ! { ldconfig -p 2>/dev/null || /sbin/ldconfig -p 2>/dev/null; } | grep -q 'libfuse\.so\.2'; then
  EXEC="env APPIMAGE_EXTRACT_AND_RUN=1 \"$TARGET\""
  echo "Note: libfuse2 not found; the menu entry uses extract-and-run mode (slower start)."
  echo "      For a faster start: sudo apt install libfuse2 (or libfuse2t64)."
fi

cat > "$ENTRY" <<EOF
[Desktop Entry]
Type=Application
Name=Flowline
Comment=Pipeline hazard forecast and emergency dispatch
Exec=$EXEC
Icon=flowline
Terminal=false
Categories=Science;
StartupWMClass=Flowline
EOF
update-desktop-database "$(dirname "$ENTRY")" >/dev/null 2>&1 || true
echo "Installed: $ENTRY -> $TARGET"
