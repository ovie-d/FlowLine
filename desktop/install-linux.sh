#!/usr/bin/env bash
# Adds Flowline to this user's app menu (no sudo).
#   desktop/install-linux.sh            menu entry
#   desktop/install-linux.sh --desktop  menu entry + a trusted launcher icon on the desktop
#   desktop/install-linux.sh --remove   remove everything this script installed
#
# AppImages need FUSE 2 (libfuse2). Without it (e.g. Kali / newer distros with FUSE 3
# only) the AppImage is unpacked once into ~/Applications/Flowline and launched from
# there: no FUSE needed, and faster than extract-and-run on every start.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPS="$HOME/Applications"
UNPACKED="$APPS/Flowline"
ENTRY="$HOME/.local/share/applications/flowline.desktop"
ICON="$HOME/.local/share/icons/hicolor/512x512/apps/flowline.png"
DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
DESKTOP_ICON="$DESKTOP_DIR/Flowline.desktop"

# A desktop file the file manager runs without asking (executable + trusted).
trust() {
  chmod +x "$1"
  command -v gio >/dev/null || return 0
  gio set "$1" metadata::trusted true 2>/dev/null || true                    # GNOME / Nautilus
  gio set -t string "$1" metadata::xfce-exe-checksum \
    "$(sha256sum "$1" | cut -d' ' -f1)" 2>/dev/null || true                     # Xfce 4.18+
}

if [[ "${1:-}" == "--remove" ]]; then
  rm -rf "$UNPACKED"
  rm -f "$ENTRY" "$ICON" "$DESKTOP_ICON" "$APPS"/Flowline-*.AppImage
  update-desktop-database "$(dirname "$ENTRY")" >/dev/null 2>&1 || true
  echo "Removed Flowline from the menu and the desktop."
  exit 0
fi

IMG="$(ls -t "$HERE"/dist/Flowline-*.AppImage 2>/dev/null | head -1 || true)"
[[ -n "$IMG" ]] || { echo "No AppImage found. Build it first: (cd desktop && npm ci && npm run dist)"; exit 1; }
mkdir -p "$APPS" "$(dirname "$ENTRY")" "$(dirname "$ICON")"
cp "$HERE/build/icon.png" "$ICON"

if { ldconfig -p 2>/dev/null || /sbin/ldconfig -p 2>/dev/null; } | grep -q 'libfuse\.so\.2'; then
  cp "$IMG" "$APPS/"
  EXEC="\"$APPS/$(basename "$IMG")\""
  echo "Using the AppImage directly (libfuse2 found)."
else
  echo "libfuse2 not found: unpacking the AppImage into $UNPACKED (one-time)…"
  TMP="$(mktemp -d)"
  (cd "$TMP" && "$IMG" --appimage-extract >/dev/null)
  rm -rf "$UNPACKED"
  mv "$TMP/squashfs-root" "$UNPACKED"
  rm -rf "$TMP"
  EXEC="\"$UNPACKED/flowline\""
fi

write_entry() {
  cat > "$1" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Flowline
GenericName=Pipeline hazard forecast
Comment=Pipeline hazard forecast and emergency dispatch
Exec=$EXEC
Icon=$ICON
Terminal=false
Categories=Science;
StartupNotify=true
StartupWMClass=Flowline
EOF
}

write_entry "$ENTRY"
update-desktop-database "$(dirname "$ENTRY")" >/dev/null 2>&1 || true
echo "Menu entry: $ENTRY"

if [[ "${1:-}" == "--desktop" ]]; then
  mkdir -p "$DESKTOP_DIR"
  write_entry "$DESKTOP_ICON"
  trust "$DESKTOP_ICON"
  echo "Desktop icon: $DESKTOP_ICON (double-click to start)"
fi
