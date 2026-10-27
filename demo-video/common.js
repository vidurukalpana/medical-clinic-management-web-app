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

// Pages are laid out at a laptop-sized viewport (like a 14" MacBook) and captured at 1920x1080,
// so the site looks the way it does in a normal browser rather than spread across a wide screen.
const VIEWPORT = { width: 1536, height: 864 };

async function openBrowser({ record } = {}) {
  const scale = 1920 / VIEWPORT.width;
  // The screencast only captures at the device scale when Chrome itself is started with it.
  const browser = await chromium.launch({ channel: "chrome", args: ["--hide-scrollbars", `--window-size=${VIEWPORT.width},${VIEWPORT.height}`, `--force-device-scale-factor=${scale}`] });
  const ctx = await browser.newContext({
    viewport: VIEWPORT,
    deviceScaleFactor: scale,
    colorScheme: "light",
    permissions: ["clipboard-read", "clipboard-write"],
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
    // Retry once: the API copy occasionally drops a connection, and an unhandled error here ends the take.
    for (let attempt = 1; ; attempt++) {
      try {
        const response = await route.fetch({ url: target, headers, timeout: 120000 });
        return await route.fulfill({ response });
      } catch (e) {
        if (attempt >= 2) return route.abort().catch(() => {});
      }
    }
  });
  return { browser, ctx };
}

module.exports = { BASE, VIEWPORT, openBrowser, readEnv };
