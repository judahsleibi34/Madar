import { describe, expect, it } from "vitest";

import {
  BUILDER_SAVE_STATES,
  canStartBuilderCloudMutation,
  getAcknowledgedBuilderSaveState,
  deriveBuilderCloudSaveState,
  getBuilderPublishBlockReason,
  getBuilderSaveRetryDelay,
  getBuilderSaveStateLabel,
  isNewerBuilderCloudSaveMessage,
  stopBuilderSaveScheduling,
  shouldDeferBuilderCloudSave,
  shouldBlockBuilderUnload,
} from "./PageBuilder.saveState";

describe("cloud save state labels", () => {
  it.each([
    [BUILDER_SAVE_STATES.dirty, true],
    [BUILDER_SAVE_STATES.savingLocal, true],
    [BUILDER_SAVE_STATES.savingCloud, true],
    [BUILDER_SAVE_STATES.saveFailed, true],
    [BUILDER_SAVE_STATES.conflict, true],
    [BUILDER_SAVE_STATES.savedCloud, false],
    [BUILDER_SAVE_STATES.clean, false],
    [BUILDER_SAVE_STATES.loading, false],
  ])("uses the visible %s save block for unload protection", (state, expected) => {
    expect(shouldBlockBuilderUnload(state)).toBe(expected);
  });
  it.each([
    [BUILDER_SAVE_STATES.dirty, "Unsaved changes"],
    [BUILDER_SAVE_STATES.savingLocal, "Saving…"],
    [BUILDER_SAVE_STATES.savingCloud, "Saving…"],
    [BUILDER_SAVE_STATES.savedCloud, "Saved"],
    [BUILDER_SAVE_STATES.saveFailed, "Save failed — Retry"],
    [BUILDER_SAVE_STATES.conflict, "Conflict detected"],
  ])("renders %s accurately", (state, label) => {
    expect(getBuilderSaveStateLabel(state)).toBe(label);
  });

  it("defers cloud saves during focused editing, dragging, or resizing", () => {
    expect(shouldDeferBuilderCloudSave({ textEditing: true })).toBe(true);
    expect(shouldDeferBuilderCloudSave({ activeTab: "chrome", textEditing: true })).toBe(false);
    expect(shouldDeferBuilderCloudSave({ dragActive: true })).toBe(true);
    expect(shouldDeferBuilderCloudSave({ activeTab: "chrome", dragActive: true })).toBe(true);
    expect(shouldDeferBuilderCloudSave()).toBe(false);
  });

  it("accepts only newer cloud revisions from another tab for the same project", () => {
    const context = { currentRevision: 8, projectId: "project-1", sourceId: "tab-a", tenantId: "4" };
    expect(isNewerBuilderCloudSaveMessage({
      type: "cloud_saved", sourceId: "tab-b", projectId: "project-1", tenantId: "4", revision: 9,
    }, context)).toBe(true);
    expect(isNewerBuilderCloudSaveMessage({
      type: "cloud_saved", sourceId: "tab-a", projectId: "project-1", tenantId: "4", revision: 9,
    }, context)).toBe(false);
    expect(isNewerBuilderCloudSaveMessage({
      type: "cloud_saved", sourceId: "tab-b", projectId: "project-2", tenantId: "4", revision: 9,
    }, context)).toBe(false);
    expect(isNewerBuilderCloudSaveMessage({
      type: "cloud_saved", sourceId: "tab-b", projectId: "project-1", tenantId: "4", revision: 8,
    }, context)).toBe(false);
  });

  it("uses bounded retry backoff", () => {
    expect([0, 1, 2, 3, 8].map(getBuilderSaveRetryDelay))
      .toEqual([2000, 4000, 8000, 16000, 30000]);
  });

  it("reports cloud saved only when the backend acknowledged the latest snapshot", () => {
    expect(getAcknowledgedBuilderSaveState({
      acknowledgedSnapshot: "snapshot-b",
      currentSnapshot: "snapshot-b",
    })).toBe(BUILDER_SAVE_STATES.savedCloud);
    expect(getAcknowledgedBuilderSaveState({
      acknowledgedSnapshot: "snapshot-a",
      currentSnapshot: "snapshot-b",
    })).toBe(BUILDER_SAVE_STATES.dirty);
  });

  it("derives Saved from authoritative equality even after a stale failure", () => {
    expect(deriveBuilderCloudSaveState({
      hydrated: true,
      currentSnapshot: "schema-b",
      acknowledgedSnapshot: "schema-b",
      latestFailureRelevant: true,
    })).toBe(BUILDER_SAVE_STATES.savedCloud);
  });

  it("shows failure only while the latest visible schema remains unacknowledged", () => {
    expect(deriveBuilderCloudSaveState({
      hydrated: true,
      currentSnapshot: "schema-b",
      acknowledgedSnapshot: "schema-a",
      latestFailureRelevant: true,
    })).toBe(BUILDER_SAVE_STATES.saveFailed);
    expect(deriveBuilderCloudSaveState({
      hydrated: true,
      currentSnapshot: "schema-b",
      acknowledgedSnapshot: "schema-a",
    })).toBe(BUILDER_SAVE_STATES.dirty);
  });

  it.each([
    [{ hydrated: false }, "loading"],
    [{ hydrated: true, routedProjectId: "p", loadedProjectId: "p", saveState: BUILDER_SAVE_STATES.conflict }, "conflict"],
    [{ hydrated: true, routedProjectId: "p", loadedProjectId: "p", saveState: BUILDER_SAVE_STATES.saveFailed }, "save_failed"],
    [{ hydrated: true, routedProjectId: "p", loadedProjectId: "p", saveState: BUILDER_SAVE_STATES.savingCloud }, "saving"],
    [{ hydrated: true, routedProjectId: "p", loadedProjectId: "p", saveState: BUILDER_SAVE_STATES.dirty }, "unsaved_changes"],
    [{ hydrated: true, routedProjectId: "p", loadedProjectId: "p", saveState: BUILDER_SAVE_STATES.savedCloud, currentSnapshot: "b", acknowledgedSnapshot: "a" }, "unsaved_changes"],
    [{ hydrated: true, routedProjectId: "p", loadedProjectId: "p", saveState: BUILDER_SAVE_STATES.savedCloud, currentSnapshot: "a", acknowledgedSnapshot: "a" }, ""],
  ])("blocks publishing until the exact backend-confirmed draft is safe", (input, expected) => {
    expect(getBuilderPublishBlockReason(input)).toBe(expected);
  });

  it("cancels all timers and queued work after the first terminal conflict", () => {
    const refs = {
      autosaveTimerRef: { current: 11 },
      safetyIntervalRef: { current: 12 },
      pendingRequestRef: { current: { snapshot: "stale" } },
      pendingSnapshotRef: { current: "stale" },
    };
    const clearedTimeouts = [];
    const clearedIntervals = [];
    stopBuilderSaveScheduling({
      ...refs,
      clearTimeoutFn: (value) => clearedTimeouts.push(value),
      clearIntervalFn: (value) => clearedIntervals.push(value),
    });
    expect(clearedTimeouts).toEqual([11]);
    expect(clearedIntervals).toEqual([12]);
    expect(refs).toMatchObject({
      autosaveTimerRef: { current: null },
      safetyIntervalRef: { current: null },
      pendingRequestRef: { current: null },
      pendingSnapshotRef: { current: "" },
    });
  });

  it("allows no cloud mutation during hydration or after terminal conflict", () => {
    expect(canStartBuilderCloudMutation({ hydrated: false, conflict: false })).toBe(false);
    expect(canStartBuilderCloudMutation({ hydrated: true, conflict: true })).toBe(false);
    expect(canStartBuilderCloudMutation({ hydrated: true, conflict: false })).toBe(true);
  });
});
