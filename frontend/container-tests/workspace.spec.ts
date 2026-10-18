// Real Caddy/production bundle/CPU Whisper. Generated silence; no live AMD.
import { test, expect } from "@playwright/test";
import { mkdirSync } from "node:fs";
test("production public custom reference and original audio stay isolated and provisional", async ({
  page,
}) => {
  await page.goto("/workspace");
  await page.getByLabel("Script title").fill("Synthetic CPU protocol test");
  await page
    .getByRole("button", { name: "Save reference & demo policy" })
    .click();
  await expect(page.getByLabel("Workspace update")).toContainText(
    "Reference saved",
  );
  const b = Buffer.alloc(64044);
  b.write("RIFF");
  b.writeUInt32LE(b.length - 8, 4);
  b.write("WAVEfmt ", 8);
  b.writeUInt32LE(16, 16);
  b.writeUInt16LE(1, 20);
  b.writeUInt16LE(1, 22);
  b.writeUInt32LE(16000, 24);
  b.writeUInt32LE(32000, 28);
  b.writeUInt16LE(2, 32);
  b.writeUInt16LE(16, 34);
  b.write("data", 36);
  b.writeUInt32LE(64000, 40);
  await page
    .getByLabel("Upload audio", { exact: true })
    .setInputFiles({
      name: "synthetic-silence.wav",
      mimeType: "audio/wav",
      buffer: b,
    });
  await page.getByRole("button", { name: "Analyze recording locally" }).click();
  await expect(
    page.getByRole("heading", { name: "Local verification findings" }),
  ).toBeVisible({ timeout: 60000 });
  const cap = await page.evaluate(() =>
    sessionStorage.getItem("dubguard-custom"),
  );
  const headers = { Authorization: "Bearer " + cap };
  const data = await (
    await page.request.get("/api/workspace/export", { headers })
  ).json();
  expect(data.analysis.state).toBe("COMPLETE");
  expect(data.analysis.verification.decision).toBe("REVIEW_REQUIRED");
  expect(data.workspace.reference.script.instructions[0].text).toBe(
    "Wait 15 minutes before restarting.",
  );
  expect(data.workspace.evidence).toBeNull();
  expect(data.analysis.amd_runs).toBe(0);
  expect(data.analysis.transcription.provider).not.toContain("stub");
  expect(
    await (await page.request.get("/api/workspace/audio", { headers })).body(),
  ).toEqual(b);
  expect(
    (await page.request.get("/api/review/workflows", { headers })).status(),
  ).toBe(401);
  await page.evaluate(() => {
    const p = document.createElement("p");
    p.textContent =
      "LOCAL CONTAINER CHECK · Synthetic silence · Real CPU ASR · No human speech or AMD call";
    document.querySelector("main")!.prepend(p);
  });
  mkdirSync("../reports/local/public-workspace", { recursive: true });
  await page.screenshot({
    path: "../reports/local/public-workspace/container-custom.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Delete temporary review" }).click();
  expect(
    (await page.request.get("/api/workspace/audio", { headers })).status(),
  ).toBe(401);
});
