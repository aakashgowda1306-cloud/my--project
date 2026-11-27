// End-to-end smoke test of the MVP, driven in a real Chromium browser.
// Requires: API on :8000 (seeded) and web app on :3000.
// Run from the repo root:  node tests/e2e/mvp-smoke.cjs
const { chromium, devices } = require("playwright");
const path = require("node:path");
const fs = require("node:fs");

const BASE = process.env.WEB_URL || "http://localhost:3000";
const SHOTS = path.join(__dirname, "screenshots");
fs.mkdirSync(SHOTS, { recursive: true });

const results = [];
function check(name, ok, detail = "") {
  results.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
}

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  const consoleErrors = [];
  page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text()));
  page.on("pageerror", (e) => consoleErrors.push(String(e)));
  const failedResponses = [];
  page.on("response", (r) => r.status() >= 400 && failedResponses.push(`${r.status()} ${new URL(r.url()).pathname}`));
  const shot = (name) => page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage: true });

  // 1. Public landing page
  await page.goto(BASE);
  check("landing page shows headline", await page.getByRole("heading", { name: /network that doesn’t exist/ }).isVisible());
  await shot("01-landing");

  // 2. Protected pages redirect to sign-in
  await page.goto(`${BASE}/dashboard`);
  check("signed-out visitor is redirected to /login", page.url().includes("/login?next=%2Fdashboard"));

  // 3. Registration → onboarding → dashboard
  const email = `e2e-${Date.now()}@example.com`;
  await page.goto(`${BASE}/register`);
  await page.fill("#display_name", "Asha Learner");
  await page.fill("#email", email);
  await page.fill("#password", "a-long-e2e-password");
  await page.fill("#confirm", "a-long-e2e-password");
  await page.click("button[type=submit]");
  await page.waitForURL("**/onboarding");
  check("registration leads to onboarding", true);
  check("httpOnly session cookie is set", (await ctx.cookies()).some((c) => c.name === "csa_session" && c.httpOnly));
  check("token is not readable by page JavaScript", !(await page.evaluate(() => document.cookie)).includes("csa_session"));
  await page.getByText("I know the basics").click();
  await page.getByRole("button", { name: "Build a cybersecurity portfolio" }).click();
  await page.getByRole("button", { name: "Go to my dashboard" }).click();
  await page.waitForURL("**/dashboard");
  await page.getByText("Continue learning").waitFor();
  check("dashboard greets learner by name", await page.getByRole("heading", { name: /, Asha/ }).isVisible());
  await shot("02-dashboard");

  // 4. Academy lesson + quiz (CIA triad answers: Integrity, Availability, Encryption)
  await page.getByRole("link", { name: "Open lesson" }).click();
  await page.getByRole("heading", { name: "The CIA triad", exact: true }).waitFor();
  const quiz = page.locator("section[aria-labelledby=quiz-title]");
  await quiz.locator("fieldset").nth(2).waitFor();
  const qs = await quiz.locator("fieldset").all();
  const picks = ["Integrity", "Availability", "Encryption"];
  for (let i = 0; i < 3; i++) await qs[i].getByText(picks[i], { exact: true }).click();
  await page.getByRole("button", { name: "Submit answers" }).click();
  await page.getByText(/3\/3 correct/).waitFor();
  check("quiz is graded server-side (3/3, passed)", await page.getByText(/3\/3 correct \(100%\) — passed/).isVisible());
  await page.getByRole("button", { name: "Mark lesson as complete" }).click();
  await page.getByText("Lesson completed").waitFor();
  check("lesson can be marked complete", true);
  await shot("03-lesson-quiz");

  // 5. Practical exercise graded inline (subnetting lab)
  await page.goto(`${BASE}/academy/computer-networking-basics`);
  await page.getByRole("link", { name: /IP addresses and subnets/ }).click();
  await page.getByRole("heading", { name: "Subnet the finance workstation" }).waitFor();
  check("exercise shows its safety boundary", await page.getByText("Safety restrictions").isVisible());
  await page.getByLabel("Network address").fill("10.20.4.0");
  await page.getByLabel("Broadcast address").fill("10.20.4.255");
  await page.getByLabel("Usable hosts").fill("253");
  await page.getByRole("button", { name: "Check my answer" }).click();
  await page.getByText(/Not quite/).waitFor();
  check("wrong lab answer gets partial credit", await page.getByText("Not quite: 66/100.").isVisible());
  await page.getByLabel("Usable hosts").fill("254");
  await page.getByRole("button", { name: "Check my answer" }).click();
  await page.getByText(/^Correct\./).waitFor();
  check("correct lab answer reveals explanation", await page.getByText(/8 host bits/).isVisible());

  // 6. SOC Operations Centre
  await page.goto(`${BASE}/soc`);
  await page.getByText("Security events").waitFor();
  await page.locator(".main-svg").first().waitFor({ timeout: 15000 });
  check("SOC shows 352 events from the database", await page.getByText("352", { exact: true }).isVisible());
  check("SOC attack chain lists linked alerts", (await page.locator("ol li").count()) >= 8);
  check("Plotly chart rendered", (await page.locator(".main-svg").count()) > 0);
  await shot("04-soc");

  // 7. SIEM explorer, alert investigation, rule run
  await page.goto(`${BASE}/siem`);
  await page.fill("#siem-q", "203.0.113.45");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await page.getByText("19 events match").waitFor();
  check("SIEM search finds 19 events for 203.0.113.45", true);
  await page.locator("table.data-table tbody tr").last().click();
  check("event detail panel opens", await page.getByText("Raw fields").isVisible());
  await shot("05-siem-events");

  await page.getByRole("tab", { name: "Alert queue" }).click();
  await page.getByRole("button", { name: /Backup Operators/ }).click();
  await page.getByRole("button", { name: "Start investigation" }).click();
  await page.getByText("Investigation started.").waitFor();
  await page.fill("#note", "Change ticket CHG-1042 is approved; admin.ops made the change.");
  await page.getByRole("button", { name: "Add note" }).click();
  await page.getByText("Note added.").waitFor();
  await page.getByLabel(/Expected activity/).check();
  await page.fill("#summary", "Approved change CHG-1042 by admin.ops. Expected activity, no further action.");
  await page.getByRole("button", { name: "Close investigation" }).click();
  await page.getByText("Investigation closed.").waitFor();
  check("alert triaged and closed as expected activity", await page.getByText("Status: closed benign").isVisible());
  await shot("06-siem-alert");

  await page.getByRole("tab", { name: "Detection rules" }).click();
  const spray = page.locator("article", { hasText: "CSA-DET-002" });
  await spray.getByRole("button", { name: /Run rule/ }).click();
  await spray.getByText(/1 match/).waitFor();
  check("live rule run returns 1 match for password spraying", true);

  // 8. Progress reflected on the dashboard
  await page.goto(`${BASE}/dashboard`);
  await page.getByText("lessons completed").waitFor();
  const stats = await page.locator("dl").first().innerText();
  check("dashboard counts 1 lesson, 1 quiz, 1 lab, 1 triage", /1\/8[\s\S]*1[\s\S]*1\/10[\s\S]*1/.test(stats), stats.replace(/\n/g, " "));

  check("no console errors or failed requests during normal use", consoleErrors.length === 0 && failedResponses.length === 0,
        [...consoleErrors, ...failedResponses].slice(0, 4).join(" | "));
  consoleErrors.length = 0; failedResponses.length = 0;

  // 9. Backend proxy safety (these requests are SUPPOSED to fail)
  const blocked = await page.evaluate(async () => (await fetch("/api/backend/auth/register", { method: "POST", body: "{}" })).status);
  check("proxy refuses areas outside the allowlist", blocked === 404, `status ${blocked}`);
  const cross = await page.request.post(`${BASE}/api/backend/me`, { headers: { Origin: "https://evil.example" }, data: {} });
  check("proxy blocks cross-site state-changing requests", cross.status() === 403, `status ${cross.status()}`);

  // 10. Mobile layout (Android phone)
  const mobile = await browser.newContext({ ...devices["Pixel 7"] });
  await mobile.addCookies((await ctx.cookies()).filter((c) => c.name === "csa_session"));
  const m = await mobile.newPage();
  await m.goto(`${BASE}/dashboard`);
  await m.getByText("lessons completed").waitFor();
  check("mobile shows bottom tab bar", await m.getByRole("navigation", { name: "Main" }).isVisible());
  check("mobile hides desktop sidebar", !(await m.locator("aside").first().isVisible()));
  await m.screenshot({ path: path.join(SHOTS, "07-mobile-dashboard.png") });
  await m.getByRole("button", { name: "More" }).click();
  check("mobile 'More' sheet opens", await m.getByRole("dialog", { name: "More navigation" }).isVisible());
  await m.goto(`${BASE}/siem`);
  await m.fill("#siem-q", "m.okafor");
  await m.getByRole("button", { name: "Search", exact: true }).click();
  await m.getByText(/events match/).waitFor();
  const overflow = await m.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  check("mobile SIEM has no horizontal overflow", overflow <= 1, `${overflow}px`);
  await m.screenshot({ path: path.join(SHOTS, "08-mobile-siem.png") });

  // 11. Sign out
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.waitForURL("**/login");
  await page.goto(`${BASE}/soc`);
  check("after sign-out protected pages redirect again", page.url().includes("/login"));

  check("only the deliberate security probe produced an error", failedResponses.every((f) => f.startsWith("404 /api/backend/auth")),
        failedResponses.join(" | "));
  await browser.close();
  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} checks passed`);
  process.exit(failed ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
