const ARABIC_RE = /[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]/;

export const normalizeLanguageMode = (value = "en") => {
  if (value === "arabic") return "ar";
  if (value === "english") return "en";
  return ["ar", "en", "bilingual"].includes(value) ? value : "en";
};

export const getDefaultFormLanguage = (form, fallback = "en") => {
  const mode = normalizeLanguageMode(form?.languageMode || form?.localeMode || form?.defaultLanguage || fallback);
  return mode === "bilingual" ? normalizeLanguageMode(form?.defaultLanguage || fallback) : mode;
};

export const getRuntimeLanguage = (form, requested = "en") => {
  const mode = normalizeLanguageMode(form?.languageMode || form?.localeMode || form?.defaultLanguage || requested);
  if (mode === "bilingual") return normalizeLanguageMode(requested);
  return mode;
};

export const isArabicLang = (lang = "en") => normalizeLanguageMode(lang) === "ar";

export const getDirectionForLanguage = (lang = "en") => (isArabicLang(lang) ? "rtl" : "ltr");

export const getContentDirection = (value, fallback = "ltr") =>
  ARABIC_RE.test(String(value || "")) ? "rtl" : fallback;

export const getLocalizedValue = (source, key, lang = "en", fallbackLang = "en") => {
  if (!source) return "";
  const localized = source.localized?.[key] || source[`${key}I18n`];
  if (localized && typeof localized === "object") {
    return localized[lang] ?? localized[fallbackLang] ?? localized.en ?? localized.ar ?? source[key] ?? "";
  }
  if (source[key] && typeof source[key] === "object") {
    return source[key][lang] ?? source[key][fallbackLang] ?? source[key].en ?? source[key].ar ?? "";
  }
  return source[key] ?? "";
};

export const setLocalizedValue = (source, key, lang = "en", value = "") => {
  const next = {
    ...source,
    localized: {
      ...(source?.localized || {}),
      [key]: {
        ...(source?.localized?.[key] || source?.[`${key}I18n`] || {}),
        [lang]: value,
      },
    },
  };

  if (lang === "en" || !next[key]) next[key] = value;
  return next;
};

export const getLocalizedOptions = (field, lang = "en", fallbackLang = "en") => {
  const localized = field?.localized?.options || field?.optionsI18n;
  if (localized && typeof localized === "object") {
    const options = localized[lang] || localized[fallbackLang] || localized.en || localized.ar;
    if (Array.isArray(options) && options.length) return options;
  }
  return Array.isArray(field?.options) && field.options.length ? field.options : [""];
};

export const setLocalizedOptions = (field, lang = "en", options = []) => {
  const nextOptions = options.length ? options : [""];
  const next = {
    ...field,
    localized: {
      ...(field?.localized || {}),
      options: {
        ...(field?.localized?.options || field?.optionsI18n || {}),
        [lang]: nextOptions,
      },
    },
  };

  if (lang === "en" || !Array.isArray(next.options) || next.options.length === 0) {
    next.options = nextOptions;
  }
  return next;
};
