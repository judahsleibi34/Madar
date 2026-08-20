const reservationContentEn = {
  defaultServices: ["Consultation", "Service appointment", "Table reservation"],
  defaultFields: ["name", "contact", "service", "date", "time", "guests", "notes"],
  requiredFields: ["name", "contact", "service", "date", "time"],
  fieldMeta: {
    name: { label: "Name", placeholder: "Full name" },
    contact: { label: "Contact", placeholder: "Phone or email" },
    service: { label: "Service" },
    date: { label: "Date" },
    time: { label: "Time" },
    guests: { label: "Guests" },
    notes: { label: "Notes", placeholder: "Special requests, location, or details" },
  },
  title: "Book a reservation",
  description: "Choose a service, date, and time. We will confirm availability with you.",
  submitLabel: "Request reservation",
  required: "Required",
  kicker: "Reservation",
  servicesLabel: "Services",
  disabledHelper: "Publish the site to accept real reservations. Builder preview does not add calendar events.",
};

export const reservationContent = {
  en: reservationContentEn,
  ar: reservationContentEn,
};

export function getReservationContent(lang = "en") {
  return reservationContent[lang] || reservationContent.en;
}
