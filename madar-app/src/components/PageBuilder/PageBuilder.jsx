import { useMemo, useState } from "react";
import logo from "../../assets/madar_header.svg";
import "../../styles/admin/PageBuilder/PageBuilder.css";

import {
  STORAGE_KEY,
  viewports,
  appTabs,
  defaultSiteChrome,
  pagePanels,
  friendlyQuestionTypes,
  elementTypes,
  starterSystems,
} from "./PageBuilder.constants";

import {
  createPosition,
  createQuestion,
  createFormSection,
  createForm,
  getFormSections,
  getFormQuestions,
  createElement,
  createColumn,
  createRow,
  createSection,
  createPage,
  createAutomation,
  createRole,
  cloneWithNewIds,
} from "./PageBuilder.factories";

import {
  heroSection,
  freeCanvasSection,
  sectionLibrary,
  buildStarterProject,
  createInitialProject,
} from "./PageBuilder.starters";

export default function PageBuilder() {
  const [project, setProject] = useState(createInitialProject);
  const [activeTab, setActiveTab] = useState("pages");
  const [pagePanel, setPagePanel] = useState("Pages");
  const [viewport, setViewport] = useState("desktop");
  const [preview, setPreview] = useState(false);
  const [selected, setSelected] = useState({ type: "page", id: null });
  const [modal, setModal] = useState(null);
  const [dragState, setDragState] = useState(null);
  const [runtimeAnswers, setRuntimeAnswers] = useState({});
  const [runtimeErrors, setRuntimeErrors] = useState({});
  const [dragQuestionType, setDragQuestionType] = useState(null);

  const activePage = useMemo(
    () => project.pages.find((page) => page.id === project.activePageId),
    [project.pages, project.activePageId]
  );

  const activeForm = useMemo(
    () => project.forms.find((form) => form.id === project.activeFormId),
    [project.forms, project.activeFormId]
  );

  const selectedSection = useMemo(() => {
    if (selected.type !== "section") return null;
    return activePage?.sections.find((section) => section.id === selected.id) || null;
  }, [activePage, selected]);

  const selectedColumn = useMemo(() => {
    if (selected.type !== "column") return null;

    for (const section of activePage?.sections || []) {
      for (const row of section.rows || []) {
        const column = row.columns.find((item) => item.id === selected.id);
        if (column) return column;
      }
    }

    return null;
  }, [activePage, selected]);

  const selectedElement = useMemo(() => {
    if (selected.type !== "element") return null;

    for (const section of activePage?.sections || []) {
      if (section.mode === "free") {
        const found = section.freeElements.find((item) => item.id === selected.id);
        if (found) return found;
      }

      for (const row of section.rows || []) {
        for (const column of row.columns || []) {
          const found = column.elements.find((item) => item.id === selected.id);
          if (found) return found;
        }
      }
    }

    return null;
  }, [activePage, selected]);

  const selectedQuestion = useMemo(() => {
    if (selected.type !== "question") return null;
    return getFormQuestions(activeForm).find((question) => question.id === selected.id) || null;
  }, [activeForm, selected]);

  const selectedAutomation = useMemo(() => {
    if (selected.type !== "automation") return null;
    return project.automations.find((automation) => automation.id === selected.id) || null;
  }, [project.automations, selected]);

  const selectedRole = useMemo(() => {
    if (selected.type !== "role") return null;
    return project.roles.find((role) => role.id === selected.id) || null;
  }, [project.roles, selected]);

  const updateProject = (updater) => {
    setProject((prev) => updater(prev));
  };

  const updateActivePage = (updater) => {
    updateProject((prev) => ({
      ...prev,
      pages: prev.pages.map((page) =>
        page.id === prev.activePageId ? updater(page) : page
      ),
    }));
  };

  const updateSections = (updater) => {
    updateActivePage((page) => ({ ...page, sections: updater(page.sections) }));
  };

  const updateActiveForm = (updater) => {
    updateProject((prev) => ({
      ...prev,
      forms: prev.forms.map((form) =>
        form.id === prev.activeFormId ? updater(form) : form
      ),
    }));
  };

  const selectPage = (pageId) => {
    updateProject((prev) => ({ ...prev, activePageId: pageId }));
    setSelected({ type: "page", id: pageId });
  };

  const selectForm = (formId) => {
    updateProject((prev) => ({ ...prev, activeFormId: formId }));
    setSelected({ type: "form", id: formId });
  };

  const addPage = () => {
    const page = createPage(`Page ${project.pages.length + 1}`, [heroSection()]);
    updateProject((prev) => ({
      ...prev,
      pages: [...prev.pages, page],
      activePageId: page.id,
    }));
    setSelected({ type: "page", id: page.id });
  };

  const deleteActivePage = () => {
    if (!activePage || project.pages.length <= 1) {
      alert("You need at least one page.");
      return;
    }

    if (!window.confirm(`Delete page "${activePage.name}"?`)) return;

    const nextPage = project.pages.find((page) => page.id !== activePage.id);
    updateProject((prev) => ({
      ...prev,
      pages: prev.pages.filter((page) => page.id !== activePage.id),
      activePageId: nextPage.id,
    }));
    setSelected({ type: "page", id: nextPage.id });
  };

  const addForm = () => {
    const form = createForm(`Form ${project.forms.length + 1}`, [
      createQuestion("Question 1", "shortText"),
    ]);

    updateProject((prev) => ({
      ...prev,
      forms: [...prev.forms, form],
      activeFormId: form.id,
      automations: [...prev.automations, createAutomation(`After ${form.title} is submitted`, form.id)],
    }));

    setSelected({ type: "form", id: form.id });
  };

  const getSelectedFormSectionId = () => {
    const sections = getFormSections(activeForm);
    if (selected.type === "formSection" && sections.some((section) => section.id === selected.id)) {
      return selected.id;
    }

    if (selected.type === "question") {
      const parent = sections.find((section) =>
        (section.elements || []).some((question) => question.id === selected.id)
      );

      if (parent) return parent.id;
    }

    return sections[0]?.id;
  };

  const addFormSection = (insertIndex = null) => {
    const section = createFormSection(`Section ${getFormSections(activeForm).length + 1}`, []);

    updateActiveForm((form) => {
      const sections = [...getFormSections(form)];

      if (insertIndex === null || insertIndex === undefined || insertIndex >= sections.length) {
        sections.push(section);
      } else {
        sections.splice(insertIndex, 0, section);
      }

      return {
        ...form,
        sections,
      };
    });

    setSelected({ type: "formSection", id: section.id });
  };

  const updateFormSection = (sectionId, updates) => {
    updateActiveForm((form) => ({
      ...form,
      sections: getFormSections(form).map((section) =>
        section.id === sectionId ? { ...section, ...updates } : section
      ),
    }));
  };

  const deleteFormSection = (sectionId) => {
    if (!window.confirm("Delete this section and everything inside it?")) return;

    updateActiveForm((form) => {
      const sections = getFormSections(form).filter((section) => section.id !== sectionId);

      return {
        ...form,
        sections: sections.length ? sections : [createFormSection("Section 1", [])],
      };
    });

    setSelected({ type: "form", id: activeForm?.id });
  };

  const duplicateFormSection = (section) => {
    const copy = cloneWithNewIds(section);
    copy.title = `${section.title} Copy`;

    updateActiveForm((form) => {
      const sections = [...getFormSections(form)];
      const index = sections.findIndex((item) => item.id === section.id);
      sections.splice(index + 1, 0, copy);

      return {
        ...form,
        sections,
      };
    });

    setSelected({ type: "formSection", id: copy.id });
  };

  const addQuestion = (type = "shortText", sectionId = null, insertIndex = null) => {
    if (!activeForm) return;

    const sections = getFormSections(activeForm);
    const fallbackSection = sections[0] || createFormSection("Section 1", []);
    const targetSectionId = sectionId || getSelectedFormSectionId() || fallbackSection.id;
    const questionType = friendlyQuestionTypes.find((item) => item.id === type);
    const newQuestion = createQuestion(questionType ? questionType.label : "Question", type);

    updateActiveForm((form) => {
      let formSections = getFormSections(form);

      if (!formSections.length) {
        formSections = [fallbackSection];
      }

      return {
        ...form,
        sections: formSections.map((section) => {
          if (section.id !== targetSectionId) return section;

          const elements = [...(section.elements || [])];

          if (insertIndex === null || insertIndex === undefined || insertIndex >= elements.length) {
            elements.push(newQuestion);
          } else {
            elements.splice(insertIndex, 0, newQuestion);
          }

          return {
            ...section,
            elements,
            collapsed: false,
          };
        }),
      };
    });

    setSelected({ type: "question", id: newQuestion.id });
  };

  const handleQuestionDrop = (event, sectionId = null, insertIndex = null) => {
    event.preventDefault();
    event.stopPropagation();

    if (!activeForm) return;

    const type =
      event.dataTransfer.getData("question/type") ||
      dragQuestionType ||
      "shortText";

    addQuestion(type, sectionId, insertIndex);
    setDragQuestionType(null);
  };

  const getQuestionTypeLabel = (typeId) => {
    return friendlyQuestionTypes.find((item) => item.id === typeId)?.label || "Short answer";
  };

  const updateQuestion = (questionId, updates) => {
    updateActiveForm((form) => ({
      ...form,
      sections: getFormSections(form).map((section) => ({
        ...section,
        elements: (section.elements || []).map((question) =>
          question.id === questionId
            ? {
                ...question,
                ...updates,
                saveAs:
                  updates.label && !updates.saveAs
                    ? slugify(updates.label).replaceAll("-", "_")
                    : updates.saveAs || question.saveAs,
              }
            : question
        ),
      })),
    }));
  };

  const deleteQuestion = (questionId) => {
    updateActiveForm((form) => ({
      ...form,
      sections: getFormSections(form).map((section) => ({
        ...section,
        elements: (section.elements || []).filter((question) => question.id !== questionId),
      })),
    }));

    setSelected({ type: "form", id: activeForm?.id });
  };

  const duplicateQuestion = (question) => {
    const copy = cloneWithNewIds(question);
    copy.label = `${question.label} Copy`;

    updateActiveForm((form) => ({
      ...form,
      sections: getFormSections(form).map((section) => {
        const index = (section.elements || []).findIndex((item) => item.id === question.id);
        if (index === -1) return section;

        const elements = [...section.elements];
        elements.splice(index + 1, 0, copy);

        return {
          ...section,
          elements,
        };
      }),
    }));

    setSelected({ type: "question", id: copy.id });
  };

  const moveQuestion = (questionId, direction) => {
    updateActiveForm((form) => {
      const sections = getFormSections(form).map((section) => ({
        ...section,
        elements: [...(section.elements || [])],
      }));

      const sectionIndex = sections.findIndex((section) =>
        section.elements.some((question) => question.id === questionId)
      );

      if (sectionIndex === -1) return form;

      const section = sections[sectionIndex];
      const questionIndex = section.elements.findIndex((question) => question.id === questionId);
      const nextIndex = direction === "up" ? questionIndex - 1 : questionIndex + 1;

      if (nextIndex >= 0 && nextIndex < section.elements.length) {
        [section.elements[questionIndex], section.elements[nextIndex]] = [
          section.elements[nextIndex],
          section.elements[questionIndex],
        ];

        return {
          ...form,
          sections,
        };
      }

      const targetSectionIndex = direction === "up" ? sectionIndex - 1 : sectionIndex + 1;
      if (targetSectionIndex < 0 || targetSectionIndex >= sections.length) return form;

      const [question] = section.elements.splice(questionIndex, 1);
      if (direction === "up") {
        sections[targetSectionIndex].elements.push(question);
      } else {
        sections[targetSectionIndex].elements.unshift(question);
      }

      return {
        ...form,
        sections,
      };
    });
  };

  const addSection = (factory) => {
    const section = factory(project.activeFormId);
    updateSections((sections) => [...sections, section]);
    setSelected({ type: "section", id: section.id });
    setModal(null);
  };

  const updateSelectedSection = (updates) => {
    if (!selectedSection) return;

    updateSections((sections) =>
      sections.map((section) =>
        section.id === selectedSection.id
          ? {
              ...section,
              ...updates,
              layout: { ...section.layout, ...(updates.layout || {}) },
            }
          : section
      )
    );
  };

  const deleteSelectedSection = () => {
    if (!selectedSection) return;
    if (!window.confirm(`Delete section "${selectedSection.name}"?`)) return;

    updateSections((sections) => sections.filter((section) => section.id !== selectedSection.id));
    setSelected({ type: "page", id: activePage.id });
  };

  const updateSelectedColumn = (updates) => {
    if (!selectedColumn) return;

    updateSections((sections) =>
      sections.map((section) => ({
        ...section,
        rows: section.rows.map((row) => ({
          ...row,
          columns: row.columns.map((column) =>
            column.id === selectedColumn.id
              ? { ...column, layout: { ...column.layout, ...(updates.layout || {}) } }
              : column
          ),
        })),
      }))
    );
  };

  const smartAddElement = (type) => {
    const element = createElement(type, type === "formBlock" ? { connectedFormId: project.activeFormId } : {});

    if (selectedSection?.mode === "free") {
      updateSections((sections) =>
        sections.map((section) =>
          section.id === selectedSection.id
            ? { ...section, freeElements: [...section.freeElements, { ...element, mode: "free" }] }
            : section
        )
      );
      setSelected({ type: "element", id: element.id });
      return;
    }

    let targetColumnId = selectedColumn?.id;

    if (!targetColumnId && selectedSection?.mode === "auto") {
      targetColumnId = selectedSection.rows?.[0]?.columns?.[0]?.id;
    }

    if (!targetColumnId) {
      const latestSection = activePage.sections[activePage.sections.length - 1];
      targetColumnId = latestSection?.rows?.[0]?.columns?.[0]?.id;
    }

    if (!targetColumnId) {
      const section = createSection({
        name: "Quick Section",
        rows: [createRow([createColumn([element])])],
      });
      updateSections((sections) => [...sections, section]);
      setSelected({ type: "element", id: element.id });
      return;
    }

    updateSections((sections) =>
      sections.map((section) => ({
        ...section,
        rows: section.rows.map((row) => ({
          ...row,
          columns: row.columns.map((column) =>
            column.id === targetColumnId
              ? { ...column, elements: [...column.elements, element] }
              : column
          ),
        })),
      }))
    );

    setSelected({ type: "element", id: element.id });
  };

  const updateSelectedElement = (updates) => {
    if (!selectedElement) return;

    const merge = (element) => ({
      ...element,
      ...updates,
      styles: { ...element.styles, ...(updates.styles || {}) },
      action: { ...element.action, ...(updates.action || {}) },
    });

    updateSections((sections) =>
      sections.map((section) => {
        if (section.mode === "free") {
          return {
            ...section,
            freeElements: section.freeElements.map((element) =>
              element.id === selectedElement.id ? merge(element) : element
            ),
          };
        }

        return {
          ...section,
          rows: section.rows.map((row) => ({
            ...row,
            columns: row.columns.map((column) => ({
              ...column,
              elements: column.elements.map((element) =>
                element.id === selectedElement.id ? merge(element) : element
              ),
            })),
          })),
        };
      })
    );
  };

  const deleteSelectedElement = () => {
    if (!selectedElement) return;
    if (!window.confirm(`Delete "${selectedElement.name}"?`)) return;

    updateSections((sections) =>
      sections.map((section) => {
        if (section.mode === "free") {
          return {
            ...section,
            freeElements: section.freeElements.filter((element) => element.id !== selectedElement.id),
          };
        }

        return {
          ...section,
          rows: section.rows.map((row) => ({
            ...row,
            columns: row.columns.map((column) => ({
              ...column,
              elements: column.elements.filter((element) => element.id !== selectedElement.id),
            })),
          })),
        };
      })
    );

    setSelected({ type: "page", id: activePage.id });
  };

  const setAnswer = (formId, questionId, value) => {
    setRuntimeAnswers((prev) => ({
      ...prev,
      [formId]: {
        ...(prev[formId] || {}),
        [questionId]: value,
      },
    }));

    setRuntimeErrors((prev) => {
      const next = { ...prev };
      delete next[questionId];
      return next;
    });
  };

  const submitRuntimeForm = (form) => {
    const answers = runtimeAnswers[form.id] || {};
    const nextErrors = {};

    getFormQuestions(form).forEach((question) => {
      if (!question.required) return;
      const value = answers[question.id];

      if (
        value === undefined ||
        value === null ||
        value === "" ||
        (Array.isArray(value) && value.length === 0)
      ) {
        nextErrors[question.id] = "This question is required.";
      }
    });

    setRuntimeErrors(nextErrors);

    if (Object.keys(nextErrors).length > 0) return;

    const response = {
      id: createId("response"),
      createdAt: new Date().toISOString(),
      status: "New",
      answers,
    };

    updateProject((prev) => ({
      ...prev,
      forms: prev.forms.map((item) =>
        item.id === form.id ? { ...item, responses: [response, ...item.responses] } : item
      ),
    }));

    setRuntimeAnswers((prev) => ({ ...prev, [form.id]: {} }));
    alert(form.successMessage);
  };

  const saveProject = () => {
    const nextProject = {
      ...project,
      publish: {
        ...project.publish,
        lastSavedAt: new Date().toISOString(),
      },
    };

    localStorage.setItem(STORAGE_KEY, JSON.stringify(nextProject));
    setProject(nextProject);
    alert("Saved locally.");
  };

  const loadProject = () => {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      alert("No saved project found.");
      return;
    }

    const loaded = JSON.parse(raw);
    setProject(loaded);
    setSelected({ type: "page", id: loaded.activePageId });
    alert("Loaded saved project.");
  };

  const publishProject = () => {
    updateProject((prev) => ({
      ...prev,
      status: "published",
      publish: {
        ...prev.publish,
        lastPublishedAt: new Date().toISOString(),
      },
    }));

    alert("Published locally. Later this should connect to your backend.");
  };

  const exportProject = () => {
    console.log(JSON.stringify(project, null, 2));
    alert("Exported JSON to console.");
  };

  const applyStarter = (starterId) => {
    const starter = buildStarterProject(starterId);

    updateProject((prev) => ({
      ...prev,
      activePageId: starter.pages[0].id,
      activeFormId: starter.forms[0].id,
      pages: starter.pages,
      forms: starter.forms,
      automations: starter.automations,
      roles: starter.roles,
      status: "draft",
    }));

    setSelected({ type: "page", id: starter.pages[0].id });
    setActiveTab("pages");
    setModal(null);
  };

  const getElementStyle = (element) => {
    const isSelected = selected.type === "element" && selected.id === element.id;

    return {
      ...element.styles,
      position: "relative",
      transform: undefined,
      width: undefined,
      minHeight: undefined,
      maxWidth: "100%",
      alignSelf:
        element.styles.alignSelf === "auto" ? undefined : element.styles.alignSelf,
      zIndex: isSelected ? 5 : 1,
    };
  };

  const getFreeElementStyle = (element) => {
    const pos = element.position?.[viewport] || createPosition()[viewport];

    return {
      ...element.styles,
      position: "absolute",
      left: `${pos.x}px`,
      top: `${pos.y}px`,
      width: `${pos.width}px`,
      minHeight: `${pos.height}px`,
    };
  };

  const updateElementPosition = (key, value) => {
    if (!selectedElement) return;

    const current = selectedElement.position?.[viewport] || createPosition()[viewport];
    const nextValue = value === "" ? "" : Number(value);

    updateSelectedElement({
      position: {
        ...selectedElement.position,
        [viewport]: {
          ...current,
          [key]: nextValue,
        },
      },
    });
  };

  const uploadImageForSelectedElement = (file) => {
    if (!file || !selectedElement || selectedElement.type !== "image") return;

    if (!file.type.startsWith("image/")) {
      alert("Please choose an image file.");
      return;
    }

    const reader = new FileReader();

    reader.onload = () => {
      updateSelectedElement({
        content: reader.result,
        name: selectedElement.name || file.name,
      });
    };

    reader.onerror = () => {
      alert("Could not read this image. Please try another file.");
    };

    reader.readAsDataURL(file);
  };

  const uploadSiteLogo = (file) => {
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      alert("Please choose an image file.");
      return;
    }

    const reader = new FileReader();

    reader.onload = () => {
      updateProject((prev) => ({
        ...prev,
        siteChrome: {
          ...(prev.siteChrome || defaultSiteChrome),
          logoUrl: reader.result,
        },
      }));
    };

    reader.onerror = () => {
      alert("Could not read this logo. Please try another file.");
    };

    reader.readAsDataURL(file);
  };

  const splitLines = (value) =>
    String(value || "")
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);



  const startDrag = (event, element) => {
    if (preview) return;

    const tagName = event.target?.tagName?.toLowerCase();
    if (["input", "textarea", "select", "option", "button"].includes(tagName)) {
      return;
    }

    event.stopPropagation();
    event.preventDefault();

    const current = element.position?.[viewport] || createPosition()[viewport];

    setSelected({ type: "element", id: element.id });
    setDragState({
      elementId: element.id,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startX: current.x || 0,
      startY: current.y || 0,
    });
  };

  const handleMouseMove = (event) => {
    if (!dragState || !selectedElement || selectedElement.id !== dragState.elementId) return;

    const current = selectedElement.position?.[viewport] || createPosition()[viewport];
    const deltaX = event.clientX - dragState.startClientX;
    const deltaY = event.clientY - dragState.startClientY;

    updateSelectedElement({
      position: {
        ...selectedElement.position,
        [viewport]: {
          ...current,
          x: Math.max(-600, dragState.startX + deltaX),
          y: Math.max(-600, dragState.startY + deltaY),
        },
      },
    });
  };

  const renderQuestionInput = (form, question, disabled = false) => {
    const value = runtimeAnswers[form.id]?.[question.id] || "";
    const error = runtimeErrors[question.id];

    const common = {
      disabled,
      value,
      onChange: (event) => setAnswer(form.id, question.id, event.target.value),
    };

    let inputNode = null;

    if (["shortText", "email", "phone", "number", "money", "date"].includes(question.type)) {
      const inputType =
        question.type === "email"
          ? "email"
          : question.type === "phone"
          ? "tel"
          : question.type === "number" || question.type === "money"
          ? "number"
          : question.type === "date"
          ? "date"
          : "text";

      inputNode = <input type={inputType} placeholder={question.placeholder} {...common} />;
    } else if (question.type === "paragraph") {
      inputNode = <textarea placeholder={question.placeholder} {...common} />;
    } else if (question.type === "dropdown" || question.type === "status") {
      inputNode = (
        <select {...common}>
          <option value="">Choose...</option>
          {question.options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      );
    } else if (question.type === "multipleChoice") {
      inputNode = (
        <div className="choice-list">
          {question.options.map((option) => (
            <label key={option}>
              <input
                type="radio"
                name={question.id}
                checked={value === option}
                disabled={disabled}
                onChange={() => setAnswer(form.id, question.id, option)}
              />
              <span>{option}</span>
            </label>
          ))}
        </div>
      );
    } else if (question.type === "checkboxes") {
      const values = Array.isArray(runtimeAnswers[form.id]?.[question.id])
        ? runtimeAnswers[form.id][question.id]
        : [];

      inputNode = (
        <div className="choice-list">
          {question.options.map((option) => (
            <label key={option}>
              <input
                type="checkbox"
                checked={values.includes(option)}
                disabled={disabled}
                onChange={(event) => {
                  const next = event.target.checked
                    ? [...values, option]
                    : values.filter((item) => item !== option);
                  setAnswer(form.id, question.id, next);
                }}
              />
              <span>{option}</span>
            </label>
          ))}
        </div>
      );
    } else if (question.type === "yesNo") {
      inputNode = (
        <div className="choice-pills">
          {["Yes", "No"].map((option) => (
            <button
              type="button"
              key={option}
              disabled={disabled}
              className={value === option ? "active" : ""}
              onClick={() => setAnswer(form.id, question.id, option)}
            >
              {option}
            </button>
          ))}
        </div>
      );
    } else if (question.type === "file") {
      inputNode = <input type="file" disabled={disabled} />;
    }

    return (
      <div className={`runtime-question ${error ? "has-error" : ""}`} key={question.id}>
        <label>
          <span>
            {question.label}
            {question.required ? " *" : ""}
          </span>
          {question.helpText && <small>{question.helpText}</small>}
          {inputNode}
          {error && <strong>{error}</strong>}
        </label>
      </div>
    );
  };

  const renderConnectedForm = (formId) => {
    const form = project.forms.find((item) => item.id === formId) || project.forms[0];
    if (!form) return <div className="empty-connected">No form selected.</div>;

    return (
      <div className="runtime-form">
        <div className="runtime-form-header">
          <h3>{form.title}</h3>
          <p>{form.description}</p>
        </div>

        {getFormSections(form).map((section) => (
          <div className="runtime-form-section" key={section.id}>
            <div className="runtime-form-section-header">
              <h4>{section.title}</h4>
              {section.description && <p>{section.description}</p>}
            </div>

            {(section.elements || []).map((question) =>
              renderQuestionInput(form, question, !preview)
            )}
          </div>
        ))}

        <button
          type="button"
          className="runtime-submit"
          disabled={!preview}
          onClick={() => submitRuntimeForm(form)}
        >
          Submit
        </button>

        {!preview && <p className="builder-note">Enable Preview to test submitting this form.</p>}
      </div>
    );
  };

  const renderResponsesTable = (formId) => {
    const form = project.forms.find((item) => item.id === formId) || project.forms[0];
    if (!form) return <div className="empty-connected">No form selected.</div>;

    const responses = form.responses;

    return (
      <div className="responses-preview">
        <div className="responses-preview-header">
          <strong>{form.title}</strong>
          <span>{responses.length} responses</span>
        </div>

        <div className="mock-table">
          <div className="mock-table-row mock-table-head">
            <span>Status</span>
            {getFormQuestions(form).slice(0, 3).map((question) => (
              <span key={question.id}>{question.label}</span>
            ))}
          </div>

          {(responses.length ? responses : [{ id: "sample", status: "Sample", answers: {} }]).map(
            (response, index) => (
              <div className="mock-table-row" key={response.id}>
                <span>{response.status || "New"}</span>
                {getFormQuestions(form).slice(0, 3).map((question) => (
                  <span key={question.id}>
                    {response.answers?.[question.id] || (index === 0 ? "—" : "")}
                  </span>
                ))}
              </div>
            )
          )}
        </div>
      </div>
    );
  };

  const renderElement = (element, isFree = false) => {
    const isSelected = selected.type === "element" && selected.id === element.id;

    const commonProps = {
      className: `builder-element builder-element-${element.type} ${isSelected ? "is-selected" : ""}`,
      style: isFree ? getFreeElementStyle(element) : getElementStyle(element),
      onMouseDown: (event) => startDrag(event, element),
      onClick: (event) => {
        event.stopPropagation();
        if (!preview) setSelected({ type: "element", id: element.id });
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
      return <img key={element.id} {...commonProps} src={element.content} alt={element.name} />;
    }

    if (element.type === "card") {
      return (
        <div key={element.id} {...commonProps}>
          {String(element.content || "").split("\n").map((line, index) => (
            <span key={`${element.id}_${index}`}>{line}</span>
          ))}
        </div>
      );
    }

    if (element.type === "formBlock") {
      return (
        <div key={element.id} {...commonProps}>
          {renderConnectedForm(element.connectedFormId)}
        </div>
      );
    }

    if (element.type === "responsesTable") {
      return (
        <div key={element.id} {...commonProps}>
          {renderResponsesTable(element.connectedFormId)}
        </div>
      );
    }

    if (element.type === "metric") {
      const [label, value] = String(element.content || "").split("\n");
      return (
        <div key={element.id} {...commonProps}>
          <span className="metric-label">{label}</span>
          <strong className="metric-value">{value}</strong>
        </div>
      );
    }

    return (
      <div key={element.id} {...commonProps}>
        {element.content}
      </div>
    );
  };

  const renderSiteHeader = () => {
    const site = project.siteChrome || defaultSiteChrome;
    if (!site.showHeader) return null;

    const logoSrc = site.logoUrl || logo;

    return (
      <header className={`built-site-header header-align-${site.headerAlign || "center"}`}>
        <div className="built-site-header-inner">
          <button
            type="button"
            className="built-site-brand"
            onClick={(event) => {
              event.stopPropagation();
              const homePage = project.pages.find((page) => page.slug === "/") || project.pages[0];
              if (homePage) selectPage(homePage.id);
            }}
          >
            <img src={logoSrc} alt={`${site.brand || "Website"} logo`} />
            <span>{site.brand || "Website"}</span>
          </button>

          <nav className="built-site-nav">
            {project.pages.map((page) => (
              <button
                type="button"
                key={page.id}
                className={activePage?.id === page.id ? "active" : ""}
                onClick={(event) => {
                  event.stopPropagation();
                  selectPage(page.id);
                }}
              >
                {page.name}
              </button>
            ))}
          </nav>

        </div>
      </header>
    );
  };

  const renderSiteFooter = () => {
    const site = project.siteChrome || defaultSiteChrome;
    if (!site.showFooter) return null;

    const shopLinks = splitLines(site.footerShopLinks || "All Products\nAll Categories");
    const helpLinks = splitLines(site.footerHelpLinks || "Our Policies\nAbout Us\nTrack Your Orders");
    const socialLinks = splitLines(site.footerSocialLinks || "Facebook\nLinkedIn\nX\nInstagram");
    const paymentMethods = splitLines(site.footerPaymentMethods || "Visa\nMastercard\nApple Pay\nGoogle Pay");
    const logoSrc = site.logoUrl || logo;

    return (
      <footer className="built-site-footer ecommerce-style-footer">
        <div className="ecommerce-footer-grid">
          <div className="ecommerce-footer-brand">
            <img className="ecommerce-footer-logo" src={logoSrc} alt={`${site.brand || "Website"} logo`} />

            <div className="ecommerce-social-row">
              {socialLinks.map((item) => (
                <button type="button" key={item} aria-label={item}>
                  {item.slice(0, 2).toUpperCase()}
                </button>
              ))}
            </div>

            <div className="ecommerce-payment-block">
              <h4>Payment Methods</h4>
              <div className="ecommerce-payment-row">
                {paymentMethods.map((method) => (
                  <span key={method}>{method}</span>
                ))}
              </div>
            </div>
          </div>

          <div className="ecommerce-footer-column">
            <h4>{site.footerShopTitle || "Shop"}</h4>
            {shopLinks.map((item) => (
              <button type="button" key={item}>
                {item}
              </button>
            ))}
          </div>

          <div className="ecommerce-footer-column">
            <h4>{site.footerHelpTitle || "Help"}</h4>
            {helpLinks.map((item) => (
              <button type="button" key={item}>
                {item}
              </button>
            ))}
          </div>

          <div className="ecommerce-footer-contact">
            <div className="footer-language-pill">
              <span>◎</span>
              <strong>{site.footerLanguageLabel || "AR"}</strong>
            </div>

            <p>{site.contactEmail || "info@madar.com"}</p>
            <p dir="ltr">{site.phone || "+972 0599203857"}</p>
          </div>
        </div>

        <div className="ecommerce-footer-bottom">
          <p>
            © 2026 {site.footerStoreName || site.brand || "Your Website"}. {site.rights || "All rights reserved."}
          </p>

          <button
            type="button"
            className="powered-by-madar"
            onClick={(event) => {
              event.stopPropagation();
              window.location.href = site.madarLink || "/";
            }}
          >
            Powered by Madar
          </button>
        </div>
      </footer>
    );
  };

  const renderPagesTab = () => (
    <div className="builder-layout">
      {!preview && (
        <aside className="builder-sidebar">
          <div className="panel-mode-select">
            <label>
              Editing panel
              <select value={pagePanel} onChange={(event) => setPagePanel(event.target.value)}>
                {pagePanels.map((panel) => (
                  <option key={panel} value={panel}>
                    {panel}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {pagePanel === "Pages" && (
            <section className="builder-panel">
              <h2>Pages</h2>
              <p className="panel-help">Create public pages, dashboards, forms, and review screens.</p>

              <select value={activePage?.id || ""} onChange={(event) => selectPage(event.target.value)}>
                {project.pages.map((page) => (
                  <option key={page.id} value={page.id}>
                    {page.name}
                  </option>
                ))}
              </select>

              <div className="compact-actions">
                <button type="button" onClick={addPage}>
                  + Page
                </button>
                <button type="button" onClick={() => setModal("starter")}>
                  Starter
                </button>
              </div>
            </section>
          )}

          {pagePanel === "Sections" && (
            <section className="builder-panel">
              <h2>Sections</h2>
              <p className="panel-help">Add page blocks. Auto layout is recommended.</p>
              <button type="button" className="full-width-action" onClick={() => setModal("section")}>
                + Add Section
              </button>
            </section>
          )}

          {pagePanel === "Layers" && (
            <section className="builder-panel">
              <h2>Layers</h2>
              <div className="layer-tree">
                {activePage?.sections.map((section) => (
                  <div key={section.id} className="layer-item">
                    <button
                      type="button"
                      className={selected.id === section.id ? "active" : ""}
                      onClick={() => setSelected({ type: "section", id: section.id })}
                    >
                      ▾ {section.name}
                    </button>

                    <div className="layer-children">
                      {section.mode === "free"
                        ? section.freeElements.map((element) => (
                            <button
                              type="button"
                              key={element.id}
                              className={selected.id === element.id ? "active" : ""}
                              onClick={() => setSelected({ type: "element", id: element.id })}
                            >
                              {element.name}
                            </button>
                          ))
                        : section.rows.map((row) =>
                            row.columns.map((column, index) => (
                              <div key={column.id} className="layer-column">
                                <button
                                  type="button"
                                  className={selected.id === column.id ? "active" : ""}
                                  onClick={() => setSelected({ type: "column", id: column.id })}
                                >
                                  Column {index + 1}
                                </button>

                                {column.elements.map((element) => (
                                  <button
                                    type="button"
                                    key={element.id}
                                    className={selected.id === element.id ? "active" : ""}
                                    onClick={() => setSelected({ type: "element", id: element.id })}
                                  >
                                    {element.name}
                                  </button>
                                ))}
                              </div>
                            ))
                          )}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {pagePanel === "Add" && (
            <section className="builder-panel">
              <h2>Add Elements</h2>
              <p className="panel-help">Select a section or column first, then add an element.</p>

              {["Content", "Connected"].map((group) => (
                <div key={group} className="add-group">
                  <span>{group}</span>
                  {elementTypes
                    .filter((item) => item.group === group)
                    .map((item) => (
                      <button type="button" key={item.id} onClick={() => smartAddElement(item.id)}>
                        + {item.label}
                      </button>
                    ))}
                </div>
              ))}
            </section>
          )}
        </aside>
      )}

      <main
        className="builder-canvas-shell"
        onClick={() => {
          if (!preview) setSelected({ type: "page", id: activePage?.id });
        }}
      >
        <div
          className={`builder-canvas viewport-${viewport}`}
          style={{ maxWidth: preview ? `${viewports[viewport]}px` : undefined }}
        >
          {renderSiteHeader()}

          {activePage?.sections.map((section) => {
            const isSelected = selected.type === "section" && selected.id === section.id;

            if (section.mode === "free") {
              return (
                <section
                  key={section.id}
                  className={`site-section free-canvas-section width-${section.layout.width} ${
                    isSelected ? "is-selected" : ""
                  }`}
                  style={{ backgroundColor: section.layout.background, minHeight: section.layout.minHeight }}
                  onClick={(event) => {
                    event.stopPropagation();
                    if (!preview) setSelected({ type: "section", id: section.id });
                  }}
                >
                  {!preview && (
                    <div className="free-canvas-toolbar">
                      <strong>Free Canvas</strong>
                      <button type="button" onClick={() => setSelected({ type: "page", id: activePage.id })}>
                        Exit Free Canvas
                      </button>
                    </div>
                  )}

                  <div
                    className="free-canvas-frame"
                    style={{
                      width: `${viewports[viewport]}px`,
                      minHeight: `${section.layout.minHeight}px`,
                    }}
                  >
                    {section.freeElements.map((element) => renderElement(element, true))}
                  </div>
                </section>
              );
            }

            return (
              <section
                key={section.id}
                className={`site-section width-${section.layout.width} padding-${section.layout.paddingY} ${
                  isSelected ? "is-selected" : ""
                }`}
                style={{ backgroundColor: section.layout.background }}
                onClick={(event) => {
                  event.stopPropagation();
                  if (!preview) setSelected({ type: "section", id: section.id });
                }}
              >
                {section.rows.map((row) => (
                  <div
                    key={row.id}
                    className={`site-row columns-${row.layout.columns} align-${row.layout.align} gap-${row.layout.gap}`}
                  >
                    {row.columns.map((column) => {
                      const columnSelected = selected.type === "column" && selected.id === column.id;

                      return (
                        <div
                          key={column.id}
                          className={`site-column column-align-${column.layout.align} ${
                            columnSelected ? "is-selected" : ""
                          }`}
                          onClick={(event) => {
                            event.stopPropagation();
                            if (!preview) setSelected({ type: "column", id: column.id });
                          }}
                        >
                          {column.elements.map((element) => renderElement(element, false))}
                          {!preview && column.elements.length === 0 && (
                            <div className="empty-column">Select this column, then add an element.</div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ))}
              </section>
            );
          })}

          {renderSiteFooter()}
        </div>
      </main>

      {!preview && renderInspector()}
    </div>
  );

  const renderInspector = () => (
    <aside className="builder-inspector">
      <div className="inspector-title">
        <h2>Inspector</h2>
        <span>{selected.type}</span>
      </div>

      {selected.type === "page" && activePage && (
        <div className="inspector-group">
          <h3>Page Settings</h3>

          <label>
            Page name
            <input
              value={activePage.name}
              onChange={(event) =>
                updateActivePage((page) => ({
                  ...page,
                  name: event.target.value,
                }))
              }
            />
          </label>

          <label>
            Page link
            <input
              value={activePage.slug}
              onChange={(event) =>
                updateActivePage((page) => ({
                  ...page,
                  slug: event.target.value,
                }))
              }
            />
          </label>

          <details open>
            <summary>Website Header & Footer</summary>

            <label className="checkbox-control">
              <input
                type="checkbox"
                checked={project.siteChrome?.showHeader ?? true}
                onChange={(event) =>
                  updateProject((prev) => ({
                    ...prev,
                    siteChrome: {
                      ...(prev.siteChrome || defaultSiteChrome),
                      showHeader: event.target.checked,
                    },
                  }))
                }
              />
              Show header
            </label>

            <label className="checkbox-control">
              <input
                type="checkbox"
                checked={project.siteChrome?.showFooter ?? true}
                onChange={(event) =>
                  updateProject((prev) => ({
                    ...prev,
                    siteChrome: {
                      ...(prev.siteChrome || defaultSiteChrome),
                      showFooter: event.target.checked,
                    },
                  }))
                }
              />
              Show footer
            </label>

            <label>
              Brand / store name
              <input
                value={project.siteChrome?.brand || "Madar"}
                onChange={(event) =>
                  updateProject((prev) => ({
                    ...prev,
                    siteChrome: {
                      ...(prev.siteChrome || defaultSiteChrome),
                      brand: event.target.value,
                    },
                  }))
                }
              />
            </label>

            <div className="image-upload-control">
              <label>
                Logo URL
                <input
                  value={project.siteChrome?.logoUrl || ""}
                  placeholder="Paste logo URL or upload from device"
                  onChange={(event) =>
                    updateProject((prev) => ({
                      ...prev,
                      siteChrome: {
                        ...(prev.siteChrome || defaultSiteChrome),
                        logoUrl: event.target.value,
                      },
                    }))
                  }
                />
              </label>

              <label className="upload-image-button">
                Upload logo from device
                <input
                  type="file"
                  accept="image/*"
                  onChange={(event) => uploadSiteLogo(event.target.files?.[0])}
                />
              </label>

              <div className="image-upload-preview">
                <img src={project.siteChrome?.logoUrl || logo} alt="Logo preview" />
              </div>
            </div>

            <label>
              Header alignment
              <select
                value={project.siteChrome?.headerAlign || "center"}
                onChange={(event) =>
                  updateProject((prev) => ({
                    ...prev,
                    siteChrome: {
                      ...(prev.siteChrome || defaultSiteChrome),
                      headerAlign: event.target.value,
                    },
                  }))
                }
              >
                <option value="center">Centered navigation</option>
                <option value="left">Logo left / nav center</option>
                <option value="split">Spread out</option>
              </select>
            </label>

            <label>
              Header button text
              <input
                value={project.siteChrome?.headerButtonLabel || "Contact"}
                onChange={(event) =>
                  updateProject((prev) => ({
                    ...prev,
                    siteChrome: {
                      ...(prev.siteChrome || defaultSiteChrome),
                      headerButtonLabel: event.target.value,
                    },
                  }))
                }
              />
            </label>

            <label>
              Footer description
              <textarea
                value={project.siteChrome?.description || defaultSiteChrome.description}
                onChange={(event) =>
                  updateProject((prev) => ({
                    ...prev,
                    siteChrome: {
                      ...(prev.siteChrome || defaultSiteChrome),
                      description: event.target.value,
                    },
                  }))
                }
              />
            </label>

            <label>
              Shop column title
              <input
                value={project.siteChrome?.footerShopTitle || "Shop"}
                onChange={(event) =>
                  updateProject((prev) => ({
                    ...prev,
                    siteChrome: {
                      ...(prev.siteChrome || defaultSiteChrome),
                      footerShopTitle: event.target.value,
                    },
                  }))
                }
              />
            </label>

            <label>
              Shop links, one per line
              <textarea
                value={project.siteChrome?.footerShopLinks || "All Products\nAll Categories"}
                onChange={(event) =>
                  updateProject((prev) => ({
                    ...prev,
                    siteChrome: {
                      ...(prev.siteChrome || defaultSiteChrome),
                      footerShopLinks: event.target.value,
                    },
                  }))
                }
              />
            </label>

            <label>
              Help column title
              <input
                value={project.siteChrome?.footerHelpTitle || "Help"}
                onChange={(event) =>
                  updateProject((prev) => ({
                    ...prev,
                    siteChrome: {
                      ...(prev.siteChrome || defaultSiteChrome),
                      footerHelpTitle: event.target.value,
                    },
                  }))
                }
              />
            </label>

            <label>
              Help links, one per line
              <textarea
                value={project.siteChrome?.footerHelpLinks || "Our Policies\nAbout Us\nTrack Your Orders"}
                onChange={(event) =>
                  updateProject((prev) => ({
                    ...prev,
                    siteChrome: {
                      ...(prev.siteChrome || defaultSiteChrome),
                      footerHelpLinks: event.target.value,
                    },
                  }))
                }
              />
            </label>

            <label>
              Social links/names, one per line
              <textarea
                value={project.siteChrome?.footerSocialLinks || "Facebook\nLinkedIn\nX\nInstagram"}
                onChange={(event) =>
                  updateProject((prev) => ({
                    ...prev,
                    siteChrome: {
                      ...(prev.siteChrome || defaultSiteChrome),
                      footerSocialLinks: event.target.value,
                    },
                  }))
                }
              />
            </label>

            <label>
              Payment methods, one per line
              <textarea
                value={project.siteChrome?.footerPaymentMethods || "Visa\nMastercard\nApple Pay\nGoogle Pay"}
                onChange={(event) =>
                  updateProject((prev) => ({
                    ...prev,
                    siteChrome: {
                      ...(prev.siteChrome || defaultSiteChrome),
                      footerPaymentMethods: event.target.value,
                    },
                  }))
                }
              />
            </label>

            <label>
              Contact email
              <input
                value={project.siteChrome?.contactEmail || "info@madar.com"}
                onChange={(event) =>
                  updateProject((prev) => ({
                    ...prev,
                    siteChrome: {
                      ...(prev.siteChrome || defaultSiteChrome),
                      contactEmail: event.target.value,
                    },
                  }))
                }
              />
            </label>

            <label>
              Phone
              <input
                value={project.siteChrome?.phone || "+972 0599203857"}
                onChange={(event) =>
                  updateProject((prev) => ({
                    ...prev,
                    siteChrome: {
                      ...(prev.siteChrome || defaultSiteChrome),
                      phone: event.target.value,
                    },
                  }))
                }
              />
            </label>

            <label>
              Madar link
              <input
                value={project.siteChrome?.madarLink || "/"}
                onChange={(event) =>
                  updateProject((prev) => ({
                    ...prev,
                    siteChrome: {
                      ...(prev.siteChrome || defaultSiteChrome),
                      madarLink: event.target.value,
                    },
                  }))
                }
              />
            </label>
          </details>

          <button type="button" className="danger-button" onClick={deleteActivePage}>
            Delete Page
          </button>
        </div>
      )}

      {selectedSection && (
        <div className="inspector-group">
          <h3>Section Settings</h3>

          <label>
            Section name
            <input
              value={selectedSection.name}
              onChange={(event) => updateSelectedSection({ name: event.target.value })}
            />
          </label>

          <label>
            Layout style
            <select
              value={selectedSection.mode}
              onChange={(event) => {
                const mode = event.target.value;
                updateSelectedSection({
                  mode,
                  rows:
                    mode === "auto"
                      ? selectedSection.rows.length
                        ? selectedSection.rows
                        : [createRow([createColumn([createElement("heading")])])]
                      : [],
                  freeElements:
                    mode === "free"
                      ? selectedSection.freeElements.length
                        ? selectedSection.freeElements
                        : freeCanvasSection().freeElements
                      : [],
                });
              }}
            >
              <option value="auto">Auto layout — recommended</option>
              <option value="free">Free canvas — advanced</option>
            </select>
          </label>

          <label>
            Width
            <select
              value={selectedSection.layout.width}
              onChange={(event) => updateSelectedSection({ layout: { width: event.target.value } })}
            >
              <option value="small">Small</option>
              <option value="medium">Medium</option>
              <option value="large">Large</option>
              <option value="full">Full</option>
            </select>
          </label>

          {selectedSection.mode === "auto" && (
            <label>
              Spacing
              <select
                value={selectedSection.layout.paddingY}
                onChange={(event) => updateSelectedSection({ layout: { paddingY: event.target.value } })}
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
              onChange={(event) => updateSelectedSection({ layout: { background: event.target.value } })}
            />
          </label>

          {selectedSection.mode === "free" && (
            <label>
              Section height
              <input
                type="number"
                value={selectedSection.layout.minHeight}
                onChange={(event) =>
                  updateSelectedSection({ layout: { minHeight: Number(event.target.value) } })
                }
              />
            </label>
          )}

          <button type="button" className="danger-button" onClick={deleteSelectedSection}>
            Delete Section
          </button>
        </div>
      )}

      {selectedColumn && (
        <div className="inspector-group">
          <h3>Column Settings</h3>
          <label>
            Alignment
            <select
              value={selectedColumn.layout.align}
              onChange={(event) => updateSelectedColumn({ layout: { align: event.target.value } })}
            >
              <option value="left">Left</option>
              <option value="center">Center</option>
              <option value="right">Right</option>
            </select>
          </label>
        </div>
      )}

      {selectedElement && (
        <div className="inspector-group">
          <h3>{selectedElement.name}</h3>

          <label>
            Internal name
            <input
              value={selectedElement.name}
              onChange={(event) => updateSelectedElement({ name: event.target.value })}
            />
          </label>

          {selectedElement.type === "image" && (
            <div className="image-upload-control">
              <label>
                Image URL
                <input
                  value={selectedElement.content}
                  placeholder="Paste image URL or upload from your device"
                  onChange={(event) => updateSelectedElement({ content: event.target.value })}
                />
              </label>

              <label className="upload-image-button">
                Upload from device
                <input
                  type="file"
                  accept="image/*"
                  onChange={(event) => uploadImageForSelectedElement(event.target.files?.[0])}
                />
              </label>

              {selectedElement.content && (
                <div className="image-upload-preview">
                  <img src={selectedElement.content} alt="Selected preview" />
                </div>
              )}
            </div>
          )}

          {selectedElement.type !== "image" &&
            selectedElement.type !== "formBlock" &&
            selectedElement.type !== "responsesTable" && (
              <label>
                Text / value
                <textarea
                  value={selectedElement.content}
                  onChange={(event) => updateSelectedElement({ content: event.target.value })}
                />
              </label>
            )}

          {(selectedElement.type === "formBlock" || selectedElement.type === "responsesTable") && (
            <label>
              Connected form
              <select
                value={selectedElement.connectedFormId}
                onChange={(event) => updateSelectedElement({ connectedFormId: event.target.value })}
              >
                <option value="">Choose form</option>
                {project.forms.map((form) => (
                  <option key={form.id} value={form.id}>
                    {form.title}
                  </option>
                ))}
              </select>
            </label>
          )}

          {selectedElement.type === "button" && (
            <details open>
              <summary>Button action</summary>
              <label>
                What should this button do?
                <select
                  value={selectedElement.action.type}
                  onChange={(event) => updateSelectedElement({ action: { type: event.target.value } })}
                >
                  <option value="none">Nothing</option>
                  <option value="goToPage">Go to page</option>
                  <option value="openUrl">Open website link</option>
                </select>
              </label>

              {selectedElement.action.type === "goToPage" && (
                <label>
                  Target page
                  <select
                    value={selectedElement.action.pageId}
                    onChange={(event) => updateSelectedElement({ action: { pageId: event.target.value } })}
                  >
                    <option value="">Choose page</option>
                    {project.pages.map((page) => (
                      <option key={page.id} value={page.id}>
                        {page.name}
                      </option>
                    ))}
                  </select>
                </label>
              )}

              {selectedElement.action.type === "openUrl" && (
                <label>
                  Website link
                  <input
                    value={selectedElement.action.url}
                    onChange={(event) => updateSelectedElement({ action: { url: event.target.value } })}
                  />
                </label>
              )}
            </details>
          )}

          <details>
            <summary>Style</summary>

            {selectedElement.type !== "image" && (
              <>
                <label>
                  Text color
                  <input
                    type="color"
                    value={selectedElement.styles.color || "#1a2744"}
                    onChange={(event) => updateSelectedElement({ styles: { color: event.target.value } })}
                  />
                </label>

                <label>
                  Font size
                  <input
                    value={selectedElement.styles.fontSize}
                    placeholder="16px"
                    onChange={(event) => updateSelectedElement({ styles: { fontSize: event.target.value } })}
                  />
                </label>

                <label>
                  Text align
                  <select
                    value={selectedElement.styles.textAlign}
                    onChange={(event) => updateSelectedElement({ styles: { textAlign: event.target.value } })}
                  >
                    <option value="left">Left</option>
                    <option value="center">Center</option>
                    <option value="right">Right</option>
                  </select>
                </label>
              </>
            )}

            {["button", "card", "metric", "formBlock", "responsesTable"].includes(selectedElement.type) && (
              <label>
                Background
                <input
                  type="color"
                  value={selectedElement.styles.backgroundColor || "#ffffff"}
                  onChange={(event) =>
                    updateSelectedElement({ styles: { backgroundColor: event.target.value } })
                  }
                />
              </label>
            )}

            <label>
              Rounded corners
              <input
                value={selectedElement.styles.borderRadius}
                onChange={(event) => updateSelectedElement({ styles: { borderRadius: event.target.value } })}
              />
            </label>
          </details>

          <details open>
            <summary>Size & Position</summary>
            <p className="inspector-help-text">
              Drag this element on the page, or adjust its width, height, X, and Y here.
            </p>

            <div className="position-grid">
              {["x", "y", "width", "height"].map((key) => (
                <label key={key}>
                  {key === "x"
                    ? "Move right"
                    : key === "y"
                    ? "Move down"
                    : key === "width"
                    ? "Width"
                    : "Height"}
                  <input
                    type="number"
                    value={selectedElement.position?.[viewport]?.[key] ?? createPosition()[viewport][key]}
                    onFocus={(event) => event.target.select()}
                    onChange={(event) => updateElementPosition(key, event.target.value)}
                  />
                </label>
              ))}
            </div>

            <button
              type="button"
              className="reset-position-button"
              onClick={() =>
                updateSelectedElement({
                  position: {
                    ...selectedElement.position,
                    [viewport]: createPosition()[viewport],
                  },
                })
              }
            >
              Reset size & position
            </button>
          </details>

          <button type="button" className="danger-button" onClick={deleteSelectedElement}>
            Delete Element
          </button>
        </div>
      )}
    </aside>
  );

  const renderFormsTab = () => (
    <main className="forms-builder-page sections-form-builder">
      <aside className="forms-left-rail">
        <div className="rail-card">
          <div className="rail-card-header">
            <div>
              <h3>Forms</h3>
              <p>Choose a form.</p>
            </div>

            <button type="button" onClick={addForm} aria-label="Create form">
              +
            </button>
          </div>

          <div className="forms-list compact-form-list">
            {project.forms.map((form) => (
              <button
                type="button"
                key={form.id}
                className={form.id === project.activeFormId ? "active" : ""}
                onClick={() => selectForm(form.id)}
              >
                <strong>{form.title}</strong>
                <span>
                  {getFormQuestions(form).length} questions · {form.responses.length} responses
                </span>
              </button>
            ))}
          </div>
        </div>
      </aside>

      <section
        className="forms-document-area"
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => handleQuestionDrop(event, getSelectedFormSectionId())}
      >
        {activeForm && (
          <div className="forms-document">
            <article className="google-form-title-card simple-form-title">
              <input
                className="form-title-clean-input"
                value={activeForm.title}
                onChange={(event) => updateActiveForm((form) => ({ ...form, title: event.target.value }))}
                placeholder="Untitled form"
              />

              <textarea
                className="form-description-clean-input"
                value={activeForm.description}
                onChange={(event) =>
                  updateActiveForm((form) => ({ ...form, description: event.target.value }))
                }
                placeholder="Form description"
              />
            </article>

            <div className="form-sections-stack">
              {getFormSections(activeForm).map((section, sectionIndex) => (
                <article
                  key={section.id}
                  className={`form-section-card ${
                    selected.type === "formSection" && selected.id === section.id ? "active" : ""
                  }`}
                  onClick={() => setSelected({ type: "formSection", id: section.id })}
                >
                  <div className="form-section-top">
                    <div className="section-index">{sectionIndex + 1}</div>

                    <div className="section-title-fields">
                      <input
                        className="section-title-input"
                        value={section.title}
                        onChange={(event) => updateFormSection(section.id, { title: event.target.value })}
                        placeholder="Section title"
                      />

                      <textarea
                        className="section-description-input"
                        value={section.description}
                        onChange={(event) =>
                          updateFormSection(section.id, { description: event.target.value })
                        }
                        placeholder="Section description, optional"
                      />
                    </div>

                    <div className="section-card-actions">
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          updateFormSection(section.id, { collapsed: !section.collapsed });
                        }}
                      >
                        {section.collapsed ? "Expand" : "Collapse"}
                      </button>

                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          duplicateFormSection(section);
                        }}
                      >
                        Duplicate
                      </button>

                      <button
                        type="button"
                        className="danger-lite"
                        onClick={(event) => {
                          event.stopPropagation();
                          deleteFormSection(section.id);
                        }}
                      >
                        Delete
                      </button>
                    </div>
                  </div>

                  {!section.collapsed && (
                    <>
                      <div
                        className="section-drop-zone"
                        onDragOver={(event) => event.preventDefault()}
                        onDrop={(event) => handleQuestionDrop(event, section.id, 0)}
                      >
                        <span>Drop a question into this section</span>
                      </div>

                      <div className="section-elements-stack">
                        {(section.elements || []).map((question, questionIndex) => (
                          <div key={question.id}>
                            <article
                              className={`google-question-card clean-question-card section-question-card ${
                                selected.id === question.id ? "active" : ""
                              }`}
                              onClick={(event) => {
                                event.stopPropagation();
                                setSelected({ type: "question", id: question.id });
                              }}
                            >
                              <div className="clean-question-top">
                                <span className="question-index">{questionIndex + 1}</span>

                                <input
                                  className="question-title-input clean-title-input"
                                  value={question.label}
                                  onChange={(event) => updateQuestion(question.id, { label: event.target.value })}
                                  placeholder="Question"
                                />
                              </div>

                              <div className="clean-answer-row">
                                <select
                                  className="answer-type-select clean-answer-select"
                                  value={question.type}
                                  onChange={(event) =>
                                    updateQuestion(question.id, {
                                      type: event.target.value,
                                      placeholder:
                                        friendlyQuestionTypes.find((item) => item.id === event.target.value)
                                          ?.placeholder || "",
                                    })
                                  }
                                >
                                  {["Basic", "Contact", "Choices", "Business"].map((group) => (
                                    <optgroup key={group} label={group}>
                                      {friendlyQuestionTypes
                                        .filter((type) => type.group === group)
                                        .map((type) => (
                                          <option key={type.id} value={type.id}>
                                            {type.label}
                                          </option>
                                        ))}
                                    </optgroup>
                                  ))}
                                </select>

                                <input
                                  className="helper-text-clean-input"
                                  value={question.helpText}
                                  placeholder="Helper text, optional"
                                  onChange={(event) => updateQuestion(question.id, { helpText: event.target.value })}
                                />
                              </div>

                              {["dropdown", "multipleChoice", "checkboxes", "status"].includes(question.type) && (
                                <label className="options-clean-field">
                                  Options
                                  <textarea
                                    value={question.options.join("\n")}
                                    onChange={(event) =>
                                      updateQuestion(question.id, {
                                        options: event.target.value
                                          .split("\n")
                                          .map((item) => item.trim())
                                          .filter(Boolean),
                                      })
                                    }
                                    placeholder={"Option 1\nOption 2"}
                                  />
                                </label>
                              )}

                              <div className="google-question-preview clean-question-preview">
                                {renderQuestionInput(activeForm, question, true)}
                              </div>

                              <div className="google-question-footer clean-question-footer">
                                <div className="question-footer-left">
                                  <button type="button" onClick={() => moveQuestion(question.id, "up")}>
                                    ↑
                                  </button>
                                  <button type="button" onClick={() => moveQuestion(question.id, "down")}>
                                    ↓
                                  </button>
                                </div>

                                <div className="question-footer-right">
                                  <button type="button" onClick={() => duplicateQuestion(question)}>
                                    Duplicate
                                  </button>

                                  <label className="required-switch">
                                    <span>Required</span>
                                    <input
                                      type="checkbox"
                                      checked={question.required}
                                      onChange={(event) =>
                                        updateQuestion(question.id, { required: event.target.checked })
                                      }
                                    />
                                  </label>

                                  <button
                                    type="button"
                                    className="danger-lite"
                                    onClick={() => deleteQuestion(question.id)}
                                  >
                                    Delete
                                  </button>
                                </div>
                              </div>
                            </article>

                            <div
                              className="drop-between-zone"
                              onDragOver={(event) => event.preventDefault()}
                              onDrop={(event) => handleQuestionDrop(event, section.id, questionIndex + 1)}
                            >
                              <span>Drop question here</span>
                            </div>
                          </div>
                        ))}
                      </div>

                      {(section.elements || []).length === 0 && (
                        <div
                          className="empty-section-drop"
                          onDragOver={(event) => event.preventDefault()}
                          onDrop={(event) => handleQuestionDrop(event, section.id)}
                        >
                          <h3>This section is empty</h3>
                          <p>Drag a question type here, or click one from the right toolbar.</p>
                        </div>
                      )}
                    </>
                  )}
                </article>
              ))}
            </div>

            <button type="button" className="add-section-inline" onClick={() => addFormSection()}>
              + Add Section
            </button>
          </div>
        )}
      </section>

      <aside className="forms-floating-tools">
        <div className="floating-tools-card">
          <h3>Add to form</h3>

          <button type="button" className="add-section-tool" onClick={() => addFormSection()}>
            + Section
          </button>

          <div className="floating-question-buttons">
            {friendlyQuestionTypes.map((type) => (
              <button
                type="button"
                key={type.id}
                draggable
                title={`Add ${type.label}`}
                onClick={() => addQuestion(type.id)}
                onDragStart={(event) => {
                  setDragQuestionType(type.id);
                  event.dataTransfer.setData("question/type", type.id);
                  event.dataTransfer.effectAllowed = "copy";
                }}
                onDragEnd={() => setDragQuestionType(null)}
              >
                <span>+</span>
                <b>{type.label}</b>
              </button>
            ))}
          </div>
        </div>

        {activeForm && (
          <div className="floating-tools-card after-submit-card">
            <h3>After submit</h3>

            <textarea
              value={activeForm.successMessage}
              onChange={(event) =>
                updateActiveForm((form) => ({ ...form, successMessage: event.target.value }))
              }
            />

            <div className="simple-flow compact-simple-flow">
              <div>
                <span>1</span>
                Save response
              </div>
              <div>
                <span>2</span>
                Show message
              </div>
            </div>
          </div>
        )}
      </aside>
    </main>
  );

  const renderResponsesTab = () => (
    <main className="workspace-page">
      <div className="workspace-header">
        <div>
          <h2>Responses</h2>
          <p>Responses are the submitted answers from your forms. No database setup needed.</p>
        </div>

        <select value={project.activeFormId} onChange={(event) => selectForm(event.target.value)}>
          {project.forms.map((form) => (
            <option key={form.id} value={form.id}>
              {form.title}
            </option>
          ))}
        </select>
      </div>

      {activeForm && (
        <section className="responses-page-card">
          <div className="responses-page-header">
            <div>
              <h3>{activeForm.title}</h3>
              <p>{activeForm.responses.length} submitted responses</p>
            </div>

            <button type="button" onClick={() => alert("Export CSV should be implemented in backend/frontend later.")}>
              Export
            </button>
          </div>

          {renderResponsesTable(activeForm.id)}
        </section>
      )}
    </main>
  );

  const renderAutomationsTab = () => (
    <main className="workspace-page">
      <div className="workspace-header">
        <div>
          <h2>Automations</h2>
          <p>Choose what happens after someone submits a form. Keep it simple and guided.</p>
        </div>

        <button
          type="button"
          onClick={() => {
            const automation = createAutomation(`After ${activeForm?.title || "form"} is submitted`, project.activeFormId);
            updateProject((prev) => ({ ...prev, automations: [...prev.automations, automation] }));
            setSelected({ type: "automation", id: automation.id });
          }}
        >
          + Automation
        </button>
      </div>

      <div className="automations-grid">
        {project.automations.map((automation) => {
          const form = project.forms.find((item) => item.id === automation.formId);

          return (
            <article
              key={automation.id}
              className={`automation-card ${selected.id === automation.id ? "active" : ""}`}
              onClick={() => setSelected({ type: "automation", id: automation.id })}
            >
              <div className="automation-card-header">
                <label>
                  Automation name
                  <input
                    value={automation.name}
                    onChange={(event) =>
                      updateProject((prev) => ({
                        ...prev,
                        automations: prev.automations.map((item) =>
                          item.id === automation.id ? { ...item, name: event.target.value } : item
                        ),
                      }))
                    }
                  />
                </label>

                <label className="checkbox-control">
                  <input
                    type="checkbox"
                    checked={automation.enabled}
                    onChange={(event) =>
                      updateProject((prev) => ({
                        ...prev,
                        automations: prev.automations.map((item) =>
                          item.id === automation.id ? { ...item, enabled: event.target.checked } : item
                        ),
                      }))
                    }
                  />
                  Enabled
                </label>
              </div>

              <div className="when-box">
                <span>When</span>
                <strong>{form?.title || "A form"} is submitted</strong>
              </div>

              <div className="then-list">
                <span>Then</span>
                {automation.steps.map((step, index) => (
                  <div key={step.id} className="then-step">
                    <b>{index + 1}</b>
                    <div>
                      <strong>{step.label}</strong>
                      <p>{step.details}</p>
                    </div>
                  </div>
                ))}
              </div>

              <div className="automation-template-actions">
                <button type="button">Save only</button>
                <button type="button">Save + notify</button>
                <button type="button">Approval process</button>
              </div>
            </article>
          );
        })}
      </div>
    </main>
  );

  const renderUsersTab = () => (
    <main className="workspace-page">
      <div className="workspace-header">
        <div>
          <h2>Users</h2>
          <p>Use simple roles. Decide who can submit, view responses, approve, edit, and publish.</p>
        </div>

        <button
          type="button"
          onClick={() => {
            const role = createRole(`Role ${project.roles.length + 1}`);
            updateProject((prev) => ({ ...prev, roles: [...prev.roles, role] }));
          }}
        >
          + Role
        </button>
      </div>

      <div className="roles-grid">
        {project.roles.map((role) => (
          <article
            key={role.id}
            className={`role-card ${selected.id === role.id ? "active" : ""}`}
            onClick={() => setSelected({ type: "role", id: role.id })}
          >
            <label>
              Role name
              <input
                value={role.name}
                onChange={(event) =>
                  updateProject((prev) => ({
                    ...prev,
                    roles: prev.roles.map((item) =>
                      item.id === role.id ? { ...item, name: event.target.value } : item
                    ),
                  }))
                }
              />
            </label>

            <div className="permissions-list">
              {Object.entries(role.permissions).map(([key, value]) => (
                <label key={key} className="checkbox-control">
                  <input
                    type="checkbox"
                    checked={value}
                    onChange={(event) =>
                      updateProject((prev) => ({
                        ...prev,
                        roles: prev.roles.map((item) =>
                          item.id === role.id
                            ? {
                                ...item,
                                permissions: {
                                  ...item.permissions,
                                  [key]: event.target.checked,
                                },
                              }
                            : item
                        ),
                      }))
                    }
                  />
                  {key}
                </label>
              ))}
            </div>
          </article>
        ))}
      </div>
    </main>
  );

  const renderPublishTab = () => (
    <main className="workspace-page">
      <div className="workspace-header">
        <div>
          <h2>Publish</h2>
          <p>Save your draft, preview it, export JSON, or publish locally in this prototype.</p>
        </div>

        <button type="button" onClick={publishProject}>
          Publish
        </button>
      </div>

      <div className="publish-grid">
        <section className="publish-card">
          <h3>Status</h3>
          <p>
            Current status: <strong>{project.status}</strong>
          </p>
          <p>
            Last saved: <strong>{project.publish.lastSavedAt || "Not saved yet"}</strong>
          </p>
          <p>
            Last published: <strong>{project.publish.lastPublishedAt || "Not published yet"}</strong>
          </p>
        </section>

        <section className="publish-card">
          <h3>Actions</h3>
          <button type="button" onClick={saveProject}>Save locally</button>
          <button type="button" onClick={loadProject}>Load saved</button>
          <button type="button" onClick={exportProject}>Export JSON</button>
        </section>

        <section className="publish-card">
          <h3>Project summary</h3>
          <pre>
            {JSON.stringify(
              {
                pages: project.pages.length,
                forms: project.forms.length,
                responses: project.forms.reduce((total, form) => total + form.responses.length, 0),
                automations: project.automations.length,
                roles: project.roles.length,
              },
              null,
              2
            )}
          </pre>
        </section>
      </div>
    </main>
  );

  const renderModal = () => {
    if (modal === "starter") {
      return (
        <div className="builder-modal-backdrop" onClick={() => setModal(null)}>
          <div className="builder-modal large-modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>Choose a starter</h2>
                <p>Pick a starting point. You can rename and edit everything after.</p>
              </div>
              <button type="button" onClick={() => setModal(null)}>×</button>
            </div>

            <div className="starter-grid">
              {starterSystems.map((starter) => (
                <article key={starter.id} className="starter-card">
                  <h3>{starter.title}</h3>
                  <p>{starter.subtitle}</p>
                  <ul>
                    {starter.creates.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                  <button type="button" onClick={() => applyStarter(starter.id)}>
                    Use Starter
                  </button>
                </article>
              ))}
            </div>
          </div>
        </div>
      );
    }

    if (modal === "section") {
      return (
        <div className="builder-modal-backdrop" onClick={() => setModal(null)}>
          <div className="builder-modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>Add section</h2>
                <p>Choose a block to add to the current page.</p>
              </div>
              <button type="button" onClick={() => setModal(null)}>×</button>
            </div>

            <div className="section-grid">
              {sectionLibrary.map((section) => (
                <article key={section.id} className="section-card">
                  <span>{section.category}</span>
                  <h3>{section.title}</h3>
                  <p>{section.description}</p>
                  <button type="button" onClick={() => addSection(section.create)}>
                    Add Section
                  </button>
                </article>
              ))}
            </div>
          </div>
        </div>
      );
    }

    return null;
  };

  return (
    <>
      <section className="builder-mobile-blocker">
        <div>
          <h1>Builder is available on larger screens.</h1>
          <p>Use tablet or desktop to safely edit pages, forms, and automations.</p>
        </div>
      </section>

      <div
        className={`page-builder builder-desktop-shell ${preview ? "preview-mode" : ""}`}
        onMouseMove={handleMouseMove}
        onMouseUp={() => setDragState(null)}
        onMouseLeave={() => setDragState(null)}
      >
        <header className="builder-topbar">
          <div className="builder-brand">
            <h1>{project.name}</h1>
            <p>{project.description}</p>
          </div>

          <div className="builder-topbar-actions">
            {activeTab === "pages" && !preview && (
              <button type="button" className="primary-action" onClick={() => setModal("section")}>
                + Add Section
              </button>
            )}

            {activeTab === "forms" && !preview && (
              <button type="button" className="primary-action" onClick={() => addQuestion("shortText")}>
                + Add Question
              </button>
            )}

            <button type="button" onClick={() => setPreview((current) => !current)}>
              {preview ? "Exit Preview" : "Preview"}
            </button>

            <button type="button" className="primary-action" onClick={saveProject}>
              Save
            </button>
          </div>
        </header>

        {!preview && (
          <div className="builder-subbar">
            <nav className="workspace-tabs">
              {appTabs.map((tab) => (
                <button
                  type="button"
                  key={tab.id}
                  className={activeTab === tab.id ? "active" : ""}
                  onClick={() => setActiveTab(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </nav>


          </div>
        )}

        {preview && (
          <div className="preview-device-toolbar">
            <div className="viewport-switcher">
              {["desktop", "tablet", "mobile"].map((mode) => (
                <button
                  type="button"
                  key={mode}
                  className={viewport === mode ? "active" : ""}
                  onClick={() => setViewport(mode)}
                >
                  {mode}
                </button>
              ))}
            </div>
          </div>
        )}

        {activeTab === "pages" && renderPagesTab()}
        {!preview && activeTab === "forms" && renderFormsTab()}
        {!preview && activeTab === "responses" && renderResponsesTab()}
        {!preview && activeTab === "automations" && renderAutomationsTab()}
        {!preview && activeTab === "users" && renderUsersTab()}
        {!preview && activeTab === "publish" && renderPublishTab()}

        {renderModal()}
      </div>
    </>
  );
}
