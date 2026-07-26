import { clampElementToBounds } from "./PageBuilder.bounds";

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
  const elementStyles =
    element.type === "formBlock"
      ? Object.fromEntries(
          Object.entries(element.styles || {}).filter(
            ([key]) => key !== "backgroundColor" && key !== "borderRadius"
          )
        )
      : element.styles;

  return {
    ...elementStyles,
    "--builder-element-width": layoutWidth || "auto",
    "--builder-element-align": normalizeElementAlignSelf(element.styles.alignSelf) || "auto",
    "--builder-element-color": element.styles.color || "inherit",
    "--builder-element-bg": element.type === "formBlock" ? "transparent" : element.styles.backgroundColor || "transparent",
    "--builder-element-radius": element.type === "formBlock" ? "0" : element.styles.borderRadius || "0",
    "--builder-element-font-size": element.styles.fontSize || "inherit",
    "--builder-element-line-height": element.styles.lineHeight || "inherit",
    "--builder-element-text-align": element.styles.textAlign || "inherit",
    position: "relative",
    transform: undefined,
    width: layoutWidth,
    minHeight: element.styles.minHeight || undefined,
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
  let clamped = clampElementToBounds(
    {
      ...(position || {}),
      width: Number(position?.width) || 240,
      height: Number(position?.height) || 80,
    },
    { x: 0, y: 0, width: viewportWidth, height: sectionHeight },
    {
      minWidth: minimumSize.width,
      minHeight: minimumSize.height,
      allowBottomOverflow: true,
    }
  );
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

