import { useMemo, useState } from "react";
import { getReservationContent } from "../../../content/pageBuilder";
import "./ReservationBlock.css";

const reservationDefaults = getReservationContent("en");
const defaultServices = reservationDefaults.defaultServices;
const defaultFields = reservationDefaults.defaultFields;
const requiredFields = reservationDefaults.requiredFields;

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
  title = reservationDefaults.title,
  description = reservationDefaults.description,
  services = defaultServices,
  fields = defaultFields,
  disabled = false,
  submitLabel = reservationDefaults.submitLabel,
  lang = "en",
  onSubmit,
}) {
  const content = getReservationContent(lang);
  const fieldMeta = content.fieldMeta;
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
        nextErrors[key] = content.required;
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
          <span>{content.kicker}</span>
          <h3>{title}</h3>
          <p>{description}</p>
        </div>

        <div className="reservation-summary">
          <strong>{serviceOptions.length}</strong>
          <small>{content.servicesLabel}</small>
        </div>
      </div>

      <div className="reservation-grid">
        {defaultFields.map((key) => renderField(key))}
      </div>

      <div className="reservation-footer">
        <button type="submit" className="reservation-submit" disabled={disabled}>
          {submitLabel}
        </button>

        {disabled && <p className="reservation-helper">{content.disabledHelper}</p>}
      </div>
    </form>
  );
}
