import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./container-tests",
  outputDir: "./test-results-container",
  workers: 1,
  timeout: 90_000,
  retries: 0,
  use: {
    baseURL:
      process.env.DUBGUARD_CONTAINER_BASE_URL || "http://127.0.0.1:18080",
    ...devices["Desktop Chrome"],
    channel: "chrome",
    trace: "retain-on-failure",
  },
});
