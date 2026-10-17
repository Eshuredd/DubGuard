import { defineConfig, devices } from "@playwright/test";
import { randomBytes } from "node:crypto";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
process.env.DUBGUARD_E2E_REVIEW_TOKEN ||= randomBytes(32).toString("hex");
process.env.DUBGUARD_E2E_DEMO_CODE ||= randomBytes(32).toString("hex");
process.env.DUBGUARD_E2E_DIR ||= mkdtempSync(join(tmpdir(), "dubguard-e2e-"));
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  timeout: 45_000,
  retries: 0,
  globalTeardown: "./tests/teardown.ts",
  use: {
    baseURL: "http://127.0.0.1:5173",
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
      command:
        "node ../scripts/python.mjs -m uvicorn e2e_server:app --app-dir ../tests --host 127.0.0.1 --port 8000",
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: false,
      env: {
        DUBGUARD_DATA_DIR: process.env.DUBGUARD_E2E_DIR,
        DUBGUARD_REVIEW_TOKENS_JSON: JSON.stringify({
          "e2e-reviewer": process.env.DUBGUARD_E2E_REVIEW_TOKEN,
        }),
        DUBGUARD_DEMO_ACCESS_CODE: process.env.DUBGUARD_E2E_DEMO_CODE,
        DUBGUARD_SEMANTIC_PROVIDER: "disabled",
        DUBGUARD_SECONDARY_WHISPER_MODEL: "e2e-fixture-only",
      },
    },
    {
      command: "npm run dev -- --port 5173",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: false,
    },
  ],
});
