import { describe, expect, it } from "vitest";
import {
  addCompletedFormPage,
  completedFormPagesBefore,
  getFormPageNavigationItems,
} from "./formPageNavigation";

describe("form page navigation", () => {
  it("allows the current and completed pages while disabling unfinished pages", () => {
    const items = getFormPageNavigationItems(5, 2, [0, 1]);
    expect(items.map(({ isDisabled }) => isDisabled)).toEqual([
      false,
      false,
      false,
      true,
      true,
    ]);
    expect(items[2].isCurrent).toBe(true);
  });

  it("restores every earlier page as completed for a resumed draft", () => {
    expect(completedFormPagesBefore(4)).toEqual([0, 1, 2, 3]);
  });

  it("records completed pages without duplicates", () => {
    expect(addCompletedFormPage([0, 1], 1)).toEqual([0, 1]);
    expect(addCompletedFormPage([0, 1], 2)).toEqual([0, 1, 2]);
  });
});