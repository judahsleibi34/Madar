import { useReservationEditorI18n } from "../../../utils/reservationEditorI18n";
import { getReservationStarterTranslation } from "../blocks/reservationForm";

export default function BookingFieldTranslations({ item, language, onLanguageChange, onUpdate, inline = false }) {
  const { t } = useReservationEditorI18n();
  const translation = item.translations?.[language] || {};
  const update = changes => onUpdate({ translations: { ...item.translations,
    [language]: { ...translation, ...changes } } });
  const fields = ["heading", "paragraph"].includes(item.type) ? ["text"]
    : ["text", "email", "phone"].includes(item.type) ? ["label", "placeholder"] : ["label"];
  const Wrapper = inline ? "section" : "details";
  return (
    <Wrapper className="booking-field-translations" aria-label={inline ? t("bookingEditor.translations") : undefined}>
      {inline ? <strong>{t("bookingEditor.translations")}</strong> : <summary>{t("bookingEditor.translations")}</summary>}
      <p>{t("bookingEditor.translationsHelp")}</p>
      <div className="booking-translation-tabs" role="group" aria-label={t("bookingEditor.translationLanguage")}>
        <button type="button" aria-pressed={language === "en"} onClick={() => onLanguageChange("en")}>English</button>
        <button type="button" aria-pressed={language === "ar"} onClick={() => onLanguageChange("ar")}>العربية</button>
      </div>
      {fields.map(field => {
        const multiline = item.type === "paragraph" && field === "text";
        const sharedHeading = item.type === "heading" && language === "en" && field === "text";
        const Input = multiline ? "textarea" : "input";
        const display = value => multiline ? value || "" : String(value || "").replace(/\r\n|[\r\n]/g, " ");
        return <label key={field}>
        {t(`bookingEditor.translationField.${field}`)}
        <Input dir={language === "ar" ? "rtl" : "ltr"} lang={language}
          aria-label={t("bookingEditor.translationInput", { language: language === "ar" ? "العربية" : "English", field: t(`bookingEditor.translationField.${field}`) })}
          value={display(sharedHeading ? item.text : translation[field]?.trim() ? translation[field] : getReservationStarterTranslation(item, field, language))} placeholder={display(item[field])}
          onChange={event => sharedHeading ? onUpdate({ text: event.target.value }) : update({ [field]: event.target.value })} />
      </label>;
      })}
      {(item.options || []).map((option, index) => <label key={option}>
        {t("bookingEditor.translationChoice", { number: index + 1 })}
        <input dir={language === "ar" ? "rtl" : "ltr"} lang={language}
          aria-label={t("bookingEditor.translationChoiceInput", { language: language === "ar" ? "العربية" : "English", number: index + 1 })}
          value={translation.options?.[option] || getReservationStarterTranslation(item, "option", language, option) || ""} placeholder={option}
          onChange={event => update({ options: { ...translation.options, [option]: event.target.value } })} />
      </label>)}
    </Wrapper>
  );
}
