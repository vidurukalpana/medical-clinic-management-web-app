// Shared setup: browser pointed at the web app, with API calls sent to the time-shifted API copy.
const { chromium } = require("playwright");
const fs = require("fs");

const BASE = "http://localhost:8080";
const SHIFTED_API = "http://localhost:8001";
// Monday 26 Oct 2026, a few minutes before the 8:00 AM session's patients arrive (Asia/Colombo).
const DEMO_START = new Date("2026-10-26T08:16:00+05:30");

function readEnv(path) {
  return Object.fromEntries(
    fs.readFileSync(path, "utf8").split("\n").filter((l) => l.includes("=") && !l.startsWith("#"))
      .map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1)])
  );
}

async function openBrowser({ record } = {}) {
  const browser = await chromium.launch({ channel: "chrome", args: ["--hide-scrollbars", "--window-size=1920,1080"] });
  const ctx = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
    colorScheme: "light",
    ...(record ? { recordVideo: { dir: record, size: { width: 1920, height: 1080 } } } : {}),
  });
  await ctx.clock.install({ time: DEMO_START });
  await ctx.clock.resume();
  await ctx.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.port !== "8080") return route.continue();
    const target = SHIFTED_API + url.pathname + url.search;
    const headers = { ...route.request().headers() };
    delete headers.host;
    const response = await route.fetch({ url: target, headers, timeout: 120000 });
    await route.fulfill({ response });
  });
  return { browser, ctx };
}

module.exports = { BASE, openBrowser, readEnv };
