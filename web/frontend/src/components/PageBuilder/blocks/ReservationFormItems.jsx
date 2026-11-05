import DateTimeInput from "../../common/DateTimeInput";
import FixedSlotPicker from "./FixedSlotPicker";
import { getReservationContent } from "../../../content/pageBuilder/reservationContent";
import { cloneElement } from "react";
import { getReservationLayoutStyle } from "./reservationLayout";
import "./reservationLayout.css";
import { getReservationTextStyle, normalizeReservationTextStyle } from "./reservationForm";

const renderFormattedText = (item, className) => {
  const textStyle = normalizeReservationTextStyle(item.textStyle);
  const style = getReservationTextStyle(item);
  const direction = item.direction === "rtl" ? "rtl" : "ltr";
  const lines = String(item.text || "").split("\n").filter((line) => line.trim());

  if (textStyle.format === "bullets" || textStyle.format === "numbers") {
    const Tag = textStyle.format === "numbers" ? "ol" : "ul";
    return <Tag className={className} dir={direction} style={style}>{lines.map((line, index) => <li key={`${item.id}_${index}`}>{line}</li>)}</Tag>;
  }

  const Tag = ["h1", "h2", "h3"].includes(textStyle.format)
    ? textStyle.format
    : item.type === "heading" ? "h4" : "p";
  return <Tag className={className} dir={direction} style={style}>{item.text}</Tag>;
};

export default function ReservationFormItems({
  items,
  answers,
  errors,
  disabled,
  availableDates = [],
  timeSlots = [],
  timeSlotsByDate,
  weeklyRepeatDates,
  selectedDate = "",
  selectedTime = "",
  slotError = "",
  lang = "en",
  onSelectSlot,
  onChange,
}) {
  const content = getReservationContent(lang);
  const toggleCheckbox = (itemId, option, checked) => {
    const current = Array.isArray(answers[itemId]) ? answers[itemId] : [];
    onChange(
      itemId,
      checked
        ? [...new Set([...current, option])]
        : current.filter((value) => value !== option)
    );
  };

  return (
    <div className="reservation-custom-form reservation-layout-grid" dir={String(lang).startsWith("ar") ? "rtl" : "ltr"} data-testid="reservation-custom-form">
      {items.map((item) => {
        const renderItem = () => {
        const direction = item.direction === "rtl" ? "rtl" : "ltr";
        if (item.type === "divider") return <div className="reservation-component-divider" role="separator" aria-orientation="horizontal" key={item.id} />;
        if (item.type === "heading") return <div className="reservation-custom-text-component" key={item.id}>{renderFormattedText(item, "reservation-custom-heading")}</div>;
        if (item.type === "paragraph") return <div className="reservation-custom-text-component" key={item.id}>{renderFormattedText(item, "reservation-custom-paragraph")}</div>;
        if (item.type === "availability") return (
          <section className="reservation-custom-availability" dir={direction} key={item.id}>
            <h4>{item.label}</h4>
            <FixedSlotPicker dates={availableDates} times={timeSlots} timesByDate={timeSlotsByDate} weeklyRepeatDates={weeklyRepeatDates} selectedDate={selectedDate} selectedTime={selectedTime} disabled={disabled} error={slotError} lang={lang} direction={direction} onSelect={onSelectSlot} />
          </section>
        );
        if (["text", "email", "phone"].includes(item.type)) {
          return (
            <label dir={direction} className={`reservation-field reservation-custom-field ${errors[item.id] ? "has-error" : ""}`} key={item.id}>
              {item.label}{item.required ? " *" : ""}
              <DateTimeInput lang={lang}
                type={item.type === "text" ? "text" : item.type}
                dir={direction}
                inputMode={item.type === "phone" ? "tel" : undefined}
                autoComplete={item.type === "email" ? "email" : item.type === "phone" ? "tel" : undefined}
                required={Boolean(item.required)}
                value={answers[item.id] || ""}
                placeholder={item.placeholder || ""}
                disabled={disabled}
                onChange={(event) => onChange(item.id, event.target.value)}
              />
              {item.type === "phone" && !errors[item.id] && <small>{content.phoneHelper}</small>}
              {errors[item.id] && <strong>{errors[item.id]}</strong>}
            </label>
          );
        }
        if (item.type === "checkbox" || item.type === "radio") {
          return (
            <fieldset dir={direction} className={`reservation-choice-field ${errors[item.id] ? "has-error" : ""}`} key={item.id}>
              <legend>{item.label}{item.required ? " *" : ""}</legend>
              <div className="reservation-choice-options">
                {item.options.map((option) => (
                  <label key={option}>
                    <DateTimeInput lang={lang}
                      type={item.type}
                      name={item.type === "radio" ? `reservation_${item.id}` : undefined}
                      value={option}
                      checked={item.type === "checkbox"
                        ? (answers[item.id] || []).includes(option)
                        : answers[item.id] === option}
                      disabled={disabled}
                      onChange={(event) => item.type === "checkbox"
                        ? toggleCheckbox(item.id, option, event.target.checked)
                        : onChange(item.id, option)}
                    />
                    <span>{item.optionLabels?.[option] || option}</span>
                  </label>
                ))}
              </div>

              {errors[item.id] && <strong>{errors[item.id]}</strong>}
            </fieldset>
          );
        }
        if (item.type === "button") {
          return (
            <button type="submit" dir={direction} className="reservation-submit reservation-custom-submit" disabled={disabled} key={item.id}>
              {item.label}
            </button>
          );
        }
        return null;
        };
        const component = renderItem();
        return component && cloneElement(component, { className: `${component.props.className || ""} reservation-layout-item`, style: { ...component.props.style, ...getReservationLayoutStyle(item) } });
      })}
    </div>
  );
}
