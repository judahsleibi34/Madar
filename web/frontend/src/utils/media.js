const CANONICAL_API_ORIGIN = "https://api.madarportal.com";
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
// Version stable managed-asset URLs to bypass stale edge 404 responses.
const MANAGED_ASSET_CACHE_VERSION = "4";

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
    if (parsed.origin === CANONICAL_API_ORIGIN && managedPattern.test(parsed.pathname)) {
      return `${parsed.pathname}?v=${MANAGED_ASSET_CACHE_VERSION}`;
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

  if (managedPattern.test(relativeSource)) {
    return `${relativeSource}?v=${MANAGED_ASSET_CACHE_VERSION}`;
  }

  // The frontend edge forwards managed uploads to the controlled backend route.
  return relativeSource;
};

export const resolveMediaUrl = (value) => resolveSupportedAssetUrl(value, {
  relativePattern: RELATIVE_MEDIA_FILE_PATTERN,
  managedPattern: MANAGED_UPLOAD_ASSET_PATTERN,
});

export const isVideoMediaUrl = (value) => /\.(?:mp4|webm)(?:[?#].*)?$/i.test(String(value || "").trim());

export const RESPONSIVE_MEDIA_WIDTHS = [320, 480, 768, 1024, 1440, 1920, 2560];

export const boundedMediaWidth = (requested) => {
  const width = Number(requested);
  if (!Number.isFinite(width) || width <= 0) return 1440;
  return RESPONSIVE_MEDIA_WIDTHS.find((candidate) => candidate >= width)
    || RESPONSIVE_MEDIA_WIDTHS.at(-1);
};

export const getResponsiveMediaProps = (
  value,
  { widths = RESPONSIVE_MEDIA_WIDTHS, fallbackWidth = 1440, sizes = "100vw" } = {}
) => {
  const src = resolveMediaUrl(value);
  const source = String(value || "").trim();
  if (!src || !MANAGED_IMAGE_ASSET_PATTERN.test(source)) return { src };

  const candidates = [...new Set(widths.map(boundedMediaWidth))]
    .sort((left, right) => left - right);
  const appendWidth = (width) => `${src}${src.includes("?") ? "&" : "?"}w=${width}`;
  const safeFallback = boundedMediaWidth(fallbackWidth);

  return {
    src: appendWidth(safeFallback),
    srcSet: (candidates.length ? candidates : RESPONSIVE_MEDIA_WIDTHS)
      .map((width) => `${appendWidth(width)} ${width}w`).join(", "),
    sizes,
  };
};

export const resolveDocumentUrl = (value) => resolveSupportedAssetUrl(value, {
  relativePattern: RELATIVE_DOCUMENT_FILE_PATTERN,
  managedPattern: MANAGED_DOCUMENT_ASSET_PATTERN,
  requireExternalExtension: true,
});
