import { clampElementToBounds } from "./PageBuilder.bounds";

export const getDirectCanvasScaleStyles = ({ logicalWidth, logicalHeight, scale = 1 }) => {
  const width = Math.max(1, Number(logicalWidth) || 1);
  const height = Math.max(1, Number(logicalHeight) || 1);
  const safeScale = Math.min(1, Math.max(0.0001, Number(scale) || 1));

  return {
    section: { minHeight: `${height * safeScale}px` },
    shell: {
      width: `${width * safeScale}px`,
      height: `${height * safeScale}px`,
    },
    frame: {
      width: `${width}px`,
      minHeight: `${height}px`,
      transform: `scale(${safeScale})`,
      transformOrigin: "top left",
    },
  };
};

export const getResponsiveDirectCanvasStyles = ({ logicalHeight, scale = 1 }) => {
  const height = Math.max(1, Number(logicalHeight) || 1);
  const safeScale = Math.max(0.0001, Number(scale) || 1);
  const renderedHeight = height * safeScale;

  return {
    section: { minHeight: `${renderedHeight}px` },
    shell: {
      width: "100%",
      height: `${renderedHeight}px`,
    },
    frame: {
      width: "100%",
      minHeight: `${renderedHeight}px`,
    },
  };
};

export const getBuilderElementStyle = ({
  element,
  selected,
  carouselElementTypes,
  getElementPlacementMargins,
  getElementLayoutWidth,
  normalizeElementAlignSelf,
}) => {
  const isSelected = selected.type === "element" && selected.id === element.id;
  const placementMargins = getElementPlacementMargins(element.styles.alignSelf);
  const layoutWidth =
    getElementLayoutWidth(element.styles.width, element.styles.alignSelf) ||
    (carouselElementTypes.has(element.type) ? "100%" : undefined);
  const sourceStyles = element.styles || {};
  const sourceTextColor = String(sourceStyles.color || "").trim();
  const resolvedElementColor = element.type === "text" && [
    "",
    "var(--theme-text)",
    "var(--theme-text-soft)",
  ].includes(sourceTextColor)
    ? "#000000"
    : sourceStyles.color || "inherit";
  const elementStyles =
    element.type === "formBlock"
      ? Object.fromEntries(
          Object.entries(element.styles || {}).filter(
            ([key]) => key !== "backgroundColor" && key !== "borderRadius"
          )
        )
      : element.type === "button"
        ? Object.fromEntries(
            Object.entries(sourceStyles).filter(
              ([key]) => key !== "backgroundColor" && key !== "color"
            )
          )
        : sourceStyles;

  return {
    ...elementStyles,
    "--builder-element-width": layoutWidth || "auto",
    "--builder-element-align": normalizeElementAlignSelf(element.styles.alignSelf) || "auto",
    "--builder-element-color": element.type === "button" ? "inherit" : resolvedElementColor,
    "--builder-element-bg": ["formBlock", "button"].includes(element.type) ? "transparent" : sourceStyles.backgroundColor || "transparent",
    "--builder-element-radius": element.type === "formBlock" ? "0" : sourceStyles.borderRadius || "0",
    "--builder-element-font-size": sourceStyles.fontSize || "inherit",
    "--builder-element-line-height": sourceStyles.lineHeight || "inherit",
    "--builder-element-text-align": sourceStyles.textAlign || "inherit",
    position: "relative",
    transform: undefined,
    ...(element.type === "text" ? { color: resolvedElementColor } : {}),
    width: layoutWidth,
    minHeight: sourceStyles.minHeight || undefined,
    maxWidth: "100%",
    alignSelf: normalizeElementAlignSelf(element.styles.alignSelf),
    ...placementMargins,
    zIndex: isSelected ? 5 : 1,
  };
};

export const getBuilderFreeElementStyle = ({
  element,
  viewport,
  activePage,
  viewports,
  createPosition,
  findElementLocation,
  getSectionCanvasHeight,
  getMetricMinimumHeight,
  getDirectElementMinimumSize,
  canvasScale = 1,
}) => {
  const pos = element.position?.[viewport] || createPosition()[viewport];
  const location = findElementLocation(element.id);
  const section = activePage?.sections.find((item) => item.id === location?.sectionId);
  const viewportWidth = viewports[viewport] || viewports.desktop;
  const sectionHeight = getSectionCanvasHeight(section, viewport);
  return getDirectElementFrameStyle({
    element,
    position: pos,
    viewportWidth,
    sectionHeight,
    getMetricMinimumHeight,
    getDirectElementMinimumSize,
    canvasScale,
  });
};

export const getDirectElementFrameStyle = ({
  element,
  position,
  viewportWidth,
  sectionHeight,
  getMetricMinimumHeight,
  getDirectElementMinimumSize,
  canvasScale = 1,
}) => {
  const minimumSize = getDirectElementMinimumSize(element);
  const requestedPosition = {
    ...(position || {}),
    width: Number(position?.width) || 240,
    height:
      element?.type === "imageButton" && element.imageButtonVariant === "editorialCard"
        ? 240
        : Number(position?.height) || 80,
  };
  let clamped = clampElementToBounds(
    requestedPosition,
    { x: 0, y: 0, width: viewportWidth, height: sectionHeight },
    {
      minWidth: minimumSize.width,
      minHeight: minimumSize.height,
      allowBottomOverflow: true,
    }
  );
  const imageAspectRatio = Number(element?.mediaAspectRatio);
  if (element.type === "image" && Number.isFinite(imageAspectRatio) && imageAspectRatio > 0) {
    clamped = {
      ...clamped,
      height: Math.max(minimumSize.height, Math.round(clamped.width / imageAspectRatio)),
    };
  }
  // Headings should use the space that is actually available in their row.
  // Older saved headings do not have directWidthMode, so they inherit the
  // improved auto-width behavior too. A resize interaction marks the heading
  // as fixed and preserves the width chosen by the user.
  if (element.type === "heading" && element.directWidthMode !== "fixed") {
    clamped = clampElementToBounds(
      {
        ...clamped,
        width: Math.max(minimumSize.width, viewportWidth - clamped.x),
      },
      { x: 0, y: 0, width: viewportWidth, height: sectionHeight },
      {
        minWidth: minimumSize.width,
        minHeight: minimumSize.height,
        allowBottomOverflow: true,
      }
    );
  }
  const { x, y, width, height } = clamped;

  return {
    position: "absolute",
    left: 0,
    top: 0,
    width: `${width * canvasScale}px`,
    height: `${height * canvasScale}px`,
    minHeight:
      element.type === "metric" || element.type === "list"
        ? `${getMetricMinimumHeight(element) * canvasScale}px`
        : element.type === "reservationBlock"
          ? `${getDirectElementMinimumSize(element).height * canvasScale}px`
        : undefined,
    maxWidth: `${Math.max(1, viewportWidth - x) * canvasScale}px`,
    transform: `translate3d(${x * canvasScale}px, ${y * canvasScale}px, 0)`,
    zIndex: element.layer === "behindText" ? 0 : 1,
  };
};
