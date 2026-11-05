import { normalizeReservationLayout } from "./reservationLayout";
import { getReservationContent } from "../../../content/pageBuilder/reservationContent";

const FORM_ITEM_TYPES = new Set([
  "heading",
  "paragraph",
  "divider",
  "availability",
  "text",
  "email",
  "phone",
  "checkbox",
  "radio",
  "button",
]);

const TEXT_FORMATS = new Set(["text", "h1", "h2", "h3", "bullets", "numbers"]);
const TEXT_ALIGNMENTS = new Set(["left", "center", "right", "justify"]);
const TEXT_DIRECTIONS = new Set(["ltr", "rtl"]);
const FONT_FAMILIES = new Set([
  "Inter",
  "Arial",
  "Verdana",
  "Tahoma",
  "Trebuchet MS",
  "Georgia",
  "Times New Roman",
  "Courier New",
  "Poppins",
  "Montserrat",
  "Raleway",
  "Lora",
  "Oswald",
  "Playfair Display",
  "Cormorant Garamond",
  "EB Garamond",
  "Bebas Neue",
  "Lobster Two",
  "IBM Plex Sans Arabic",
]);

const cleanText = (value, fallback = "") => String(value ?? fallback).trim().slice(0, 500);
const cleanOptions = (options) => (Array.isArray(options) ? options : [])
  .map((option) => cleanText(option))
  .filter(Boolean)
  .slice(0, 20);
const cleanColor = (value) => /^#[0-9a-f]{6}$/i.test(String(value || "")) ? String(value) : undefined;
const cleanNumber = (value, min, max, fallback) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.max(min, Math.min(max, parsed)) : fallback;
};

export const normalizeReservationTextStyle = (style) => {
  const source = style && typeof style === "object" && !Array.isArray(style) ? style : {};
  const color = cleanColor(source.color);
  const backgroundColor = cleanColor(source.backgroundColor);
  return {
    format: TEXT_FORMATS.has(source.format) ? source.format : "text",
    fontFamily: FONT_FAMILIES.has(source.fontFamily) ? source.fontFamily : "Inter",
    fontSize: cleanNumber(source.fontSize, 8, 256, 16),
    opacity: cleanNumber(source.opacity, 0, 1, 1),
    fontWeight: source.fontWeight === "700" ? "700" : "400",
    fontStyle: source.fontStyle === "italic" ? "italic" : "normal",
    textDecoration: source.textDecoration === "underline" ? "underline" : "none",
    textAlign: TEXT_ALIGNMENTS.has(source.textAlign) ? source.textAlign : "left",
    ...(color ? { color } : {}),
    ...(backgroundColor ? { backgroundColor } : {}),
  };
};

export const getReservationTextStyle = (item) => {
  const style = normalizeReservationTextStyle(item?.textStyle);
  return {
    fontFamily: style.fontFamily,
    fontSize: `${style.fontSize}px`,
    opacity: style.opacity,
    fontWeight: style.fontWeight,
    fontStyle: style.fontStyle,
    textDecoration: style.textDecoration,
    textAlign: style.textAlign,
    ...(style.color ? { color: style.color } : {}),
    ...(style.backgroundColor ? { backgroundColor: style.backgroundColor } : {}),
  };
};

export const createReservationFormItemId = () =>
  globalThis.crypto?.randomUUID?.() || `reservation_item_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

export const createReservationFormItem = (type, overrides = {}) => {
  const id = overrides.id || createReservationFormItemId();
  const presets = {
    heading: { text: "New section heading", textStyle: { format: "h3", fontSize: 22, fontWeight: "700" } },
    paragraph: { text: "Add helpful instructions for your visitors.", textStyle: { format: "text", fontSize: 16 } },
    divider: {},
    availability: { label: "Choose an available slot" },
    text: { label: "Your question", placeholder: "Type your answer", required: false },
    email: { label: "Email address", placeholder: "you@example.com", required: true },
    phone: { label: "Phone number", placeholder: "+970 59 000 0000", required: true },
    checkbox: { label: "Choose all that apply", options: ["Option 1", "Option 2"], required: false },
    radio: { label: "Choose one option", options: ["Option 1", "Option 2"], required: false },
    button: { label: "Request reservation" },
  };

  return {
    id,
    type: FORM_ITEM_TYPES.has(type) ? type : "text",
    direction: "ltr",
    ...(presets[type] || presets.text),
    ...overrides,
  };
};

export const moveBookingComponent = (items, sourceId, targetIndex) => {
  const current = Array.isArray(items) ? [...items] : [];
  const sourceIndex = current.findIndex((item) => item.id === sourceId);
  if (sourceIndex < 0) return current;
  const [moved] = current.splice(sourceIndex, 1);
  const adjustedIndex = sourceIndex < targetIndex ? targetIndex - 1 : targetIndex;
  current.splice(Math.max(0, Math.min(adjustedIndex, current.length)), 0, moved);
  return current;
};

export const normalizeReservationFormItems = (items) => {
  if (!Array.isArray(items)) return [];

  let hasButton = false;
  let hasAvailability = false;
  return items.slice(0, 40).flatMap((item) => {
    if (!item || !FORM_ITEM_TYPES.has(item.type)) return [];
    if (item.type === "button") {
      if (hasButton) return [];
      hasButton = true;
    }
    if (item.type === "availability") {
      if (hasAvailability) return [];
      hasAvailability = true;
    }

    const normalized = {
      id: cleanText(item.id) || createReservationFormItemId(),
      type: item.type,
      direction: TEXT_DIRECTIONS.has(item.direction) ? item.direction : "ltr",
    };
    if (item.layout) normalized.layout = normalizeReservationLayout(item.layout);

    if (item.type === "heading" || item.type === "paragraph") {
      normalized.text = cleanText(item.text, item.type === "heading" ? "Section heading" : "Instructions");
      normalized.textStyle = normalizeReservationTextStyle({
        ...(item.type === "heading" ? { format: "h3", fontSize: 22, fontWeight: "700" } : {}),
        ...(item.textStyle || {}),
      });
    } else if (item.type !== "divider") {
      normalized.label = cleanText(item.label, item.type === "button" ? "Request reservation" : item.type === "availability" ? "Choose an available slot" : "Question");
    }

    if (["text", "email", "phone"].includes(item.type)) {
      normalized.placeholder = cleanText(item.placeholder);
      normalized.required = Boolean(item.required);
    }

    if (item.type === "checkbox" || item.type === "radio") {
      normalized.options = cleanOptions(item.options);
      if (normalized.options.length === 0) normalized.options = ["Option 1"];
      normalized.required = Boolean(item.required);
    }

    if (item.translations && typeof item.translations === "object") {
      const translations = {};
      for (const language of ["en", "ar"]) {
        const source = item.translations[language];
        if (!source || typeof source !== "object" || Array.isArray(source)) continue;
        const translated = {};
        if (TEXT_DIRECTIONS.has(source.direction)) translated.direction = source.direction;
        for (const key of ["text", "label", "placeholder"]) {
          if (typeof source[key] === "string") translated[key] = cleanText(source[key]);
        }
        if (normalized.options && source.options && typeof source.options === "object" && !Array.isArray(source.options)) {
          translated.options = Object.fromEntries(normalized.options.filter(option => typeof source.options[option] === "string")
            .map(option => [option, cleanText(source.options[option])]));
        }
        translations[language] = translated;
      }
      normalized.translations = translations;
    }
    if (normalized.type === "heading") normalized.translations = { ...normalized.translations,
      en: { ...normalized.translations?.en, text: normalized.text } };
    return [normalized];
  });
};

const EMAIL_PATTERN = /^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$/i;
const ISRAEL_PHONE_PATTERN = /^(?:\+972(?:5\d{8}|7\d{8}|[23489]\d{7})|0(?:5\d{8}|7\d{8}|[23489]\d{7}))$/;
const PALESTINE_PHONE_PATTERN = /^(?:\+970(?:5[69]\d{7}|[28]\d{7})|0(?:5[69]\d{7}|[28]\d{7}))$/;

export const normalizeReservationPhone = (value) => {
  const compact = String(value || "").trim().replace(/[\s().-]/g, "");
  return compact.startsWith("00") ? `+${compact.slice(2)}` : compact;
};

export const isValidReservationEmail = (value) => {
  const email = String(value || "").trim();
  const [local = ""] = email.split("@");
  return email.length <= 254
    && local.length > 0
    && local.length <= 64
    && !local.startsWith(".")
    && !local.endsWith(".")
    && !local.includes("..")
    && EMAIL_PATTERN.test(email);
};

export const isValidRegionalPhone = (value) => {
  const phone = normalizeReservationPhone(value);
  return ISRAEL_PHONE_PATTERN.test(phone) || PALESTINE_PHONE_PATTERN.test(phone);
};

export const getReservationAnswerError = (item, answer, lang = "en") => {
  const content = getReservationContent(lang).validation;
  const value = String(answer || "").trim();
  if (!value) return item?.required ? content.required : "";
  if (item?.type === "email" && !isValidReservationEmail(value)) {
    return content.email;
  }
  if (item?.type === "phone" && !isValidRegionalPhone(value)) {
    return content.phone;
  }
  return "";
};
export const reservationFormItemNeedsAnswer = (item, answer) => {
  if (!item?.required) return false;
  if (item.type === "checkbox") return !Array.isArray(answer) || answer.length === 0;
  return !String(answer || "").trim();
};

export const reservationFormItemLabels = {
  heading: "Heading",
  paragraph: "Text",
  divider: "Divider",
  availability: "Available slots",
  text: "Text field",
  email: "Email",
  phone: "Phone number",
  checkbox: "Checkboxes",
  radio: "Radio choices",
  button: "Submit button",
};


const starterFields = {
  heading: { text: ["heading", "emptyHeading", "requestTitle", "fixedTitle", "reservationTitle"] },
  paragraph: { text: ["paragraph", "emptyParagraph", "requestHelp", "fixedHelp", "reservationHelp"] },
  availability: { label: ["availability"] },
  text: { label: ["question", "emptyQuestion"], placeholder: ["placeholder"] },
  email: { label: ["email"] }, phone: { label: ["phone"] },
  checkbox: { label: ["checkbox"] }, radio: { label: ["radio"] },
  button: { label: ["submit", "sendRequest", "bookSlot"] },
};

export const getReservationStarterTranslation = (item, field, language, value = item?.[field]) => {
  if (!String(language).startsWith("ar")) return undefined;
  const source = String(value || "").trim();
  const target = getReservationContent("ar").starter;
  if (field === "option" && ["checkbox", "radio"].includes(item?.type)) {
    const match = /^Option ([1-9]|1\d|20)$/.exec(source);
    return match ? target.option.replace("{number}", match[1]) : undefined;
  }
  const english = getReservationContent("en").starter;
  const key = starterFields[item?.type]?.[field]?.find(key => english[key] === source);
  return key ? target[key] : undefined;
};

// Only known starter copy is automatic; authored overrides win and choice values stay canonical.
export const localizeReservationFormItem = (item, language = "en") => {
  const locale = String(language).startsWith("ar") ? "ar" : "en";
  if (locale === "en" && item.type === "heading") return item;
  const translated = item.translations?.[locale] || {};
  const overrides = Object.fromEntries(["text", "label", "placeholder"].flatMap(key => {
    const value = typeof translated[key] === "string" && translated[key].trim()
      ? translated[key] : getReservationStarterTranslation(item, key, locale);
    return value ? [[key, value]] : [];
  }));
  const optionLabels = Object.fromEntries((item.options || []).flatMap(option => {
    const value = typeof translated.options?.[option] === "string" && translated.options[option].trim()
      ? translated.options[option] : getReservationStarterTranslation(item, "option", locale, option);
    return value ? [[option, value]] : [];
  }));
  if (locale !== "ar" && !Object.keys(overrides).length && !Object.keys(optionLabels).length && !translated.direction) return item;
  const direction = translated.direction || (locale === "ar" ? "rtl" : item.direction || "ltr");
  const style = item.textStyle || (["heading", "paragraph"].includes(item.type) ? normalizeReservationTextStyle() : null);
  return { ...item, ...overrides, optionLabels, direction,
    ...(style ? { textStyle: { ...style,
      ...(!style.textAlign || ["left", "right"].includes(style.textAlign) ? { textAlign: direction === "rtl" ? "right" : "left" } : {}),
      ...(locale === "ar" && (!style.fontFamily || style.fontFamily === "Inter") ? { fontFamily: "IBM Plex Sans Arabic" } : {}),
    } } : {}),
  };
};
