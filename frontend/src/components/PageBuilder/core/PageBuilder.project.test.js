import { describe, expect, it } from "vitest";
import { createElement, createPage, createSection } from "./PageBuilder.factories";
import { getSectionElements } from "./PageBuilder.layout";
import { cleanBuilderProject } from "./PageBuilder.project";

describe("cleanBuilderProject", () => {
  it("keeps the full page canvas when it contains a Metrics component", () => {
    const heading = createElement("heading", { content: "Keep this heading" });
    const metric = createElement("metric");
    const section = createSection({
      name: "Page Canvas",
      isPageCanvas: true,
      mode: "direct",
      rows: [],
      freeElements: [heading, metric],
    });
    const page = createPage("Home", [section], { canvasLayoutVersion: 1 });

    const cleaned = cleanBuilderProject({
      name: "Metrics site",
      pages: [page],
      activePageId: page.id,
    });

    const elements = getSectionElements(cleaned.pages[0].sections[0]);

    expect(elements.map((element) => element.id)).toEqual(
      expect.arrayContaining([heading.id, metric.id])
    );
    expect(elements).toHaveLength(2);
  });

  it("keeps existing canvas elements when a new Metrics component is added", () => {
    const existing = [
      createElement("heading"),
      createElement("text"),
      createElement("image"),
    ];
    const section = createSection({
      name: "Page Canvas",
      isPageCanvas: true,
      mode: "direct",
      rows: [],
      freeElements: existing,
    });
    const page = createPage("Home", [section], { canvasLayoutVersion: 1 });
    const metric = createElement("metric");
    const projectAfterAdd = {
      name: "Metrics site",
      pages: [{
        ...page,
        sections: [{ ...section, freeElements: [...existing, metric] }],
      }],
      activePageId: page.id,
    };

    const cleaned = cleanBuilderProject(projectAfterAdd);
    const elements = getSectionElements(cleaned.pages[0].sections[0]);

    expect(elements.map((element) => element.id)).toEqual(
      expect.arrayContaining([...existing.map((element) => element.id), metric.id])
    );
    expect(elements).toHaveLength(4);
  });
});
