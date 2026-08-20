export const BUTTON_COLOR_FIELDS = Object.freeze([
  "backgroundColor",
  "textColor",
  "hoverBackgroundColor",
  "hoverTextColor",
  "borderColor",
]);

const SIX_DIGIT_HEX = /^#[0-9a-f]{6}$/i;

export const normalizeButtonColor = (value) => {
  const candidate = String(value ?? "").trim();
  if (!candidate) return "";
  return SIX_DIGIT_HEX.test(candidate) ? candidate.toUpperCase() : null;
};

export const normalizeButtonColorFields = (element = {}) => {
  if (element?.type !== "button") return element;
  const normalized = { ...element };
  BUTTON_COLOR_FIELDS.forEach((field) => {
    const value = normalizeButtonColor(element[field]);
    if (value) normalized[field] = value;
    else delete normalized[field];
  });
  return normalized;
};

export const getButtonColorPresentation = (element = {}) => {
  const values = Object.fromEntries(
    BUTTON_COLOR_FIELDS.map((field) => [field, normalizeButtonColor(element[field])])
  );
  const classes = [];
  const style = {};
  const bind = (field, className, property) => {
    if (!values[field]) return;
    classes.push(className);
    style[property] = values[field];
  };
  bind("backgroundColor", "has-button-background-color", "--button-background-color");
  bind("textColor", "has-button-text-color", "--button-text-color");
  bind("hoverBackgroundColor", "has-button-hover-background-color", "--button-hover-background-color");
  bind("hoverTextColor", "has-button-hover-text-color", "--button-hover-text-color");
  bind("borderColor", "has-button-border-color", "--button-border-color");
  return { className: classes.join(" "), style };
};

const relativeLuminance = (hex) => {
  const color = normalizeButtonColor(hex);
  if (!color) return null;
  const channels = [1, 3, 5].map((index) => parseInt(color.slice(index, index + 2), 16) / 255);
  const linear = channels.map((channel) => (
    channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
  ));
  return (0.2126 * linear[0]) + (0.7152 * linear[1]) + (0.0722 * linear[2]);
};

export const getButtonContrastRatio = (foreground, background) => {
  const foregroundLuminance = relativeLuminance(foreground);
  const backgroundLuminance = relativeLuminance(background);
  if (foregroundLuminance === null || backgroundLuminance === null) return null;
  const lighter = Math.max(foregroundLuminance, backgroundLuminance);
  const darker = Math.min(foregroundLuminance, backgroundLuminance);
  return (lighter + 0.05) / (darker + 0.05);
};

export const getButtonContrastWarnings = (element = {}) => {
  const warnings = [];
  const normal = getButtonContrastRatio(element.textColor, element.backgroundColor);
  if (normal !== null && normal < 4.5) warnings.push("Button text contrast may be too low.");
  const hover = getButtonContrastRatio(
    element.hoverTextColor || element.textColor,
    element.hoverBackgroundColor || element.backgroundColor
  );
  if (hover !== null && hover < 4.5) warnings.push("Button hover contrast may be too low.");
  return warnings;
};
