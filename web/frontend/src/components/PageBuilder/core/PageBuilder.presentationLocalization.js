// Translate presentation only. Identity, routes, permissions and answers stay
// canonical even when a saved translation contains unexpected properties.
export const PRESENTATION_TEXT_KEYS = new Set([
  "name", "title", "navigationLabel", "content", "description", "alt",
  "brand", "headerButtonLabel", "footerText", "footerCopyright", "listTitle",
  "buttonLabel", "heading", "metaTitle", "metaDescription",
  "eyebrow", "primaryLabel", "secondaryLabel", "caption",
  "rights", "footerStoreName", "footerShopTitle", "footerHelpTitle", "footerFollowTitle",
]);

export function localizePresentation(value, language = "en") {
  if (Array.isArray(value)) return value.map(item => localizePresentation(item, language));
  if (!value || typeof value !== "object") return value;
  const result = Object.fromEntries(Object.entries(value).map(([key, item]) =>
    [key, key === "localized" ? item : localizePresentation(item, language)]));
  for (const key of PRESENTATION_TEXT_KEYS) {
    // Standard Builder inspectors edit the base English field. An older
    // duplicated English translation must not conceal that persisted edit.
    if (language === 'en' && typeof value[key] === 'string') continue;
    const translated = value.localized?.[key]?.[language];
    if (typeof translated === "string" && translated.trim()) result[key] = translated;
  }
  const items=value.localized?.listItems?.[language];
  if(language !== 'en' && Array.isArray(items) && items.length && items.every(item=>typeof item==='string'))result.listItems=[...items];
  return result;
}
