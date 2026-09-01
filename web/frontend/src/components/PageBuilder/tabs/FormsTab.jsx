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
  Italic,
  List,
  ListOrdered,
  ListPlus,
  Plus,
  Redo2,
  RotateCcw,
  Send,
  Settings,
  Save,
  Highlighter,
  Trash2,
  Underline,
  Undo2,
  Upload,
  X,
} from "lucide-react";
import { createId } from "../core/PageBuilder.constants";
import { applyFormTemplate, FORM_TEMPLATES } from "../core/PageBuilder.formTemplates";
import {
  getDirectionForLanguage,
  getLocalizedOptions,
  getLocalizedValue,
  normalizeLanguageMode,
  setLocalizedOptions,
  setLocalizedValue,
} from "../core/PageBuilder.localization";
import { defaultFormTheme, getFormThemeVars } from "../core/PageBuilder.theme";
import PageDeleteConfirmModal from "../modals/PageDeleteConfirmModal";
import { getFormsTabContent } from "../../../content/pageBuilder";
import FormButton from "./FormsTab/FormButton";
import FormsEmptyState from "./FormsTab/FormsEmptyState";

const defaultFormsCopy = getFormsTabContent("en");

const choiceFieldTypes = new Set(["dropdown", "radio", "checkboxes", "status"]);

const commonFieldTypes = [
  "shortText",
  "paragraph",
  "email",
  "phone",
  "number",
  "date",
  "radio",
  "checkboxes",
  "file",
];

const legacyFieldTypes = {
  money: { id: "money", label: defaultFormsCopy.legacyFieldTypes.money.label, group: defaultFormsCopy.legacyFieldTypes.money.group, input: "number" },
  phone: { id: "phone", label: defaultFormsCopy.legacyFieldTypes.phone.label, group: defaultFormsCopy.legacyFieldTypes.phone.group, input: "tel" },
  radio: { id: "radio", label: defaultFormsCopy.legacyFieldTypes.radio.label, group: defaultFormsCopy.legacyFieldTypes.radio.group, input: "radio" },
  yesNo: { id: "yesNo", label: defaultFormsCopy.legacyFieldTypes.yesNo.label, group: defaultFormsCopy.legacyFieldTypes.yesNo.group, input: "yesNo" },
  status: { id: "status", label: defaultFormsCopy.legacyFieldTypes.status.label, group: defaultFormsCopy.legacyFieldTypes.status.group, input: "select" },
};

const textToolbarButtons = [
  { action: "undo", label: defaultFormsCopy.toolbar.undo, icon: Undo2 },
  { action: "redo", label: defaultFormsCopy.toolbar.redo, icon: Redo2 },
  { action: "bold", label: defaultFormsCopy.toolbar.bold, icon: Bold },
  { action: "italic", label: defaultFormsCopy.toolbar.italic, icon: Italic },
  { action: "underline", label: defaultFormsCopy.toolbar.underline, icon: Underline },
  { action: "bullets", label: defaultFormsCopy.toolbar.bullets, icon: List },
  { action: "numbers", label: defaultFormsCopy.toolbar.numbers, icon: ListOrdered },
  { action: "align-left", label: defaultFormsCopy.toolbar.alignLeft, icon: AlignLeft },
  { action: "align-center", label: defaultFormsCopy.toolbar.alignCenter, icon: AlignCenter },
  { action: "align-right", label: defaultFormsCopy.toolbar.alignRight, icon: AlignRight },
  { action: "align-justify", label: defaultFormsCopy.toolbar.justify, icon: AlignJustify },
];

const formThemeColorControls = [
  ["surface", "Card"],
  ["inputBackground", "Field"],
  ["text", "Text"],
  ["muted", "Helper"],
  ["border", "Border"],
  ["accent", "Action"],
  ["buttonText", "Button text"],
];

const isHexColor = (value) => /^#[0-9a-f]{6}$/i.test(String(value || ""));
const getColorValue = (value, fallback = "#000000") =>
  isHexColor(value) ? value : fallback;
const formatColorValue = (value) => String(value || "").toUpperCase();

const FORM_IMPORT_GUIDE = `Create a Madar form as a data-only JavaScript module. Return only this code shape (no functions, imports, comments, or markdown fences):

export default {
  "type": "madar-form",
  "version": 1,
  "form": {
    "name": "Contact form",
    "title": "Contact us",
    "description": "Send us a message.",
    "languageMode": "en",
    "defaultLanguage": "en",
    "pageMode": "paged",
    "sections": [
      {
        "id": "contact-page",
        "title": "Contact details",
        "description": "",
        "fields": [
          {
            "id": "email-field",
            "label": "Email address",
            "type": "email",
            "required": true,
            "helpText": "",
            "placeholder": "name@example.com",
            "options": []
          }
        ]
      }
    ]
  }
};

Allowed field types: shortText, paragraph, email, number, date, dropdown, radio, checkboxes, file, money, phone, yesNo, status.
Allowed languageMode values: en, ar, bilingual. Use unique string IDs. JSON with the same object shape is also accepted.`;

const parseFormImportText = (contents) => {
  let source = String(contents || "").replace(/^\uFEFF/, "").trim();
  source = source.replace(/^```(?:javascript|js|json)?\s*/i, "").replace(/\s*```$/, "").trim();
  source = source.replace(/^export\s+default\s+/i, "");
  source = source.replace(/^module\.exports\s*=\s*/i, "");
  source = source.replace(/;\s*$/, "").trim();
  return JSON.parse(source);
};

const cloneFormWithNewIds = (sourceForm) => {
  const idMap = new Map();
  const collectIds = (value) => {
    if (Array.isArray(value)) {
      value.forEach(collectIds);
      return;
    }
    if (!value || typeof value !== "object") return;
    if (typeof value.id === "string" && value.id) {
      idMap.set(value.id, createId("import"));
    }
    Object.values(value).forEach(collectIds);
  };
  const cloneValue = (value) => {
    if (typeof value === "string") return idMap.get(value) || value;
    if (Array.isArray(value)) return value.map(cloneValue);
    if (!value || typeof value !== "object") return value;
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, cloneValue(item)]));
  };

  collectIds(sourceForm);
  return cloneValue(sourceForm);
};

export default function FormsTab({
  project,
  updateProject,
  activeForm,
  fieldTypes,
  selected,
  lang = "en",

  selectForm,
  selectPage,
  setActiveTab,
  setDesignPanel,
  setSelected,

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
  const copy = getFormsTabContent(lang);
  const [questionType, setQuestionType] = useState("shortText");
  const [showPublishPanel, setShowPublishPanel] = useState(false);
  const [templateId, setTemplateId] = useState("");
  const [deleteFormCandidate, setDeleteFormCandidate] = useState(null);
  const [deleteFormPageCandidate, setDeleteFormPageCandidate] = useState(null);
  const [importGuideCopied, setImportGuideCopied] = useState(false);
  const [isSavingForm, setIsSavingForm] = useState(false);
  const activeTextTargetRef = useRef(null);
  const activePageTextTargetRef = useRef("description");
  const formImportInputRef = useRef(null);
  const formTheme = project.theme?.form || {};
  const formLanguageMode = normalizeLanguageMode(activeForm?.languageMode || lang);
  const primaryLanguage =
    formLanguageMode === "bilingual"
      ? normalizeLanguageMode(activeForm?.defaultLanguage || "en")
      : formLanguageMode;
  const translationLanguage = primaryLanguage === "ar" ? "en" : "ar";
  const translationsEnabled = formLanguageMode === "bilingual";
  const formDirection = getDirectionForLanguage(primaryLanguage);
  const translationDirection = getDirectionForLanguage(translationLanguage);
  const getLanguageName = (language) =>
    language === "ar" ? copy.labels.arabic : copy.labels.english;
  const formatCopy = (value, replacements = {}) =>
    Object.entries(replacements).reduce(
      (text, [key, replacement]) => text.replaceAll(`{${key}}`, replacement),
      value
    );

  const getFormLibraryName = (form) =>
    String(form?.name || form?.title || copy.labels.untitledForm).trim();

  const importForm = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    try {
      const parsed = parseFormImportText(await file.text());
      const sourceForm = parsed?.type === "madar-form" ? parsed.form : parsed;
      if (!sourceForm || typeof sourceForm !== "object" || !Array.isArray(sourceForm.sections)) {
        throw new Error("Invalid form file");
      }

      const importedForm = cloneFormWithNewIds({
        ...sourceForm,
        name: String(sourceForm.name || sourceForm.title || "Imported form").trim(),
        title: String(sourceForm.title || sourceForm.name || "Imported form").trim(),
        responses: [],
        connectedCollectionId: "",
      });
      importedForm.id ||= createId("form");
      importedForm.sections = importedForm.sections.map((section) => ({
        ...section,
        id: section.id || createId("formSection"),
        fields: (section.fields || []).map((field) => ({
          ...field,
          id: field.id || createId("field"),
        })),
      }));

      updateProject((currentProject) => ({
        ...currentProject,
        forms: [...(currentProject.forms || []), importedForm],
        activeFormId: importedForm.id,
      }));
      setSelected({ type: "form", id: importedForm.id });
    } catch {
      window.alert("This file is not valid Madar form JSON or JavaScript data.");
    }
  };

  const copyImportGuide = async () => {
    try {
      await navigator.clipboard.writeText(FORM_IMPORT_GUIDE);
      setImportGuideCopied(true);
      window.setTimeout(() => setImportGuideCopied(false), 1800);
    } catch {
      window.alert("Could not copy the guide. Select the documentation text and copy it manually.");
    }
  };

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
    const title = section.title || "";
    const legacyMatch = title.match(/^Section\s+(\d+)$/i);
    return legacyMatch
      ? `${copy.labels.page} ${legacyMatch[1]}`
      : title || (sectionIndex === 0 ? copy.labels.titlePage : `${copy.labels.page} ${sectionIndex + 1}`);
  };

  const addQuestion = (typeId = questionType, sectionId = activeSectionId) => {
    addFieldToForm(sectionId, typeId);
  };

  const applyTemplate = (nextTemplateId) => {
    setTemplateId(nextTemplateId);
    if (!nextTemplateId) return;
    if (!window.confirm(copy.messages.replaceTemplateConfirm)) {
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

  const getFieldDisplayName = (fieldId) => {
    const field = getFormFields(activeForm).find((item) => item.id === fieldId);
    return getLocalizedValue(field, "label", primaryLanguage) || copy.labels.untitledQuestion;
  };

  const getVisibilityRulesForField = (fieldId) =>
    (activeForm.logicRules || []).filter((rule) => rule.targetFieldId === fieldId);

  const getVisibilityRuleText = (rule) => {
    const action = rule.action === "hide" ? "Hidden" : "Shown";
    const sourceName = getFieldDisplayName(rule.sourceFieldId);
    const answer = String(rule.value || "").trim() || copy.labels.answer;
    return `${action} when "${sourceName}" is "${answer}"`;
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

  const updatePageTextStyle = (section, updates) => {
    const target = activePageTextTargetRef.current === "title" ? "title" : "description";
    const styleKey = `${target}Style`;
    updateFormSection(section.id, {
      [styleKey]: { ...(section[styleKey] || {}), ...updates },
    });
  };

  const runPageTextAction = (section, action) => {
    const target = activePageTextTargetRef.current === "title" ? "title" : "description";
    const current = section[`${target}Style`] || {};
    const toggle = (property, value) =>
      updatePageTextStyle(section, { [property]: current[property] === value ? "" : value });
    if (action === "bold") toggle("fontWeight", "700");
    if (action === "italic") toggle("fontStyle", "italic");
    if (action === "underline") toggle("textDecoration", "underline");
    if (action.startsWith("align-")) {
      updatePageTextStyle(section, { textAlign: action.replace("align-", "") });
    }
  };

  const applyPageTextStyle = (section, textStyle) => {
    const styles = {
      h1: { fontSize: "24px", fontWeight: "950" },
      h2: { fontSize: "20px", fontWeight: "900" },
      h3: { fontSize: "17px", fontWeight: "850" },
      text: { fontSize: "", fontWeight: "" },
    };
    updatePageTextStyle(section, { textStyle, ...(styles[textStyle] || styles.text) });
  };

  const openPlacement = (placement) => {
    selectPage(placement.pageId);
    setActiveTab("design");
    setDesignPanel("Sections");
  };

  const saveSettings = () => {
    setQuizOptionsOpen(false);
  };

  const saveForm = async () => {
    if ((!publishProject && !saveProject) || isSavingForm) return;
    setIsSavingForm(true);
    try {
      if (publishProject) {
        await publishProject();
      } else {
        await saveProject({ successMessage: "Form saved." });
      }
    } finally {
      setIsSavingForm(false);
    }
  };

  const previewForm = async () => {
    if (!openFormPreviewPage || isSavingForm) return;
    setIsSavingForm(true);
    try {
      const saved = saveProject ? await saveProject({ silent: true }) : true;
      if (saved) openFormPreviewPage(activeForm.id);
    } finally {
      setIsSavingForm(false);
    }
  };
  const updateFormThemeValue = (key, value) => {
    updateProject?.((prev) => ({
      ...prev,
      theme: {
        ...prev.theme,
        form: {
          ...(prev.theme?.form || {}),
          [key]: value,
        },
      },
    }));
  };

  const resetFormTheme = () => {
    updateProject?.((prev) => ({
      ...prev,
      theme: {
        ...prev.theme,
        form: { ...defaultFormTheme },
      },
    }));
  };

  const renderFormThemeColorControl = ([key, label]) => {
    const currentValue = getColorValue(formTheme[key], defaultFormTheme[key]);

    return (
      <label className="forms-theme-token" key={key}>
        <span>{label}</span>
        <span className="forms-theme-color-input">
          <span
            className="forms-theme-swatch"
            style={{ "--forms-theme-token": currentValue }}
            aria-hidden="true"
          />
          <strong>{formatColorValue(currentValue)}</strong>
          <input
            aria-label={label}
            type="color"
            value={currentValue}
            onChange={(event) => updateFormThemeValue(key, event.target.value)}
          />
        </span>
      </label>
    );
  };

  if (!activeForm) {
    return (
      <FormsEmptyState
        addForm={addForm}
        copy={copy}
        project={project}
      />
    );
  }

  return (
    <div
      className="workspace-page forms-workbench forms-simple-workbench"
      dir={formDirection}
      style={getFormThemeVars(project.theme)}
    >
      <div className="forms-simple-shell">
        <aside className="simple-add-question" aria-label={copy.labels.formControls}>
          <div className="forms-panel-heading">
            <div>
              <h2>Form library</h2>
            </div>
            <span className="forms-count" aria-label={`${project.forms.length} forms`}>
              {project.forms.length}
            </span>
          </div>
          <p className="panel-help">Create forms, edit questions, and place them on your pages.</p>
          <div className="forms-sidebar-stats" aria-label="Current form summary">
            <div>
              <span>{copy.counts.questions}</span>
              <strong>{getFormFields(activeForm).length}</strong>
            </div>
            <div>
              <span>{copy.counts.pages}</span>
              <strong>{sections.length}</strong>
            </div>
            <div>
              <span>{copy.counts.responses}</span>
              <strong>{activeForm.responses.length}</strong>
            </div>
            <div>
              <span>Type</span>
              <strong>{activeForm.mode === "quiz" ? copy.counts.quiz : copy.counts.form}</strong>
            </div>
          </div>

          <label>
            {copy.labels.currentForm}
            <select value={activeForm.id} onChange={(event) => selectForm(event.target.value)}>
              {project.forms.map((form) => (
                <option key={form.id} value={form.id}>
                  {getFormLibraryName(form)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Form name
            <input
              value={activeForm.name || activeForm.title || ""}
              placeholder="Name this form"
              onChange={(event) =>
                updateActiveForm((form) => ({ ...form, name: event.target.value }))
              }
            />
          </label>
          <div className="form-library-file-actions">
            <FormButton icon={Upload} onClick={() => formImportInputRef.current?.click()}>Import form</FormButton>
            <input
              ref={formImportInputRef}
              type="file"
              accept="application/json,application/javascript,text/javascript,.json,.js,.mjs"
              hidden
              onChange={importForm}
            />
          </div>
          <details className="form-import-guide">
            <summary>AI form format guide</summary>
            <p>Copy this guide into ChatGPT, describe the form you need, then import the generated JSON or JS file.</p>
            <FormButton icon={Copy} onClick={copyImportGuide}>
              {importGuideCopied ? "Copied" : "Copy ChatGPT guide"}
            </FormButton>
            <pre>{FORM_IMPORT_GUIDE}</pre>
          </details>
          <FormButton className="forms-primary-action" icon={Plus} onClick={addForm}>
            {copy.messages.newForm}
          </FormButton>

          <div className="forms-secondary-actions">
            <label>
              {copy.labels.templates}
              <select value={templateId} onChange={(event) => applyTemplate(event.target.value)}>
                <option value="">{copy.labels.chooseTemplate}</option>
                {FORM_TEMPLATES.map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <label>
            {copy.labels.language}
            <select
              value={primaryLanguage}
              onChange={(event) => setPrimaryLanguage(event.target.value)}
            >
              <option value="en">{copy.labels.english}</option>
              <option value="ar">{copy.labels.arabic}</option>
            </select>
          </label>

          <div className="form-translation-panel">
            <label className="checkbox-control">
              <input
                type="checkbox"
                checked={translationsEnabled}
                onChange={(event) => setTranslationsEnabled(event.target.checked)}
              />
              {formatCopy(copy.messages.addTranslations, { language: getLanguageName(translationLanguage) })}
            </label>
          </div>

          <details className="simple-action-group forms-theme-action-group">
            <summary className="simple-action-group-title">Form colors</summary>
            <div className="forms-theme-action-body">
              <div className="forms-theme-grid">
                {formThemeColorControls.map(renderFormThemeColorControl)}
              </div>
              <div className="forms-theme-shape-grid">
                <label>
                  Form corners
                  <input
                    type="number"
                    min="0"
                    value={formTheme.radius ?? defaultFormTheme.radius}
                    onChange={(event) => updateFormThemeValue("radius", Number(event.target.value))}
                  />
                </label>
                <label>
                  Field corners
                  <input
                    type="number"
                    min="0"
                    value={formTheme.fieldRadius ?? defaultFormTheme.fieldRadius}
                    onChange={(event) => updateFormThemeValue("fieldRadius", Number(event.target.value))}
                  />
                </label>
              </div>
              <FormButton icon={RotateCcw} onClick={resetFormTheme}>
                Reset form colors
              </FormButton>
            </div>
          </details>

          <label>
            {copy.labels.addQuestion}
            <select value={questionType} onChange={(event) => setQuestionType(event.target.value)}>
              {getVisibleFieldTypes().map((type) => (
                <option key={type.id} value={type.id}>
                  {type.label}
                </option>
              ))}
            </select>
          </label>
          <div className="forms-builder-actions">
            <FormButton variant="primary" icon={Plus} onClick={() => addQuestion()}>
              {copy.labels.addQuestion}
            </FormButton>
            <FormButton icon={ListPlus} onClick={addFormSection}>
              {copy.labels.addPage}
            </FormButton>
          </div>
          <div className="simple-action-groups">
            <section className="simple-action-group forms-form-actions-group">
              <span className="simple-action-group-title">{copy.labels.formActions}</span>
              <FormButton variant="primary" icon={Save} disabled={isSavingForm} onClick={saveForm}>
                {isSavingForm ? "Publishing..." : publishProject ? "Save & publish form" : "Save form"}
              </FormButton>
              <FormButton icon={Settings} onClick={() => setQuizOptionsOpen(true)}>
                {copy.labels.formSettings}
              </FormButton>
              <FormButton icon={Eye} disabled={isSavingForm} onClick={previewForm}>
                {copy.labels.previewForm}
              </FormButton>
              <FormButton variant="primary" icon={Send} onClick={() => setShowPublishPanel((value) => !value)}>
                {copy.labels.placeForm}
              </FormButton>
              <FormButton
                variant="danger"
                icon={Trash2}
                onClick={deleteCurrentForm}
              >
                {copy.labels.deleteForm}
              </FormButton>
            </section>

          </div>
        </aside>

        <main className="forms-simple-document">
        {showPublishPanel && (
          <section className="simple-side-panel">
            <div className="simple-panel-grid">
              <label>
                {copy.labels.pageLabel}
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
                {copy.labels.saveSubmissionsTo}
                <select
                  value={activeForm.connectedCollectionId || ""}
                  onChange={(event) =>
                    updateActiveForm((form) => ({
                      ...form,
                      connectedCollectionId: event.target.value,
                    }))
                  }
                >
                  <option value="">{copy.labels.formSubmissionsOnly}</option>
                  {project.collections.map((collection) => (
                    <option key={collection.id} value={collection.id}>{collection.name}</option>
                  ))}
                </select>
              </label>
              <FormButton variant="primary" icon={Send} onClick={() => addConnectedFormSectionToPage(activeForm.id)}>
                {copy.labels.addToPage}
              </FormButton>
            </div>

            {placements.length > 0 && (
              <div className="connected-placement-list">
                <span>{copy.labels.alreadyPlacedOn}</span>
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
              {copy.labels.successMessage}
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
              <div className="question-format-toolbar form-page-description-toolbar" role="toolbar" aria-label={copy.labels.pageDescription}>
                <select aria-label={copy.toolbar.textStyle} defaultValue="text" onChange={(event) => getActiveFormTextTarget() ? applyTargetTextStyle(getActiveFormTextTarget(), event.target.value) : applyPageTextStyle(section, event.target.value)}>
                  <option value="text">{copy.toolbar.text}</option><option value="h1">{copy.toolbar.heading1}</option><option value="h2">{copy.toolbar.heading2}</option><option value="h3">{copy.toolbar.heading3}</option>
                </select>
                {textToolbarButtons.filter(({ action }) => !["undo", "redo", "bullets", "numbers"].includes(action)).map(({ action, label, icon: Icon }) => (
                  <button key={action} type="button" title={label} aria-label={label} onMouseDown={(event) => { event.preventDefault(); getActiveFormTextTarget() ? runFormDescriptionToolbarAction(action) : runPageTextAction(section, action); }}><Icon size={15} aria-hidden="true" /></button>
                ))}
                <button type="button" title={copy.toolbar.leftToRight} onMouseDown={(event) => { event.preventDefault(); getActiveFormTextTarget() ? setActiveFormTextDirection("ltr") : updatePageTextStyle(section, { direction: "ltr", textAlign: "left" }); }}>{copy.toolbar.directionLtrShort}</button>
                <button type="button" title={copy.toolbar.rightToLeft} onMouseDown={(event) => { event.preventDefault(); getActiveFormTextTarget() ? setActiveFormTextDirection("rtl") : updatePageTextStyle(section, { direction: "rtl", textAlign: "right" }); }}>{copy.toolbar.directionRtlShort}</button>
                <label className="question-toolbar-color" title={copy.toolbar.textColor}><Baseline size={16} aria-hidden="true" /><input type="color" defaultValue="#162033" onChange={(event) => getActiveFormTextTarget() ? applyTargetColor(getActiveFormTextTarget(), "color", event.target.value) : updatePageTextStyle(section, { color: event.target.value })} /></label>
                <label className="question-toolbar-color" title={copy.toolbar.backgroundColor}><Highlighter size={16} aria-hidden="true" /><input type="color" defaultValue="#fffdfa" onChange={(event) => getActiveFormTextTarget() ? applyTargetColor(getActiveFormTextTarget(), "backgroundColor", event.target.value) : updatePageTextStyle(section, { backgroundColor: event.target.value })} /></label>
              </div>
              <div className="forms-section-heading">
                <input
                  value={getFriendlyPageTitle(section, sectionIndex)}
                  placeholder={sectionIndex === 0 ? copy.labels.titlePage : `${copy.labels.page} ${sectionIndex + 1}`}
                  dir={section.titleStyle?.direction || formDirection}
                  style={{ ...(section.titleStyle || {}), textStyle: undefined }}
                  onFocus={() => {
                    activeTextTargetRef.current = null;
                    activePageTextTargetRef.current = "title";
                  }}
                  onChange={(event) =>
                    updateFormSection(section.id, { title: event.target.value })
                  }
                />
                <FormButton
                  variant="danger"
                  icon={Trash2}
                  className="forms-page-delete-button"
                  onClick={() =>
                    setDeleteFormPageCandidate({
                      section,
                      name: getFriendlyPageTitle(section, sectionIndex),
                    })
                  }
                >
                  {copy.messages.deletePage}
                </FormButton>
              </div>

              <textarea
                value={section.description || ""}
                placeholder={copy.placeholders.pageDescription}
                dir={section.descriptionStyle?.direction || formDirection}
                style={{ ...(section.descriptionStyle || {}), textStyle: undefined }}
                onFocus={() => {
                  activeTextTargetRef.current = null;
                  activePageTextTargetRef.current = "description";
                }}
                onChange={(event) =>
                  updateFormSection(section.id, { description: event.target.value })
                }
              />

              {sectionIndex === 0 && (
                <div className="form-page-intro" style={{ display: "none" }} aria-hidden="true">
                  <div hidden style={{ display: "none" }} className="question-format-toolbar form-title-toolbar" role="toolbar" aria-label={copy.labels.formTitleFormatting}>
                    <select
                      aria-label={copy.toolbar.textStyle}
                      defaultValue="h1"
                      onChange={(event) => applyTargetTextStyle(getActiveFormTextTarget(), event.target.value)}
                    >
                      <option value="text">{copy.toolbar.text}</option>
                      <option value="h1">{copy.toolbar.heading1}</option>
                      <option value="h2">{copy.toolbar.heading2}</option>
                      <option value="h3">{copy.toolbar.heading3}</option>
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
                      title={copy.toolbar.leftToRight}
                      onMouseDown={(event) => {
                        event.preventDefault();
                        setActiveFormTextDirection("ltr");
                      }}
                    >
                      {copy.toolbar.directionLtrShort}
                    </button>
                    <button
                      type="button"
                      title={copy.toolbar.rightToLeft}
                      onMouseDown={(event) => {
                        event.preventDefault();
                        setActiveFormTextDirection("rtl");
                      }}
                    >
                      {copy.toolbar.directionRtlShort}
                    </button>
                    <label className="question-toolbar-color" title={copy.toolbar.textColor}>
                      <Baseline size={16} aria-hidden="true" />
                      <input
                        type="color"
                        defaultValue="var(--theme-text)"
                        onChange={(event) => applyTargetColor(getActiveFormTextTarget(), "color", event.target.value)}
                      />
                    </label>
                    <label className="question-toolbar-color" title={copy.toolbar.backgroundColor}>
                      <Highlighter size={16} aria-hidden="true" />
                      <input
                        type="color"
                        defaultValue="#f8f4ed"
                        onChange={(event) => applyTargetColor(getActiveFormTextTarget(), "backgroundColor", event.target.value)}
                      />
                    </label>
                  </div>
                  <input
                    className="form-title-clean-input"
                    data-form-text="title"
                    dir={formDirection}
                    value={getLocalizedValue(activeForm, "title", primaryLanguage)}
                    placeholder={copy.placeholders.untitledForm}
                    onFocus={(event) => {
                      activeTextTargetRef.current = event.currentTarget;
                    }}
                    onChange={(event) =>
                      updateLocalizedFormValue("title", event.target.value)
                    }
                  />
                  {translationsEnabled && (
                    <label className="translation-entry-field">
                      <span>{getLanguageName(translationLanguage)} {copy.suffixes.titleTranslation}</span>
                      <textarea
                        data-form-text="title"
                        data-form-lang={translationLanguage}
                        rows={2}
                        dir={translationDirection}
                        value={getExplicitLocalizedValue(activeForm, "title", translationLanguage)}
                        placeholder={formatCopy(copy.placeholders.addTitle, { language: getLanguageName(translationLanguage) })}
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
                    <span>{copy.messages.formDescriptionHelp}</span>
                    <div hidden style={{ display: "none" }} className="question-format-toolbar form-description-toolbar" role="toolbar" aria-label={copy.labels.formDescriptionFormatting}>
                      <select
                        aria-label={copy.toolbar.textStyle}
                        defaultValue="text"
                        onChange={(event) => applyTargetTextStyle(getActiveFormTextTarget(), event.target.value)}
                      >
                        <option value="text">{copy.toolbar.text}</option>
                        <option value="h1">{copy.toolbar.heading1}</option>
                        <option value="h2">{copy.toolbar.heading2}</option>
                        <option value="h3">{copy.toolbar.heading3}</option>
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
                        title={copy.toolbar.leftToRight}
                        onMouseDown={(event) => {
                          event.preventDefault();
                          setActiveFormTextDirection("ltr");
                        }}
                      >
                      {copy.toolbar.directionLtrShort}
                      </button>
                      <button
                        type="button"
                        title={copy.toolbar.rightToLeft}
                        onMouseDown={(event) => {
                          event.preventDefault();
                          setActiveFormTextDirection("rtl");
                        }}
                      >
                      {copy.toolbar.directionRtlShort}
                      </button>
                      <label className="question-toolbar-color" title={copy.toolbar.textColor}>
                        <Baseline size={16} aria-hidden="true" />
                        <input
                          type="color"
                          defaultValue="var(--theme-text)"
                          onChange={(event) => applyTargetColor(getActiveFormTextTarget(), "color", event.target.value)}
                        />
                      </label>
                      <label className="question-toolbar-color" title={copy.toolbar.backgroundColor}>
                        <Highlighter size={16} aria-hidden="true" />
                        <input
                          type="color"
                          defaultValue="var(--theme-surface)"
                          onChange={(event) => applyTargetColor(getActiveFormTextTarget(), "backgroundColor", event.target.value)}
                        />
                      </label>
                    </div>
                    <textarea
                      className="form-description-clean-input"
                      data-form-text="description"
                      dir={formDirection}
                      value={getLocalizedValue(activeForm, "description", primaryLanguage)}
                      placeholder={copy.placeholders.formDescription}
                      onFocus={(event) => {
                        activeTextTargetRef.current = event.currentTarget;
                      }}
                      onChange={(event) =>
                        updateLocalizedFormValue("description", event.target.value)
                      }
                    />
                    {translationsEnabled && (
                      <div className="translation-entry-field">
                        <span>{getLanguageName(translationLanguage)} {copy.suffixes.descriptionTranslation}</span>
                        <textarea
                          data-form-text="description"
                          data-form-lang={translationLanguage}
                          rows={3}
                          dir={translationDirection}
                          value={getExplicitLocalizedValue(activeForm, "description", translationLanguage)}
                          placeholder={formatCopy(copy.placeholders.addDescription, { language: getLanguageName(translationLanguage) })}
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
                </div>
              )}

              <div className="questions-stack">
                {(section.fields || []).length === 0 && (
                  <div className="forms-empty-inline">
                    <strong>{copy.messages.emptyPageTitle}</strong>
                    <span>{copy.messages.emptyPageBody}</span>
                  </div>
                )}
                {(section.fields || []).map((field, fieldIndex) => {
                  const visibilityRules = getVisibilityRulesForField(field.id);
                  return (
                    <article
                      className={`question-sheet simple-question-card ${selected.id === field.id ? "active" : ""}`}
                      key={field.id}
                      onClick={() => setSelected({ type: "field", id: field.id })}
                    >
                    <div className="question-format-toolbar question-card-toolbar" role="toolbar" aria-label={copy.toolbar.descriptionExampleFormatting}>
                      <select aria-label={copy.toolbar.textStyle} defaultValue="text" onChange={(event) => applyTargetTextStyle(getActiveTextTarget(field), event.target.value)}>
                        <option value="text">{copy.toolbar.text}</option><option value="h1">{copy.toolbar.heading1}</option><option value="h2">{copy.toolbar.heading2}</option><option value="h3">{copy.toolbar.heading3}</option>
                      </select>
                      {textToolbarButtons.filter(({ action }) => !["undo", "redo", "bullets", "numbers"].includes(action)).map(({ action, label, icon: Icon }) => (
                        <button key={action} type="button" title={label} aria-label={label} onMouseDown={(event) => { event.preventDefault(); runTextToolbarAction(field, action); }}><Icon size={15} aria-hidden="true" /></button>
                      ))}
                      <button type="button" title={copy.toolbar.leftToRight} onMouseDown={(event) => { event.preventDefault(); setTextDirection(field, "ltr"); }}>{copy.toolbar.directionLtrShort}</button>
                      <button type="button" title={copy.toolbar.rightToLeft} onMouseDown={(event) => { event.preventDefault(); setTextDirection(field, "rtl"); }}>{copy.toolbar.directionRtlShort}</button>
                      <label className="question-toolbar-color" title={copy.toolbar.textColor}><Baseline size={16} aria-hidden="true" /><input type="color" defaultValue="#162033" onChange={(event) => applyTargetColor(getActiveTextTarget(field), "color", event.target.value)} /></label>
                      <label className="question-toolbar-color" title={copy.toolbar.backgroundColor}><Highlighter size={16} aria-hidden="true" /><input type="color" defaultValue="#fffdfa" onChange={(event) => applyTargetColor(getActiveTextTarget(field), "backgroundColor", event.target.value)} /></label>
                    </div>
                    <div className="simple-question-main">
                      <span className="question-index">{fieldIndex + 1}</span>
                      <input
                        className="question-title-input"
                        data-field-id={field.id}
                        data-field-key="label"
                        dir={formDirection}
                        value={getLocalizedValue(field, "label", primaryLanguage)}
                        placeholder={copy.placeholders.question}
                        onFocus={(event) => { activeTextTargetRef.current = event.currentTarget; }}
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
                    {visibilityRules.length > 0 && (
                      <div className="question-visibility-note" aria-label="Question visibility">
                        {visibilityRules.map((rule) => (
                          <span key={rule.id}>{getVisibilityRuleText(rule)}</span>
                        ))}
                      </div>
                    )}
                    {translationsEnabled && (
                      <label className="translation-entry-field question-translation-title">
                        <span>{getLanguageName(translationLanguage)} {copy.suffixes.questionTranslation}</span>
                        <textarea
                          data-field-id={field.id}
                          data-field-key="label"
                          data-field-lang={translationLanguage}
                          rows={2}
                          dir={translationDirection}
                          value={getExplicitLocalizedValue(field, "label", translationLanguage)}
                          placeholder={formatCopy(copy.placeholders.addQuestionText, { language: getLanguageName(translationLanguage) })}
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
                      {field.showDetailsEditor === true && (
                      <div hidden style={{ display: "none" }} className="question-format-toolbar" role="toolbar" aria-label={copy.toolbar.descriptionExampleFormatting}>
                        <select
                          aria-label={copy.toolbar.textStyle}
                          defaultValue="text"
                          onChange={(event) => applyTargetTextStyle(getActiveTextTarget(field), event.target.value)}
                        >
                          <option value="text">{copy.toolbar.text}</option>
                          <option value="h1">{copy.toolbar.heading1}</option>
                          <option value="h2">{copy.toolbar.heading2}</option>
                          <option value="h3">{copy.toolbar.heading3}</option>
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
                          title={copy.toolbar.leftToRight}
                          onMouseDown={(event) => {
                            event.preventDefault();
                            setTextDirection(field, "ltr");
                          }}
                        >
                          {copy.toolbar.directionLtrShort}
                        </button>
                        <button
                          type="button"
                          title={copy.toolbar.rightToLeft}
                          onMouseDown={(event) => {
                            event.preventDefault();
                            setTextDirection(field, "rtl");
                          }}
                        >
                          {copy.toolbar.directionRtlShort}
                        </button>
                        <label className="question-toolbar-color" title={copy.toolbar.textColor}>
                          <Baseline size={16} aria-hidden="true" />
                          <input
                            type="color"
                            defaultValue="var(--theme-text)"
                            onChange={(event) => applyTargetColor(getActiveTextTarget(field), "color", event.target.value)}
                          />
                        </label>
                        <label className="question-toolbar-color" title={copy.toolbar.backgroundColor}>
                          <Highlighter size={16} aria-hidden="true" />
                          <input
                            type="color"
                            defaultValue="#f8f4ed"
                            onChange={(event) => applyTargetColor(getActiveTextTarget(field), "backgroundColor", event.target.value)}
                          />
                        </label>
                      </div>
                      )}
                      {field.showDetailsEditor === true && (
                      <div className="question-detail-row">
                        {field.showDetailsEditor === true && (
                        <label className="question-mini-field">
                          <span>{copy.labels.description}</span>
                          <textarea
                            data-field-id={field.id}
                            data-field-key="helpText"
                            dir={formDirection}
                            value={getLocalizedValue(field, "helpText", primaryLanguage)}
                            placeholder={copy.placeholders.shownUnderQuestion}
                            onFocus={(event) => {
                              activeTextTargetRef.current = event.currentTarget;
                            }}
                            onChange={(event) =>
                              updateLocalizedFieldValue(field, "helpText", event.target.value)
                            }
                          />
                          {translationsEnabled && (
                            <div className="translation-entry-field">
                              <span>{getLanguageName(translationLanguage)} {copy.suffixes.descriptionTranslation}</span>
                              <textarea
                                data-field-id={field.id}
                                data-field-key="helpText"
                                data-field-lang={translationLanguage}
                                rows={2}
                                dir={translationDirection}
                                value={getExplicitLocalizedValue(field, "helpText", translationLanguage)}
                                placeholder={formatCopy(copy.placeholders.addDescription, { language: getLanguageName(translationLanguage) })}
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
                        )}
                        {field.showDetailsEditor === true && (
                        <label className="question-mini-field">
                          <span>{copy.labels.example}</span>
                          <input
                            data-field-id={field.id}
                            data-field-key="placeholder"
                            dir={formDirection}
                            value={getLocalizedValue(field, "placeholder", primaryLanguage)}
                            placeholder={copy.placeholders.example}
                            onFocus={(event) => {
                              activeTextTargetRef.current = event.currentTarget;
                            }}
                            onChange={(event) =>
                              updateLocalizedFieldValue(field, "placeholder", event.target.value)
                            }
                          />
                          {translationsEnabled && (
                            <div className="translation-entry-field">
                              <span>{getLanguageName(translationLanguage)} {copy.suffixes.exampleTranslation}</span>
                              <textarea
                                data-field-id={field.id}
                                data-field-key="placeholder"
                                data-field-lang={translationLanguage}
                                rows={2}
                                dir={translationDirection}
                                value={getExplicitLocalizedValue(field, "placeholder", translationLanguage)}
                                placeholder={formatCopy(copy.placeholders.addExample, { language: getLanguageName(translationLanguage) })}
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
                        )}
                      </div>
                      )}

                      {choiceFieldTypes.has(field.type) && (
                        <div className="options-editor option-row-editor" dir={formDirection}>
                          <div className="option-row-editor-header">
                            <strong>{copy.labels.answerOptions}</strong>
                            <FormButton icon={Plus} onClick={() => insertFieldOption(field)}>
                              {copy.labels.addOption}
                            </FormButton>
                          </div>

                          {getEditableOptions(field).map((option, optionIndex) => (
                            <div className="option-editor-stack" key={`${field.id}_${optionIndex}`}>
                              <div className="option-editor-row">
                                <span>{optionIndex + 1}</span>
                                <input
                                  data-field-id={field.id}
                                  data-field-key="option"
                                  data-option-index={optionIndex}
                                  value={option}
                                  dir={formDirection}
                                  placeholder={formatCopy(copy.placeholders.option, { number: optionIndex + 1 })}
                                  onFocus={(event) => {
                                    activeTextTargetRef.current = event.currentTarget;
                                  }}
                                  onChange={(event) =>
                                    updateFieldOption(field, optionIndex, event.target.value)
                                  }
                                />
                                <FormButton
                                  icon={Plus}
                                  title={copy.labels.insertOptionBelow}
                                  onClick={() => insertFieldOption(field, optionIndex)}
                                />
                                <FormButton
                                  variant="danger"
                                  icon={Trash2}
                                  title={copy.labels.deleteOption}
                                  onClick={() => deleteFieldOption(field, optionIndex)}
                                />
                              </div>
                              {translationsEnabled && (
                                <label className="translation-entry-field option-translation-field">
                                  <span>{getLanguageName(translationLanguage)} {formatCopy(copy.suffixes.optionTranslation, { number: optionIndex + 1 })}</span>
                                  <textarea
                                    data-field-id={field.id}
                                    data-field-key="option"
                                    data-field-lang={translationLanguage}
                                    data-option-index={optionIndex}
                                    rows={2}
                                    dir={translationDirection}
                                    value={getExplicitTranslationOptions(field)[optionIndex] || ""}
                                    placeholder={formatCopy(copy.placeholders.translateOption, { number: optionIndex + 1 })}
                                    onFocus={(event) => {
                                      activeTextTargetRef.current = event.currentTarget;
                                    }}
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
                            {copy.labels.from}
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
                            {copy.labels.to}
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
                            {copy.labels.lowLabel}
                            <input
                              value={field.scaleMinLabel || ""}
                              onChange={(event) =>
                                updateFormField(field.id, { scaleMinLabel: event.target.value })
                              }
                            />
                          </label>
                          <label>
                            {copy.labels.highLabel}
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
                          {copy.labels.maxRating}
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
                            {copy.labels.timeOverride}
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
                      <div className="question-toggle-controls">
                        <label className="checkbox-control">
                          <input
                            type="checkbox"
                            checked={field.required}
                            onChange={(event) =>
                              updateFormField(field.id, { required: event.target.checked })
                            }
                          />
                          {copy.labels.required}
                        </label>
                        <label className="checkbox-control">
                          <input
                            type="checkbox"
                            checked={field.showDetailsEditor === true}
                            onChange={(event) => updateFormField(field.id, { showDetailsEditor: event.target.checked })}
                          />
                          {copy.labels.description}
                        </label>
                      </div>
                      <FormButton icon={ChevronUp} title={copy.labels.moveQuestionUp} onClick={() => moveFormField(field.id, "up")} />
                      <FormButton icon={ChevronDown} title={copy.labels.moveQuestionDown} onClick={() => moveFormField(field.id, "down")} />
                      <FormButton icon={Copy} onClick={() => duplicateFormField(field.id)}>
                        {copy.labels.duplicate}
                      </FormButton>
                      <FormButton
                        variant="danger"
                        icon={Trash2}
                        title={copy.labels.deleteQuestion}
                        onClick={() => {
                          if (window.confirm(copy.messages.deleteQuestionConfirm)) deleteFormField(field.id);
                        }}
                      />
                    </footer>
                    </article>
                  );
                })}
              </div>

              <FormButton
                className="add-question-wide"
                icon={Plus}
                onClick={() => addQuestion(questionType, section.id)}
              >
                {copy.labels.addQuestionHere}
              </FormButton>
              <FormButton
                className="forms-insert-page-button"
                icon={ListPlus}
                onClick={() => addFormSection(section.id)}
              >
                Add page after this page
              </FormButton>
            </section>
          ))}
          <FormButton
            className="forms-add-page-button"
            icon={ListPlus}
            onClick={addFormSection}
          >
            {copy.labels.addPage}
          </FormButton>
        </div>
        </main>

      </div>

      {quizOptionsOpen && (
        <div className="quiz-drawer-backdrop" dir="ltr" onClick={() => setQuizOptionsOpen(false)}>
          <div
            className="quiz-options-drawer"
            role="dialog"
            aria-modal="true"
            aria-label={copy.labels.quizOptions}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="quiz-drawer-header">
              <div>
                <h3>{copy.labels.formSettings}</h3>
                <p>Language, confirmation, quiz, and logic.</p>
              </div>
              <button
                type="button"
                className="quiz-drawer-close"
                aria-label={copy.labels.closeSettings}
                onClick={() => setQuizOptionsOpen(false)}
              >
                <X size={16} aria-hidden="true" />
              </button>
            </div>

            <div className="quiz-settings-grid quiz-drawer-grid">
              <section className="quiz-settings-section">
                <h4>General</h4>
              <label>
                <span className="quiz-setting-title">{copy.labels.primaryLanguage}</span>
                <select
                  value={primaryLanguage}
                  onChange={(event) => setPrimaryLanguage(event.target.value)}
                >
                  <option value="en">{copy.labels.english}</option>
                  <option value="ar">{copy.labels.arabic}</option>
                </select>
              </label>

              <section className="translation-settings-card">
                <div>
                  <span className="quiz-setting-title">{copy.labels.translations}</span>
                </div>
                <label className="checkbox-control">
                  <input
                    type="checkbox"
                    checked={translationsEnabled}
                    onChange={(event) => setTranslationsEnabled(event.target.checked)}
                  />
                  {formatCopy(copy.messages.addTranslations, { language: getLanguageName(translationLanguage) })}
                </label>
              </section>

              <label>
                <span className="quiz-setting-title">{copy.labels.successMessage}</span>
                <textarea
                  dir={formDirection}
                  value={getLocalizedValue(activeForm, "successMessage", primaryLanguage)}
                  onChange={(event) => updateLocalizedFormValue("successMessage", event.target.value)}
                />
                {translationsEnabled && (
                  <div className="translation-entry-field">
                    <span>{getLanguageName(translationLanguage)} {copy.suffixes.successMessageTranslation}</span>
                    <textarea
                      data-form-text="successMessage"
                      data-form-lang={translationLanguage}
                      rows={3}
                      dir={translationDirection}
                      value={getExplicitLocalizedValue(activeForm, "successMessage", translationLanguage)}
                      placeholder={formatCopy(copy.placeholders.addSuccessMessage, { language: getLanguageName(translationLanguage) })}
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
              </section>

              <section className="quiz-settings-section">
                <h4>Quiz</h4>
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
                  {copy.labels.enableQuizMode}
                </span>
              </label>

              <label className="checkbox-control">
                <span className="quiz-setting-title">
                  <input
                    type="checkbox"
                    checked={Boolean(getQuizSettings(activeForm).lockScreen)}
                    onChange={(event) => updateActiveFormQuiz({ lockScreen: event.target.checked })}
                  />
                  {copy.labels.focusMode}
                </span>
              </label>

              <label>
                <span className="quiz-setting-title">{copy.labels.totalTimeLimit}</span>
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
                <span className="quiz-setting-title">{copy.labels.timePerQuestion}</span>
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
                <span className="quiz-setting-title">{copy.labels.scoring}</span>
                <select
                  value={getQuizSettings(activeForm).scoring}
                  onChange={(event) => updateActiveFormQuiz({ scoring: event.target.value })}
                >
                  <option value="automatic">{copy.scoringOptions.automatic}</option>
                  <option value="manual">{copy.scoringOptions.manual}</option>
                  <option value="completion">{copy.scoringOptions.completion}</option>
                </select>
              </label>

              <label>
                <span className="quiz-setting-title">{copy.labels.passingScore}</span>
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
                  {copy.labels.showResults}
                </span>
              </label>

              <label className="checkbox-control">
                <span className="quiz-setting-title">
                  <input
                    type="checkbox"
                    checked={Boolean(getQuizSettings(activeForm).allowRetakes)}
                    onChange={(event) => updateActiveFormQuiz({ allowRetakes: event.target.checked })}
                  />
                  {copy.labels.allowRetakes}
                </span>
              </label>

              <label>
                <span className="quiz-setting-title">{copy.labels.maxRetakes}</span>
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
              </section>

              <section className="logic-settings-card quiz-settings-section">
                <h4>Logic</h4>
                <div className="logic-settings-header">
                  <div>
                    <span className="quiz-setting-title">{copy.labels.conditionalLogic}</span>
                  </div>
                  <FormButton icon={Plus} disabled={getFormFields(activeForm).length < 2} onClick={addLogicRule}>
                    {copy.labels.addRule}
                  </FormButton>
                </div>

                {(activeForm.logicRules || []).length === 0 ? (
                  <p className="logic-empty">{copy.messages.noLogicRules}</p>
                ) : (
                  <div className="logic-rule-list">
                    {(activeForm.logicRules || []).map((rule) => (
                      <div className="logic-rule-row" key={rule.id}>
                        <label className="logic-rule-field logic-rule-source">
                          <span>When question</span>
                          <select
                            value={rule.sourceFieldId}
                            onChange={(event) => updateLogicRule(rule.id, { sourceFieldId: event.target.value })}
                          >
                            {getFormFields(activeForm).map((field) => (
                              <option key={field.id} value={field.id}>
                                {getLocalizedValue(field, "label", primaryLanguage) || copy.labels.untitledQuestion}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="logic-rule-field logic-rule-answer">
                          <span>Has answer</span>
                          <input
                            value={rule.value || ""}
                            placeholder={copy.labels.answer}
                            onChange={(event) => updateLogicRule(rule.id, { value: event.target.value })}
                          />
                        </label>
                        <label className="logic-rule-field logic-rule-action">
                          <span>Then</span>
                          <select
                            value={rule.action || "show"}
                            onChange={(event) => updateLogicRule(rule.id, { action: event.target.value })}
                          >
                            <option value="show">Show</option>
                            <option value="hide">Hide</option>
                          </select>
                        </label>
                        <label className="logic-rule-field logic-rule-target">
                          <span>This question</span>
                          <select
                            value={rule.targetFieldId}
                            onChange={(event) => updateLogicRule(rule.id, { targetFieldId: event.target.value })}
                          >
                            {getFormFields(activeForm).map((field) => (
                              <option key={field.id} value={field.id}>
                                {getLocalizedValue(field, "label", primaryLanguage) || copy.labels.untitledQuestion}
                              </option>
                            ))}
                          </select>
                        </label>
                        <FormButton
                          variant="danger"
                          icon={Trash2}
                          title={copy.labels.deleteRule}
                          onClick={() => deleteLogicRule(rule.id)}
                        />
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </div>

            <footer className="quiz-drawer-footer">
              <button type="button" onClick={() => setQuizOptionsOpen(false)}>{copy.labels.close}</button>
              <button type="button" className="quiz-drawer-save" onClick={saveSettings}>
                <Save size={16} aria-hidden="true" />
                {copy.labels.save}
              </button>
            </footer>
          </div>
        </div>
      )}

      {deleteFormCandidate && (
        <PageDeleteConfirmModal
          title={copy.messages.deleteFormTitle}
          message={
            <>
              <strong>"{deleteFormCandidate.title || copy.labels.untitledForm}"</strong> {copy.messages.deleteFormMessage}
            </>
          }
          cancelLabel={copy.messages.keepForm}
          confirmLabel={copy.labels.deleteForm}
          onCancel={() => setDeleteFormCandidate(null)}
          onConfirm={confirmDeleteCurrentForm}
        />
      )}

      {deleteFormPageCandidate && (
        <PageDeleteConfirmModal
          title={copy.messages.deleteFormPageTitle}
          message={
            <>
              <strong>"{deleteFormPageCandidate.name}"</strong> {copy.messages.deleteFormPageMessage}
            </>
          }
          cancelLabel={copy.messages.keepPage}
          confirmLabel={copy.messages.deletePage}
          onCancel={() => setDeleteFormPageCandidate(null)}
          onConfirm={confirmDeleteFormPage}
        />
      )}
    </div>
  );
}
