import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { createElement } from "../core/PageBuilder.factories";
import PageBuilderCarousel from "./PageBuilderCarousel";
import { serializeCarouselSlides } from "./PageBuilderCarousel.utils";

afterEach(cleanup);

describe("PageBuilderCarousel logo slider", () => {
  it("creates a compact trusted-logo component preset", () => {
    const slider = createElement("logoSlider");

    expect(slider).toMatchObject({
      type: "logoSlider",
      carouselVariant: "logos",
      autoScroll: true,
      logoSliderTitle: "Trusted by leading brands",
    });
    expect(slider.styles["--carousel-height"]).toBe("260px");
  });

  it("renders partner names in a horizontal rail and moves with its controls", () => {
    const content = serializeCarouselSlides(
      Array.from({ length: 6 }, (_, index) => ({
        title: `Partner ${index + 1}`,
        description: "Partner",
        image: "",
      }))
    );

    render(
      <PageBuilderCarousel
        content={content}
        variant="logos"
        logoSliderTitle="Trusted by leading brands"
        logoSliderSubtitle="Organizations that work with us."
      />
    );

    expect(screen.getByRole("heading", { name: "Trusted by leading brands" })).toBeTruthy();
    expect(screen.getByLabelText("Partner 1")).toBeTruthy();
    expect(screen.queryByLabelText("Partner 6")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Next partners" }));

    expect(screen.queryByLabelText("Partner 1")).toBeNull();
    expect(screen.getByLabelText("Partner 6")).toBeTruthy();
  });
});