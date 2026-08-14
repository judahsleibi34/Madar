import { describe, expect, it } from "vitest";

import {
  RESPONSIVE_ELEMENT_GAP_RATIO,
  resolveDirectElementCollisionPadding,
  resolveMobileReadingOrder,
} from "./PageBuilder.collisionPadding";

const entry = (id, position, layer, flowRole, type) => ({ element: { id, layer, type }, position, flowRole });

describe("direct element collision padding", () => {
  it("uses y, x, then saved array order and cascades later overlaps downward", () => {
    const result = resolveDirectElementCollisionPadding([
      entry("third", { x: 20, y: 70, width: 300, height: 60 }),
      entry("second", { x: 20, y: 40, width: 300, height: 50 }),
      entry("first", { x: 20, y: 10, width: 300, height: 50 }),
    ]);

    expect(result.first.y).toBe(10);
    expect(result.second.y).toBe(10 + 50 + Math.ceil(50 * RESPONSIVE_ELEMENT_GAP_RATIO));
    expect(result.third.y).toBe(
      result.second.y + 50 + Math.ceil(50 * RESPONSIVE_ELEMENT_GAP_RATIO)
    );
  });

  it("preserves side-by-side x/y geometry", () => {
    const result = resolveDirectElementCollisionPadding([
      entry("left", { x: 10, y: 20, width: 150, height: 80 }),
      entry("right", { x: 180, y: 20, width: 150, height: 80 }),
    ]);

    expect(result.left).toEqual({ x: 10, y: 20, width: 150, height: 80 });
    expect(result.right).toEqual({ x: 180, y: 20, width: 150, height: 80 });
  });

  it("does not let background artwork move or push foreground content", () => {
    const result = resolveDirectElementCollisionPadding([
      entry("art", { x: 0, y: 0, width: 390, height: 500 }, "behindText"),
      entry("heading", { x: 20, y: 30, width: 350, height: 90 }),
      entry("copy", { x: 20, y: 80, width: 350, height: 100 }),
    ]);

    expect(result.art.y).toBe(0);
    expect(result.heading.y).toBe(30);
    expect(result.copy.y).toBe(134);
  });

  it("does not move or collide inferred under-text artwork", () => {
    const result = resolveDirectElementCollisionPadding([
      entry("art", { x: 0, y: 80, width: 390, height: 500 }, undefined, "underText"),
      entry("copy", { x: 20, y: 100, width: 350, height: 120 }, undefined, undefined, "text"),
      entry("card", { x: 20, y: 180, width: 350, height: 100 }),
    ]);

    expect(result.art.y).toBe(80);
    expect(result.copy.y).toBe(100);
    expect(result.card.y).toBe(80 + 500 + Math.ceil(500 * RESPONSIVE_ELEMENT_GAP_RATIO));
  });

  it("does not mutate saved positions", () => {
    const entries = [
      entry("one", { x: 20, y: 20, width: 300, height: 80 }),
      entry("two", { x: 20, y: 40, width: 300, height: 80 }),
    ];
    const before = JSON.stringify(entries);

    resolveDirectElementCollisionPadding(entries);

    expect(JSON.stringify(entries)).toBe(before);
  });

  it("moves under-text artwork with its wrapped text anchor on mobile", () => {
    const result = resolveDirectElementCollisionPadding([
      entry("heading", { x: 20, y: 30, width: 350, height: 120 }, undefined, undefined, "heading"),
      entry("copy", { x: 20, y: 80, width: 350, height: 220 }, undefined, undefined, "text"),
      {
        ...entry("art", { x: 78, y: 100, width: 130, height: 130 }, undefined, "underText", "image"),
        anchorElementId: "copy",
        anchorOffsetX: 45.5,
        anchorOffsetY: -13,
      },
      entry("card", { x: 20, y: 310, width: 350, height: 200 }, undefined, undefined, "card"),
    ]);

    expect(result.copy.y).toBe(168);
    expect(result.art.x).toBe(78);
    expect(result.art.y).toBe(155);
    expect(result.card.y).toBe(421);
  });

  it("lets horizontal separators sit directly below the preceding element", () => {
    const result = resolveDirectElementCollisionPadding([
      entry("heading", { x: 20, y: 100, width: 350, height: 100 }, undefined, undefined, "heading"),
      entry("line", { x: 20, y: 150, width: 350, height: 32 }, undefined, undefined, "thinDivider"),
    ]);

    expect(result.line.y).toBe(200);
  });

  it('repairs mobile geometry using desktop heading and reading order', () => {
    const result = resolveMobileReadingOrder([
      { ...entry('copy', { x: 20, y: 30, width: 350, height: 180 }, undefined, undefined, 'text'), readingOrderPosition: { x: 70, y: 360, width: 600, height: 180 } },
      { ...entry('tagline', { x: 20, y: 260, width: 350, height: 60 }, undefined, undefined, 'text'), readingOrderPosition: { x: 70, y: 445, width: 600, height: 60 } },
      { ...entry('heading', { x: 20, y: 550, width: 350, height: 110 }, undefined, undefined, 'heading'), readingOrderPosition: { x: 70, y: 100, width: 500, height: 110 } },
      { ...entry('button', { x: 20, y: 700, width: 300, height: 52 }, undefined, undefined, 'button'), readingOrderPosition: { x: 70, y: 560, width: 260, height: 52 } },
    ]);
    const headingBottom = 30 + 110 + Math.ceil(110 * RESPONSIVE_ELEMENT_GAP_RATIO);
    const copyBottom = headingBottom + 180 + Math.ceil(180 * RESPONSIVE_ELEMENT_GAP_RATIO);
    const taglineBottom = copyBottom + 60 + Math.ceil(60 * RESPONSIVE_ELEMENT_GAP_RATIO);

    expect(result.map((item) => item.position.y)).toEqual([headingBottom, copyBottom, 30, taglineBottom]);
  });

  it('derives timeless -> artwork -> heading even when legacy storage starts with the image', () => {
    const result = resolveMobileReadingOrder([
      { ...entry('portrait', { x: 170, y: 20, width: 200, height: 260 }, 'behindText', undefined, 'image'), readingOrderPosition: { x: 650, y: 40, width: 500, height: 650 } },
      { ...entry('timeless', { x: 20, y: 410, width: 350, height: 40 }, undefined, undefined, 'text'), readingOrderPosition: { x: 70, y: 100, width: 300, height: 40 } },
      { ...entry('heading', { x: 20, y: 520, width: 350, height: 180 }, undefined, undefined, 'heading'), readingOrderPosition: { x: 70, y: 190, width: 500, height: 180 } },
    ]);
    const gapAfterTimeless = Math.ceil(40 * RESPONSIVE_ELEMENT_GAP_RATIO);
    const gapAfterPortrait = Math.ceil(260 * RESPONSIVE_ELEMENT_GAP_RATIO);

    expect(result[1].position.y).toBe(20);
    expect(result[0].position.y).toBe(20 + 40 + gapAfterTimeless);
    expect(result[2].position.y).toBe(20 + 40 + gapAfterTimeless + 260 + gapAfterPortrait);
    expect(result[0].element.layer).toBe('behindText');
  });

  it('applies the indexed phone sequence even when saved mobile y values look ordered', () => {
    const result = resolveMobileReadingOrder([
      { ...entry('portrait', { x: 170, y: 500, width: 200, height: 260 }, 'behindText', undefined, 'image'), readingOrderPosition: { x: 650, y: 40, width: 500, height: 650 } },
      { ...entry('timeless', { x: 20, y: 20, width: 350, height: 40 }, undefined, undefined, 'text'), readingOrderPosition: { x: 70, y: 100, width: 300, height: 40 } },
      { ...entry('heading', { x: 20, y: 100, width: 350, height: 180 }, undefined, undefined, 'heading'), readingOrderPosition: { x: 70, y: 190, width: 500, height: 180 } },
    ]);

    expect(result[1].position.y).toBe(20);
    expect(result[0].position.y).toBeGreaterThan(result[1].position.y);
    expect(result[2].position.y).toBeGreaterThan(result[0].position.y);
  });
});
