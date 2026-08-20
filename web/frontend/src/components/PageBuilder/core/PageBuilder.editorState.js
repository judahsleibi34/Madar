import {
  areBuilderSchemasEqual,
  hashBuilderSchema,
  serializeBuilderSchema,
} from "./PageBuilder.schemaIdentity";

export const EDITOR_ONLY_PROJECT_FIELDS = [
  "activePageId",
  "activeFormId",
  "activeCollectionId",
  "activeWorkflowId",
  "activeRoleId",
];

export const SERVER_ONLY_PROJECT_FIELDS = [
  "status",
  "draft_revision",
  "published_revision",
  "published_version",
  "updated_at",
  "last_published_at",
];

const VOLATILE_PUBLISH_FIELDS = ["lastSavedAt", "lastPublishedAt"];

export const stripEditorOnlyState = (project = {}) => {
  const sharedProject = { ...project };
  EDITOR_ONLY_PROJECT_FIELDS.forEach((field) => delete sharedProject[field]);
  return sharedProject;
};

// The single content contract used by cloud writes, recovery snapshots,
// dirty comparisons, and publish preflight checks.
export const getPersistableProject = (project = {}) => {
  const sharedProject = stripEditorOnlyState(project);
  SERVER_ONLY_PROJECT_FIELDS.forEach((field) => delete sharedProject[field]);
  if (sharedProject.publish && typeof sharedProject.publish === "object" && !Array.isArray(sharedProject.publish)) {
    sharedProject.publish = { ...sharedProject.publish };
    VOLATILE_PUBLISH_FIELDS.forEach((field) => delete sharedProject.publish[field]);
  }
  return sharedProject;
};

export const serializePersistableProject = (project = {}) =>
  serializeBuilderSchema(getPersistableProject(project));

export const hashPersistableProject = (project = {}) =>
  hashBuilderSchema(getPersistableProject(project));

export const arePersistableProjectsEqual = (left, right) =>
  areBuilderSchemasEqual(getPersistableProject(left), getPersistableProject(right));

// Compatibility alias for the initial cross-device implementation.
export const DEVICE_LOCAL_PROJECT_FIELDS = EDITOR_ONLY_PROJECT_FIELDS;
export const stripDeviceLocalProjectState = stripEditorOnlyState;

export const getProjectEditorDefaults = (project = {}) => ({
  activePageId:
    project.pages?.find((page) => page?.id === project.defaultPageId)?.id ||
    project.pages?.find((page) => page?.isDefault === true)?.id ||
    project.pages?.[0]?.id ||
    "",
  activeFormId: project.forms?.[0]?.id || "",
  activeWorkflowId: project.workflows?.[0]?.id || "",
  activeRoleId: project.roles?.[0]?.id || "",
});

export const withLocalProjectEditorDefaults = (project = {}) => {
  const sharedProject = stripEditorOnlyState(project);
  return {
    ...sharedProject,
    ...getProjectEditorDefaults(sharedProject),
  };
};
