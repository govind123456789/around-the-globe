// Accessibility scan with axe-core in the runner's own Chrome (no ChromeDriver).
// Usage: node scripts/axe-check.mjs http://localhost:8000 / /rankings/ /compare/
import { chromium } from "playwright";
import { AxeBuilder } from "@axe-core/playwright";

const [base, ...paths] = process.argv.slice(2);
const browser = await chromium.launch({ channel: process.env.AXE_CHANNEL || "chrome" });
let failed = 0;
for (const p of paths) {
  const page = await browser.newPage();
  await page.goto(base + p, { waitUntil: "networkidle" });
  const { violations } = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  console.log(`${p}: ${violations.length} violation(s)`);
  for (const v of violations) {
    console.log(`  [${v.impact}] ${v.id}: ${v.help} (${v.nodes.length} node(s))`);
    if (v.impact === "critical" || v.impact === "serious") failed++;
  }
  await page.close();
}
await browser.close();
process.exit(failed ? 1 : 0);
