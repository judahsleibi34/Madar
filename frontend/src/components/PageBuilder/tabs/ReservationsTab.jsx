import { CalendarDays, Clock, Eye, ListPlus, Plus, Trash2 } from "lucide-react";

const fallbackReservation = {
  title: "Book an appointment",
  description: "Choose a service, date, and time. We will confirm your appointment shortly.",
  bookingMode: "restricted",
  services: ["Consultation", "Follow-up", "Project planning"],
  availableDates: ["2026-07-08", "2026-07-10", "2026-07-12"],
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
  return `${day}/${month}/${year}`;
};

export default function ReservationsTab({
  reservationBlocks,
  activeReservationId,
  onAddReservationBlock,
  onOpenReservationBlock,
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
          <h2>Reservations</h2>
          <p>Set what visitors can book, when they can book it, and how the booking form appears.</p>
        </div>
      </header>

      <div className="reservation-editor-layout">
        <aside className="object-list reservation-block-list" aria-label="Reservation blocks">
          <div className="reservation-panel-heading">
            <div>
              <span className="workspace-kicker">Library</span>
              <strong>Reservation blocks</strong>
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
              <strong>{item.element.reservation?.title || item.element.name || "Reservation block"}</strong>
              <span>{item.page.name} / {item.section.name}</span>
            </button>
          ))}
        </aside>

        <section className={`form-editor reservation-editor-card ${activeElement ? "" : "is-empty"}`}>
          {activeElement ? (
            <>
              <div className="editor-card-header">
                <div>
                  <span className="workspace-kicker">Setup</span>
                  <h3>Configure booking block</h3>
                </div>
                <div className="reservation-editor-actions">
                  <button type="button" onClick={() => onOpenReservationBlock(activeElement.id, activeItem.page.id)}>
                    <Eye size={16} aria-hidden="true" />
                    Open on page
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

              <div className="reservation-settings-section">
                <div>
                  <span className="workspace-kicker">Visitor copy</span>
                  <h4>Block copy</h4>
                </div>
                <div className="reservation-copy-grid">
                  <label>
                    Internal name
                    <input
                      value={activeElement.name || ""}
                      onChange={(event) => onUpdateReservationBlock(activeElement.id, { name: event.target.value })}
                    />
                  </label>
                  <label>
                    Public title
                    <input
                      value={reservation.title}
                      onChange={(event) => updateReservation({ title: event.target.value })}
                    />
                  </label>
                  <label className="reservation-wide-field">
                    Description
                    <textarea
                      value={reservation.description}
                      onChange={(event) => updateReservation({ description: event.target.value })}
                    />
                  </label>
                  <label>
                    Button text
                    <input
                      value={reservation.submitLabel}
                      onChange={(event) => updateReservation({ submitLabel: event.target.value })}
                    />
                  </label>
                </div>
              </div>

              <div className="reservation-settings-section">
                <div className="reservation-mode-card">
                  <div>
                    <span className="workspace-kicker">Booking mode</span>
                    <h4>{isRestricted ? "Fixed reservation slots" : "Visitor enters date and time"}</h4>
                    <p>
                      {isRestricted
                        ? "Visitors choose from the dates and time slots you publish."
                        : "Visitors type or pick the date and time they want. You confirm it later."}
                    </p>
                  </div>
                  <div className="reservation-mode-switch" role="group" aria-label="Reservation booking mode">
                    <button
                      type="button"
                      className={!isRestricted ? "active" : ""}
                      onClick={() => updateReservation({ bookingMode: "flexible" })}
                    >
                      Visitor date
                    </button>
                    <button
                      type="button"
                      className={isRestricted ? "active" : ""}
                      onClick={() => updateReservation({ bookingMode: "restricted" })}
                    >
                      Fixed slots
                    </button>
                  </div>
                </div>
              </div>

              <div className="reservation-settings-section">
                <div className="reservation-list-heading">
                  <div>
                    <span className="workspace-kicker">Options</span>
                    <h4>Services</h4>
                  </div>
                  <button type="button" onClick={() => addReservationListItem("services", `Service ${services.length + 1}`)}>
                    <Plus size={15} aria-hidden="true" />
                    Add service
                  </button>
                </div>
                <div className="reservation-bullet-editor">
                  {services.map((service, index) => (
                    <div className="reservation-bullet-row" key={`service_${index}`}>
                      <span className="reservation-bullet-dot" aria-hidden="true" />
                      <input
                        value={service}
                        placeholder={`Service ${index + 1}`}
                        onBlur={() => cleanReservationList("services")}
                        onChange={(event) => updateReservationListItem("services", index, event.target.value)}
                      />
                      <button
                        type="button"
                        aria-label="Remove service"
                        disabled={services.length <= 1}
                        onClick={() => removeReservationListItem("services", index)}
                      >
                        <Trash2 size={15} aria-hidden="true" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {isRestricted && (
                <div className="reservation-settings-section">
                  <div>
                    <span className="workspace-kicker">Calendar</span>
                    <h4>Available dates</h4>
                  </div>
                    <label className="reservation-date-add">
                      Add available date
                      <input
                        type="date"
                        onChange={(event) => {
                          const nextDate = event.target.value;
                          if (!nextDate || availableDates.includes(nextDate)) return;
                          updateReservation({ availableDates: [...availableDates, nextDate].sort() });
                          event.target.value = "";
                        }}
                      />
                    </label>
                    <div className="reservation-date-picker-grid" aria-label="Selected available dates">
                      {availableDates.map((date) => (
                        <button
                          type="button"
                          key={date}
                          onClick={() =>
                            updateReservation({
                              availableDates: availableDates.filter((item) => item !== date),
                            })
                          }
                        >
                          <CalendarDays size={15} aria-hidden="true" />
                          <span>{formatDateLabel(date)}</span>
                          <Trash2 size={14} aria-hidden="true" />
                        </button>
                      ))}
                    </div>
                </div>
              )}

              {isRestricted && (
                <div className="reservation-settings-section">
                <div className="reservation-list-heading">
                  <div>
                    <span className="workspace-kicker">Schedule</span>
                    <h4>Time slots</h4>
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
            </>
          ) : (
            <div className="reservation-editor-empty">
              <div className="reservation-empty-icon" aria-hidden="true">
                <ListPlus size={24} />
              </div>
              <div className="reservation-empty-copy">
                <span className="workspace-kicker">Start here</span>
                <h3>Create your first reservation block</h3>
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
