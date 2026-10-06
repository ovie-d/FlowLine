// Flowline desktop: a window around the local app. It starts the services with the
// existing launcher (start.sh / start.ps1), waits for the health checks, opens the app,
// and stops the services again when the window closes (only if it started them).
// Docker is still required: the database and router run in containers.

const { app, BrowserWindow, dialog, shell } = require("electron");
const { spawn, execFile } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const API_PORT = process.env.API_PORT || "8000";
const WEB_PORT = process.env.WEB_PORT || "3000";
const API_URL = `http://127.0.0.1:${API_PORT}/health`;
const APP_URL = `http://localhost:${WEB_PORT}/`;
const HEALTH_TIMEOUT_MS = 180_000;
const IS_WIN = process.platform === "win32";
const ICON = path.join(__dirname, "build", "icon.png");

// ------------------------------------------------------------------ WebGL
// The map needs WebGL. Use the GPU even when Chromium blocklists it, and allow the
// software (SwiftShader) fallback when there is no usable GPU. FLOWLINE_WEBGL=software
// forces software rendering; the app also relaunches itself that way if WebGL is missing.
const SOFTWARE_FLAG = "--flowline-software-webgl";
const forceSoftware = process.env.FLOWLINE_WEBGL === "software" || process.argv.includes(SOFTWARE_FLAG);
app.commandLine.appendSwitch("ignore-gpu-blocklist");
app.commandLine.appendSwitch("enable-unsafe-swiftshader");
if (forceSoftware) app.commandLine.appendSwitch("use-angle", "swiftshader");

// Smoke test (CI / headless checks): --smoke-test=<png> saves a screenshot of the
// loaded app and quits, stopping the services if this run started them.
const smokeArg = process.argv.find((a) => a.startsWith("--smoke-test="));
const SMOKE_PNG = smokeArg ? path.resolve(smokeArg.split("=")[1]) : null;

let splash = null;
let main = null;
let home = null;
let ownsServices = false;
let stopping = false;
let logFile = null;
const early = []; // lines logged before the Flowline folder (and its logs/) is known

function log(line) {
  const text = String(line).replace(/\x1b\[[0-9;]*m/g, "").trimEnd();
  if (!text) return;
  const stamped = `${new Date().toISOString()} ${text}\n`;
  if (logFile) fs.appendFileSync(logFile, stamped);
  else early.push(stamped);
  if (splash && !splash.isDestroyed()) splash.webContents.send("status", text);
  if (!app.isPackaged || process.env.FLOWLINE_DEBUG) console.log(text);
}

// ------------------------------------------------------------------ repo location
function isFlowlineHome(dir) {
  return !!dir && fs.existsSync(path.join(dir, IS_WIN ? "start.ps1" : "start.sh")) &&
    fs.existsSync(path.join(dir, "docker-compose.yml"));
}

function configPath() {
  return path.join(app.getPath("userData"), "config.json");
}

function readConfigHome() {
  try {
    return JSON.parse(fs.readFileSync(configPath(), "utf8")).home;
  } catch {
    return null;
  }
}

function bakedHome() {
  // Written by `npm run dist` (scripts/write-home.js) so the package knows its checkout.
  try {
    return JSON.parse(fs.readFileSync(path.join(process.resourcesPath, "flowline-home.json"), "utf8")).home;
  } catch {
    return null;
  }
}

async function resolveHome() {
  const candidates = [process.env.FLOWLINE_HOME, readConfigHome(), path.resolve(__dirname, ".."), bakedHome()];
  const found = candidates.find(isFlowlineHome);
  if (found) return found;
  const pick = await dialog.showOpenDialog({
    title: "Where is your Flowline folder?",
    message: "Choose the Flowline folder (the one with start.sh and docker-compose.yml).",
    properties: ["openDirectory"],
  });
  const dir = pick.filePaths[0];
  if (!isFlowlineHome(dir)) return null;
  fs.mkdirSync(app.getPath("userData"), { recursive: true });
  fs.writeFileSync(configPath(), JSON.stringify({ home: dir }, null, 2));
  return dir;
}

// ------------------------------------------------------------------ environment
// Apps started from a desktop menu get a minimal PATH. Borrow the login shell's PATH
// so the launcher finds docker, node, npm and python like it does in a terminal.
function loginShellPath() {
  if (IS_WIN) return Promise.resolve(process.env.PATH);
  const sh = process.env.SHELL || "/bin/bash";
  return new Promise((resolve) => {
    execFile(sh, ["-ilc", 'printf "__FLPATH__%s__FLPATH__" "$PATH"'], { timeout: 10_000 }, (err, out) => {
      const m = /__FLPATH__(.*)__FLPATH__/.exec(out || "");
      resolve(m ? m[1] : process.env.PATH);
    });
  });
}

function run(script, args, env) {
  const cmd = IS_WIN ? "powershell.exe" : "bash";
  const argv = IS_WIN ? ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, ...args] : [script, ...args];
  return new Promise((resolve) => {
    const child = spawn(cmd, argv, { cwd: home, env, windowsHide: true });
    const pipe = (buf) => String(buf).split(/\r?\n/).forEach(log);
    child.stdout.on("data", pipe);
    child.stderr.on("data", pipe);
    child.on("error", (e) => {
      log(`Could not run ${script}: ${e.message}`);
      resolve(1);
    });
    child.on("close", (code) => resolve(code ?? 1));
  });
}

async function up(url) {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(2000) });
    return res.ok;
  } catch {
    return false;
  }
}

async function waitHealthy() {
  const t0 = Date.now();
  while (Date.now() - t0 < HEALTH_TIMEOUT_MS) {
    if ((await up(API_URL)) && (await up(APP_URL))) return true;
    await new Promise((r) => setTimeout(r, 1000));
  }
  return false;
}

// ------------------------------------------------------------------ windows
function createSplash() {
  splash = new BrowserWindow({
    width: 560,
    height: 380,
    frame: false,
    resizable: false,
    show: false,
    backgroundColor: "#0B1426",
    icon: ICON,
    title: "Flowline",
    webPreferences: { preload: path.join(__dirname, "preload.js") },
  });
  splash.loadFile(path.join(__dirname, "splash.html"));
  splash.once("ready-to-show", () => splash.show());
  return new Promise((r) => splash.webContents.once("did-finish-load", r));
}

async function webglAvailable(win) {
  try {
    return await win.webContents.executeJavaScript(
      "(() => { try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')); } catch { return false; } })()",
    );
  } catch {
    return false;
  }
}

function createMain() {
  main = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 820,
    minHeight: 600,
    show: false,
    backgroundColor: "#0B1426",
    icon: ICON,
    title: "Flowline",
    autoHideMenuBar: true,
    webPreferences: { contextIsolation: true, sandbox: true },
  });
  // Links that leave the app (docs, Mapbox attribution) open in the default browser.
  main.webContents.setWindowOpenHandler(({ url }) => {
    if (!url.startsWith(APP_URL)) shell.openExternal(url);
    return { action: "deny" };
  });
  main.webContents.on("will-navigate", (e, url) => {
    if (!url.startsWith(APP_URL)) {
      e.preventDefault();
      shell.openExternal(url);
    }
  });
  main.on("close", (e) => {
    if (ownsServices && !stopping) {
      e.preventDefault();
      void shutdown();
    }
  });
  main.once("ready-to-show", () => {
    if (splash && !splash.isDestroyed()) splash.destroy();
    if (!SMOKE_PNG) main.show();
  });
  return main.loadURL(APP_URL);
}

function fail(message) {
  log(message);
  if (splash && !splash.isDestroyed()) splash.webContents.send("failed", message);
}

// ------------------------------------------------------------------ lifecycle
async function start() {
  await createSplash();

  // No WebGL even with the GPU flags: relaunch once with software rendering.
  const webgl = await webglAvailable(splash);
  log(`WebGL ${webgl ? "available" : "unavailable"}${forceSoftware ? " (software rendering)" : ""}`);
  if (!webgl && !forceSoftware) {
    log("Relaunching with software WebGL…");
    app.relaunch({ args: [...process.argv.slice(1), SOFTWARE_FLAG] });
    app.exit(0);
    return;
  }

  home = await resolveHome();
  if (!home) return fail("No Flowline folder chosen. Set FLOWLINE_HOME or pick the folder that has start.sh.");
  fs.mkdirSync(path.join(home, "logs"), { recursive: true });
  logFile = path.join(home, "logs", "desktop.log");
  fs.appendFileSync(logFile, early.splice(0).join(""));
  log(`Flowline folder: ${home}`);

  const env = { ...process.env, PATH: await loginShellPath(), API_PORT, WEB_PORT };
  delete env.ELECTRON_RUN_AS_NODE;

  if ((await up(API_URL)) && (await up(APP_URL))) {
    log("Flowline is already running; attaching (it keeps running when this window closes).");
  } else {
    log("Starting services (Docker, database, router, API, web app)…");
    ownsServices = true;
    const code = await run(IS_WIN ? "start.ps1" : "start.sh", [IS_WIN ? "-NoOpen" : "--no-open"], env);
    if (code !== 0) {
      await run(IS_WIN ? "stop.ps1" : "stop.sh", [], env);
      ownsServices = false;
      return fail(`The launcher stopped with an error (exit ${code}). Details: ${path.join(home, "logs")}`);
    }
  }
  log("Waiting for the health checks…");
  if (!(await waitHealthy())) return fail(`Services did not become healthy within ${HEALTH_TIMEOUT_MS / 1000} s.`);
  log("Opening Flowline…");
  await createMain();

  if (SMOKE_PNG) {
    await new Promise((r) => setTimeout(r, 12000));
    const ok = await webglAvailable(main);
    const shot = await main.webContents.capturePage();
    fs.writeFileSync(SMOKE_PNG, shot.toPNG());
    log(`Smoke test: WebGL in app window ${ok ? "OK" : "MISSING"}; screenshot ${SMOKE_PNG}`);
    await shutdown();
  }
}

async function shutdown() {
  if (stopping) return;
  stopping = true;
  if (ownsServices && home) {
    if (main && !main.isDestroyed()) main.hide();
    await createSplash();
    splash.webContents.send("mode", "stopping");
    log("Stopping Flowline services…");
    const env = { ...process.env, PATH: await loginShellPath() };
    await run(IS_WIN ? "stop.ps1" : "stop.sh", [], env);
    log("Stopped.");
  }
  app.exit(0);
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    const w = main && !main.isDestroyed() ? main : splash;
    if (w && !w.isDestroyed()) {
      if (w.isMinimized()) w.restore();
      w.focus();
    }
  });
  app.whenReady().then(start);
  app.on("window-all-closed", () => void shutdown());
  for (const sig of ["SIGINT", "SIGTERM"]) process.on(sig, () => void shutdown());
}

// Splash buttons.
const { ipcMain } = require("electron");
ipcMain.on("quit", () => void shutdown());
ipcMain.on("open-logs", () => home && shell.openPath(path.join(home, "logs")));
