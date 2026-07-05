export const persistBuilderProject = ({
  nextProject,
  message = "",
  demoMode,
  storageKey,
  setProject,
  showToast,
  silent = false,
}) => {
  if (!demoMode) {
    localStorage.setItem(storageKey, JSON.stringify(nextProject));
  }

  setProject(nextProject);

  if (!silent && message) {
    showToast(message);
  }

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

const downloadBuilderProjectJson = (payload) => {
  if (typeof document === "undefined" || typeof Blob === "undefined" || typeof URL === "undefined") {
    throw new Error("Project export download is unavailable.");
  }

  const blob = new Blob([payload], { type: "application/json" });
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");

  try {
    link.href = objectUrl;
    link.download = "madar-builder-project.json";
    link.rel = "noopener";
    document.body.appendChild(link);
    link.click();
  } finally {
    link.remove();
    URL.revokeObjectURL(objectUrl);
  }
};

export const exportBuilderProjectJson = async ({ project, showToast }) => {
  const payload = JSON.stringify(project, null, 2);

  try {
    await navigator.clipboard.writeText(payload);
    showToast("Exported JSON copied to clipboard.");
  } catch {
    try {
      downloadBuilderProjectJson(payload);
      showToast("Exported JSON downloaded.");
    } catch {
      showToast("Export is unavailable. Please try again.");
    }
  }
};
