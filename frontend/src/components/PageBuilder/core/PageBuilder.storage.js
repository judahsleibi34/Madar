import { STORAGE_KEY } from "./PageBuilder.constants";
import { createBlankWorkspaceProject } from "./PageBuilder.starters";
import { cleanBuilderProject } from "./PageBuilder.project";

export const loadInitialProject = (storageKey = STORAGE_KEY) => {
  try {
    const raw = localStorage.getItem(storageKey);
    return cleanBuilderProject(raw ? JSON.parse(raw) : createBlankWorkspaceProject());
  } catch {
    return cleanBuilderProject(createBlankWorkspaceProject());
  }
};
