import { getStoredUrlError } from "./PageBuilder.url";

const legacyItems = (value) => String(value || "")
  .split("\n")
  .map((label) => ({ label: label.trim(), url: "" }));

export const getFooterLinkItems = (items, legacyValue = "", { preserveEmpty = false } = {}) => {
  const source = Array.isArray(items) && items.length ? items : legacyItems(legacyValue);
  const normalized = source.map((item) => (
    typeof item === "string"
      ? { label: item.trim(), url: "" }
      : {
          label: String(item?.label || "").trim(),
          url: String(item?.url || "").trim(),
        }
  ));

  return preserveEmpty
    ? (normalized.length ? normalized : [{ label: "", url: "" }])
    : normalized.filter((item) => item.label);
};

export const getFooterLinkUrlError = (url, label = "Footer link") =>
  getStoredUrlError(url, {
    fieldName: `${label} destination`,
    allowRelative: true,
  });

export const getSafeFooterLinkUrl = (url, label) =>
  getFooterLinkUrlError(url, label) ? "" : String(url || "").trim();

export const isExternalFooterLink = (url) => /^https:\/\//i.test(String(url || "").trim());
