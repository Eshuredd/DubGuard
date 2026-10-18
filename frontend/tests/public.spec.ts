import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { capture } from "./capture";

test("public local mode: no code, original upload download, local evidence and restricted AMD", async ({
  page,
}) => {
  test.skip(
    process.env.DUBGUARD_E2E_PUBLIC !== "true",
    "Run separately with DUBGUARD_E2E_PUBLIC=true",
  );
  await page.goto("/test");
  await expect(
    page.getByRole("heading", { name: "Start a public local test" }),
  ).toBeVisible();
  await expect(
    page.getByLabel("Demo access code", { exact: true }),
  ).toHaveCount(0);
  await capture(page, "public-landing");
  await page.getByRole("button", { name: "Start Quick Test" }).click();
  await page.getByRole("button", { name: "15 versus 50", exact: true }).click();
  // Explicit synthetic silence; no approved script is used as ground truth.
  const data = Buffer.alloc(32044);
  data.write("RIFF");
  data.writeUInt32LE(data.length - 8, 4);
  data.write("WAVEfmt ", 8);
  data.writeUInt32LE(16, 16);
  data.writeUInt16LE(1, 20);
  data.writeUInt16LE(1, 22);
  data.writeUInt32LE(16000, 24);
  data.writeUInt32LE(32000, 28);
  data.writeUInt16LE(2, 32);
  data.writeUInt16LE(16, 34);
  data.write("data", 36);
  data.writeUInt32LE(32000, 40);
  await page
    .getByLabel("Upload audio", { exact: true })
    .setInputFiles({
      name: "original-evaluation.wav",
      mimeType: "audio/wav",
      buffer: data,
    });
  const pending = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download Original Recording" }).click();
  const download = await pending;
  expect(download.suggestedFilename()).toBe(
    "dubguard-fifteen-fifty-original.wav",
  );
  expect(readFileSync((await download.path())!)).toEqual(data);
  await page.getByRole("button", { name: "Analyze recording" }).click();
  await expect(
    page.getByRole("heading", { name: "Verification findings", exact: true }),
  ).toBeVisible();
  const cap = await page.evaluate(() =>
    sessionStorage.getItem("dubguard-demo"),
  );
  const headers = { Authorization: "Bearer " + cap };
  const report = await (
    await page.request.get("/api/quick/session", { headers })
  ).json();
  expect(report.mode).toBe("local");
  expect(report.amd_runs).toBe(0);
  expect(report.semantic_verification).toBeNull();
  expect(
    Buffer.from(
      await (await page.request.get("/api/quick/audio", { headers })).body(),
    ),
  ).toEqual(data);
  expect(
    (
      await page.request.post(
        "/api/quick/analyze?scenario_id=correct&mode=amd&consent=true",
        { headers, data: "must not be parsed" },
      )
    ).status(),
  ).toBe(403);
  await page
    .getByRole("button", { name: "On versus off", exact: true })
    .click();
  await expect(
    page.getByText("these results still belong to the previous analysis", {
      exact: false,
    }),
  ).toBeVisible();
  await page.getByLabel("Verification mode").selectOption("amd");
  await expect(page.getByLabel("AMD demo access code")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Analyze recording" }),
  ).toBeDisabled();
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    expect(
      (
        await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
          .analyze()
      ).violations,
    ).toEqual([]);
  }
  await capture(page, "public-local-evidence");
  await page.getByRole("button", { name: "Delete session and audio" }).click();
  expect(
    (await page.request.get("/api/quick/audio", { headers })).status(),
  ).toBe(401);
});
