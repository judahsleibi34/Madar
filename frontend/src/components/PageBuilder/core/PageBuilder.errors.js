export const isBuilderError = (error, code) => error?.code === code;

export const isBuilderRevisionError = (error) =>
  isBuilderError(error, "project_revision_conflict") ||
  isBuilderError(error, "project_revision_required");

export const getBuilderConflictMessage = (error) => {
  const currentRevision = Number(error?.context?.current_revision);
  const revisionNote = Number.isInteger(currentRevision)
    ? ` The server is now on revision ${currentRevision}.`
    : "";

  return `This site was updated in another tab or session.${revisionNote} Your local edits are still here; review them before reloading.`;
};
