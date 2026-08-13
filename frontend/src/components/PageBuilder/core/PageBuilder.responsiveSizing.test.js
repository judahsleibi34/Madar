import { describe, expect, it } from "vitest";

import {
  getTabletContentBounds,
  resolveResponsiveElementSizing,
} from "./PageBuilder.responsiveSizing";

const entry = (id, type, position, layer) => ({ element: { id, type, layer }, position });

describe("tablet responsive element sizing", () => {
  it("gives a single flow component the full safe content lane", () => {
    const bounds = getTabletContentBounds(768);
    const [text] = resolveResponsiveElementSizing([
      entry("copy", "text", { x: 40, y: 80, width: 300, height: 180 }),
    ], "tablet", 768);

    expect(text.position).toEqual({ x: bounds.x, y: 80, width: bounds.width, height: 180 });
  });

  it("centers and proportionally enlarges tablet media", () => {
    const [image] = resolveResponsiveElementSizing([
      entry("image", "image", { x: 40, y: 200, width: 300, height: 200 }),
    ], "tablet", 768);

    expect(image.position.width).toBeCloseTo(427.8, 2);
    expect(image.position.height).toBeCloseTo(285.2, 2);
    expect(image.position.x).toBeCloseTo(170.1, 2);
  });

  it("preserves inferred under-text artwork while sizing standalone images normally", () => {
    const [art, photo] = resolveResponsiveElementSizing([
      { ...entry("art", "image", { x: 280, y: 120, width: 360, height: 360 }), flowRole: "underText" },
      entry("photo", "image", { x: 20, y: 620, width: 300, height: 200 }),
    ], "tablet", 768);

    expect(art.position).toEqual({ x: 280, y: 120, width: 360, height: 360 });
    expect(photo.position.width).toBeCloseTo(427.8, 2);
    expect(photo.position.x).toBeCloseTo(170.1, 2);
  });

  it("scales side-by-side elements together instead of stacking their widths", () => {
    const result = resolveResponsiveElementSizing([
      entry("left", "card", { x: 20, y: 40, width: 330, height: 180 }),
      entry("right", "card", { x: 390, y: 40, width: 330, height: 180 }),
    ], "tablet", 768);

    expect(result[0].position.x).toBeLessThan(result[1].position.x);
    expect(result[0].position.x + result[0].position.width)
      .toBeLessThanOrEqual(result[1].position.x);
    expect(result[0].position.y).toBe(result[1].position.y);
  });

  it("leaves desktop, mobile, backgrounds, and saved input untouched", () => {
    const entries = [entry("art", "image", { x: 0, y: 0, width: 768, height: 400 }, "behindText")];
    const before = JSON.stringify(entries);

    expect(resolveResponsiveElementSizing(entries, "desktop", 1200)[0].position)
      .toEqual(entries[0].position);
    expect(resolveResponsiveElementSizing(entries, "mobile", 390)[0].position)
      .toEqual(entries[0].position);
    expect(resolveResponsiveElementSizing(entries, "tablet", 768)[0].position)
      .toEqual(entries[0].position);
    expect(JSON.stringify(entries)).toBe(before);
  });
});
