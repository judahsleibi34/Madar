import { describe, expect, it } from "vitest";

import {
  areBuilderSchemasEqual,
  canonicalizeBuilderSchema,
  hashBuilderSchema,
  serializeBuilderSchema,
} from "./PageBuilder.schemaIdentity";

describe("builder schema semantic identity", () => {
  it("ignores recursively reordered object keys while preserving unknown fields", () => {
    const left = {
      theme: { colors: { accent: "#f00", surface: "#fff" }, custom: true },
      pages: [{ id: "home", metadata: { z: 2, a: 1 } }],
    };
    const right = {
      pages: [{ metadata: { a: 1, z: 2 }, id: "home" }],
      theme: { custom: true, colors: { surface: "#fff", accent: "#f00" } },
    };

    expect(areBuilderSchemasEqual(left, right)).toBe(true);
    expect(serializeBuilderSchema(left)).toBe(serializeBuilderSchema(right));
    expect(hashBuilderSchema(left)).toBe(hashBuilderSchema(right));
    expect(canonicalizeBuilderSchema(left).theme.custom).toBe(true);
  });

  it("keeps array order significant for pages and blocks", () => {
    const pages = [{ id: "home" }, { id: "reports" }];
    expect(areBuilderSchemasEqual({ pages }, { pages: [...pages].reverse() })).toBe(false);
    expect(areBuilderSchemasEqual(
      { blocks: [{ id: "a" }, { id: "b" }] },
      { blocks: [{ id: "b" }, { id: "a" }] }
    )).toBe(false);
  });

  it("is immutable, deterministic, and idempotent", () => {
    const source = { z: { b: 2, a: 1 }, a: [3, undefined, -0, Number.NaN] };
    const first = canonicalizeBuilderSchema(source);
    const second = canonicalizeBuilderSchema(source);

    expect(first).toEqual(second);
    expect(canonicalizeBuilderSchema(first)).toEqual(first);
    expect(first).toEqual({ a: [3, null, 0, null], z: { a: 1, b: 2 } });
    expect(source.z).toEqual({ b: 2, a: 1 });
  });

  it("uses explicit JSON-compatible scalar semantics", () => {
    expect(canonicalizeBuilderSchema({ omitted: undefined, kept: null })).toEqual({ kept: null });
    expect(canonicalizeBuilderSchema([undefined, Infinity, -Infinity, Number.NaN, -0]))
      .toEqual([null, null, null, null, 0]);
    expect(canonicalizeBuilderSchema({ at: new Date("2025-01-02T03:04:05.000Z") }))
      .toEqual({ at: "2025-01-02T03:04:05.000Z" });
  });

  it("rejects cycles and unsupported values", () => {
    const cyclic = {};
    cyclic.self = cyclic;
    expect(() => serializeBuilderSchema(cyclic)).toThrow(/Cyclic builder schema value/);
    expect(() => serializeBuilderSchema({ value: 1n })).toThrow(/Unsupported builder schema value/);
    expect(() => serializeBuilderSchema({ value: new Map() })).toThrow(/Unsupported builder schema object/);
  });
});
