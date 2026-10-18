// Records genuine DOM interactions against the unmodified local app. No routes are mocked.
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
const require = createRequire(
  new URL("../frontend/package.json", import.meta.url),
);
const { chromium } = require("playwright");
const root = path.resolve(".");
const dest = path.join(root, "demo/private/capture");
fs.mkdirSync(dest, { recursive: true });
const browser = await chromium.launch({ channel: "chrome", headless: true });
const context = await browser.newContext({
  viewport: { width: 1920, height: 1080 },
  recordVideo: { dir: dest, size: { width: 1920, height: 1080 } },
  acceptDownloads: true,
});
const page = await context.newPage();
const started = Date.now(),
  events = [];
const mark = (name) => {
  events.push({ name, seconds: (Date.now() - started) / 1000 });
  fs.writeFileSync(
    path.join(dest, "events.json"),
    JSON.stringify(events, null, 2),
  );
  console.log(name, events.at(-1).seconds);
};
const wait = (ms) => page.waitForTimeout(ms);
// The cursor overlay visualizes real mouse events only and never changes app content.
await page.addInitScript(() => {
  addEventListener("DOMContentLoaded", () => {
    const c = document.createElement("div");
    c.id = "capture-cursor";
    c.style.cssText =
      "position:fixed;width:24px;height:24px;border:2px solid #23b6a3;border-radius:50%;background:#23b6a333;pointer-events:none;z-index:2147483647;left:-50px;top:-50px;box-shadow:0 0 0 5px #ffffff77;";
    document.body.appendChild(c);
    addEventListener("mousemove", (e) => {
      c.style.left = e.clientX - 12 + "px";
      c.style.top = e.clientY - 12 + "px";
    });
    addEventListener("mousedown", () => (c.style.background = "#f5bc55bb"));
    addEventListener("mouseup", () => (c.style.background = "#23b6a333"));
  });
});
async function move(locator) {
  await locator.scrollIntoViewIfNeeded();
  const b = await locator.boundingBox();
  if (b)
    await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2, { steps: 24 });
  await wait(350);
}
async function click(locator) {
  await move(locator);
  await locator.click();
}
async function type(locator, text) {
  await move(locator);
  await locator.fill("");
  await locator.pressSequentially(text, { delay: 65 });
}
async function scroll(locator) {
  await locator.evaluate((e) =>
    e.scrollIntoView({ behavior: "smooth", block: "center" }),
  );
  await wait(1300);
}
try {
  await page.goto("http://127.0.0.1:5182/test");
  await wait(1800);
  mark("landing");
  await page.mouse.move(750, 450, { steps: 30 });
  await wait(17000);
  mark("create");
  await click(
    page.getByRole("link", { name: "Create Your Own Review", exact: true }),
  );
  await wait(1500);
  await click(page.getByRole("button", { name: "Start blank", exact: true }));
  await type(page.getByLabel("Script title"), "Power isolation narration");
  await type(page.getByLabel(/Reference narration/), "Switch the power off.");
  await click(
    page.getByRole("button", { name: "Protect polarity", exact: true }),
  );
  await type(page.getByLabel("Required phrase", { exact: true }), "off");
  await type(page.getByLabel("Dangerous reversal", { exact: true }), "on");
  await wait(2300);
  await click(
    page.getByRole("button", {
      name: "Save reference & demo policy",
      exact: true,
    }),
  );
  await page
    .getByLabel("Workspace update")
    .filter({ hasText: "Reference saved" })
    .waitFor();
  await wait(2200);
  mark("saved");
  await scroll(page.locator("#custom-audio"));
  await wait(1000);
  mark("upload");
  await move(page.getByLabel("Upload audio", { exact: true }));
  await page
    .getByLabel("Upload audio", { exact: true })
    .setInputFiles(path.join(root, "recorded-evaluation/on-off.wav"));
  await wait(3500);
  await scroll(page.getByRole("group", { name: "Preview transport" }));
  mark("preview");
  await click(page.getByRole("button", { name: "Play audio", exact: true }));
  mark("preview-play");
  await wait(4200);
  mark("analyze");
  await click(
    page.getByRole("button", {
      name: "Analyze recording locally",
      exact: true,
    }),
  );
  await page
    .getByRole("heading", { name: "Local verification findings", exact: true })
    .waitFor({ timeout: 90000 });
  mark("result");
  await wait(1500);
  await page.screenshot({ path: path.join(dest, "result.png") });
  const report = await page.evaluate(async () => {
    const token = sessionStorage.getItem("dubguard-custom");
    return await (
      await fetch("/api/workspace/session", {
        headers: { Authorization: "Bearer " + token },
      })
    ).json();
  });
  fs.writeFileSync(
    path.join(dest, "actual-result.json"),
    JSON.stringify(report, null, 2),
  );
  await wait(5500);
  const finding = page
    .locator("article.finding")
    .filter({ hasText: "Potential instruction mismatch" });
  await scroll(finding);
  mark("finding");
  await wait(7000);
  await click(finding.locator("summary"));
  await wait(4000);
  await page.screenshot({ path: path.join(dest, "finding.png") });
  mark("source");
  await click(finding.getByRole("button", { name: /0.00/ }));
  await wait(3200);
  await scroll(page.getByRole("heading", { name: /Recognized narration/ }));
  await wait(3500);
  mark("human");
  await scroll(page.getByRole("group", { name: "Source audio transport" }));
  await click(page.getByRole("button", { name: "Play audio", exact: true }));
  mark("review-play");
  await wait(4000);
  await scroll(page.locator(".visitor-corrections"));
  await wait(6500);
  await page.screenshot({ path: path.join(dest, "human.png") });
  // No listening attestation or human-confirmed evidence is manufactured.
  await scroll(page.getByLabel("Temporary review notes"));
  await type(
    page.getByLabel("Temporary review notes"),
    "Unresolved ASR candidate. Human listening and confirmation required before release.",
  );
  await page
    .getByLabel("Demo decision", { exact: true })
    .selectOption("NEEDS_REVIEW");
  await click(
    page.getByRole("button", {
      name: "Save demo decision & notes",
      exact: true,
    }),
  );
  await wait(3000);
  mark("decision");
  const exportButton = page.getByRole("button", { name: /Export/ });
  await scroll(exportButton);
  await move(exportButton);
  const downloadPromise = page.waitForEvent("download");
  await exportButton.click();
  const download = await downloadPromise;
  await download.saveAs(path.join(dest, "evidence-export.json"));
  mark("export");
  await wait(5000);
  await page.screenshot({ path: path.join(dest, "export.png") });
  mark("end");
} catch (error) {
  await page.screenshot({ path: path.join(dest, "error.png") });
  console.error(error);
  throw error;
} finally {
  const video = page.video();
  await context.close();
  await video.saveAs(path.join(dest, "browser-original.webm"));
  await browser.close();
}
