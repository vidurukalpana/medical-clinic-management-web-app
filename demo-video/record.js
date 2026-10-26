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

async function moveTo(x, y, ms = 360) {
  const steps = Math.max(8, Math.round(ms / 16));
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

async function click(locator, { ms, pause = 250 } = {}) {
  await locator.waitFor({ state: "visible", timeout: 30000 });
  await point(locator, ms);
  await wait(60);
  await page.mouse.down(); await wait(60); await page.mouse.up();
  await wait(pause);
}

async function type(locator, text, delay = 40) {
  await click(locator, { pause: 80 });
  await locator.pressSequentially(text, { delay });
  await wait(150);
}

// Smooth scroll of the window to an absolute y.
async function scrollTo(y, ms = 700) {
  const start = await page.evaluate(() => scrollY);
  const steps = Math.round(ms / 16);
  for (let i = 1; i <= steps; i++) {
    await page.evaluate((v) => scrollTo(0, v), start + (y - start) * ease(i / steps));
    await wait(16);
  }
}

const caption = (t) => page.evaluate((t) => window.__demo.caption(t), t);
async function card(opts, hold = 1900) {
  await page.evaluate((o) => window.__demo.card(o), opts);
  mark("card", [].concat(opts.title || opts.kicker || "logo").join(" "));
  await wait(hold);
}
async function hideCard() { await page.evaluate(() => window.__demo.hideCard()); await wait(450); }
async function nav(name) { await click(page.locator(".topnav-links").getByRole("link", { name, exact: true })); }
async function side(name) { await click(page.locator(".sidebar").getByRole("link", { name, exact: true })); await wait(500); }
// A section starts with a title card naming the feature; the page underneath changes while it is up.
async function section(title, prepare) {
  await card({ title });
  if (prepare) await prepare();
  await hideCard();
}

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
  await card({ logo: true, sub: "Skip the waiting room, See your Doctor on time" }, 4300);
  await hideCard();
  mark("intro-done");
  if (process.env.INTRO_ONLY) {
    mark("end");
    await cdp.send("Page.stopScreencast");
    fs.writeFileSync(path.join(OUT, "timeline.json"), JSON.stringify({ frames, marks }, null, 1));
    await browser.close();
    return;
  }

  // ---- Home page ----
  await caption("A simple home page");
  await wait(1600);
  await scrollTo(620, 800); await wait(1000);
  await scrollTo(1000, 700); await wait(1000);
  await scrollTo(1500, 700); await wait(900);
  await scrollTo(0, 700);

  // ---- Find the right doctor ----
  await section(["Find the right", "doctor"]);
  await caption("Doctors, hours and fees");
  await nav("Doctors");
  await page.locator(".doctor-card").first().waitFor();
  await scrollTo(420, 800); await wait(900);
  if (process.env.UNTIL_BOOKING) {
    mark("cut");
    await cdp.send("Page.stopScreencast");
    fs.writeFileSync(path.join(OUT, "timeline.json"), JSON.stringify({ frames, marks }, null, 1));
    await browser.close();
    return;
  }

  // ---- Booking ----
  await section(["Book a visit in", "under a minute"], async () => { await scrollTo(0, 10); });
  await caption("Pick a doctor");
  await nav("Book a visit");
  await type(page.getByLabel("Search doctors"), "General", 55);
  await click(page.locator("button.choice").filter({ hasText: "Kasun" }), { pause: 500 });
  await caption("Pick a day and session");
  const sessionBtn = page.locator("button.session-option").first();
  await sessionBtn.waitFor({ timeout: 15000 });
  await click(sessionBtn, { pause: 300 });
  await click(page.getByRole("button", { name: "Continue" }), { pause: 300 });
  await caption("Just a name and phone");
  await type(page.getByPlaceholder("e.g. Nimal Perera"), "Sanduni Perera", 45);
  await type(page.getByPlaceholder("+94 77 123 4567"), "+94 77 482 6150", 45);
  await click(page.getByRole("button", { name: "Confirm booking" }), { pause: 100 });
  await page.getByRole("heading", { name: "You're booked!" }).waitFor({ timeout: 30000 });
  await caption("Booked, with a check-in QR code");
  mark("booked");
  const checkinCode = await page.evaluate(() => {
    const el = document.querySelector(".checkin-qr figcaption strong");
    return el ? el.textContent.trim() : null;
  });
  await wait(1300);
  await scrollTo(380, 800); await wait(1300);

  // ---- Live queue ----
  await section(["Follow the", "live queue"], async () => { await scrollTo(0, 10); });
  await caption("Numbers only, never names");
  await nav("Live queue");
  await page.getByRole("heading", { name: "Who's being seen now" }).waitFor();
  await wait(1800);

  // ---- AI assistant ----
  await section(["Ask the", "AI clinic assistant"]);
  await caption("A real conversation");
  await click(page.getByRole("button", { name: "Ask a question" }), { pause: 200 });
  await page.evaluate(() => window.__demo.chatFocus(true));
  await wait(800);
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
    await type(page.getByLabel("Your question"), question, 28);
    await page.keyboard.press("Enter");
    mark("fast", 10);
    await page.waitForFunction((n) => document.querySelectorAll(".chat-bubble.is-assistant:not(.chat-typing)").length >= n && !document.querySelector(".chat-typing"), i + 2, { timeout: 180000 });
    mark("fast", 1);
    const reply = await answers.nth(i + 1).innerText();
    mark("chat", `${question} -> ${reply}`);
    if (!isRight(reply)) throw new Error(`CHAT_CHECK_FAILED: ${question}`);
    await wait(Math.min(3600, 1300 + reply.length * 16));
  }
  await page.evaluate(() => window.__demo.chatFocus(false));
  await wait(500);

  // ---- Clinic dashboard ----
  await section(["Run the day from", "one dashboard"], async () => {
    await caption(null);
    await page.getByRole("button", { name: "Close chat" }).first().click();
    await page.getByRole("link", { name: "Sign in" }).click();
    await page.getByLabel("Username").waitFor();
  });
  await caption("Staff sign in");
  await type(page.getByLabel("Username"), env.CLINIC_ADMIN_USERNAME, 50);
  await click(page.getByLabel("Password"), { pause: 60 });
  await page.getByLabel("Password").pressSequentially(env.CLINIC_ADMIN_PASSWORD, { delay: 25 });
  await page.keyboard.press("Enter");
  await page.waitForURL(/staff|my-bookings|\/$/, { timeout: 20000 }).catch(() => {});
  if (!page.url().includes("/staff")) { await page.goto(BASE + "/staff"); }
  await page.locator(".stat-value").first().waitFor({ timeout: 20000 });
  await caption("Today at a glance");
  await wait(1500);

  await caption("The doctor arrives");
  await scrollTo(380, 600);
  await click(page.getByRole("button", { name: "Doctor arrived" }).last(), { pause: 800 });

  await caption("Patients check in");
  for (let i = 0; i < 2; i++) {
    await click(page.locator(".dash-appointments, .card").getByRole("button", { name: "Check in" }).first(), { pause: 800 });
  }

  await caption("Or scan their QR code");
  await scrollTo(0, 500);
  await click(page.getByRole("button", { name: /Scan check-in/ }), { pause: 400 });
  if (checkinCode) {
    await type(page.getByLabel("Check-in code"), checkinCode, 25);
  } else {
    mark("warn", "no check-in code captured");
  }
  await page.keyboard.press("Enter");
  await click(page.getByRole("button", { name: /^Check in No\./ }), { pause: 1000 });
  if (!page.url().endsWith("/staff")) { await side("Dashboard"); }
  const closeDialog = page.getByRole("dialog").getByRole("button", { name: /Close|Done/ }).first();
  if (await closeDialog.count()) await click(closeDialog, { pause: 400 });

  await caption("Call the next patient");
  await scrollTo(380, 600);
  await click(page.getByRole("button", { name: "Start" }).first(), { pause: 1100 });
  await click(page.locator(".now-serving").first().getByRole("button").first(), { pause: 1000 });
  await click(page.getByRole("button", { name: "Start" }).first(), { pause: 1200 });

  await caption("The public queue updates");
  await page.goto(BASE + "/live");
  await page.getByRole("heading", { name: "Who's being seen now" }).waitFor();
  await wait(1900);

  // ---- Appointments, patients, schedules ----
  await section(["Appointments, patients", "and schedules"], async () => {
    await page.goBack();
    await page.locator(".stat-value").first().waitFor({ timeout: 20000 });
  });
  await caption("Find, move or cancel bookings");
  await side("Appointments"); await wait(1300);
  await caption("Search patient records");
  await side("Patients");
  const search = page.getByPlaceholder(/Search/i).first();
  if (await search.count()) { await type(search, "Perera", 55); await wait(1000); }
  await caption("Weekly sessions and time off");
  await side("Schedule");
  const docSelect = page.locator("select").first();
  await click(docSelect, { pause: 50 });
  await page.keyboard.press("Escape");
  await docSelect.selectOption({ label: "Dr. Priya Raman" }).catch(() => {});
  await wait(1500);

  // ---- Admin ----
  await section(["Simple", "admin tools"]);
  await caption("Doctor profiles");
  await side("Doctors"); await wait(1100);
  await caption("Staff and patient accounts");
  await side("Accounts"); await wait(1100);
  await caption("SMS outbox");
  await side("SMS outbox"); await wait(1100);

  // ---- Doctor portal ----
  await section(["A portal for", "doctors"], async () => {
    await caption(null);
    await page.locator(".sidebar").getByRole("button", { name: "Sign out" }).click();
    await page.waitForTimeout(800);
    if (!page.url().includes("/login")) await page.goto(BASE + "/login");
    await page.getByLabel("Username").waitFor();
  });
  await caption("Doctors sign in");
  await type(page.getByLabel("Username"), "demo.kasun", 50);
  await click(page.getByLabel("Password"), { pause: 60 });
  await page.getByLabel("Password").pressSequentially(JSON.parse(env.CLINIC_DEMO_DOCTOR_PASSWORDS)["demo.kasun"], { delay: 25 });
  await page.keyboard.press("Enter");
  await page.waitForURL(/staff/, { timeout: 20000 }).catch(() => {});
  if (!page.url().includes("/staff")) await page.goto(BASE + "/staff");
  await page.locator(".stat-value").first().waitFor({ timeout: 20000 });
  await caption("Only their own queue");
  await scrollTo(380, 600); await wait(700);
  await click(page.locator(".now-serving").first().getByRole("button").first(), { pause: 900 });
  await click(page.getByRole("button", { name: "Start" }).first(), { pause: 1200 });

  await caption("Their patients");
  await side("Patients"); await wait(1100);

  await caption("Edit their profile");
  await click(page.locator('.sidebar a[href="/staff/account"]').first(), { pause: 500 });
  const languages = page.getByLabel("Languages");
  await click(languages, { pause: 80 });
  await page.keyboard.press("End");
  await languages.pressSequentially(", Tamil", { delay: 50 });
  await click(page.getByRole("button", { name: "Save profile" }), { pause: 1100 });

  await caption("Live on the website");
  await page.goto(BASE + "/doctors");
  const kasunCard = page.locator(".doctor-card").filter({ hasText: "Kasun" }).first();
  await kasunCard.waitFor({ timeout: 15000 });
  await kasunCard.evaluate((el) => el.scrollIntoView({ block: "center" }));
  await wait(300);
  await point(kasunCard.getByText("Tamil").first(), 400);
  await wait(1500);

  // ---- Theme ----
  await section(["Light or", "dark theme"], async () => {
    await caption(null);
    await page.goto(BASE + "/staff");
    await page.locator(".stat-value").first().waitFor({ timeout: 20000 });
  });
  await caption("Switch any time");
  await click(page.getByRole("radio", { name: "Dark" }), { pause: 1900 });
  await click(page.getByRole("radio", { name: "Light" }), { pause: 1000 });
  await caption(null);
  await wait(300);

  await card({ logo: true, sub: "Skip the waiting room, See your Doctor on time",
    chips: ["Online booking", "Live queue", "QR check-in", "AI assistant", "Staff portal", "Doctor portal"] }, 4300);
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
