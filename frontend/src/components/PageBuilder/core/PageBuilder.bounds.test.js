import { describe, expect, it } from "vitest";

import {
  clampElementToBounds,
  clientPointToCanvasLocal,
  getCanvasLocalGeometry,
  getImmediateParentCanvasGeometry,
} from "./PageBuilder.bounds";

const bounds = { x: 0, y: 0, width: 300, height: 200 };
const size = { width: 80, height: 50 };

describe("clampElementToBounds dragging", () => {
  it.each([
    ["left", { x: -40, y: 70, ...size }, { x: 0, y: 70 }],
    ["top", { x: 90, y: -25, ...size }, { x: 90, y: 0 }],
    ["right", { x: 280, y: 70, ...size }, { x: 220, y: 70 }],
    ["bottom", { x: 90, y: 190, ...size }, { x: 90, y: 150 }],
  ])("clamps against the %s edge", (_edge, position, expected) => {
    expect(clampElementToBounds(position, bounds)).toMatchObject(expected);
  });

  it("shrinks an element larger than its immediate parent", () => {
    expect(
      clampElementToBounds(
        { x: 40, y: 30, width: 500, height: 400 },
        bounds,
        { minWidth: 360, minHeight: 250 }
      )
    ).toEqual({ x: 0, y: 0, width: 300, height: 200 });
  });
});

describe("clampElementToBounds resizing", () => {
  it.each([
    ["left", { x: -20, y: 40, width: 120, height: 60 }, { x: 0, width: 120 }],
    ["top", { x: 40, y: -20, width: 120, height: 60 }, { y: 0, height: 60 }],
    ["right", { x: 240, y: 40, width: 120, height: 60 }, { x: 240, width: 60 }],
    ["bottom", { x: 40, y: 170, width: 120, height: 80 }, { y: 170, height: 30 }],
  ])("prevents resizing beyond the %s edge", (_edge, position, expected) => {
    expect(
      clampElementToBounds(position, bounds, {
        minWidth: 40,
        minHeight: 30,
        mode: "resize",
      })
    ).toMatchObject(expected);
  });
});

describe("clampElementToBounds downward canvas growth", () => {
  it("keeps the top edge clamped while allowing a dragged element below the bottom", () => {
    expect(
      clampElementToBounds(
        { x: 280, y: -30, width: 80, height: 50 },
        bounds,
        { allowBottomOverflow: true }
      )
    ).toEqual({ x: 220, y: 0, width: 80, height: 50 });

    expect(
      clampElementToBounds(
        { x: 40, y: 260, width: 80, height: 50 },
        bounds,
        { allowBottomOverflow: true }
      )
    ).toEqual({ x: 40, y: 260, width: 80, height: 50 });
  });

  it("keeps horizontal resize bounds but allows height to extend downward", () => {
    expect(
      clampElementToBounds(
        { x: 260, y: 170, width: 120, height: 140 },
        bounds,
        {
          minWidth: 40,
          minHeight: 30,
          mode: "resize",
          allowBottomOverflow: true,
        }
      )
    ).toEqual({ x: 260, y: 170, width: 40, height: 140 });
  });
});

describe("canvas-local geometry", () => {
  it("accounts for transforms, model scale, scrolling, and borders", () => {
    const canvas = {
      offsetWidth: 110,
      offsetHeight: 60,
      clientWidth: 100,
      clientHeight: 50,
      clientLeft: 5,
      clientTop: 3,
      scrollLeft: 20,
      scrollTop: 10,
      getBoundingClientRect: () => ({
        left: 10,
        top: 20,
        width: 220,
        height: 120,
      }),
    };

    expect(
      getCanvasLocalGeometry(canvas, { coordinateScale: 0.5 })?.bounds
    ).toEqual({ x: 0, y: 0, width: 200, height: 100 });
    expect(
      clientPointToCanvasLocal(canvas, 70, 76, { coordinateScale: 0.5 })
    ).toMatchObject({ x: 90, y: 70 });
  });

  it("uses a nested element's immediate parent as its canvas", () => {
    const outer = { clientWidth: 900, clientHeight: 700 };
    const parent = {
      parentElement: outer,
      offsetWidth: 240,
      offsetHeight: 160,
      clientWidth: 240,
      clientHeight: 160,
      clientLeft: 0,
      clientTop: 0,
      scrollLeft: 0,
      scrollTop: 0,
      getBoundingClientRect: () => ({
        left: 100,
        top: 80,
        width: 240,
        height: 160,
      }),
    };
    const nestedElement = { parentElement: parent };

    expect(
      getImmediateParentCanvasGeometry(nestedElement)?.geometry?.bounds
    ).toEqual({ x: 0, y: 0, width: 240, height: 160 });
  });
});
