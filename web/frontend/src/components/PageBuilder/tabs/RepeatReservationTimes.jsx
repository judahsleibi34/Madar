import { useReservationEditorI18n } from "../../../utils/reservationEditorI18n";
export default function RepeatReservationTimes({ checked, onChange }) {
  const { t } = useReservationEditorI18n();
  return (
    <div className="reservation-repeat">
      <label className="reservation-repeat-toggle">
        <input type="checkbox" checked={checked} onChange={event => onChange(event.target.checked)} />{t("bookingEditor.repeatWeekly", { defaultValue: "Repeat weekly" })}</label>
    </div>
  );
}
