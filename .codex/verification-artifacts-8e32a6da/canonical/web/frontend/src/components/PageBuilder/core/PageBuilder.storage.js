import { STORAGE_KEY } from "./PageBuilder.constants";
import { createBlankWorkspaceProject } from "./PageBuilder.starters";
import { cleanBuilderProject } from "./PageBuilder.project";

const unreadableBuilderDraftKeys = new Set();
const builderDraftReadStatuses = new Map();

export const hasUnreadableBuilderDraft = (storageKey = STORAGE_KEY) =>
  unreadableBuilderDraftKeys.has(storageKey);

export const getBuilderDraftReadStatus = (storageKey = STORAGE_KEY) =>
  builderDraftReadStatuses.get(storageKey) || "unknown";

const parseStoredProject = (raw) => cleanBuilderProject(JSON.parse(raw));

export const loadInitialProject = (storageKey = STORAGE_KEY) => {
  const raw = localStorage.getItem(storageKey);

  if (!raw) {
    unreadableBuilderDraftKeys.delete(storageKey);
    builderDraftReadStatuses.set(storageKey, "missing");
    return cleanBuilderProject(createBlankWorkspaceProject());
  }

  try {
    const project = parseStoredProject(raw);
    unreadableBuilderDraftKeys.delete(storageKey);
    builderDraftReadStatuses.set(storageKey, "primary");
    return project;
  } catch (error) {
    unreadableBuilderDraftKeys.add(storageKey);
    if (import.meta.env.DEV) {
      console.error("Builder draft JSON is unreadable; the stored value was preserved.", error);
    }

    const backupRaw = localStorage.getItem(`${storageKey}:backup`);
    if (backupRaw) {
      try {
        const backupProject = parseStoredProject(backupRaw);
        builderDraftReadStatuses.set(storageKey, "backup");
        return backupProject;
      } catch (backupError) {
        if (import.meta.env.DEV) {
          console.error("Builder backup JSON is also unreadable; both stored values were preserved.", backupError);
        }
      }
    }

    builderDraftReadStatuses.set(storageKey, "unrecoverable");
    return cleanBuilderProject(createBlankWorkspaceProject());
  }
};
