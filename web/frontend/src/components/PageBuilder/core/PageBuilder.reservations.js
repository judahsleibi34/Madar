const getSectionReservationElements = (section = {}) => {
  const directElements = Array.isArray(section.freeElements) ? section.freeElements : [];
  const columnElements = (section.rows || []).flatMap((row) =>
    (row.columns || []).flatMap((column) => column.elements || [])
  );

  return [...directElements, ...columnElements].filter(
    (element) => element?.type === "reservationBlock"
  );
};

export const findReservationBlockElement = (pages = [], elementId = "") => {
  if (!elementId) return null;

  for (const page of pages || []) {
    for (const section of page.sections || []) {
      const match = getSectionReservationElements(section).find(
        (element) => String(element.id) === String(elementId)
      );
      if (match) return match;
    }
  }

  return null;
};

export const resolveReservationBlockElement = (element, pages = []) => {
  if (!element) return null;

  const sourceId = element.connectedReservationBlockId;
  if (!sourceId || String(sourceId) === String(element.id)) return element;

  return findReservationBlockElement(pages, sourceId) || element;
};

export const resolveReservationBlockValue = (element, pages = []) =>
  resolveReservationBlockElement(element, pages)?.reservation ||
  element?.reservation ||
  null;

export const getReservationPaletteItems = (reservationDefinitions = []) =>
  (Array.isArray(reservationDefinitions) ? reservationDefinitions : []).flatMap((definition, index) => {
    const element = definition?.element || definition;
    if (!element?.id || element.type !== "reservationBlock") return [];
    const reservation = element.reservation || {};
    const mode = reservation.bookingMode === "flexible" ? "flexible" : "restricted";
    return [{
      id: String(element.id),
      label: element.name || reservation.title || `Reservation ${index + 1}`,
      mode,
      type: mode === "flexible" ? "reservationRequest" : "reservationFixedSlots",
      helper: mode === "flexible" ? "Date request" : "Fixed slots",
    }];
  });
export const createReservationPalettePlacement = (reservationDefinitions = [], definitionId = "") => {
  const definition = (reservationDefinitions || []).find(
    (candidate) => String((candidate?.element || candidate)?.id) === String(definitionId)
  );
  const source = definition?.element || definition;
  if (!source) return null;
  const mode = source.reservation?.bookingMode === "flexible" ? "flexible" : "restricted";
  return {
    type: mode === "flexible" ? "reservationRequest" : "reservationFixedSlots",
    overrides: {
      name: source.name || source.reservation?.title || "Reservation build",
      connectedReservationBlockId: source.id,
      reservationPlacementType: mode,
      reservation: source.reservation,
      directSizeMode: "auto",
    },
  };
};