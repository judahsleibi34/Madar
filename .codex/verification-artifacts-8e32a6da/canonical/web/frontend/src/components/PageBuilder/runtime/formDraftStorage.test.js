import { describe, expect, it } from "vitest";

import {
  readRuntimeFormDrafts,
  removeRuntimeFormDraft,
  saveRuntimeFormDraft,
} from "./formDraftStorage";

const memoryStorage = () => {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };
};

describe("runtime form draft storage", () => {
  it("persists partial answers and the page needed to resume", () => {
    const storage = memoryStorage();
    const now = Date.UTC(2026, 7, 25, 12);

    expect(saveRuntimeFormDraft(storage, "Tenant-Site", "block_form-1", {
      formId: "form-1",
      answers: { required_name: "", notes: "Finish this later" },
      pageIndex: 2,
      language: "en",
    }, now)).toBe(true);

    expect(readRuntimeFormDrafts(storage, "tenant-site", now)).toEqual({
      "block_form-1": {
        formId: "form-1",
        answers: { required_name: "", notes: "Finish this later" },
        pageIndex: 2,
        language: "en",
        savedAt: "2026-08-25T12:00:00.000Z",
      },
    });
  });

  it("removes a draft after final submission", () => {
    const storage = memoryStorage();
    saveRuntimeFormDraft(storage, "tenant-site", "block_form-1", {
      formId: "form-1",
      answers: { name: "Sam" },
    });

    removeRuntimeFormDraft(storage, "tenant-site", "block_form-1");

    expect(readRuntimeFormDrafts(storage, "tenant-site")).toEqual({});
  });

  it("keeps drafts until the form is completed or browser storage is cleared", () => {
    const storage = memoryStorage();
    const savedAt = Date.UTC(2026, 5, 1);
    saveRuntimeFormDraft(storage, "tenant-site", "block_form-1", {
      formId: "form-1",
      answers: { name: "Old" },
    }, savedAt);

    expect(readRuntimeFormDrafts(storage, "tenant-site")["block_form-1"].answers).toEqual({
      name: "Old",
    });
  });
});
