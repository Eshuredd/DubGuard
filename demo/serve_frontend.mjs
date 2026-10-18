import { spawn } from "node:child_process";
const child = spawn(
  process.execPath,
  [
    "frontend/node_modules/vite/bin/vite.js",
    "frontend",
    "--host",
    "127.0.0.1",
    "--port",
    "5182",
  ],
  {
    stdio: "inherit",
    env: { ...process.env, DUBGUARD_DEV_API_TARGET: "http://127.0.0.1:8011" },
  },
);
child.on("exit", (code) => process.exit(code ?? 1));
