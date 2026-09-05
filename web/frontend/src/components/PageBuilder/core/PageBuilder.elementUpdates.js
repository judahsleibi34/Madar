const mergeElementUpdates = (element, updates) => ({
  ...element,
  ...updates,
  styles: { ...element.styles, ...(updates.styles || {}) },
  action: { ...element.action, ...(updates.action || {}) },
});

const updateElementList = (elements = [], elementId, updates) => {
  let changed = false;
  const nextElements = elements.map((element) => {
    if (element.id !== elementId) return element;
    changed = true;
    return mergeElementUpdates(element, updates);
  });
  return changed ? nextElements : elements;
};

export const updateElementInSectionsPreservingLayout = (
  sections = [],
  elementId,
  updates
) =>
  sections.map((section) => {
    if (section.mode === "direct") {
      const freeElements = updateElementList(section.freeElements, elementId, updates);
      return freeElements === section.freeElements ? section : { ...section, freeElements };
    }

    let sectionChanged = false;
    const rows = (section.rows || []).map((row) => {
      let rowChanged = false;
      const columns = (row.columns || []).map((column) => {
        const elements = updateElementList(column.elements, elementId, updates);
        if (elements === column.elements) return column;
        rowChanged = true;
        return { ...column, elements };
      });
      if (!rowChanged) return row;
      sectionChanged = true;
      return { ...row, columns };
    });

    return sectionChanged ? { ...section, rows } : section;
  });