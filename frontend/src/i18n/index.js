import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import enCommon from "./locales/en/common.json";
import enAuth from "./locales/en/auth.json";
import enPublic from "./locales/en/public.json";
import enDashboard from "./locales/en/dashboard.json";
import enPageBuilder from "./locales/en/pageBuilder.json";
import enDataAnalysis from "./locales/en/dataAnalysis.json";

import arCommon from "./locales/ar/common.json";
import arAuth from "./locales/ar/auth.json";
import arPublic from "./locales/ar/public.json";
import arDashboard from "./locales/ar/dashboard.json";
import arPageBuilder from "./locales/ar/pageBuilder.json";
import arDataAnalysis from "./locales/ar/dataAnalysis.json";

export const I18N_NAMESPACES = [
  "common",
  "auth",
  "public",
  "dashboard",
  "pageBuilder",
  "dataAnalysis",
];

const resources = {
  en: {
    common: enCommon,
    auth: enAuth,
    public: enPublic,
    dashboard: enDashboard,
    pageBuilder: enPageBuilder,
    dataAnalysis: enDataAnalysis,
  },
  ar: {
    common: arCommon,
    auth: arAuth,
    public: arPublic,
    dashboard: arDashboard,
    pageBuilder: arPageBuilder,
    dataAnalysis: arDataAnalysis,
  },
};

const savedLanguage = localStorage.getItem("appLanguage");
const initialLanguage = savedLanguage === "ar" || savedLanguage === "en" ? savedLanguage : "en";

i18n.use(initReactI18next).init({
  resources,
  lng: initialLanguage,
  fallbackLng: "en",
  defaultNS: "common",
  ns: I18N_NAMESPACES,
  interpolation: {
    escapeValue: false,
  },
});

const applyDocumentLanguage = (lang) => {
  const safeLang = lang === "ar" ? "ar" : "en";
  const direction = safeLang === "ar" ? "rtl" : "ltr";

  document.documentElement.lang = safeLang;
  document.documentElement.dir = direction;
  document.body.classList.remove("lang-en", "lang-ar");
  document.body.classList.add(`lang-${safeLang}`);
};

applyDocumentLanguage(initialLanguage);

i18n.on("languageChanged", applyDocumentLanguage);

export default i18n;
