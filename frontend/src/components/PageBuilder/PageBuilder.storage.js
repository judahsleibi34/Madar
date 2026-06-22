import { STORAGE_KEY } from "./PageBuilder.constants";
import { createInitialProject } from "./PageBuilder.starters";
import { cleanBuilderProject } from "./PageBuilder.project";

export const loadInitialProject = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return cleanBuilderProject(raw ? JSON.parse(raw) : createInitialProject());
  } catch {
    return cleanBuilderProject(createInitialProject());
  }
};
