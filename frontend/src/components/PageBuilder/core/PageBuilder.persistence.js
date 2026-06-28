export const persistBuilderProject = ({
  nextProject,
  message,
  demoMode,
  storageKey,
  setProject,
  showToast,
}) => {
  if (!demoMode) {
    localStorage.setItem(storageKey, JSON.stringify(nextProject));
  }

  setProject(nextProject);
  showToast(message);

  return nextProject;
};

export const createBuilderProjectPayload = ({
  project,
  builderProjectRecord,
  getBuilderProjectName,
  getBuilderProjectSlug,
}) => ({
  name: getBuilderProjectName(project),
  slug: getBuilderProjectSlug(project, builderProjectRecord),
  draft_schema: project,
});

export const exportBuilderProjectJson = async ({ project, showToast }) => {
  const payload = JSON.stringify(project, null, 2);
  console.log(payload);

  try {
    await navigator.clipboard.writeText(payload);
    showToast("Exported JSON copied to clipboard.");
  } catch {
    showToast("Exported JSON printed to console.");
  }
};
