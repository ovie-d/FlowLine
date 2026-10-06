// Records this checkout's path for the packaged app (resources/flowline-home.json), so
// the AppImage finds start.sh without asking. Machine-specific: not committed.
//   node scripts/write-home.js         this checkout
//   node scripts/write-home.js --none  no path (CI builds): the app asks on first start
const fs = require("node:fs");
const path = require("node:path");

const home = process.argv.includes("--none") ? null : path.resolve(__dirname, "..", "..");
const out = path.join(__dirname, "..", "build", "flowline-home.json");
fs.writeFileSync(out, JSON.stringify({ home }, null, 2) + "\n");
console.log(`flowline-home.json -> ${home ?? "(none: asks for the folder on first start)"}`);
