import { getDefaultPublicPage } from "./PageBuilder.routing";

export const resolveInspectorPage = (project = {}) => {
  const pages = Array.isArray(project.pages) ? project.pages : [];
  return pages.find((page) => page?.id === project.activePageId) ||
    getDefaultPublicPage(pages, project.defaultPageId) ||
    null;
};

export const resolveInspectorMode = ({
  selected,
  selectedElement,
  selectedSection,
  selectedColumn,
  activePage,
} = {}) => {
  if (selected?.type === "element" && selectedElement) return "element";
  if (selected?.type === "section" && selectedSection) return "section";
  if (selected?.type === "column" && selectedColumn) return "column";
  if (["siteHeader", "siteFooter"].includes(selected?.type)) return selected.type;
  return activePage ? "page" : "empty";
};
