const savedResult = (details = {}) => ({ status: "saved", ...details });

export const createBuilderSaveEntry = ({
  project,
  snapshot,
  reason = "autosave",
  repairs = [],
  silent = true,
  successMessage = "",
} = {}) => ({
  project,
  snapshot: String(snapshot || ""),
  reason,
  repairs,
  silent,
  successMessage,
  requestedAt: Date.now(),
});

/**
 * Owns the one logical draft-write chain for a mounted project. Queue entries
 * intentionally contain no revision: the revision is read immediately before
 * dispatching each request.
 */
export const createBuilderSaveCoordinator = ({
  getProjectId,
  getGeneration,
  getRevision,
  getAcknowledgedSnapshot,
  getLatestEntry,
  dispatch,
} = {}) => {
  let activePromise = null;
  let activeEntry = null;
  let queuedEntry = null;
  let invalidated = false;
  let operationCounter = 0;
  let latestSuccessfulOperationId = 0;

  const isCurrent = (generation, projectId) =>
    !invalidated &&
    generation === getGeneration?.() &&
    projectId &&
    projectId === getProjectId?.();

  const reconcileQueue = () => {
    const latest = getLatestEntry?.() || queuedEntry;
    queuedEntry = null;
    if (!latest?.snapshot || latest.snapshot === getAcknowledgedSnapshot?.()) return null;
    return latest;
  };

  const drain = async (firstEntry) => {
    const generation = getGeneration?.();
    const projectId = getProjectId?.();
    let entry = firstEntry;
    let finalResult = savedResult();

    while (entry) {
      if (!isCurrent(generation, projectId)) return { status: "obsolete" };
      if (entry.snapshot === getAcknowledgedSnapshot?.()) {
        entry = reconcileQueue();
        continue;
      }

      activeEntry = entry;
      const operationId = ++operationCounter;
      const expectedRevision = Number(getRevision?.());
      const result = await dispatch(entry, {
        expectedRevision,
        generation,
        operationId,
        projectId,
      });
      if (!isCurrent(generation, projectId)) return { status: "obsolete" };
      finalResult = result || { status: "failed" };
      if (operationId < latestSuccessfulOperationId) return { status: "obsolete" };
      if (finalResult.status !== "saved") return finalResult;
      latestSuccessfulOperationId = operationId;

      // The dispatch acknowledgement updates revision and acknowledged hash
      // synchronously. Only the newest editor difference survives.
      entry = reconcileQueue();
    }
    return {
      ...finalResult,
      status: "saved",
      revision: Number(getRevision?.()),
      snapshot: getAcknowledgedSnapshot?.() || "",
    };
  };

  const requestSave = (entry) => {
    if (!entry?.snapshot) return Promise.resolve({ status: "failed" });
    invalidated = false;
    if (entry.snapshot === getAcknowledgedSnapshot?.() && !activePromise) {
      return Promise.resolve(savedResult({
        revision: Number(getRevision?.()),
        snapshot: entry.snapshot,
      }));
    }
    if (activePromise) {
      if (entry.snapshot !== activeEntry?.snapshot) queuedEntry = entry;
      return activePromise;
    }

    let operation;
    operation = drain(entry).finally(() => {
      if (activePromise === operation) {
        activePromise = null;
        activeEntry = null;
      }
    });
    activePromise = operation;
    return operation;
  };

  return {
    requestSave,
    flushLatest() {
      const latest = getLatestEntry?.();
      if (!latest) return activePromise || Promise.resolve({ status: "failed" });
      return requestSave(latest);
    },
    awaitIdle() {
      return activePromise || Promise.resolve(savedResult({
        revision: Number(getRevision?.()),
        snapshot: getAcknowledgedSnapshot?.() || "",
      }));
    },
    invalidate() {
      invalidated = true;
      queuedEntry = null;
      activeEntry = null;
      activePromise = null;
    },
    resume() {
      invalidated = false;
    },
    getStatus() {
      return {
        active: Boolean(activePromise),
        activeSnapshot: activeEntry?.snapshot || "",
        queuedSnapshot: queuedEntry?.snapshot || "",
        latestSuccessfulOperationId,
      };
    },
  };
};
