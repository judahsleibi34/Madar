import { describe, expect, it, vi } from "vitest";

import {
  getBuilderPublicationLabel,
  getBuilderPublicationState,
  getBuilderPublishReadiness,
  prepareBuilderProjectForPublish,
  runBuilderPublishSingleFlight,
} from "./PageBuilder.publishState";

describe("builder draft and published state", () => {
  it("reports a matching backend draft as published", () => {
    const schema = { pages: [{ id: "home" }] };
    const state = getBuilderPublicationState({ draft_schema: schema, published_schema: schema });
    expect(state.status).toBe("published");
    expect(getBuilderPublicationLabel(state)).toBe("Published");
  });

  it("treats recursively reordered published jsonb as the same schema", () => {
    const state = getBuilderPublicationState({
      draft_schema: {
        pages: [{ id: "home", sections: [{ id: "hero", layout: { width: "full", gap: "large" } }] }],
        theme: { colors: { primary: "#111", surface: "#fff" } },
      },
      published_schema: {
        theme: { colors: { surface: "#fff", primary: "#111" } },
        pages: [{ sections: [{ layout: { gap: "large", width: "full" }, id: "hero" }], id: "home" }],
      },
    });
    expect(state.status).toBe("published");
    expect(state.differs).toBe(false);
  });

  it("warns when the durable published site has more pages than the saved draft", () => {
    const state = getBuilderPublicationState({
      draft_schema: { pages: [{ id: "home" }] },
      published_schema: { pages: [{ id: "home" }, { id: "two" }, { id: "three" }] },
    });
    expect(state).toMatchObject({
      status: "unpublished_changes",
      draftPageCount: 1,
      publishedPageCount: 3,
      publishedHasMorePages: true,
    });
    expect(getBuilderPublicationLabel(state)).toContain("differs");
  });

  it("does not let legacy editor selections create a false publication difference", () => {
    const state = getBuilderPublicationState({
      draft_schema: { pages: [{ id: "home" }], activePageId: "home" },
      published_schema: { pages: [{ id: "home" }] },
    });
    expect(state.status).toBe("published");
  });
});

describe("builder publish preparation", () => {
  const state = (overrides = {}) => ({
    hydrated: true,
    routedProjectId: "project-1",
    loadedProjectId: "project-1",
    draftRevision: 80,
    currentSnapshot: "schema-80",
    acknowledgedSnapshot: "schema-80",
    acknowledgedSchema: { pages: [{ id: "home" }] },
    conflict: false,
    operationInFlight: false,
    ...overrides,
  });

  it("reports readiness only for the exact acknowledged backend draft", () => {
    expect(getBuilderPublishReadiness(state())).toMatchObject({
      ready: true,
      projectId: "project-1",
      draftRevision: 80,
      acknowledgedHash: "schema-80",
    });
    expect(getBuilderPublishReadiness(state({ currentSnapshot: "local" }))).toMatchObject({
      ready: false,
      reason: "unsaved_changes",
    });
    expect(getBuilderPublishReadiness(state({ loadedProjectId: "project-2" }))).toMatchObject({
      ready: false,
      reason: "loading",
    });
  });

  it("publishes a clean project without issuing a save", async () => {
    const flushSave = vi.fn();
    const result = await prepareBuilderProjectForPublish({
      getState: () => state(),
      flushSave,
    });
    expect(result).toMatchObject({ ready: true, draftRevision: 80 });
    expect(flushSave).not.toHaveBeenCalled();
  });

  it("clean Go Live performs zero draft PUTs and one publish despite stale failure text", async () => {
    const flushSave = vi.fn();
    const publish = vi.fn().mockResolvedValue({ published_revision: 80 });
    const prepared = await prepareBuilderProjectForPublish({
      getState: () => state({ saveState: "save_failed" }),
      flushSave,
    });
    expect(prepared.ready).toBe(true);
    await publish(prepared.projectId, prepared.draftRevision);
    expect(flushSave).not.toHaveBeenCalled();
    expect(publish).toHaveBeenCalledTimes(1);
    expect(publish).toHaveBeenCalledWith("project-1", 80);
  });

  it("flushes a dirty project and returns the acknowledged new revision", async () => {
    let current = state({ currentSnapshot: "local-81" });
    const flushSave = vi.fn(async () => {
      current = state({
        draftRevision: 81,
        currentSnapshot: "local-81",
        acknowledgedSnapshot: "local-81",
        acknowledgedSchema: { pages: [{ id: "home", title: "Local" }] },
      });
      return true;
    });
    const result = await prepareBuilderProjectForPublish({
      getState: () => current,
      flushSave,
    });
    expect(flushSave).toHaveBeenCalledTimes(1);
    expect(result).toMatchObject({ ready: true, draftRevision: 81, acknowledgedHash: "local-81" });
  });

  it("awaits an in-flight save and uses its acknowledgement", async () => {
    let resolveSave;
    let current = state({
      currentSnapshot: "local-81",
      operationInFlight: true,
    });
    const active = new Promise((resolve) => { resolveSave = resolve; });
    const preparation = prepareBuilderProjectForPublish({
      getState: () => current,
      getActiveOperation: () => current.operationInFlight ? active : null,
      flushSave: vi.fn(),
    });
    current = state({
      draftRevision: 81,
      currentSnapshot: "local-81",
      acknowledgedSnapshot: "local-81",
      operationInFlight: false,
    });
    resolveSave(true);
    await expect(preparation).resolves.toMatchObject({ ready: true, draftRevision: 81 });
  });

  it("uses the merged acknowledgement immediately after automatic rebase", async () => {
    let current = state({ currentSnapshot: "merged-82" });
    const flushSave = vi.fn(async () => {
      current = state({
        draftRevision: 82,
        currentSnapshot: "merged-82",
        acknowledgedSnapshot: "merged-82",
        acknowledgedSchema: { pages: [{ id: "home", title: "Merged" }] },
      });
      return true;
    });
    await expect(prepareBuilderProjectForPublish({
      getState: () => current,
      flushSave,
    })).resolves.toMatchObject({
      ready: true,
      draftRevision: 82,
      acknowledgedHash: "merged-82",
    });
  });

  it("waits for the queued latest snapshot before becoming ready", async () => {
    let current = state({ currentSnapshot: "schema-b", acknowledgedSnapshot: "schema-a" });
    let flushCount = 0;
    const flushSave = vi.fn(async () => {
      flushCount += 1;
      if (flushCount === 1) {
        current = state({
          draftRevision: 81,
          currentSnapshot: "schema-b",
          acknowledgedSnapshot: "schema-a-saved",
        });
      } else {
        current = state({
          draftRevision: 82,
          currentSnapshot: "schema-b",
          acknowledgedSnapshot: "schema-b",
        });
      }
      return true;
    });
    const result = await prepareBuilderProjectForPublish({ getState: () => current, flushSave });
    expect(flushSave).toHaveBeenCalledTimes(2);
    expect(result).toMatchObject({ ready: true, draftRevision: 82 });
  });

  it("blocks an overlapping conflict and never performs another flush", async () => {
    const flushSave = vi.fn();
    const result = await prepareBuilderProjectForPublish({
      getState: () => state({ conflict: true, currentSnapshot: "local" }),
      flushSave,
    });
    expect(result).toEqual({ ready: false, reason: "conflict" });
    expect(flushSave).not.toHaveBeenCalled();
  });

  it("does not include browser recovery in publish readiness", async () => {
    const current = state({ recovery: { schema: { pages: [{ id: "stale" }] } } });
    const result = await prepareBuilderProjectForPublish({
      getState: () => current,
      flushSave: vi.fn(),
    });
    expect(result).toMatchObject({ ready: true, draftRevision: 80 });
    expect(result.acknowledgedSchema).toEqual(current.acknowledgedSchema);
  });

  it("coalesces double-clicks into one logical publish request", async () => {
    const promiseRef = { current: null };
    let resolvePublish;
    const operation = vi.fn(() => new Promise((resolve) => { resolvePublish = resolve; }));
    const first = runBuilderPublishSingleFlight(promiseRef, operation);
    const second = runBuilderPublishSingleFlight(promiseRef, operation);
    expect(second).toBe(first);
    await Promise.resolve();
    expect(operation).toHaveBeenCalledTimes(1);
    resolvePublish(true);
    await expect(first).resolves.toBe(true);
    expect(promiseRef.current).toBeNull();
  });
});
