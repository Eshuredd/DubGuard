// Read-only visual audit: reject every request except GET/HEAD. No credentials.
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
const url = "https://134-209-145-248.sslip.io/test";
const dir = "../reports/phase6/public-baseline";
mkdirSync(dir, { recursive: true });
const browser = await chromium.launch({ channel: "chrome" });
try {
  const context = await browser.newContext();
  await context.route("**/*", route => ["GET", "HEAD"].includes(route.request().method()) ? route.continue() : route.abort());
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", e => errors.push(e.message));
  const response = await page.goto(url, { waitUntil: "networkidle", timeout: 30000 });
  for (const [name, width, height] of [["desktop",1440,1000],["mobile",390,844]]) {
    await page.setViewportSize({width,height});
    await page.screenshot({path:`${dir}/landing-${name}.png`,fullPage:true});
  }
  writeFileSync(`${dir}/audit.json`, JSON.stringify({url, observed_at:new Date().toISOString(), http_status:response.status(), heading:await page.locator("h1").allTextContents(), page_errors:errors, mutations_allowed:false, credentials_submitted:false},null,2));
} finally { await browser.close(); }
