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

## Windows and macOS (built by CI, unsigned, UNTESTED)

GitHub Actions (`.github/workflows/desktop-installers.yml`) builds the desktop app on
Windows (`.exe` installer, NSIS), macOS (`.dmg`, Apple silicon and Intel) and Linux
(`.AppImage`). It runs on pull requests that touch `desktop/`, on `desktop-v*` tags, or
by hand (Actions → *Desktop installers* → *Run workflow*). Download the files from the
run's **Artifacts**. **Nobody has run the Windows or macOS builds yet.**

The desktop app is a window around a Flowline folder, so install Flowline first (the
one-line installer in the main README). On first start the CI-built app asks for that
folder (e.g. `C:\Users\you\flowline` or `~/flowline`) and remembers it. Docker Desktop,
git, Node.js and Python must be installed, as for the command-line route.

The builds are **unsigned** (no code-signing certificate), so the operating system warns
on first open:

- **Windows SmartScreen** ("Windows protected your PC"): click **More info**, then
  **Run anyway**. Some company policies block unsigned apps entirely; then use the
  command-line route (`start.ps1`).
- **macOS Gatekeeper** ("cannot be opened because the developer cannot be verified"): in
  Finder, **right-click** Flowline.app, choose **Open**, then **Open** again. On recent
  macOS, use System Settings → Privacy & Security → **Open Anyway**. If macOS says the app
  is "damaged", clear the download quarantine flag:
  `xattr -dr com.apple.quarantine /Applications/Flowline.app`.

For real distribution:

- **Windows:** sign with a code-signing certificate (`CSC_LINK` / `CSC_KEY_PASSWORD` in
  electron-builder).
- **macOS:** sign and notarise with an Apple Developer ID (`CSC_LINK`, `APPLE_ID`,
  `APPLE_APP_SPECIFIC_PASSWORD`, `APPLE_TEAM_ID`).

Both are left out on purpose until there is an owner for the certificates.

Platform notes:

- **Windows:** the app runs `start.ps1 -NoOpen` / `stop.ps1` through Windows PowerShell
  5.1. Docker Desktop needs the WSL 2 backend. `PATH` comes from the system environment.
- **macOS:** the app runs `start.sh`, which starts Docker Desktop if needed. Like Linux,
  it borrows the login shell's `PATH` so Homebrew's `node` / `python3` are found.
