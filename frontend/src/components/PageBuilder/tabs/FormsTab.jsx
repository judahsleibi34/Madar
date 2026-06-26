import { useRef, useState } from "react";
import {
  AlignCenter,
  AlignJustify,
  AlignLeft,
  AlignRight,
  Baseline,
  Bold,
  ChevronDown,
  ChevronUp,
  Copy,
  Eye,
  FilePlus2,
  Italic,
  List,
  ListOrdered,
  ListPlus,
  Plus,
  Redo2,
  Send,
  Settings,
  Save,
  Highlighter,
  Trash2,
  Underline,
  Undo2,
} from "lucide-react";
import { applyFormTemplate, FORM_TEMPLATES } from "../PageBuilder.formTemplates";
import {
  getDirectionForLanguage,
  getLocalizedOptions,
  getLocalizedValue,
  normalizeLanguageMode,
  setLocalizedOptions,
  setLocalizedValue,
} from "../PageBuilder.localization";
import PageDeleteConfirmModal from "../PageDeleteConfirmModal";

const choiceFieldTypes = new Set(["dropdown", "radio", "checkboxes", "status"]);

const commonFieldTypes = [
  "shortText",
  "paragraph",
  "email",
  "number",
  "date",
  "radio",
  "checkboxes",
  "file",
];

const legacyFieldTypes = {
  money: { id: "money", label: "Price or budget", group: "Number", input: "number" },
  phone: { id: "phone", label: "Phone", group: "Contact", input: "tel" },
  radio: { id: "radio", label: "Radio buttons", group: "Choice", input: "radio" },
  yesNo: { id: "yesNo", label: "Yes or no", group: "Choice", input: "yesNo" },
  status: { id: "status", label: "Status selector", group: "Workflow", input: "select" },
};

const textToolbarButtons = [
  { action: "undo", label: "Undo", icon: Undo2 },
  { action: "redo", label: "Redo", icon: Redo2 },
  { action: "bold", label: "Bold", icon: Bold },
  { action: "italic", label: "Italic", icon: Italic },
  { action: "underline", label: "Underline", icon: Underline },
  { action: "bullets", label: "Bulleted list", icon: List },
  { action: "numbers", label: "Numbered list", icon: ListOrdered },
  { action: "align-left", label: "Align left", icon: AlignLeft },
  { action: "align-center", label: "Align center", icon: AlignCenter },
  { action: "align-right", label: "Align right", icon: AlignRight },
  { action: "align-justify", label: "Justify", icon: AlignJustify },
];

function FormButton({
  children,
  ariaLabel,
  className = "",
  disabled = false,
  icon: Icon,
  onClick,
  title,
  variant = "default",
}) {
  const classes = ["form-command-button", `form-command-button-${variant}`, className]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      type="button"
      className={classes}
      disabled={disabled}
      onClick={onClick}
      aria-label={ariaLabel || (typeof children === "string" ? children : title)}
      title={title}
    >
      {Icon && <Icon size={16} aria-hidden="true" />}
      {children}
    </button>
  );
}

export default function FormsTab({
  project,
  activeForm,
  fieldTypes,
  selected,
  lang = "en",

  selectForm,
  selectPage,
  setActiveTab,
  setDesignPanel,
  setSelected,
  openPreviewPage,

  addForm,
  deleteActiveForm,
  addFormSection,
  addFieldToForm,
  updateActiveForm,
  updateActiveFormQuiz,
  updateFormField,
  updateFormSection,
  renderQuizAnswerKeyEditor,
  moveFormField,
  duplicateFormField,
  deleteFormField,
  deleteFormSection,

  getFormFields,
  getFormSections,
  getQuizSettings,
  getFormPlacements,
  addConnectedFormSectionToPage,
  openFormPreviewPage,
  saveProject,
  publishProject,

  quizOptionsOpen,
  setQuizOptionsOpen,
}) {
  const [questionType, setQuestionType] = useState("shortText");
  const [showPublishPanel, setShowPublishPanel] = useState(false);
  const [templateId, setTemplateId] = useState("");
  const [deleteFormCandidate, setDeleteFormCandidate] = useState(null);
  const [deleteFormPageCandidate, setDeleteFormPageCandidate] = useState(null);
  const activeTextTargetRef = useRef(null);
  const formLanguageMode = normalizeLanguageMode(activeForm?.languageMode || lang);
  const primaryLanguage =
    formLanguageMode === "bilingual"
      ? normalizeLanguageMode(activeForm?.defaultLanguage || "en")
      : formLanguageMode;
  const translationLanguage = primaryLanguage === "ar" ? "en" : "ar";
  const translationsEnabled = formLanguageMode === "bilingual";
  const formDirection = getDirectionForLanguage(primaryLanguage);
  const translationDirection = getDirectionForLanguage(translationLanguage);

  const getFieldType = (type) =>
    fieldTypes.find((item) => item.id === type) || legacyFieldTypes[type] || fieldTypes[0];
  const getVisibleFieldTypes = (currentType = "") => {
    const visibleTypes = commonFieldTypes.map((typeId) => getFieldType(typeId));
    if (currentType && !commonFieldTypes.includes(currentType)) {
      return [getFieldType(currentType), ...visibleTypes];
    }
    return visibleTypes;
  };
  const sections = activeForm ? getFormSections(activeForm) : [];
  const activeSectionId = sections[0]?.id || null;
  const placements = activeForm ? getFormPlacements(activeForm.id) : [];
  const getFriendlyPageTitle = (section, sectionIndex) => {
    if (sectionIndex === 0) return "Title page";
    const title = section.title || "";
    const legacyMatch = title.match(/^Section\s+(\d+)$/i);
    return legacyMatch ? `Page ${legacyMatch[1]}` : title || `Page ${sectionIndex + 1}`;
  };

  const addQuestion = (typeId = questionType, sectionId = activeSectionId) => {
    addFieldToForm(sectionId, typeId);
  };

  const applyTemplate = (nextTemplateId) => {
    setTemplateId(nextTemplateId);
    if (!nextTemplateId) return;
    if (!window.confirm("Replace this form with the selected template?")) {
      setTemplateId("");
      return;
    }
    updateActiveForm((form) => applyFormTemplate(form, nextTemplateId));
  };

  const deleteCurrentForm = () => {
    if (!activeForm) return;
    setDeleteFormCandidate(activeForm);
  };

  const confirmDeleteCurrentForm = () => {
    if (!deleteFormCandidate) return;
    deleteActiveForm?.();
    setDeleteFormCandidate(null);
  };

  const confirmDeleteFormPage = () => {
    if (!deleteFormPageCandidate) return;
    deleteFormSection(deleteFormPageCandidate.section.id);
    setDeleteFormPageCandidate(null);
  };

  const getEditableOptions = (field) => getLocalizedOptions(field, primaryLanguage);
  const getTranslationOptions = (field) => getLocalizedOptions(field, translationLanguage);
  const getExplicitTranslationOptions = (field) => {
    const localized = field?.localized?.options || field?.optionsI18n;
    if (localized && typeof localized === "object" && Array.isArray(localized[translationLanguage])) {
      return localized[translationLanguage];
    }
    return [];
  };

  const updateFieldOption = (field, optionIndex, value) => {
    const nextOptions = getEditableOptions(field).map((option, index) =>
      index === optionIndex ? value : option
    );
    updateFormField(field.id, setLocalizedOptions(field, primaryLanguage, nextOptions));
  };

  const updateFieldTranslationOption = (field, optionIndex, value) => {
    const nextOptions = getTranslationOptions(field).map((option, index) =>
      index === optionIndex ? value : option
    );
    updateFormField(field.id, setLocalizedOptions(field, translationLanguage, nextOptions));
  };

  const insertFieldOption = (field, afterIndex = getEditableOptions(field).length - 1) => {
    const nextOptions = [...getEditableOptions(field)];
    nextOptions.splice(afterIndex + 1, 0, "");
    if (translationsEnabled) {
      const translationOptions = [...getTranslationOptions(field)];
      translationOptions.splice(afterIndex + 1, 0, "");
      updateFormField(field.id, {
        ...setLocalizedOptions(field, primaryLanguage, nextOptions),
        localized: {
          ...(field.localized || {}),
          options: {
            ...(field.localized?.options || field.optionsI18n || {}),
            [primaryLanguage]: nextOptions,
            [translationLanguage]: translationOptions,
          },
        },
        options: primaryLanguage === "en" ? nextOptions : field.options,
      });
      return;
    }
    updateFormField(field.id, setLocalizedOptions(field, primaryLanguage, nextOptions));
  };

  const deleteFieldOption = (field, optionIndex) => {
    const nextOptions = getEditableOptions(field).filter((_, index) => index !== optionIndex);
    if (translationsEnabled) {
      const translationOptions = getTranslationOptions(field).filter((_, index) => index !== optionIndex);
      const safePrimaryOptions = nextOptions.length ? nextOptions : [""];
      const safeTranslationOptions = translationOptions.length ? translationOptions : [""];
      updateFormField(field.id, {
        ...setLocalizedOptions(field, primaryLanguage, safePrimaryOptions),
        localized: {
          ...(field.localized || {}),
          options: {
            ...(field.localized?.options || field.optionsI18n || {}),
            [primaryLanguage]: safePrimaryOptions,
            [translationLanguage]: safeTranslationOptions,
          },
        },
        options: primaryLanguage === "en" ? safePrimaryOptions : field.options,
      });
      return;
    }
    updateFormField(field.id, setLocalizedOptions(field, primaryLanguage, nextOptions.length ? nextOptions : [""]));
  };

  const updateLocalizedFormValue = (key, value, targetLang = primaryLanguage) => {
    updateActiveForm((form) => setLocalizedValue(form, key, targetLang, value));
  };

  const updateLocalizedFieldValue = (field, key, value, targetLang = primaryLanguage) => {
    updateFormField(field.id, setLocalizedValue(field, key, targetLang, value));
  };

  const getExplicitLocalizedValue = (source, key, targetLang) => {
    const localized = source?.localized?.[key] || source?.[`${key}I18n`];
    if (localized && typeof localized === "object") return localized[targetLang] || "";
    if (source?.[key] && typeof source[key] === "object") return source[key][targetLang] || "";
    return "";
  };

  const addLogicRule = () => {
    const fields = getFormFields(activeForm);
    if (fields.length < 2) return;
    updateActiveForm((form) => ({
      ...form,
      logicRules: [
        ...(Array.isArray(form.logicRules) ? form.logicRules : []),
        {
          id: `logic_${Date.now()}`,
          sourceFieldId: fields[0].id,
          operator: "equals",
          value: "",
          action: "show",
          targetFieldId: fields[1]?.id || fields[0].id,
        },
      ],
    }));
  };

  const updateLogicRule = (ruleId, patch) => {
    updateActiveForm((form) => ({
      ...form,
      logicRules: (form.logicRules || []).map((rule) =>
        rule.id === ruleId ? { ...rule, ...patch } : rule
      ),
    }));
  };

  const deleteLogicRule = (ruleId) => {
    updateActiveForm((form) => ({
      ...form,
      logicRules: (form.logicRules || []).filter((rule) => rule.id !== ruleId),
    }));
  };

  const setPrimaryLanguage = (nextLanguage) => {
    updateActiveForm((form) => ({
      ...form,
      languageMode: formLanguageMode === "bilingual" ? "bilingual" : nextLanguage,
      defaultLanguage: nextLanguage,
    }));
  };

  const setTranslationsEnabled = (enabled) => {
    updateActiveForm((form) => ({
      ...form,
      languageMode: enabled ? "bilingual" : primaryLanguage,
      defaultLanguage: primaryLanguage,
    }));
  };

  const getActiveTextTarget = (field) => {
    const activeElement = document.activeElement;
    if (activeElement?.dataset?.fieldId === field.id && activeElement.dataset.fieldKey) {
      return activeElement;
    }
    const remembered = activeTextTargetRef.current;
    if (remembered?.isConnected && remembered.dataset?.fieldId === field.id && remembered.dataset.fieldKey) {
      return remembered;
    }
    return null;
  };

  const replaceSelection = (field, formatter) => {
    const target = getActiveTextTarget(field);
    const key = target?.dataset?.fieldKey || "helpText";
    const targetLang = target?.dataset?.fieldLang || primaryLanguage;
    const value = target ? String(target.value || "") : String(getLocalizedValue(field, key, targetLang) || "");
    const start = target ? target.selectionStart ?? value.length : value.length;
    const end = target ? target.selectionEnd ?? value.length : value.length;
    const selected = value.slice(start, end);
    const result = formatter({ value, selected, start, end });
    updateLocalizedFieldValue(field, key, result.text, targetLang);
    window.requestAnimationFrame(() => {
      if (!target) return;
      target.focus();
      const cursorStart = result.selectionStart ?? result.text.length;
      const cursorEnd = result.selectionEnd ?? cursorStart;
      target.setSelectionRange?.(cursorStart, cursorEnd);
    });
  };

  const listSelection = (field, ordered = false) => {
    replaceSelection(field, ({ value, selected, start, end }) => {
      if (!selected) {
        return {
          text: `${value.slice(0, start)}${ordered ? "1. " : "- "}${value.slice(end)}`,
          selectionStart: start + (ordered ? 3 : 2),
          selectionEnd: start + (ordered ? 3 : 2),
        };
      }
      const lines = selected.split("\n");
      const replacement = lines
        .map((line, index) => `${ordered ? `${index + 1}.` : "-"} ${line.replace(/^(\d+\.|-)\s*/, "")}`)
        .join("\n");
      return {
        text: `${value.slice(0, start)}${replacement}${value.slice(end)}`,
        selectionStart: start,
        selectionEnd: start + replacement.length,
      };
    });
  };

  const setTextDirection = (field, direction) => {
    const target = getActiveTextTarget(field);
    if (target) {
      target.dir = direction;
      target.style.textAlign = direction === "rtl" ? "right" : "left";
    }
  };

  const runTextToolbarAction = (field, action) => {
    const target = getActiveTextTarget(field);
    if (action === "undo" || action === "redo") {
      document.execCommand(action);
      return;
    }
    if (action === "bold" && target) {
      target.style.fontWeight = target.style.fontWeight === "700" ? "" : "700";
    }
    if (action === "italic" && target) {
      target.style.fontStyle = target.style.fontStyle === "italic" ? "" : "italic";
    }
    if (action === "underline" && target) {
      target.style.textDecoration = target.style.textDecoration === "underline" ? "" : "underline";
    }
    if (action === "bullets") listSelection(field);
    if (action === "numbers") listSelection(field, true);
    if (action === "align-left" && target) target.style.textAlign = "left";
    if (action === "align-center" && target) target.style.textAlign = "center";
    if (action === "align-right" && target) target.style.textAlign = "right";
    if (action === "align-justify" && target) target.style.textAlign = "justify";
  };

  const getFormDescriptionTarget = () => {
    const activeElement = document.activeElement;
    return activeElement?.dataset?.formText ? activeElement : null;
  };

  const replaceFormDescriptionSelection = (formatter) => {
    const target = getActiveFormTextTarget() || getFormDescriptionTarget();
    const key = target?.dataset?.formText || "description";
    const targetLang = target?.dataset?.formLang || primaryLanguage;
    const value = target ? String(target.value || "") : String(getLocalizedValue(activeForm, key, targetLang) || "");
    const start = target ? target.selectionStart ?? value.length : value.length;
    const end = target ? target.selectionEnd ?? value.length : value.length;
    const selected = value.slice(start, end);
    const result = formatter({ value, selected, start, end });
    updateLocalizedFormValue(key, result.text, targetLang);
    window.requestAnimationFrame(() => {
      if (!target) return;
      target.focus();
      const cursorStart = result.selectionStart ?? result.text.length;
      const cursorEnd = result.selectionEnd ?? cursorStart;
      target.setSelectionRange?.(cursorStart, cursorEnd);
    });
  };

  const listFormDescriptionSelection = (ordered = false) => {
    replaceFormDescriptionSelection(({ value, selected, start, end }) => {
      if (!selected) {
        return {
          text: `${value.slice(0, start)}${ordered ? "1. " : "- "}${value.slice(end)}`,
          selectionStart: start + (ordered ? 3 : 2),
          selectionEnd: start + (ordered ? 3 : 2),
        };
      }
      const lines = selected.split("\n");
      const replacement = lines
        .map((line, index) => `${ordered ? `${index + 1}.` : "-"} ${line.replace(/^(\d+\.|-)\s*/, "")}`)
        .join("\n");
      return {
        text: `${value.slice(0, start)}${replacement}${value.slice(end)}`,
        selectionStart: start,
        selectionEnd: start + replacement.length,
      };
    });
  };

  const setFormDescriptionDirection = (direction) => {
    const target = getFormDescriptionTarget();
    if (target) {
      target.dir = direction;
      target.style.textAlign = direction === "rtl" ? "right" : "left";
    }
  };

  const getActiveFormTextTarget = () => {
    const activeElement = document.activeElement;
    if (activeElement?.dataset?.formText) return activeElement;
    const remembered = activeTextTargetRef.current;
    return remembered?.isConnected && remembered.dataset?.formText ? remembered : null;
  };

  const setActiveFormTextDirection = (direction) => {
    const target = getActiveFormTextTarget();
    if (target) {
      target.dir = direction;
      target.style.textAlign = direction === "rtl" ? "right" : "left";
    }
  };

  const runFormDescriptionToolbarAction = (action) => {
    const target = getActiveFormTextTarget();
    if (action === "undo" || action === "redo") {
      document.execCommand(action);
      return;
    }
    if (action === "bold" && target) {
      target.style.fontWeight = target.style.fontWeight === "700" ? "" : "700";
    }
    if (action === "italic" && target) {
      target.style.fontStyle = target.style.fontStyle === "italic" ? "" : "italic";
    }
    if (action === "underline" && target) {
      target.style.textDecoration = target.style.textDecoration === "underline" ? "" : "underline";
    }
    if (action === "bullets") listFormDescriptionSelection();
    if (action === "numbers") listFormDescriptionSelection(true);
    if (action === "align-left" && target) target.style.textAlign = "left";
    if (action === "align-center" && target) target.style.textAlign = "center";
    if (action === "align-right" && target) target.style.textAlign = "right";
    if (action === "align-justify" && target) target.style.textAlign = "justify";
  };

  const applyTargetColor = (target, property, color) => {
    if (!target) return;
    target.style[property] = color;
    target.focus();
  };

  const applyTargetTextStyle = (target, style) => {
    if (!target) return;
    if (style === "h1") {
      target.style.fontSize = "24px";
      target.style.fontWeight = "950";
    } else if (style === "h2") {
      target.style.fontSize = "20px";
      target.style.fontWeight = "900";
    } else if (style === "h3") {
      target.style.fontSize = "17px";
      target.style.fontWeight = "850";
    } else {
      target.style.fontSize = "";
      target.style.fontWeight = "";
    }
    target.focus();
  };

  const openPlacement = (placement) => {
    selectPage(placement.pageId);
    setActiveTab("design");
    setDesignPanel("Layers");
  };

  const saveSettings = async () => {
    if (saveProject) {
      await saveProject();
    }
    setQuizOptionsOpen(false);
  };

  if (!activeForm) {
    return (
      <div className="workspace-page forms-workbench forms-simple-workbench">
        <section className="forms-empty-state">
          <FilePlus2 size={34} aria-hidden="true" />
          <h2>Create your first form</h2>
          <p>Start with a clean form, add questions, then place it on a page.</p>
          <FormButton variant="primary" icon={Plus} onClick={addForm}>
            New form
          </FormButton>
        </section>
      </div>
    );
  }

  return (
    <div className="workspace-page forms-workbench forms-simple-workbench" dir={formDirection}>
      <div className="forms-simple-shell">
        <aside className="simple-add-question" aria-label="Form controls">
          <label>
            Current form
            <select value={activeForm.id} onChange={(event) => selectForm(event.target.value)}>
              {project.forms.map((form) => (
                <option key={form.id} value={form.id}>
                  {form.title || "Untitled form"}
                </option>
              ))}
            </select>
          </label>
          <FormButton icon={Plus} onClick={addForm}>
            New form
          </FormButton>

          <label>
            Templates
            <select value={templateId} onChange={(event) => applyTemplate(event.target.value)}>
              <option value="">Choose a template</option>
              {FORM_TEMPLATES.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.label}
                </option>
              ))}
            </select>
          </label>

          <label>
            Language
            <select
              value={primaryLanguage}
              onChange={(event) => setPrimaryLanguage(event.target.value)}
            >
              <option value="en">English</option>
              <option value="ar">Arabic</option>
            </select>
          </label>

          <div className="form-translation-panel">
            <label className="checkbox-control">
              <input
                type="checkbox"
                checked={translationsEnabled}
                onChange={(event) => setTranslationsEnabled(event.target.checked)}
              />
              Add {translationLanguage === "ar" ? "Arabic" : "English"} translations
            </label>
          </div>

          <label>
            Add question
            <select value={questionType} onChange={(event) => setQuestionType(event.target.value)}>
              {getVisibleFieldTypes().map((type) => (
                <option key={type.id} value={type.id}>
                  {type.label}
                </option>
              ))}
            </select>
          </label>
          <FormButton variant="primary" icon={Plus} onClick={() => addQuestion()}>
            Add question
          </FormButton>
          <FormButton icon={ListPlus} onClick={addFormSection}>
            Add page
          </FormButton>
          <div className="simple-action-groups">
            <section className="simple-action-group">
              <span className="simple-action-group-title">Form actions</span>
              <FormButton icon={Settings} onClick={() => setQuizOptionsOpen(true)}>
                Form settings
              </FormButton>
              <FormButton icon={Eye} onClick={() => openFormPreviewPage?.(activeForm.id)}>
                Preview form
              </FormButton>
              <FormButton variant="primary" icon={Send} onClick={() => setShowPublishPanel((value) => !value)}>
                Place form
              </FormButton>
              <FormButton
                variant="danger"
                icon={Trash2}
                onClick={deleteCurrentForm}
              >
                Delete form
              </FormButton>
            </section>

          </div>
        </aside>

        <main className="forms-simple-document">
        {showPublishPanel && (
          <section className="simple-side-panel">
            <div className="simple-panel-grid">
              <label>
                Page
                <select
                  value={project.activePageId || ""}
                  onChange={(event) => selectPage(event.target.value)}
                >
                  {project.pages.map((page) => (
                    <option key={page.id} value={page.id}>{page.name}</option>
                  ))}
                </select>
              </label>
              <label>
                Save submissions to
                <select
                  value={activeForm.connectedCollectionId || ""}
                  onChange={(event) =>
                    updateActiveForm((form) => ({
                      ...form,
                      connectedCollectionId: event.target.value,
                    }))
                  }
                >
                  <option value="">Form submissions only</option>
                  {project.collections.map((collection) => (
                    <option key={collection.id} value={collection.id}>{collection.name}</option>
                  ))}
                </select>
              </label>
              <FormButton variant="primary" icon={Send} onClick={() => addConnectedFormSectionToPage(activeForm.id)}>
                Add to page
              </FormButton>
            </div>

            {placements.length > 0 && (
              <div className="connected-placement-list">
                <span>Already placed on</span>
                {placements.map((placement) => (
                  <button
                    type="button"
                    key={`${placement.pageId}_${placement.sectionName}`}
                    onClick={() => openPlacement(placement)}
                  >
                    {placement.pageName}
                  </button>
                ))}
              </div>
            )}

            <label>
              Success message
              <textarea
                dir={formDirection}
                value={getLocalizedValue(activeForm, "successMessage", primaryLanguage)}
                onChange={(event) =>
                  updateLocalizedFormValue("successMessage", event.target.value)
                }
              />
            </label>
          </section>
        )}

        <div className="forms-section-stack">
          {sections.map((section, sectionIndex) => (
            <section
              className={`forms-section-sheet simple-section-sheet ${sectionIndex === 0 ? "form-intro-page" : ""}`}
              key={section.id}
            >
              <div className="forms-section-heading">
                <input
                  value={getFriendlyPageTitle(section, sectionIndex)}
                  placeholder={sectionIndex === 0 ? "Title page" : `Page ${sectionIndex + 1}`}
                  readOnly={sectionIndex === 0}
                  onChange={(event) =>
                    updateFormSection(section.id, { title: event.target.value })
                  }
                />
                <FormButton
                  variant="danger"
                  icon={Trash2}
                  onClick={() =>
                    setDeleteFormPageCandidate({
                      section,
                      name: getFriendlyPageTitle(section, sectionIndex),
                    })
                  }
                >
                  Delete page
                </FormButton>
              </div>

              <textarea
                value={section.description || ""}
                placeholder="Page description"
                onChange={(event) =>
                  updateFormSection(section.id, { description: event.target.value })
                }
              />

              {sectionIndex === 0 && (
                <div className="form-page-intro">
                  <div className="question-format-toolbar form-title-toolbar" role="toolbar" aria-label="Form title formatting">
                    <select
                      aria-label="Text style"
                      defaultValue="h1"
                      onChange={(event) => applyTargetTextStyle(getActiveFormTextTarget(), event.target.value)}
                    >
                      <option value="text">Text</option>
                      <option value="h1">H1</option>
                      <option value="h2">H2</option>
                      <option value="h3">H3</option>
                    </select>
                    {textToolbarButtons.map(({ action, label, icon: Icon }) => (
                      <button
                        key={action}
                        type="button"
                        title={label}
                        aria-label={label}
                        onMouseDown={(event) => {
                          event.preventDefault();
                          runFormDescriptionToolbarAction(action);
                        }}
                      >
                        <Icon size={15} aria-hidden="true" />
                      </button>
                    ))}
                    <button
                      type="button"
                      title="Left-to-right"
                      onMouseDown={(event) => {
                        event.preventDefault();
                        setActiveFormTextDirection("ltr");
                      }}
                    >
                      LTR
                    </button>
                    <button
                      type="button"
                      title="Right-to-left"
                      onMouseDown={(event) => {
                        event.preventDefault();
                        setActiveFormTextDirection("rtl");
                      }}
                    >
                      RTL
                    </button>
                    <label className="question-toolbar-color" title="Text color">
                      <Baseline size={16} aria-hidden="true" />
                      <input
                        type="color"
                        defaultValue="#1a2744"
                        onChange={(event) => applyTargetColor(getActiveFormTextTarget(), "color", event.target.value)}
                      />
                    </label>
                    <label className="question-toolbar-color" title="Background color">
                      <Highlighter size={16} aria-hidden="true" />
                      <input
                        type="color"
                        defaultValue="#f4f7fb"
                        onChange={(event) => applyTargetColor(getActiveFormTextTarget(), "backgroundColor", event.target.value)}
                      />
                    </label>
                  </div>
                  <input
                    className="form-title-clean-input"
                    data-form-text="title"
                    dir={formDirection}
                    value={getLocalizedValue(activeForm, "title", primaryLanguage)}
                    placeholder="Untitled form"
                    onFocus={(event) => {
                      activeTextTargetRef.current = event.currentTarget;
                    }}
                    onChange={(event) =>
                      updateLocalizedFormValue("title", event.target.value)
                    }
                  />
                  {translationsEnabled && (
                    <label className="translation-entry-field">
                      <span>{translationLanguage === "ar" ? "Arabic" : "English"} title translation</span>
                      <textarea
                        data-form-text="title"
                        data-form-lang={translationLanguage}
                        rows={2}
                        dir={translationDirection}
                        value={getExplicitLocalizedValue(activeForm, "title", translationLanguage)}
                        placeholder={`Add ${translationLanguage === "ar" ? "Arabic" : "English"} title`}
                        onFocus={(event) => {
                          activeTextTargetRef.current = event.currentTarget;
                        }}
                        onChange={(event) =>
                          updateLocalizedFormValue("title", event.target.value, translationLanguage)
                        }
                      />
                    </label>
                  )}
                  <label className="form-description-field">
                    <span>Form description, shown to people filling it out</span>
                    <div className="question-format-toolbar form-description-toolbar" role="toolbar" aria-label="Form description formatting">
                      <select
                        aria-label="Text style"
                        defaultValue="text"
                        onChange={(event) => applyTargetTextStyle(getActiveFormTextTarget(), event.target.value)}
                      >
                        <option value="text">Text</option>
                        <option value="h1">H1</option>
                        <option value="h2">H2</option>
                        <option value="h3">H3</option>
                      </select>
                      {textToolbarButtons.map(({ action, label, icon: Icon }) => (
                        <button
                          key={action}
                          type="button"
                          title={label}
                          aria-label={label}
                          onMouseDown={(event) => {
                            event.preventDefault();
                            runFormDescriptionToolbarAction(action);
                          }}
                        >
                          <Icon size={15} aria-hidden="true" />
                        </button>
                      ))}
                      <button
                        type="button"
                        title="Left-to-right"
                        onMouseDown={(event) => {
                          event.preventDefault();
                          setActiveFormTextDirection("ltr");
                        }}
                      >
                        LTR
                      </button>
                      <button
                        type="button"
                        title="Right-to-left"
                        onMouseDown={(event) => {
                          event.preventDefault();
                          setActiveFormTextDirection("rtl");
                        }}
                      >
                        RTL
                      </button>
                      <label className="question-toolbar-color" title="Text color">
                        <Baseline size={16} aria-hidden="true" />
                        <input
                          type="color"
                          defaultValue="#1a2744"
                          onChange={(event) => applyTargetColor(getActiveFormTextTarget(), "color", event.target.value)}
                        />
                      </label>
                      <label className="question-toolbar-color" title="Background color">
                        <Highlighter size={16} aria-hidden="true" />
                        <input
                          type="color"
                          defaultValue="#ffffff"
                          onChange={(event) => applyTargetColor(getActiveFormTextTarget(), "backgroundColor", event.target.value)}
                        />
                      </label>
                    </div>
                    <textarea
                      className="form-description-clean-input"
                      data-form-text="description"
                      dir={formDirection}
                      value={getLocalizedValue(activeForm, "description", primaryLanguage)}
                      placeholder="Add a short description or leave this empty"
                      onFocus={(event) => {
                        activeTextTargetRef.current = event.currentTarget;
                      }}
                      onChange={(event) =>
                        updateLocalizedFormValue("description", event.target.value)
                      }
                    />
                    {translationsEnabled && (
                      <div className="translation-entry-field">
                        <span>{translationLanguage === "ar" ? "Arabic" : "English"} description translation</span>
                        <textarea
                          data-form-text="description"
                          data-form-lang={translationLanguage}
                          rows={3}
                          dir={translationDirection}
                          value={getExplicitLocalizedValue(activeForm, "description", translationLanguage)}
                          placeholder={`Add ${translationLanguage === "ar" ? "Arabic" : "English"} description`}
                          onFocus={(event) => {
                            activeTextTargetRef.current = event.currentTarget;
                          }}
                          onChange={(event) =>
                            updateLocalizedFormValue("description", event.target.value, translationLanguage)
                          }
                        />
                      </div>
                    )}
                  </label>
                  <div className="forms-simple-meta">
                    <span>{getFormFields(activeForm).length} questions</span>
                    <span>{sections.length} pages</span>
                    <span>{activeForm.responses.length} responses</span>
                    <span>{activeForm.mode === "quiz" ? "Quiz" : "Form"}</span>
                  </div>
                </div>
              )}

              <div className="questions-stack">
                {(section.fields || []).length === 0 && (
                  <div className="forms-empty-inline">
                    <strong>No questions on this page yet.</strong>
                    <span>Add a question from the side panel to start building this form.</span>
                  </div>
                )}
                {(section.fields || []).map((field, fieldIndex) => (
                  <article
                    className={`question-sheet simple-question-card ${selected.id === field.id ? "active" : ""}`}
                    key={field.id}
                    onClick={() => setSelected({ type: "field", id: field.id })}
                  >
                    <div className="simple-question-main">
                      <span className="question-index">{fieldIndex + 1}</span>
                      <input
                        className="question-title-input"
                        dir={formDirection}
                        value={getLocalizedValue(field, "label", primaryLanguage)}
                        placeholder="Question"
                        onChange={(event) =>
                          updateLocalizedFieldValue(field, "label", event.target.value)
                        }
                      />
                      <select
                        value={field.type}
                        onChange={(event) =>
                          updateFormField(field.id, { type: event.target.value })
                        }
                      >
                        {getVisibleFieldTypes(field.type).map((type) => (
                          <option key={type.id} value={type.id}>{type.label}</option>
                        ))}
                      </select>
                    </div>
                    {translationsEnabled && (
                      <label className="translation-entry-field question-translation-title">
                        <span>{translationLanguage === "ar" ? "Arabic" : "English"} question translation</span>
                        <textarea
                          data-field-id={field.id}
                          data-field-key="label"
                          data-field-lang={translationLanguage}
                          rows={2}
                          dir={translationDirection}
                          value={getExplicitLocalizedValue(field, "label", translationLanguage)}
                          placeholder={`Add ${translationLanguage === "ar" ? "Arabic" : "English"} question text`}
                          onFocus={(event) => {
                            activeTextTargetRef.current = event.currentTarget;
                          }}
                          onChange={(event) =>
                            updateLocalizedFieldValue(field, "label", event.target.value, translationLanguage)
                          }
                        />
                      </label>
                    )}

                    <div className="question-advanced">
                      <div className="question-format-toolbar" role="toolbar" aria-label="Description and example formatting">
                        <select
                          aria-label="Text style"
                          defaultValue="text"
                          onChange={(event) => applyTargetTextStyle(getActiveTextTarget(field), event.target.value)}
                        >
                          <option value="text">Text</option>
                          <option value="h1">H1</option>
                          <option value="h2">H2</option>
                          <option value="h3">H3</option>
                        </select>
                        {textToolbarButtons.map(({ action, label, icon: Icon }) => (
                          <button
                            key={action}
                            type="button"
                            title={label}
                            aria-label={label}
                            onMouseDown={(event) => {
                              event.preventDefault();
                              runTextToolbarAction(field, action);
                            }}
                          >
                            <Icon size={15} aria-hidden="true" />
                          </button>
                        ))}
                        <button
                          type="button"
                          title="Left-to-right"
                          onMouseDown={(event) => {
                            event.preventDefault();
                            setTextDirection(field, "ltr");
                          }}
                        >
                          LTR
                        </button>
                        <button
                          type="button"
                          title="Right-to-left"
                          onMouseDown={(event) => {
                            event.preventDefault();
                            setTextDirection(field, "rtl");
                          }}
                        >
                          RTL
                        </button>
                        <label className="question-toolbar-color" title="Text color">
                          <Baseline size={16} aria-hidden="true" />
                          <input
                            type="color"
                            defaultValue="#1a2744"
                            onChange={(event) => applyTargetColor(getActiveTextTarget(field), "color", event.target.value)}
                          />
                        </label>
                        <label className="question-toolbar-color" title="Background color">
                          <Highlighter size={16} aria-hidden="true" />
                          <input
                            type="color"
                            defaultValue="#f4f7fb"
                            onChange={(event) => applyTargetColor(getActiveTextTarget(field), "backgroundColor", event.target.value)}
                          />
                        </label>
                      </div>
                      <div className="question-detail-row">
                        <label className="question-mini-field">
                          <span>Description</span>
                          <textarea
                            data-field-id={field.id}
                            data-field-key="helpText"
                            dir={formDirection}
                            value={getLocalizedValue(field, "helpText", primaryLanguage)}
                            placeholder="Shown under the question"
                            onFocus={(event) => {
                              activeTextTargetRef.current = event.currentTarget;
                            }}
                            onChange={(event) =>
                              updateLocalizedFieldValue(field, "helpText", event.target.value)
                            }
                          />
                          {translationsEnabled && (
                            <div className="translation-entry-field">
                              <span>{translationLanguage === "ar" ? "Arabic" : "English"} description translation</span>
                              <textarea
                                data-field-id={field.id}
                                data-field-key="helpText"
                                data-field-lang={translationLanguage}
                                rows={2}
                                dir={translationDirection}
                                value={getExplicitLocalizedValue(field, "helpText", translationLanguage)}
                                placeholder={`Add ${translationLanguage === "ar" ? "Arabic" : "English"} description`}
                                onFocus={(event) => {
                                  activeTextTargetRef.current = event.currentTarget;
                                }}
                                onChange={(event) =>
                                  updateLocalizedFieldValue(field, "helpText", event.target.value, translationLanguage)
                                }
                              />
                            </div>
                          )}
                        </label>
                        <label className="question-mini-field">
                          <span>Example</span>
                          <input
                            data-field-id={field.id}
                            data-field-key="placeholder"
                            dir={formDirection}
                            value={getLocalizedValue(field, "placeholder", primaryLanguage)}
                            placeholder="Example answer or placeholder"
                            onFocus={(event) => {
                              activeTextTargetRef.current = event.currentTarget;
                            }}
                            onChange={(event) =>
                              updateLocalizedFieldValue(field, "placeholder", event.target.value)
                            }
                          />
                          {translationsEnabled && (
                            <div className="translation-entry-field">
                              <span>{translationLanguage === "ar" ? "Arabic" : "English"} example translation</span>
                              <textarea
                                data-field-id={field.id}
                                data-field-key="placeholder"
                                data-field-lang={translationLanguage}
                                rows={2}
                                dir={translationDirection}
                                value={getExplicitLocalizedValue(field, "placeholder", translationLanguage)}
                                placeholder={`Add ${translationLanguage === "ar" ? "Arabic" : "English"} example`}
                                onFocus={(event) => {
                                  activeTextTargetRef.current = event.currentTarget;
                                }}
                                onChange={(event) =>
                                  updateLocalizedFieldValue(field, "placeholder", event.target.value, translationLanguage)
                                }
                              />
                            </div>
                          )}
                        </label>
                      </div>

                      {choiceFieldTypes.has(field.type) && (
                        <div className="options-editor option-row-editor" dir={formDirection}>
                          <div className="option-row-editor-header">
                            <strong>Answer options</strong>
                            <FormButton icon={Plus} onClick={() => insertFieldOption(field)}>
                              Add option
                            </FormButton>
                          </div>

                          {getEditableOptions(field).map((option, optionIndex) => (
                            <div className="option-editor-stack" key={`${field.id}_${optionIndex}`}>
                              <div className="option-editor-row">
                                <span>{optionIndex + 1}</span>
                                <input
                                  value={option}
                                  dir={formDirection}
                                  placeholder={`Option ${optionIndex + 1}`}
                                  onChange={(event) =>
                                    updateFieldOption(field, optionIndex, event.target.value)
                                  }
                                />
                                <FormButton
                                  icon={Plus}
                                  title="Insert option below"
                                  onClick={() => insertFieldOption(field, optionIndex)}
                                />
                                <FormButton
                                  variant="danger"
                                  icon={Trash2}
                                  title="Delete option"
                                  onClick={() => deleteFieldOption(field, optionIndex)}
                                />
                              </div>
                              {translationsEnabled && (
                                <label className="translation-entry-field option-translation-field">
                                  <span>{translationLanguage === "ar" ? "Arabic" : "English"} option {optionIndex + 1} translation</span>
                                  <textarea
                                    rows={2}
                                    dir={translationDirection}
                                    value={getExplicitTranslationOptions(field)[optionIndex] || ""}
                                    placeholder={`Translate option ${optionIndex + 1}`}
                                    onChange={(event) =>
                                      updateFieldTranslationOption(field, optionIndex, event.target.value)
                                    }
                                  />
                                </label>
                              )}
                            </div>
                          ))}
                        </div>
                      )}

                      {field.type === "linearScale" && (
                        <div className="scale-editor compact-scale-editor">
                          <label>
                            From
                            <input
                              type="number"
                              min="0"
                              max="10"
                              value={field.scaleMin || 1}
                              onChange={(event) =>
                                updateFormField(field.id, { scaleMin: Number(event.target.value) })
                              }
                            />
                          </label>
                          <label>
                            To
                            <input
                              type="number"
                              min="2"
                              max="10"
                              value={field.scaleMax || 5}
                              onChange={(event) =>
                                updateFormField(field.id, { scaleMax: Number(event.target.value) })
                              }
                            />
                          </label>
                          <label>
                            Low label
                            <input
                              value={field.scaleMinLabel || ""}
                              onChange={(event) =>
                                updateFormField(field.id, { scaleMinLabel: event.target.value })
                              }
                            />
                          </label>
                          <label>
                            High label
                            <input
                              value={field.scaleMaxLabel || ""}
                              onChange={(event) =>
                                updateFormField(field.id, { scaleMaxLabel: event.target.value })
                              }
                            />
                          </label>
                        </div>
                      )}

                      {field.type === "rating" && (
                        <label className="inline-setting">
                          Max rating
                          <input
                            type="number"
                            min="2"
                            max="10"
                            value={field.maxRating || 5}
                            onChange={(event) =>
                              updateFormField(field.id, { maxRating: Number(event.target.value) })
                            }
                          />
                        </label>
                      )}

                      {activeForm.mode === "quiz" && (
                        <div className="quiz-question-settings">
                          {renderQuizAnswerKeyEditor(field)}
                          <label>
                            Time override
                            <input
                              type="number"
                              min="0"
                              value={Number(field.quizTimeLimitSec || 0)}
                              onChange={(event) =>
                                updateFormField(field.id, {
                                  quizTimeLimitSec: Math.max(0, Number(event.target.value || 0)),
                                })
                              }
                            />
                          </label>
                        </div>
                      )}
                    </div>

                    <footer className="question-actions simple-question-actions">
                      <label className="checkbox-control">
                        <input
                          type="checkbox"
                          checked={field.required}
                          onChange={(event) =>
                            updateFormField(field.id, { required: event.target.checked })
                          }
                        />
                        Required
                      </label>
                      <FormButton icon={ChevronUp} title="Move question up" onClick={() => moveFormField(field.id, "up")} />
                      <FormButton icon={ChevronDown} title="Move question down" onClick={() => moveFormField(field.id, "down")} />
                      <FormButton icon={Copy} onClick={() => duplicateFormField(field.id)}>
                        Duplicate
                      </FormButton>
                      <FormButton
                        variant="danger"
                        icon={Trash2}
                        title="Delete question"
                        onClick={() => {
                          if (window.confirm("Delete this question?")) deleteFormField(field.id);
                        }}
                      />
                    </footer>
                  </article>
                ))}
              </div>

              <FormButton
                className="add-question-wide"
                icon={Plus}
                onClick={() => addQuestion(questionType, section.id)}
              >
                Add question here
              </FormButton>
            </section>
          ))}
        </div>
        </main>
      </div>

      {quizOptionsOpen && (
        <div className="quiz-drawer-backdrop" dir="ltr" onClick={() => setQuizOptionsOpen(false)}>
          <div
            className="quiz-options-drawer"
            role="dialog"
            aria-modal="true"
            aria-label="Quiz options"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="quiz-drawer-header">
              <div>
                <h3>Form settings</h3>
                <p>Control language, success message, quiz mode, focus mode, scoring, and retakes.</p>
              </div>
              <button
                type="button"
                className="quiz-drawer-close"
                aria-label="Close settings"
                onClick={() => setQuizOptionsOpen(false)}
              >
                ×
              </button>
            </div>

            <div className="quiz-settings-grid quiz-drawer-grid">
              <label>
                <span className="quiz-setting-title">Primary language</span>
                <small>Sets the default writing direction. Translations are entered manually.</small>
                <select
                  value={primaryLanguage}
                  onChange={(event) => setPrimaryLanguage(event.target.value)}
                >
                  <option value="en">English</option>
                  <option value="ar">Arabic</option>
                </select>
              </label>

              <section className="translation-settings-card">
                <div>
                  <span className="quiz-setting-title">Translations</span>
                  <small>Show translation fields throughout the form editor. Madar does not auto-translate these fields.</small>
                </div>
                <label className="checkbox-control">
                  <input
                    type="checkbox"
                    checked={translationsEnabled}
                    onChange={(event) => setTranslationsEnabled(event.target.checked)}
                  />
                  Add {translationLanguage === "ar" ? "Arabic" : "English"} translations
                </label>
              </section>

              <label>
                <span className="quiz-setting-title">Success message</span>
                <small>Shown after submit in the primary language.</small>
                <textarea
                  dir={formDirection}
                  value={getLocalizedValue(activeForm, "successMessage", primaryLanguage)}
                  onChange={(event) => updateLocalizedFormValue("successMessage", event.target.value)}
                />
                {translationsEnabled && (
                  <div className="translation-entry-field">
                    <span>{translationLanguage === "ar" ? "Arabic" : "English"} success message translation</span>
                    <textarea
                      data-form-text="successMessage"
                      data-form-lang={translationLanguage}
                      rows={3}
                      dir={translationDirection}
                      value={getExplicitLocalizedValue(activeForm, "successMessage", translationLanguage)}
                      placeholder={`Add ${translationLanguage === "ar" ? "Arabic" : "English"} success message`}
                      onFocus={(event) => {
                        activeTextTargetRef.current = event.currentTarget;
                      }}
                      onChange={(event) =>
                        updateLocalizedFormValue("successMessage", event.target.value, translationLanguage)
                      }
                    />
                  </div>
                )}
              </label>

              <label className="checkbox-control">
                <span className="quiz-setting-title">
                  <input
                    type="checkbox"
                    checked={activeForm.mode === "quiz"}
                    onChange={(event) =>
                      updateActiveForm((form) => ({
                        ...form,
                        mode: event.target.checked ? "quiz" : "form",
                        quiz: getQuizSettings(form),
                      }))
                    }
                  />
                  Enable quiz mode
                </span>
                <small>Turns this form into a scored assessment with quiz-specific controls.</small>
              </label>

              <label className="checkbox-control">
                <span className="quiz-setting-title">
                  <input
                    type="checkbox"
                    checked={Boolean(getQuizSettings(activeForm).lockScreen)}
                    onChange={(event) => updateActiveFormQuiz({ lockScreen: event.target.checked })}
                  />
                  Focus mode
                </span>
                <small>Requires fullscreen while the quiz is active. Exiting fullscreen locks the attempt and prevents retakes.</small>
              </label>

              <label>
                <span className="quiz-setting-title">Total time limit (minutes)</span>
                <small>Set the maximum time allowed for the full quiz. Use 0 for no limit.</small>
                <input
                  type="number"
                  min="0"
                  value={Math.round(Number(getQuizSettings(activeForm).totalTimeLimitSec || 0) / 60)}
                  onChange={(event) =>
                    updateActiveFormQuiz({
                      totalTimeLimitSec: Math.max(0, Number(event.target.value || 0) * 60),
                    })
                  }
                />
              </label>

              <label>
                <span className="quiz-setting-title">Time per question (seconds)</span>
                <small>Limit each question individually. Use 0 when questions should not be timed.</small>
                <input
                  type="number"
                  min="0"
                  value={Number(getQuizSettings(activeForm).questionTimeLimitSec || 0)}
                  onChange={(event) =>
                    updateActiveFormQuiz({
                      questionTimeLimitSec: Math.max(0, Number(event.target.value || 0)),
                    })
                  }
                />
              </label>

              <label>
                <span className="quiz-setting-title">Scoring</span>
                <small>Choose whether answers are graded automatically, manually, or by completion.</small>
                <select
                  value={getQuizSettings(activeForm).scoring}
                  onChange={(event) => updateActiveFormQuiz({ scoring: event.target.value })}
                >
                  <option value="automatic">Automatic</option>
                  <option value="manual">Manual review</option>
                  <option value="completion">Completion only</option>
                </select>
              </label>

              <label>
                <span className="quiz-setting-title">Passing score (%)</span>
                <small>Minimum score required to pass when scoring is enabled.</small>
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={Number(getQuizSettings(activeForm).passingScore || 0)}
                  onChange={(event) =>
                    updateActiveFormQuiz({
                      passingScore: Math.min(100, Math.max(0, Number(event.target.value || 0))),
                    })
                  }
                />
              </label>

              <label className="checkbox-control">
                <span className="quiz-setting-title">
                  <input
                    type="checkbox"
                    checked={Boolean(getQuizSettings(activeForm).showResults)}
                    onChange={(event) => updateActiveFormQuiz({ showResults: event.target.checked })}
                  />
                  Show results
                </span>
                <small>Displays the respondent's result after submission.</small>
              </label>

              <label className="checkbox-control">
                <span className="quiz-setting-title">
                  <input
                    type="checkbox"
                    checked={Boolean(getQuizSettings(activeForm).allowRetakes)}
                    onChange={(event) => updateActiveFormQuiz({ allowRetakes: event.target.checked })}
                  />
                  Allow retakes
                </span>
                <small>Lets respondents submit the same quiz again when allowed.</small>
              </label>

              <label>
                <span className="quiz-setting-title">Max retakes</span>
                <small>Maximum number of additional attempts. Use 0 for unlimited retakes.</small>
                <input
                  type="number"
                  min="0"
                  value={Number(getQuizSettings(activeForm).maxRetakes || 0)}
                  onChange={(event) =>
                    updateActiveFormQuiz({
                      maxRetakes: Math.max(0, Number(event.target.value || 0)),
                    })
                  }
                />
              </label>

              <section className="logic-settings-card">
                <div className="logic-settings-header">
                  <div>
                    <span className="quiz-setting-title">Conditional logic</span>
                    <small>If a question equals an answer, show or hide another question.</small>
                  </div>
                  <FormButton icon={Plus} disabled={getFormFields(activeForm).length < 2} onClick={addLogicRule}>
                    Add rule
                  </FormButton>
                </div>

                {(activeForm.logicRules || []).length === 0 ? (
                  <p className="logic-empty">No logic rules yet.</p>
                ) : (
                  <div className="logic-rule-list">
                    {(activeForm.logicRules || []).map((rule) => (
                      <div className="logic-rule-row" key={rule.id}>
                        <select
                          value={rule.sourceFieldId}
                          onChange={(event) => updateLogicRule(rule.id, { sourceFieldId: event.target.value })}
                        >
                          {getFormFields(activeForm).map((field) => (
                            <option key={field.id} value={field.id}>
                              {getLocalizedValue(field, "label", primaryLanguage) || "Untitled question"}
                            </option>
                          ))}
                        </select>
                        <span>equals</span>
                        <input
                          value={rule.value || ""}
                          placeholder="Answer"
                          onChange={(event) => updateLogicRule(rule.id, { value: event.target.value })}
                        />
                        <select
                          value={rule.action || "show"}
                          onChange={(event) => updateLogicRule(rule.id, { action: event.target.value })}
                        >
                          <option value="show">show</option>
                          <option value="hide">hide</option>
                        </select>
                        <select
                          value={rule.targetFieldId}
                          onChange={(event) => updateLogicRule(rule.id, { targetFieldId: event.target.value })}
                        >
                          {getFormFields(activeForm).map((field) => (
                            <option key={field.id} value={field.id}>
                              {getLocalizedValue(field, "label", primaryLanguage) || "Untitled question"}
                            </option>
                          ))}
                        </select>
                        <FormButton
                          variant="danger"
                          icon={Trash2}
                          title="Delete rule"
                          onClick={() => deleteLogicRule(rule.id)}
                        />
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </div>

            <footer className="quiz-drawer-footer">
              <button type="button" onClick={() => setQuizOptionsOpen(false)}>Close</button>
              <button type="button" className="quiz-drawer-save" onClick={saveSettings}>
                <Save size={16} aria-hidden="true" />
                Save
              </button>
            </footer>
          </div>
        </div>
      )}

      {deleteFormCandidate && (
        <PageDeleteConfirmModal
          title="Delete this form?"
          message={
            <>
              <strong>"{deleteFormCandidate.title || "Untitled form"}"</strong> and its
              questions, translations, placements, and workflows will be removed. This cannot
              be undone.
            </>
          }
          cancelLabel="Keep form"
          confirmLabel="Delete form"
          onCancel={() => setDeleteFormCandidate(null)}
          onConfirm={confirmDeleteCurrentForm}
        />
      )}

      {deleteFormPageCandidate && (
        <PageDeleteConfirmModal
          title="Delete this form page?"
          message={
            <>
              <strong>"{deleteFormPageCandidate.name}"</strong> and its questions will be
              removed from this form. This cannot be undone.
            </>
          }
          cancelLabel="Keep page"
          confirmLabel="Delete page"
          onCancel={() => setDeleteFormPageCandidate(null)}
          onConfirm={confirmDeleteFormPage}
        />
      )}
    </div>
  );
}
