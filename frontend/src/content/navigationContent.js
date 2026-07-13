import publicEn from "../i18n/locales/en/public.json";
import publicAr from "../i18n/locales/ar/public.json";
import { PUBLIC_ROUTES } from "../config/routes";

export const primaryNavigationItems = [
  { id: "home", labelKey: "home", path: PUBLIC_ROUTES.home },
  { id: "pricing", labelKey: "pricing", path: PUBLIC_ROUTES.pricing },
  { id: "team", labelKey: "team", path: PUBLIC_ROUTES.team },
  { id: "about", labelKey: "about", path: PUBLIC_ROUTES.about },
  { id: "contact", labelKey: "contact", path: PUBLIC_ROUTES.contact },
];

export const footerNavigationItems = [
  { id: "home", labelKey: "home", path: PUBLIC_ROUTES.home },
  { id: "pricing", labelKey: "pricing", path: PUBLIC_ROUTES.pricing },
  { id: "contact", labelKey: "contact", path: PUBLIC_ROUTES.contact },
];

export const navigationContent = {
  en: publicEn.nav,
  ar: publicAr.nav,
};

export const getNavigationContent = (lang = "en") =>
  navigationContent[lang === "ar" ? "ar" : "en"];
