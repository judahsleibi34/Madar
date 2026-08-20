import commonEn from "../i18n/locales/en/common.json";
import commonAr from "../i18n/locales/ar/common.json";

export const siteContent = {
  en: commonEn.app,
  ar: commonAr.app,
};

export const getSiteContent = (lang = "en") =>
  siteContent[lang === "ar" ? "ar" : "en"];
