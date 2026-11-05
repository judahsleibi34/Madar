import DateTimeInput from "../../common/DateTimeInput";
import { useReservationEditorI18n } from "../../../utils/reservationEditorI18n";
import { useState } from "react";
import { ChevronDown, Trash2 } from "lucide-react";

export default function ReservationSessionCard({ dateLabel, time, index, session, onTimeChange, onTimeBlur, onRemove, onSettingsChange }) {
  const { t } = useReservationEditorI18n();
  const [expanded, setExpanded] = useState(false);
  const group = session.sessionType === "group";
  return (
    <div className={`reservation-bullet-row reservation-session-card${expanded ? " is-editing" : ""}`}>
      <DateTimeInput type="time" aria-label={t("bookingEditor.timeForDate", { number: index + 1, date: dateLabel })} value={time}
        onChange={event => onTimeChange(event.target.value)} onBlur={onTimeBlur} />
      <button type="button" aria-label={t("bookingEditor.removeTime", { time, date: dateLabel })} onClick={onRemove}>
        <Trash2 size={15} aria-hidden="true" />
      </button>
      <button type="button" className="reservation-session-summary" aria-expanded={expanded}
        aria-label={t("bookingEditor.editSession", { time: time || t("bookingEditor.newTime"), date: dateLabel })}
        onClick={() => setExpanded(value => !value)}>
        <span>{group ? t("bookingEditor.groupCapacity", { count: session.seatCapacity || 2 }) : t("bookingEditor.oneToOne1Person", { defaultValue: "One-to-one · 1 person" })}</span>
        <ChevronDown size={14} aria-hidden="true" />
      </button>
      {expanded && <div className="reservation-session-fields">
        <label>{t("bookingEditor.bookingType", { defaultValue: "Booking type" })}<select aria-label={t("bookingEditor.bookingTypeAtTime", { time })} value={group ? "group" : "private"}
            onChange={event => onSettingsChange({ sessionType: event.target.value,
              seatCapacity: event.target.value === "group" ? Math.max(2, Number(session.seatCapacity) || 2) : 1 })}>
            <option value="private">{t("bookingEditor.oneToOneSession", { defaultValue: "One-to-one session" })}</option>
            <option value="group">{t("bookingEditor.groupSession", { defaultValue: "Group session" })}</option>
          </select>
        </label>
        {group && <label>{t("bookingEditor.maximumPeople", { defaultValue: "Maximum people" })}<input type="number" aria-label={t("bookingEditor.maximumPeopleAtTime", { time })} min="2" max="1000" step="1"
            value={session.seatCapacity ?? 2}
            onBlur={event => onSettingsChange({ ...session, seatCapacity: Math.min(1000, Math.max(2, Number(event.target.value) || 2)) })}
            onChange={event => {
              const capacity = Number(event.target.value);
              if (event.target.value === "" || (Number.isInteger(capacity) && capacity >= 0 && capacity <= 1000))
                onSettingsChange({ ...session, seatCapacity: event.target.value === "" ? "" : capacity });
            }} />
        </label>}
        <small>{t("bookingEditor.otherTimesKeepTheirOwnSettings", { defaultValue: "Other times keep their own settings." })}</small>
      </div>}
    </div>
  );
}
