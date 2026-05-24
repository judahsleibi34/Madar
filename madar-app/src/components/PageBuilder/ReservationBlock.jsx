import { useMemo, useState } from "react";
import "./ReservationBlock.css";

const defaultServices = ["Consultation", "Service appointment", "Table reservation"];
const defaultFields = ["name", "contact", "service", "date", "time", "guests", "notes"];
const requiredFields = ["name", "contact", "service", "date", "time"];

const fieldMeta = {
  name: { label: "Name", placeholder: "Full name" },
  contact: { label: "Contact", placeholder: "Phone or email" },
  service: { label: "Service" },
  date: { label: "Date" },
  time: { label: "Time" },
  guests: { label: "Guests" },
  notes: { label: "Notes", placeholder: "Special requests, location, or details" },
};

const initialValues = (service) => ({
  name: "",
  contact: "",
  service,
  date: "",
  time: "",
  guests: "1",
  notes: "",
});

const normalizeServices = (services) => {
  const cleanServices = (services || [])
    .map((service) => String(service || "").trim())
    .filter(Boolean);

  return cleanServices.length > 0 ? cleanServices : defaultServices;
};

export default function ReservationBlock({
  title = "Book a reservation",
  description = "Choose a service, date, and time. We will confirm availability with you.",
  services = defaultServices,
  fields = defaultFields,
  disabled = false,
  submitLabel = "Request reservation",
  onSubmit,
}) {
  const serviceOptions = useMemo(() => normalizeServices(services), [services]);
  const enabledFields = useMemo(
    () => (Array.isArray(fields) && fields.length > 0 ? fields : defaultFields),
    [fields]
  );
  const [values, setValues] = useState(() => initialValues(serviceOptions[0]));
  const [errors, setErrors] = useState({});

  const today = new Date().toISOString().slice(0, 10);

  const updateValue = (key, value) => {
    setValues((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const submitReservation = (event) => {
    event.preventDefault();

    const nextErrors = {};
    requiredFields.filter((key) => enabledFields.includes(key)).forEach((key) => {
      if (!String(values[key] || "").trim()) {
        nextErrors[key] = "Required";
      }
    });

    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    onSubmit?.({
      ...values,
      guests: Number(values.guests) || 1,
      submittedAt: new Date().toISOString(),
    });

    setValues(initialValues(serviceOptions[0]));
  };

  const renderField = (key) => {
    const meta = fieldMeta[key];
    if (!meta || !enabledFields.includes(key)) return null;

    if (key === "service") {
      return (
        <label className={`reservation-field reservation-field-${key} ${errors[key] ? "has-error" : ""}`} key={key}>
          {meta.label}
          <select
            value={values.service}
            disabled={disabled}
            onChange={(event) => updateValue("service", event.target.value)}
          >
            {serviceOptions.map((service) => (
              <option key={service} value={service}>
                {service}
              </option>
            ))}
          </select>
          {errors[key] && <strong>{errors[key]}</strong>}
        </label>
      );
    }

    if (key === "notes") {
      return (
        <label className={`reservation-field reservation-field-${key}`} key={key}>
          {meta.label}
          <textarea
            value={values.notes}
            disabled={disabled}
            placeholder={meta.placeholder}
            onChange={(event) => updateValue("notes", event.target.value)}
          />
        </label>
      );
    }

    const inputProps =
      key === "date"
        ? { type: "date", min: today }
        : key === "time"
          ? { type: "time" }
          : key === "guests"
            ? { type: "number", min: "1" }
            : {};

    return (
      <label className={`reservation-field reservation-field-${key} ${errors[key] ? "has-error" : ""}`} key={key}>
        {meta.label}
        <input
          {...inputProps}
          value={values[key]}
          disabled={disabled}
          placeholder={meta.placeholder}
          onChange={(event) => updateValue(key, event.target.value)}
        />
        {errors[key] && <strong>{errors[key]}</strong>}
      </label>
    );
  };

  return (
    <form className="reservation-block" onSubmit={submitReservation}>
      <div className="reservation-block-header">
        <div>
          <span>Reservation</span>
          <h3>{title}</h3>
          <p>{description}</p>
        </div>

        <div className="reservation-summary">
          <strong>{serviceOptions.length}</strong>
          <small>Services</small>
        </div>
      </div>

      <div className="reservation-grid">
        {defaultFields.map((key) => renderField(key))}
      </div>

      <div className="reservation-footer">
        <button type="submit" className="reservation-submit" disabled={disabled}>
          {submitLabel}
        </button>

        {disabled && <p className="reservation-helper">Enable Preview to test reservations.</p>}
      </div>
    </form>
  );
}
