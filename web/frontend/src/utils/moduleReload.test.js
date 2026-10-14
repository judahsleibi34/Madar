import { describe, expect, it, vi } from "vitest";
import { isModuleLoadError, reloadOnce } from "./moduleReload";

const memory = () => { const data = new Map(); return { getItem: key => data.get(key) ?? null, setItem: (key, value) => data.set(key, value) }; };

describe("module reload recovery", () => {
  it("recognises failed module loads but not ordinary errors", () => {
    expect(isModuleLoadError(new TypeError("Failed to fetch dynamically imported module: /src/x.jsx"))).toBe(true);
    expect(isModuleLoadError(new SyntaxError("The requested module '/src/a.jsx' does not provide an export named 'default'"))).toBe(true);
    expect(isModuleLoadError(new TypeError("Cannot read properties of undefined"))).toBe(false);
  });
  it("reloads once and never loops within a minute", () => {
    const storage = memory(), reload = vi.fn();
    expect(reloadOnce({ storage, now: 1_000_000, reload })).toBe(true);
    expect(reloadOnce({ storage, now: 1_030_000, reload })).toBe(false);
    expect(reloadOnce({ storage, now: 1_061_000, reload })).toBe(true);
    expect(reload).toHaveBeenCalledTimes(2);
  });
});
