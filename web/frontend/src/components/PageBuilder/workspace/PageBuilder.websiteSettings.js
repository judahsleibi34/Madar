import { defaultSiteChrome } from "../core/PageBuilder.constants";
import { sanitizeSubdomain } from "../core/PageBuilder.routing";

// Private Website projection: hydration retains its separate raw-value semantics.
export const getWebsiteSettingsPayload = (project = {}) => {
  const siteChrome = { ...defaultSiteChrome, ...(project.siteChrome || {}) };
  return {
    subdomain: sanitizeSubdomain(project.publish?.subdomain || ""),
    brand: String(siteChrome.brand || "").trim(),
    footer_store_name: String(siteChrome.footerStoreName || "").trim(),
    logo_url: String(siteChrome.logoUrl || "").trim(),
    contact_email: String(siteChrome.contactEmail || "").trim(),
    phone: String(siteChrome.phone || "").trim(),
    description: String(siteChrome.description || "").trim(),
  };
};

export const websiteSettingsPayloadChanged = (previousProject, nextProject) =>
  JSON.stringify(getWebsiteSettingsPayload(previousProject)) !==
  JSON.stringify(getWebsiteSettingsPayload(nextProject));
