import i18n, {
  DEFAULT_LANGUAGE,
  LANGUAGE_STORAGE_KEY,
  SUPPORTED_LANGUAGES,
  applyDocumentLanguage,
  getStoredLanguage,
  normalizeLanguage,
} from "./index";

export { DEFAULT_LANGUAGE, LANGUAGE_STORAGE_KEY, SUPPORTED_LANGUAGES };

export function getCurrentLanguage() {
  return normalizeLanguage(i18n.language || getStoredLanguage());
}

export function setAppLanguage(language) {
  const safeLanguage = normalizeLanguage(language);

  if (typeof window !== "undefined") {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, safeLanguage);
  }

  i18n.changeLanguage(safeLanguage);
  applyDocumentLanguage(safeLanguage);

  return safeLanguage;
}
