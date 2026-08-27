import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const editorStyles = readFileSync(
  resolve(process.cwd(), "src/styles/admin/PageBuilder/reservations.css"),
  "utf8"
);
const runtimeStyles = readFileSync(
  resolve(process.cwd(), "src/components/PageBuilder/blocks/ReservationBlock.css"),
  "utf8"
);

describe("reservation responsive CSS contract", () => {
  it("responds to the editor card's available width", () => {
    expect(editorStyles).toContain("container: reservation-editor / inline-size");
    expect(editorStyles).toMatch(/@container reservation-editor \(max-width: 900px\)[\s\S]*?booking-element-builder[\s\S]*?grid-template-columns: minmax\(0, 1fr\)/);
    expect(editorStyles).toMatch(/@container reservation-editor \(max-width: 460px\)[\s\S]*?booking-component-toolbox-list[\s\S]*?grid-template-columns: minmax\(0, 1fr\)/);
  });

  it("stacks the reservation library before the page becomes cramped", () => {
    expect(editorStyles).toMatch(/@media \(max-width: 1100px\)[\s\S]*?reservation-editor-layout[\s\S]*?grid-template-columns: minmax\(0, 1fr\)/);
  });

  it("keeps the published custom reservation within narrow containers", () => {
    expect(runtimeStyles).toContain("container-type: inline-size");
    expect(runtimeStyles).toMatch(/reservation-block\.has-custom-composition \.reservation-custom-form[\s\S]*?grid-template-columns: minmax\(0, 1fr\)/);
    const customMobileStart = runtimeStyles.lastIndexOf("@container (max-width: 460px)");
    const customNarrowStart = runtimeStyles.indexOf("@container (max-width: 320px)", customMobileStart);
    const mobileSubmitRule = runtimeStyles.indexOf(".reservation-block.has-custom-composition .reservation-custom-submit", customMobileStart);
    expect(customMobileStart).toBeGreaterThan(-1);
    expect(mobileSubmitRule).toBeGreaterThan(customMobileStart);
    expect(mobileSubmitRule).toBeLessThan(customNarrowStart);
    expect(runtimeStyles).toMatch(/reservation-choice-options label > span[\s\S]*?overflow-wrap: anywhere/);
    expect(runtimeStyles).toMatch(/fixed-slot-picker > legend\.sr-only[\s\S]*?position: absolute !important/);
    expect(runtimeStyles).toMatch(/reservation-custom-availability[\s\S]*?grid-template-columns: minmax\(0, 1fr\)[\s\S]*?width: 100%/);
    expect(runtimeStyles).toMatch(/reservation-custom-availability > \*[\s\S]*?width: 100%/);
    expect(runtimeStyles).toMatch(/reservation-custom-availability > h4[\s\S]*?white-space: nowrap[\s\S]*?word-break: normal/);
    expect(runtimeStyles).toMatch(/reservation-block > \.fixed-slot-picker[\s\S]*?grid-area: slots/);
    expect(runtimeStyles).not.toMatch(/\.fixed-slot-picker \{[\s\S]*?grid-area: slots[\s\S]*?inline-size: 100%/);
  });
});
