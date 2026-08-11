const blockedStoredUrlSchemes = new Set(["javascript", "data", "vbscript", "file", "ftp"]);
const urlLikeSiteChromeKeys = new Set(["href", "image", "imageUrl", "logoUrl", "src", "url"]);
const CONTROL_CHARS_PATTERN = new RegExp(
  `[${String.fromCharCode(0)}-${String.fromCharCode(31)}${String.fromCharCode(127)}]`,
  "u"
);
const urlSchemePattern = /^([a-z][a-z0-9+.-]*):/i;
const managedUploadAssetPattern =
  /^\/uploads\/tenant_[1-9][0-9]*\/builder_assets\/[a-f0-9]{32}\.(?:png|jpg|jpeg|webp|mp4|webm|pdf|doc|docx)$/;

export const isSvgUrlPath = (value) => {
  const path = String(value || "").split(/[?#]/, 1)[0].toLowerCase();
  return path.endsWith(".svg") || path.endsWith(".svgz");
};

export const getStoredUrlError = (
  value,
  { fieldName = "URL", allowRelative = false, allowEmpty = true } = {}
) => {
  const cleanValue = String(value ?? "").trim();

  if (!cleanValue) return allowEmpty ? "" : `${fieldName} is required.`;
  if (CONTROL_CHARS_PATTERN.test(cleanValue)) return `${fieldName} contains invalid characters.`;
  if (cleanValue.startsWith("//")) return `${fieldName} cannot be protocol-relative.`;

  if (cleanValue.startsWith("/")) {
    if (!allowRelative) return `${fieldName} must use an HTTPS URL.`;
    if (cleanValue.includes("\\")) return `${fieldName} contains invalid characters.`;
    if (isSvgUrlPath(cleanValue)) return `${fieldName} cannot be an SVG URL.`;
    if (cleanValue.startsWith("/uploads/") && !managedUploadAssetPattern.test(cleanValue)) {
      return `${fieldName} must use a managed upload asset path.`;
    }
    return "";
  }

  const schemeMatch = cleanValue.match(urlSchemePattern);
  if (!schemeMatch) {
    return allowRelative
      ? `${fieldName} must be an HTTPS URL or managed internal path.`
      : `${fieldName} must be an HTTPS URL.`;
  }

  const scheme = schemeMatch[1].toLowerCase();

  if (blockedStoredUrlSchemes.has(scheme)) return `${fieldName} cannot use ${scheme}: URLs.`;
  if (scheme === "http") return `${fieldName} must use HTTPS instead of HTTP.`;
  if (scheme !== "https") return `${fieldName} cannot use ${scheme}: URLs.`;

  try {
    const parsedUrl = new URL(cleanValue);
    if (!parsedUrl.hostname) return `${fieldName} must include a host.`;
    if (isSvgUrlPath(parsedUrl.pathname)) return `${fieldName} cannot be an SVG URL.`;
  } catch {
    return `${fieldName} must be a valid HTTPS URL.`;
  }

  return "";
};

export const collectSiteChromeUrlErrors = (siteChrome = {}) => {
  const directErrors = Object.entries(siteChrome).flatMap(([key, value]) => {
    if (!urlLikeSiteChromeKeys.has(key) || typeof value !== "string") return [];

    const error = getStoredUrlError(value, {
      fieldName: `Site ${key}`,
      allowRelative: true,
    });

    return error ? [error] : [];
  });

  const footerErrors = [
    ["footerSocialItems", "Social link"],
    ["footerPaymentItems", "Payment link"],
  ].flatMap(([key, label]) => {
    if (!Array.isArray(siteChrome[key])) return [];
    return siteChrome[key].flatMap((item, index) => {
      const error = getStoredUrlError(item?.url, {
        fieldName: `${label} ${index + 1} destination`,
        allowRelative: true,
      });
      return error ? [error] : [];
    });
  });

  return [...directErrors, ...footerErrors];
};

export const collectCarouselImageUrlErrors = (content, fieldName) =>
  String(content || "")
    .split("\n\n")
    .map((block) => block.trim())
    .filter(Boolean)
    .flatMap((block, index) => {
      const lines = block.split("\n").map((line) => line.trim());
      const imageUrl = lines[2] || "";
      const error = getStoredUrlError(imageUrl, {
        fieldName: `${fieldName} slide ${index + 1} image URL`,
        allowRelative: true,
      });

      return error ? [error] : [];
    });

export const collectBuilderUrlErrorsFromUtils = ({
  project,
  collectBuilderElements,
  carouselElementTypes,
}) => {
  const errors = collectSiteChromeUrlErrors(project?.siteChrome || {});

  collectBuilderElements(project).forEach((element) => {
    const elementName = element?.name || element?.type || "Element";

    if (["image", "video", "document"].includes(element?.type)) {
      const error = getStoredUrlError(element.content, {
        fieldName: `${elementName} asset URL`,
        allowRelative: true,
      });
      if (error) errors.push(error);
    }

    if (element?.type === "embed") {
      const error = getStoredUrlError(element.content, {
        fieldName: `${elementName} embed URL`,
      });
      if (error) errors.push(error);
    }

    if (carouselElementTypes.has(element?.type)) {
      errors.push(...collectCarouselImageUrlErrors(element.content, elementName));
    }

    if (element?.action?.url) {
      const error = getStoredUrlError(element.action.url, {
        fieldName: `${elementName} action URL`,
        allowRelative: true,
      });
      if (error) errors.push(error);
    }
  });

  return errors;
};
