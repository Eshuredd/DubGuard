// Resolve the repository virtualenv on Windows and Unix without shell expansion.
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";
const executable = ["../.venv/Scripts/python.exe", "../.venv/bin/python"]
  .map((path) => fileURLToPath(new URL(path, import.meta.url)))
  .find(existsSync);
if (!executable) throw new Error("Create the repository .venv and install dependencies first.");
const child = spawn(executable, process.argv.slice(2), { stdio: "inherit" });
child.on("error", (error) => { console.error(error.message); process.exitCode = 1; });
child.on("exit", (code) => { process.exitCode = code ?? 1; });
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => child.kill(signal));
