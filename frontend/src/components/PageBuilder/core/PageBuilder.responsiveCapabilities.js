export const RESPONSIVE_LAYOUT_ENGINE_VERSION = 1;
export const RESPONSIVE_LAYOUT_MODES = Object.freeze({
  legacy: "legacy",
  smart: "smart",
});

const DEFAULT_CAPABILITIES = Object.freeze({
  sizingX: "relative",
  sizingY: "auto",
  minWidth: 80,
  minHeight: 48,
  maxWidth: Infinity,
  maxHeight: Infinity,
  preferredWidth: 240,
  preferredHeight: 96,
  aspectRatio: null,
  canShrinkX: true,
  canGrowX: true,
  canGrowY: true,
  canWrap: true,
  keepWithNext: false,
  collisionPolicy: "solid",
  alignmentPreference: "start",
  responsivePriority: 50,
  minimumFontSize: 12,
});

const capabilityRegistry = new Map();

const finiteOr = (value, fallback) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const normalizeCapabilities = (value = {}) => ({
  ...DEFAULT_CAPABILITIES,
  ...value,
  minWidth: Math.max(1, finiteOr(value.minWidth, DEFAULT_CAPABILITIES.minWidth)),
  minHeight: Math.max(1, finiteOr(value.minHeight, DEFAULT_CAPABILITIES.minHeight)),
  maxWidth: Math.max(1, finiteOr(value.maxWidth, DEFAULT_CAPABILITIES.maxWidth)),
  maxHeight: Math.max(1, finiteOr(value.maxHeight, DEFAULT_CAPABILITIES.maxHeight)),
  preferredWidth: Math.max(1, finiteOr(value.preferredWidth, DEFAULT_CAPABILITIES.preferredWidth)),
  preferredHeight: Math.max(1, finiteOr(value.preferredHeight, DEFAULT_CAPABILITIES.preferredHeight)),
  aspectRatio: finiteOr(value.aspectRatio, null),
  responsivePriority: finiteOr(value.responsivePriority, DEFAULT_CAPABILITIES.responsivePriority),
  minimumFontSize: Math.max(1, finiteOr(value.minimumFontSize, DEFAULT_CAPABILITIES.minimumFontSize)),
});

export const registerResponsiveCapabilities = (componentType, capabilities) => {
  const type = String(componentType || "").trim();
  if (!type) throw new Error("A component type is required for responsive capabilities.");
  capabilityRegistry.set(type, Object.freeze(normalizeCapabilities(capabilities)));
};

const register = (types, capabilities) => {
  types.forEach((type) => registerResponsiveCapabilities(type, capabilities));
};

register(["heading"], {
  sizingX: "relative",
  sizingY: "auto",
  minWidth: 120,
  minHeight: 48,
  preferredWidth: 520,
  preferredHeight: 112,
  responsivePriority: 90,
  minimumFontSize: 18,
});
register(["text"], {
  sizingX: "relative",
  sizingY: "auto",
  minWidth: 120,
  minHeight: 48,
  preferredWidth: 420,
  preferredHeight: 104,
  responsivePriority: 80,
  minimumFontSize: 12,
});
register(["button"], {
  sizingX: "hug",
  sizingY: "hug",
  minWidth: 80,
  minHeight: 42,
  preferredWidth: 160,
  preferredHeight: 42,
  canGrowY: false,
  responsivePriority: 85,
});
register(["image"], {
  sizingX: "relative",
  sizingY: "aspect",
  minWidth: 80,
  minHeight: 48,
  preferredWidth: 380,
  preferredHeight: 260,
  aspectRatio: 380 / 260,
  responsivePriority: 35,
});
register(["divider", "thinDivider"], {
  sizingX: "fill",
  sizingY: "fixed",
  minWidth: 80,
  minHeight: 24,
  preferredWidth: 380,
  preferredHeight: 32,
  canGrowY: false,
  responsivePriority: 20,
});
register(["metric", "list", "document"], {
  sizingX: "relative",
  sizingY: "auto",
  minWidth: 160,
  minHeight: 170,
  preferredWidth: 280,
  preferredHeight: 170,
});
register(["card", "carousel", "carouselCards", "carouselSplit", "carouselSpotlight", "carouselStack", "carouselEditorial", "circularGallery", "photoProofing"], {
  sizingX: "relative",
  sizingY: "auto",
  minWidth: 180,
  minHeight: 180,
  preferredWidth: 360,
  preferredHeight: 360,
  responsivePriority: 40,
});
register(["formBlock", "reservationBlock", "loginBlock", "registrationBlock"], {
  sizingX: "fill",
  sizingY: "auto",
  minWidth: 280,
  minHeight: 320,
  preferredWidth: 640,
  preferredHeight: 460,
  responsivePriority: 95,
});
register(["embed"], {
  sizingX: "relative",
  sizingY: "aspect",
  minWidth: 180,
  minHeight: 120,
  preferredWidth: 480,
  preferredHeight: 270,
  aspectRatio: 16 / 9,
});

export const getResponsiveCapabilities = (element) => {
  const registered = capabilityRegistry.get(String(element?.type || "")) || DEFAULT_CAPABILITIES;
  const declared = element?.responsive?.capabilities;
  const capabilities = normalizeCapabilities({
    ...registered,
    ...(declared && typeof declared === "object" ? declared : {}),
  });

  if (element?.layer === "behindText") {
    capabilities.collisionPolicy = "background";
  }
  return capabilities;
};

export const isSmartResponsiveProject = (project) =>
  project?.responsiveLayout?.mode === RESPONSIVE_LAYOUT_MODES.smart &&
  Number(project?.responsiveLayout?.engineVersion) === RESPONSIVE_LAYOUT_ENGINE_VERSION;

export const getResponsiveOverride = (element, viewportMode) => {
  const override = element?.responsive?.overrides?.[viewportMode];
  if (!override || typeof override !== "object") return null;
  if (override.mode === "auto") return { mode: "auto" };
  if (override.mode !== "manual" || !override.rect) return null;
  return {
    mode: "manual",
    rect: {
      x: finiteOr(override.rect.x, 0),
      y: finiteOr(override.rect.y, 0),
      width: Math.max(1, finiteOr(override.rect.width, DEFAULT_CAPABILITIES.preferredWidth)),
      height: Math.max(1, finiteOr(override.rect.height, DEFAULT_CAPABILITIES.preferredHeight)),
    },
  };
};

export const withManualResponsiveOverride = (element, viewportMode, rect) => ({
  ...element,
  responsive: {
    ...(element?.responsive || {}),
    overrides: {
      ...(element?.responsive?.overrides || {}),
      [viewportMode]: { mode: "manual", rect: { ...rect } },
    },
  },
});

export const withAutoResponsiveOverride = (element, viewportMode) => ({
  ...element,
  responsive: {
    ...(element?.responsive || {}),
    overrides: {
      ...(element?.responsive?.overrides || {}),
      [viewportMode]: { mode: "auto" },
    },
  },
});

export const getRegisteredResponsiveComponentTypes = () => [...capabilityRegistry.keys()].sort();

export { DEFAULT_CAPABILITIES };
