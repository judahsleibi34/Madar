import { arePersistableProjectsEqual } from "./PageBuilder.editorState";

export const getBuilderPublicationState = (record) => {
  const draft = record?.draft_schema;
  const published = record?.published_schema;
  const draftPageCount = Array.isArray(draft?.pages) ? draft.pages.length : 0;
  const publishedPageCount = Array.isArray(published?.pages) ? published.pages.length : 0;
  const hasPublishedSchema = Boolean(published && typeof published === "object");
  const differs = hasPublishedSchema && !arePersistableProjectsEqual(draft, published);

  return {
    status: !hasPublishedSchema ? "draft_saved" : differs ? "unpublished_changes" : "published",
    differs,
    draftPageCount,
    publishedPageCount,
    publishedHasMorePages: differs && publishedPageCount > draftPageCount,
  };
};

export const getBuilderPublicationLabel = (state) => {
  if (state?.status === "published") return "Published";
  if (state?.status === "unpublished_changes") {
    return "The saved draft differs from the currently published site.";
  }
  return "Draft saved — not published";
};

const blockedPublishPreparation = (reason, details = {}) => ({
  ready: false,
  reason,
  ...details,
});

export const getBuilderPublishReadiness = ({
  hydrated = false,
  routedProjectId = "",
  loadedProjectId = "",
  draftRevision = null,
  currentSnapshot = "",
  acknowledgedSnapshot = "",
  conflict = false,
  operationInFlight = false,
} = {}) => {
  if (!hydrated || !routedProjectId || routedProjectId !== loadedProjectId) {
    return blockedPublishPreparation("loading");
  }
  if (conflict) return blockedPublishPreparation("conflict");
  if (operationInFlight) return blockedPublishPreparation("saving");
  if (!Number.isInteger(Number(draftRevision)) || Number(draftRevision) < 0) {
    return blockedPublishPreparation("loading");
  }
  if (!acknowledgedSnapshot || currentSnapshot !== acknowledgedSnapshot) {
    return blockedPublishPreparation("unsaved_changes");
  }
  return {
    ready: true,
    projectId: routedProjectId,
    draftRevision: Number(draftRevision),
    acknowledgedHash: acknowledgedSnapshot,
  };
};

/**
 * Turns the latest editor state into one backend-confirmed publish input.
 * Every value is read through a getter so an autosave or automatic rebase that
 * finishes while this function is awaiting cannot leave publishing with a
 * render-time revision or snapshot.
 */
export const prepareBuilderProjectForPublish = async ({
  getState,
  getActiveOperation = () => null,
  flushSave,
  maxFlushes = 2,
} = {}) => {
  if (typeof getState !== "function" || typeof flushSave !== "function") {
    return blockedPublishPreparation("loading");
  }

  const read = () => getState() || {};
  const inspect = () => getBuilderPublishReadiness(read());
  let readiness = inspect();
  if (readiness.reason === "loading" || readiness.reason === "conflict") return readiness;

  const activeOperation = getActiveOperation();
  if (activeOperation) {
    const activeResult = await activeOperation;
    readiness = inspect();
    if (readiness.reason === "loading" || readiness.reason === "conflict") return readiness;
    if (activeResult === false && readiness.reason !== "unsaved_changes") {
      return blockedPublishPreparation("save_failed");
    }
  }

  for (let attempt = 0; attempt < maxFlushes; attempt += 1) {
    readiness = inspect();
    if (readiness.ready) {
      return {
        ...readiness,
        acknowledgedSchema: read().acknowledgedSchema,
      };
    }
    if (readiness.reason === "loading" || readiness.reason === "conflict") return readiness;

    const saved = await flushSave();
    const trailingOperation = getActiveOperation();
    if (trailingOperation) await trailingOperation;

    readiness = inspect();
    if (readiness.ready) {
      return {
        ...readiness,
        acknowledgedSchema: read().acknowledgedSchema,
      };
    }
    if (readiness.reason === "loading" || readiness.reason === "conflict") return readiness;
    if (!saved) return blockedPublishPreparation("save_failed");
  }

  return blockedPublishPreparation("unsaved_changes");
};

export const runBuilderPublishSingleFlight = (promiseRef, operation) => {
  if (promiseRef?.current) return promiseRef.current;
  if (!promiseRef || typeof operation !== "function") return Promise.resolve(false);

  let lockedPromise;
  lockedPromise = Promise.resolve()
    .then(operation)
    .finally(() => {
      if (promiseRef.current === lockedPromise) promiseRef.current = null;
    });
  promiseRef.current = lockedPromise;
  return lockedPromise;
};
