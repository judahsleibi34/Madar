import publicEn from "../i18n/locales/en/public.json";
import publicAr from "../i18n/locales/ar/public.json";

export const footerContent = {
  en: {
    ...publicEn.footer,
    email: "info@madar.com",
    phone: "+972 599 203 857",
    phoneHref: "tel:+972599203857",
    emailHref: "mailto:info@madar.com",
    instagramHref: "https://www.instagram.com/maadar_ps/",
    instagramTitle: "Instagram",
  },
  ar: {
    ...publicAr.footer,
    email: "info@madar.com",
    phone: "+972 599 203 857",
    phoneHref: "tel:+972599203857",
    emailHref: "mailto:info@madar.com",
    instagramHref: "https://www.instagram.com/maadar_ps/",
    instagramTitle: "Instagram",
  },
};

export const getFooterContent = (lang = "en") =>
  footerContent[lang === "ar" ? "ar" : "en"];
