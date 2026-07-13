import { act, cleanup, render } from "@testing-library/react";
import { useEffect } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import useDebouncedProjectStorage, {
  isNewerExternalDraftMessage,
} from "./useDebouncedProjectStorage";

const STORAGE_KEY = "madar-builder-stability-test";

function StorageProbe({ onReady, project }) {
  const storage = useDebouncedProjectStorage({
    backupInterval: 120000,
    delay: 7000,
    project,
    storageKey: STORAGE_KEY,
  });

  useEffect(() => onReady(storage), [onReady, storage]);
  return null;
}

describe("safe builder draft autosave", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    localStorage.clear();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("coalesces rapid live revisions into one inactivity save", () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    const onReady = vi.fn();
    const { rerender } = render(<StorageProbe onReady={onReady} project={{ id: "one" }} />);

    rerender(<StorageProbe onReady={onReady} project={{ id: "two" }} />);
    rerender(<StorageProbe onReady={onReady} project={{ id: "final", title: "Latest" }} />);
    const storage = onReady.mock.calls.at(-1)[0];
    expect(storage.getRevisionState().currentRevision)
      .toBeGreaterThan(storage.getRevisionState().lastSuccessfullySavedRevision);
    act(() => vi.advanceTimersByTime(6999));
    expect(setItem).not.toHaveBeenCalled();

    act(() => vi.advanceTimersByTime(1));
    expect(setItem).toHaveBeenCalledTimes(1);
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY))).toEqual({ id: "final", title: "Latest" });
    expect(storage.getRevisionState().lastSuccessfullySavedRevision)
      .toBe(storage.getRevisionState().currentRevision);
  });

  it("keeps the draft dirty after a failed write", () => {
    let storage;
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("storage denied");
    });
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    render(<StorageProbe onReady={(value) => { storage = value; }} project={{ id: "unsaved" }} />);

    let saved;
    act(() => { saved = storage.persistNow(); });

    expect(saved).toBe(false);
    expect(storage.hasUnsavedChanges()).toBe(true);
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it("rejects self, stale, duplicate, and wrong-project cross-tab revisions", () => {
    const candidate = {
      sourceId: "other-tab",
      revision: 8,
      projectId: "project-a",
      timestamp: 200,
      serializedProject: '{"id":"project-a"}',
    };
    const context = {
      currentProjectId: "project-a",
      lastPersistedAt: 100,
      previousRevision: 7,
      sourceId: "this-tab",
    };

    expect(isNewerExternalDraftMessage(candidate, context)).toBe(true);
    expect(isNewerExternalDraftMessage({ ...candidate, sourceId: "this-tab" }, context)).toBe(false);
    expect(isNewerExternalDraftMessage({ ...candidate, revision: 7 }, context)).toBe(false);
    expect(isNewerExternalDraftMessage({ ...candidate, timestamp: 100 }, context)).toBe(false);
    expect(isNewerExternalDraftMessage({ ...candidate, projectId: "project-b" }, context)).toBe(false);
  });
});
