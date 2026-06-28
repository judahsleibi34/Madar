import publicEn from "../i18n/locales/en/public.json";
import publicAr from "../i18n/locales/ar/public.json";

export const primaryNavigationItems = [
  { id: "home", labelKey: "home", path: "/" },
  { id: "features", labelKey: "features", path: "/features" },
  { id: "pricing", labelKey: "pricing", path: "/pricing" },
  { id: "team", labelKey: "team", path: "/team" },
  { id: "about", labelKey: "about", path: "/about" },
  { id: "contact", labelKey: "contact", path: "/contact" },
];

export const footerNavigationItems = [
  { id: "home", labelKey: "home", path: "/" },
  { id: "features", labelKey: "features", path: "/features" },
  { id: "pricing", labelKey: "pricing", path: "/pricing" },
  { id: "contact", labelKey: "contact", path: "/contact" },
];

export const navigationContent = {
  en: publicEn.nav,
  ar: publicAr.nav,
};

export const getNavigationContent = (lang = "en") =>
  navigationContent[lang === "ar" ? "ar" : "en"];
