import { useTranslation } from "react-i18next";

export default function PresentationTranslationInspector({ element, onChange }) {
  const { i18n } = useTranslation();
  const arabic = i18n.language.startsWith("ar");
  const keys = ["content", "title", "description", "alt", "listTitle", "eyebrow", "primaryLabel", "secondaryLabel", "caption"]
    .filter(key => typeof element[key] === "string");
  if (!keys.length) return null;
  return <details className="builder-presentation-translations">
    <summary>{arabic ? "ترجمة المحتوى" : "Content translations"}</summary>
    {keys.map(key => <fieldset key={key}><legend>{key}</legend>
      {["en", "ar"].map(language => <label key={language}>
        {language === "ar" ? "العربية" : "English"}
        <textarea dir={language === "ar" ? "rtl" : "ltr"} lang={language}
          value={language === "en" ? element[key] : element.localized?.[key]?.[language] ?? ""}
          onChange={event => onChange({
            ...(language === "en" ? { [key]: event.target.value } : {}),
            localized: { ...element.localized, [key]: {
              ...element.localized?.[key], [language]: event.target.value,
            } },
          })} />
      </label>)}
    </fieldset>)}
  </details>;
}
