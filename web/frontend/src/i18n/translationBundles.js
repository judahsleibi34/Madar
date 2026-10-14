// Raw translation JSON per language and namespace, each in its own lazy
// chunk, so hosted tenant pages download only what their route renders.
// This module deliberately has no i18next dependency: the hosted entry
// starts these downloads before the i18n runtime itself has loaded.

const BUNDLE_LOADERS = {
  en: {
    common: () => import("./locales/en/common.json"),
    auth: () => import("./locales/en/auth.json"),
    public: () => import("./locales/en/public.json"),
    dashboard: () => import("./locales/en/dashboard.json"),
    commerce: () => import("./locales/en/commerce.json"),
    pageBuilder: () => import("./locales/en/pageBuilder.json"),
    dataAnalysis: () => import("./locales/en/dataAnalysis.json"),
  },
  ar: {
    common: () => import("./locales/ar/common.json"),
    auth: () => import("./locales/ar/auth.json"),
    public: () => import("./locales/ar/public.json"),
    dashboard: () => import("./locales/ar/dashboard.json"),
    commerce: () => import("./locales/ar/commerce.json"),
    pageBuilder: () => import("./locales/ar/pageBuilder.json"),
    dataAnalysis: () => import("./locales/ar/dataAnalysis.json"),
  },
};

export const TRANSLATION_LANGUAGES = Object.keys(BUNDLE_LOADERS);
export const TRANSLATION_NAMESPACES = Object.keys(BUNDLE_LOADERS.en);

// Arabic resolves missing keys from English (i18next fallbackLng), so an
// Arabic page needs both to render exactly the same text.
export const translationLanguagesFor = (language) => (language === "ar" ? ["ar", "en"] : ["en"]);

const pendingBundles = new Map();

const loadBundle = (language, namespace) => {
  const key = `${language}:${namespace}`;
  if (!pendingBundles.has(key)) {
    pendingBundles.set(
      key,
      BUNDLE_LOADERS[language][namespace]().then(
        (module) => module.default,
        (error) => {
          pendingBundles.delete(key); // a later request may retry
          throw error;
        },
      ),
    );
  }
  return pendingBundles.get(key);
};

// Resolves to { [language]: { [namespace]: data } }.
export const loadTranslationBundles = (languages, namespaces) => {
  const pairs = languages.flatMap((language) => namespaces.map((namespace) => [language, namespace]));
  return Promise.all(pairs.map(([language, namespace]) => loadBundle(language, namespace))).then((data) => {
    const bundles = {};
    pairs.forEach(([language, namespace], index) => {
      (bundles[language] ||= {})[namespace] = data[index];
    });
    return bundles;
  });
};
