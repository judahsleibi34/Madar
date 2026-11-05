import { useReservationEditorI18n } from "../../../utils/reservationEditorI18n";
import { useEffect, useRef, useState } from "react";
import { CalendarDays, ChevronDown, ChevronLeft, ChevronRight, Save, ListPlus, Plus, Trash2 } from "lucide-react";
import ReservationBlockBuilder from "./ReservationBlockBuilder";
import RepeatReservationTimes from "./RepeatReservationTimes";
import ReservationSessionCard from "./ReservationSessionCard";
import { createReservationFormItem } from "../blocks/reservationForm";
import { flattenTimeSlotsByDate, getReservationSession, normalizeTimeSlotsByDate, summarizeReservationSchedule } from "../blocks/reservationAvailability";

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
const createDefaultBookingComponents = ({ title, description, submitLabel, includeAvailability = false, direction = "ltr" }) => [
  createReservationFormItem("heading", { text: title }),
  createReservationFormItem("paragraph", { text: description }),
  ...(includeAvailability ? [createReservationFormItem("availability")] : []),
  createReservationFormItem("button", { label: submitLabel }),
].map(item => ({ ...item, direction, ...(["heading", "paragraph"].includes(item.type)
  ? { textStyle: { ...item.textStyle, ...(direction === "rtl" ? { fontFamily: "IBM Plex Sans Arabic" } : {}), textAlign: direction === "rtl" ? "right" : "left" } } : {}) }));

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
const formatBookingDate = (dateValue, locale) => {
  const [year, month, day] = String(dateValue).split("-");
  if (!year || !month || !day) return dateValue;
  return new Intl.DateTimeFormat(locale, {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(Number(year), Number(month) - 1, Number(day), 12));
};

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
  const { t, locale } = useReservationEditorI18n();
  const calendarMonthFormatter = new Intl.DateTimeFormat(locale, { month: "long", year: "numeric" });
  const calendarDayFormatter = new Intl.DateTimeFormat(locale, { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const weekdays = Array.from({ length: 7 }, (_, index) => new Intl.DateTimeFormat(locale, { weekday: "short" }).format(new Date(2026, 0, 4 + index, 12)));
  const [isOpen, setIsOpen] = useState(false);
  const [visibleMonth, setVisibleMonth] = useState(() => new Date());
  const pickerRef = useRef(null);
  const triggerRef = useRef(null);
  const todayValue = toCalendarValue(new Date());
  const monthDays = getCalendarMonthDays(visibleMonth);

  useEffect(() => {
    if (!isOpen) return undefined;

    const closeOnOutsideClick = (event) => {
      if (!pickerRef.current?.contains(event.target)) setIsOpen(false);
    };
    const closeOnEscape = (event) => {
      if (event.key === "Escape") {
        setIsOpen(false);
        triggerRef.current?.focus();
      }
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
        ref={triggerRef}
        aria-haspopup="dialog"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((current) => !current)}
      >
        <span className="reservation-calendar-trigger-icon" aria-hidden="true">
          <CalendarDays size={18} />
        </span>
        <span>
          <small>{t("bookingEditor.chooseADate", { defaultValue: "Choose a date" })}</small>
          <strong>{t("bookingEditor.openCalendar", { defaultValue: "Open calendar" })}</strong>
        </span>
        <ChevronDown size={17} aria-hidden="true" />
      </button>

      {isOpen && (
        <div className="reservation-calendar-popover" role="dialog" aria-label={t("bookingEditor.chooseAnAvailableDate", { defaultValue: "Choose an available date" })}>
          <div className="reservation-calendar-toolbar">
            <strong>{calendarMonthFormatter.format(visibleMonth)}</strong>
            <div>
              <button type="button" aria-label={t("bookingEditor.previousMonth", { defaultValue: "Previous month" })} onClick={() => changeMonth(-1)}>
                <ChevronLeft size={17} aria-hidden="true" />
              </button>
              <button type="button" aria-label={t("bookingEditor.nextMonth", { defaultValue: "Next month" })} onClick={() => changeMonth(1)}>
                <ChevronRight size={17} aria-hidden="true" />
              </button>
            </div>
          </div>
          <div className="reservation-calendar-weekdays" aria-hidden="true">
            {weekdays.map((day) => <span key={day}>{day}</span>)}
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
                    triggerRef.current?.focus();
                  }}
                >
                  {new Intl.NumberFormat(locale).format(date.getDate())}
                </button>
              );
            })}
          </div>
          <div className="reservation-calendar-footer">
            <button type="button" onClick={showToday}>{t("bookingEditor.today", { defaultValue: "Today" })}</button>
            <button type="button" onClick={() => { setIsOpen(false); triggerRef.current?.focus(); }}>{t("bookingEditor.close", { defaultValue: "Close" })}</button>
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
  onSave,
  isSaving = false,
  saveDisabled = false,
}) {
  const { t, locale, direction } = useReservationEditorI18n();
  const formatDateLabel = date => formatBookingDate(date, locale);
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

  const configuredReservation = activeElement?.reservation || {};
  const availableDates = Array.isArray(configuredReservation.availableDates)
    ? [...new Set(cleanList(configuredReservation.availableDates))].sort()
    : [];
  const timeSlotsByDate = normalizeTimeSlotsByDate(
    availableDates,
    configuredReservation.timeSlots || [],
    configuredReservation.timeSlotsByDate
  );
  const timeSlots = flattenTimeSlotsByDate(timeSlotsByDate);
  const scheduleSummary = summarizeReservationSchedule(reservation, timeSlotsByDate);
  const isRestricted = reservation.bookingMode !== "flexible";
  const [availabilityDateSelection, setAvailabilityDateSelection] = useState({ reservationId: "", date: "" });
  const selectedAvailabilityDate = availabilityDateSelection.reservationId === String(activeElement?.id || "")
    && availableDates.includes(availabilityDateSelection.date)
    ? availabilityDateSelection.date
    : availableDates[0] || "";
  const selectedDateTimes = timeSlotsByDate[selectedAvailabilityDate] || [];
  const selectedDateRepeatsWeekly = Array.isArray(reservation.weeklyRepeatDates) && reservation.weeklyRepeatDates.includes(selectedAvailabilityDate);

  const saveTimeSlotsByDate = (nextMap, settings = reservation.sessionSettingsByDate) => {
    const nextSettings = settings && Object.fromEntries(Object.entries(settings).filter(([date]) => nextMap[date])
      .map(([date, sessions]) => [date, Object.fromEntries(Object.entries(sessions || {})
        .filter(([time]) => nextMap[date].includes(time)))]));
    updateReservation({
      ...(nextSettings ? { sessionSettingsByDate: nextSettings } : {}),
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
      ? [{ id: "availability", label: t("bookingEditor.availability"), helper: t("bookingEditor.datesAndTimes") }]
      : []),
    { id: "layout", label: t("bookingEditor.builder"), helper: t("bookingEditor.designBookingElement") },
  ];
  const bookingComponents = getBookingComponents(activeElement, reservation);
  const activeStepIndex = Math.max(
    0,
    reservationSteps.findIndex((step) => step.id === activeStep)
  );

  const nextBlockNumber = reservationBlocks.length + 1;
  const addFlexibleBlock = () =>
    onAddReservationBlock({
      name: reservationBlocks.length > 0 ? t("bookingEditor.newRequestName", { number: nextBlockNumber }) : t("bookingEditor.visitorDateRequest", { defaultValue: "Visitor date request" }),
      reservation: {
        ...fallbackReservation,
        title: t("bookingEditor.requestAnAppointment", { defaultValue: "Request an appointment" }),
        description: t("bookingEditor.chooseTheServiceDateAndTimeThatWorksForYou", { defaultValue: "Choose the service, date, and time that works for you." }),
        bookingMode: "flexible",
        submitLabel: t("bookingEditor.sendRequest", { defaultValue: "Send request" }),
        formItems: createDefaultBookingComponents({
          direction,
          title: t("bookingEditor.requestAnAppointment", { defaultValue: "Request an appointment" }),
          description: t("bookingEditor.chooseTheServiceDateAndTimeThatWorksForYou", { defaultValue: "Choose the service, date, and time that works for you." }),
          submitLabel: t("bookingEditor.sendRequest", { defaultValue: "Send request" }),
        }),
      },
    });
  const addFixedBlock = () =>
    onAddReservationBlock({
      name: reservationBlocks.length > 0 ? t("bookingEditor.newSlotsName", { number: nextBlockNumber }) : t("bookingEditor.fixedAppointmentSlots", { defaultValue: "Fixed appointment slots" }),
      reservation: {
        ...fallbackReservation,
        title: t("bookingEditor.bookAnAvailableSlot", { defaultValue: "Book an available slot" }),
        description: t("bookingEditor.chooseOneOfTheAvailableDatesAndTimes", { defaultValue: "Choose one of the available dates and times." }),
        bookingMode: "restricted",
        submitLabel: t("bookingEditor.bookSlot", { defaultValue: "Book slot" }),
        formItems: createDefaultBookingComponents({
          direction,
          title: t("bookingEditor.bookAnAvailableSlot", { defaultValue: "Book an available slot" }),
          description: t("bookingEditor.chooseOneOfTheAvailableDatesAndTimes", { defaultValue: "Choose one of the available dates and times." }),
          submitLabel: t("bookingEditor.bookSlot", { defaultValue: "Book slot" }),
          includeAvailability: true,
        }),
      },
    });

  return (
    <main dir={direction} className={`workspace-page reservations-workspace${activeStep === "layout" ? " is-form-editing" : ""}`}>
      <header className="workspace-header reservations-header app-page-intro">
        <div>
          <h1>{t("bookingEditor.reservations", { defaultValue: "Reservations" })}</h1>
          <p>{t("bookingEditor.manageYourBookingBlocksAvailableDatesAndAppointmentTimes", { defaultValue: "Manage your booking blocks, available dates, and appointment times." })}</p>
        </div>
      </header>


      <div className="reservation-editor-layout">
        <aside className="object-list reservation-block-list" aria-label={t("bookingEditor.reservationBlocks", { defaultValue: "Reservation blocks" })}>
          <div className="reservation-panel-heading">
            <div>
              <h2>{t("bookingEditor.bookingBlocks", { defaultValue: "Booking blocks" })}</h2>
            </div>
            <span className="reservation-count">{reservationBlocks.length}</span>
          </div>
          {reservationBlocks.length > 0 && (
            <div className="reservation-library-actions" aria-label={t("bookingEditor.addReservationBlock", { defaultValue: "Add reservation block" })}>
              <button type="button" onClick={addFlexibleBlock}>
                <Plus size={15} aria-hidden="true" />{t("bookingEditor.dateRequest", { defaultValue: "Date request" })}</button>
              <button type="button" onClick={addFixedBlock}>
                <CalendarDays size={15} aria-hidden="true" />{t("bookingEditor.fixedSlots", { defaultValue: "Fixed slots" })}</button>
            </div>
          )}
          {reservationBlocks.length === 0 && (
            <div className="reservation-empty-list">
              <CalendarDays size={20} aria-hidden="true" />
              <p>{t("bookingEditor.noReservationBlocksYet", { defaultValue: "No reservation blocks yet." })}</p>
            </div>
          )}
          {reservationBlocks.map((item) => (
            <button
              type="button"
              key={item.element.id}
              className={`reservation-list-item ${activeItem?.element.id === item.element.id ? "is-active" : ""}`}
              aria-current={activeItem?.element.id === item.element.id ? "true" : undefined}
              onClick={() => onSelectReservationBlock(item.element.id, item.page.id)}
            >
              <strong>{item.element.name || item.element.reservation?.title || t("bookingEditor.reservationBlock", { defaultValue: "Reservation block" })}</strong>
              <span>{item.element.reservation?.bookingMode === "flexible" ? t("bookingEditor.dateRequest", { defaultValue: "Date request" }) : t("bookingEditor.fixedSlots", { defaultValue: "Fixed slots" })} · {item.page.name}</span>
            </button>
          ))}
        </aside>

        <section className={`form-editor reservation-editor-card ${activeElement ? (isRestricted ? "is-restricted" : "is-flexible") : "is-empty"}`}>
          {activeElement ? (
            <>
              <div className="editor-card-header">
                <div>
                  <h2>{t("bookingEditor.bookingSetup", { defaultValue: "Booking setup" })}</h2>
                  {activeStep === "layout" && <button type="button" className="reservation-back-button"
                    onClick={() => setActiveStep(isRestricted ? "availability" : "overview")}>
                    {direction === "rtl" ? <ChevronRight size={16} aria-hidden="true" /> : <ChevronLeft size={16} aria-hidden="true" />}
                    {t("bookingEditor.backToReservations")}
                  </button>}
                  {activeStep === "layout" && <label className="reservation-form-chooser">{t("bookingEditor.bookingForm", { defaultValue: "Booking form" })}<select aria-label={t("bookingEditor.bookingForm", { defaultValue: "Booking form" })} value={activeElement.id} onChange={event => {
                      if (event.target.value === "__new_request__") return addFlexibleBlock();
                      if (event.target.value === "__new_scheduled__") return addFixedBlock();
                      const item = reservationBlocks.find(item => item.element.id === event.target.value);
                      if (item) onSelectReservationBlock(item.element.id, item.page.id);
                    }}>
                      {reservationBlocks.map(item => <option key={item.element.id} value={item.element.id}>{item.element.name || item.element.reservation?.title || t("bookingEditor.untitledForm", { defaultValue: "Untitled form" })}</option>)}
                      <option value="__new_request__">{t("bookingEditor.newAppointmentRequest", { defaultValue: "+ New appointment request" })}</option>
                      <option value="__new_scheduled__">{t("bookingEditor.newScheduledAppointments", { defaultValue: "+ New scheduled appointments" })}</option>
                    </select>
                  </label>}
                  <label className="reservation-build-name">
                    <span>{activeStep === "layout" ? t("bookingEditor.formName", { defaultValue: "Form name" }) : t("bookingEditor.name", { defaultValue: "Name" })}</span>
                    <input
                      aria-label={t("bookingEditor.reservationBuildName", { defaultValue: "Reservation build name" })}
                      value={activeElement.name || ""}
                      onChange={(event) => onUpdateReservationBlock(activeElement.id, { name: event.target.value })}
                    />
                  </label>
                  <p className="reservation-booking-meta">
                    {isRestricted
                      ? t("bookingEditor.scheduleSummary", { appointments: scheduleSummary.appointments, dates: scheduleSummary.dates,
                          appointmentLabel: t("bookingEditor.appointment", { count: scheduleSummary.appointments }), dateLabel: t("bookingEditor.date", { count: scheduleSummary.dates }) })
                        + (scheduleSummary.capacity === null ? t("bookingEditor.setMissingPeopleLimits") : t("bookingEditor.capacitySummary", { capacity: scheduleSummary.capacity, personLabel: t("bookingEditor.person", { count: scheduleSummary.capacity }) }))
                      : t("bookingEditor.visitorsChooseTheirPreferredDateAndTime", { defaultValue: "Visitors choose their preferred date and time" })}
                  </p>
                  {isRestricted && scheduleSummary.weekly && <p className="reservation-booking-meta">{t("bookingEditor.weeklyRepeatsAreEnabledFutureRepeatsAreAdditionalToTheseSavedAppointments", { defaultValue: "Weekly repeats are enabled. Future repeats are additional to these saved appointments." })}</p>}
                </div>
                <div className="reservation-editor-actions">
                  <button type="button" onClick={() => onSave?.()} disabled={isSaving || saveDisabled || !onSave}>
                    <Save size={16} aria-hidden="true" />
                    {isSaving ? t("bookingEditor.saving", { defaultValue: "Saving..." }) : t("bookingEditor.save", { defaultValue: "Save" })}
                  </button>
                  <button
                    type="button"
                    className="reservation-delete-block"
                    onClick={() => onDeleteReservationBlock(activeElement.id, activeItem.page.id)}
                  >
                    <Trash2 size={16} aria-hidden="true" />{t("bookingEditor.deleteBlock", { defaultValue: "Delete block" })}</button>
                </div>
              </div>

              <nav className="reservation-setup-steps" aria-label={t("bookingEditor.reservationSetupSteps", { defaultValue: "Reservation setup steps" })}>
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
                      <h3>{t("bookingEditor.buildYourBookingForm", { defaultValue: "Build your booking form" })}</h3>
                      <p>{t("bookingEditor.addFieldsOnTheLeftSelectAFieldToEditItOnTheRight", { defaultValue: "Add fields on the left. Select a field to edit it on the right." })}</p>
                    </div>
                    <span>{bookingComponents.length} {t("bookingEditor.fields", { defaultValue: "fields" })}</span>
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
                <div className="reservation-availability-layout">
                <div className="reservation-settings-section reservation-schedule-section reservation-date-section">
                  <div className="reservation-date-heading">
                    <span className="reservation-date-heading-icon" aria-hidden="true">
                      <CalendarDays size={20} />
                    </span>
                    <div>
                      <h3>{t("bookingEditor.availableDates", { defaultValue: "Available dates" })}</h3>
                      <p>{t("bookingEditor.chooseTheDaysVisitorsCanBook", { defaultValue: "Choose the days visitors can book." })}</p>
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
                  <div className="reservation-date-picker-grid" aria-label={t("bookingEditor.selectedAvailableDates", { defaultValue: "Selected available dates" })}>
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
                            <small>{(timeSlotsByDate[date] || []).length} {t("bookingEditor.timeSlots", { defaultValue: "time slots" })}{selectedAvailabilityDate === date ? t("bookingEditor.selected", { defaultValue: " · Selected" }) : ""}</small>
                            <strong>{formatDateLabel(date)}</strong>
                          </span>
                        </button>
                        <button
                          type="button"
                          aria-label={t("bookingEditor.removeDate", { date: formatDateLabel(date) })}
                          onClick={() => {
                            const nextDates = availableDates.filter((item) => item !== date);
                            const nextMap = { ...timeSlotsByDate };
                            delete nextMap[date];
                            updateReservation({
                              availableDates: nextDates,
                              ...(reservation.sessionSettingsByDate ? { sessionSettingsByDate: Object.fromEntries(
                                Object.entries(reservation.sessionSettingsByDate).filter(([source]) => source !== date)) } : {}),
                              weeklyRepeatDates: (Array.isArray(reservation.weeklyRepeatDates) ? reservation.weeklyRepeatDates : []).filter(source => source !== date),
                              timeSlotsByDate: nextMap,
                              timeSlots: flattenTimeSlotsByDate(nextMap),
                            });
                          }}
                        >
                          <Trash2 size={14} aria-hidden="true" />
                        </button>
                      </div>
                    )) : (
                      <p className="reservation-date-empty">{t("bookingEditor.addADateThenGiveItItsOwnAvailableTimes", { defaultValue: "Add a date, then give it its own available times." })}</p>
                    )}
                  </div>
                </div>
                <div className="reservation-settings-section reservation-schedule-section reservation-times-section">
                  <div className="reservation-list-heading">
                    <div>
                      <h3>{selectedAvailabilityDate ? t("bookingEditor.timesForDate", { date: formatDateLabel(selectedAvailabilityDate) }) : t("bookingEditor.chooseADateFirst", { defaultValue: "Choose a date first" })}</h3>
                      <p>{selectedAvailabilityDate ? (selectedDateRepeatsWeekly ? t("bookingEditor.theseAppointmentsRepeatEveryWeekSetEachOneSeparately", { defaultValue: "These appointments repeat every week. Set each one separately." }) : t("bookingEditor.chooseATimeBelowToSetWhoCanJoinAndHowManyPeopleCanBook", { defaultValue: "Choose a time below to set who can join and how many people can book." })) : t("bookingEditor.addOrSelectADateAboveToManageItsTimes", { defaultValue: "Add or select a date above to manage its times." })}</p>
                    </div>
                    <button
                      type="button"
                      disabled={!selectedAvailabilityDate}
                      onClick={() => saveTimeSlotsByDate({
                        ...timeSlotsByDate,
                        [selectedAvailabilityDate]: [...selectedDateTimes, getNextTimeSlot(selectedDateTimes)],
                      })}
                    >
                      <Plus size={15} aria-hidden="true" />{t("bookingEditor.addTime", { defaultValue: "Add time" })}</button>
                  </div>
                  {selectedAvailabilityDate && (
                    <RepeatReservationTimes
                      checked={selectedDateRepeatsWeekly}
                      onChange={enabled => {
                        const dates = Array.isArray(reservation.weeklyRepeatDates) ? reservation.weeklyRepeatDates : [];
                        updateReservation({
                          weeklyRepeatDates: enabled
                            ? [...new Set([...dates, selectedAvailabilityDate])]
                            : dates.filter(date => date !== selectedAvailabilityDate),
                          timeSlotsByDate,
                        });
                      }}
                    />
                  )}
                  <div className="reservation-bullet-editor reservation-time-editor">
                    {selectedAvailabilityDate && selectedDateTimes.length > 0 ? selectedDateTimes.map((slot, index) => (
                      <ReservationSessionCard key={`${selectedAvailabilityDate}_${index}`}
                        dateLabel={formatDateLabel(selectedAvailabilityDate)} time={slot} index={index}
                        session={getReservationSession({ ...reservation, timeSlotsByDate }, selectedAvailabilityDate, slot)}
                        onTimeBlur={() => saveTimeSlotsByDate({ ...timeSlotsByDate,
                          [selectedAvailabilityDate]: cleanList(selectedDateTimes) })}
                        onTimeChange={nextTime => {
                          if (nextTime !== slot && selectedDateTimes.includes(nextTime)) return;
                          const settings = reservation.sessionSettingsByDate;
                          let nextSettings = settings;
                          if (settings?.[selectedAvailabilityDate]?.[slot]) {
                            const daySettings = { ...settings[selectedAvailabilityDate] };
                            daySettings[nextTime] = daySettings[slot];
                            if (nextTime !== slot) delete daySettings[slot];
                            nextSettings = { ...settings, [selectedAvailabilityDate]: daySettings };
                          }
                          saveTimeSlotsByDate({ ...timeSlotsByDate,
                            [selectedAvailabilityDate]: selectedDateTimes.map((value, i) => i === index ? nextTime : value) }, nextSettings);
                        }}
                        onRemove={() => saveTimeSlotsByDate({ ...timeSlotsByDate,
                          [selectedAvailabilityDate]: selectedDateTimes.filter((_, i) => i !== index) })}
                        onSettingsChange={settings => updateReservation({
                          sessionSettingsByDate: {
                            ...reservation.sessionSettingsByDate,
                            [selectedAvailabilityDate]: { ...reservation.sessionSettingsByDate?.[selectedAvailabilityDate], [slot]: settings },
                          },
                        })}
                      />
                    )) : (
                      <p className="reservation-date-empty">
                        {selectedAvailabilityDate ? t("bookingEditor.noTimesAddedForThisDateYet", { defaultValue: "No times added for this date yet." }) : t("bookingEditor.noDateSelected", { defaultValue: "No date selected." })}
                      </p>
                    )}
                  </div>

                </div>
                </div>
              )}

              {activeStep !== "overview" && <footer className="reservation-step-actions">
                <button
                  type="button"
                  disabled={activeStepIndex === 0}
                  onClick={() => setActiveStep(reservationSteps[activeStepIndex - 1]?.id || reservationSteps[0].id)}
                >{t("bookingEditor.back", { defaultValue: "Back" })}</button>
                <span>{t("bookingEditor.changesSaveAutomatically", { defaultValue: "Changes save automatically" })}</span>
                {activeStepIndex < reservationSteps.length - 1 && (
                  <button
                    type="button"
                    className="primary-action page-primary-action"
                    onClick={() => setActiveStep(reservationSteps[activeStepIndex + 1].id)}
                  >{t("bookingEditor.continue", { defaultValue: "Continue" })}</button>
                )}
              </footer>}
            </>
          ) : (
            <div className="reservation-editor-empty">
              <div className="reservation-empty-icon" aria-hidden="true">
                <ListPlus size={24} />
              </div>
              <div className="reservation-empty-copy">
                <h2>{t("bookingEditor.createYourFirstReservationBlock", { defaultValue: "Create your first reservation block" })}</h2>
                <p>{t("bookingEditor.pickTheBookingStyleThatMatchesHowYouWantToHandleAppointments", { defaultValue: "Pick the booking style that matches how you want to handle appointments." })}</p>
              </div>
              <div className="reservation-empty-actions">
                <button type="button" className="primary-action page-primary-action" onClick={addFlexibleBlock}>
                  <Plus size={16} aria-hidden="true" />
                  <span>
                    <strong>{t("bookingEditor.visitorDateRequest", { defaultValue: "Visitor date request" })}</strong>
                    <small>{t("bookingEditor.visitorsSuggestADateAndTime", { defaultValue: "Visitors suggest a date and time." })}</small>
                  </span>
                </button>
                <button type="button" onClick={addFixedBlock}>
                  <CalendarDays size={16} aria-hidden="true" />
                  <span>
                    <strong>{t("bookingEditor.fixedSlots", { defaultValue: "Fixed slots" })}</strong>
                    <small>{t("bookingEditor.visitorsChooseFromYourSchedule", { defaultValue: "Visitors choose from your schedule." })}</small>
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
