import { capture } from "./capture";
import { readFileSync } from "node:fs";
import AxeBuilder from "@axe-core/playwright";
import { test, expect, type Page } from "@playwright/test";
function wav() {
  const b = Buffer.alloc(44 + 32000);
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
async function login(page: Page) {
  await page.goto("/login");
  await page
    .getByLabel("Reviewer token")
    .fill(process.env.DUBGUARD_E2E_REVIEW_TOKEN!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Narration reviews" }),
  ).toBeVisible();
}
async function newReview(page: Page) {
  await login(page);
  await capture(page, "dashboard");
  await page.getByRole("link", { name: "Scripts & policies" }).click();
  await page.getByRole("button", { name: "Save policy draft" }).click();
  await capture(page, "policy-editor");
  await expect(page.getByRole("status")).toContainText("Draft saved");
  await page.getByLabel("I reviewed the saved instructions").check();
  await page
    .getByRole("button", { name: "Approve saved policy revision" })
    .click();
  await expect(page.getByRole("status")).toContainText("explicitly approved");
  await page.goto("/review/new");
  await page.getByLabel("Approved script & policy").selectOption({ index: 1 });
  await page.getByLabel("Upload audio", { exact: true }).setInputFiles({
    name: "recording.wav",
    mimeType: "audio/wav",
    buffer: wav(),
  });
  await page
    .getByRole("button", { name: "Create review", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Transcribe original audio" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Transcribe original audio" }).click();
  await expect(
    page.getByRole("heading", { name: "Human transcript evidence" }),
  ).toBeVisible();
}
async function correct(page: Page, text: string) {
  await page.getByLabel("Actual spoken text").fill(text);
  await page
    .getByLabel("Instruction mapping", { exact: true })
    .selectOption("step-1");
  await page.getByLabel("Still unclear or uncertain").uncheck();
  await page.getByLabel("I listened to the original audio and entered").check();
  await page.getByLabel("I reviewed the entire recording").check();
  await page
    .getByLabel("Correction / verification reason")
    .fill(
      "Browser protocol test; silent fixture and stub ASR, not real human speech.",
    );
  await page
    .getByRole("button", { name: "Save human evidence revision" })
    .click();
  await expect(page.getByRole("status")).toContainText("Human evidence saved");
  await page.getByRole("button", { name: "Verify with local rules" }).click();
  await expect(
    page.getByRole("heading", { name: "Verification findings" }),
  ).toBeVisible();
}

test("real MediaRecorder on fake device → private Quick Test → refresh and delete", async ({
  page,
}) => {
  await page.goto("/test");
  await capture(page, "landing");
  await page
    .getByLabel("Demo access code")
    .fill(process.env.DUBGUARD_E2E_DEMO_CODE!);
  await page.getByRole("button", { name: "Start Quick Test" }).click();
  await capture(page, "scenarios");
  await expect(
    page.getByRole("button", { name: "Record narration" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Record narration" }).click();
  await page
    .getByRole("button", { name: "Start recording", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText("Recording");
  await expect(
    page.getByRole("meter", { name: "Microphone input level" }),
  ).toBeVisible();
  await page.waitForTimeout(650);
  await capture(page, "microphone");
  await page
    .getByRole("button", { name: "Stop recording", exact: true })
    .click();
  await expect(
    page.getByRole("group", { name: "Preview transport", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Recording preview")).toHaveAttribute(
    "src",
    /^blob:/,
  );
  await expect(page.getByRole("meter")).toHaveCount(0);
  await expect(page.getByText("narration.webm")).toBeVisible();
  const transport = page.getByRole("group", {
    name: "Preview transport",
    exact: true,
  });
  await transport.getByLabel("Playback speed").selectOption("1.25");
  await expect(page.getByLabel("Recording preview")).toHaveJSProperty(
    "playbackRate",
    1.25,
  );
  await transport
    .getByRole("button", { name: "Play audio", exact: true })
    .click();
  await expect(page.getByLabel("Recording preview")).toHaveJSProperty(
    "paused",
    false,
  );
  await transport
    .getByRole("button", { name: "Pause audio", exact: true })
    .click();
  await expect(page.getByLabel("Recording preview")).toHaveJSProperty(
    "paused",
    true,
  );
  await capture(page, "recording-preview");
  const original = await page
    .getByLabel("Recording preview")
    .evaluate(async (el) =>
      Array.from(
        new Uint8Array(
          await (await fetch((el as HTMLAudioElement).src)).arrayBuffer(),
        ),
      ),
    );
  const downloading = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download Original Recording" }).click();
  const download = await downloading;
  expect(download.suggestedFilename()).toBe("dubguard-correct-original.webm");
  expect(readFileSync((await download.path())!)).toEqual(Buffer.from(original));
  await page.getByRole("button", { name: "Analyze recording" }).click();
  await expect(
    page.getByRole("heading", { name: "Verification findings" }),
  ).toBeVisible();
  await expect(
    page.getByText("Recognized narration · provisional", { exact: true }),
  ).toBeVisible();
  await page
    .getByText("Source evidence & audit details", { exact: true })
    .click();
  await expect(
    page.getByText("Raw ASR · unverified", { exact: true }),
  ).toBeVisible();
  await page
    .getByText("Source evidence & audit details", { exact: true })
    .click();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Verification findings" }),
  ).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  await capture(page, "local-evidence");
  await page.screenshot({
    path: "test-results/quick-test.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Delete session and audio" }).click();
  await expect(
    page.getByRole("button", { name: "Start Quick Test" }),
  ).toBeVisible();
});

test("Quick Test AMD consent, mocked citation evidence, invalid citations and quota", async ({
  page,
}) => {
  await page.goto("/test");
  await capture(page, "landing");
  await page
    .getByLabel("Demo access code")
    .fill(process.env.DUBGUARD_E2E_DEMO_CODE!);
  await page.getByRole("button", { name: "Start Quick Test" }).click();
  await capture(page, "scenarios");
  await expect(page.getByLabel("Verification mode")).toHaveValue("local");
  await page.getByLabel("Upload audio", { exact: true }).setInputFiles({
    name: "protocol.wav",
    mimeType: "audio/wav",
    buffer: wav(),
  });
  await page.getByLabel("Verification mode").selectOption("amd");
  await page
    .getByLabel("AMD demo access code")
    .fill(process.env.DUBGUARD_E2E_AMD_CODE!);
  await expect(
    page.getByRole("button", { name: "Analyze recording" }),
  ).toBeDisabled();
  await page.getByLabel("I consent to sending script").check();
  await page.getByRole("button", { name: "Analyze recording" }).click();
  await page.getByRole("button", { name: /^Inspect amd finding 1:/ }).click();
  await expect(
    page.getByRole("heading", { name: "AMD semantic findings" }),
  ).toBeVisible();
  await page.getByText("AMD model & consent details", { exact: true }).click();
  await expect(
    page.getByText(/Returned model: playwright-mock-no-real-AMD/),
  ).toBeVisible();
  await expect(
    page.getByText(/Analyzed mode: AMD Semantic Review/),
  ).toBeVisible();
  await page
    .getByLabel("AMD Semantic Review result", { exact: true })
    .getByText("Provider request details", { exact: true })
    .click();
  await expect(page.getByText(/1 HTTP attempts/)).toBeVisible();
  await expect(
    page.getByText(/Mocked HTTP, not actual AMD inference/),
  ).toBeVisible();
  await expect(
    page.getByLabel("I consent to sending script"),
  ).not.toBeChecked();
  const a11y = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(a11y.violations).toEqual([]);
  await capture(page, "amd-mocked");
  await page.screenshot({
    path: "test-results/quick-amd-mocked.png",
    fullPage: true,
  });
  await page.reload();
  await page.getByRole("button", { name: /^Inspect amd finding 1:/ }).click();
  await expect(
    page.getByRole("heading", { name: "AMD semantic findings" }),
  ).toBeVisible();
  await expect(page.getByLabel("Verification mode")).toHaveValue("local");
  await page.getByRole("button", { name: "15 versus 50", exact: true }).click();
  await page.getByLabel("Verification mode").selectOption("amd");
  await page
    .getByLabel("AMD demo access code")
    .fill(process.env.DUBGUARD_E2E_AMD_CODE!);
  await page.getByLabel("Upload audio", { exact: true }).setInputFiles({
    name: "protocol.wav",
    mimeType: "audio/wav",
    buffer: wav(),
  });
  await page.getByLabel("I consent to sending script").check();
  await page.getByRole("button", { name: "Analyze recording" }).click();
  await expect(page.getByText(/Status: invalid citations/)).toBeVisible();
  await expect(
    page.getByText(/invalid requirement, source reference/),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Verification findings", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Upload audio", { exact: true }).setInputFiles({
    name: "protocol.wav",
    mimeType: "audio/wav",
    buffer: wav(),
  });
  await page.getByLabel("I consent to sending script").check();
  await expect(
    page.getByRole("button", { name: "Analyze recording" }),
  ).toBeDisabled();
  await page.getByLabel("Verification mode").selectOption("local");
  await expect(
    page.getByRole("button", { name: "Analyze recording" }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Delete session and audio" }).click();
});

test("full review policy approval, upload, tentative mapping, correction, critical block and explicit signoff", async ({
  page,
}) => {
  await newReview(page);
  await page.getByRole("button", { name: "Propose alignment" }).click();
  await expect(page.getByText(/asr-1 → step-1/)).toBeVisible();
  await page.getByLabel("Map asr-1").selectOption("step-1");
  await page
    .getByLabel("Review note / action reason")
    .fill("Mapped actual source segment.");
  await page.getByRole("button", { name: "Confirm selected mappings" }).click();
  await expect(
    page.getByText("Reviewer-confirmed raw-ASR mapping is saved.", {
      exact: false,
    }),
  ).toBeVisible();
  await correct(page, "Switch the power on.");
  await expect(
    page.getByRole("button", { name: "Approve recording", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByText("critical deviation", { exact: true }),
  ).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  await capture(page, "critical-signoff");
  await page.screenshot({
    path: "test-results/critical-review.png",
    fullPage: true,
  });
  await correct(page, "Switch the power off.");
  await page.getByRole("button", { name: "Recheck protected audio" }).click();
  await expect(
    page.getByRole("heading", { name: "Independent acoustic evidence" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Approve recording", exact: true }),
  ).toBeDisabled();
  await page
    .getByLabel("Review note / action reason")
    .fill("Resolved stub acoustic conflict against verified test transcript.");
  await page.getByLabel("I listened to every affected source span").check();
  await page
    .getByRole("button", { name: "Resolve against saved human evidence" })
    .click();
  await expect(page.getByRole("status")).toContainText("Saved");
  await page.getByRole("button", { name: "Verify with local rules" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Deterministic verification completed",
  );
  await page
    .getByLabel("Review note / action reason")
    .fill("Reviewed each satisfied check.");
  const buttons = page.getByRole("button", { name: "Mark check reviewed" });
  for (let i = 0; i < (await buttons.count()); i++) {
    await buttons.nth(i).click();
    await expect(page.getByRole("status")).toContainText("Saved");
  }
  await page
    .getByLabel("Final decision reason")
    .fill("Explicit simulated reviewer decision on test evidence.");
  await page.getByLabel("I am making an explicit human decision").check();
  await expect(
    page.getByRole("button", { name: "Approve recording", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Approve recording", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText(
    "Human approval recorded",
  );
  await capture(page, "approved-signoff");
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Approve recording", exact: true }),
  ).toBeDisabled();
  await page.getByRole("link", { name: "All reviews", exact: false }).click();
  await expect(
    page.getByRole("heading", { name: "Narration reviews" }),
  ).toBeVisible();
  await page.goBack();
  await expect(
    page.getByRole("heading", { name: "Audit & evidence history" }),
  ).toBeVisible();
});

test("authentication failure and signout remove privileged access", async ({
  page,
}) => {
  await page.goto("/review");
  await expect(
    page.getByRole("heading", { name: "Reviewer access" }),
  ).toBeVisible();
  await page.getByLabel("Reviewer token").fill("invalid-token");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("401");
  await login(page);
  await capture(page, "dashboard");
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.goto("/review");
  await expect(
    page.getByRole("heading", { name: "Reviewer access" }),
  ).toBeVisible();
});

test("microphone denied and unavailable states are explicit", async ({
  page,
}) => {
  await login(page);
  await capture(page, "dashboard");
  await page.goto("/review/new");
  await page.evaluate(() => {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: async () => {
          throw new DOMException("denied", "NotAllowedError");
        },
      },
    });
  });
  await page.getByRole("button", { name: "Record narration" }).click();
  await expect(page.getByRole("alert")).toContainText("permission denied");
  await page.evaluate(() => {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: undefined,
    });
  });
  await page.getByRole("button", { name: "Record narration" }).click();
  await expect(page.getByRole("alert")).toContainText("unavailable");
});

test("stale verification is rejected by real API and mobile layout stays usable", async ({
  page,
}) => {
  await newReview(page);
  await correct(page, "Switch the power off.");
  const wid = page.url().split("/").pop();
  const headers = {
    Authorization: "Bearer " + process.env.DUBGUARD_E2E_REVIEW_TOKEN,
  };
  const prior = await (
    await page.request.get("/api/review/workflows/" + wid, { headers })
  ).json();
  await page.getByRole("button", { name: "Verify with local rules" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Deterministic verification completed",
  );
  const stale = await page.request.post(
    "/api/review/workflows/" + wid + "/signoff",
    {
      headers,
      data: {
        verification_record_id: prior.workflow.verification_record_id,
        decision: "APPROVED",
        reason: "Stale test attempt",
      },
    },
  );
  expect(stale.status()).toBe(409);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("heading", { name: "Verification findings" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: "test-results/mobile-review.png",
    fullPage: true,
  });
});

test("accessibility audit on Quick Test and full evidence workspace", async ({
  page,
}) => {
  await page.goto("/test");
  await capture(page, "landing");
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await newReview(page);
  await correct(page, "Switch the power on.");
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
});

test("unsaved spoken-text edits block approval and verification", async ({
  page,
}) => {
  await newReview(page);
  await correct(page, "Switch the power off.");
  await page.getByLabel("Actual spoken text").fill("Switch the power on.");
  await expect(
    page.getByRole("button", { name: "Verify with local rules" }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Approve recording", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByText("Unsaved transcript edits.", { exact: false }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Discard unsaved transcript edits" })
    .click();
  await expect(page.getByLabel("Actual spoken text")).toHaveValue(
    "Switch the power off.",
  );
  await expect(
    page.getByRole("button", { name: "Verify with local rules" }),
  ).toBeEnabled();
});

test("keyboard navigation reaches the demo and changes scenario without a pointer", async ({
  page,
}) => {
  await page.goto("/test");
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to content" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await page.getByLabel("Demo access code").focus();
  await page.keyboard.type(process.env.DUBGUARD_E2E_DEMO_CODE!);
  await page.keyboard.press("Enter");
  const scenario = page.getByRole("button", {
    name: "15 versus 50",
    exact: true,
  });
  await expect(scenario).toBeVisible();
  await scenario.focus();
  await page.keyboard.press("Space");
  await expect(scenario).toHaveAttribute("aria-pressed", "true");
  await page
    .getByRole("link", { name: "Record or upload", exact: true })
    .focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#capture-panel")).toBeFocused();
  await page.setViewportSize({ width: 320, height: 800 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "Delete session and audio" }).click();
  await page.locator(".mobile-navigation > summary").focus();
  await page.keyboard.press("Enter");
  await expect(page.locator(".mobile-navigation")).toHaveJSProperty(
    "open",
    true,
  );
  await page
    .getByRole("navigation", { name: "Mobile workspace" })
    .getByRole("link", { name: "Policies", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Reviewer access" }),
  ).toBeVisible();
  await expect(page.locator(".mobile-navigation")).toHaveJSProperty(
    "open",
    false,
  );
});

test("recoverable connection errors, queue filters and narrow keyboard evidence disclosure", async ({
  page,
}) => {
  await page.route("**/api/quick/config", (route) =>
    route.fulfill({ status: 503, json: { detail: "Temporary test outage" } }),
  );
  await page.goto("/test");
  await expect(page.getByRole("alert")).toContainText("Temporary test outage");
  await page.unroute("**/api/quick/config");
  await page.getByRole("button", { name: "Reload session status" }).click();
  await page
    .getByLabel("Demo access code")
    .fill(process.env.DUBGUARD_E2E_DEMO_CODE!);
  await page.getByRole("button", { name: "Start Quick Test" }).click();
  await page.getByRole("button", { name: "15 versus 50", exact: true }).click();
  await page.getByLabel("Upload audio", { exact: true }).setInputFiles({
    name: "synthetic.wav",
    mimeType: "audio/wav",
    buffer: wav(),
  });
  await page.route("**/api/quick/audio", (route) =>
    route.fulfill({ status: 503 }),
  );
  await page.getByRole("button", { name: "Analyze recording" }).click();
  await expect(page.getByRole("button", { name: "Retry audio" })).toBeVisible();
  await page.unroute("**/api/quick/audio");
  await page.getByRole("button", { name: "Retry audio" }).click();
  await expect(
    page.getByRole("group", { name: "Source audio transport", exact: true }),
  ).toBeVisible();
  await expect(
    page.locator(".narration-comparison mark").first(),
  ).toBeVisible();
  await expect(
    page.getByText(/Text differences are not confirmed spoken errors/),
  ).toBeVisible();
  const findingSelection = page
    .getByRole("button", { name: /^Inspect local finding/ })
    .last();
  await findingSelection.click();
  await expect(findingSelection).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("#selected-evidence")).toBeFocused();
  await page.getByLabel("Search narration lines").fill("Switch");
  await expect(page.locator(".search-line")).toHaveCount(1);
  await page.getByLabel("Search narration lines").fill("");
  const source = page.getByText("Source evidence & audit details", {
    exact: true,
  });
  await source.focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByText("Raw ASR · unverified", { exact: true }),
  ).toBeVisible();
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const width of [320, 768, 1440]) {
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
  await page.locator("#local-findings").scrollIntoViewIfNeeded();
  expect(
    await page
      .locator(".original-player")
      .evaluate((el) => getComputedStyle(el).position),
  ).toBe("sticky");
  await page.getByRole("button", { name: "Delete session and audio" }).click();
  await login(page);
  await page
    .getByLabel("Search scripts on this page")
    .fill("no-matching-script-fixture");
  await expect(
    page.getByText(/matching “no-matching-script-fixture”/),
  ).toBeVisible();
  await page.getByRole("button", { name: "Clear filters" }).click();
  await expect(page.getByLabel("Search scripts on this page")).toHaveValue("");
  await page.route("**/api/review/workflows?*", (route) =>
    route.fulfill({
      status: 503,
      json: { detail: "Queue connection interrupted" },
    }),
  );
  await page.reload();
  await expect(page.getByRole("alert")).toContainText(
    "Queue connection interrupted",
  );
  await expect(page.getByText("No reviews yet")).toHaveCount(0);
  await page.unroute("**/api/review/workflows?*");
  await page.getByRole("button", { name: "Retry loading reviews" }).click();
  await expect(page.locator(".review-row").first()).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await page.getByRole("link", { name: "Overview", exact: true }).click();
  await expect(page.locator("#workspace-overview")).toBeVisible();
  await page.getByRole("link", { name: "Review history", exact: true }).click();
  await expect(page.getByLabel("Show reviews on this page")).toHaveValue(
    "history",
  );
});
