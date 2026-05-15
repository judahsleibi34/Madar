import { useMemo, useState } from "react";
import "../styles/admin/PageBuilder.css";

const createId = (prefix) => `${prefix}_${crypto.randomUUID()}`;

const createEmptyAction = () => ({
  type: "none",
  pageId: "",
  url: "",
});

const initialWebsite = {
  id: "site_1",
  name: "Madar Builder",
  activePageId: "home",
  pages: [
    {
      id: "home",
      name: "Home",
      slug: "/",
      parentId: null,
      sections: [
        {
          id: "section_hero",
          type: "section",
          name: "Hero Section",
          layout: {
            width: "large",
            background: "#f8fafc",
            paddingY: "large",
          },
          rows: [
            {
              id: "row_hero",
              layout: {
                columns: "2",
                align: "center",
                gap: "large",
              },
              columns: [
                {
                  id: "col_hero_left",
                  layout: {
                    align: "left",
                  },
                  elements: [
                    {
                      id: "heading_hero",
                      type: "heading",
                      content: "Build flexible digital systems",
                      styles: {
                        fontSize: "48px",
                        color: "#0f172a",
                        textAlign: "left",
                        alignSelf: "auto",
                        offsetX: 0,
                      },
                    },
                    {
                      id: "text_hero",
                      type: "text",
                      content:
                        "Create websites, forms, workflows, dashboards, exams, HR tools, finance screens, checkout flows, and more using structured responsive blocks.",
                      styles: {
                        fontSize: "18px",
                        color: "#475569",
                        textAlign: "left",
                        alignSelf: "auto",
                        offsetX: 0,
                      },
                    },
                    {
                      id: "button_hero",
                      type: "button",
                      content: "Start Building",
                      action: {
                        type: "internal",
                        pageId: "contact",
                        url: "",
                      },
                      styles: {
                        backgroundColor: "#2563eb",
                        color: "#ffffff",
                        borderRadius: "12px",
                        alignSelf: "auto",
                        offsetX: 0,
                      },
                    },
                  ],
                },
                {
                  id: "col_hero_right",
                  layout: {
                    align: "center",
                  },
                  elements: [
                    {
                      id: "card_hero",
                      type: "card",
                      content: "Builder System\nPages\nForms\nWorkflows\nManagement",
                      styles: {
                        backgroundColor: "#ffffff",
                        color: "#0f172a",
                        borderRadius: "24px",
                        alignSelf: "stretch",
                        offsetX: 0,
                      },
                    },
                  ],
                },
              ],
            },
          ],
        },
      ],
    },
    {
      id: "contact",
      name: "Contact",
      slug: "/contact",
      parentId: null,
      sections: [],
    },
  ],
};

const sectionPresets = [
  { label: "Hero Split", value: "heroSplit" },
  { label: "Centered CTA", value: "centeredCta" },
  { label: "Stats Row", value: "statsRow" },
  { label: "Management Header", value: "managementHeader" },
  { label: "Form Builder", value: "formBuilder" },
  { label: "Workflow Checklist", value: "workflowChecklist" },
];

const elementTypes = [
  { label: "Heading", value: "heading" },
  { label: "Text", value: "text" },
  { label: "Button", value: "button" },
  { label: "Image", value: "image" },
  { label: "Card", value: "card" },
  { label: "Input", value: "input" },
  { label: "Textarea", value: "textarea" },
  { label: "Checkbox", value: "checkbox" },
  { label: "Select", value: "select" },
  { label: "Radio Group", value: "radio" },
];

const defaultElement = (type) => {
  const base = {
    id: createId(type),
    type,
    content: "",
    styles: {
      alignSelf: "auto",
      offsetX: 0,
    },
  };

  if (type === "heading") {
    return {
      ...base,
      content: "New Heading",
      styles: {
        fontSize: "36px",
        color: "#0f172a",
        textAlign: "left",
        alignSelf: "auto",
        offsetX: 0,
      },
    };
  }

  if (type === "text") {
    return {
      ...base,
      content: "Write your text here.",
      styles: {
        fontSize: "16px",
        color: "#475569",
        textAlign: "left",
        alignSelf: "auto",
        offsetX: 0,
      },
    };
  }

  if (type === "button") {
    return {
      ...base,
      content: "Button",
      action: createEmptyAction(),
      styles: {
        backgroundColor: "#2563eb",
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
        color: "#0f172a",
        borderRadius: "16px",
        alignSelf: "stretch",
        offsetX: 0,
      },
    };
  }

  if (type === "input") {
    return {
      ...base,
      content: "Full name",
      placeholder: "Enter your full name",
      inputType: "text",
      required: false,
      styles: {
        color: "#0f172a",
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
      content: "Message",
      placeholder: "Write your message...",
      required: false,
      styles: {
        color: "#0f172a",
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
      content: "I agree to the terms",
      checked: false,
      required: false,
      styles: {
        color: "#0f172a",
        fontSize: "15px",
        alignSelf: "auto",
        offsetX: 0,
      },
    };
  }

  if (type === "select") {
    return {
      ...base,
      content: "Choose an option",
      options: ["Option 1", "Option 2", "Option 3"],
      required: false,
      styles: {
        color: "#0f172a",
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
      content: "Select one",
      options: ["Choice A", "Choice B", "Choice C"],
      selectedOption: "",
      required: false,
      styles: {
        color: "#0f172a",
        fontSize: "15px",
        alignSelf: "auto",
        offsetX: 0,
      },
    };
  }

  return base;
};

const createSectionPreset = (preset) => {
  if (preset === "centeredCta") {
    return {
      id: createId("section"),
      type: "section",
      name: "Centered CTA",
      layout: {
        width: "medium",
        background: "#eff6ff",
        paddingY: "large",
      },
      rows: [
        {
          id: createId("row"),
          layout: {
            columns: "1",
            align: "center",
            gap: "medium",
          },
          columns: [
            {
              id: createId("column"),
              layout: {
                align: "center",
              },
              elements: [
                {
                  ...defaultElement("heading"),
                  content: "Ready to build your system?",
                  styles: {
                    fontSize: "42px",
                    color: "#0f172a",
                    textAlign: "center",
                    alignSelf: "auto",
                    offsetX: 0,
                  },
                },
                {
                  ...defaultElement("text"),
                  content:
                    "Create pages, forms, and workflows using responsive professional blocks.",
                  styles: {
                    fontSize: "18px",
                    color: "#475569",
                    textAlign: "center",
                    alignSelf: "auto",
                    offsetX: 0,
                  },
                },
                defaultElement("button"),
              ],
            },
          ],
        },
      ],
    };
  }

  if (preset === "statsRow") {
    return {
      id: createId("section"),
      type: "section",
      name: "Stats Row",
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
    };
  }

  if (preset === "managementHeader") {
    return {
      id: createId("section"),
      type: "section",
      name: "Management Header",
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
                    color: "#0f172a",
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
              elements: [
                {
                  ...defaultElement("button"),
                  content: "Add User",
                },
              ],
            },
          ],
        },
      ],
    };
  }

  if (preset === "formBuilder") {
    return {
      id: createId("section"),
      type: "section",
      name: "Form Builder",
      layout: {
        width: "medium",
        background: "#f8fafc",
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
              elements: [
                {
                  ...defaultElement("heading"),
                  content: "General Form",
                },
                {
                  ...defaultElement("input"),
                  content: "Full name",
                  placeholder: "Enter your full name",
                },
                {
                  ...defaultElement("input"),
                  content: "Email address",
                  placeholder: "Enter your email",
                  inputType: "email",
                },
                {
                  ...defaultElement("select"),
                  content: "Department",
                  options: ["HR", "Finance", "Operations", "Education"],
                },
                {
                  ...defaultElement("checkbox"),
                  content: "I confirm the information is correct",
                },
                {
                  ...defaultElement("button"),
                  content: "Submit",
                },
              ],
            },
          ],
        },
      ],
    };
  }

  if (preset === "workflowChecklist") {
    return {
      id: createId("section"),
      type: "section",
      name: "Workflow Checklist",
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
              elements: [
                {
                  ...defaultElement("heading"),
                  content: "Process Checklist",
                },
                {
                  ...defaultElement("checkbox"),
                  content: "Step 1 completed",
                },
                {
                  ...defaultElement("checkbox"),
                  content: "Step 2 reviewed",
                },
                {
                  ...defaultElement("checkbox"),
                  content: "Step 3 approved",
                },
                {
                  ...defaultElement("button"),
                  content: "Continue Process",
                },
              ],
            },
          ],
        },
      ],
    };
  }

  return {
    id: createId("section"),
    type: "section",
    name: "Hero Split",
    layout: {
      width: "large",
      background: "#f8fafc",
      paddingY: "large",
    },
    rows: [
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
    ],
  };
};

export default function PageBuilder() {
  const [website, setWebsite] = useState(initialWebsite);
  const [selected, setSelected] = useState({
    type: "page",
    id: initialWebsite.activePageId,
  });
  const [previewMode, setPreviewMode] = useState(false);

  const activePage = useMemo(() => {
    return website.pages.find((page) => page.id === website.activePageId);
  }, [website]);

  const selectedSection = useMemo(() => {
    if (!activePage || selected.type !== "section") return null;
    return activePage.sections.find((section) => section.id === selected.id);
  }, [activePage, selected]);

  const selectedColumn = useMemo(() => {
    if (!activePage || selected.type !== "column") return null;

    for (const section of activePage.sections) {
      for (const row of section.rows) {
        const column = row.columns.find((item) => item.id === selected.id);
        if (column) return column;
      }
    }

    return null;
  }, [activePage, selected]);

  const selectedElement = useMemo(() => {
    if (!activePage || selected.type !== "element") return null;

    for (const section of activePage.sections) {
      for (const row of section.rows) {
        for (const column of row.columns) {
          const element = column.elements.find((item) => item.id === selected.id);
          if (element) return element;
        }
      }
    }

    return null;
  }, [activePage, selected]);

  const updateActivePage = (updater) => {
    setWebsite((prev) => ({
      ...prev,
      pages: prev.pages.map((page) =>
        page.id === prev.activePageId ? updater(page) : page
      ),
    }));
  };

  const addPage = () => {
    const pageId = createId("page");

    setWebsite((prev) => ({
      ...prev,
      activePageId: pageId,
      pages: [
        ...prev.pages,
        {
          id: pageId,
          name: "New Page",
          slug: `/new-page-${prev.pages.length}`,
          parentId: null,
          sections: [],
        },
      ],
    }));

    setSelected({
      type: "page",
      id: pageId,
    });
  };

  const selectPage = (pageId) => {
    setWebsite((prev) => ({
      ...prev,
      activePageId: pageId,
    }));

    setSelected({
      type: "page",
      id: pageId,
    });
  };

  const updatePageField = (key, value) => {
    setWebsite((prev) => ({
      ...prev,
      pages: prev.pages.map((page) =>
        page.id === prev.activePageId
          ? {
              ...page,
              [key]: value,
            }
          : page
      ),
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

    setSelected({
      type: "page",
      id: nextPage.id,
    });
  };

  const addSection = (preset) => {
    const newSection = createSectionPreset(preset);

    updateActivePage((page) => ({
      ...page,
      sections: [...page.sections, newSection],
    }));

    setSelected({
      type: "section",
      id: newSection.id,
    });
  };

  const deleteSelectedSection = () => {
    if (!selectedSection) return;

    updateActivePage((page) => ({
      ...page,
      sections: page.sections.filter(
        (section) => section.id !== selectedSection.id
      ),
    }));

    setSelected({
      type: "page",
      id: activePage.id,
    });
  };

  const updateSelectedSectionLayout = (key, value) => {
    if (!selectedSection) return;

    updateActivePage((page) => ({
      ...page,
      sections: page.sections.map((section) =>
        section.id === selectedSection.id
          ? {
              ...section,
              layout: {
                ...section.layout,
                [key]: value,
              },
            }
          : section
      ),
    }));
  };

  const updateSelectedColumnLayout = (key, value) => {
    if (!selectedColumn) return;

    updateActivePage((page) => ({
      ...page,
      sections: page.sections.map((section) => ({
        ...section,
        rows: section.rows.map((row) => ({
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
      })),
    }));
  };

  const clearSelectedColumn = () => {
    if (!selectedColumn) return;

    updateActivePage((page) => ({
      ...page,
      sections: page.sections.map((section) => ({
        ...section,
        rows: section.rows.map((row) => ({
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
      })),
    }));
  };

  const addElementToColumn = (columnId, type) => {
    const newElement = defaultElement(type);

    updateActivePage((page) => ({
      ...page,
      sections: page.sections.map((section) => ({
        ...section,
        rows: section.rows.map((row) => ({
          ...row,
          columns: row.columns.map((column) =>
            column.id === columnId
              ? {
                  ...column,
                  elements: [...column.elements, newElement],
                }
              : column
          ),
        })),
      })),
    }));

    setSelected({
      type: "element",
      id: newElement.id,
    });
  };

  const updateSelectedElement = (updates) => {
    if (!selectedElement) return;

    updateActivePage((page) => ({
      ...page,
      sections: page.sections.map((section) => ({
        ...section,
        rows: section.rows.map((row) => ({
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
      })),
    }));
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

  const deleteSelectedElement = () => {
    if (!selectedElement) return;

    updateActivePage((page) => ({
      ...page,
      sections: page.sections.map((section) => ({
        ...section,
        rows: section.rows.map((row) => ({
          ...row,
          columns: row.columns.map((column) => ({
            ...column,
            elements: column.elements.filter(
              (element) => element.id !== selectedElement.id
            ),
          })),
        })),
      })),
    }));

    setSelected({
      type: "page",
      id: activePage.id,
    });
  };

  const updateOptions = (rawValue) => {
    const options = rawValue
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);

    updateSelectedElement({
      options,
    });
  };

  const exportJSON = () => {
    console.log(JSON.stringify(website, null, 2));
    alert("Website JSON exported to console.");
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

  const renderElement = (element) => {
    const isSelected = selected.type === "element" && selected.id === element.id;

    const commonProps = {
      className: `builder-element builder-element-${element.type} ${
        isSelected ? "is-selected" : ""
      }`,
      style: getElementStyle(element),
      onClick: (event) => {
        event.stopPropagation();

        if (!previewMode) {
          setSelected({
            type: "element",
            id: element.id,
          });
        }
      },
    };

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
            {element.required ? " *" : ""}
          </span>
          <input
            type={element.inputType || "text"}
            placeholder={element.placeholder || ""}
            onClick={(event) => event.stopPropagation()}
            readOnly
          />
        </label>
      );
    }

    if (element.type === "textarea") {
      return (
        <label key={element.id} {...commonProps}>
          <span>
            {element.content}
            {element.required ? " *" : ""}
          </span>
          <textarea
            placeholder={element.placeholder || ""}
            onClick={(event) => event.stopPropagation()}
            readOnly
          />
        </label>
      );
    }

    if (element.type === "checkbox") {
      return (
        <label key={element.id} {...commonProps}>
          <input
            type="checkbox"
            checked={element.checked || false}
            onChange={() => {}}
            onClick={(event) => event.stopPropagation()}
            readOnly
          />
          <span>
            {element.content}
            {element.required ? " *" : ""}
          </span>
        </label>
      );
    }

    if (element.type === "select") {
      return (
        <label key={element.id} {...commonProps}>
          <span>
            {element.content}
            {element.required ? " *" : ""}
          </span>
          <select onClick={(event) => event.stopPropagation()} disabled>
            {(element.options || []).map((option) => (
              <option key={option}>{option}</option>
            ))}
          </select>
        </label>
      );
    }

    if (element.type === "radio") {
      return (
        <div key={element.id} {...commonProps}>
          <strong>
            {element.content}
            {element.required ? " *" : ""}
          </strong>

          <div className="radio-options">
            {(element.options || []).map((option) => (
              <label key={option}>
                <input
                  type="radio"
                  name={element.id}
                  checked={element.selectedOption === option}
                  onChange={() => {}}
                  readOnly
                />
                <span>{option}</span>
              </label>
            ))}
          </div>
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

  return (
    <div className={`page-builder ${previewMode ? "preview-mode" : ""}`}>
      <header className="builder-topbar">
        <div>
          <h1>{website.name}</h1>
          <p>Generalized responsive website, form, and workflow builder</p>
        </div>

        <div className="builder-topbar-actions">
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
            <section className="builder-panel">
              <div className="builder-panel-header">
                <h2>Pages</h2>
                <button type="button" onClick={addPage}>
                  +
                </button>
              </div>

              <div className="page-list">
                {website.pages.map((page) => (
                  <button
                    key={page.id}
                    type="button"
                    className={page.id === activePage.id ? "active" : ""}
                    onClick={() => selectPage(page.id)}
                  >
                    <span>{page.name}</span>
                    <small>{page.slug}</small>
                  </button>
                ))}
              </div>
            </section>

            <section className="builder-panel">
              <h2>Sections</h2>

              <div className="preset-list">
                {sectionPresets.map((preset) => (
                  <button
                    key={preset.value}
                    type="button"
                    onClick={() => addSection(preset.value)}
                  >
                    + {preset.label}
                  </button>
                ))}
              </div>
            </section>

            <section className="builder-panel">
              <h2>Elements</h2>
              <p className="hint">
                Select a column in the canvas, then add an element.
              </p>

              <div className="preset-list">
                {elementTypes.map((element) => (
                  <button
                    key={element.value}
                    type="button"
                    disabled={selected.type !== "column"}
                    onClick={() => addElementToColumn(selected.id, element.value)}
                  >
                    + {element.label}
                  </button>
                ))}
              </div>
            </section>
          </aside>
        )}

        <main
          className="builder-canvas-shell"
          onClick={() =>
            !previewMode &&
            setSelected({
              type: "page",
              id: activePage.id,
            })
          }
        >
          <div className="builder-canvas">
            {activePage.sections.length === 0 ? (
              <div className="empty-builder-state">
                <h2>Start with a section</h2>
                <p>Add a layout, form, checklist, management header, or hero.</p>
              </div>
            ) : (
              activePage.sections.map((section) => {
                const sectionSelected =
                  selected.type === "section" && selected.id === section.id;

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

                      if (!previewMode) {
                        setSelected({
                          type: "section",
                          id: section.id,
                        });
                      }
                    }}
                  >
                    {section.rows.map((row) => (
                      <div
                        key={row.id}
                        className={`site-row columns-${row.layout.columns} align-${row.layout.align} gap-${row.layout.gap}`}
                      >
                        {row.columns.map((column) => {
                          const columnSelected =
                            selected.type === "column" &&
                            selected.id === column.id;

                          return (
                            <div
                              key={column.id}
                              className={`site-column column-align-${column.layout.align} ${
                                columnSelected ? "is-selected" : ""
                              }`}
                              onClick={(event) => {
                                event.stopPropagation();

                                if (!previewMode) {
                                  setSelected({
                                    type: "column",
                                    id: column.id,
                                  });
                                }
                              }}
                            >
                              {column.elements.map(renderElement)}

                              {!previewMode && column.elements.length === 0 && (
                                <div className="empty-column">
                                  Select column, then add element
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    ))}
                  </section>
                );
              })
            )}
          </div>
        </main>

        {!previewMode && (
          <aside className="builder-inspector">
            <h2>Inspector</h2>

            {selected.type === "page" && (
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

                <button
                  type="button"
                  className="danger-button"
                  onClick={deleteActivePage}
                >
                  Delete Page
                </button>
              </div>
            )}

            {selectedSection && (
              <div className="inspector-group">
                <h3>Section Layout</h3>

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

                <label>
                  Padding
                  <select
                    value={selectedSection.layout.paddingY}
                    onChange={(event) =>
                      updateSelectedSectionLayout("paddingY", event.target.value)
                    }
                  >
                    <option value="small">Small</option>
                    <option value="medium">Medium</option>
                    <option value="large">Large</option>
                  </select>
                </label>

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
                <h3>Column Position</h3>

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
                <h3>{selectedElement.type} Settings</h3>

                <label>
                  Content / Label
                  {selectedElement.type === "image" ? (
                    <input
                      value={selectedElement.content}
                      onChange={(event) =>
                        updateSelectedElement({
                          content: event.target.value,
                        })
                      }
                    />
                  ) : (
                    <textarea
                      value={selectedElement.content}
                      onChange={(event) =>
                        updateSelectedElement({
                          content: event.target.value,
                        })
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
                    Input Type
                    <select
                      value={selectedElement.inputType || "text"}
                      onChange={(event) =>
                        updateSelectedElement({
                          inputType: event.target.value,
                        })
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
                    />
                  </label>
                )}

                {["input", "textarea", "checkbox", "select", "radio"].includes(
                  selectedElement.type
                ) && (
                  <label className="checkbox-control">
                    <input
                      type="checkbox"
                      checked={selectedElement.required || false}
                      onChange={(event) =>
                        updateSelectedElement({
                          required: event.target.checked,
                        })
                      }
                    />
                    Required field
                  </label>
                )}

                {selectedElement.type === "checkbox" && (
                  <label className="checkbox-control">
                    <input
                      type="checkbox"
                      checked={selectedElement.checked || false}
                      onChange={(event) =>
                        updateSelectedElement({
                          checked: event.target.checked,
                        })
                      }
                    />
                    Checked by default
                  </label>
                )}

                {selectedElement.type !== "image" && (
                  <>
                    <label>
                      Text Color
                      <input
                        type="color"
                        value={selectedElement.styles.color || "#000000"}
                        onChange={(event) =>
                          updateSelectedElementStyle("color", event.target.value)
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

                <label>
                  Element Position
                  <select
                    value={selectedElement.styles.alignSelf || "auto"}
                    onChange={(event) =>
                      updateSelectedElementStyle("alignSelf", event.target.value)
                    }
                  >
                    <option value="auto">Follow Column</option>
                    <option value="flex-start">Left</option>
                    <option value="center">Center</option>
                    <option value="flex-end">Right</option>
                    <option value="stretch">Stretch</option>
                  </select>
                </label>

                <label>
                  Horizontal Fine Move
                  <input
                    type="range"
                    min="-120"
                    max="120"
                    value={selectedElement.styles.offsetX || 0}
                    onChange={(event) =>
                      updateSelectedElementStyle(
                        "offsetX",
                        Number(event.target.value)
                      )
                    }
                  />
                  <small>{selectedElement.styles.offsetX || 0}px</small>
                </label>

                {["button", "card", "input", "textarea", "select"].includes(
                  selectedElement.type
                ) && (
                  <label>
                    Background
                    <input
                      type="color"
                      value={
                        selectedElement.styles.backgroundColor || "#ffffff"
                      }
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

                {selectedElement.type === "button" && (
                  <>
                    <label>
                      Button Action
                      <select
                        value={selectedElement.action?.type || "none"}
                        onChange={(event) =>
                          updateSelectedElement({
                            action: {
                              ...selectedElement.action,
                              type: event.target.value,
                            },
                          })
                        }
                      >
                        <option value="none">None</option>
                        <option value="internal">Internal Page</option>
                        <option value="external">External URL</option>
                        <option value="submit">Submit Form</option>
                        <option value="nextStep">Next Workflow Step</option>
                      </select>
                    </label>

                    {selectedElement.action?.type === "internal" && (
                      <label>
                        Link Page
                        <select
                          value={selectedElement.action?.pageId || ""}
                          onChange={(event) =>
                            updateSelectedElement({
                              action: {
                                ...selectedElement.action,
                                pageId: event.target.value,
                              },
                            })
                          }
                        >
                          <option value="">Select page</option>
                          {website.pages.map((page) => (
                            <option key={page.id} value={page.id}>
                              {page.name}
                            </option>
                          ))}
                        </select>
                      </label>
                    )}

                    {selectedElement.action?.type === "external" && (
                      <label>
                        External URL
                        <input
                          value={selectedElement.action?.url || ""}
                          onChange={(event) =>
                            updateSelectedElement({
                              action: {
                                ...selectedElement.action,
                                url: event.target.value,
                              },
                            })
                          }
                          placeholder="https://example.com"
                        />
                      </label>
                    )}
                  </>
                )}

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
  );
}