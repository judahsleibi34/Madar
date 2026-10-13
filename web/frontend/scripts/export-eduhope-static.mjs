#!/usr/bin/env node
// Snapshot the EduHope academy preview into static pages served by the Madar frontend at /eduhope/.
// Usage: node scripts/export-eduhope-static.mjs [previewOrigin]   (default http://127.0.0.1:5180)
// Static pages carry no scripts (production CSP forbids inline scripts) and no account actions:
// sign-in, enrolment and application submission point visitors to the Contact page.
import { createHash } from "node:crypto";
import { mkdir, rm, writeFile } from "node:fs/promises";
import { dirname, extname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { replaceStaticNavigation } from "./eduhope-static-navigation.mjs";

const ORIGIN = process.argv[2] || "http://127.0.0.1:5180";
const ACADEMY = "/academy/eduhope-local";
const SITE = "/eduhope";
const PUBLIC_ORIGIN = process.env.EDUHOPE_PUBLIC_ORIGIN || "https://madarportal.com";
const OUT = join(dirname(fileURLToPath(import.meta.url)), "../public/eduhope");
const LANGS = ["en", "ar"];

const academy = await (await fetch(`${ORIGIN}/api${ACADEMY.replace("/academy/", "/public/academies/")}`)).json();
const slugs = [...academy.landing.pages.map(page => page.slug), "/courses", ...academy.courses.map(course => `/courses/${course.id}`)];
const sitePath = (lang, slug) => `${SITE}${lang === "ar" ? "/ar" : ""}${slug === "/" ? "" : slug}/`;

await rm(OUT, { recursive: true, force: true });
await mkdir(join(OUT, "assets"), { recursive: true });
const saved = new Map();
async function saveAsset(url, body, ext) {
  const name = `${createHash("sha256").update(body).digest("hex").slice(0, 16)}${ext}`;
  if (!saved.has(name)) { await writeFile(join(OUT, "assets", name), body); saved.set(name, url); }
  return `${SITE}/assets/${name}`;
}
async function download(url) {
  const absolute = new URL(url, ORIGIN);
  const response = await fetch(absolute);
  if (!response.ok) throw new Error(`${response.status} ${absolute}`);
  const ext = extname(absolute.pathname).toLowerCase() || ".bin";
  return saveAsset(absolute.href, Buffer.from(await response.arrayBuffer()), ext);
}

const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || "/usr/bin/google-chrome" });
for (const lang of LANGS) {
  const context = await browser.newContext({ viewport: { width: 1366, height: 900 } });
  await context.addInitScript(language => localStorage.setItem("madar.language", language), lang);
  const page = await context.newPage();
  for (const slug of slugs) {
    await page.goto(`${ORIGIN}${ACADEMY}${slug === "/" ? "" : slug}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(800);
    await page.evaluate(replaceStaticNavigation, { site: SITE, lang });
    const snapshot = await page.evaluate(({ ACADEMY, SITE, lang, slug }) => {
      const contact = `${SITE}${lang === "ar" ? "/ar" : ""}/contact/`;
      const note = lang === "ar" ? "يفتح التسجيل والتقديم عبر الإنترنت عند إطلاق بوابة التعلم. تواصل معنا للبدء." : "Online sign-up and applications open when the EduHope learning portal launches. Contact us to get started.";
      const label = lang === "ar" ? "تواصل معنا" : "Contact us";
      document.querySelectorAll("script, link[rel=modulepreload], link[rel=preload], noscript, vite-error-overlay").forEach(node => node.remove());
      const fonts = [...document.querySelectorAll("link[rel=stylesheet]")].map(link => { const href = link.href; link.remove(); return href; });
      const styles = [...document.querySelectorAll("style")].map(style => { const css = style.textContent; style.remove(); return css; });
      // Account actions cannot run on a static page; route them to Contact.
      document.querySelectorAll("a[href]").forEach(anchor => {
        const href = anchor.getAttribute("href");
        if (/\/(login|register|dashboard)(\?|\/|$)|^\/my-learning/.test(href) || /[?&]register=1/.test(href)) anchor.setAttribute("href", contact);
      });
      document.querySelectorAll(".learning-form-runtime").forEach(form => {
        form.querySelectorAll("a.runtime-submit, button.runtime-submit, p[role=status]").forEach(node => node.remove());
        form.querySelector("fieldset")?.setAttribute("disabled", "");
        form.removeAttribute("action");
        const notice = document.createElement("p"); notice.className = "eduhope-static-notice"; notice.textContent = note;
        const link = document.createElement("a"); link.className = "runtime-submit"; link.href = contact; link.textContent = label;
        form.append(notice, link);
      });
      document.querySelectorAll("button.academy-button, .academy-detail .academy-button").forEach(button => {
        const link = document.createElement("a"); link.className = button.className; link.href = contact; link.textContent = label; button.replaceWith(link);
      });
      document.querySelectorAll(".academy-detail a.academy-button").forEach(anchor => { anchor.href = contact; anchor.textContent = label; });
      // Language switch: link to the other language's copy of this page.
      const other = lang === "ar" ? "en" : "ar";
      const otherHref = `${SITE}${other === "ar" ? "/ar" : ""}${slug === "/" ? "" : slug}/`;
      document.querySelectorAll("button").forEach(button => {
        const text = button.textContent.trim();
        if (["العربية", "English", "English | العربية", "English|العربية"].includes(text) || /English\s*\|\s*العربية/.test(text)) {
          const link = document.createElement("a"); link.className = button.className; link.href = otherHref; link.innerHTML = button.innerHTML; link.setAttribute("lang", other); button.replaceWith(link);
        }
      });
      const images = new Set();
      document.querySelectorAll("img[src]").forEach(img => images.add(img.getAttribute("src")));
      document.querySelectorAll("[style*='url(']").forEach(node => (node.getAttribute("style").match(/url\(["']?([^"')]+)["']?\)/g) || []).forEach(match => images.add(match.replace(/^url\(["']?|["']?\)$/g, ""))));
      document.querySelectorAll("img[srcset], source[srcset]").forEach(node => node.removeAttribute("srcset"));
      return { html: document.documentElement.outerHTML, fonts, styles, images: [...images].filter(src => src && !src.startsWith("data:")), title: document.title };
    }, { ACADEMY, SITE, lang, slug });

    let html = snapshot.html;
    for (const src of snapshot.images) {
      try { const asset = await download(src); html = html.split(src.replaceAll("&", "&amp;")).join(asset).split(src).join(asset); } catch (error) { console.warn(`asset skipped: ${src} (${error.message})`); }
    }
    let head = "";
    for (const href of snapshot.fonts) {
      if (!href.startsWith("https://fonts.googleapis.com")) continue;
      const css = await (await fetch(href, { headers: { "user-agent": "Mozilla/5.0 Chrome/130" } })).text();
      head += `<link rel="stylesheet" href="${await saveAsset(href, Buffer.from(css), ".css")}">`;
    }
    for (const css of snapshot.styles) {
      let rewritten = css;
      for (const match of css.match(/url\(["']?(\/(?:uploads|src|assets|node_modules)[^"')]+)["']?\)/g) || []) {
        const src = match.replace(/^url\(["']?|["']?\)$/g, "");
        try { rewritten = rewritten.split(src).join(await download(src)); } catch (error) { console.warn(`css asset skipped: ${src}`); }
      }
      head += `<link rel="stylesheet" href="${await saveAsset("inline-style", Buffer.from(rewritten), ".css")}">`;
    }
    // Absolute SEO URLs (canonical, og:url, og:image) point at the public Madar copy.
    for (const match of new Set(html.split(`${ORIGIN}/uploads/`).slice(1).map(rest => `${ORIGIN}/uploads/${rest.split(/["'\s)]/)[0]}`))) {
      try { html = html.split(match).join(PUBLIC_ORIGIN + await download(match)); } catch (error) { console.warn(`seo asset skipped: ${match}`); }
    }
    html = html.split(`${ORIGIN}${ACADEMY}`).map((part, index) => {
      if (index === 0) return part;
      const end = part.search(/["'\s]/), path = part.slice(0, end).split(/[?#]/)[0].replace(/\/$/, "");
      return PUBLIC_ORIGIN + sitePath(lang, path || "/") + part.slice(end);
    }).join("");
    // Internal academy links become static paths in the same language.
    html = html.replace(/href="\/academy\/eduhope-local([^"#?]*)([^"]*)"/g, (_, path, rest) => `href="${sitePath(lang, path || "/")}${rest.startsWith("#") ? rest : ""}"`);
    html = html.replace("</head>", `${head}<meta name="robots" content="index,follow"></head>`);
    const file = join(OUT, ...sitePath(lang, slug).slice(SITE.length + 1).split("/").filter(Boolean), "index.html");
    await mkdir(dirname(file), { recursive: true });
    await writeFile(file, `<!doctype html>\n${html}\n`);
    console.log(`${lang} ${slug} -> ${file.slice(OUT.length)}`);
  }
  await context.close();
}
await browser.close();
console.log(`assets: ${saved.size}`);
