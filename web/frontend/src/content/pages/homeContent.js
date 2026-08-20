import publicEn from "../../i18n/locales/en/public.json";
import publicAr from "../../i18n/locales/ar/public.json";

export const homeContent = {
  en: {
    hero: publicEn.hero,
  },
  ar: {
    hero: publicAr.hero,
  },
};

export const getHomeContent = (lang = "en") =>
  homeContent[lang === "ar" ? "ar" : "en"];
