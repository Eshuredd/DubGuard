import { type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect } from "@playwright/test";

export async function capture(page: Page, name: string) {
  const stage = process.env.DUBGUARD_VISUAL_STAGE || "after";
  const dir = resolve("../reports/phase6", stage);
  mkdirSync(dir, { recursive: true });
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
    await page.screenshot({
      path: `${dir}/${name}-${size}.png`,
      fullPage: true,
    });
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
}
