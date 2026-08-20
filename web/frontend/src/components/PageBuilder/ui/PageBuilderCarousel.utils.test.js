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

  it("upgrades existing Unsplash card URLs without changing uploaded assets", () => {
    expect(getHighQualityCarouselImageUrl(
      "https://images.unsplash.com/photo-example?w=900&auto=format&fit=crop"
    )).toContain("w=1800");
    expect(getHighQualityCarouselImageUrl(
      "https://images.unsplash.com/photo-example?w=900&auto=format&fit=crop"
    )).toContain("q=90");
    expect(getHighQualityCarouselImageUrl(
      "/api/uploads/tenant_1/builder_assets/example.png"
    )).toBe("/api/uploads/tenant_1/builder_assets/example.png");
  });
});
