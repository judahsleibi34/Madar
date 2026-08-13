import { useEffect, useRef, useState } from "react";
import { CalendarDays, ChevronDown, ChevronLeft, ChevronRight, Clock, CopyPlus, ListPlus, Plus, Trash2 } from "lucide-react";
import ReservationBlockBuilder from "./ReservationBlockBuilder";
import { createReservationFormItem } from "../blocks/reservationForm";
import { countConfiguredSlots, flattenTimeSlotsByDate, normalizeTimeSlotsByDate } from "../blocks/reservationAvailability";

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
  formItems: [],
};

const getReservationValue = (element) => ({
  ...fallbackReservation,
  ...(element?.reservation || {}),
});
const createDefaultBookingComponents = ({ title, description, submitLabel, includeAvailability = false }) => [
  createReservationFormItem("heading", { text: title }),
  createReservationFormItem("paragraph", { text: description }),
  ...(includeAvailability ? [createReservationFormItem("availability")] : []),
  createReservationFormItem("button", { label: submitLabel }),
];

const getBookingComponents = (element, reservation) => {
  if (Array.isArray(element?.reservation?.formItems)) return reservation.formItems;
  const legacyId = String(element?.id || "reservation");
  return [
    createReservationFormItem("heading", { id: `${legacyId}_heading`, text: reservation.title }),
    createReservationFormItem("paragraph", { id: `${legacyId}_instructions`, text: reservation.description }),
    createReservationFormItem("button", { id: `${legacyId}_submit`, label: reservation.submitLabel }),
  ];
};

const cleanList = (items) =>
  (Array.isArray(items) ? items : [])
    .map((item) => String(item).trim())
    .filter(Boolean);

const getEditableList = (items, fallback) => {
  if (Array.isArray(items) && items.length > 0) return items;
  return fallback;
};

const getNextTimeSlot = (currentTimes) => {
  const used = new Set(cleanList(currentTimes));
  for (let hour = 9; hour <= 20; hour += 1) {
    for (const minutes of ["00", "30"]) {
      const candidate = `${String(hour).padStart(2, "0")}:${minutes}`;
      if (!used.has(candidate)) return candidate;
    }
  }
  return "21:00";
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
  const availableDates = Array.isArray(reservation.availableDates)
    ? cleanList(reservation.availableDates).sort()
    : fallbackReservation.availableDates;
  const timeSlotsByDate = normalizeTimeSlotsByDate(
    availableDates,
    reservation.timeSlots || fallbackReservation.timeSlots,
    reservation.timeSlotsByDate
  );
  const timeSlots = flattenTimeSlotsByDate(timeSlotsByDate);
  const configuredSlotCount = countConfiguredSlots(timeSlotsByDate);
  const isRestricted = reservation.bookingMode !== "flexible";
  const [availabilityDateSelection, setAvailabilityDateSelection] = useState({ reservationId: "", date: "" });
  const selectedAvailabilityDate = availabilityDateSelection.reservationId === String(activeElement?.id || "")
    && availableDates.includes(availabilityDateSelection.date)
    ? availabilityDateSelection.date
    : availableDates[0] || "";
  const selectedDateTimes = timeSlotsByDate[selectedAvailabilityDate] || [];

  const saveTimeSlotsByDate = (nextMap) => {
    updateReservation({
      timeSlotsByDate: nextMap,
      timeSlots: flattenTimeSlotsByDate(nextMap),
    });
  };

  const [stepSelection, setStepSelection] = useState({ reservationId: "", step: "" });
  const selectedReservationId = String(activeElement?.id || "");
  const selectedStep = stepSelection.reservationId === selectedReservationId
    ? stepSelection.step
    : (isRestricted ? "availability" : "layout");
  const activeStep = ["details", "services"].includes(selectedStep) || (!isRestricted && selectedStep === "availability")
    ? "layout"
    : selectedStep;
  const setActiveStep = (step) => {
    setStepSelection({ reservationId: selectedReservationId, step });
  };
  const reservationSteps = [
    ...(isRestricted
      ? [{ id: "availability", label: "Availability", helper: "Dates and time slots" }]
      : []),
    { id: "layout", label: "Builder", helper: "Design the booking element" },
  ];
  const bookingComponents = getBookingComponents(activeElement, reservation);
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
        formItems: createDefaultBookingComponents({
          title: "Request an appointment",
          description: "Choose the service, date, and time that works for you.",
          submitLabel: "Send request",
        }),
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
        formItems: createDefaultBookingComponents({
          title: "Book an available slot",
          description: "Choose one of the available dates and times.",
          submitLabel: "Book slot",
          includeAvailability: true,
        }),
      },
    });

  const saveAsNewBuild = () => {
    if (!activeElement) return;
    const formItems = bookingComponents.map(({ id: _id, ...item }) =>
      createReservationFormItem(item.type, {
        ...item,
        options: Array.isArray(item.options) ? [...item.options] : item.options,
        textStyle: item.textStyle ? { ...item.textStyle } : item.textStyle,
      })
    );
    const copiedTimeSlotsByDate = Object.fromEntries(
      Object.entries(timeSlotsByDate).map(([date, slots]) => [date, [...slots]])
    );
    onAddReservationBlock({
      name: `${activeElement.name || reservation.title || "Reservation build"} copy ${nextBlockNumber}`,
      reservation: {
        ...reservation,
        services: [...services],
        availableDates: [...availableDates],
        timeSlots: [...timeSlots],
        timeSlotsByDate: copiedTimeSlotsByDate,
        formItems,
      },
    });
  };
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
              <h2>Saved builds</h2>
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
                  ? `${availableDates.length} dates / ${configuredSlotCount} slots`
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
                  <label className="reservation-build-name">
                    <span>Build name</span>
                    <input
                      aria-label="Reservation build name"
                      value={activeElement.name || ""}
                      onChange={(event) => onUpdateReservationBlock(activeElement.id, { name: event.target.value })}
                    />
                  </label>
                </div>
                <div className="reservation-editor-actions">
                  <button type="button" onClick={saveAsNewBuild}>
                    <CopyPlus size={16} aria-hidden="true" />
                    Save as new build
                  </button>
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

              {activeStep === "layout" && (
                <div className="reservation-settings-section reservation-block-builder-section">
                  <div className="reservation-block-builder-section-heading">
                    <div>
                      <span className="workspace-kicker">Booking builder</span>
                      <h3>Design your booking block</h3>
                      <p>Add components, arrange them, and edit the selected item.</p>
                    </div>
                    <span>{bookingComponents.length} components</span>
                  </div>
                  <ReservationBlockBuilder
                    items={bookingComponents}
                    availableDates={availableDates}
                    timeSlots={timeSlots}
                    timeSlotsByDate={timeSlotsByDate}
                    allowAvailability={isRestricted}
                    onChange={(formItems) => updateReservation({ formItems })}
                  />
                </div>
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
                      if (availableDates.includes(nextDate)) {
                        setAvailabilityDateSelection({ reservationId: selectedReservationId, date: nextDate });
                        return;
                      }
                      const nextDates = [...availableDates, nextDate].sort();
                      const nextMap = { ...timeSlotsByDate, [nextDate]: [] };
                      updateReservation({
                        availableDates: nextDates,
                        timeSlotsByDate: nextMap,
                        timeSlots: flattenTimeSlotsByDate(nextMap),
                      });
                      setAvailabilityDateSelection({ reservationId: selectedReservationId, date: nextDate });
                    }}
                  />
                  <div className="reservation-date-picker-grid" aria-label="Selected available dates">
                    {availableDates.length > 0 ? availableDates.map((date) => (
                      <div className={`reservation-date-card ${selectedAvailabilityDate === date ? "is-selected" : ""}`} key={date}>
                        <button
                          type="button"
                          className="reservation-date-select"
                          aria-pressed={selectedAvailabilityDate === date}
                          onClick={() => setAvailabilityDateSelection({ reservationId: selectedReservationId, date })}
                        >
                          <span className="reservation-date-card-icon" aria-hidden="true">
                            <CalendarDays size={17} />
                          </span>
                          <span>
                            <small>{selectedAvailabilityDate === date ? "Editing times" : "Available"}</small>
                            <strong>{formatDateLabel(date)}</strong>
                          </span>
                        </button>
                        <button
                          type="button"
                          aria-label={`Remove ${formatDateLabel(date)}`}
                          onClick={() => {
                            const nextDates = availableDates.filter((item) => item !== date);
                            const nextMap = { ...timeSlotsByDate };
                            delete nextMap[date];
                            updateReservation({
                              availableDates: nextDates,
                              timeSlotsByDate: nextMap,
                              timeSlots: flattenTimeSlotsByDate(nextMap),
                            });
                          }}
                        >
                          <Trash2 size={14} aria-hidden="true" />
                        </button>
                      </div>
                    )) : (
                      <p className="reservation-date-empty">Add a date, then give it its own available times.</p>
                    )}
                  </div>
                </div>
              )}
              {activeStep === "availability" && isRestricted && (
                <div className="reservation-settings-section reservation-schedule-section">
                  <div className="reservation-list-heading">
                    <div>
                      <span className="workspace-kicker">Schedule</span>
                      <h3>{selectedAvailabilityDate ? `Times for ${formatDateLabel(selectedAvailabilityDate)}` : "Choose a date first"}</h3>
                      <p>{selectedAvailabilityDate ? "These times apply only to this date." : "Add or select a date above to manage its times."}</p>
                    </div>
                    <button
                      type="button"
                      disabled={!selectedAvailabilityDate}
                      onClick={() => saveTimeSlotsByDate({
                        ...timeSlotsByDate,
                        [selectedAvailabilityDate]: [...selectedDateTimes, getNextTimeSlot(selectedDateTimes)],
                      })}
                    >
                      <Plus size={15} aria-hidden="true" />
                      Add time
                    </button>
                  </div>
                  <div className="reservation-bullet-editor reservation-time-editor">
                    {selectedAvailabilityDate && selectedDateTimes.length > 0 ? selectedDateTimes.map((slot, index) => (
                      <div className="reservation-bullet-row" key={`${selectedAvailabilityDate}_${index}`}>
                        <Clock size={15} aria-hidden="true" />
                        <input
                          type="time"
                          aria-label={`Time ${index + 1} for ${formatDateLabel(selectedAvailabilityDate)}`}
                          value={slot}
                          placeholder="09:00"
                          onBlur={() => saveTimeSlotsByDate({
                            ...timeSlotsByDate,
                            [selectedAvailabilityDate]: cleanList(selectedDateTimes),
                          })}
                          onChange={(event) => saveTimeSlotsByDate({
                            ...timeSlotsByDate,
                            [selectedAvailabilityDate]: selectedDateTimes.map((item, itemIndex) => itemIndex === index ? event.target.value : item),
                          })}
                        />
                        <button
                          type="button"
                          aria-label={`Remove time ${slot} from ${formatDateLabel(selectedAvailabilityDate)}`}
                          onClick={() => saveTimeSlotsByDate({
                            ...timeSlotsByDate,
                            [selectedAvailabilityDate]: selectedDateTimes.filter((_, itemIndex) => itemIndex !== index),
                          })}
                        >
                          <Trash2 size={15} aria-hidden="true" />
                        </button>
                      </div>
                    )) : (
                      <p className="reservation-date-empty">
                        {selectedAvailabilityDate ? "No times added for this date yet." : "No date selected."}
                      </p>
                    )}
                  </div>
                </div>
              )}

              <footer className="reservation-step-actions">
                <button
                  type="button"
                  disabled={activeStepIndex === 0}
                  onClick={() => setActiveStep(reservationSteps[activeStepIndex - 1]?.id || reservationSteps[0].id)}
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
