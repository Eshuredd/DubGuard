import { type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect } from "@playwright/test";

export async function capture(page: Page, name: string) {
  const stage = process.env.DUBGUARD_VISUAL_STAGE || "after";
  const dir = resolve(
    process.env.DUBGUARD_VISUAL_DIR || "../reports/local/ux-refinement",
    stage,
  );
  mkdirSync(dir, { recursive: true });
  await page.evaluate(() => {
    const banner = document.createElement("div");
    banner.id = "development-capture-label";
    banner.textContent =
      "DEVELOPMENT FIXTURE · Fake microphone / synthetic audio · Stub ASR · Mocked AMD when shown";
    banner.style.cssText =
      "padding:8px 12px;margin-bottom:16px;background:#fff2cc;color:#604b20;border:1px solid #d8c48e;border-radius:5px;font:11px/1.5 system-ui,sans-serif";
    document.querySelector("main")?.prepend(banner);
  });
  const original = page.viewportSize();
  for (const [size, width, height] of [
    ["desktop", 1440, 1000],
    ["mobile", 390, 844],
  ] as const) {
    await page.setViewportSize({ width, height });
    if (stage === "after") {
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
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({
      path: `${dir}/${name}-${size}.png`,
      fullPage: true,
    });
    const focus =
      name.includes("evidence") || name === "amd-mocked"
        ? page.locator("#actual-evidence")
        : ["microphone", "recording-preview"].includes(name)
          ? page.locator("#capture-panel")
          : null;
    if (focus && (await focus.count())) {
      await focus.scrollIntoViewIfNeeded();
      await page.screenshot({ path: `${dir}/${name}-focus-${size}.png` });
    }
    if (name === "amd-mocked") {
      await page
        .locator("#amd-findings")
        .screenshot({ path: `${dir}/${name}-findings-${size}.png` });
    }
    if (name === "critical-signoff") {
      await page
        .locator("#approved-script")
        .screenshot({ path: `${dir}/${name}-comparison-${size}.png` });
    }
    if (
      stage === "after" &&
      (name === "critical-signoff" || name === "approved-signoff")
    ) {
      await page
        .locator(".approval-state")
        .screenshot({ path: `${dir}/${name}-explanation-${size}.png` });
    }
  }
  if (original) await page.setViewportSize(original);
  await page.evaluate(() =>
    document.getElementById("development-capture-label")?.remove(),
  );
}
