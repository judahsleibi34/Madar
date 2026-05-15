import { useMemo, useState } from "react";
import "../styles/admin/PageBuilder.css";

const createId = (prefix) => `${prefix}_${crypto.randomUUID()}`;

const createEmptyAction = () => ({
  type: "none",
  pageId: "",
  url: "",
});

const createPosition = () => ({
  desktop: { x: 40, y: 40, width: 320, height: 80 },
  tablet: { x: 32, y: 32, width: 280, height: 80 },
  mobile: { x: 20, y: 20, width: 260, height: 80 },
});

const createEmptyValidation = () => ({
  required: false,
  message: "This field is required.",
});

const viewportWidths = {
  desktop: 1200,
  tablet: 768,
  mobile: 390,
};

const pageTypeLabels = {
  standard: "Standard Page",
  flow: "Multi-Step Flow",
};

const slugify = (value) => {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
};

const getNextPageNumber = (pages, type) => {
  return pages.filter((page) => page.type === type).length + 1;
};

const createUniqueSlug = (pages, baseSlug) => {
  let slug = baseSlug;
  let count = 2;

  while (pages.some((page) => page.slug === slug)) {
    slug = `${baseSlug}-${count}`;
    count += 1;
  }

  return slug;
};

const sectionPresets = [
  { label: "Hero Section", value: "heroSplit" },
  { label: "Metrics Section", value: "statsRow" },
  { label: "Management Header", value: "managementHeader" },
  { label: "Form Section", value: "formBuilder" },
  { label: "Checklist Section", value: "workflowChecklist" },
  { label: "Free Design Section", value: "freeCanvas" },
];

const elementTypes = [
  { label: "Title", value: "heading", group: "Content" },
  { label: "Paragraph", value: "text", group: "Content" },
  { label: "Action Button", value: "button", group: "Content" },
  { label: "Image", value: "image", group: "Content" },
  { label: "Content Card", value: "card", group: "Content" },
  { label: "Short Answer", value: "input", group: "Form Fields" },
  { label: "Long Answer", value: "textarea", group: "Form Fields" },
  { label: "Checkbox", value: "checkbox", group: "Form Fields" },
  { label: "Dropdown", value: "select", group: "Form Fields" },
  { label: "Single Choice", value: "radio", group: "Form Fields" },
];

const getElementLabel = (type) => {
  return elementTypes.find((item) => item.value === type)?.label || type;
};

const defaultElement = (type) => {
  const base = {
    id: createId(type),
    type,
    content: "",
    mode: "auto",
    position: createPosition(),
    validation: createEmptyValidation(),
    styles: {
      alignSelf: "auto",
      offsetX: 0,
    },
  };

  if (type === "heading") {
    return {
      ...base,
      content: "New Title",
      styles: {
        fontSize: "36px",
        color: "#1a2744",
        textAlign: "left",
        alignSelf: "auto",
        offsetX: 0,
      },
    };
  }

  if (type === "text") {
    return {
      ...base,
      content: "Write your paragraph here.",
      styles: {
        fontSize: "16px",
        color: "#334155",
        textAlign: "left",
        alignSelf: "auto",
        offsetX: 0,
      },
    };
  }

  if (type === "button") {
    return {
      ...base,
      content: "Action Button",
      action: createEmptyAction(),
      styles: {
        backgroundColor: "#8b2a1a",
        color: "#ffffff",
        borderRadius: "10px",
        alignSelf: "auto",
        offsetX: 0,
      },
    };
  }

  if (type === "image") {
    return {
      ...base,
      content:
        "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=900&auto=format&fit=crop",
      styles: {
        borderRadius: "16px",
        alignSelf: "stretch",
        offsetX: 0,
      },
    };
  }

  if (type === "card") {
    return {
      ...base,
      content: "Card title\nCard description or value.",
      styles: {
        backgroundColor: "#ffffff",
        color: "#1a2744",
        borderRadius: "16px",
        alignSelf: "stretch",
        offsetX: 0,
      },
    };
  }

  if (type === "input") {
    return {
      ...base,
      content: "Short answer",
      fieldKey: createId("field"),
      placeholder: "Enter your answer",
      inputType: "text",
      validation: {
        required: false,
        message: "This field is required.",
      },
      styles: {
        color: "#1a2744",
        backgroundColor: "#ffffff",
        borderRadius: "10px",
        alignSelf: "stretch",
        offsetX: 0,
      },
    };
  }

  if (type === "textarea") {
    return {
      ...base,
      content: "Long answer",
      fieldKey: createId("field"),
      placeholder: "Write your answer...",
      validation: {
        required: false,
        message: "This field is required.",
      },
      styles: {
        color: "#1a2744",
        backgroundColor: "#ffffff",
        borderRadius: "10px",
        alignSelf: "stretch",
        offsetX: 0,
      },
    };
  }

  if (type === "checkbox") {
    return {
      ...base,
      content: "Checkbox option",
      fieldKey: createId("field"),
      checked: false,
      validation: {
        required: false,
        message: "This checkbox must be checked.",
      },
      styles: {
        color: "#1a2744",
        fontSize: "15px",
        alignSelf: "auto",
        offsetX: 0,
      },
    };
  }

  if (type === "select") {
    return {
      ...base,
      content: "Dropdown question",
      fieldKey: createId("field"),
      options: ["Option 1", "Option 2"],
      validation: {
        required: false,
        message: "Please select an option.",
      },
      styles: {
        color: "#1a2744",
        backgroundColor: "#ffffff",
        borderRadius: "10px",
        alignSelf: "stretch",
        offsetX: 0,
      },
    };
  }

  if (type === "radio") {
    return {
      ...base,
      content: "Single choice question",
      fieldKey: createId("field"),
      options: ["Option 1", "Option 2"],
      validation: {
        required: false,
        message: "Please choose one option.",
      },
      styles: {
        color: "#1a2744",
        fontSize: "15px",
        alignSelf: "auto",
        offsetX: 0,
      },
    };
  }

  return base;
};

const createAutoSection = (name = "Auto Section") => ({
  id: createId("section"),
  type: "section",
  name,
  mode: "auto",
  layout: {
    width: "medium",
    background: "#ffffff",
    paddingY: "large",
  },
  rows: [
    {
      id: createId("row"),
      layout: {
        columns: "1",
        align: "start",
        gap: "medium",
      },
      columns: [
        {
          id: createId("column"),
          layout: {
            align: "left",
          },
          elements: [],
        },
      ],
    },
  ],
  freeElements: [],
});

const createFreeSection = () => ({
  id: createId("section"),
  type: "section",
  name: "Free Design Section",
  mode: "free",
  layout: {
    width: "large",
    background: "#ffffff",
    paddingY: "none",
    minHeight: 560,
  },
  rows: [],
  freeElements: [
    {
      ...defaultElement("heading"),
      content: "Design freely inside this section",
      mode: "free",
      position: {
        desktop: { x: 60, y: 70, width: 520, height: 80 },
        tablet: { x: 40, y: 60, width: 440, height: 80 },
        mobile: { x: 24, y: 50, width: 300, height: 80 },
      },
    },
    {
      ...defaultElement("text"),
      content:
        "Drag elements inside this frame. Then check desktop, tablet, and mobile warnings.",
      mode: "free",
      position: {
        desktop: { x: 60, y: 160, width: 520, height: 90 },
        tablet: { x: 40, y: 150, width: 440, height: 90 },
        mobile: { x: 24, y: 140, width: 300, height: 100 },
      },
    },
    {
      ...defaultElement("button"),
      content: "Action Button",
      mode: "free",
      position: {
        desktop: { x: 60, y: 280, width: 170, height: 52 },
        tablet: { x: 40, y: 270, width: 170, height: 52 },
        mobile: { x: 24, y: 270, width: 170, height: 52 },
      },
    },
  ],
});

const createSectionPreset = (preset) => {
  if (preset === "freeCanvas") {
    return createFreeSection();
  }

  if (preset === "formBuilder") {
    const section = createAutoSection("Form Section");

    section.rows[0].columns[0].elements = [
      { ...defaultElement("heading"), content: "Form Section" },
      {
        ...defaultElement("input"),
        content: "Full name",
        placeholder: "Enter your full name",
        validation: {
          required: true,
          message: "Full name is required.",
        },
      },
      {
        ...defaultElement("input"),
        content: "Email address",
        placeholder: "Enter your email",
        inputType: "email",
        validation: {
          required: true,
          message: "Email address is required.",
        },
      },
      {
        ...defaultElement("select"),
        content: "Department",
        options: ["HR", "Finance", "Operations", "Education"],
      },
      {
        ...defaultElement("checkbox"),
        content: "I confirm the information is correct",
        validation: {
          required: true,
          message: "You must confirm the information.",
        },
      },
    ];

    return section;
  }

  if (preset === "workflowChecklist") {
    const section = createAutoSection("Checklist Section");

    section.rows[0].columns[0].elements = [
      { ...defaultElement("heading"), content: "Checklist Section" },
      {
        ...defaultElement("checkbox"),
        content: "Step 1 completed",
        validation: {
          required: true,
          message: "Step 1 must be completed.",
        },
      },
      { ...defaultElement("checkbox"), content: "Step 2 reviewed" },
      { ...defaultElement("checkbox"), content: "Step 3 approved" },
    ];

    return section;
  }

  if (preset === "managementHeader") {
    return {
      id: createId("section"),
      type: "section",
      name: "Management Header",
      mode: "auto",
      layout: {
        width: "large",
        background: "#ffffff",
        paddingY: "small",
      },
      rows: [
        {
          id: createId("row"),
          layout: {
            columns: "2",
            align: "center",
            gap: "medium",
          },
          columns: [
            {
              id: createId("column"),
              layout: {
                align: "left",
              },
              elements: [
                {
                  ...defaultElement("heading"),
                  content: "Users Management",
                  styles: {
                    fontSize: "32px",
                    color: "#1a2744",
                    textAlign: "left",
                    alignSelf: "auto",
                    offsetX: 0,
                  },
                },
                {
                  ...defaultElement("text"),
                  content: "Manage users, permissions, and activity.",
                },
              ],
            },
            {
              id: createId("column"),
              layout: {
                align: "right",
              },
              elements: [{ ...defaultElement("button"), content: "Add User" }],
            },
          ],
        },
      ],
      freeElements: [],
    };
  }

  if (preset === "statsRow") {
    return {
      id: createId("section"),
      type: "section",
      name: "Metrics Section",
      mode: "auto",
      layout: {
        width: "large",
        background: "#ffffff",
        paddingY: "medium",
      },
      rows: [
        {
          id: createId("row"),
          layout: {
            columns: "4",
            align: "stretch",
            gap: "medium",
          },
          columns: [1, 2, 3, 4].map((number) => ({
            id: createId("column"),
            layout: {
              align: "left",
            },
            elements: [
              {
                ...defaultElement("card"),
                content: `Metric ${number}\n12,450`,
              },
            ],
          })),
        },
      ],
      freeElements: [],
    };
  }

  const section = createAutoSection("Hero Section");

  section.layout.width = "large";
  section.layout.background = "#ffffff";
  section.rows = [
    {
      id: createId("row"),
      layout: {
        columns: "2",
        align: "center",
        gap: "large",
      },
      columns: [
        {
          id: createId("column"),
          layout: {
            align: "left",
          },
          elements: [
            {
              ...defaultElement("heading"),
              content: "Your main website message",
            },
            {
              ...defaultElement("text"),
              content:
                "Build landing pages, management pages, forms, exams, checkout flows, dashboards, and CMS screens.",
            },
            defaultElement("button"),
          ],
        },
        {
          id: createId("column"),
          layout: {
            align: "center",
          },
          elements: [defaultElement("card")],
        },
      ],
    },
  ];

  return section;
};

const createNormalPage = (pages = []) => {
  const pageNumber = getNextPageNumber(pages, "standard");
  const name = `Page ${pageNumber}`;
  const baseSlug = `/${slugify(name)}`;

  return {
    id: createId("page"),
    name,
    slug: createUniqueSlug(pages, baseSlug),
    type: "standard",
    parentId: null,
    sections: [],
  };
};

const createFlowPage = (pages = []) => {
  const pageNumber = getNextPageNumber(pages, "flow");
  const name = `Flow ${pageNumber}`;
  const baseSlug = `/${slugify(name)}`;

  return {
    id: createId("page"),
    name,
    slug: createUniqueSlug(pages, baseSlug),
    type: "flow",
    parentId: null,
    activeStepId: "step_1",
    flowSettings: {
      showProgress: true,
      allowBack: true,
      requireStepValidation: true,
    },
    steps: [
      {
        id: "step_1",
        name: "Details",
        sections: [createSectionPreset("formBuilder")],
      },
      {
        id: "step_2",
        name: "Review",
        sections: [createSectionPreset("workflowChecklist")],
      },
    ],
  };
};

const initialWebsite = {
  id: "site_1",
  name: "Madar Builder",
  activePageId: "home",
  pages: [
    {
      id: "home",
      name: "Page 1",
      slug: "/",
      type: "standard",
      parentId: null,
      sections: [createSectionPreset("heroSplit")],
    },
    {
      id: "finance_flow",
      name: "Flow 1",
      slug: "/finance-request",
      type: "flow",
      parentId: null,
      activeStepId: "finance_step_1",
      flowSettings: {
        showProgress: true,
        allowBack: true,
        requireStepValidation: true,
      },
      steps: [
        {
          id: "finance_step_1",
          name: "Details",
          sections: [createSectionPreset("formBuilder")],
        },
        {
          id: "finance_step_2",
          name: "Review",
          sections: [createSectionPreset("workflowChecklist")],
        },
      ],
    },
  ],
};

export default function PageBuilder() {
  const [website, setWebsite] = useState(initialWebsite);
  const [selected, setSelected] = useState({
    type: "page",
    id: initialWebsite.activePageId,
  });
  const [previewMode, setPreviewMode] = useState(false);
  const [viewportMode, setViewportMode] = useState("desktop");
  const [formValues, setFormValues] = useState({});
  const [validationErrors, setValidationErrors] = useState({});
  const [dragState, setDragState] = useState(null);
  const [selectedSectionPreset, setSelectedSectionPreset] = useState("heroSplit");
  const [quickAddOpen, setQuickAddOpen] = useState(false);

  const activePage = useMemo(() => {
    return website.pages.find((page) => page.id === website.activePageId);
  }, [website]);

  const activeStep = useMemo(() => {
    if (!activePage || activePage.type !== "flow") return null;
    return activePage.steps.find((step) => step.id === activePage.activeStepId);
  }, [activePage]);

  const currentSections =
    activePage?.type === "flow"
      ? activeStep?.sections || []
      : activePage?.sections || [];

  const selectedSection = useMemo(() => {
    if (!selected || selected.type !== "section") return null;
    return currentSections.find((section) => section.id === selected.id);
  }, [currentSections, selected]);

  const selectedColumn = useMemo(() => {
    if (!selected || selected.type !== "column") return null;

    for (const section of currentSections) {
      for (const row of section.rows || []) {
        const column = row.columns.find((item) => item.id === selected.id);
        if (column) return column;
      }
    }

    return null;
  }, [currentSections, selected]);

  const selectedElement = useMemo(() => {
    if (!selected || selected.type !== "element") return null;

    for (const section of currentSections) {
      if (section.mode === "free") {
        const freeElement = section.freeElements.find(
          (item) => item.id === selected.id
        );
        if (freeElement) return freeElement;
      }

      for (const row of section.rows || []) {
        for (const column of row.columns) {
          const element = column.elements.find(
            (item) => item.id === selected.id
          );
          if (element) return element;
        }
      }
    }

    return null;
  }, [currentSections, selected]);

  const selectedTargetText = useMemo(() => {
    if (selectedColumn) return "Adding to selected column";
    if (selectedSection?.mode === "free") return "Adding to selected free design section";
    if (selectedSection?.mode === "auto") return "Adding to first column in selected section";
    if (currentSections.length > 0) return "Adding to latest section";
    return "No section selected — builder will create one";
  }, [selectedColumn, selectedSection, currentSections.length]);

  const updateActivePage = (updater) => {
    setWebsite((prev) => ({
      ...prev,
      pages: prev.pages.map((page) =>
        page.id === prev.activePageId ? updater(page) : page
      ),
    }));
  };

  const updateCurrentSections = (updater) => {
    updateActivePage((page) => {
      if (page.type === "flow") {
        return {
          ...page,
          steps: page.steps.map((step) =>
            step.id === page.activeStepId
              ? {
                  ...step,
                  sections: updater(step.sections),
                }
              : step
          ),
        };
      }

      return {
        ...page,
        sections: updater(page.sections),
      };
    });
  };

  const addStandardPage = () => {
    setWebsite((prev) => {
      const page = createNormalPage(prev.pages);

      setSelected({ type: "page", id: page.id });

      return {
        ...prev,
        activePageId: page.id,
        pages: [...prev.pages, page],
      };
    });

    setValidationErrors({});
  };

  const addFlowPage = () => {
    setWebsite((prev) => {
      const page = createFlowPage(prev.pages);

      setSelected({ type: "page", id: page.id });

      return {
        ...prev,
        activePageId: page.id,
        pages: [...prev.pages, page],
      };
    });

    setValidationErrors({});
  };

  const selectPage = (pageId) => {
    setWebsite((prev) => ({
      ...prev,
      activePageId: pageId,
    }));

    setSelected({ type: "page", id: pageId });
    setValidationErrors({});
  };

  const updatePageField = (key, value) => {
    updateActivePage((page) => ({
      ...page,
      [key]: value,
    }));
  };

  const deleteActivePage = () => {
    if (website.pages.length <= 1) {
      alert("You need at least one page.");
      return;
    }

    const currentPageId = website.activePageId;
    const nextPage = website.pages.find((page) => page.id !== currentPageId);

    setWebsite((prev) => ({
      ...prev,
      activePageId: nextPage.id,
      pages: prev.pages.filter((page) => page.id !== currentPageId),
    }));

    setSelected({ type: "page", id: nextPage.id });
  };

  const addStep = () => {
    if (!activePage || activePage.type !== "flow") return;

    const nextStepNumber = activePage.steps.length + 1;
    const step = {
      id: createId("step"),
      name: `Step ${nextStepNumber}`,
      sections: [],
    };

    updateActivePage((page) => ({
      ...page,
      activeStepId: step.id,
      steps: [...page.steps, step],
    }));

    setSelected({ type: "step", id: step.id });
  };

  const selectStep = (stepId) => {
    updateActivePage((page) => ({
      ...page,
      activeStepId: stepId,
    }));

    setSelected({ type: "step", id: stepId });
    setValidationErrors({});
  };

  const updateActiveStepField = (key, value) => {
    if (!activePage || activePage.type !== "flow") return;

    updateActivePage((page) => ({
      ...page,
      steps: page.steps.map((step) =>
        step.id === page.activeStepId ? { ...step, [key]: value } : step
      ),
    }));
  };

  const deleteActiveStep = () => {
    if (!activePage || activePage.type !== "flow") return;

    if (activePage.steps.length <= 1) {
      alert("A flow needs at least one step.");
      return;
    }

    const currentStepId = activePage.activeStepId;
    const nextStep = activePage.steps.find((step) => step.id !== currentStepId);

    updateActivePage((page) => ({
      ...page,
      activeStepId: nextStep.id,
      steps: page.steps.filter((step) => step.id !== currentStepId),
    }));

    setSelected({ type: "step", id: nextStep.id });
  };

  const addSection = (preset) => {
    const section = createSectionPreset(preset);

    updateCurrentSections((sections) => [...sections, section]);

    setSelected({ type: "section", id: section.id });
  };

  const deleteSelectedSection = () => {
    if (!selectedSection) return;

    updateCurrentSections((sections) =>
      sections.filter((section) => section.id !== selectedSection.id)
    );

    setSelected({
      type: activePage.type === "flow" ? "step" : "page",
      id: activePage.type === "flow" ? activePage.activeStepId : activePage.id,
    });
  };

  const updateSelectedSectionLayout = (key, value) => {
    if (!selectedSection) return;

    updateCurrentSections((sections) =>
      sections.map((section) =>
        section.id === selectedSection.id
          ? {
              ...section,
              layout: {
                ...section.layout,
                [key]: value,
              },
            }
          : section
      )
    );
  };

  const updateSelectedColumnLayout = (key, value) => {
    if (!selectedColumn) return;

    updateCurrentSections((sections) =>
      sections.map((section) => ({
        ...section,
        rows: (section.rows || []).map((row) => ({
          ...row,
          columns: row.columns.map((column) =>
            column.id === selectedColumn.id
              ? {
                  ...column,
                  layout: {
                    ...column.layout,
                    [key]: value,
                  },
                }
              : column
          ),
        })),
      }))
    );
  };

  const addElementToColumn = (columnId, type) => {
    const element = defaultElement(type);

    updateCurrentSections((sections) =>
      sections.map((section) => ({
        ...section,
        rows: (section.rows || []).map((row) => ({
          ...row,
          columns: row.columns.map((column) =>
            column.id === columnId
              ? {
                  ...column,
                  elements: [...column.elements, element],
                }
              : column
          ),
        })),
      }))
    );

    setSelected({ type: "element", id: element.id });
  };

  const addElementToFreeSection = (sectionId, type) => {
    const element = {
      ...defaultElement(type),
      mode: "free",
    };

    updateCurrentSections((sections) =>
      sections.map((section) =>
        section.id === sectionId
          ? {
              ...section,
              freeElements: [...section.freeElements, element],
            }
          : section
      )
    );

    setSelected({ type: "element", id: element.id });
  };

  const smartAddElement = (type) => {
    setQuickAddOpen(false);

    if (selectedColumn) {
      addElementToColumn(selectedColumn.id, type);
      return;
    }

    if (selectedSection?.mode === "free") {
      addElementToFreeSection(selectedSection.id, type);
      return;
    }

    if (selectedSection?.mode === "auto") {
      const firstColumn = selectedSection.rows?.[0]?.columns?.[0];
      if (firstColumn) {
        addElementToColumn(firstColumn.id, type);
        return;
      }
    }

    const latestSection = currentSections[currentSections.length - 1];

    if (latestSection?.mode === "free") {
      addElementToFreeSection(latestSection.id, type);
      return;
    }

    const latestColumn = latestSection?.rows?.[0]?.columns?.[0];

    if (latestColumn) {
      addElementToColumn(latestColumn.id, type);
      return;
    }

    const newSection = createAutoSection("Quick Start Section");
    const newElement = defaultElement(type);

    newSection.rows[0].columns[0].elements = [newElement];

    updateCurrentSections((sections) => [...sections, newSection]);
    setSelected({ type: "element", id: newElement.id });
  };

  const clearSelectedColumn = () => {
    if (!selectedColumn) return;

    updateCurrentSections((sections) =>
      sections.map((section) => ({
        ...section,
        rows: (section.rows || []).map((row) => ({
          ...row,
          columns: row.columns.map((column) =>
            column.id === selectedColumn.id
              ? {
                  ...column,
                  elements: [],
                }
              : column
          ),
        })),
      }))
    );
  };

  const updateSelectedElement = (updates) => {
    if (!selectedElement) return;

    updateCurrentSections((sections) =>
      sections.map((section) => {
        if (section.mode === "free") {
          return {
            ...section,
            freeElements: section.freeElements.map((element) =>
              element.id === selectedElement.id
                ? {
                    ...element,
                    ...updates,
                  }
                : element
            ),
          };
        }

        return {
          ...section,
          rows: (section.rows || []).map((row) => ({
            ...row,
            columns: row.columns.map((column) => ({
              ...column,
              elements: column.elements.map((element) =>
                element.id === selectedElement.id
                  ? {
                      ...element,
                      ...updates,
                    }
                  : element
              ),
            })),
          })),
        };
      })
    );
  };

  const updateSelectedElementStyle = (key, value) => {
    if (!selectedElement) return;

    updateSelectedElement({
      styles: {
        ...selectedElement.styles,
        [key]: value,
      },
    });
  };

  const updateSelectedElementValidation = (key, value) => {
    if (!selectedElement) return;

    updateSelectedElement({
      validation: {
        ...selectedElement.validation,
        [key]: value,
      },
    });
  };

  const updateSelectedElementPosition = (key, value) => {
    if (!selectedElement) return;

    const currentPosition =
      selectedElement.position?.[viewportMode] || createPosition()[viewportMode];

    updateSelectedElement({
      position: {
        ...selectedElement.position,
        [viewportMode]: {
          ...currentPosition,
          [key]: Number(value),
        },
      },
    });
  };

  const deleteSelectedElement = () => {
    if (!selectedElement) return;

    updateCurrentSections((sections) =>
      sections.map((section) => {
        if (section.mode === "free") {
          return {
            ...section,
            freeElements: section.freeElements.filter(
              (element) => element.id !== selectedElement.id
            ),
          };
        }

        return {
          ...section,
          rows: (section.rows || []).map((row) => ({
            ...row,
            columns: row.columns.map((column) => ({
              ...column,
              elements: column.elements.filter(
                (element) => element.id !== selectedElement.id
              ),
            })),
          })),
        };
      })
    );

    setSelected({
      type: activePage.type === "flow" ? "step" : "page",
      id: activePage.type === "flow" ? activePage.activeStepId : activePage.id,
    });
  };

  const updateOptions = (rawValue) => {
    const options = rawValue
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);

    updateSelectedElement({ options });
  };

  const setFieldValue = (fieldKey, value) => {
    setFormValues((prev) => ({
      ...prev,
      [fieldKey]: value,
    }));

    setValidationErrors((prev) => {
      const next = { ...prev };
      delete next[fieldKey];
      return next;
    });
  };

  const collectStepFields = (step) => {
    const fields = [];

    for (const section of step.sections) {
      if (section.mode === "free") {
        for (const element of section.freeElements || []) {
          if (element.fieldKey) fields.push(element);
        }
      }

      for (const row of section.rows || []) {
        for (const column of row.columns) {
          for (const element of column.elements) {
            if (element.fieldKey) fields.push(element);
          }
        }
      }
    }

    return fields;
  };

  const validateStep = (step) => {
    const fields = collectStepFields(step);
    const errors = {};

    fields.forEach((field) => {
      const isRequired = field.validation?.required;
      if (!isRequired) return;

      const value = formValues[field.fieldKey];

      if (field.type === "checkbox") {
        if (value !== true) {
          errors[field.fieldKey] =
            field.validation?.message || "This checkbox must be checked.";
        }
        return;
      }

      if (value === undefined || value === null || String(value).trim() === "") {
        errors[field.fieldKey] =
          field.validation?.message || "This field is required.";
      }
    });

    setValidationErrors(errors);

    return Object.keys(errors).length === 0;
  };

  const goToNextStep = () => {
    if (!activePage || activePage.type !== "flow" || !activeStep) return;

    if (activePage.flowSettings.requireStepValidation) {
      const isValid = validateStep(activeStep);
      if (!isValid) return;
    }

    const currentIndex = activePage.steps.findIndex(
      (step) => step.id === activePage.activeStepId
    );

    if (currentIndex >= activePage.steps.length - 1) {
      alert("Flow submitted successfully. Data is ready for backend.");
      console.log("Flow values:", formValues);
      return;
    }

    const nextStep = activePage.steps[currentIndex + 1];

    updateActivePage((page) => ({
      ...page,
      activeStepId: nextStep.id,
    }));

    setSelected({ type: "step", id: nextStep.id });
    setValidationErrors({});
  };

  const goToPreviousStep = () => {
    if (!activePage || activePage.type !== "flow") return;

    const currentIndex = activePage.steps.findIndex(
      (step) => step.id === activePage.activeStepId
    );

    if (currentIndex <= 0) return;

    const previousStep = activePage.steps[currentIndex - 1];

    updateActivePage((page) => ({
      ...page,
      activeStepId: previousStep.id,
    }));

    setSelected({ type: "step", id: previousStep.id });
    setValidationErrors({});
  };

  const getElementStyle = (element) => {
    const alignSelf = element.styles?.alignSelf;
    const offsetX = Number(element.styles?.offsetX || 0);

    return {
      ...element.styles,
      alignSelf: alignSelf === "auto" ? undefined : alignSelf,
      transform: offsetX ? `translateX(${offsetX}px)` : undefined,
    };
  };

  const getFreeElementStyle = (element) => {
    const position =
      element.position?.[viewportMode] || createPosition()[viewportMode];

    return {
      ...element.styles,
      position: "absolute",
      left: `${position.x}px`,
      top: `${position.y}px`,
      width: `${position.width}px`,
      minHeight: `${position.height}px`,
      transform: undefined,
    };
  };

  const startDrag = (event, element) => {
    if (previewMode || element.mode !== "free") return;

    event.stopPropagation();
    event.preventDefault();

    const position =
      element.position?.[viewportMode] || createPosition()[viewportMode];

    setSelected({ type: "element", id: element.id });

    setDragState({
      elementId: element.id,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startX: position.x,
      startY: position.y,
    });
  };

  const handleMouseMove = (event) => {
    if (!dragState || !selectedElement) return;

    const deltaX = event.clientX - dragState.startClientX;
    const deltaY = event.clientY - dragState.startClientY;

    const currentPosition =
      selectedElement.position?.[viewportMode] ||
      createPosition()[viewportMode];

    updateSelectedElement({
      position: {
        ...selectedElement.position,
        [viewportMode]: {
          ...currentPosition,
          x: Math.max(0, dragState.startX + deltaX),
          y: Math.max(0, dragState.startY + deltaY),
        },
      },
    });
  };

  const stopDrag = () => {
    setDragState(null);
  };

  const getResponsiveWarnings = () => {
    const warnings = [];

    currentSections.forEach((section) => {
      if (section.mode !== "free") return;

      const frameWidth = viewportWidths[viewportMode];
      const frameHeight = Number(section.layout.minHeight || 560);

      section.freeElements.forEach((element) => {
        const position = element.position?.[viewportMode];
        if (!position) return;

        if (position.x + position.width > frameWidth) {
          warnings.push(
            `${getElementLabel(element.type)} "${element.content}" is outside the ${viewportMode} frame.`
          );
        }

        if (position.y + position.height > frameHeight) {
          warnings.push(
            `${getElementLabel(element.type)} "${element.content}" is below the section height.`
          );
        }
      });

      section.freeElements.forEach((a, index) => {
        const aPos = a.position?.[viewportMode];
        if (!aPos) return;

        section.freeElements.slice(index + 1).forEach((b) => {
          const bPos = b.position?.[viewportMode];
          if (!bPos) return;

          const overlaps =
            aPos.x < bPos.x + bPos.width &&
            aPos.x + aPos.width > bPos.x &&
            aPos.y < bPos.y + bPos.height &&
            aPos.y + aPos.height > bPos.y;

          if (overlaps) {
            warnings.push(
              `${getElementLabel(a.type)} overlaps with ${getElementLabel(
                b.type
              )} on ${viewportMode}.`
            );
          }
        });
      });
    });

    return warnings;
  };

  const warnings = getResponsiveWarnings();
  const validationErrorMessages = Object.values(validationErrors);

  const renderElement = (element, isFree = false) => {
    const isSelected = selected.type === "element" && selected.id === element.id;
    const fieldError = element.fieldKey ? validationErrors[element.fieldKey] : "";

    const commonProps = {
      className: `builder-element builder-element-${element.type} ${
        isSelected ? "is-selected" : ""
      } ${fieldError ? "has-error" : ""}`,
      style: isFree ? getFreeElementStyle(element) : getElementStyle(element),
      onMouseDown: (event) => startDrag(event, element),
      onClick: (event) => {
        event.stopPropagation();
        if (!previewMode) setSelected({ type: "element", id: element.id });
      },
    };

    const errorNode = fieldError ? (
      <span className="field-error">{fieldError}</span>
    ) : null;

    if (element.type === "heading") {
      return (
        <h1 key={element.id} {...commonProps}>
          {element.content}
        </h1>
      );
    }

    if (element.type === "text") {
      return (
        <p key={element.id} {...commonProps}>
          {element.content}
        </p>
      );
    }

    if (element.type === "button") {
      return (
        <button key={element.id} type="button" {...commonProps}>
          {element.content}
        </button>
      );
    }

    if (element.type === "image") {
      return (
        <img
          key={element.id}
          {...commonProps}
          src={element.content}
          alt="Builder content"
        />
      );
    }

    if (element.type === "input") {
      return (
        <label key={element.id} {...commonProps}>
          <span>
            {element.content}
            {element.validation?.required ? " *" : ""}
          </span>
          <input
            type={element.inputType || "text"}
            placeholder={element.placeholder || ""}
            value={formValues[element.fieldKey] || ""}
            onChange={(event) =>
              setFieldValue(element.fieldKey, event.target.value)
            }
            onMouseDown={(event) => event.stopPropagation()}
            readOnly={!previewMode}
          />
          {errorNode}
        </label>
      );
    }

    if (element.type === "textarea") {
      return (
        <label key={element.id} {...commonProps}>
          <span>
            {element.content}
            {element.validation?.required ? " *" : ""}
          </span>
          <textarea
            placeholder={element.placeholder || ""}
            value={formValues[element.fieldKey] || ""}
            onChange={(event) =>
              setFieldValue(element.fieldKey, event.target.value)
            }
            onMouseDown={(event) => event.stopPropagation()}
            readOnly={!previewMode}
          />
          {errorNode}
        </label>
      );
    }

    if (element.type === "checkbox") {
      return (
        <label key={element.id} {...commonProps}>
          <input
            type="checkbox"
            checked={formValues[element.fieldKey] || false}
            onChange={(event) =>
              setFieldValue(element.fieldKey, event.target.checked)
            }
            onMouseDown={(event) => event.stopPropagation()}
            disabled={!previewMode}
          />
          <span>
            {element.content}
            {element.validation?.required ? " *" : ""}
          </span>
          {errorNode}
        </label>
      );
    }

    if (element.type === "select") {
      return (
        <label key={element.id} {...commonProps}>
          <span>
            {element.content}
            {element.validation?.required ? " *" : ""}
          </span>
          <select
            value={formValues[element.fieldKey] || ""}
            onChange={(event) =>
              setFieldValue(element.fieldKey, event.target.value)
            }
            onMouseDown={(event) => event.stopPropagation()}
            disabled={!previewMode}
          >
            <option value="">Select...</option>
            {(element.options || []).map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          {errorNode}
        </label>
      );
    }

    if (element.type === "radio") {
      return (
        <div key={element.id} {...commonProps}>
          <strong>
            {element.content}
            {element.validation?.required ? " *" : ""}
          </strong>

          <div className="radio-options">
            {(element.options || []).map((option) => (
              <label key={option}>
                <input
                  type="radio"
                  name={element.fieldKey}
                  checked={formValues[element.fieldKey] === option}
                  onChange={() => setFieldValue(element.fieldKey, option)}
                  disabled={!previewMode}
                />
                <span>{option}</span>
              </label>
            ))}
          </div>

          {errorNode}
        </div>
      );
    }

    return (
      <div key={element.id} {...commonProps}>
        {element.content.split("\n").map((line, index) => (
          <span key={`${element.id}_line_${index}`}>{line}</span>
        ))}
      </div>
    );
  };

  const renderSections = () => {
    if (!currentSections.length) {
      return (
        <div className="empty-builder-state">
          <h2>Start creating visually</h2>
          <p>
            Add a title, button, form field, or section. The builder will place it
            for you.
          </p>
          <button
            type="button"
            className="empty-state-action"
            onClick={(event) => {
              event.stopPropagation();
              smartAddElement("heading");
            }}
          >
            + Add First Title
          </button>
        </div>
      );
    }

    return currentSections.map((section) => {
      const sectionSelected =
        selected.type === "section" && selected.id === section.id;

      if (section.mode === "free") {
        return (
          <section
            key={section.id}
            className={`site-section free-canvas-section width-${section.layout.width} ${
              sectionSelected ? "is-selected" : ""
            }`}
            style={{
              backgroundColor: section.layout.background,
              minHeight: `${section.layout.minHeight || 560}px`,
            }}
            onClick={(event) => {
              event.stopPropagation();
              if (!previewMode) setSelected({ type: "section", id: section.id });
            }}
          >
            <div
              className="free-canvas-frame"
              style={{
                width: `${viewportWidths[viewportMode]}px`,
                minHeight: `${section.layout.minHeight || 560}px`,
              }}
            >
              {section.freeElements.map((element) =>
                renderElement(element, true)
              )}
            </div>

            {!previewMode && (
              <button
                type="button"
                className="add-free-element-button"
                onClick={(event) => {
                  event.stopPropagation();
                  addElementToFreeSection(section.id, "button");
                }}
              >
                + Add Button
              </button>
            )}
          </section>
        );
      }

      return (
        <section
          key={section.id}
          className={`site-section width-${section.layout.width} padding-${section.layout.paddingY} ${
            sectionSelected ? "is-selected" : ""
          }`}
          style={{
            backgroundColor: section.layout.background,
          }}
          onClick={(event) => {
            event.stopPropagation();
            if (!previewMode) setSelected({ type: "section", id: section.id });
          }}
        >
          {(section.rows || []).map((row) => (
            <div
              key={row.id}
              className={`site-row columns-${row.layout.columns} align-${row.layout.align} gap-${row.layout.gap}`}
            >
              {row.columns.map((column) => {
                const columnSelected =
                  selected.type === "column" && selected.id === column.id;

                return (
                  <div
                    key={column.id}
                    className={`site-column column-align-${column.layout.align} ${
                      columnSelected ? "is-selected" : ""
                    }`}
                    onClick={(event) => {
                      event.stopPropagation();
                      if (!previewMode) {
                        setSelected({ type: "column", id: column.id });
                      }
                    }}
                  >
                    {column.elements.map((element) =>
                      renderElement(element, false)
                    )}

                    {!previewMode && column.elements.length === 0 && (
                      <div className="empty-column">
                        Click here or use quick add
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
        </section>
      );
    });
  };

  const exportJSON = () => {
    console.log(JSON.stringify(website, null, 2));
    alert("Builder JSON exported to console.");
  };

  const activeStepIndex =
    activePage?.type === "flow"
      ? activePage.steps.findIndex((step) => step.id === activePage.activeStepId)
      : -1;

  return (
    <>
      <section className="builder-mobile-blocker">
        <div>
          <h1>Page Builder is available on tablets and desktops only.</h1>
          <p>
            Please open this tool on a larger screen to use the builder safely.
          </p>
        </div>
      </section>

      <div
        className={`page-builder builder-desktop-shell ${
          previewMode ? "preview-mode" : ""
        }`}
        onMouseMove={handleMouseMove}
        onMouseUp={stopDrag}
        onMouseLeave={stopDrag}
      >
        <header className="builder-topbar">
          <div>
            <h1>{website.name}</h1>
            <p>Build pages, forms, workflows, and responsive sections visually</p>
          </div>

          <div className="builder-topbar-actions">
            <div className="viewport-switcher">
              {["desktop", "tablet", "mobile"].map((mode) => (
                <button
                  key={mode}
                  type="button"
                  className={viewportMode === mode ? "active" : ""}
                  onClick={() => setViewportMode(mode)}
                >
                  {mode}
                </button>
              ))}
            </div>

            <button type="button" onClick={() => setPreviewMode((prev) => !prev)}>
              {previewMode ? "Exit Preview" : "Preview"}
            </button>

            <button type="button" onClick={exportJSON}>
              Export JSON
            </button>
          </div>
        </header>

        <div className="builder-layout">
          {!previewMode && (
            <aside className="builder-sidebar">
              <section className="builder-panel compact-panel">
                <h2>Pages</h2>

                <select
                  value={activePage?.id || ""}
                  onChange={(event) => selectPage(event.target.value)}
                >
                  {website.pages.map((page) => (
                    <option key={page.id} value={page.id}>
                      {page.name}
                    </option>
                  ))}
                </select>

                <div className="compact-actions">
                  <button type="button" onClick={addStandardPage}>
                    + Page
                  </button>
                  <button type="button" onClick={addFlowPage}>
                    + Flow
                  </button>
                </div>
              </section>

              {activePage?.type === "flow" && (
                <section className="builder-panel compact-panel">
                  <h2>Flow Steps</h2>

                  <select
                    value={activePage.activeStepId}
                    onChange={(event) => selectStep(event.target.value)}
                  >
                    {activePage.steps.map((step, index) => (
                      <option key={step.id} value={step.id}>
                        {index + 1}. {step.name}
                      </option>
                    ))}
                  </select>

                  <div className="compact-actions">
                    <button type="button" onClick={addStep}>
                      + Step
                    </button>
                  </div>
                </section>
              )}

              <section className="builder-panel compact-panel">
                <h2>Quick Add</h2>

                <p className="target-helper">{selectedTargetText}</p>

                <div className="builder-dropdown">
                  <button
                    type="button"
                    className={`builder-dropdown-trigger ${
                      quickAddOpen ? "is-open" : ""
                    }`}
                    onClick={() => setQuickAddOpen((prev) => !prev)}
                  >
                    <span>Add element</span>
                    <span className="dropdown-chevron">
                      {quickAddOpen ? "⌃" : "⌄"}
                    </span>
                  </button>

                  {quickAddOpen && (
                    <div className="builder-dropdown-menu">
                      {["Content", "Form Fields"].map((group) => (
                        <div key={group} className="builder-dropdown-group">
                          <span>{group}</span>

                          {elementTypes
                            .filter((item) => item.group === group)
                            .map((element) => (
                              <button
                                key={element.value}
                                type="button"
                                onClick={() => smartAddElement(element.value)}
                              >
                                {element.label}
                              </button>
                            ))}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </section>

              <section className="builder-panel compact-panel">
                <h2>Sections</h2>

                <select
                  value={selectedSectionPreset}
                  onChange={(event) =>
                    setSelectedSectionPreset(event.target.value)
                  }
                >
                  {sectionPresets.map((preset) => (
                    <option key={preset.value} value={preset.value}>
                      {preset.label}
                    </option>
                  ))}
                </select>

                <button
                  type="button"
                  className="full-width-action"
                  onClick={() => addSection(selectedSectionPreset)}
                >
                  + Add Section
                </button>
              </section>

              {warnings.length > 0 && (
                <section className="builder-panel warning-panel">
                  <h2>Responsive Warnings</h2>
                  {warnings.map((warning, index) => (
                    <p key={`${warning}_${index}`}>{warning}</p>
                  ))}
                </section>
              )}
            </aside>
          )}

          <main
            className="builder-canvas-shell"
            onClick={() =>
              !previewMode &&
              setSelected({
                type: activePage?.type === "flow" ? "step" : "page",
                id:
                  activePage?.type === "flow"
                    ? activePage.activeStepId
                    : activePage.id,
              })
            }
          >
            <div
              className={`builder-canvas viewport-${viewportMode}`}
              style={{
                maxWidth: previewMode
                  ? `${viewportWidths[viewportMode]}px`
                  : undefined,
              }}
            >
              {validationErrorMessages.length > 0 && (
                <div className="main-validation-banner">
                  <div>
                    <strong>Please complete the required fields</strong>
                    <p>Fix these issues before continuing:</p>
                  </div>

                  <ul>
                    {validationErrorMessages.map((message, index) => (
                      <li key={`${message}_${index}`}>{message}</li>
                    ))}
                  </ul>
                </div>
              )}

              {activePage?.type === "flow" && (
                <div className="flow-runtime-header">
                  {activePage.flowSettings.showProgress && (
                    <div className="flow-progress">
                      <span>
                        Step {activeStepIndex + 1} of {activePage.steps.length}
                      </span>
                      <strong>{activeStep?.name}</strong>
                    </div>
                  )}
                </div>
              )}

              {renderSections()}

              {activePage?.type === "flow" && (
                <div className="flow-navigation">
                  {activePage.flowSettings.allowBack && (
                    <button
                      type="button"
                      onClick={goToPreviousStep}
                      disabled={activeStepIndex <= 0}
                    >
                      Back
                    </button>
                  )}

                  <button type="button" onClick={goToNextStep}>
                    {activeStepIndex >= activePage.steps.length - 1
                      ? "Submit"
                      : "Next"}
                  </button>
                </div>
              )}
            </div>
          </main>

          {!previewMode && (
            <aside className="builder-inspector">
              <h2>Inspector</h2>

              {selected.type === "page" && activePage && (
                <div className="inspector-group">
                  <h3>Page Settings</h3>

                  <label>
                    Page Name
                    <input
                      value={activePage.name}
                      onChange={(event) =>
                        updatePageField("name", event.target.value)
                      }
                    />
                  </label>

                  <label>
                    Slug
                    <input
                      value={activePage.slug}
                      onChange={(event) =>
                        updatePageField("slug", event.target.value)
                      }
                    />
                  </label>

                  <label>
                    Page Type
                    <input value={pageTypeLabels[activePage.type]} readOnly />
                  </label>

                  <button
                    type="button"
                    className="danger-button"
                    onClick={deleteActivePage}
                  >
                    Delete Page
                  </button>
                </div>
              )}

              {selected.type === "step" &&
                activePage?.type === "flow" &&
                activeStep && (
                  <div className="inspector-group">
                    <h3>Step Settings</h3>

                    <label>
                      Step Name
                      <input
                        value={activeStep.name}
                        onChange={(event) =>
                          updateActiveStepField("name", event.target.value)
                        }
                      />
                    </label>

                    <button
                      type="button"
                      className="danger-button"
                      onClick={deleteActiveStep}
                    >
                      Delete Step
                    </button>
                  </div>
                )}

              {selectedSection && (
                <div className="inspector-group">
                  <h3>Section Settings</h3>

                  <label>
                    Mode
                    <input
                      value={
                        selectedSection.mode === "free"
                          ? "Free Design"
                          : "Auto Layout"
                      }
                      readOnly
                    />
                  </label>

                  <label>
                    Width
                    <select
                      value={selectedSection.layout.width}
                      onChange={(event) =>
                        updateSelectedSectionLayout("width", event.target.value)
                      }
                    >
                      <option value="small">Small</option>
                      <option value="medium">Medium</option>
                      <option value="large">Large</option>
                      <option value="full">Full</option>
                    </select>
                  </label>

                  {selectedSection.mode === "free" && (
                    <>
                      <label>
                        Section Height
                        <input
                          type="number"
                          value={selectedSection.layout.minHeight || 560}
                          onChange={(event) =>
                            updateSelectedSectionLayout(
                              "minHeight",
                              Number(event.target.value)
                            )
                          }
                        />
                      </label>

                      <label>
                        Add to Canvas
                        <select
                          defaultValue=""
                          onChange={(event) => {
                            if (!event.target.value) return;
                            addElementToFreeSection(
                              selectedSection.id,
                              event.target.value
                            );
                            event.target.value = "";
                          }}
                        >
                          <option value="">Choose element</option>
                          {elementTypes.map((item) => (
                            <option key={item.value} value={item.value}>
                              {item.label}
                            </option>
                          ))}
                        </select>
                      </label>
                    </>
                  )}

                  {selectedSection.mode !== "free" && (
                    <label>
                      Padding
                      <select
                        value={selectedSection.layout.paddingY}
                        onChange={(event) =>
                          updateSelectedSectionLayout(
                            "paddingY",
                            event.target.value
                          )
                        }
                      >
                        <option value="small">Small</option>
                        <option value="medium">Medium</option>
                        <option value="large">Large</option>
                      </select>
                    </label>
                  )}

                  <label>
                    Background
                    <input
                      type="color"
                      value={selectedSection.layout.background}
                      onChange={(event) =>
                        updateSelectedSectionLayout(
                          "background",
                          event.target.value
                        )
                      }
                    />
                  </label>

                  <button
                    type="button"
                    className="danger-button"
                    onClick={deleteSelectedSection}
                  >
                    Delete Section
                  </button>
                </div>
              )}

              {selectedColumn && (
                <div className="inspector-group">
                  <h3>Column Settings</h3>

                  <label>
                    Content Align
                    <select
                      value={selectedColumn.layout.align}
                      onChange={(event) =>
                        updateSelectedColumnLayout("align", event.target.value)
                      }
                    >
                      <option value="left">Left</option>
                      <option value="center">Center</option>
                      <option value="right">Right</option>
                    </select>
                  </label>

                  <button
                    type="button"
                    className="danger-button"
                    onClick={clearSelectedColumn}
                  >
                    Clear Column Elements
                  </button>
                </div>
              )}

              {selectedElement && (
                <div className="inspector-group">
                  <h3>{getElementLabel(selectedElement.type)} Settings</h3>

                  <label>
                    Text / Label
                    {selectedElement.type === "image" ? (
                      <input
                        value={selectedElement.content}
                        onChange={(event) =>
                          updateSelectedElement({ content: event.target.value })
                        }
                      />
                    ) : (
                      <textarea
                        value={selectedElement.content}
                        onChange={(event) =>
                          updateSelectedElement({ content: event.target.value })
                        }
                      />
                    )}
                  </label>

                  {(selectedElement.type === "input" ||
                    selectedElement.type === "textarea") && (
                    <label>
                      Placeholder
                      <input
                        value={selectedElement.placeholder || ""}
                        onChange={(event) =>
                          updateSelectedElement({
                            placeholder: event.target.value,
                          })
                        }
                      />
                    </label>
                  )}

                  {selectedElement.type === "input" && (
                    <label>
                      Answer Type
                      <select
                        value={selectedElement.inputType || "text"}
                        onChange={(event) =>
                          updateSelectedElement({ inputType: event.target.value })
                        }
                      >
                        <option value="text">Text</option>
                        <option value="email">Email</option>
                        <option value="password">Password</option>
                        <option value="number">Number</option>
                        <option value="tel">Phone</option>
                        <option value="date">Date</option>
                      </select>
                    </label>
                  )}

                  {(selectedElement.type === "select" ||
                    selectedElement.type === "radio") && (
                    <label>
                      Options
                      <textarea
                        value={(selectedElement.options || []).join("\n")}
                        onChange={(event) => updateOptions(event.target.value)}
                        placeholder={"Option 1\nOption 2\nOption 3\nOption 4"}
                      />
                      <small className="inspector-help">
                        Add one option per line. You can add as many options as needed.
                      </small>
                    </label>
                  )}

                  {selectedElement.fieldKey && (
                    <>
                      <label>
                        Data Name
                        <input
                          value={selectedElement.fieldKey}
                          onChange={(event) =>
                            updateSelectedElement({
                              fieldKey: event.target.value,
                            })
                          }
                        />
                      </label>

                      <label className="checkbox-control">
                        <input
                          type="checkbox"
                          checked={selectedElement.validation?.required || false}
                          onChange={(event) =>
                            updateSelectedElementValidation(
                              "required",
                              event.target.checked
                            )
                          }
                        />
                        Required field
                      </label>

                      <label>
                        Validation Message
                        <input
                          value={selectedElement.validation?.message || ""}
                          onChange={(event) =>
                            updateSelectedElementValidation(
                              "message",
                              event.target.value
                            )
                          }
                        />
                      </label>
                    </>
                  )}

                  {selectedElement.mode === "free" && (
                    <>
                      <label>
                        X Position
                        <input
                          type="number"
                          value={
                            selectedElement.position?.[viewportMode]?.x ||
                            createPosition()[viewportMode].x
                          }
                          onChange={(event) =>
                            updateSelectedElementPosition("x", event.target.value)
                          }
                        />
                      </label>

                      <label>
                        Y Position
                        <input
                          type="number"
                          value={
                            selectedElement.position?.[viewportMode]?.y ||
                            createPosition()[viewportMode].y
                          }
                          onChange={(event) =>
                            updateSelectedElementPosition("y", event.target.value)
                          }
                        />
                      </label>

                      <label>
                        Width
                        <input
                          type="number"
                          value={
                            selectedElement.position?.[viewportMode]?.width ||
                            createPosition()[viewportMode].width
                          }
                          onChange={(event) =>
                            updateSelectedElementPosition(
                              "width",
                              event.target.value
                            )
                          }
                        />
                      </label>

                      <label>
                        Height
                        <input
                          type="number"
                          value={
                            selectedElement.position?.[viewportMode]?.height ||
                            createPosition()[viewportMode].height
                          }
                          onChange={(event) =>
                            updateSelectedElementPosition(
                              "height",
                              event.target.value
                            )
                          }
                        />
                      </label>
                    </>
                  )}

                  {selectedElement.type !== "image" && (
                    <>
                      <label>
                        Text Color
                        <input
                          type="color"
                          value={selectedElement.styles.color || "#000000"}
                          onChange={(event) =>
                            updateSelectedElementStyle(
                              "color",
                              event.target.value
                            )
                          }
                        />
                      </label>

                      <label>
                        Font Size
                        <input
                          value={selectedElement.styles.fontSize || ""}
                          onChange={(event) =>
                            updateSelectedElementStyle(
                              "fontSize",
                              event.target.value
                            )
                          }
                          placeholder="16px"
                        />
                      </label>

                      <label>
                        Text Align
                        <select
                          value={selectedElement.styles.textAlign || "left"}
                          onChange={(event) =>
                            updateSelectedElementStyle(
                              "textAlign",
                              event.target.value
                            )
                          }
                        >
                          <option value="left">Left</option>
                          <option value="center">Center</option>
                          <option value="right">Right</option>
                        </select>
                      </label>
                    </>
                  )}

                  {["button", "card", "input", "textarea", "select"].includes(
                    selectedElement.type
                  ) && (
                    <label>
                      Background
                      <input
                        type="color"
                        value={selectedElement.styles.backgroundColor || "#ffffff"}
                        onChange={(event) =>
                          updateSelectedElementStyle(
                            "backgroundColor",
                            event.target.value
                          )
                        }
                      />
                    </label>
                  )}

                  <label>
                    Border Radius
                    <input
                      value={selectedElement.styles.borderRadius || ""}
                      onChange={(event) =>
                        updateSelectedElementStyle(
                          "borderRadius",
                          event.target.value
                        )
                      }
                      placeholder="12px"
                    />
                  </label>

                  <button
                    type="button"
                    className="danger-button"
                    onClick={deleteSelectedElement}
                  >
                    Delete Element
                  </button>
                </div>
              )}
            </aside>
          )}
        </div>
      </div>
    </>
  );
}