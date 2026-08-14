const FORM_ITEM_TYPES = new Set([
  "heading",
  "paragraph",
  "availability",
  "text",
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
    availability: { label: "Choose an available slot" },
    text: { label: "Your question", placeholder: "Type your answer", required: false },
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

    if (item.type === "heading" || item.type === "paragraph") {
      normalized.text = cleanText(item.text, item.type === "heading" ? "Section heading" : "Instructions");
      normalized.textStyle = normalizeReservationTextStyle({
        ...(item.type === "heading" ? { format: "h3", fontSize: 22, fontWeight: "700" } : {}),
        ...(item.textStyle || {}),
      });
    } else {
      normalized.label = cleanText(item.label, item.type === "button" ? "Request reservation" : item.type === "availability" ? "Choose an available slot" : "Question");
    }

    if (item.type === "text") {
      normalized.placeholder = cleanText(item.placeholder);
      normalized.required = Boolean(item.required);
    }

    if (item.type === "checkbox" || item.type === "radio") {
      normalized.options = cleanOptions(item.options);
      if (normalized.options.length === 0) normalized.options = ["Option 1"];
      normalized.required = Boolean(item.required);
    }

    return [normalized];
  });
};

export const reservationFormItemNeedsAnswer = (item, answer) => {
  if (!item?.required) return false;
  if (item.type === "checkbox") return !Array.isArray(answer) || answer.length === 0;
  return !String(answer || "").trim();
};

export const reservationFormItemLabels = {
  heading: "Heading",
  paragraph: "Text",
  availability: "Available slots",
  text: "Text field",
  checkbox: "Checkboxes",
  radio: "Radio choices",
  button: "Submit button",
};
