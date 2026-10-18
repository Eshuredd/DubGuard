import { defineConfig, devices } from "@playwright/test";
import { randomBytes } from "node:crypto";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
process.env.DUBGUARD_E2E_REVIEW_TOKEN ||= randomBytes(32).toString("hex");
process.env.DUBGUARD_E2E_DEMO_CODE ||= randomBytes(32).toString("hex");
process.env.DUBGUARD_E2E_AMD_CODE ||= randomBytes(32).toString("hex");
process.env.DUBGUARD_E2E_DIR ||= mkdtempSync(join(tmpdir(), "dubguard-e2e-"));
const apiPort = process.env.DUBGUARD_E2E_API_PORT || "8000";
const webPort = process.env.DUBGUARD_E2E_WEB_PORT || "5173";
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  timeout: 75_000,
  retries: 0,
  globalTeardown: "./tests/teardown.ts",
  use: {
    baseURL: `http://127.0.0.1:${webPort}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chrome",
      use: {
        ...devices["Desktop Chrome"],
        channel: "chrome",
        launchOptions: {
          args: [
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream",
          ],
        },
      },
    },
  ],
  webServer: [
    {
      command: `node ../scripts/python.mjs -m uvicorn e2e_server:app --app-dir ../tests --host 127.0.0.1 --port ${apiPort}`,
      url: `http://127.0.0.1:${apiPort}/health`,
      reuseExistingServer: false,
      env: {
        DUBGUARD_DATA_DIR: process.env.DUBGUARD_E2E_DIR,
        DUBGUARD_REVIEW_TOKENS_JSON: JSON.stringify({
          "e2e-reviewer": process.env.DUBGUARD_E2E_REVIEW_TOKEN,
        }),
        DUBGUARD_DEMO_ACCESS_CODE: process.env.DUBGUARD_E2E_DEMO_CODE,
        DUBGUARD_PUBLIC_WORKSPACE: "true",
        DUBGUARD_CLIENT_EDITS_PER_HOUR: "120",
        DUBGUARD_OPERATOR_LOGINS_PER_HOUR: "30",
        DUBGUARD_AMD_DEMO_ACCESS_CODE: process.env.DUBGUARD_E2E_AMD_CODE,
        DUBGUARD_PUBLIC_LOCAL_DEMO:
          process.env.DUBGUARD_E2E_PUBLIC === "true" ? "true" : "false",
        DUBGUARD_CLIENT_SESSIONS_PER_HOUR: "30",
        DUBGUARD_CLIENT_UPLOADS_PER_HOUR: "90",
        DUBGUARD_SEMANTIC_PROVIDER: "disabled",
        DUBGUARD_SECONDARY_WHISPER_MODEL: "e2e-fixture-only",
      },
    },
    {
      command: `npm run dev -- --port ${webPort}`,
      url: `http://127.0.0.1:${webPort}`,
      env: { DUBGUARD_DEV_API_TARGET: `http://127.0.0.1:${apiPort}` },
      reuseExistingServer: false,
    },
  ],
});
