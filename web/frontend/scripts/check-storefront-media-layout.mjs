import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const css = await readFile(fileURLToPath(new URL("../src/styles/public/ecommerce-storefront.css", import.meta.url)), "utf8");
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  const image = "data:image/svg+xml," + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="2048" height="768" viewBox="0 0 2048 768"><rect width="2048" height="768" fill="navy"/></svg>'
  );
  await page.setContent(`<style>html,body{margin:0}*{box-sizing:border-box}</style>
    <section class="live-store-hero-carousel">
      <div class="live-store-hero-carousel-slides">
        <article class="live-store-hero-carousel-slide is-active"><img src="${image}" alt=""></article>
      </div>
      <div class="live-store-hero-carousel-shade"></div>
      <div class="live-store-hero-carousel-content is-no-copy"></div>
    </section>`);
  await page.addStyleTag({ content: css });
  for (const [width, height] of [[375, 667], [667, 375], [768, 1024], [1440, 900]]) {
    await page.setViewportSize({ width, height });
    const result = await page.evaluate(() => {
      const carousel = document.querySelector(".live-store-hero-carousel");
      const slides = document.querySelector(".live-store-hero-carousel-slides");
      const image = slides.querySelector("img");
      return {
        viewport: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
        carouselHeight: carousel.getBoundingClientRect().height,
        slidesWidth: slides.getBoundingClientRect().width,
        slidesHeight: slides.getBoundingClientRect().height,
        fit: getComputedStyle(image).objectFit,
      };
    });
    assert.ok(result.scrollWidth <= result.viewport + 1, `horizontal overflow at ${width}px`);
    if (width <= 760) {
      assert.equal(result.fit, "contain");
      assert.ok(Math.abs(result.slidesWidth / result.slidesHeight - 16 / 9) < 0.02);
      assert.ok(result.carouselHeight < 520, `old fixed mobile height at ${width}px`);
    } else {
      assert.equal(result.fit, "cover");
    }
    process.stdout.write(`${width}x${height}: ${result.fit}, carousel ${Math.round(result.carouselHeight)}px, no overflow\n`);
  }
  await page.setViewportSize({ width: 375, height: 667 });
  await page.locator(".live-store-hero-carousel-content").evaluate((content) => {
    content.classList.remove("is-no-copy");
    content.innerHTML = "<h1>Promotional title</h1><p>Campaign details remain readable below the image.</p>";
  });
  const withCopy = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
    imageBottom: document.querySelector(".live-store-hero-carousel-slides").getBoundingClientRect().bottom,
    copyTop: document.querySelector(".live-store-hero-carousel-content").getBoundingClientRect().top,
  }));
  assert.ok(withCopy.scrollWidth <= withCopy.viewport + 1);
  assert.ok(withCopy.copyTop >= withCopy.imageBottom - 1, "mobile copy must remain below the uncropped image");
  await page.close();
} finally {
  await browser.close();
}
