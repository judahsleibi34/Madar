import { describe, expect, it, vi } from "vitest";

import {
  createBuilderSaveCoordinator,
  createBuilderSaveEntry,
} from "./PageBuilder.saveCoordinator";

const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
};

const harness = ({ revision = 89, snapshot = "base" } = {}) => {
  let generation = 1;
  let projectId = "project-1";
  let currentRevision = revision;
  let acknowledged = snapshot;
  let latest = createBuilderSaveEntry({ project: { value: snapshot }, snapshot });
  const dispatches = [];
  const dispatch = vi.fn(async (entry, context) => {
    dispatches.push({ entry, context });
    currentRevision += 1;
    acknowledged = entry.snapshot;
    return { status: "saved", revision: currentRevision, snapshot: acknowledged };
  });
  const coordinator = createBuilderSaveCoordinator({
    getProjectId: () => projectId,
    getGeneration: () => generation,
    getRevision: () => currentRevision,
    getAcknowledgedSnapshot: () => acknowledged,
    getLatestEntry: () => latest,
    dispatch,
  });
  return {
    coordinator,
    dispatch,
    dispatches,
    edit(next) {
      latest = createBuilderSaveEntry({ project: { value: next }, snapshot: next });
      return latest;
    },
    acknowledge(nextSnapshot, nextRevision) {
      acknowledged = nextSnapshot;
      currentRevision = nextRevision;
    },
    invalidateGeneration() { generation += 1; },
    switchProject(next) { projectId = next; generation += 1; },
    revision: () => currentRevision,
    snapshot: () => acknowledged,
  };
};

describe("builder save coordinator", () => {
  it("stores schema/hash metadata without capturing a revision", () => {
    const entry = createBuilderSaveEntry({ project: { value: 1 }, snapshot: "hash", reason: "blur" });
    expect(entry).toMatchObject({ project: { value: 1 }, snapshot: "hash", reason: "blur" });
    expect(entry).not.toHaveProperty("expected_revision");
    expect(entry).not.toHaveProperty("draft_revision");
  });

  it("dispatches one edit once and reads revision at dispatch time", async () => {
    const h = harness();
    await h.coordinator.requestSave(h.edit("edit-a"));
    expect(h.dispatch).toHaveBeenCalledTimes(1);
    expect(h.dispatches[0].context.expectedRevision).toBe(89);
    expect(h.revision()).toBe(90);
  });

  it("forces an explicit manual save through to the server even when already acknowledged", async () => {
    const h = harness({ revision: 89, snapshot: "base" });
    const manualEntry = createBuilderSaveEntry({
      project: { value: "base" },
      snapshot: "base",
      reason: "manual",
      silent: false,
      force: true,
    });

    await h.coordinator.requestSave(manualEntry);

    expect(h.dispatch).toHaveBeenCalledTimes(1);
    expect(h.dispatches[0].entry).toMatchObject({ force: true, reason: "manual" });
    expect(h.dispatches[0].context.expectedRevision).toBe(89);
    expect(h.revision()).toBe(90);
  });

  it("continues to deduplicate unchanged autosaves", async () => {
    const h = harness({ revision: 89, snapshot: "base" });

    await h.coordinator.requestSave(createBuilderSaveEntry({
      project: { value: "base" },
      snapshot: "base",
    }));

    expect(h.dispatch).not.toHaveBeenCalled();
    expect(h.revision()).toBe(89);
  });

  it("coalesces callers and serializes only the newest edit", async () => {
    const h = harness();
    const first = deferred();
    h.dispatch
      .mockImplementationOnce(async (entry, context) => {
        h.dispatches.push({ entry, context });
        await first.promise;
        h.acknowledge(entry.snapshot, 90);
        return { status: "saved" };
      })
      .mockImplementationOnce(async (entry, context) => {
        h.dispatches.push({ entry, context });
        h.acknowledge(entry.snapshot, 91);
        return { status: "saved" };
      });
    const pending = h.coordinator.requestSave(h.edit("edit-a"));
    const joined = h.coordinator.requestSave(h.edit("edit-b"));
    h.coordinator.requestSave(h.edit("edit-c"));
    expect(joined).toBe(pending);
    expect(h.dispatch).toHaveBeenCalledTimes(1);
    first.resolve();
    await pending;
    expect(h.dispatch).toHaveBeenCalledTimes(2);
    expect(h.dispatches.map((item) => item.entry.snapshot)).toEqual(["edit-a", "edit-c"]);
    expect(h.dispatches.map((item) => item.context.expectedRevision)).toEqual([89, 90]);
  });

  it("drops a queued snapshot that the acknowledgement already covers", async () => {
    const h = harness();
    const first = deferred();
    h.dispatch.mockImplementationOnce(async (entry) => {
      await first.promise;
      h.acknowledge(entry.snapshot, 90);
      return { status: "saved" };
    });
    const entry = h.edit("same-edit");
    const pending = h.coordinator.requestSave(entry);
    h.coordinator.requestSave(entry);
    first.resolve();
    await pending;
    expect(h.dispatch).toHaveBeenCalledTimes(1);
  });

  it("makes flushLatest join the active full chain", async () => {
    const h = harness();
    const first = deferred();
    h.dispatch.mockImplementationOnce(async (entry) => {
      await first.promise;
      h.acknowledge(entry.snapshot, 90);
      return { status: "saved" };
    });
    const pending = h.coordinator.requestSave(h.edit("publish-edit"));
    const flushed = h.coordinator.flushLatest();
    expect(flushed).toBe(pending);
    first.resolve();
    await expect(flushed).resolves.toMatchObject({ status: "saved", revision: 90 });
  });

  it("ignores a late result after generation invalidation", async () => {
    const h = harness();
    const old = deferred();
    h.dispatch.mockImplementationOnce(() => old.promise);
    const pending = h.coordinator.requestSave(h.edit("old-edit"));
    h.invalidateGeneration();
    h.coordinator.invalidate();
    old.resolve({ status: "failed" });
    await expect(pending).resolves.toEqual({ status: "obsolete" });
  });

  it("ignores a late 409 after a project switch", async () => {
    const h = harness();
    const old = deferred();
    h.dispatch.mockImplementationOnce(() => old.promise);
    const pending = h.coordinator.requestSave(h.edit("old-project-edit"));
    h.switchProject("project-2");
    h.coordinator.invalidate();
    old.resolve({ status: "conflict" });
    await expect(pending).resolves.toEqual({ status: "obsolete" });
  });

  it("reproduces revision 89 without dispatching stale queued work", async () => {
    const h = harness({ revision: 89 });
    const entry = h.edit("revision-90-schema");
    const first = h.coordinator.requestSave(entry);
    h.coordinator.requestSave(entry); // stale timer callback for the same schema
    const result = await first;
    expect(h.dispatch).toHaveBeenCalledTimes(1);
    expect(h.dispatches[0].context.expectedRevision).toBe(89);
    expect(result).toMatchObject({ status: "saved", revision: 90 });
    expect(h.coordinator.getStatus()).toMatchObject({
      active: false,
      activeSnapshot: "",
      queuedSnapshot: "",
      latestSuccessfulOperationId: 1,
    });
  });
});
