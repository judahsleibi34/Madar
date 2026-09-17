import FixedSlotPicker from "./FixedSlotPicker";
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
  selectedDate = "",
  selectedTime = "",
  slotError = "",
  lang = "en",
  onSelectSlot,
  onChange,
}) {
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
    <div className="reservation-custom-form" data-testid="reservation-custom-form">
      {items.map((item) => {
        const direction = item.direction === "rtl" ? "rtl" : "ltr";
        if (item.type === "heading") return <div className="reservation-custom-text-component" key={item.id}>{renderFormattedText(item, "reservation-custom-heading")}</div>;
        if (item.type === "paragraph") return <div className="reservation-custom-text-component" key={item.id}>{renderFormattedText(item, "reservation-custom-paragraph")}</div>;
        if (item.type === "availability") return (
          <section className="reservation-custom-availability" dir={direction} key={item.id}>
            <h4>{item.label}</h4>
            <FixedSlotPicker dates={availableDates} times={timeSlots} timesByDate={timeSlotsByDate} selectedDate={selectedDate} selectedTime={selectedTime} disabled={disabled} error={slotError} lang={lang} direction={direction} onSelect={onSelectSlot} />
          </section>
        );
        if (["text", "email", "phone"].includes(item.type)) {
          return (
            <label dir={direction} className={`reservation-field reservation-custom-field ${errors[item.id] ? "has-error" : ""}`} key={item.id}>
              {item.label}{item.required ? " *" : ""}
              <input
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
              {item.type === "phone" && !errors[item.id] && <small>Palestinian (+970) or Israeli (+972) numbers only.</small>}
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
                    <input
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
                    <span>{option}</span>
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
      })}
    </div>
  );
}