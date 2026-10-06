// Splash window bridge: status lines in, button presses out.
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("flowline", {
  onStatus: (fn) => ipcRenderer.on("status", (_e, line) => fn(line)),
  onFailed: (fn) => ipcRenderer.on("failed", (_e, msg) => fn(msg)),
  onMode: (fn) => ipcRenderer.on("mode", (_e, mode) => fn(mode)),
  quit: () => ipcRenderer.send("quit"),
  openLogs: () => ipcRenderer.send("open-logs"),
});
