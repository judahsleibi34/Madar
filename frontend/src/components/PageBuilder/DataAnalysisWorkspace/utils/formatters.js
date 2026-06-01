import { columnLabelsAr, fieldLabelsAr, methodLabelsAr } from '../constants/analysisConfig';

export const cleanObject = (params) =>
  Object.fromEntries(
    Object.entries(params).filter(([, value]) => {
      if (value === "" || value === null || value === undefined) return false;
      if (Array.isArray(value) && value.length === 0) return false;
      return true;
    })
  );

export const hasArabic = (value) => /[\u0600-\u06FF]/.test(String(value ?? ""));
export const valueDir = (value) => (hasArabic(value) ? "rtl" : "ltr");

export const toLabel = (key, lang = "en") => {
  if (lang === "ar" && fieldLabelsAr[key]) return fieldLabelsAr[key];

  return String(key)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
    .replace(/\bNgo\b/g, "NGO");
};

export const methodLabel = (method, lang = "en") =>
  lang === "ar" ? methodLabelsAr[method.id] || method.label : method.label;

export const columnLabel = (column, lang = "en") => {
  if (lang === "ar" && columnLabelsAr[column]) return columnLabelsAr[column];
  return String(column ?? "");
};

export const displayValue = (value, t) => {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "boolean") return value ? t.yes : t.no;

  if (typeof value === "number") {
    return Number.isInteger(value) ? value : Number(value.toFixed(3));
  }

  if (Array.isArray(value)) {
    return value.map((item) => displayValue(item, t)).join(", ");
  }

  if (typeof value === "object") {
    return JSON.stringify(value, null, 2);
  }

  return String(value);
};

export const escapeCsvValue = (value) => {
  if (value === null || value === undefined) return '""';

  let text;

  if (Array.isArray(value)) {
    text = value.map((item) => String(item ?? "")).join("; ");
  } else if (typeof value === "object") {
    text = JSON.stringify(value);
  } else {
    text = String(value);
  }

  return `"${text.replace(/"/g, '""')}"`;
};

export const getDatasetTitle = (dataset, t) => {
  const name = dataset?.original_filename || dataset?.file_path;
  if (!name) return t.noDataset;
  if (String(name).startsWith("http")) return "External dataset";
  return name;
};
