import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const storefrontStyles = readFileSync(
  resolve(process.cwd(), "src/styles/public/ecommerce-storefront.css"),
  "utf8"
);

describe("ecommerce storefront media sizing", () => {
  it("gives the desktop landing carousel a taller bounded frame", () => {
    expect(storefrontStyles).toMatch(
      /\.live-store-hero-carousel\s*\{[\s\S]*?min-height:\s*clamp\(500px, 56vw, 800px\)/
    );
    expect(storefrontStyles).toMatch(
      /\.live-store-hero-carousel-content\s*\{[^}]*min-height:\s*clamp\(500px, 56vw, 800px\)/
    );
  });

  it("fills the desktop hero without stretching and preserves the mobile image ratio", () => {
    expect(storefrontStyles).toMatch(
      /\.live-store-hero-carousel-slide img\s*\{[^}]*width:\s*100%;[^}]*height:\s*100%;[^}]*object-fit:\s*cover/
    );
    expect(storefrontStyles).toMatch(
      /@media \(max-width: 760px\)[\s\S]*?\.live-store-hero-carousel-slides\s*\{[^}]*aspect-ratio:\s*16 \/ 9/
    );
  });

  it("provides the Black Friday storefront and popup presentation", () => {
    expect(storefrontStyles).not.toMatch(/\.live-store\.is-black-friday\s*\{/);
    expect(storefrontStyles).toMatch(/\.live-store-sale-bar\.live-store-black-friday-bar\s*\{/);
    expect(storefrontStyles).toMatch(/\.live-store-black-friday-popup\s*\{/);
    expect(storefrontStyles).toMatch(/\.live-store-black-friday-offer\s*\{/);
    expect(storefrontStyles).toMatch(/\.live-store-black-friday-hero\s*\{/);
    expect(storefrontStyles).toMatch(/\.live-store-black-friday-hero-copy > strong\s*\{[^}]*color:\s*var\(--store-campaign-accent\)/);
    expect(storefrontStyles).toMatch(/@media \(max-width: 760px\)[\s\S]*?\.live-store-black-friday-hero\s*\{[^}]*grid-template-columns:\s*1fr/);
  });

  it("keeps pointer focus from adding an unrelated filter outline", () => {
    expect(storefrontStyles).toMatch(
      /\.live-store \.live-store-tags button:focus\s*\{[^}]*outline:\s*none;[^}]*box-shadow:\s*none !important/
    );
    expect(storefrontStyles).toMatch(
      /\.live-store \.live-store-tags button:focus-visible\s*\{[^}]*outline:\s*2px solid var\(--store-accent\)/
    );
  });
});
