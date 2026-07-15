import { describe, expect, it } from "vitest";

import {
  builderValuesEqual,
  mergeBuilderDraftSchemas,
  resolveBuilderDraftConflicts,
} from "./PageBuilder.merge";

const project = () => ({
  defaultPageId: "home",
  theme: { colors: { primary: "#111111", secondary: "#ffffff" } },
  pages: [
    {
      id: "home",
      name: "Home",
      slug: "/",
      sections: [{
        id: "hero",
        freeElements: [
          { id: "heading", type: "heading", content: "Welcome", position: { desktop: { x: 0, y: 0 } } },
          { id: "button", type: "button", content: "Start" },
        ],
      }],
    },
    { id: "about", name: "About", slug: "/about", sections: [] },
  ],
  forms: [{
    id: "contact",
    title: "Contact",
    fields: [{ id: "email", label: "Email", required: true }],
  }],
  workflows: [{ id: "workflow-1", name: "Follow up" }],
  customSupportedField: { nested: { value: "base" } },
  activePageId: "home",
});

const merge = (base, local, server) => mergeBuilderDraftSchemas({
  baseSchema: base,
  localSchema: local,
  serverSchema: server,
});

describe("builder draft three-way merge", () => {
  it("keeps server-only and local-only property changes", () => {
    const base = project();
    const local = { ...base, customSupportedField: { nested: { value: "local" } } };
    const server = { ...base, theme: { ...base.theme, colors: { ...base.theme.colors, primary: "#222222" } } };
    const result = merge(base, local, server);
    expect(result.conflicts).toEqual([]);
    expect(result.mergedSchema.customSupportedField.nested.value).toBe("local");
    expect(result.mergedSchema.theme.colors.primary).toBe("#222222");
  });

  it("accepts the same concurrent value", () => {
    const base = project();
    const local = { ...base, defaultPageId: "about" };
    const server = { ...base, defaultPageId: "about" };
    expect(merge(base, local, server)).toMatchObject({
      mergedSchema: { defaultPageId: "about" },
      conflicts: [],
    });
  });

  it("reports different edits to the same scalar", () => {
    const base = project();
    const local = { ...base, defaultPageId: "local-home" };
    const server = { ...base, defaultPageId: "server-home" };
    const result = merge(base, local, server);
    expect(result.conflicts).toHaveLength(1);
    expect(result.conflicts[0]).toMatchObject({
      path: "defaultPageId",
      localValue: "local-home",
      serverValue: "server-home",
    });
  });

  it("merges additions with different stable IDs", () => {
    const base = project();
    const local = { ...base, pages: [...base.pages, { id: "local", name: "Local", sections: [] }] };
    const server = { ...base, pages: [...base.pages, { id: "server", name: "Server", sections: [] }] };
    const result = merge(base, local, server);
    expect(result.conflicts).toEqual([]);
    // Concurrent additions sharing the same anchor use a deterministic
    // server-then-local tie break without discarding either entity.
    expect(result.mergedSchema.pages.map(({ id }) => id)).toEqual(["home", "about", "server", "local"]);
  });

  it("applies deletion when the other side is unchanged", () => {
    const base = project();
    const local = { ...base, pages: base.pages.filter(({ id }) => id !== "about") };
    const result = merge(base, local, base);
    expect(result.conflicts).toEqual([]);
    expect(result.mergedSchema.pages.map(({ id }) => id)).toEqual(["home"]);
  });

  it("reports delete-versus-modify without losing the modified entity", () => {
    const base = project();
    const local = { ...base, pages: base.pages.filter(({ id }) => id !== "about") };
    const server = {
      ...base,
      pages: base.pages.map((page) => page.id === "about" ? { ...page, name: "About us" } : page),
    };
    const result = merge(base, local, server);
    expect(result.conflicts[0]).toMatchObject({ kind: "delete_modify", path: "pages[id=about]" });
    expect(result.mergedSchema.pages.find(({ id }) => id === "about").name).toBe("About us");
  });

  it("merges changes to different blocks on the same page", () => {
    const base = project();
    const editBlock = (source, id, content) => ({
      ...source,
      pages: source.pages.map((page) => page.id !== "home" ? page : ({
        ...page,
        sections: page.sections.map((section) => ({
          ...section,
          freeElements: section.freeElements.map((block) => block.id === id ? { ...block, content } : block),
        })),
      })),
    });
    const result = merge(base, editBlock(base, "button", "Final Test??"), editBlock(base, "heading", "Remote heading"));
    expect(result.conflicts).toEqual([]);
    const blocks = result.mergedSchema.pages[0].sections[0].freeElements;
    expect(blocks.find(({ id }) => id === "button").content).toBe("Final Test??");
    expect(blocks.find(({ id }) => id === "heading").content).toBe("Remote heading");
  });

  it("reports different edits to the same block property", () => {
    const base = project();
    const setHeading = (content) => ({
      ...base,
      pages: base.pages.map((page) => page.id !== "home" ? page : ({
        ...page,
        sections: page.sections.map((section) => ({
          ...section,
          freeElements: section.freeElements.map((block) => block.id === "heading" ? { ...block, content } : block),
        })),
      })),
    });
    const result = merge(base, setHeading("Local"), setHeading("Server"));
    expect(result.conflicts).toHaveLength(1);
    expect(result.conflicts[0].path).toBe("pages[id=home].sections[id=hero].freeElements[id=heading].content");
  });

  it("merges page and form fields by stable ID", () => {
    const base = project();
    const local = { ...base, pages: base.pages.map((page) => page.id === "about" ? { ...page, name: "Company" } : page) };
    const server = {
      ...base,
      forms: base.forms.map((form) => ({
        ...form,
        fields: form.fields.map((field) => ({ ...field, label: "Work email" })),
      })),
    };
    const result = merge(base, local, server);
    expect(result.conflicts).toEqual([]);
    expect(result.mergedSchema.pages[1].name).toBe("Company");
    expect(result.mergedSchema.forms[0].fields[0].label).toBe("Work email");
  });

  it("merges different theme properties and conflicts on the same property", () => {
    const base = project();
    const local = { ...base, theme: { colors: { ...base.theme.colors, primary: "#aaaaaa" } } };
    const server = { ...base, theme: { colors: { ...base.theme.colors, secondary: "#bbbbbb" } } };
    expect(merge(base, local, server).mergedSchema.theme.colors).toEqual({ primary: "#aaaaaa", secondary: "#bbbbbb" });
    const overlap = merge(base, local, { ...base, theme: { colors: { ...base.theme.colors, primary: "#cccccc" } } });
    expect(overlap.conflicts[0].path).toBe("theme.colors.primary");
  });

  it("preserves unknown supported fields recursively", () => {
    const base = project();
    const local = { ...base, customSupportedField: { ...base.customSupportedField, local: true } };
    const server = { ...base, customSupportedField: { ...base.customSupportedField, server: true } };
    expect(merge(base, local, server).mergedSchema.customSupportedField).toEqual({
      nested: { value: "base" }, local: true, server: true,
    });
  });

  it("accepts a one-sided reorder and reports incompatible two-sided reorder", () => {
    const base = { pages: [{ id: "a" }, { id: "b" }, { id: "c" }] };
    const local = { pages: [{ id: "c" }, { id: "a" }, { id: "b" }] };
    const oneSide = merge(base, local, base);
    expect(oneSide.conflicts).toEqual([]);
    expect(oneSide.mergedSchema.pages.map(({ id }) => id)).toEqual(["c", "a", "b"]);
    const server = { pages: [{ id: "b" }, { id: "c" }, { id: "a" }] };
    expect(merge(base, local, server).conflicts[0]).toMatchObject({ kind: "order", path: "pages.$order" });
  });

  it("is pure, immutable, deterministic, and idempotent", () => {
    const base = project();
    const local = { ...base, defaultPageId: "about" };
    const server = { ...base, theme: { colors: { ...base.theme.colors, primary: "#222222" } } };
    const before = JSON.stringify({ base, local, server });
    const first = merge(base, local, server);
    const second = merge(base, local, server);
    const repeated = merge(base, first.mergedSchema, server);
    expect(JSON.stringify({ base, local, server })).toBe(before);
    expect(first).toEqual(second);
    expect(repeated.conflicts).toEqual([]);
    expect(builderValuesEqual(repeated.mergedSchema, first.mergedSchema)).toBe(true);
  });

  it("resolves scalar and deletion conflicts using explicit choices", () => {
    const base = project();
    const local = {
      ...base,
      defaultPageId: "local",
      pages: base.pages.filter(({ id }) => id !== "about"),
    };
    const server = {
      ...base,
      defaultPageId: "server",
      pages: base.pages.map((page) => page.id === "about" ? { ...page, name: "Changed" } : page),
    };
    const result = merge(base, local, server);
    const resolved = resolveBuilderDraftConflicts({
      mergedSchema: result.mergedSchema,
      conflicts: result.conflicts,
      resolutions: { defaultPageId: "local", "pages[id=about]": "local" },
    });
    expect(resolved.defaultPageId).toBe("local");
    expect(resolved.pages.some(({ id }) => id === "about")).toBe(false);
  });

  it("strips editor-only state before comparison", () => {
    const base = project();
    const local = { ...base, activePageId: "about" };
    const result = merge(base, local, base);
    expect(result.conflicts).toEqual([]);
    expect(result.mergedSchema).not.toHaveProperty("activePageId");
  });
});
