import { mkdir, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { chromium } from "@playwright/test";

const baseUrl = process.env.CONTRAST_AUDIT_URL || "http://127.0.0.1:5173";
const mockApi = process.env.CONTRAST_AUDIT_MOCK === "1";
if (mockApi && !["localhost", "127.0.0.1", "[::1]"].includes(new URL(baseUrl).hostname)) throw new Error("Mock contrast checks require a loopback frontend");
const outputDir = process.env.CONTRAST_AUDIT_OUTPUT_DIR || path.join(os.tmpdir(), "madar-contrast-audit");
const viewports = [
  { name: "compact", width: 390, height: 844 },
  { name: "intermediate", width: 768, height: 1024 },
  { name: "wide", width: 1440, height: 900 },
];
const themes = ["light", "dark"];
const languageModes = [{ name: "ltr", language: "en" }, { name: "rtl", language: "ar" }];
const auditModes = themes.flatMap((theme) => languageModes.map((languageMode) => ({ theme, languageMode })));
const requestedRoutes = new Set((process.env.CONTRAST_AUDIT_ROUTES || "").split(",").map((value) => value.trim()).filter(Boolean));
const selectedRoutes = (routes) => requestedRoutes.size ? routes.filter((route) => requestedRoutes.has(route)) : routes;

const publicRoutes = [
  "/", "/demo", "/pricing", "/pricing/base-plans", "/pricing/custom-plan",
  "/team", "/about", "/contact", "/privacy-policy", "/terms-and-conditions",
  "/login", "/signup", "/forgot-password", "/reset-password", "/verify-email",
  "/site/demo/shop", "/site/demo/shop/products", "/site/demo/shop/product/chair", "/site/demo/shop/checkout",
];
const adminRoutes = [
  "/dashboard", "/admin/users", "/admin/account-access", "/notifications",
  "/page-builder", "/builder-responses", "/builder-data", "/archive", "/my-plan",
  "/settings/security", "/settings",
];
const userRoutes = [
  "/dashboard", "/page-builder", "/builder-responses", "/builder-data", "/calendar",
  "/agenda", "/archive", "/ecommerce/tags", "/ecommerce/categories",
  "/ecommerce/products", "/ecommerce/products/new", "/ecommerce/delivery", "/ecommerce/orders", "/ecommerce/loyalty", "/ecommerce/theme", "/ecommerce/cv-rerank",
  "/ecommerce/store", "/my-plan", "/notifications", "/settings/change-password",
  "/settings/security", "/settings", "/settings?tab=website", "/settings?tab=ecommerce", "/settings?tab=devices", "/settings?tab=notifications", "/admin/users",
];

const fakeUser = (role) => ({
  id: role === "admin" ? 9101 : 9102,
  auth_id: `contrast-audit-${role}`,
  tenant_id: 910,
  first_name: "Contrast",
  last_name: "Audit",
  name: "Contrast Audit",
  email: `${role}@contrast-audit.invalid`,
  subscription_type: "pro",
  plan: "pro",
  builder_type: "website",
  features: [],
  payment_status: "active",
  user_type: role,
});

async function installEnvironment(page, role, theme, language) {
  await page.addInitScript((selectedTheme) => {
    localStorage.setItem("madar-theme-mode", selectedTheme);
  }, theme);
  await page.addInitScript((selectedLanguage) => localStorage.setItem("madar.language", selectedLanguage), language);

  if (mockApi) {
    const user = fakeUser(role || "user");
    await page.route("**/*", route => {
      const url = new URL(route.request().url());
      const path = url.pathname;
      if (!path.startsWith("/api/") && url.origin === new URL(baseUrl).origin) return route.continue();
      const json = data => route.fulfill({contentType:"application/json", body:JSON.stringify(data)});
      if (path.includes("/public/sites/")) {
        const product = {id:"product-1",slug:"chair",name:"Chair",price:"20",currency:"USD",in_stock:true,images:[]};
        const site = {brand:"Madar Store",commerce_currency:"USD",description:"Store description"};
        if (path.endsWith("/store-profile")) return json({site});
        if (path.includes("/catalog/products/")) return json({site,product,category:null,tags:[],attributes:[],options:[],variants:[]});
        if (path.endsWith("/delivery-areas")) return json({areas:[{id:"area-1",name_en:"City",name_ar:"City"}]});
        if (path.endsWith("/discounts")) return json({conditions:[]});
        if (path.endsWith("/loyalty/me")) return json({eligible:false});
        if (path.endsWith("/visits")) return json({success:true});
        return json({site,catalog:{products:[product],categories:[],tags:[],pagination:{page:1,pages:1,total:1,limit:12}}});
      }
      if (path.endsWith("/auth/user_status")) return json({logged_in:Boolean(role), authenticated:Boolean(role), user:role ? user : null});
      if (path.endsWith("/auth/refresh")) return json({logged_in:false});
      if (path.endsWith("/website/settings")) return json({website:{brand:"Madar",footer_store_name:"Madar Store",description:"Store description",standard_path_slug:"demo",ecommerce_theme:{}}});
      if (path.endsWith("/ecommerce/settings")) return json({currency:"USD",currency_locked:false});
      if (path.endsWith("/ecommerce/catalog")) return json({products:[],categories:[],tags:[],commerce_currency:"USD"});
      if (path.endsWith("/ecommerce/loyalty")) return json({currency:"USD",rule:{reward_product_id:"product-a"}});
      if (path.endsWith("/notifications/preferences")) return json({preferences:["calendar","reservations","forms","general"].flatMap(category=>["in_app","push","email"].map(channel=>({category,channel,enabled:true})))});
      if (path.endsWith("/auth/mfa/status")) return json({factors:[],current_level:"aal1",next_level:"aal1"});
      if (path.endsWith("/info")) return json({user});
      if (path.startsWith("/api/") || url.origin !== new URL(baseUrl).origin) return json({success:true,user,orders:[],areas:[],projects:[],pagination:{},notifications:[],unread_count:0,installations:[],preferences:[],users:[],data:[],reservations:[],events:[],forms:[],pages:[],theme:{},rule:{},totals:{}});
      return route.continue();
    });
    return;
  }
  if (!role) return;
  const user = fakeUser(role);
  await page.route("**/api/auth/user_status**", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ logged_in: true, authenticated: true, user }),
  }));
}

async function inspectContrast(page) {
  return page.evaluate(() => {
    const parse = (value) => {
      const srgb = String(value || "").match(/color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*\/\s*([\d.]+))?\)/i);
      if (srgb) return [Number(srgb[1]) * 255, Number(srgb[2]) * 255, Number(srgb[3]) * 255, srgb[4] === undefined ? 1 : Number(srgb[4])];
      const match = String(value || "").match(/rgba?\(([^)]+)\)/i);
      if (!match) return null;
      const parts = match[1].replaceAll(",", " ").replace("/", " ").split(/\s+/).filter(Boolean);
      if (parts.length < 3) return null;
      const channel = (part) => part.endsWith("%") ? Number.parseFloat(part) * 2.55 : Number.parseFloat(part);
      return [channel(parts[0]), channel(parts[1]), channel(parts[2]), parts[3] === undefined ? 1 : Number.parseFloat(parts[3])];
    };
    const blend = (front, back) => {
      const alpha = front[3] + back[3] * (1 - front[3]);
      if (alpha === 0) return [0, 0, 0, 0];
      return [0, 1, 2].map((index) => (front[index] * front[3] + back[index] * back[3] * (1 - front[3])) / alpha).concat(alpha);
    };
    const luminance = (color) => {
      const channels = color.slice(0, 3).map((value) => value / 255).map((value) => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
      return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
    };
    const ratio = (first, second) => {
      const a = luminance(first);
      const b = luminance(second);
      return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    };
    const backgroundOf = (element, includeSelf = true) => {
      const chain = [];
      let current = includeSelf ? element : element.parentElement;
      while (current) {
        chain.unshift(current);
        current = current.parentElement;
      }
      let result = parse(getComputedStyle(document.documentElement).backgroundColor) || [255, 255, 255, 1];
      for (const node of chain) {
        const nodeStyle = getComputedStyle(node);
        let background = parse(nodeStyle.backgroundColor);
        if (!background || background[3] === 0) background = parse(nodeStyle.backgroundImage);
        if (background && background[3] > 0) result = blend(background, result);
      }
      return result;
    };
    const effectiveColor = (element, property = "color") => {
      const style = getComputedStyle(element);
      const parsed = parse(style.getPropertyValue(property)) || parse(style.color);
      if (!parsed) return null;
      let opacity = 1;
      let current = element;
      while (current) {
        opacity *= Number.parseFloat(getComputedStyle(current).opacity || "1");
        current = current.parentElement;
      }
      parsed[3] *= opacity;
      return blend(parsed, backgroundOf(element));
    };
    const isVisible = (element) => {
      if (element.checkVisibility && !element.checkVisibility({checkVisibilityCSS:true,checkOpacity:true})) return false;
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      let effectiveOpacity = 1;
      let current = element;
      while (current) { effectiveOpacity *= Number.parseFloat(getComputedStyle(current).opacity || "1"); current = current.parentElement; }
      return style.display !== "none" && style.visibility !== "hidden" && effectiveOpacity > 0.05 && rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.top < window.innerHeight && rect.right > 0 && rect.left < window.innerWidth;
    };
    const selector = (element) => {
      const id = element.id ? `#${element.id}` : "";
      const classes = String(element.getAttribute("class") || "").trim().split(/\s+/).filter(Boolean).slice(0, 3).map((name) => `.${name}`).join("");
      const label = element.getAttribute("aria-label") || element.getAttribute("title") || element.getAttribute("name") || element.getAttribute("type");
      const detail = label ? `[label=${String(label).slice(0, 48)}]` : "";
      return `${element.tagName.toLowerCase()}${id}${classes}${detail}`.slice(0, 180);
    };
    const failures = [];
    const checked = { text: 0, placeholders: 0, controls: 0, icons: 0 };

    for (const element of document.querySelectorAll("body *")) {
      if (!isVisible(element) || element.closest("[aria-hidden='true']")) continue;
      const authored = element.closest(".builder-canvas, .builder-form-preview-page, .tenant-site-runtime");
      if (authored) continue;
      const hasText = [...element.childNodes].some((node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim());
      if (!hasText) continue;
      const style = getComputedStyle(element);
      const fill = parse(style.webkitTextFillColor);
      if (fill && fill[3] === 0) continue;
      const foreground = effectiveColor(element, fill ? "-webkit-text-fill-color" : "color");
      const background = backgroundOf(element);
      if (!foreground) continue;
      checked.text += 1;
      const fontSize = Number.parseFloat(style.fontSize);
      const fontWeight = Number.parseInt(style.fontWeight, 10) || 400;
      const threshold = fontSize >= 24 || (fontSize >= 18.66 && fontWeight >= 700) ? 3 : 4.5;
      const actual = ratio(foreground, background);
      if (actual + 0.01 < threshold) failures.push({
        kind: "text", selector: selector(element), text: element.textContent.trim().replace(/\s+/g, " ").slice(0, 100),
        ratio: Number(actual.toFixed(2)), required: threshold, color: style.color, background: getComputedStyle(element).backgroundColor,
        effectiveColor: foreground.map((value) => Number(value.toFixed(2))),
        effectiveBackground: background.map((value) => Number(value.toFixed(2))),
      });
    }

    for (const element of document.querySelectorAll("svg.lucide")) {
      if (!isVisible(element) || element.closest(".builder-canvas, .builder-form-preview-page, .tenant-site-runtime")) continue;
      const foreground = effectiveColor(element, "stroke");
      if (!foreground) continue;
      checked.icons += 1;
      const actual = ratio(foreground, backgroundOf(element));
      if (actual + 0.01 < 3) failures.push({kind:"icon", selector:selector(element), ratio:Number(actual.toFixed(2)), required:3, color:getComputedStyle(element).stroke});
    }

    for (const element of document.querySelectorAll("input[placeholder], textarea[placeholder]")) {
      if (!isVisible(element) || element.closest(".builder-canvas, .builder-form-preview-page, .tenant-site-runtime")) continue;
      const placeholder = getComputedStyle(element, "::placeholder");
      const parsed = parse(placeholder.color);
      if (!parsed) continue;
      checked.placeholders += 1;
      const actual = ratio(blend(parsed, backgroundOf(element)), backgroundOf(element));
      if (actual + 0.01 < 4.5) failures.push({ kind: "placeholder", selector: selector(element), ratio: Number(actual.toFixed(2)), required: 4.5, color: placeholder.color });
    }

    const controlSelector = "input:not([type='hidden']):not([type='checkbox']):not([type='radio']):not([type='range']):not([type='color']), select, textarea, button, [role='button'], [role='tab'], [aria-current='page']";
    for (const element of document.querySelectorAll(controlSelector)) {
      if (!isVisible(element) || element.closest(".builder-canvas, .builder-form-preview-page, .tenant-site-runtime") || element.matches(".dashboard-sidebar-backdrop")) continue;
      const style = getComputedStyle(element);
      const isFormControl = element.matches("input, select, textarea");
      const isStateful = !element.matches("a") && element.matches("[role='tab'], [aria-current], [aria-selected='true'], [aria-pressed='true']");
      const hasVisibleBorder = Number.parseFloat(style.borderTopWidth) >= 1 && (parse(style.borderTopColor)?.[3] || 0) > 0;
      const hasVisibleFill = (parse(style.backgroundColor)?.[3] || 0) > 0 || style.backgroundImage !== "none";
      if (!hasVisibleBorder && !hasVisibleFill) continue;
      const surrounding = backgroundOf(element, false);
      const ownBackground = backgroundOf(element, true);
      const border = parse(style.borderTopColor);
      const borderWidth = Number.parseFloat(style.borderTopWidth);
      const backgroundRatio = ratio(ownBackground, surrounding);
      const borderRatio = border && borderWidth >= 1 ? ratio(blend(border, surrounding), surrounding) : 1;
      checked.controls += 1;
      if (Math.max(backgroundRatio, borderRatio) + 0.01 < 3) failures.push({
        kind: "control", selector: selector(element), text: element.textContent.trim().replace(/\s+/g, " ").slice(0, 80),
        ratio: Number(Math.max(backgroundRatio, borderRatio).toFixed(2)), required: 3,
        border: style.borderTopColor, background: style.backgroundColor, disabled: Boolean(element.disabled),
      });
    }

    const unique = [];
    const keys = new Set();
    for (const failure of failures) {
      const key = [failure.kind, failure.selector, failure.text, failure.ratio].join("|");
      if (!keys.has(key)) { keys.add(key); unique.push(failure); }
    }
    return { checked, failures: unique.slice(0, 80), failureCount: unique.length };
  });
}

async function auditRouteSet(browser, routes, role) {
  const results = [];
  for (const viewport of viewports) {
    for (const { theme, languageMode } of auditModes) {
      const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height } });
      const page = await context.newPage();
      await installEnvironment(page, role, theme, languageMode.language);
      for (const route of routes) {
        const pageErrors = [];
        page.removeAllListeners("pageerror");
        page.on("pageerror", (error) => pageErrors.push(error.message));
        const response = await page.goto(`${baseUrl}${route}`, { waitUntil: "domcontentloaded", timeout: 30_000 });
        await page.waitForTimeout(mockApi ? 500 : 1500);
        await page.evaluate(async () => {
          const animations = document.getAnimations().filter(animation => animation.playState === "running" && Number.isFinite(animation.effect?.getComputedTiming().endTime));
          await Promise.all(animations.map(animation => animation.finished.catch(() => {})));
        });
        const pageHeight = await page.evaluate(() => (document.querySelector(".authenticated-main, .live-store, .tenant-site-runtime") || document.documentElement).scrollHeight);
        const maxScroll = Math.max(0, pageHeight - viewport.height);
        const stepCount = Math.min(6, Math.max(1, Math.ceil(pageHeight / viewport.height)));
        const positions = Array.from({ length: stepCount }, (_, index) => stepCount === 1 ? 0 : Math.round(maxScroll * index / (stepCount - 1)));
        const aggregate = { checked: { text: 0, placeholders: 0, controls: 0, icons: 0 }, failures: [], failureCount: 0 };
        const failureKeys = new Set();
        for (const position of positions) {
          await page.evaluate((top) => {
            const scroller = document.querySelector(".authenticated-main, .live-store, .tenant-site-runtime");
            if (scroller) scroller.scrollTo({top,behavior:"instant"});
            else window.scrollTo({top,behavior:"instant"});
          }, position);
          await page.waitForTimeout(mockApi ? 60 : 180);
          await page.evaluate(async () => {
            const animations = document.getAnimations().filter(animation => animation.playState === "running" && Number.isFinite(animation.effect?.getComputedTiming().endTime));
            await Promise.all(animations.map(animation => animation.finished.catch(() => {})));
          });
          const inspection = await inspectContrast(page);
          for (const key of Object.keys(aggregate.checked)) aggregate.checked[key] += inspection.checked[key];
          for (const failure of inspection.failures) {
            const key = [failure.kind, failure.selector, failure.text, failure.ratio].join("|");
            if (!failureKeys.has(key)) { failureKeys.add(key); aggregate.failures.push(failure); }
          }
        }
        aggregate.failureCount = aggregate.failures.length;
        results.push({ role: role || "public", route, theme, direction: languageMode.name, viewport: viewport.name, status: response?.status() || 0, pageErrors, ...aggregate });
      }
      console.log(`${role || "public"} ${viewport.name} ${theme} ${languageMode.name}: ${routes.length} pages checked`);
      await context.close();
    }
  }
  return results;
}

await mkdir(outputDir, { recursive: true });
const browser = await chromium.launch({ channel: "chrome", headless: true });
const [publicResults, adminResults, userResults] = await Promise.all([
  auditRouteSet(browser, selectedRoutes(publicRoutes), null),
  auditRouteSet(browser, selectedRoutes(adminRoutes), "admin"),
  auditRouteSet(browser, selectedRoutes(userRoutes), "user"),
]);
const results = [...publicResults, ...adminResults, ...userResults];
await browser.close();

const failures = results.filter((result) => result.failureCount > 0 || result.pageErrors.length > 0);
const report = {
  generatedAt: new Date().toISOString(), baseUrl, outputDir,
  routeChecks: results.length,
  textChecks: results.reduce((sum, result) => sum + result.checked.text, 0),
  placeholderChecks: results.reduce((sum, result) => sum + result.checked.placeholders, 0),
  controlChecks: results.reduce((sum, result) => sum + result.checked.controls, 0),
  iconChecks: results.reduce((sum, result) => sum + result.checked.icons, 0),
  failedRouteChecks: failures.length,
  failures,
};
await writeFile(path.join(outputDir, "report.json"), `${JSON.stringify(report, null, 2)}\n`, "utf8");
console.log(JSON.stringify({
  outputDir, routeChecks: report.routeChecks, textChecks: report.textChecks,
  placeholderChecks: report.placeholderChecks, controlChecks: report.controlChecks,
  iconChecks: report.iconChecks,
  failedRouteChecks: report.failedRouteChecks,
}, null, 2));
if (failures.length > 0) process.exitCode = 1;
