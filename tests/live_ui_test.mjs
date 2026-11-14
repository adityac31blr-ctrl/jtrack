import { chromium } from "playwright";
import assert from "node:assert/strict";

const base = process.env.UI_BASE_URL || "http://127.0.0.1:8765";
const browser = await chromium.launch({ headless: true });

try {
  for (const viewport of [{ width: 360, height: 800 }, { width: 1280, height: 900 }]) {
    const page = await browser.newPage({ viewport });
    const consoleErrors = [];
    page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
    await page.goto(base, { waitUntil: "networkidle" });
    await page.locator("#loading-state").waitFor({ state: "hidden" });
    const snapshot = await page.evaluate(() => fetch("./data/jobs.json", { cache: "no-cache" }).then((response) => response.json()));
    assert.equal(await page.locator(".job-card").count(), Math.min(snapshot.stats.total, 12));
    assert.equal(await page.locator("#stat-total").innerText(), String(snapshot.stats.total));
    if (snapshot.stats.total > 0) {
      assert.equal(await page.locator("a.apply-link").first().getAttribute("rel"), "noopener noreferrer");
      assert.equal(await page.locator("a.apply-link").first().getAttribute("target"), "_blank");
      assert.match(await page.locator(".source-credit").first().innerText(), /^Source:/);
    } else {
      assert.equal(await page.locator("#empty-state").isVisible(), true);
    }
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    assert.equal(overflow, false, `horizontal overflow at ${viewport.width}px`);
    assert.deepEqual(consoleErrors, []);
    await page.close();
  }
} finally {
  await browser.close();
}

console.log("Live-data UI checks passed at mobile and desktop viewports.");
