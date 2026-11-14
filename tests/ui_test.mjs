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
    await page.locator(".job-card").first().waitFor();

    assert.equal(await page.locator(".job-card").count(), 2);
    assert.match(await page.locator("#notices").innerText(), /outdated/i);
    assert.match(await page.locator("#notices").innerText(), /partial/i);
    assert.equal(await page.locator("a.apply-link").first().getAttribute("rel"), "noopener noreferrer");
    assert.equal(await page.locator("a.apply-link").first().getAttribute("target"), "_blank");

    await page.locator("#search-input").fill("finance");
    await page.waitForTimeout(250);
    assert.equal(await page.locator(".job-card").count(), 1);
    assert.match(await page.locator(".job-title").innerText(), /finance/i);

    await page.locator("#search-input").fill("no-such-role");
    await page.waitForTimeout(250);
    assert.equal(await page.locator("#empty-state").isVisible(), true);

    await page.locator("#empty-reset").click();
    await page.locator("#filter-function").selectOption("Marketing");
    assert.equal(await page.locator(".job-card").count(), 1);

    await page.locator("#reset-filters").click();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    assert.equal(overflow, false, `horizontal overflow at ${viewport.width}px`);
    assert.deepEqual(consoleErrors, []);
    await page.close();
  }
} finally {
  await browser.close();
}

console.log("UI fixture checks passed at mobile and desktop viewports.");
