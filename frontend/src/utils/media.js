const API_URL = import.meta.env.VITE_API_URL || "/api";
const API_BASE_URL = API_URL.replace(/\/+$/, "");
const BLOCKED_MEDIA_SCHEMES = new Set(["javascript", "data", "vbscript", "file", "ftp"]);
const URL_SCHEME_PATTERN = /^([a-z][a-z0-9+.-]*):/i;
const MANAGED_UPLOAD_ASSET_PATTERN =
  /^\/uploads\/tenant_[1-9][0-9]*\/builder_assets\/[a-f0-9]{32}\.(?:png|jpg|jpeg|webp)$/;

const isSvgPath = (value) => {
  const path = String(value || "").split(/[?#]/, 1)[0].toLowerCase();
  return path.endsWith(".svg") || path.endsWith(".svgz");
};

export const resolveMediaUrl = (value) => {
  const source = String(value || "").trim();

  if (!source) return "";

  if (source.startsWith("//") || source.includes("\\") || isSvgPath(source)) {
    return "";
  }

  const schemeMatch = source.match(URL_SCHEME_PATTERN);

  if (schemeMatch) {
    const scheme = schemeMatch[1].toLowerCase();

    if (BLOCKED_MEDIA_SCHEMES.has(scheme) || scheme === "http") {
      return "";
    }

    if (scheme !== "https") {
      return "";
    }

    return source;
  }

  const relativeSource = source.startsWith("/") ? source : `/${source}`;

  if (relativeSource.startsWith("/uploads/") && !MANAGED_UPLOAD_ASSET_PATTERN.test(relativeSource)) {
    return "";
  }

  return `${API_BASE_URL}${relativeSource}`;
};
