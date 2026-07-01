import { spawn } from "node:child_process";
import { mkdir, rm, writeFile } from "node:fs/promises";
import { setTimeout as delay } from "node:timers/promises";

const chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const port = 9333;
const origin = "http://localhost:5173";
const outDir = "qa_screenshots";
const userDataDir = "D:\\Madar\\.tmp-chrome-visual-qa";

const routes = [
  "/",
  "/product-tour",
  "/pricing",
  "/contact",
  "/login",
  "/signup",
  "/dashboard",
  "/settings",
  "/my-plan",
  "/page-builder",
  "/builder-responses",
  "/builder-data",
  "/page-builder/preview",
  "/site/my-site",
];

const viewports = {
  desktop: { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false },
  mobile: { width: 390, height: 844, deviceScaleFactor: 2, mobile: true },
};

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`${response.status} ${response.statusText} for ${url}`);
  return response.json();
}

async function waitForChrome() {
  for (let i = 0; i < 60; i += 1) {
    try {
      await fetchJson(`http://127.0.0.1:${port}/json/version`);
      return;
    } catch {
      await delay(250);
    }
  }
  throw new Error("Chrome remote debugging did not start");
}

function connect(wsUrl) {
  const ws = new WebSocket(wsUrl);
  let id = 0;
  const pending = new Map();
  const events = [];

  ws.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) reject(new Error(JSON.stringify(message.error)));
      else resolve(message.result || {});
      return;
    }
    if (message.method) events.push(message);
  });

  return new Promise((resolve, reject) => {
    ws.addEventListener("open", () => {
      resolve({
        events,
        send(method, params = {}) {
          id += 1;
          ws.send(JSON.stringify({ id, method, params }));
          return new Promise((sendResolve, sendReject) => {
            pending.set(id, { resolve: sendResolve, reject: sendReject });
          });
        },
        close() {
          ws.close();
        },
      });
    });
    ws.addEventListener("error", reject, { once: true });
  });
}

function sanitize(value) {
  return value.replace(/[^a-z0-9]+/gi, "_").replace(/^_+|_+$/g, "") || "root";
}

async function captureRoute(route, mode, viewportName) {
  const tab = await fetchJson(`http://127.0.0.1:${port}/json/new?${encodeURIComponent("about:blank")}`, {
    method: "PUT",
  });
  const client = await connect(tab.webSocketDebuggerUrl);
  const viewport = viewports[viewportName];
  const url = `${origin}${route}`;
  const themeSetup = `
    localStorage.setItem("madar-light-theme-restored-v1", "true");
    localStorage.setItem("madar-theme-mode", "${mode}");
  `;

  await client.send("Page.enable");
  await client.send("Runtime.enable");
  await client.send("Log.enable");
  await client.send("Emulation.setDeviceMetricsOverride", viewport);
  await client.send("Page.addScriptToEvaluateOnNewDocument", { source: themeSetup });
  await client.send("Page.navigate", { url });
  await delay(2500);

  const data = await client.send("Runtime.evaluate", {
    returnByValue: true,
    expression: `(() => {
      const pick = (selector) => {
        const el = document.querySelector(selector);
        if (!el) return null;
        const s = getComputedStyle(el);
        return {
          selector,
          color: s.color,
          background: s.backgroundColor,
          border: s.borderColor,
          display: s.display,
          text: (el.innerText || el.textContent || "").trim().slice(0, 80),
        };
      };
      return {
        requested: ${JSON.stringify(route)},
        url: location.href,
        title: document.title,
        theme: document.documentElement.dataset.theme,
        bodyBackground: getComputedStyle(document.body).backgroundColor,
        htmlBackground: getComputedStyle(document.documentElement).backgroundColor,
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
        hasHorizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
        elements: [
          pick("header"),
          pick("main"),
          pick("footer"),
          pick("button"),
          pick("input"),
          pick(".card, .feature-card, .pricing-card, .contact-card, .login-card, .register-card, .dashboard-panel, .overview-card, .builder-panel"),
        ].filter(Boolean),
        visibleText: (document.body.innerText || "").trim().slice(0, 220),
      };
    })()`,
  });

  const screenshot = await client.send("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: false,
  });

  const errors = client.events
    .filter((event) =>
      event.method === "Runtime.exceptionThrown" ||
      (event.method === "Log.entryAdded" && ["error", "warning"].includes(event.params?.entry?.level))
    )
    .map((event) => event.params);

  const fileBase = `${sanitize(route)}_${mode}_${viewportName}`;
  await writeFile(`${outDir}/${fileBase}.png`, Buffer.from(screenshot.data, "base64"));
  await fetch(`http://127.0.0.1:${port}/json/close/${tab.id}`);
  client.close();

  return {
    route,
    mode,
    viewport: viewportName,
    screenshot: `${outDir}/${fileBase}.png`,
    data: data.result.value,
    errors,
  };
}

await mkdir(outDir, { recursive: true });
await rm(userDataDir, { recursive: true, force: true });

const chrome = spawn(chromePath, [
  "--headless",
  `--remote-debugging-port=${port}`,
  "--remote-allow-origins=*",
  `--user-data-dir=${userDataDir}`,
  "--no-first-run",
  "--no-default-browser-check",
  "--no-sandbox",
  "--disable-dev-shm-usage",
  "--disable-background-networking",
  "--disable-gpu",
  "--hide-scrollbars",
  "about:blank",
], { stdio: "ignore", windowsHide: true });

try {
  await waitForChrome();
  const results = [];

  for (const route of routes) {
    for (const mode of ["light", "dark"]) {
      results.push(await captureRoute(route, mode, "desktop"));
    }
  }

  for (const route of ["/", "/login", "/page-builder"]) {
    for (const mode of ["light", "dark"]) {
      results.push(await captureRoute(route, mode, "mobile"));
    }
  }

  await writeFile(`${outDir}/visual-qa-report.json`, JSON.stringify(results, null, 2));
  console.log(JSON.stringify({
    screenshots: results.length,
    report: `${outDir}/visual-qa-report.json`,
    routes: routes.length,
  }, null, 2));
} finally {
  chrome.kill();
}
