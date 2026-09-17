import { useTranslation } from "react-i18next";
import appI18n from "../i18n";

export const normalizeCommerceLocale = (value) => String(value || "en").split("-")[0] === "ar" ? "ar" : "en";

export const localizeCommerceValue = (value, locale = "en", field = "") => {
  const language = normalizeCommerceLocale(locale);
  if (value == null) return "";
  const translations = field ? value?.[`${field}_translations`] : value?.translations || value;
  if (translations && typeof translations === "object" && !Array.isArray(translations)) {
    const preferred = translations[language];
    const fallback = translations.en ?? translations.ar ?? Object.values(translations)[0];
    if (preferred && typeof preferred === "object") return preferred.name || preferred.description || Object.values(preferred)[0] || "";
    if (fallback && typeof fallback === "object") return fallback.name || fallback.description || Object.values(fallback)[0] || "";
    return String(preferred || fallback || "");
  }
  return String(value?.[`${field}_${language}`] || value?.[`${field}_en`] || value?.[`${field}_ar`] || value?.[field] || value || "");
};

export const formatCommerceMoney = (value, currency, locale = "en") => {
  try { return new Intl.NumberFormat(normalizeCommerceLocale(locale) === "ar" ? "ar" : "en", { style: "currency", currency: String(currency || "USD").toUpperCase() }).format(Number(value || 0)); }
  catch { return `${Number(value || 0).toFixed(2)} ${String(currency || "").toUpperCase()}`.trim(); }
};

export const formatCommerceDateTime = (value, locale = "en") => {
  if (!value) return "—";
  try { return new Intl.DateTimeFormat(normalizeCommerceLocale(locale) === "ar" ? "ar" : "en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); }
  catch { return String(value); }
};

export function useCommerceI18n() {
  const translation = useTranslation("commerce", { i18n: appI18n });
  const i18n = translation?.i18n || appI18n;
  const t = typeof translation?.t === "function" ? translation.t : appI18n.getFixedT(i18n.language, "commerce");
  const locale = normalizeCommerceLocale(i18n.resolvedLanguage || i18n.language);
  return {
    t,
    locale,
    direction: locale === "ar" ? "rtl" : "ltr",
    money: (value, currency) => formatCommerceMoney(value, currency, locale),
    dateTime: (value) => formatCommerceDateTime(value, locale),
    number: (value) => new Intl.NumberFormat(locale === "ar" ? "ar" : "en").format(Number(value || 0)),
    status: (value) => t(`status.${value}`, { defaultValue: String(value || "").replaceAll("_", " ") }),
    payment: (value) => t(`payment.${value}`, { defaultValue: String(value || "").replaceAll("_", " ") }),
    localize: (value, field = "") => localizeCommerceValue(value, locale, field),
  };
}
