import { useEffect, useMemo, useRef, useState } from "react";
import { getReservationContent } from "../../../content/pageBuilder";
import { createReservationIdempotencyKey } from "../runtime/reservationSubmission";
import FixedSlotPicker from "./FixedSlotPicker";
import ReservationFormItems from "./ReservationFormItems";
import { normalizeReservationFormItems, reservationFormItemNeedsAnswer } from "./reservationForm";
import "./ReservationBlock.css";

const reservationDefaults = getReservationContent("en");
const defaultServices = reservationDefaults.defaultServices;
const defaultFields = reservationDefaults.defaultFields;
const requiredFields = reservationDefaults.requiredFields;

const initialValues = (service) => ({
  name: "",
  contact: "",
  email: "",
  phone: "",
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

  return Array.isArray(services) ? cleanServices : defaultServices;
};

export default function ReservationBlock({
  title = reservationDefaults.title,
  description = reservationDefaults.description,
  services,
  fields,
  formItems,
  bookingMode = "flexible",
  availableDates = [],
  timeSlots = [],
  timeSlotsByDate,
  disabled = false,
  submitLabel = reservationDefaults.submitLabel,
  lang = "en",
  onSubmit,
}) {
  const content = getReservationContent(lang);
  const fieldMeta = content.fieldMeta;
  const serviceOptions = useMemo(() => normalizeServices(services), [services]);
  const isFixedSlots = bookingMode !== "flexible";
  const normalizedFormItems = useMemo(() => normalizeReservationFormItems(formItems), [formItems]);
  const hasCustomSubmit = normalizedFormItems.some((item) => item.type === "button");
  const hasCustomComposition = normalizedFormItems.length > 0;
  const hasAvailabilityComponent = normalizedFormItems.some((item) => item.type === "availability");
  const enabledFields = useMemo(
    () => Array.isArray(fields)
      ? fields
      : defaultFields.filter((key) => isFixedSlots || !["service", "guests"].includes(key)),
    [fields, isFixedSlots]
  );
  const hasContactFields = ["name", "contact"].some((key) => enabledFields.includes(key));
  const hasScheduleFields = ["date", "time"].some((key) => enabledFields.includes(key));
  const [values, setValues] = useState(() => initialValues(serviceOptions[0]));
  const [errors, setErrors] = useState({});
  const [customAnswers, setCustomAnswers] = useState({});
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

  const updateCustomAnswer = (itemId, value) => {
    setCustomAnswers((prev) => ({ ...prev, [itemId]: value }));
    setErrors((prev) => {
      const next = { ...prev };
      delete next[itemId];
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
    (hasCustomComposition
      ? (hasAvailabilityComponent ? ["date", "time"] : [])
      : isFixedSlots
        ? ["name", "email", "phone", "date", "time"]
        : requiredFields.filter((key) => enabledFields.includes(key)))
      .filter((key) => key !== "service" || serviceOptions.length > 0)
      .forEach((key) => {
        if (!String(values[key] || "").trim()) {
          nextErrors[key] = content.required;
        }
      });

    normalizedFormItems.forEach((item) => {
      if (reservationFormItemNeedsAnswer(item, customAnswers[item.id])) {
        nextErrors[item.id] = content.required;
      }
    });

    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    setIsSubmitting(true);

    try {
      const submitted = await onSubmit?.({
        ...values,
        ...(isFixedSlots ? { contact: values.phone } : {}),
        guests: Number(values.guests) || 1,
        ...(normalizedFormItems.length > 0 ? { customAnswers } : {}),
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
        setCustomAnswers({});
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
    if (key === "service" && serviceOptions.length === 0) return null;

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
    <form className={`reservation-block ${isFixedSlots ? "is-fixed-slots" : "is-date-request"} ${hasCustomComposition ? "has-custom-composition" : ""}`} onSubmit={submitReservation}>
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
      {!hasCustomComposition && (
        <div className="reservation-block-header">
          <div>
          {isFixedSlots && <span>Book an appointment</span>}
          <h3>{title}</h3>
          <p>{description}</p>
        </div>

        </div>
      )}

      {isFixedSlots && !hasCustomComposition && !hasAvailabilityComponent && (
        <FixedSlotPicker
          dates={availableDates}
          times={timeSlots}
          timesByDate={timeSlotsByDate}
          selectedDate={values.date}
          selectedTime={values.time}
          disabled={submissionDisabled}
          error={errors.date || errors.time || ""}
          lang={lang}
          onSelect={selectFixedSlot}
        />
      )}

      {!hasCustomComposition && (isFixedSlots ? (
        <div className="reservation-grid fixed-slot-contact-grid">
          <label className={`reservation-field reservation-field-name ${errors.name ? "has-error" : ""}`}>
            Full name *
            <input
              value={values.name}
              disabled={submissionDisabled}
              placeholder="Enter your full name"
              onChange={(event) => updateValue("name", event.target.value)}
            />
            {errors.name && <strong>{errors.name}</strong>}
          </label>
          <label className={`reservation-field reservation-field-email ${errors.email ? "has-error" : ""}`}>
            Email address *
            <input
              type="email"
              value={values.email}
              disabled={submissionDisabled}
              placeholder="you@example.com"
              onChange={(event) => updateValue("email", event.target.value)}
            />
            {errors.email && <strong>{errors.email}</strong>}
          </label>
          <label className={`reservation-field reservation-field-phone ${errors.phone ? "has-error" : ""}`}>
            Phone number *
            <input
              type="tel"
              value={values.phone}
              disabled={submissionDisabled}
              placeholder="+1 555 123 4567"
              onChange={(event) => updateValue("phone", event.target.value)}
            />
            {errors.phone && <strong>{errors.phone}</strong>}
          </label>
          {renderField("notes")}
        </div>
      ) : (
        <div className="reservation-request-form">
          {hasContactFields && <section className="reservation-request-section">
            <div className="reservation-request-heading">
              <h4>Your details</h4>
              <p>Tell us how to contact you.</p>
            </div>
            <div className="reservation-request-grid reservation-request-contact">
              {renderField("name")}
              {renderField("contact")}
            </div>
          </section>}

          {hasScheduleFields && <section className="reservation-request-section">
            <div className="reservation-request-heading">
              <h4>Appointment details</h4>
              <p>Choose when you prefer to visit.</p>
            </div>
            <div className="reservation-request-grid reservation-request-schedule">
              {renderField("date")}
              {renderField("time")}
            </div>
          </section>}

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
      ))}

      {normalizedFormItems.length > 0 && (
        <ReservationFormItems
          items={normalizedFormItems}
          answers={customAnswers}
          errors={errors}
          disabled={submissionDisabled}
          availableDates={availableDates}
          timeSlots={timeSlots}
          timeSlotsByDate={timeSlotsByDate}
          selectedDate={values.date}
          selectedTime={values.time}
          slotError={errors.date || errors.time || ""}
          lang={lang}
          onSelectSlot={selectFixedSlot}
          onChange={updateCustomAnswer}
        />
      )}

      {!hasCustomComposition && (
        <div className="reservation-footer">
          {!hasCustomSubmit && (
            <button type="submit" className="reservation-submit" disabled={submissionDisabled}>
              {submitLabel}
            </button>
          )}
          {disabled && <p className="reservation-helper">{content.disabledHelper}</p>}
        </div>
      )}
    </form>
  );
}
