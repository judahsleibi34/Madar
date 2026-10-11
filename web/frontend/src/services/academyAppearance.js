export function getAcademyAppearance(site, landing) {
  if (!site) return site;
  const presentation = landing;
  return {
    ...site,
    brand: presentation?.siteChrome?.brand || site?.brand,
    logo_url: presentation?.siteChrome?.logoUrl || site?.logo_url,
    theme: presentation?.theme || site?.theme,
  };
}
