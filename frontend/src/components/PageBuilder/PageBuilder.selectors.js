export const findElementLocationInPage = (page, elementId) => {
  for (const section of page?.sections || []) {
    if (section.mode === "direct") {
      const elementIndex = (section.freeElements || []).findIndex(
        (element) => element.id === elementId
      );

      if (elementIndex >= 0) {
        return {
          sectionId: section.id,
          elementIndex,
          isFree: true,
        };
      }
    }

    for (const row of section.rows || []) {
      for (const column of row.columns || []) {
        const elementIndex = (column.elements || []).findIndex(
          (element) => element.id === elementId
        );

        if (elementIndex >= 0) {
          return {
            sectionId: section.id,
            rowId: row.id,
            columnId: column.id,
            elementIndex,
            isFree: false,
          };
        }
      }
    }
  }

  return null;
};

export const getResponseCountFromProject = (project) =>
  (project?.forms || []).reduce((total, form) => total + (form.responses?.length || 0), 0);

export const getSavedRecordCountFromProject = (project) =>
  (project?.collections || []).reduce(
    (total, collection) => total + (collection.records?.length || 0),
    0
  );

export const collectBuilderElementsFromProject = (project, getSectionElements) =>
  (project?.pages || []).flatMap((page) =>
    (page.sections || []).flatMap((section) => getSectionElements(section))
  );

export const collectBuilderUrlErrorsForProject = ({
  project,
  collectBuilderUrlErrorsFromUtils,
  getSectionElements,
  carouselElementTypes,
}) =>
  collectBuilderUrlErrorsFromUtils({
    project,
    collectBuilderElements: (targetProject) =>
      collectBuilderElementsFromProject(targetProject, getSectionElements),
    carouselElementTypes,
  });

export const getFieldTypeById = (fieldTypes, type) =>
  fieldTypes.find((item) => item.id === type) || fieldTypes[0];

export const createBuilderUrlErrorCollector = ({
  collectBuilderUrlErrorsFromUtils,
  getSectionElements,
  carouselElementTypes,
}) => (project) =>
  collectBuilderUrlErrorsForProject({
    project,
    collectBuilderUrlErrorsFromUtils,
    getSectionElements,
    carouselElementTypes,
  });

export const getElementSectionFromPage = ({
  page,
  elementId,
  findElementLocation,
}) => {
  const location = findElementLocation(elementId);
  return page?.sections.find((section) => section.id === location?.sectionId) || null;
};

export const getFormPlacementsFromProject = (project, formId) =>
  (project?.pages || []).flatMap((page) =>
    (page.sections || []).flatMap((section) => {
      const autoElements = (section.rows || []).flatMap((row) =>
        (row.columns || []).flatMap((column) => column.elements || [])
      );
      const freeElements = section.freeElements || [];
      const connected = [...autoElements, ...freeElements].some(
        (element) => element.type === "formBlock" && element.connectedFormId === formId
      );

      return connected
        ? [{ pageId: page.id, pageName: page.name, sectionName: section.name }]
        : [];
    })
  );
