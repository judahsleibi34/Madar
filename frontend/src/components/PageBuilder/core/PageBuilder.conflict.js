import { getPersistableProject } from "./PageBuilder.editorState";
import { mergeBuilderDraftSchemas } from "./PageBuilder.merge";

export const prepareBuilderServerAdoption = ({
  serverRecord,
  routedProjectId,
  normalizeProject,
  createSnapshot,
} = {}) => {
  if (!serverRecord?.id || serverRecord.id !== routedProjectId) {
    throw new Error("The routed project could not be verified");
  }
  const revision = Number(serverRecord.draft_revision);
  if (!Number.isInteger(revision) || revision < 0) {
    throw new Error("The server draft revision is invalid");
  }
  const project = normalizeProject(serverRecord);
  if (!project || typeof project !== "object") {
    throw new Error("The server draft could not be loaded");
  }
  const persistableProject = getPersistableProject(project);
  const snapshot = createSnapshot(persistableProject);
  return { project, persistableProject, record: serverRecord, revision, snapshot };
};

export const adoptBuilderServerRuntime = ({
  adoption,
  refs,
  stopScheduling,
} = {}) => {
  if (!adoption || !refs) throw new Error("Server adoption state is incomplete");
  stopScheduling?.();
  if (refs.requestGeneration) refs.requestGeneration.current += 1;
  refs.builderProjectRecord.current = adoption.record;
  refs.backendDraftRevision.current = adoption.revision;
  refs.project.current = adoption.project;
  if (refs.baseSchema) refs.baseSchema.current = adoption.persistableProject;
  refs.acknowledgedSnapshot.current = adoption.snapshot;
  refs.pendingSnapshot.current = "";
  refs.pendingRequest.current = null;
  refs.activeSnapshot.current = "";
  refs.savePromise.current = null;
  refs.saveInFlight.current = false;
  refs.pendingExternalDraft.current = null;
  refs.externalDraftRevisions?.current?.clear?.();
  refs.hydrationComplete.current = true;
  // Clear conflict last: every authoritative ref is ready before writes resume.
  refs.conflict.current = false;
};

export const runBuilderAutomaticRebase = async ({
  baseSchema,
  localSchema,
  routedProjectId,
  fetchServerProject,
  normalizeServerSchema,
  prepareMergedProject = (schema) => schema,
  createRetryPayload,
  updateServerProject,
  validateAcknowledgement,
  resolveConflicts,
  isCurrent = () => true,
} = {}) => {
  const serverRecord = await fetchServerProject(routedProjectId);
  if (!isCurrent()) return { status: "obsolete" };
  if (!serverRecord?.id || serverRecord.id !== routedProjectId) {
    throw new Error("The routed project could not be verified during conflict recovery");
  }
  const serverRevision = Number(serverRecord.draft_revision);
  if (!Number.isInteger(serverRevision) || serverRevision < 0) {
    throw new Error("The latest server revision is invalid");
  }
  const serverSchema = getPersistableProject(normalizeServerSchema(serverRecord));
  const mergeResult = mergeBuilderDraftSchemas({ baseSchema, localSchema, serverSchema });
  const mergeState = { baseSchema, localSchema, serverSchema, serverRecord, mergeResult };
  let mergedSchema = mergeResult.mergedSchema;
  if (mergeResult.conflicts.length > 0) {
    const resolvedSchema = resolveConflicts?.(mergeState);
    if (!resolvedSchema) return { status: "conflict", ...mergeState };
    mergedSchema = getPersistableProject(resolvedSchema);
  }

  const mergedProject = prepareMergedProject(mergedSchema);
  const payload = createRetryPayload({ mergedProject, serverRecord, serverRevision });
  try {
    if (!isCurrent()) return { status: "obsolete" };
    const savedRecord = await updateServerProject(routedProjectId, payload);
    if (!isCurrent()) return { status: "obsolete" };
    const savedRevision = validateAcknowledgement({
      projectId: routedProjectId,
      previousRevision: serverRevision,
      savedRecord,
    });
    return {
      status: "saved",
      ...mergeState,
      mergedProject,
      payload,
      savedRecord,
      savedRevision,
    };
  } catch (error) {
    error.builderMergeState = mergeState;
    throw error;
  }
};
