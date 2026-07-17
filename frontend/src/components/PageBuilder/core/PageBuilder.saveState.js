export const BUILDER_SAVE_STATES = Object.freeze({
  loading: "loading",
  clean: "clean",
  dirty: "dirty",
  savingLocal: "saving_local",
  savingCloud: "saving_cloud",
  savedCloud: "saved_cloud",
  saveFailed: "save_failed",
  conflict: "conflict",
});

export const BUILDER_SAVE_STATE_LABELS = Object.freeze({
  loading: "Loading project…",
  clean: "Saved",
  dirty: "Unsaved changes",
  saving_local: "Saving…",
  saving_cloud: "Saving…",
  saved_cloud: "Saved",
  save_failed: "Save failed — Retry",
  conflict: "Conflict detected",
});

export const getBuilderSaveStateLabel = (state) =>
  BUILDER_SAVE_STATE_LABELS[state] || BUILDER_SAVE_STATE_LABELS.dirty;

export const shouldDeferBuilderCloudSave = ({ dragActive = false, textEditing = false } = {}) =>
  Boolean(dragActive || textEditing);

export const getBuilderSaveRetryDelay = (attempt) =>
  Math.min(30000, 2000 * (2 ** Math.max(0, Number(attempt) || 0)));

export const getAcknowledgedBuilderSaveState = ({
  acknowledgedSnapshot,
  currentSnapshot,
} = {}) =>
  acknowledgedSnapshot && acknowledgedSnapshot === currentSnapshot
    ? BUILDER_SAVE_STATES.savedCloud
    : BUILDER_SAVE_STATES.dirty;

export const deriveBuilderCloudSaveState = ({
  hydrated = false,
  conflict = false,
  saveActive = false,
  rebaseActive = false,
  currentSnapshot = "",
  acknowledgedSnapshot = "",
  latestFailureRelevant = false,
} = {}) => {
  if (!hydrated) return BUILDER_SAVE_STATES.loading;
  if (conflict) return BUILDER_SAVE_STATES.conflict;
  if (rebaseActive || saveActive) return BUILDER_SAVE_STATES.savingCloud;
  if (acknowledgedSnapshot && currentSnapshot === acknowledgedSnapshot) {
    return BUILDER_SAVE_STATES.savedCloud;
  }
  if (latestFailureRelevant) return BUILDER_SAVE_STATES.saveFailed;
  return BUILDER_SAVE_STATES.dirty;
};

export const isTerminalBuilderSaveState = (state) =>
  state === BUILDER_SAVE_STATES.conflict;

export const canStartBuilderCloudMutation = ({ hydrated = false, conflict = false } = {}) =>
  Boolean(hydrated && !conflict);

export const stopBuilderSaveScheduling = ({
  autosaveTimerRef,
  safetyIntervalRef,
  pendingRequestRef,
  pendingSnapshotRef,
  clearTimeoutFn = clearTimeout,
  clearIntervalFn = clearInterval,
} = {}) => {
  if (autosaveTimerRef?.current) clearTimeoutFn(autosaveTimerRef.current);
  if (safetyIntervalRef?.current) clearIntervalFn(safetyIntervalRef.current);
  if (autosaveTimerRef) autosaveTimerRef.current = null;
  if (safetyIntervalRef) safetyIntervalRef.current = null;
  if (pendingRequestRef) pendingRequestRef.current = null;
  if (pendingSnapshotRef) pendingSnapshotRef.current = "";
};

export const getBuilderPublishBlockReason = ({
  hydrated = false,
  saveState,
  saveInFlight = false,
  currentSnapshot = "",
  acknowledgedSnapshot = "",
  routedProjectId = "",
  loadedProjectId = "",
} = {}) => {
  if (!hydrated || !routedProjectId || routedProjectId !== loadedProjectId) return "loading";
  if (saveState === BUILDER_SAVE_STATES.conflict) return "conflict";
  if (saveState === BUILDER_SAVE_STATES.saveFailed) return "save_failed";
  if (
    saveInFlight ||
    saveState === BUILDER_SAVE_STATES.savingLocal ||
    saveState === BUILDER_SAVE_STATES.savingCloud
  ) return "saving";
  if (saveState === BUILDER_SAVE_STATES.dirty) return "unsaved_changes";
  if (!acknowledgedSnapshot || currentSnapshot !== acknowledgedSnapshot) return "unsaved_changes";
  return "";
};
