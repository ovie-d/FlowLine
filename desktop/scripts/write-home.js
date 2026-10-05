// Records this checkout's path for the packaged app (resources/flowline-home.json), so
// the AppImage finds start.sh without asking. Machine-specific: not committed.
const fs = require("node:fs");
const path = require("node:path");

const home = path.resolve(__dirname, "..", "..");
const out = path.join(__dirname, "..", "build", "flowline-home.json");
fs.writeFileSync(out, JSON.stringify({ home }, null, 2) + "\n");
console.log(`flowline-home.json -> ${home}`);
