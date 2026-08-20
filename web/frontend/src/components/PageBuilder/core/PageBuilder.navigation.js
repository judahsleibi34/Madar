import { normalizePublicPageSlug } from "./PageBuilder.routing";

export const getPageNavigationLabel = (page = {}) =>
  String(page.navigationLabel || page.name || page.title || "Untitled page").trim();

export const findPageByNavigationReference = (pages = [], value = "") => {
  const target = String(value || "").toLowerCase().replace(/^\/+|\/+$/g, "").trim();
  if (!target) return null;
  return (pages || []).find((page) => {
    const references = [
      page?.id,
      page?.name,
      page?.navigationLabel,
      normalizePublicPageSlug(page?.slug, page?.name),
    ].map((item) => String(item || "").toLowerCase().replace(/^\/+|\/+$/g, "").trim());
    return references.includes(target);
  }) || null;
};

export const getNavigablePages = (pages = [], { excludePageIds = [] } = {}) => {
  const excluded = new Set((excludePageIds || []).map((id) => String(id || "")));
  const seenIds = new Set();
  const seenSlugs = new Set();

  return (Array.isArray(pages) ? pages : []).filter((page) => {
    const id = String(page?.id || "").trim();
    if (!id || excluded.has(id) || page?.showInNavigation === false || seenIds.has(id)) {
      return false;
    }
    const slug = normalizePublicPageSlug(page?.slug, page?.name);
    if (seenSlugs.has(slug)) return false;
    seenIds.add(id);
    seenSlugs.add(slug);
    return true;
  });
};
