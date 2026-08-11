import { useEffect, useRef, useState } from "react";
import { CalendarDays, ChevronDown, ChevronLeft, ChevronRight, Clock, ListPlus, Plus, Trash2 } from "lucide-react";

const toCalendarValue = (date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const futureDateValue = (daysAhead) => {
  const date = new Date();
  date.setDate(date.getDate() + daysAhead);
  return toCalendarValue(date);
};

const fallbackReservation = {
  title: "Book an appointment",
  description: "Choose a service, date, and time. We will confirm your appointment shortly.",
  bookingMode: "restricted",
  services: ["Consultation", "Follow-up", "Project planning"],
  availableDates: [futureDateValue(1), futureDateValue(3), futureDateValue(5)],
  timeSlots: ["09:00", "10:30", "13:00", "15:30"],
  submitLabel: "Request appointment",
};

const getReservationValue = (element) => ({
  ...fallbackReservation,
  ...(element?.reservation || {}),
});

const cleanList = (items) =>
  (Array.isArray(items) ? items : [])
    .map((item) => String(item).trim())
    .filter(Boolean);

const getEditableList = (items, fallback) => {
  if (Array.isArray(items) && items.length > 0) return items;
  return fallback;
};

const formatDateLabel = (dateValue) => {
  const [year, month, day] = String(dateValue).split("-");
  if (!year || !month || !day) return dateValue;
  return new Intl.DateTimeFormat(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(Number(year), Number(month) - 1, Number(day), 12));
};

const calendarMonthFormatter = new Intl.DateTimeFormat(undefined, {
  month: "long",
  year: "numeric",
});

const calendarDayFormatter = new Intl.DateTimeFormat(undefined, {
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
});

const getCalendarMonthDays = (visibleMonth) => {
  const year = visibleMonth.getFullYear();
  const month = visibleMonth.getMonth();
  const firstWeekday = new Date(year, month, 1).getDay();
  const dayCount = new Date(year, month + 1, 0).getDate();
  return [
    ...Array.from({ length: firstWeekday }, () => null),
    ...Array.from({ length: dayCount }, (_, index) => new Date(year, month, index + 1, 12)),
  ];
};

function ReservationDatePicker({ availableDates, onSelect }) {
  const [isOpen, setIsOpen] = useState(false);
  const [visibleMonth, setVisibleMonth] = useState(() => new Date());
  const pickerRef = useRef(null);
  const todayValue = toCalendarValue(new Date());
  const monthDays = getCalendarMonthDays(visibleMonth);

  useEffect(() => {
    if (!isOpen) return undefined;

    const closeOnOutsideClick = (event) => {
      if (!pickerRef.current?.contains(event.target)) setIsOpen(false);
    };
    const closeOnEscape = (event) => {
      if (event.key === "Escape") setIsOpen(false);
    };

    document.addEventListener("pointerdown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [isOpen]);

  const changeMonth = (offset) => {
    setVisibleMonth((current) => new Date(current.getFullYear(), current.getMonth() + offset, 1, 12));
  };

  const showToday = () => {
    const today = new Date();
    setVisibleMonth(new Date(today.getFullYear(), today.getMonth(), 1, 12));
  };

  return (
    <div className="reservation-calendar-picker" ref={pickerRef}>
      <button
        type="button"
        className="reservation-calendar-trigger"
        aria-haspopup="dialog"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((current) => !current)}
      >
        <span className="reservation-calendar-trigger-icon" aria-hidden="true">
          <CalendarDays size={18} />
        </span>
        <span>
          <small>Choose a date</small>
          <strong>Open calendar</strong>
        </span>
        <ChevronDown size={17} aria-hidden="true" />
      </button>

      {isOpen && (
        <div className="reservation-calendar-popover" role="dialog" aria-label="Choose an available date">
          <div className="reservation-calendar-toolbar">
            <strong>{calendarMonthFormatter.format(visibleMonth)}</strong>
            <div>
              <button type="button" aria-label="Previous month" onClick={() => changeMonth(-1)}>
                <ChevronLeft size={17} aria-hidden="true" />
              </button>
              <button type="button" aria-label="Next month" onClick={() => changeMonth(1)}>
                <ChevronRight size={17} aria-hidden="true" />
              </button>
            </div>
          </div>
          <div className="reservation-calendar-weekdays" aria-hidden="true">
            {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((day) => <span key={day}>{day}</span>)}
          </div>
          <div className="reservation-calendar-days" role="grid">
            {monthDays.map((date, index) => {
              if (!date) return <span className="is-empty" key={`empty_${index}`} />;
              const dateValue = toCalendarValue(date);
              const isSelected = availableDates.includes(dateValue);
              return (
                <button
                  type="button"
                  key={dateValue}
                  className={`${dateValue === todayValue ? "is-today" : ""} ${isSelected ? "is-selected" : ""}`.trim()}
                  aria-label={calendarDayFormatter.format(date)}
                  aria-pressed={isSelected}
                  disabled={isSelected}
                  onClick={() => {
                    onSelect(dateValue);
                    setIsOpen(false);
                  }}
                >
                  {date.getDate()}
                </button>
              );
            })}
          </div>
          <div className="reservation-calendar-footer">
            <button type="button" onClick={showToday}>Today</button>
            <button type="button" onClick={() => setIsOpen(false)}>Close</button>
          </div>
        </div>
      )}
    </div>
  );
}
export default function ReservationsTab({
  reservationBlocks,
  activeReservationId,
  onAddReservationBlock,
  onSelectReservationBlock,
  onUpdateReservationBlock,
  onDeleteReservationBlock,
}) {
  const activeItem =
    reservationBlocks.find((item) => item.element.id === activeReservationId) ||
    reservationBlocks[0] ||
    null;
  const activeElement = activeItem?.element || null;
  const reservation = getReservationValue(activeElement);

  const updateReservation = (updates) => {
    if (!activeElement) return;
    onUpdateReservationBlock(activeElement.id, {
      reservation: {
        ...(activeElement.reservation || {}),
        ...updates,
      },
    });
  };

  const updateReservationListItem = (key, index, value) => {
    const fallback = key === "timeSlots" ? fallbackReservation.timeSlots : fallbackReservation.services;
    const current = getEditableList(reservation[key], fallback);
    updateReservation({
      [key]: current.map((item, itemIndex) => (itemIndex === index ? value : item)),
    });
  };

  const addReservationListItem = (key, value) => {
    const fallback = key === "timeSlots" ? fallbackReservation.timeSlots : fallbackReservation.services;
    const current = getEditableList(reservation[key], fallback);
    updateReservation({ [key]: [...current, value] });
  };

  const removeReservationListItem = (key, index) => {
    const fallback = key === "timeSlots" ? fallbackReservation.timeSlots : fallbackReservation.services;
    const current = getEditableList(reservation[key], fallback);
    updateReservation({ [key]: current.filter((_, itemIndex) => itemIndex !== index) });
  };

  const cleanReservationList = (key) => {
    updateReservation({ [key]: cleanList(reservation[key]) });
  };

  const services = getEditableList(reservation.services, fallbackReservation.services);
  const availableDates = getEditableList(reservation.availableDates, fallbackReservation.availableDates);
  const timeSlots = getEditableList(reservation.timeSlots, fallbackReservation.timeSlots);
  const isRestricted = reservation.bookingMode !== "flexible";
  const [stepSelection, setStepSelection] = useState({ reservationId: "", step: "details" });
  const selectedReservationId = String(activeElement?.id || "");
  const selectedStep = stepSelection.reservationId === selectedReservationId
    ? stepSelection.step
    : "details";
  const activeStep = selectedStep === "services" || (!isRestricted && selectedStep === "availability")
    ? "details"
    : selectedStep;
  const setActiveStep = (step) => {
    setStepSelection({ reservationId: selectedReservationId, step });
  };
  const reservationSteps = [
    { id: "details", label: "Details", helper: "Name and public text" },
    ...(isRestricted
      ? [{ id: "availability", label: "Availability", helper: "Dates and time slots" }]
      : []),
  ];
  const activeStepIndex = Math.max(
    0,
    reservationSteps.findIndex((step) => step.id === activeStep)
  );

  const nextBlockNumber = reservationBlocks.length + 1;
  const addFlexibleBlock = () =>
    onAddReservationBlock({
      name: reservationBlocks.length > 0 ? `Visitor date request ${nextBlockNumber}` : "Visitor date request",
      reservation: {
        ...fallbackReservation,
        title: "Request an appointment",
        description: "Choose the service, date, and time that works for you.",
        bookingMode: "flexible",
        submitLabel: "Send request",
      },
    });
  const addFixedBlock = () =>
    onAddReservationBlock({
      name: reservationBlocks.length > 0 ? `Fixed appointment slots ${nextBlockNumber}` : "Fixed appointment slots",
      reservation: {
        ...fallbackReservation,
        title: "Book an available slot",
        description: "Choose one of the available dates and times.",
        bookingMode: "restricted",
        submitLabel: "Book slot",
      },
    });

  return (
    <main className="workspace-page reservations-workspace">
      <header className="workspace-header reservations-header">
        <div>
          <span className="workspace-kicker">Reservation builder</span>
          <h1>Reservations</h1>
          <p>Set what visitors can book, when they can book it, and how the booking form appears.</p>
        </div>
      </header>


      <div className="reservation-editor-layout">
        <aside className="object-list reservation-block-list" aria-label="Reservation blocks">
          <div className="reservation-panel-heading">
            <div>
              <span className="workspace-kicker">Library</span>
              <h2>Reservation blocks</h2>
            </div>
            <span className="reservation-count">{reservationBlocks.length}</span>
          </div>
          {reservationBlocks.length > 0 && (
            <div className="reservation-library-actions" aria-label="Add reservation block">
              <button type="button" onClick={addFlexibleBlock}>
                <Plus size={15} aria-hidden="true" />
                Date request
              </button>
              <button type="button" onClick={addFixedBlock}>
                <CalendarDays size={15} aria-hidden="true" />
                Fixed slots
              </button>
            </div>
          )}
          {activeElement && (
            <div className="reservation-summary">
              <strong>{services.length} services</strong>
              <span>
                {isRestricted
                  ? `${availableDates.length} dates / ${timeSlots.length} times`
                  : "Visitor chooses date and time"}
              </span>
            </div>
          )}
          {reservationBlocks.length === 0 && (
            <div className="reservation-empty-list">
              <CalendarDays size={20} aria-hidden="true" />
              <p>No reservation blocks yet.</p>
            </div>
          )}
          {reservationBlocks.map((item) => (
            <button
              type="button"
              key={item.element.id}
              className={`reservation-list-item ${activeItem?.element.id === item.element.id ? "is-active" : ""}`}
              onClick={() => onSelectReservationBlock(item.element.id, item.page.id)}
            >
              <strong>{item.element.name || item.element.reservation?.title || "Reservation block"}</strong>
              <span>{item.page.name} / {item.section.name}</span>
            </button>
          ))}
        </aside>

        <section className={`form-editor reservation-editor-card ${activeElement ? (isRestricted ? "is-restricted" : "is-flexible") : "is-empty"}`}>
          {activeElement ? (
            <>
              <div className="editor-card-header">
                <div>
                  <span className="workspace-kicker">Setup</span>
                  <h2>Configure booking block</h2>
                </div>
                <div className="reservation-editor-actions">
                  <button
                    type="button"
                    className="reservation-delete-block"
                    onClick={() => onDeleteReservationBlock(activeElement.id, activeItem.page.id)}
                  >
                    <Trash2 size={16} aria-hidden="true" />
                    Delete block
                  </button>
                </div>
              </div>

              <nav className="reservation-setup-steps" aria-label="Reservation setup steps">
                {reservationSteps.map((step, index) => (
                  <button
                    type="button"
                    key={step.id}
                    className={activeStep === step.id ? "is-active" : ""}
                    aria-current={activeStep === step.id ? "step" : undefined}
                    onClick={() => setActiveStep(step.id)}
                  >
                    <span>{index + 1}</span>
                    <div>
                      <strong>{step.label}</strong>
                      <small>{step.helper}</small>
                    </div>
                  </button>
                ))}
              </nav>

              {activeStep === "details" && (
                <>
                  <div className="reservation-settings-section reservation-copy-section">
                <div>
                  <span className="workspace-kicker">Booking details</span>
                  <h3>{activeElement.name || "Reservation block"}</h3>
                  <p>What visitors will see</p>
                </div>
                <div className="reservation-copy-grid">
                  <label>
                    Reservation name
                    <input
                      value={activeElement.name || ""}
                      onChange={(event) => onUpdateReservationBlock(activeElement.id, { name: event.target.value })}
                    />
                  </label>
                  <label>
                    Booking page heading
                    <input
                      value={reservation.title}
                      onChange={(event) => updateReservation({ title: event.target.value })}
                    />
                  </label>
                  <label className="reservation-wide-field">
                    Instructions for visitors
                    <textarea
                      value={reservation.description}
                      onChange={(event) => updateReservation({ description: event.target.value })}
                    />
                  </label>
                  <label>
                    Booking button label
                    <input
                      value={reservation.submitLabel}
                      onChange={(event) => updateReservation({ submitLabel: event.target.value })}
                    />
                  </label>
                </div>
              </div>


                </>
              )}

              {activeStep === "availability" && isRestricted && (
                <div className="reservation-settings-section reservation-schedule-section reservation-date-section">
                  <div className="reservation-date-heading">
                    <span className="reservation-date-heading-icon" aria-hidden="true">
                      <CalendarDays size={20} />
                    </span>
                    <div>
                      <span className="workspace-kicker">Calendar</span>
                      <h3>Available dates</h3>
                      <p>Choose the days visitors can book.</p>
                    </div>
                  </div>
                  <ReservationDatePicker
                    availableDates={availableDates}
                    onSelect={(nextDate) => {
                      if (availableDates.includes(nextDate)) return;
                      updateReservation({ availableDates: [...availableDates, nextDate].sort() });
                    }}
                  />
                  <div className="reservation-date-picker-grid" aria-label="Selected available dates">
                    {availableDates.length > 0 ? availableDates.map((date) => (
                      <div className="reservation-date-card" key={date}>
                        <span className="reservation-date-card-icon" aria-hidden="true">
                          <CalendarDays size={17} />
                        </span>
                        <div>
                          <small>Available</small>
                          <strong>{formatDateLabel(date)}</strong>
                        </div>
                        <button
                          type="button"
                          aria-label={`Remove ${formatDateLabel(date)}`}
                          onClick={() =>
                            updateReservation({
                              availableDates: availableDates.filter((item) => item !== date),
                            })
                          }
                        >
                          <Trash2 size={14} aria-hidden="true" />
                        </button>
                      </div>
                    )) : (
                      <p className="reservation-date-empty">No available dates added yet.</p>
                    )}
                  </div>
                </div>
              )}
              {activeStep === "availability" && isRestricted && (
                <div className="reservation-settings-section reservation-schedule-section">
                <div className="reservation-list-heading">
                  <div>
                    <span className="workspace-kicker">Schedule</span>
                    <h3>Time slots</h3>
                  </div>
                  <button type="button" onClick={() => addReservationListItem("timeSlots", "16:30")}>
                    <Plus size={15} aria-hidden="true" />
                    Add time
                  </button>
                </div>
                <div className="reservation-bullet-editor reservation-time-editor">
                  {timeSlots.map((slot, index) => (
                    <div className="reservation-bullet-row" key={`slot_${index}`}>
                      <Clock size={15} aria-hidden="true" />
                      <input
                        type="time"
                        value={slot}
                        placeholder="09:00"
                        onBlur={() => cleanReservationList("timeSlots")}
                        onChange={(event) => updateReservationListItem("timeSlots", index, event.target.value)}
                      />
                      <button
                        type="button"
                        aria-label="Remove time slot"
                        disabled={timeSlots.length <= 1}
                        onClick={() => removeReservationListItem("timeSlots", index)}
                      >
                        <Trash2 size={15} aria-hidden="true" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
              )}

              <footer className="reservation-step-actions">
                <button
                  type="button"
                  disabled={activeStepIndex === 0}
                  onClick={() => setActiveStep(reservationSteps[activeStepIndex - 1]?.id || "details")}
                >
                  Back
                </button>
                <span>Changes save automatically</span>
                {activeStepIndex < reservationSteps.length - 1 && (
                  <button
                    type="button"
                    className="primary-action"
                    onClick={() => setActiveStep(reservationSteps[activeStepIndex + 1].id)}
                  >
                    Continue
                  </button>
                )}
              </footer>
            </>
          ) : (
            <div className="reservation-editor-empty">
              <div className="reservation-empty-icon" aria-hidden="true">
                <ListPlus size={24} />
              </div>
              <div className="reservation-empty-copy">
                <span className="workspace-kicker">Start here</span>
                <h2>Create your first reservation block</h2>
                <p>Pick the booking style that matches how you want to handle appointments.</p>
              </div>
              <div className="reservation-empty-actions">
                <button type="button" className="primary-action" onClick={addFlexibleBlock}>
                  <Plus size={16} aria-hidden="true" />
                  <span>
                    <strong>Visitor date request</strong>
                    <small>Visitors suggest a date and time.</small>
                  </span>
                </button>
                <button type="button" onClick={addFixedBlock}>
                  <CalendarDays size={16} aria-hidden="true" />
                  <span>
                    <strong>Fixed slots</strong>
                    <small>Visitors choose from your schedule.</small>
                  </span>
                </button>
              </div>
            </div>
          )}
        </section>

      </div>
    </main>
  );
}
