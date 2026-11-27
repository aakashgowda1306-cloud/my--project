// Renders each mockup to PNG for review. Run from the repo root: node design/mockups/render.cjs
const { chromium } = require("playwright");
const path = require("node:path");
const shots = [["landing", 1440, 900, true], ["dashboard", 1440, 960], ["soc", 1440, 1000], ["siem", 1440, 900],
               ["mobile-dashboard", 390, 844], ["mobile-siem", 390, 844]];
(async () => {
  const browser = await chromium.launch();
  for (const [name, width, height, full] of shots) {
    const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 2 });
    await page.goto("file://" + path.join(__dirname, `${name}.html`));
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: path.join(__dirname, "..", "screenshots", `${name}.png`), fullPage: !!full });
    console.log("rendered", name);
  }
  await browser.close();
})();
