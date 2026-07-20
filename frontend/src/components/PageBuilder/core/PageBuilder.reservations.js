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
