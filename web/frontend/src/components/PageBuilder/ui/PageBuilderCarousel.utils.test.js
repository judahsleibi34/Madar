import { describe, expect, it } from "vitest";

import {
  getHighQualityCarouselImageUrl,
  parseCarouselSlides,
  serializeCarouselSlides,
} from "./PageBuilderCarousel.utils";

describe("workspace card carousel content", () => {
  it("round-trips card title, description, and image fields", () => {
    const content = serializeCarouselSlides([{
      title: "Design pages",
      description: "Arrange content visually.",
      image: "https://example.com/page.jpg",
    }]);

    expect(parseCarouselSlides(content)).toEqual([{
      title: "Design pages",
      description: "Arrange content visually.",
      image: "https://example.com/page.jpg",
    }]);
  });

  it("keeps legacy three-line carousel slides usable as cards", () => {
    expect(parseCarouselSlides("Old title\nOld description\nhttps://example.com/old.jpg")).toEqual([{
      title: "Old title",
      description: "Old description",
      image: "https://example.com/old.jpg",
    }]);
  });

  it("preserves legacy URLs and managed uploaded assets without rewriting them", () => {
    expect(getHighQualityCarouselImageUrl("https://example.com/legacy.jpg")).toBe(
      "https://example.com/legacy.jpg"
    );
    expect(getHighQualityCarouselImageUrl(
      "/api/uploads/tenant_1/builder_assets/example.png"
    )).toBe("/api/uploads/tenant_1/builder_assets/example.png");
  });
});
