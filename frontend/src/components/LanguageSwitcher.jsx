import { Languages } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  SUPPORTED_LANGUAGES,
  getCurrentLanguage,
  setAppLanguage,
} from "../i18n/language";
import "./LanguageSwitcher/LanguageSwitcher.css";

export default function LanguageSwitcher({
  current,
  onChange,
  compact = false,
  className = "",
}) {
  const { t, i18n } = useTranslation("common");

  const activeLanguage =
    current || i18n.language?.split("-")?.[0] || getCurrentLanguage();

  const safeLanguage = activeLanguage === "ar" ? "ar" : "en";
  const nextLanguage = safeLanguage === "ar" ? "en" : "ar";

  const selected = SUPPORTED_LANGUAGES[safeLanguage] || SUPPORTED_LANGUAGES.en;
  const next = SUPPORTED_LANGUAGES[nextLanguage] || SUPPORTED_LANGUAGES.en;
  const selectedLabel = t(`language.${safeLanguage}`, {
    defaultValue: selected.label,
  });
  const nextLabel = t(`language.${nextLanguage}`, {
    defaultValue: next.label,
  });

  const handleToggle = () => {
    const selectedLanguage = setAppLanguage(nextLanguage);

    document.documentElement.dir = selectedLanguage === "ar" ? "rtl" : "ltr";
    document.documentElement.lang = selectedLanguage === "ar" ? "ar" : "en";

    if (typeof onChange === "function") {
      onChange(selectedLanguage);
    }
  };

  return (
    <button
      type="button"
      dir="ltr"
      className={[
        "lang-switcher",
        "language-toggle-button",
        compact ? "is-compact" : "",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      onClick={handleToggle}
      aria-label={t("language.switchTo", {
        language: nextLabel,
        defaultValue: `Switch language to ${nextLabel}`,
      })}
      title={t("language.switchTo", {
        language: nextLabel,
        defaultValue: `Switch language to ${nextLabel}`,
      })}
      data-language={safeLanguage}
      data-next-language={nextLanguage}
    >
      <span className="language-toggle-animation" aria-hidden="true">
        <Languages size={22} />
      </span>

      {!compact && (
        <span
          className="language-toggle-current"
          dir={safeLanguage === "ar" ? "rtl" : "ltr"}
        >
          {selectedLabel}
        </span>
      )}

      <span className="language-toggle-dot" aria-hidden="true" />
    </button>
  );
}
