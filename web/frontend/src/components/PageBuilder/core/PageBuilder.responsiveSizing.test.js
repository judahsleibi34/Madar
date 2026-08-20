import { describe, expect, it } from "vitest";

import {
  getMobileContentBounds,
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

  it("centers neutral buttons while preserving explicit edge alignment", () => {
    const bounds = getTabletContentBounds(768);
    const result = resolveResponsiveElementSizing([
      { element: { id: "neutral", type: "button", styles: { alignSelf: "auto" } }, position: { x: 40, y: 400, width: 220, height: 52 } },
      { element: { id: "left", type: "button", styles: { alignSelf: "flex-start" } }, position: { x: 40, y: 500, width: 220, height: 52 } },
      { element: { id: "right", type: "button", styles: { alignSelf: "flex-end" } }, position: { x: 40, y: 600, width: 220, height: 52 } },
    ], "tablet", 768);

    expect(result[0].position.x).toBeCloseTo(bounds.x + (bounds.width - 220) / 2, 3);
    expect(result[1].position.x).toBe(bounds.x);
    expect(result[2].position.x).toBe(bounds.x + bounds.width - 220);
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

  it("leaves desktop, tablet backgrounds, and saved input untouched", () => {
    const entries = [entry("art", "image", { x: 0, y: 0, width: 768, height: 400 }, "behindText")];
    const before = JSON.stringify(entries);

    expect(resolveResponsiveElementSizing(entries, "desktop", 1200)[0].position)
      .toEqual(entries[0].position);
    expect(resolveResponsiveElementSizing(entries, "tablet", 768)[0].position)
      .toEqual(entries[0].position);
    expect(JSON.stringify(entries)).toBe(before);
  });
});

describe("mobile responsive element sizing", () => {
  it("gives headings and text a readable full-width content lane", () => {
    const bounds = getMobileContentBounds(390);
    const result = resolveResponsiveElementSizing([
      entry("heading", "heading", { x: 18, y: 200, width: 205, height: 180 }),
      entry("copy", "text", { x: 18, y: 410, width: 240, height: 120 }),
    ], "mobile", 390);

    expect(result[0].position).toEqual({ x: bounds.x, y: 200, width: bounds.width, height: 180 });
    expect(result[1].position).toEqual({ x: bounds.x, y: 410, width: bounds.width, height: 120 });
  });

  it("stacks editorial cards at the safe mobile width with the fixed base height", () => {
    const bounds = getMobileContentBounds(390);
    const [card] = resolveResponsiveElementSizing([{
      element: { id: "family", type: "imageButton", imageButtonVariant: "editorialCard" },
      position: { x: 210, y: 700, width: 180, height: 310 },
    }], "mobile", 390);

    expect(card.position).toEqual({ x: bounds.x, y: 700, width: bounds.width, height: 240 });
  });

  it("preserves movable under-text artwork on mobile", () => {
    const artwork = {
      ...entry("portrait", "image", { x: 170, y: 60, width: 220, height: 300 }),
      flowRole: "underText",
    };
    const [result] = resolveResponsiveElementSizing([artwork], "mobile", 390);

    expect(result.position).toEqual(artwork.position);
    expect(result.flowRole).toBe("underText");
  });

  it("centers a default button in the mobile safe lane", () => {
    const bounds = getMobileContentBounds(390);
    const [button] = resolveResponsiveElementSizing([{
      element: { id: "cta", type: "button", styles: { alignSelf: "auto" } },
      position: { x: 12, y: 620, width: 298, height: 48 },
    }], "mobile", 390);

    expect(button.position.x).toBe(bounds.x + (bounds.width - 298) / 2);
    expect(button.position.width).toBe(298);
  });

  it("uses the whole mobile lane for a stretch-oriented button", () => {
    const bounds = getMobileContentBounds(390);
    const [button] = resolveResponsiveElementSizing([{
      element: { id: "cta", type: "button", styles: { alignSelf: "stretch" } },
      position: { x: 12, y: 620, width: 180, height: 48 },
    }], "mobile", 390);

    expect(button.position.x).toBe(bounds.x);
    expect(button.position.width).toBe(bounds.width);
  });
});
