import { describe, expect, it } from "vitest";

import {
  getUnderTextImageIds,
  getUnderTextImageRelationships,
  projectUnderTextImagePosition,
} from "./PageBuilder.underTextLayout";

const entry = (id, type, position, layer) => ({ element: { id, type, layer }, position });

describe("under-text image relationships", () => {
  it("recognizes an image meaningfully underneath authored text", () => {
    const ids = getUnderTextImageIds([
      entry("copy", "text", { x: 100, y: 100, width: 500, height: 180 }),
      entry("art", "image", { x: 240, y: 60, width: 400, height: 400 }),
    ]);

    expect(ids.has("art")).toBe(true);
  });

  it("treats a standalone image as normal content", () => {
    const ids = getUnderTextImageIds([
      entry("copy", "text", { x: 80, y: 80, width: 500, height: 120 }),
      entry("photo", "image", { x: 80, y: 300, width: 400, height: 260 }),
    ]);

    expect(ids.has("photo")).toBe(false);
  });

  it("always respects an explicit behind-text layer", () => {
    const ids = getUnderTextImageIds([
      entry("art", "image", { x: 700, y: 700, width: 100, height: 100 }, "behindText"),
    ]);

    expect(ids.has("art")).toBe(true);
  });

  it("projects desktop position and size proportionally at each responsive width", () => {
    const desktop = { x: 600, y: 300, width: 400, height: 400 };

    expect(projectUnderTextImagePosition(desktop, 768)).toEqual({
      x: 384,
      y: 192,
      width: 256,
      height: 256,
    });
    expect(projectUnderTextImagePosition(desktop, 390)).toEqual({
      x: 195,
      y: 97.5,
      width: 130,
      height: 130,
    });
  });

  it("records the image offset from the text it overlaps most", () => {
    const relationships = getUnderTextImageRelationships([
      entry("heading", "heading", { x: 100, y: 20, width: 500, height: 80 }),
      entry("copy", "text", { x: 100, y: 180, width: 500, height: 180 }),
      entry("art", "image", { x: 240, y: 140, width: 400, height: 400 }),
    ]);

    expect(relationships.get("art")).toEqual({
      anchorElementId: "copy",
      offsetX: 140,
      offsetY: -40,
    });
  });
});
