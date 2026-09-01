import os from "node:os";
import path from "node:path";
import { mkdir } from "node:fs/promises";
import { chromium } from "@playwright/test";

const baseUrl = String(process.env.TENANT_SITE_AUDIT_URL || "").replace(/\/$/, "");
if (!baseUrl) throw new Error("TENANT_SITE_AUDIT_URL is required");

const routes = String(process.env.TENANT_SITE_AUDIT_ROUTES || "/")
  .split(",")
  .map((value) => value.trim())
  .filter(Boolean);
const requestedWidths = String(process.env.TENANT_SITE_AUDIT_WIDTHS || "375,430,768,1024,1280,1440,1920")
  .split(",")
  .map((value) => Number.parseInt(value.trim(), 10))
  .filter((value) => Number.isInteger(value) && value >= 320 && value <= 2560);
const viewports = [...new Set(requestedWidths)].map((width) => ({
  width,
  height: width <= 430 ? 844 : width <= 768 ? 1024 : 1000,
}));
const outputDir = path.join(os.tmpdir(), "madar-tenant-site-audit");
await mkdir(outputDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const failures = [];
const checks = [];

try {
  for (const viewport of viewports) {
    const context = await browser.newContext({ viewport });
    for (const route of routes) {
      const page = await context.newPage();
      const pageErrors = [];
      const consoleErrors = [];
      const failedRequests = [];
      page.on("pageerror", (error) => pageErrors.push(String(error?.message || error)));
      page.on("console", (message) => {
        const value = message.text();
        const expectedAnonymousNoise = value.includes("static.cloudflareinsights.com") ||
          value.includes("Executing inline script violates") ||
          value.includes("status of 401");
        if (message.type() === "error" && !expectedAnonymousNoise) consoleErrors.push(value);
      });
      page.on("response", (response) => {
        const expectedAnonymousRefresh = response.status() === 401 && response.url().includes("/auth/refresh");
        if (response.status() >= 400 && !expectedAnonymousRefresh) failedRequests.push(`${response.status()} ${response.url()}`);
      });

      const response = await page.goto(`${baseUrl}${route === "/" ? "" : route}`, {
        waitUntil: "domcontentloaded",
        timeout: 45_000,
      });
      await page.waitForSelector(".tenant-site-runtime", { timeout: 30_000 });
      await page.waitForSelector(".built-site-header", { timeout: 30_000 });
      await page.evaluate(() => {
        for (const image of document.images) image.loading = "eager";
        window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "instant" });
      });
      await page.waitForTimeout(2000);
      await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));

      const result = await page.evaluate(() => {
        const parse = (value) => {
          const match = String(value || "").match(/rgba?\(([^)]+)\)/i);
          if (!match) return null;
          const values = match[1].replaceAll(",", " ").replace("/", " ").split(/\s+/).filter(Boolean);
          const channel = (item) => item.endsWith("%") ? Number.parseFloat(item) * 2.55 : Number.parseFloat(item);
          return [channel(values[0]), channel(values[1]), channel(values[2]), values[3] === undefined ? 1 : Number.parseFloat(values[3])];
        };
        const blend = (front, back) => {
          const alpha = front[3] + back[3] * (1 - front[3]);
          return [0, 1, 2].map((index) => (
            (front[index] * front[3] + back[index] * back[3] * (1 - front[3])) / (alpha || 1)
          )).concat(alpha);
        };
        const luminance = (color) => {
          const values = color.slice(0, 3).map((item) => item / 255).map((item) => (
            item <= 0.04045 ? item / 12.92 : ((item + 0.055) / 1.055) ** 2.4
          ));
          return 0.2126 * values[0] + 0.7152 * values[1] + 0.0722 * values[2];
        };
        const contrast = (first, second) => {
          const a = luminance(first);
          const b = luminance(second);
          return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
        };
        const visible = (element) => {
          const style = getComputedStyle(element);
          const rect = element.getBoundingClientRect();
          return style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity) > 0.05 && rect.width > 0 && rect.height > 0;
        };
        const background = (element) => {
          const chain = [];
          let current = element;
          while (current) {
            chain.unshift(current);
            current = current.parentElement;
          }
          let result = [255, 255, 255, 1];
          for (const node of chain) {
            const color = parse(getComputedStyle(node).backgroundColor);
            if (color && color[3] > 0) result = blend(color, result);
          }
          return result;
        };
        const contrastFailures = [];
        let textChecks = 0;
        for (const element of document.querySelectorAll(".tenant-site-runtime *")) {
          if (!visible(element) || element.closest("[aria-hidden='true']")) continue;
          const hasDirectText = [...element.childNodes].some((node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim());
          if (!hasDirectText) continue;
          const style = getComputedStyle(element);
          const foreground = parse(style.color);
          if (!foreground) continue;
          const back = background(element);
          const actual = contrast(blend(foreground, back), back);
          const size = Number.parseFloat(style.fontSize);
          const weight = Number.parseInt(style.fontWeight, 10) || 400;
          const required = size >= 24 || (size >= 18.66 && weight >= 700) ? 3 : 4.5;
          textChecks += 1;
          if (actual + 0.01 < required) {
            contrastFailures.push({
              text: element.textContent.trim().replace(/\s+/g, " ").slice(0, 90),
              ratio: Number(actual.toFixed(2)),
              required,
              color: style.color,
              background: style.backgroundColor,
              className: String(element.className || "").slice(0, 120),
            });
          }
        }
        const images = [...document.images].filter(visible);
        const brokenImages = images
          .filter((item) => !item.complete || item.naturalWidth === 0)
          .map((item) => item.currentSrc || item.src);
        const h1Count = document.querySelectorAll(".tenant-site-runtime h1").length;
        return {
          title: document.title,
          runtimeState: document.querySelector(".tenant-site-runtime")?.getAttribute("data-runtime-state") || "",
          overflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth,
          brokenImages,
          imageCount: images.length,
          h1Count,
          textChecks,
          contrastFailures,
          unavailable: /page unavailable|site unavailable|could not load|not found/i.test(document.body.innerText),
        };
      });

      const record = {
        route,
        width: viewport.width,
        status: response?.status() || 0,
        ...result,
        pageErrors,
        consoleErrors,
        failedRequests,
      };
      checks.push(record);
      if (
        record.status !== 200 || record.unavailable || record.overflow > 1 || record.h1Count !== 1 ||
        record.brokenImages.length || record.contrastFailures.length || record.pageErrors.length ||
        record.consoleErrors.length || record.failedRequests.length
      ) failures.push(record);

      if (route === "/" && [375, 1440, 1920].includes(viewport.width)) {
        await page.screenshot({
          path: path.join(outputDir, `ibtikar-home-${viewport.width}.png`),
          fullPage: true,
        });
      }
      await page.close();
    }
    await context.close();
  }
} finally {
  await browser.close();
}

console.log(JSON.stringify({
  baseUrl,
  routes,
  viewportCount: viewports.length,
  checks: checks.length,
  totalTextChecks: checks.reduce((total, item) => total + item.textChecks, 0),
  totalImages: checks.reduce((total, item) => total + item.imageCount, 0),
  failures,
  outputDir,
}, null, 2));

if (failures.length) process.exitCode = 1;
