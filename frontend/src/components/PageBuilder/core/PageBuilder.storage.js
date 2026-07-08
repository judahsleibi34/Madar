import { STORAGE_KEY } from "./PageBuilder.constants";
import { createBlankWorkspaceProject } from "./PageBuilder.starters";
import { cleanBuilderProject } from "./PageBuilder.project";

export const loadInitialProject = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return cleanBuilderProject(raw ? JSON.parse(raw) : createBlankWorkspaceProject());
  } catch {
    return cleanBuilderProject(createBlankWorkspaceProject());
  }
};
