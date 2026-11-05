import { useTranslation } from "react-i18next";
import appI18n from "../i18n";
import { reservationFormItemLabels } from "../components/PageBuilder/blocks/reservationForm";

export function useReservationEditorI18n() {
  const { t, i18n } = useTranslation("pageBuilder", { i18n: appI18n });
  const locale = String(i18n.resolvedLanguage || i18n.language || "en").startsWith("ar") ? "ar" : "en";
  return { t, locale, direction: locale === "ar" ? "rtl" : "ltr",
    fieldLabel: type => t(`bookingEditor.fieldTypes.${type}`, { defaultValue: reservationFormItemLabels[type] || type }) };
}
