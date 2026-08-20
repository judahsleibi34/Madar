import { act, cleanup, render } from "@testing-library/react";
import { useEffect } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import useDebouncedProjectStorage, {
  isNewerExternalDraftMessage,
} from "./useDebouncedProjectStorage";

const STORAGE_KEY = "madar-builder-stability-test";

function StorageProbe({ enableBrowserPersistence = true, onReady, project, recoveryContext = null }) {
  const storage = useDebouncedProjectStorage({
    backupInterval: 120000,
    delay: 7000,
    enableBrowserPersistence,
    project,
    recoveryContext,
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

  it("does not persist or mark dirty when only editor selection changes", () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    const onReady = vi.fn();
    const shared = {
      id: "project-1",
      defaultPageId: "home",
      pages: [{ id: "home" }, { id: "page-2" }],
      forms: [{ id: "form-1", fields: [] }],
      activePageId: "home",
      activeFormId: "form-1",
    };
    const { rerender } = render(<StorageProbe onReady={onReady} project={shared} />);
    const storage = onReady.mock.calls.at(-1)[0];
    act(() => { storage.persistNow(); });
    setItem.mockClear();

    rerender(<StorageProbe
      onReady={onReady}
      project={{ ...shared, activePageId: "page-2", activeFormId: "" }}
    />);
    act(() => vi.advanceTimersByTime(7000));

    expect(setItem).not.toHaveBeenCalled();
    expect(onReady.mock.calls.at(-1)[0].hasUnsavedChanges()).toBe(false);
  });

  it("marks real shared changes dirty while preserving default and responsive content", () => {
    let storage;
    const initial = {
      id: "project-1",
      defaultPageId: "home",
      pages: [{ id: "home", position: { desktop: { x: 0 } } }],
    };
    const { rerender } = render(
      <StorageProbe onReady={(value) => { storage = value; }} project={initial} />
    );
    act(() => { storage.persistNow(); });

    rerender(<StorageProbe
      onReady={(value) => { storage = value; }}
      project={{
        ...initial,
        defaultPageId: "page-2",
        pages: [
          { id: "page-2", position: { desktop: { x: 24 } } },
          initial.pages[0],
        ],
      }}
    />);

    expect(storage.hasUnsavedChanges()).toBe(true);
    act(() => vi.advanceTimersByTime(7000));
    const persisted = JSON.parse(localStorage.getItem(STORAGE_KEY));
    expect(persisted.defaultPageId).toBe("page-2");
    expect(persisted.pages.map((page) => page.id)).toEqual(["page-2", "home"]);
    expect(persisted.pages[0].position.desktop.x).toBe(24);
  });

  it("treats cross-tab messages as identity-scoped timestamp advisories", () => {
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
      sourceId: "this-tab",
    };

    expect(isNewerExternalDraftMessage(candidate, context)).toBe(true);
    expect(isNewerExternalDraftMessage({ ...candidate, sourceId: "this-tab" }, context)).toBe(false);
    expect(isNewerExternalDraftMessage({ ...candidate, revision: 7 }, context)).toBe(true);
    expect(isNewerExternalDraftMessage({ ...candidate, timestamp: 100 }, context)).toBe(false);
    expect(isNewerExternalDraftMessage({ ...candidate, projectId: "project-b" }, context)).toBe(false);
    expect(isNewerExternalDraftMessage(
      { ...candidate, tenantId: "tenant-b" },
      { ...context, currentTenantId: "tenant-a" }
    )).toBe(false);
    expect(isNewerExternalDraftMessage(
      { ...candidate, baseDraftRevision: 59 },
      { ...context, currentBackendRevision: 60 }
    )).toBe(false);
  });

  it("keeps cloud drafts dirty without writing browser recovery", () => {
    let storage;
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    render(
      <StorageProbe
        enableBrowserPersistence={false}
        onReady={(value) => { storage = value; }}
        project={{ id: "server-project", title: "Unsaved edit" }}
        recoveryContext={{
          userId: "user-1",
          tenantId: "tenant-1",
          projectId: "server-project",
          baseDraftRevision: 4,
        }}
      />
    );

    act(() => vi.advanceTimersByTime(120000));

    expect(setItem).not.toHaveBeenCalled();
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
    expect(storage.hasUnsavedChanges()).toBe(true);
  });

  it("writes scoped recovery envelopes and clears them only after cloud acknowledgement", () => {
    let storage;
    const recoveryContext = {
      userId: "user-1",
      tenantId: "tenant-6",
      projectId: "project-1",
      baseDraftRevision: 5,
    };
    const project = {
      id: "project-1",
      activePageId: "page-2",
      pages: [{ id: "home" }, { id: "page-2" }],
    };
    render(
      <StorageProbe
        onReady={(value) => { storage = value; }}
        project={project}
        recoveryContext={recoveryContext}
      />
    );

    act(() => { storage.persistNow(); });
    const raw = localStorage.getItem(STORAGE_KEY);
    const envelope = JSON.parse(raw);
    expect(envelope).toMatchObject({
      user_id: "user-1",
      tenant_id: "tenant-6",
      project_id: "project-1",
      base_draft_revision: 5,
    });
    expect(envelope.schema.pages).toHaveLength(2);
    expect(envelope.schema).not.toHaveProperty("activePageId");
    expect(localStorage.getItem(`${STORAGE_KEY}:backup`)).toBeNull();

    act(() => { storage.acknowledgeCloudSave(project, 6); });
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
    expect(storage.hasUnsavedChanges()).toBe(false);
  });
});
