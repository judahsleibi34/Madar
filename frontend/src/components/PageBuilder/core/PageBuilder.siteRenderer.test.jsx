import { act, render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SiteRenderer from "./PageBuilder.siteRenderer";
import { getFitPresentationZoom } from "./PageBuilder.artboard";

const project = {
  theme: {},
  pages: [],
};

const activePage = {
  id: "page_1",
  sections: [
    {
      id: "section_1",
      mode: "direct",
      layout: { width: "full", background: "transparent", minHeight: 500 },
      freeElements: [
        {
          id: "element_1",
          type: "text",
          content: "Stable geometry",
          styles: {},
          position: {
            desktop: { x: 100, y: 80, width: 320, height: 90 },
            tablet: { x: 40, y: 50, width: 280, height: 80 },
            mobile: { x: 20, y: 30, width: 200, height: 70 },
          },
        },
      ],
    },
  ],
};

describe("SiteRenderer artboard camera", () => {
  beforeEach(() => {
    globalThis.ResizeObserver = class ResizeObserver {
      observe() {}
      disconnect() {}
    };
    vi.stubGlobal("requestAnimationFrame", (callback) => {
      callback();
      return 1;
    });
    vi.stubGlobal("cancelAnimationFrame", () => {});
  });

  it("keeps logical element geometry identical at Fit and 100% zoom", () => {
    const renderElement = (element) => <span>{element.content}</span>;
    const view = render(
      <SiteRenderer
        project={project}
        activePage={activePage}
        viewportMode="desktop"
        presentationZoom={1}
        renderElement={renderElement}
      />
    );

    const frameAt100 = view.container.querySelector('[data-builder-element-id="element_1"]');
    const logicalStyleAt100 = {
      width: frameAt100.style.width,
      height: frameAt100.style.height,
      transform: frameAt100.style.transform,
    };

    view.rerender(
      <SiteRenderer
        project={project}
        activePage={activePage}
        viewportMode="desktop"
        presentationZoom={0.5}
        renderElement={renderElement}
      />
    );

    const frameAtFit = view.container.querySelector('[data-builder-element-id="element_1"]');
    const camera = view.container.querySelector(".site-renderer-camera");
    const artboard = view.container.querySelector(".site-renderer-artboard");

    expect({
      width: frameAtFit.style.width,
      height: frameAtFit.style.height,
      transform: frameAtFit.style.transform,
    }).toEqual(logicalStyleAt100);
    expect(camera.dataset.logicalWidth).toBe("1200");
    expect(camera.style.width).toBe("600px");
    expect(artboard.style.width).toBe("1200px");
    expect(artboard.style.transform).toBe("scale(0.5)");
  });

  it("uses only the explicit viewport mode for responsive geometry", () => {
    const view = render(
      <SiteRenderer
        project={project}
        activePage={activePage}
        viewportMode="mobile"
        presentationZoom={1}
        renderElement={(element) => <span>{element.content}</span>}
      />
    );
    const frame = view.container.querySelector('[data-builder-element-id="element_1"]');
    const artboard = view.container.querySelector(".site-renderer-artboard");

    expect(artboard.style.width).toBe("390px");
    expect(frame.style.width).toBe("200px");
    expect(frame.style.height).toBe("70px");
    expect(frame.style.transform).toBe("translate3d(20px, 30px, 0)");
  });

  it("bleeds only the section background while content stays on the canonical artboard", () => {
    const view = render(
      <SiteRenderer
        project={project}
        activePage={activePage}
        viewportMode="desktop"
        presentationZoom={1}
        availablePresentationWidth={1920}
        renderElement={(element) => <span>{element.content}</span>}
      />
    );
    const section = view.container.querySelector(".site-section");
    const bleed = view.container.querySelector(".site-section-bleed-background");
    const frame = view.container.querySelector(".direct-layout-frame");

    expect(section.classList.contains("has-full-bleed")).toBe(true);
    expect(section.style.backgroundColor).toBe("transparent");
    expect(bleed.style.width).toBe("1920px");
    expect(frame.style.width).toBe("1200px");
  });

  it("changes only camera presentation for Editor Fit workspace widths", () => {
    const originalSchema = JSON.stringify(activePage);
    const renderElement = (element) => <span>{element.content}</span>;
    const workspaceWidths = [1600, 1200, 1024, 769, 600, 390];
    const view = render(
      <SiteRenderer
        project={project}
        activePage={activePage}
        viewportMode="desktop"
        presentationZoom={1}
        availablePresentationWidth={1600}
        renderElement={renderElement}
      />
    );
    const logicalFrames = [];

    workspaceWidths.forEach((workspaceWidth) => {
      const zoom = getFitPresentationZoom(workspaceWidth, 1200);
      view.rerender(
        <SiteRenderer
          project={project}
          activePage={activePage}
          viewportMode="desktop"
          presentationZoom={zoom}
          availablePresentationWidth={workspaceWidth}
          renderElement={renderElement}
        />
      );
      const camera = view.container.querySelector(".site-renderer-camera");
      const artboard = view.container.querySelector(".site-renderer-artboard");
      const frame = view.container.querySelector("[data-builder-element-id='element_1']");
      logicalFrames.push({ width: frame.style.width, height: frame.style.height, transform: frame.style.transform });
      expect(Number(camera.dataset.presentationZoom)).toBeCloseTo(zoom, 4);
      expect(camera.style.width).toBe(String(1200 * zoom) + "px");
      expect(artboard.style.width).toBe("1200px");
    });

    expect(logicalFrames.every((frame) => JSON.stringify(frame) === JSON.stringify(logicalFrames[0]))).toBe(true);
    expect(JSON.stringify(activePage)).toBe(originalSchema);
  });

  it("propagates derived dynamic height through section flow without mutating schema", async () => {
    const observerCallbacks = [];
    const animationCallbacks = [];
    vi.stubGlobal("requestAnimationFrame", (callback) => {
      animationCallbacks.push(callback);
      return animationCallbacks.length;
    });
    globalThis.ResizeObserver = class ResizeObserver {
      constructor(callback) { observerCallbacks.push(callback); }
      observe() {}
      disconnect() {}
    };
    const dynamicPage = {
      id: "dynamic_page",
      sections: [
        {
          id: "dynamic_section",
          mode: "direct",
          layout: { width: "full", background: "transparent", minHeight: 300 },
          freeElements: [{
            id: "dynamic_form",
            type: "formBlock",
            styles: {},
            position: { desktop: { x: 100, y: 100, width: 400, height: 100 } },
          }],
        },
        {
          id: "following_section",
          mode: "direct",
          layout: { width: "large", background: "transparent", minHeight: 200 },
          freeElements: [{
            id: "following_text",
            type: "text",
            content: "Following content",
            styles: {},
            position: { desktop: { x: 20, y: 20, width: 200, height: 50 } },
          }],
        },
      ],
    };
    const originalSchema = JSON.stringify(dynamicPage);
    const view = render(
      <SiteRenderer
        project={project}
        activePage={dynamicPage}
        viewportMode="desktop"
        presentationZoom={1}
        renderElement={(element) => <div>{element.content || "Dynamic form"}</div>}
      />
    );
    const content = view.container.querySelector(".direct-element-frame-formBlock > .direct-element-content");
    Object.defineProperty(content, "scrollHeight", { configurable: true, value: 620 });
    Object.defineProperty(content, "offsetHeight", { configurable: true, value: 620 });

    await act(async () => {
      animationCallbacks.splice(0).forEach((callback) => callback());
    });

    const sections = view.container.querySelectorAll(".site-section");
    const formFrame = view.container.querySelector(".direct-element-frame-formBlock");
    expect(sections[0].style.minHeight).toBe("768px");
    expect(formFrame.style.height).toBe("620px");
    expect(sections[0].compareDocumentPosition(sections[1]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    Object.defineProperty(content, "scrollHeight", { configurable: true, value: 700 });
    Object.defineProperty(content, "offsetHeight", { configurable: true, value: 700 });
    await act(async () => {
      observerCallbacks.slice().forEach((callback) => callback([]));
      animationCallbacks.splice(0).forEach((callback) => callback());
    });
    expect(sections[0].style.minHeight).toBe("848px");
    expect(formFrame.style.height).toBe("700px");
    expect(JSON.stringify(dynamicPage)).toBe(originalSchema);
  });

  it("renders smart live geometry at the actual CSS width without whole-page scaling", () => {
    const smartProject = {
      theme: {},
      responsiveLayout: { mode: "smart", engineVersion: 1 },
    };
    const originalSchema = JSON.stringify(activePage);
    const view = render(
      <SiteRenderer
        project={smartProject}
        activePage={activePage}
        viewportMode="tablet"
        presentationZoom={1}
        responsiveLayoutWidth={900}
        availablePresentationWidth={1440}
        renderElement={(element) => <span>{element.content}</span>}
      />
    );
    const camera = view.container.querySelector(".site-renderer-camera");
    const artboard = view.container.querySelector(".site-renderer-artboard");
    const directFrame = view.container.querySelector(".direct-layout-frame");
    const bleed = view.container.querySelector(".site-section-bleed-background");

    expect(camera.dataset.responsiveLayoutMode).toBe("smart");
    expect(camera.dataset.presentationZoom).toBe("1.0000");
    expect(camera.dataset.logicalWidth).toBe("900");
    expect(camera.style.width).toBe("900px");
    expect(artboard.style.width).toBe("900px");
    expect(directFrame.style.width).toBe("900px");
    expect(bleed.style.width).toBe("1440px");
    expect(JSON.stringify(activePage)).toBe(originalSchema);
  });

  it("measures generic smart content and pushes a downstream element without mutating schema", async () => {
    const observerCallbacks = [];
    const animationCallbacks = [];
    vi.stubGlobal("requestAnimationFrame", (callback) => {
      animationCallbacks.push(callback);
      return animationCallbacks.length;
    });
    globalThis.ResizeObserver = class ResizeObserver {
      constructor(callback) { observerCallbacks.push(callback); }
      observe() {}
      disconnect() {}
    };
    const smartProject = {
      theme: {},
      responsiveLayout: { mode: "smart", engineVersion: 1 },
    };
    const smartPage = {
      id: "smart-dynamic-page",
      sections: [{
        id: "smart-dynamic-section",
        mode: "direct",
        layout: { width: "full", background: "transparent", minHeight: 200 },
        freeElements: [
          {
            id: "growing-text",
            type: "text",
            content: "Growing text",
            styles: {},
            position: {
              desktop: { x: 24, y: 20, width: 320, height: 80 },
              tablet: { x: 24, y: 20, width: 320, height: 80 },
              mobile: { x: 24, y: 20, width: 320, height: 80 },
            },
          },
          {
            id: "future-block",
            type: "future-component",
            content: "Future component",
            styles: {},
            position: {
              desktop: { x: 24, y: 120, width: 320, height: 80 },
              tablet: { x: 24, y: 120, width: 320, height: 80 },
              mobile: { x: 24, y: 120, width: 320, height: 80 },
            },
          },
        ],
      }],
    };
    const originalSchema = JSON.stringify(smartPage);
    const view = render(
      <SiteRenderer
        project={smartProject}
        activePage={smartPage}
        viewportMode="tablet"
        presentationZoom={1}
        responsiveLayoutWidth={768}
        renderElement={(element) => <div>{element.content}</div>}
      />
    );
    const content = view.container.querySelector('[data-builder-element-id="growing-text"] > .direct-element-content');
    Object.defineProperty(content, "scrollHeight", { configurable: true, value: 300 });
    Object.defineProperty(content, "offsetHeight", { configurable: true, value: 300 });

    await act(async () => {
      observerCallbacks.slice().forEach((callback) => callback([]));
      animationCallbacks.splice(0).forEach((callback) => callback());
    });

    const growing = view.container.querySelector('[data-builder-element-id="growing-text"]');
    const downstream = view.container.querySelector('[data-builder-element-id="future-block"]');
    expect(growing.style.height).toBe("300px");
    expect(Number(downstream.dataset.logicalY)).toBeGreaterThanOrEqual(336);
    expect(JSON.stringify(smartPage)).toBe(originalSchema);
  });
});
