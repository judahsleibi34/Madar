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
}) => {
  const pos = element.position?.[viewport] || createPosition()[viewport];
  const location = findElementLocation(element.id);
  const section = activePage?.sections.find((item) => item.id === location?.sectionId);
  const viewportWidth = viewports[viewport] || viewports.desktop;
  const sectionHeight = getSectionCanvasHeight(section, viewport);
  const x = Math.max(0, Math.min(Number(pos.x) || 0, viewportWidth));
  const y = Math.max(0, Math.min(Number(pos.y) || 0, sectionHeight));
  const width = Math.max(1, Math.min(Number(pos.width) || 240, viewportWidth - x));
  const height = Math.max(1, Number(pos.height) || 80);

  return {
    position: "absolute",
    left: 0,
    top: 0,
    width: `${width}px`,
    height: `${height}px`,
    minHeight:
      element.type === "metric" || element.type === "list"
        ? `${getMetricMinimumHeight(element)}px`
        : element.type === "reservationBlock"
          ? `${getDirectElementMinimumSize(element).height}px`
        : undefined,
    maxWidth: `${Math.max(1, viewportWidth - x)}px`,
    transform: `translate3d(${x}px, ${y}px, 0)`,
  };
};

