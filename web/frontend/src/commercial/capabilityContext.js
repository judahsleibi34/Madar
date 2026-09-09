import { createContext, useContext } from "react";
export const DENIED = { ready: false, capabilities: [], revision: "unresolved", can: () => false };
export const WorkspaceContext = createContext(DENIED);
export const useWorkspaceCapabilities = () => useContext(WorkspaceContext);

// The server owns the plan matrix. These are route requirements only.
export const builderTabCapabilities = {
  design: ["page_builder"], chrome: ["page_builder"], theme: ["page_builder"], users: ["page_builder"],
  forms: ["forms"], reservations: ["reservation_management"], responses: ["response_management"],
  data: ["data_import"], publish: ["website_publish", "public_form_links"], workflows: ["forms"],
};
export function workspaceRouteCapabilities(path) {
  const tab = path.match(/^\/page-builder\/projects\/[^/]+\/(pages|header-footer|website-theme|users|forms|reservations|data|responses|publish|workflows|preview|form-preview)(?:\/|$)/)?.[1];
  if (tab) return ({ pages: ["page_builder"], "header-footer": ["page_builder"], "website-theme": ["page_builder"], preview: ["website_publish"], "form-preview": ["forms"], ...builderTabCapabilities })[tab];
  if (/^\/ecommerce\/cv-rerank(?:\/|$)/.test(path)) return ["cv_reranker"];
  if (/^\/ecommerce(?:\/|$)/.test(path)) return ["ecommerce_management"];
  if (/^\/(calendar|agenda)(?:\/|$)/.test(path)) return ["internal_calendar"];
  if (/^\/builder-data(?:\/|$)/.test(path)) return ["data_import"];
  if (/^\/builder-responses(?:\/|$)/.test(path)) return ["response_management"];
  if (/^\/(page-builder|archive)(?:\/|$)/.test(path)) return ["forms", "page_builder"];
  return [];
}
