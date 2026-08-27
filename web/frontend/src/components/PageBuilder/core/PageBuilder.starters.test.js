import { describe, expect, it } from "vitest";

import { buildStarterProject, createInitialProject, PILATES_DEMO_THEME } from "./PageBuilder.starters";

const getElements = (page) => (page?.sections || []).flatMap((section) => [
  ...(section.freeElements || []),
  ...(section.rows || []).flatMap((row) =>
    (row.columns || []).flatMap((column) => column.elements || [])
  ),
]);

describe("Pilates demo starter", () => {
  it("uses the Pilates project as the public demo", () => {
    const project = createInitialProject();

    expect(project.name).toBe("Form & Flow");
    expect(project.theme).toEqual(PILATES_DEMO_THEME);
    expect(project.siteChrome.brand).toBe("Form & Flow");
    expect(project.siteChrome.footerStoreName).toBe("Form & Flow");
    expect(project.pages.map((page) => page.name)).toEqual(["Studio", "Book a Class", "Shop"]);
    expect(project.siteChrome.headerButtonPageId).toBe(project.pages[1].id);
    expect(project.siteChrome.footerHelpLinks).toBeTruthy();
    expect(project.siteChrome.footerSocialLinks).toBeTruthy();
    expect(project.siteChrome.footerPaymentMethods).toBeTruthy();
  });

  it("provides fixed future booking slots and dummy shop products", () => {
    const project = buildStarterProject("pilates");
    const studioElements = getElements(project.pages[0]);
    const bookingElements = getElements(project.pages[1]);
    const reservation = bookingElements.find((element) => element.type === "reservationBlock");
    const today = new Date().toISOString().slice(0, 10);

    expect(reservation.reservation.bookingMode).toBe("fixed");
    expect(reservation.reservation.availableDates).toHaveLength(5);
    expect(reservation.reservation.availableDates.every((date) => date > today)).toBe(true);
    expect(Object.keys(reservation.reservation.timeSlotsByDate)).toEqual(
      reservation.reservation.availableDates
    );
    expect(reservation.reservation.submitLabel).toBe("Reserve my spot");

    const bookingButtons = studioElements.filter((element) => element.type === "button");
    expect(bookingButtons).toHaveLength(2);
    expect(bookingButtons.every((button) => (
      button.action?.type === "goToPage" && button.action?.pageId === project.pages[1].id
    ))).toBe(true);
    expect(studioElements.filter((element) => element.type === "image")).toHaveLength(1);
    expect(bookingElements.filter((element) => element.type === "image")).toHaveLength(1);
    const classGallery = studioElements.find((element) => element.type === "carousel");
    const gallerySlides = classGallery.content.split("\n\n");
    expect(gallerySlides).toHaveLength(3);
    expect(gallerySlides.every((slide) => /^.+\n.+\nhttps:\/\//.test(slide))).toBe(true);

    const shopElements = getElements(project.pages[2]);
    const shopGallery = shopElements.find((element) => element.type === "carousel");
    const productSlides = shopGallery.content.split("\n\n");
    expect(productSlides).toHaveLength(6);
    expect(productSlides.every((slide) => /^.+\n.+\nhttps:\/\//.test(slide))).toBe(true);
    expect(shopGallery.content).toContain("Studio Grip Socks");
  });

  it("does not leave visible template components empty", () => {
    const project = buildStarterProject("pilates");
    const contentTypes = new Set(["heading", "text", "card", "carousel", "list", "button", "image"]);
    const visibleElements = project.pages.flatMap(getElements).filter((element) => contentTypes.has(element.type));

    expect(visibleElements.length).toBeGreaterThan(0);
    expect(visibleElements.every((element) => String(element.content || "").trim().length > 0)).toBe(true);
    expect(visibleElements.filter((element) => element.type === "image").every((element) => (
      /^https:\/\//.test(element.content)
    ))).toBe(true);
  });
});
