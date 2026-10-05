# Flowline desktop app

A desktop window around the local Flowline app (Electron). On launch it:

1. checks WebGL (the map needs it) and, if it is missing, relaunches once with software
   rendering;
2. finds your Flowline folder (the checkout with `start.sh`);
3. runs the normal launcher (`start.sh --no-open`, or `start.ps1 -NoOpen` on Windows) and
   shows its progress on a splash screen;
4. waits for the health checks (API `/health` and the web app), then opens the app window;
5. on close, runs `stop.sh` / `stop.ps1`, which stops the API, the web app and the Docker
   containers. Data is kept.

If Flowline is already running when the app starts (for example you ran `./start.sh` in a
terminal), the window attaches to it and leaves it running when you close the window.

**Docker is still required.** The database and router run in Docker containers, so Docker
must be installed and running (Linux: the Docker engine and your user in the `docker`
group; Windows/macOS: Docker Desktop). The first start can take several minutes. It may
download data and build the database, the routing graph and the web app.

## Linux (first target)

```bash
cd desktop
npm ci              # Electron + electron-builder (first time only)
npm start           # run from the checkout (development)
npm run dist        # build dist/Flowline-<version>-x86_64.AppImage
./install-linux.sh            # optional: add Flowline to your app menu (no sudo)
./install-linux.sh --desktop  # …and a trusted launcher icon on the desktop
./install-linux.sh --remove   # undo
```

- The AppImage remembers the checkout it was built from (`build/flowline-home.json`,
  machine-specific, not committed). To use another checkout, set `FLOWLINE_HOME`.
  If neither works, the app asks for the folder and remembers it.
- AppImages need FUSE 2. Without `libfuse2` (Kali and other distros ship only FUSE 3),
  `install-linux.sh` unpacks the AppImage once into `~/Applications/Flowline` and the
  menu/desktop entries launch it from there. No FUSE is needed, and startup is faster than
  `APPIMAGE_EXTRACT_AND_RUN=1`. With libfuse2 installed (`sudo apt install libfuse2`,
  `libfuse2t64` on newer Debian/Ubuntu) the AppImage runs directly.
- The desktop icon is made executable and marked trusted for GNOME (`metadata::trusted`)
  and Xfce 4.18+ (`metadata::xfce-exe-checksum`), so a double-click starts it without a
  prompt. Re-run the script after rebuilding the AppImage.
- Apps started from a menu get a short `PATH`. The app borrows your login shell's `PATH`
  so `docker`, `node` and `python3` are found the same way as in a terminal.
- Logs: `logs/desktop.log` in the Flowline folder (plus the usual `logs/*.log`).

### WebGL

The window starts Chromium with `--ignore-gpu-blocklist` and `--enable-unsafe-swiftshader`.
The map then uses the GPU even when Chromium blocklists it, and falls back to software
WebGL when there is no usable GPU. `FLOWLINE_WEBGL=software` forces software rendering
(`--use-angle=swiftshader`). This is slower but works in VMs and on remote desktops. If
WebGL is still missing, the app shows the offline Alberta map.

### Checks

`--smoke-test=<file.png>` starts everything, saves a screenshot of the loaded app,
reports whether WebGL works in the app window, and shuts down. It works headless:

```bash
xvfb-run -a -s "-screen 0 1600x1000x24" npx electron . --smoke-test=/tmp/flowline.png
```

## Windows and macOS (not built or tested yet)

The code already handles both. What's still needed:

- **Windows:** build on Windows with `npx electron-builder --win nsis`, and add a
  `build/icon.ico` (256×256). The app runs `start.ps1 -NoOpen` / `stop.ps1` through
  PowerShell 5.1+. It needs Docker Desktop (WSL 2 backend), Python 3.11+ and Node 20+ on
  `PATH`. Unsigned installers trigger SmartScreen; sign with a code-signing certificate
  for distribution.
- **macOS:** build on a Mac with `npx electron-builder --mac dmg`, and add a
  `build/icon.icns`. The app runs `start.sh`, which starts Docker Desktop if needed.
  Distribution outside your own machine needs an Apple Developer ID, code signing and
  notarisation, or Gatekeeper blocks the app. Apple-silicon and Intel builds are separate
  (`--arm64` / `--x64`) or one universal build.
- Both: the menu `PATH` caveat above applies on macOS (handled the same way). On Windows
  `PATH` comes from the system environment.
