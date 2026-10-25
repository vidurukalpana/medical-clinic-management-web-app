// Drives CareFlow like a real user and records it as timestamped frames.
// Usage: node record.js <path to .env.docker> <out dir>
const fs = require("fs");
const path = require("path");
const { BASE, openBrowser, readEnv } = require("./common");

const env = readEnv(process.argv[2]);
const OUT = process.argv[3] || "take";
fs.rmSync(OUT, { recursive: true, force: true });
fs.mkdirSync(path.join(OUT, "frames"), { recursive: true });

const frames = [];   // {file, ts}
const marks = [];    // {ts, kind, value}
const now = () => Date.now() / 1000;
const mark = (kind, value) => { marks.push({ ts: now(), kind, value }); console.log(`[${(now() - T0).toFixed(1)}s] ${kind} ${value ?? ""}`); };
let T0 = now();
let page, mouse = { x: 960, y: 540 };

const wait = (ms) => page.waitForTimeout(ms);
const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

async function moveTo(x, y, ms = 650) {
  const steps = Math.max(12, Math.round(ms / 16));
  const sx = mouse.x, sy = mouse.y;
  // Slight arc, like a hand moving a mouse.
  const cx = (sx + x) / 2 + (y - sy) * 0.08, cy = (sy + y) / 2 - (x - sx) * 0.08;
  for (let i = 1; i <= steps; i++) {
    const t = ease(i / steps);
    const px = (1 - t) * (1 - t) * sx + 2 * (1 - t) * t * cx + t * t * x;
    const py = (1 - t) * (1 - t) * sy + 2 * (1 - t) * t * cy + t * t * y;
    await page.mouse.move(px, py);
    await wait(16);
  }
  mouse = { x, y };
}

async function point(locator, ms) {
  await locator.scrollIntoViewIfNeeded();
  const box = await locator.boundingBox();
  await moveTo(box.x + box.width / 2, box.y + box.height / 2, ms);
  return box;
}

async function click(locator, { ms, pause = 350 } = {}) {
  await locator.waitFor({ state: "visible", timeout: 30000 });
  await point(locator, ms);
  await wait(140);
  await page.mouse.down(); await wait(90); await page.mouse.up();
  await wait(pause);
}

async function type(locator, text, delay = 70) {
  await click(locator, { pause: 150 });
  await locator.pressSequentially(text, { delay });
  await wait(250);
}

// Smooth scroll of the window to an absolute y.
async function scrollTo(y, ms = 1200) {
  const start = await page.evaluate(() => scrollY);
  const steps = Math.round(ms / 16);
  for (let i = 1; i <= steps; i++) {
    await page.evaluate((v) => scrollTo(0, v), start + (y - start) * ease(i / steps));
    await wait(16);
  }
}

const caption = (t) => page.evaluate((t) => window.__demo.caption(t), t);
async function card(opts, hold = 2600) {
  await page.evaluate((o) => window.__demo.card(o), opts);
  mark("card", [].concat(opts.title || opts.kicker || "logo").join(" "));
  await wait(hold);
}
async function hideCard() { await page.evaluate(() => window.__demo.hideCard()); await wait(700); }
async function nav(name) { await click(page.locator(".topnav-links").getByRole("link", { name, exact: true })); }
async function side(name) { await click(page.locator(".sidebar").getByRole("link", { name, exact: true })); await wait(900); }

(async () => {
  const { browser, ctx } = await openBrowser();
  await ctx.addInitScript({ path: path.join(__dirname, "overlay.js") });
  page = await ctx.newPage();

  const cdp = await ctx.newCDPSession(page);
  let n = 0;
  cdp.on("Page.screencastFrame", async ({ data, metadata, sessionId }) => {
    const file = `f${String(n++).padStart(6, "0")}.jpg`;
    fs.writeFile(path.join(OUT, "frames", file), Buffer.from(data, "base64"), () => {});
    frames.push({ file, ts: metadata.timestamp });
    cdp.send("Page.screencastFrameAck", { sessionId }).catch(() => {});
  });

  // Opening title over the home page.
  await page.goto(BASE + "/");
  await page.evaluate(() => sessionStorage.clear());
  await page.evaluate(() => window.__demo.card({}));
  await wait(1200);
  await cdp.send("Page.startScreencast", { format: "jpeg", quality: 92, maxWidth: 1920, maxHeight: 1080, everyNthFrame: 1 });
  T0 = now();
  mark("start");
  await page.mouse.move(1900, 1070);
  mouse = { x: 1900, y: 1070 };
  await wait(700);
  await card({ logo: true, sub: "Skip the waiting room, See your Doctor on time" }, 4200);
  await hideCard();
  mark("intro-done");
  if (process.env.INTRO_ONLY) {
    mark("end");
    await cdp.send("Page.stopScreencast");
    fs.writeFileSync(path.join(OUT, "timeline.json"), JSON.stringify({ frames, marks }, null, 1));
    await browser.close();
    return;
  }

  // ---- Public website ----
  await caption("A simple home page");
  await wait(1500);
  await moveTo(1250, 330, 900);
  await wait(900);
  await scrollTo(620, 1600); await wait(1200);
  await scrollTo(1000, 1400); await wait(1500);
  await point(page.locator(".doctor-card, .doctor-grid > *").first(), 700); await wait(600);
  await scrollTo(0, 1300); await wait(500);

  await caption("All doctors in one place");
  await nav("Doctors"); await wait(1500);
  await scrollTo(450, 1600); await wait(1200); await scrollTo(0, 1000);

  await card({ title: ["Book in", "under a minute"] }, 2400);
  await caption("Find a doctor");
  await hideCard();
  await nav("Book a visit"); await wait(900);
  await type(page.getByLabel("Search doctors"), "General", 90);
  await wait(700);
  await click(page.locator("button.choice").filter({ hasText: "Kasun" }), { pause: 900 });
  await caption("Pick a day and session");
  await wait(600);
  const sessionBtn = page.locator("button.session-option").first();
  await sessionBtn.waitFor({ timeout: 15000 });
  await point(page.locator(".day-chip").nth(1), 700); await wait(500);
  await click(sessionBtn, { pause: 700 });
  await click(page.getByRole("button", { name: "Continue" }), { pause: 700 });
  await caption("Just a name and phone");
  await type(page.getByPlaceholder("e.g. Nimal Perera"), "Sanduni Perera", 75);
  await type(page.getByPlaceholder("+94 77 123 4567"), "+94 77 482 6150", 75);
  await click(page.getByText("Remember on this device"), { pause: 400 });
  await click(page.getByRole("button", { name: "Confirm booking" }), { pause: 300 });
  await page.getByRole("heading", { name: "You're booked!" }).waitFor({ timeout: 30000 });
  await caption("Booked, with a QR code");
  mark("booked");
  const checkinCode = await page.evaluate(() => {
    const el = document.querySelector(".checkin-qr figcaption strong");
    return el ? el.textContent.trim() : null;
  });
  await wait(2200);
  await scrollTo(380, 1500); await wait(2200);
  await point(page.getByRole("button", { name: "Copy code" }), 700);
  await wait(800);
  await scrollTo(0, 900);

  // Live queue for patients.
  await caption("Follow the live queue");
  await nav("Live queue"); await wait(3200);
  await moveTo(900, 420, 800); await wait(1500);

  // Chat assistant.
  await card({ title: ["Questions answered", "instantly"] }, 2400);
  await hideCard();
  await caption("Ask the clinic assistant");
  await click(page.getByRole("button", { name: "Ask a question" }), { pause: 500 });
  await page.evaluate(() => window.__demo.chatFocus(true));
  await wait(1300);
  // One natural conversation. Each answer is checked, because a small local model sometimes gets details wrong.
  const QUESTIONS = [
    ["Hi! I would like to bring my daughter to see a doctor. Who is the paediatrician?", (r) => /Ayesha/.test(r) && !/contact|reception|phone|call|email/i.test(r)],
    ["What are Dr. Ayesha Fernando's consultation hours?", (r) => /Monday/.test(r) && /Wednesday/.test(r) && /17:00|5:00|5 ?PM/i.test(r) && !/Tuesday|Thursday|Friday|Saturday|Sunday|also|separate|not listed/i.test(r)],
    ["How much is the consultation fee?", (r) => /2,?500/.test(r) && !/Ruwan|Priya|Kasun|also/i.test(r)],
    ["Do I need an account to book?", (r) => /\bno\b|don't need|do not need|not need/i.test(r) && !/phone|sent|email|SMS|call/i.test(r)],
    ["Great, thank you!", (r) => r.length > 0],
  ];
  const answers = page.locator(".chat-bubble.is-assistant:not(.chat-typing)");
  for (const [i, [question, isRight]] of QUESTIONS.entries()) {
    await type(page.getByLabel("Your question"), question, 55);
    await page.keyboard.press("Enter");
    mark("fast", 6);
    await page.waitForFunction((n) => document.querySelectorAll(".chat-bubble.is-assistant:not(.chat-typing)").length >= n && !document.querySelector(".chat-typing"), i + 2, { timeout: 180000 });
    mark("fast", 1);
    const reply = await answers.nth(i + 1).innerText();
    mark("chat", `${question} -> ${reply}`);
    if (!isRight(reply)) throw new Error(`CHAT_CHECK_FAILED: ${question}`);
    await wait(Math.min(5200, 2200 + reply.length * 22));
  }
  await page.evaluate(() => window.__demo.chatFocus(false));
  await wait(800);
  await click(page.getByRole("button", { name: "Close chat" }).first(), { pause: 400 });

  // ---- Staff portal ----
  await card({ title: ["One portal for", "the clinic"] }, 2400);
  await caption(null);
  await hideCard();
  await click(page.getByRole("link", { name: "Sign in" }), { pause: 700 });
  await caption("Staff sign in");
  await type(page.getByLabel("Username"), env.CLINIC_ADMIN_USERNAME, 90);
  await click(page.getByLabel("Password"), { pause: 100 });
  await page.getByLabel("Password").pressSequentially(env.CLINIC_ADMIN_PASSWORD, { delay: 45 });
  await page.keyboard.press("Enter");
  await page.waitForURL(/staff|my-bookings|\/$/, { timeout: 20000 }).catch(() => {});
  if (!page.url().includes("/staff")) { await page.goto(BASE + "/staff"); }
  await page.locator(".stat-value").first().waitFor({ timeout: 20000 });
  await caption("Today at a glance");
  await wait(2600);
  await moveTo(700, 260, 900); await wait(500); await moveTo(1400, 260, 900); await wait(700);

  await caption("Doctor arrives");
  await scrollTo(380, 1000);
  await click(page.getByRole("button", { name: "Doctor arrived" }).last(), { pause: 1400 });

  await caption("Patients check in");
  for (let i = 0; i < 2; i++) {
    await click(page.locator(".dash-appointments, .card").getByRole("button", { name: "Check in" }).first(), { pause: 1500 });
  }

  await caption("Or scan their QR code");
  await scrollTo(0, 900);
  await click(page.getByRole("button", { name: /Scan check-in/ }), { pause: 900 });
  if (checkinCode) {
    await type(page.getByLabel("Check-in code"), checkinCode, 40);
  } else {
    mark("warn", "no check-in code captured");
  }
  await page.keyboard.press("Enter");
  await wait(1600);
  await click(page.getByRole("button", { name: /^Check in No\./ }), { pause: 1800 });
  if (!page.url().endsWith("/staff")) { await side("Dashboard"); }
  const closeDialog = page.getByRole("dialog").getByRole("button", { name: /Close|Done/ }).first();
  if (await closeDialog.count()) await click(closeDialog, { pause: 800 });

  await caption("Call the next patient");
  await scrollTo(380, 1000);
  await click(page.getByRole("button", { name: "Start" }).first(), { pause: 1800 });
  await point(page.locator(".now-serving").first(), 700); await wait(1600);
  const done = page.locator(".now-serving").first().getByRole("button").first();
  await click(done, { pause: 1800 });
  await click(page.getByRole("button", { name: "Start" }).first(), { pause: 2200 });

  await caption("The live queue updates");
  await page.goto(BASE + "/live"); await wait(3500);
  await moveTo(820, 460, 800); await wait(1800);
  await page.goBack(); await page.locator(".stat-value").first().waitFor({ timeout: 20000 });
  await wait(500);

  // Appointments, patients, schedule.
  await caption("Manage appointments");
  await side("Appointments"); await wait(1500);
  await scrollTo(500, 1800); await wait(900); await scrollTo(0, 1000);
  await point(page.getByRole("button", { name: "Move" }).first(), 700); await wait(900);

  await caption("Search patients");
  await side("Patients"); await wait(1200);
  const search = page.getByPlaceholder(/Search/i).first();
  if (await search.count()) { await type(search, "Perera", 90); await wait(1600); }

  await caption("Plan the schedule");
  await side("Schedule"); await wait(1000);
  const docSelect = page.locator("select").first();
  await point(docSelect, 600);
  await docSelect.selectOption({ label: "Dr. Priya Raman" }).catch(() => {});
  await wait(2200);
  await moveTo(1100, 260, 900); await wait(1200);

  // Admin areas.
  await caption("Manage doctors");
  await side("Doctors"); await wait(1600); await scrollTo(400, 1400); await wait(600); await scrollTo(0, 800);
  await caption("Staff accounts");
  await side("Accounts"); await wait(2200);
  await caption("SMS outbox");
  await side("SMS outbox"); await wait(2200);

  // ---- Doctor ----
  await card({ title: ["Made for", "doctors"] }, 2400);
  await page.locator(".sidebar").getByRole("button", { name: "Sign out" }).click();
  await wait(1200);
  if (!page.url().includes("/login")) await page.goto(BASE + "/login");
  await page.getByLabel("Username").waitFor();
  await hideCard();
  await caption("Doctor signs in");
  await type(page.getByLabel("Username"), "demo.kasun", 90);
  await click(page.getByLabel("Password"), { pause: 100 });
  await page.getByLabel("Password").pressSequentially(JSON.parse(env.CLINIC_DEMO_DOCTOR_PASSWORDS)["demo.kasun"], { delay: 45 });
  await page.keyboard.press("Enter");
  await page.waitForURL(/staff/, { timeout: 20000 }).catch(() => {});
  if (!page.url().includes("/staff")) await page.goto(BASE + "/staff");
  await page.locator(".stat-value").first().waitFor({ timeout: 20000 });
  await caption("Their own queue");
  await wait(2600);
  await scrollTo(380, 1000); await wait(600);
  await caption("Next patient, please");
  await click(page.locator(".now-serving").first().getByRole("button").first(), { pause: 1600 });
  await click(page.getByRole("button", { name: "Start" }).first(), { pause: 2200 });
  await scrollTo(0, 800);

  await caption("Their patients");
  await side("Patients"); await wait(1800);
  await moveTo(900, 420, 800); await wait(900);

  await caption("Edit their profile");
  await click(page.locator('.sidebar a[href="/staff/account"]').first(), { pause: 1200 });
  const languages = page.getByLabel("Languages");
  await click(languages, { pause: 200 });
  await page.keyboard.press("End");
  await languages.pressSequentially(", Tamil", { delay: 90 });
  await wait(500);
  const about = page.getByLabel("About");
  await click(about, { pause: 200 });
  await page.keyboard.press("ControlOrMeta+End");
  await about.pressSequentially(" Walk-ins are welcome.", { delay: 60 });
  await wait(600);
  await click(page.getByRole("button", { name: "Save profile" }), { pause: 2000 });

  await caption("Live on the website");
  await page.goto(BASE + "/doctors");
  const kasunCard = page.locator(".doctor-card").filter({ hasText: "Kasun" }).first();
  await kasunCard.waitFor({ timeout: 15000 });
  await kasunCard.evaluate((el) => el.scrollIntoView({ block: "center", behavior: "smooth" }));
  await wait(1400);
  await point(kasunCard.getByText("Tamil").first(), 900);
  await wait(2400);


  await caption(null);
  await wait(500);

  await card({ logo: true, sub: "Skip the waiting room, See your Doctor on time",
    chips: ["Online booking", "Live queue", "QR check-in", "AI assistant", "Staff portal", "Doctor portal"] }, 5200);
  mark("end");
  await cdp.send("Page.stopScreencast");
  await wait(500);
  fs.writeFileSync(path.join(OUT, "timeline.json"), JSON.stringify({ frames, marks }, null, 1));
  console.log(`frames: ${frames.length}, duration ${(marks.at(-1).ts - marks[0].ts).toFixed(1)}s`);
  await browser.close();
})().catch(async (e) => {
  console.error(e);
  fs.writeFileSync(path.join(OUT, "timeline.json"), JSON.stringify({ frames, marks, error: String(e) }, null, 1));
  try { await page.screenshot({ path: path.join(OUT, "error.png") }); } catch {}
  process.exit(String(e).includes("CHAT_CHECK_FAILED") ? 2 : 1);
});
