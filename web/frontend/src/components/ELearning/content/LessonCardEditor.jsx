import { useTranslation } from "react-i18next";
import { Plus, Trash2 } from "lucide-react";
import LessonComponentCard from "./LessonCards";

const FIELDS = {
  vocabulary: [["word", true], ["meaning", true], ["arabic"], ["example"], ["pronunciation"], ["stress"]],
  expressions: [["expression", true], ["meaning"], ["arabic"], ["example"]],
};
const blank = kind => Object.fromEntries(FIELDS[kind].map(([name]) => [name, ""]));

/** Owner form for one structured lesson card; the parent stores it in a text block. */
export default function LessonCardEditor({ component, onChange }) {
  const { t } = useTranslation("dashboard");
  const label = name => t(`elearning.lessonCards.fields.${name}`);
  const field = (name, value, update, { required = false, long = false, lang = "en" } = {}) => <label key={name}>{label(name)}{required ? " *" : ""}
    {long ? <textarea rows={3} maxLength={2000} required={required} lang={lang} dir={lang === "ar" ? "rtl" : "ltr"} value={value} onChange={event => update(event.target.value)} />
      : <input maxLength={300} required={required} lang={lang} dir={lang === "ar" ? "rtl" : "ltr"} value={value} onChange={event => update(event.target.value)} />}
  </label>;
  const items = component.items || [];
  const setItem = (index, name, value) => onChange({ ...component, items: items.map((item, i) => i === index ? { ...item, [name]: value } : item) });
  return <div className="lesson-card-editor">
    {component.kind === "situation" && field("situation", component.text, text => onChange({ ...component, text }), { required: true, long: true })}
    {component.kind === "speaker_tip" && <>
      {field("tip", component.tip, tip => onChange({ ...component, tip }), { required: true, long: true })}
      {field("tipArabic", component.arabic, arabic => onChange({ ...component, arabic }), { long: true, lang: "ar" })}
      {field("avoid", component.avoid, avoid => onChange({ ...component, avoid }))}
      {field("say", component.say, say => onChange({ ...component, say }))}
    </>}
    {FIELDS[component.kind] && <>
      {items.map((item, index) => <fieldset key={index} className="lesson-card-editor-item">
        <legend>{t("elearning.lessonCards.item", { number: index + 1 })}</legend>
        {FIELDS[component.kind].map(([name, required]) => field(name, item[name], value => setItem(index, name, value), { required, lang: name === "arabic" ? "ar" : "en" }))}
        <button type="button" className="ecommerce-secondary-button" disabled={items.length <= 1} onClick={() => onChange({ ...component, items: items.filter((_, i) => i !== index) })}><Trash2 size={16} aria-hidden="true" />{t("elearning.lessonCards.removeItem")}</button>
      </fieldset>)}
      <button type="button" className="ecommerce-secondary-button" disabled={items.length >= 40} onClick={() => onChange({ ...component, items: [...items, blank(component.kind)] })}><Plus size={16} aria-hidden="true" />{t("elearning.lessonCards.addItem")}</button>
    </>}
    <details open><summary>{t("elearning.content.preview")}</summary><LessonComponentCard component={component} /></details>
  </div>;
}
