import madarLearningLanding from "../content/pageBuilder/madarLearningLanding.json";

export function getAcademyAppearance(site, landing) {
  if (!site) return site;
  const presentation = import.meta.env.DEV && import.meta.env.VITE_MADAR_LOCAL_LANDING_PREVIEW === "true" && site?.subdomain === "testing" ? madarLearningLanding : landing;
  return {
    ...site,
    brand: presentation?.siteChrome?.brand || site?.brand,
    logo_url: presentation?.siteChrome?.logoUrl || site?.logo_url,
    theme: presentation?.theme || site?.theme,
  };
}
