const API_URL = import.meta.env.VITE_API_URL || "/api";
const API_BASE_URL = API_URL.replace(/\/+$/, "");
const BLOCKED_MEDIA_SCHEMES = new Set(["javascript", "data", "vbscript", "file", "ftp"]);
const URL_SCHEME_PATTERN = /^([a-z][a-z0-9+.-]*):/i;
const MANAGED_UPLOAD_ASSET_PATTERN =
  /^\/uploads\/tenant_[1-9][0-9]*\/builder_assets\/[a-f0-9]{32}\.(?:png|jpg|jpeg|webp|mp4|webm)$/;
const MANAGED_IMAGE_ASSET_PATTERN =
  /^\/uploads\/tenant_[1-9][0-9]*\/builder_assets\/[a-f0-9]{32}\.(?:png|jpg|jpeg|webp)$/;
const RELATIVE_MEDIA_FILE_PATTERN = /\.(?:avif|gif|jpe?g|png|webp|mp4|webm)(?:[?#].*)?$/i;
const MANAGED_DOCUMENT_ASSET_PATTERN =
  /^\/uploads\/tenant_[1-9][0-9]*\/builder_assets\/[a-f0-9]{32}\.(?:pdf|doc|docx)$/;
const RELATIVE_DOCUMENT_FILE_PATTERN = /\.(?:pdf|doc|docx)(?:[?#].*)?$/i;
const MANAGED_ASSET_CACHE_VERSION = "3";

const isSvgPath = (value) => {
  const path = String(value || "").split(/[?#]/, 1)[0].toLowerCase();
  return path.endsWith(".svg") || path.endsWith(".svgz");
};

const resolveSupportedAssetUrl = (
  value,
  { relativePattern, managedPattern, requireExternalExtension = false }
) => {
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

    let parsed;
    try {
      parsed = new URL(source);
    } catch {
      return "";
    }
    if (parsed.username || parsed.password) return "";
    if (requireExternalExtension && !relativePattern.test(`${parsed.pathname}${parsed.search}${parsed.hash}`)) {
      return "";
    }

    return source;
  }

  const relativeSource = source.startsWith("/") ? source : `/${source}`;

  if (!relativePattern.test(relativeSource)) {
    return "";
  }

  if (relativeSource.startsWith("/uploads/") && !managedPattern.test(relativeSource)) {
    return "";
  }

  const resolvedUrl = `${API_BASE_URL}${relativeSource}`;

  if (managedPattern.test(relativeSource)) {
    return `${resolvedUrl}?v=${MANAGED_ASSET_CACHE_VERSION}`;
  }

  return resolvedUrl;
};

export const resolveMediaUrl = (value) => resolveSupportedAssetUrl(value, {
  relativePattern: RELATIVE_MEDIA_FILE_PATTERN,
  managedPattern: MANAGED_UPLOAD_ASSET_PATTERN,
});

export const RESPONSIVE_MEDIA_WIDTHS = [320, 480, 768, 1024, 1440, 1920, 2560];

export const getResponsiveMediaProps = (
  value,
  { widths = RESPONSIVE_MEDIA_WIDTHS, fallbackWidth = 1440, sizes = "100vw" } = {}
) => {
  const src = resolveMediaUrl(value);
  const source = String(value || "").trim();
  if (!src || !MANAGED_IMAGE_ASSET_PATTERN.test(source)) return { src };

  const candidates = [...new Set(widths)]
    .map(Number)
    .filter((width) => RESPONSIVE_MEDIA_WIDTHS.includes(width))
    .sort((left, right) => left - right);
  const appendWidth = (width) => `${src}${src.includes("?") ? "&" : "?"}w=${width}`;
  const safeFallback = RESPONSIVE_MEDIA_WIDTHS.includes(Number(fallbackWidth))
    ? Number(fallbackWidth)
    : 1440;

  return {
    src: appendWidth(safeFallback),
    srcSet: candidates.map((width) => `${appendWidth(width)} ${width}w`).join(", "),
    sizes,
  };
};

export const resolveDocumentUrl = (value) => resolveSupportedAssetUrl(value, {
  relativePattern: RELATIVE_DOCUMENT_FILE_PATTERN,
  managedPattern: MANAGED_DOCUMENT_ASSET_PATTERN,
  requireExternalExtension: true,
});
