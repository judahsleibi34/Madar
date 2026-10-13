// "English | العربية": the inactive language is the button; the active one is marked.
export default function LanguageText({ language, onChange }) {
  return <span className="academy-language-text" role="group" aria-label="Language">
    <button type="button" lang="en" aria-pressed={language === "en"} onClick={() => onChange("en")}>English</button>
    <span aria-hidden="true">|</span>
    <button type="button" lang="ar" aria-pressed={language === "ar"} onClick={() => onChange("ar")}>العربية</button>
  </span>;
}
