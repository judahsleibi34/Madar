import { describe, expect, it } from "vitest";

import publicAr from "./locales/ar/public.json";
import publicEn from "./locales/en/public.json";

function schemaOf(value) {
  if (Array.isArray(value)) {
    return value.map(schemaOf);
  }

  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, child]) => [key, schemaOf(child)])
    );
  }

  return typeof value;
}

function stringLeaves(value) {
  if (typeof value === "string") return [value];
  if (Array.isArray(value)) return value.flatMap(stringLeaves);
  if (value && typeof value === "object") {
    return Object.values(value).flatMap(stringLeaves);
  }
  return [];
}

describe("public translation schema", () => {
  it("keeps Arabic and English keys and collection shapes aligned", () => {
    expect(schemaOf(publicAr)).toEqual(schemaOf(publicEn));
  });

  it("does not contain replacement characters or common UTF-8 mojibake", () => {
    const copy = stringLeaves(publicAr).join("\n");
    expect(copy).not.toMatch(/\uFFFD|Ã|Â|ط§|ظ„|ط©/u);
  });
});
