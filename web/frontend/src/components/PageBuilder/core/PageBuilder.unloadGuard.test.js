import { describe, expect, it, vi } from "vitest";

import {
  isBuilderReloadShortcut,
  requestBuilderUnloadWarning,
} from "./PageBuilder.unloadGuard";

describe("Page Builder unload guard", () => {
  it("recognizes refresh commands that React can intercept", () => {
    expect(isBuilderReloadShortcut({ key: "F5" })).toBe(true);
    expect(isBuilderReloadShortcut({ key: "r", ctrlKey: true })).toBe(true);
    expect(isBuilderReloadShortcut({ key: "R", metaKey: true })).toBe(true);
    expect(isBuilderReloadShortcut({ key: "r" })).toBe(false);
  });
  it("requests the native browser warning for unsaved work", () => {
    const event = { preventDefault: vi.fn(), returnValue: false };

    expect(requestBuilderUnloadWarning(event, true)).toBe(true);
    expect(event.preventDefault).toHaveBeenCalledOnce();
    expect(event.returnValue).toBe(true);
  });

  it("does not block after the server has acknowledged all work", () => {
    const event = { preventDefault: vi.fn(), returnValue: false };

    expect(requestBuilderUnloadWarning(event, false)).toBe(false);
    expect(event.preventDefault).not.toHaveBeenCalled();
    expect(event.returnValue).toBe(false);
  });
});
