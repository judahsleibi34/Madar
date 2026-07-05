import {
  createContext,
  createElement,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import enCommon from "./locales/en/common.json";
import enAuth from "./locales/en/auth.json";
import enPublic from "./locales/en/public.json";
import enDashboard from "./locales/en/dashboard.json";
import enPageBuilder from "./locales/en/pageBuilder.json";
import enDataAnalysis from "./locales/en/dataAnalysis.json";
import en from "./locales/en";

import arCommon from "./locales/ar/common.json";
import arAuth from "./locales/ar/auth.json";
import arPublic from "./locales/ar/public.json";
import arDashboard from "./locales/ar/dashboard.json";
import arPageBuilder from "./locales/ar/pageBuilder.json";
import arDataAnalysis from "./locales/ar/dataAnalysis.json";
import ar from "./locales/ar";

export const LANGUAGE_STORAGE_KEY = "madar.language";
export const DEFAULT_LANGUAGE = "en";
export const SUPPORTED_LANGUAGES = {
  en: {
    code: "en",
    label: "English",
    dir: "ltr",
  },
  ar: {
    code: "ar",
    label: "\u0627\u0644\u0639\u0631\u0628\u064a\u0629",
    dir: "rtl",
  },
};

export const I18N_NAMESPACES = [
  "common",
  "auth",
  "public",
  "dashboard",
  "pageBuilder",
  "dataAnalysis",
];

export const appLocales = { en, ar };

const LanguageContext = createContext(null);

const canUseDOM = () => typeof window !== "undefined" && typeof document !== "undefined";

function deepMerge(target, source) {
  return Object.entries(source).reduce(
    (result, [key, value]) => {
      if (
        value &&
        typeof value === "object" &&
        !Array.isArray(value) &&
        result[key] &&
        typeof result[key] === "object" &&
        !Array.isArray(result[key])
      ) {
        return {
          ...result,
          [key]: deepMerge(result[key], value),
        };
      }

      return {
        ...result,
        [key]: value,
      };
    },
    { ...target },
  );
}

function resolvePath(source, key) {
  if (!key) return undefined;

  return key.split(".").reduce((current, part) => {
    if (current && Object.prototype.hasOwnProperty.call(current, part)) {
      return current[part];
    }

    return undefined;
  }, source);
}

function interpolate(value, params = {}) {
  if (typeof value !== "string") return value;

  return value.replace(/\{\{\s*(\w+)\s*\}\}/g, (match, paramKey) =>
    Object.prototype.hasOwnProperty.call(params, paramKey)
      ? String(params[paramKey])
      : match,
  );
}

export function isSupportedLanguage(language) {
  return Boolean(SUPPORTED_LANGUAGES[language]);
}

export function normalizeLanguage(language) {
  const code = String(language || "").split("-")[0];
  return isSupportedLanguage(code) ? code : DEFAULT_LANGUAGE;
}

export function getStoredLanguage(storage = canUseDOM() ? window.localStorage : null) {
  const storedLanguage = storage?.getItem(LANGUAGE_STORAGE_KEY);

  if (isSupportedLanguage(storedLanguage)) {
    return storedLanguage;
  }

  if (storedLanguage) {
    storage?.setItem(LANGUAGE_STORAGE_KEY, DEFAULT_LANGUAGE);
  }

  return DEFAULT_LANGUAGE;
}

export function getDirection(language) {
  return SUPPORTED_LANGUAGES[normalizeLanguage(language)].dir;
}

export function applyDocumentLanguage(language) {
  if (!canUseDOM()) return normalizeLanguage(language);

  const safeLanguage = normalizeLanguage(language);
  const direction = getDirection(safeLanguage);
  const root = document.documentElement;

  root.lang = safeLanguage;
  root.dir = direction;
  root.classList.remove("lang-en", "lang-ar", "is-ltr", "is-rtl");
  root.classList.add(`lang-${safeLanguage}`, direction === "rtl" ? "is-rtl" : "is-ltr");
  document.body.dir = direction;

  return safeLanguage;
}

export function translate(key, fallback, params, language = i18n.language) {
  const safeLanguage = normalizeLanguage(language);
  const value = resolvePath(appLocales[safeLanguage], key);
  const englishValue = resolvePath(appLocales.en, key);
  const resolvedValue = value ?? englishValue;
  const fallbackValue = fallback && typeof fallback === "object" ? undefined : fallback;
  const interpolationParams = fallback && typeof fallback === "object" ? fallback : params;

  if (resolvedValue === undefined || resolvedValue === null) {
    return fallbackValue ?? key;
  }

  return interpolate(resolvedValue, interpolationParams);
}

const resources = {
  en: {
    common: deepMerge(enCommon, {
      common: en.common,
      language: en.language,
    }),
    auth: enAuth,
    public: enPublic,
    dashboard: deepMerge(enDashboard, {
      sidebar: en.sidebar,
      notifications: en.notifications,
      myPlan: en.myPlan,
    }),
    pageBuilder: enPageBuilder,
    dataAnalysis: enDataAnalysis,
  },
  ar: {
    common: deepMerge(arCommon, {
      common: ar.common,
      language: ar.language,
    }),
    auth: arAuth,
    public: arPublic,
    dashboard: deepMerge(arDashboard, {
      sidebar: ar.sidebar,
      notifications: ar.notifications,
      myPlan: ar.myPlan,
    }),
    pageBuilder: arPageBuilder,
    dataAnalysis: arDataAnalysis,
  },
};

const initialLanguage = getStoredLanguage();

i18n.use(initReactI18next).init({
  resources,
  lng: initialLanguage,
  fallbackLng: DEFAULT_LANGUAGE,
  defaultNS: "common",
  ns: I18N_NAMESPACES,
  interpolation: {
    escapeValue: false,
  },
});

applyDocumentLanguage(initialLanguage);

i18n.on("languageChanged", (nextLanguage) => {
  applyDocumentLanguage(nextLanguage);

  if (canUseDOM()) {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, normalizeLanguage(nextLanguage));
  }
});

export function LanguageProvider({ children }) {
  const [language, setLanguageState] = useState(() => getStoredLanguage());

  useEffect(() => {
    const safeLanguage = normalizeLanguage(language);
    applyDocumentLanguage(safeLanguage);

    if (i18n.language !== safeLanguage) {
      i18n.changeLanguage(safeLanguage);
    }
  }, [language]);

  const setLanguage = useCallback((nextLanguage) => {
    const safeLanguage = normalizeLanguage(nextLanguage);

    if (canUseDOM()) {
      window.localStorage.setItem(LANGUAGE_STORAGE_KEY, safeLanguage);
    }

    applyDocumentLanguage(safeLanguage);
    i18n.changeLanguage(safeLanguage);
    setLanguageState(safeLanguage);

    return safeLanguage;
  }, []);

  const t = useCallback(
    (key, fallback, params) => {
      const fallbackValue =
        fallback && typeof fallback === "object" ? undefined : fallback;
      const interpolationParams =
        fallback && typeof fallback === "object" ? fallback : params;
      const value = resolvePath(appLocales[language], key);
      const englishValue = resolvePath(appLocales.en, key);
      const resolvedValue = value ?? englishValue;

      if (resolvedValue === undefined || resolvedValue === null) {
        return fallbackValue ?? key;
      }

      return interpolate(resolvedValue, interpolationParams);
    },
    [language],
  );

  const value = useMemo(
    () => ({
      direction: getDirection(language),
      isRtl: getDirection(language) === "rtl",
      language,
      setLanguage,
      supportedLanguages: SUPPORTED_LANGUAGES,
      t,
    }),
    [language, setLanguage, t],
  );

  return createElement(LanguageContext.Provider, { value }, children);
}

export function useLanguage() {
  const context = useContext(LanguageContext);

  if (context) {
    return context;
  }

  const language = normalizeLanguage(i18n.language);

  return {
    direction: getDirection(language),
    isRtl: getDirection(language) === "rtl",
    language,
    setLanguage: (nextLanguage) => {
      const safeLanguage = normalizeLanguage(nextLanguage);
      i18n.changeLanguage(safeLanguage);
      return applyDocumentLanguage(safeLanguage);
    },
    supportedLanguages: SUPPORTED_LANGUAGES,
    t: (key, fallback, params) => translate(key, fallback, params, language),
  };
}

export default i18n;
