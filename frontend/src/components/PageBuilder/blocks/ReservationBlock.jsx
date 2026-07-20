import { useEffect, useMemo, useRef, useState } from "react";
import { getReservationContent } from "../../../content/pageBuilder";
import { createReservationIdempotencyKey } from "../runtime/reservationSubmission";
import FixedSlotPicker from "./FixedSlotPicker";
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
  bookingMode = "flexible",
  availableDates = [],
  timeSlots = [],
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
  const isFixedSlots = bookingMode !== "flexible";
  const [values, setValues] = useState(() => initialValues(serviceOptions[0]));
  const [errors, setErrors] = useState({});
  const [idempotencyKey, setIdempotencyKey] = useState(createReservationIdempotencyKey);
  const [honeypot, setHoneypot] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const submissionStartedAtRef = useRef(0);
  const submissionDisabled = disabled || isSubmitting;

  useEffect(() => {
    submissionStartedAtRef.current = Date.now();
  }, []);

  const today = new Date().toISOString().slice(0, 10);

  const updateValue = (key, value) => {
    setValues((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const selectFixedSlot = (date, time) => {
    setValues((prev) => ({ ...prev, date, time }));
    setErrors((prev) => {
      const next = { ...prev };
      delete next.date;
      delete next.time;
      return next;
    });
  };

  const submitReservation = async (event) => {
    event.preventDefault();

    const nextErrors = {};
    requiredFields.filter((key) => enabledFields.includes(key)).forEach((key) => {
      if (!String(values[key] || "").trim()) {
        nextErrors[key] = content.required;
      }
    });

    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    setIsSubmitting(true);

    try {
      const submitted = await onSubmit?.({
        ...values,
        guests: Number(values.guests) || 1,
      }, idempotencyKey, honeypot, Math.min(
        86_400_000,
        Math.max(0, Date.now() - submissionStartedAtRef.current)
      ));

      if (submitted === "reset_idempotency") {
        // The server confirmed this key belongs to different data. Preserve all
        // fields, but let the user's next intentional submit start a new request.
        setIdempotencyKey(createReservationIdempotencyKey());
      } else if (submitted !== false) {
        setValues(initialValues(serviceOptions[0]));
        setIdempotencyKey(createReservationIdempotencyKey());
        setHoneypot("");
        submissionStartedAtRef.current = Date.now();
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const renderField = (key) => {
    const meta = fieldMeta[key];
    if (!meta || !enabledFields.includes(key)) return null;
    if (isFixedSlots && ["date", "time", "service", "guests"].includes(key)) return null;

    if (key === "service") {
      return (
        <label className={`reservation-field reservation-field-${key} ${errors[key] ? "has-error" : ""}`} key={key}>
          {meta.label}
          <select
            value={values.service}
            disabled={submissionDisabled}
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
            disabled={submissionDisabled}
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
          disabled={submissionDisabled}
          placeholder={meta.placeholder}
          onChange={(event) => updateValue(key, event.target.value)}
        />
        {errors[key] && <strong>{errors[key]}</strong>}
      </label>
    );
  };

  return (
    <form className={`reservation-block ${isFixedSlots ? "is-fixed-slots" : "is-date-request"}`} onSubmit={submitReservation}>
      <label className="runtime-honeypot" aria-hidden="true">
        Website
        <input
          type="text"
          name="website"
          value={honeypot}
          tabIndex={-1}
          autoComplete="off"
          onChange={(event) => setHoneypot(event.target.value)}
        />
      </label>
      <div className="reservation-block-header">
        <div>
          <h3>{title}</h3>
          <p>{description}</p>
        </div>

      </div>

      {isFixedSlots && (
        <FixedSlotPicker
          dates={availableDates}
          times={timeSlots}
          selectedDate={values.date}
          selectedTime={values.time}
          disabled={submissionDisabled}
          error={errors.date || errors.time || ""}
          lang={lang}
          onSelect={selectFixedSlot}
        />
      )}

      {isFixedSlots ? (
        <div className="reservation-grid">
          {defaultFields.map((key) => renderField(key))}
        </div>
      ) : (
        <div className="reservation-request-form">
          <section className="reservation-request-section">
            <div className="reservation-request-heading">
              <h4>Your details</h4>
              <p>Tell us how to contact you.</p>
            </div>
            <div className="reservation-request-grid reservation-request-contact">
              {renderField("name")}
              {renderField("contact")}
            </div>
          </section>

          <section className="reservation-request-section">
            <div className="reservation-request-heading">
              <h4>Appointment details</h4>
              <p>Choose what you need and when you prefer to visit.</p>
            </div>
            <div className="reservation-request-grid reservation-request-schedule">
              {renderField("service")}
              {renderField("date")}
              {renderField("time")}
            </div>
          </section>

          {enabledFields.includes("notes") && (
            <section className="reservation-request-section">
              <div className="reservation-request-heading">
                <h4>Additional notes</h4>
                <p>Share anything that will help us prepare.</p>
              </div>
              <div className="reservation-request-grid reservation-request-notes">
                {renderField("notes")}
              </div>
            </section>
          )}
        </div>
      )}

      <div className="reservation-footer">
        <button type="submit" className="reservation-submit" disabled={submissionDisabled}>
          {submitLabel}
        </button>

        {disabled && <p className="reservation-helper">{content.disabledHelper}</p>}
      </div>
    </form>
  );
}
