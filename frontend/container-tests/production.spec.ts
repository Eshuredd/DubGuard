// Running Caddy + real CPU ASR, generated silence only. No AMD request is made.
import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
const root = resolve(import.meta.dirname, "../..");
const config = readFileSync(
  resolve(root, ".dubguard-data/phase5/server.env"),
  "utf8",
);
const value = (name: string) =>
  config
    .split(/\r?\n/)
    .find((line) => line.startsWith(name + "="))
    ?.slice(name.length + 1) ?? "";
if (value("AMD_TOKEN_FACTORY_API_KEY"))
  throw new Error("Container test requires a blank AMD key");

test("production SPA, CSP, private upload and real CPU ASR remain provisional", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  const response = await page.goto("/test");
  expect(response?.headers()["permissions-policy"]).toBe("microphone=(self)");
  await page
    .getByLabel("Demo access code")
    .fill(value("DUBGUARD_DEMO_ACCESS_CODE"));
  await page.getByRole("button", { name: "Start Quick Test" }).click();
  await expect(page.getByLabel("Verification mode")).toHaveValue("local");
  const wav = Buffer.alloc(44 + 64000);
  wav.write("RIFF");
  wav.writeUInt32LE(wav.length - 8, 4);
  wav.write("WAVEfmt ", 8);
  wav.writeUInt32LE(16, 16);
  wav.writeUInt16LE(1, 20);
  wav.writeUInt16LE(1, 22);
  wav.writeUInt32LE(16000, 24);
  wav.writeUInt32LE(32000, 28);
  wav.writeUInt16LE(2, 32);
  wav.writeUInt16LE(16, 34);
  wav.write("data", 36);
  wav.writeUInt32LE(64000, 40);
  await page.getByLabel("Upload audio", { exact: true }).setInputFiles({
    name: "generated-silence.wav",
    mimeType: "audio/wav",
    buffer: wav,
  });
  await page.getByRole("button", { name: "Analyze recording" }).click();
  await expect(
    page.getByRole("heading", { name: "Verification findings" }),
  ).toBeVisible({ timeout: 60_000 });
  await expect(
    page.getByText(/Analyzed mode: Local Verification/),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Raw ASR · unverified" }),
  ).toBeVisible();
  await expect(
    page.getByText("review required", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByText(/Analyzed mode: Local Verification/),
  ).toBeVisible();
  await page.getByLabel("Verification mode").selectOption("amd");
  await expect(
    page.getByLabel("I consent to sending script"),
  ).not.toBeChecked();
  await page.screenshot({
    path: resolve(root, "reports/phase5/production-local.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Delete session and audio" }).click();
  expect(errors).toEqual([]);
});
