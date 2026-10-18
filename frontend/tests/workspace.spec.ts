import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { capture } from "./capture";

function silence() {
  const b = Buffer.alloc(32044);
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
  b.writeUInt32LE(32000, 40);
  return b;
}
async function save(page: import("@playwright/test").Page) {
  await page.goto("/workspace");
  await expect(
    page.getByRole("heading", { name: "Create a Review." }),
  ).toBeVisible();
  await page.getByLabel("Script title").fill("My custom power procedure");
  await page
    .getByRole("button", { name: "Polarity example", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Save reference & demo policy", exact: true })
    .click();
  await expect(page.getByLabel("Workspace update")).toContainText(
    "Reference saved",
  );
}

test("no-login custom review: script, upload, actual local rules, visitor correction, demo decision and export", async ({
  page,
}) => {
  await page.goto("/test");
  await page.getByRole("link", { name: "Create Your Own Review" }).click();
  await expect(page).toHaveURL(/\/workspace$/);
  expect(
    await page.evaluate(() => sessionStorage.getItem("dubguard-reviewer")),
  ).toBeNull();
  await expect(page.getByLabel("Reviewer token", { exact: true })).toHaveCount(
    0,
  );
  await save(page);
  await capture(page, "custom-reference");
  await page.getByLabel("Upload audio", { exact: true }).setInputFiles({
    name: "synthetic-silence.wav",
    mimeType: "audio/wav",
    buffer: silence(),
  });
  const downloading = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download Original Recording" }).click();
  expect(readFileSync((await (await downloading).path())!)).toEqual(silence());
  await capture(page, "custom-preview");
  await page
    .getByRole("button", { name: "Analyze recording locally", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Local verification findings" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Recognized narration · provisional" }),
  ).toBeVisible();
  await capture(page, "custom-local-evidence");
  await page
    .getByLabel("Actual spoken words · Segment 1")
    .fill("Switch the power on.");
  await page
    .getByLabel("Match to reference instruction 1")
    .selectOption("step-1");
  await page.getByLabel("Words remain unclear · Segment 1").uncheck();
  await page
    .getByLabel("Reason for correction")
    .fill("Synthetic protocol fixture only, not human ground truth.");
  await page.getByLabel("I listened to this original recording").check();
  await page.getByLabel("I checked the entire recording").check();
  await page
    .getByRole("button", { name: "Save demo evidence & rerun local rules" })
    .click();
  await expect(page.getByLabel("Workspace update")).toContainText(
    "Visitor corrections saved",
  );
  await expect(
    page.getByText("critical deviation", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Approve recording", exact: true }),
  ).toHaveCount(0);
  await page
    .getByLabel("Temporary review notes")
    .fill("Request a new take. Demo only.");
  await page
    .getByLabel("Demo decision", { exact: true })
    .selectOption("REQUEST_NEW_RECORDING");
  await page
    .getByRole("button", { name: "Save demo decision & notes" })
    .click();
  await expect(page.getByLabel("Workspace update")).toContainText(
    "No organizational approval",
  );
  await capture(page, "custom-demo-decision");
  const exporting = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Export demonstration evidence report" })
    .click();
  const report = JSON.parse(
    readFileSync((await (await exporting).path())!, "utf8"),
  );
  expect(report.workspace.demo_decision).toBe("REQUEST_NEW_RECORDING");
  expect(report.workspace.evidence.result.decision).toBe("CRITICAL_DEVIATION");
  expect(report.analysis.transcription.transcript.segments[0].text).toBe(
    "Switch the power off.",
  );
  expect(report.analysis.amd_runs).toBe(0);
  const cap = await page.evaluate(() =>
    sessionStorage.getItem("dubguard-custom"),
  );
  expect(JSON.stringify(report)).not.toContain(cap);
  const auth = { Authorization: "Bearer " + cap };
  expect(
    (
      await page.request.get("/api/review/workflows", { headers: auth })
    ).status(),
  ).toBe(401);
  expect(
    (
      await page.request.post("/api/review/workflows/missing/signoff", {
        headers: auth,
        data: {},
      })
    ).status(),
  ).toBe(401);
  await page.reload();
  await expect(
    page.getByText(/Saved demo decision: REQUEST NEW RECORDING/),
  ).toBeVisible();
  await page.getByRole("button", { name: "Delete temporary review" }).click();
  expect(
    (
      await page.request.get("/api/workspace/audio", { headers: auth })
    ).status(),
  ).toBe(401);
});

test("custom workspace supports a blank multi-instruction reference on mobile", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/test");
  await page.locator(".mobile-navigation summary").click();
  await page
    .getByRole("navigation", { name: "Mobile workspace" })
    .getByRole("link", { name: "Create a Review" })
    .click();
  await expect(page).toHaveURL(/\/workspace$/);
  await page.getByRole("button", { name: "Start blank", exact: true }).click();
  await page
    .getByLabel("Reference narration · Instruction 1")
    .fill("Close the valve.");
  await page
    .getByRole("button", { name: "Add instruction", exact: true })
    .click();
  await page
    .getByLabel("Reference narration · Instruction 2")
    .fill("Start the pump.");
  await page
    .getByRole("button", { name: "Protect order", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Save reference & demo policy" })
    .click();
  await expect(page.getByLabel("Workspace update")).toContainText(
    "Reference saved",
  );
  await capture(page, "custom-multiple-instructions");
  await page
    .getByRole("button", { name: "Record narration", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Start recording", exact: true })
    .click();
  await page.waitForTimeout(650);
  await page
    .getByRole("button", { name: "Stop recording", exact: true })
    .click();
  await expect(
    page.getByRole("link", { name: "Download Original Recording" }),
  ).toBeVisible();
  await capture(page, "custom-browser-recording");
  await page.getByRole("button", { name: "Discard recording" }).click();
  await page.getByRole("button", { name: "Delete temporary review" }).click();
});

test("operator credential is exchanged for an HttpOnly session and never stored in JavaScript", async ({
  page,
}) => {
  await page.goto("/operator");
  await page
    .getByLabel("Reviewer token")
    .fill(process.env.DUBGUARD_E2E_REVIEW_TOKEN!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Narration reviews" }),
  ).toBeVisible();
  const storage = await page.evaluate(() =>
    JSON.stringify({ ...sessionStorage, ...localStorage }),
  );
  expect(storage).not.toContain(process.env.DUBGUARD_E2E_REVIEW_TOKEN!);
  expect(await page.evaluate(() => document.cookie)).not.toContain(
    "dubguard_operator",
  );
  expect(
    (await page.context().cookies()).find((c) => c.name === "dubguard_operator")
      ?.httpOnly,
  ).toBe(true);
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.goto("/review");
  await expect(
    page.getByRole("heading", { name: "Reviewer access" }),
  ).toBeVisible();
});
