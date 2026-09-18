import { Languages } from "lucide-react";

import { useLanguage } from "../i18n";
import "./LanguageSwitcher/LanguageSwitcher.css";

export default function LanguageSwitcher({
  current,
  onChange,
  compact = false,
  className = "",
  label,
}) {
  const { language, setLanguage, supportedLanguages, t } = useLanguage();

  const safeLanguage = supportedLanguages[current] ? current : language;
  const nextLanguage = safeLanguage === "ar" ? "en" : "ar";

  const selected = supportedLanguages[safeLanguage] || supportedLanguages.en;
  const next = supportedLanguages[nextLanguage] || supportedLanguages.en;
  const selectedLabel = t(`language.${safeLanguage}`, selected.label);
  const nextLabel = t(`language.${nextLanguage}`, next.label);
  const switchLabel = t("language.switchTo", {
    language: nextLabel,
  });

  const handleToggle = () => {
    const selectedLanguage = setLanguage(nextLanguage);

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
      aria-label={switchLabel}
      title={switchLabel}
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
          {label || selectedLabel}
        </span>
      )}

      <span className="language-toggle-dot" aria-hidden="true" />
    </button>
  );
}
