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

  return {
    ...element.styles,
    "--builder-element-width": layoutWidth || "auto",
    "--builder-element-align": normalizeElementAlignSelf(element.styles.alignSelf) || "auto",
    "--builder-element-color": element.styles.color || "inherit",
    "--builder-element-bg": element.styles.backgroundColor || "transparent",
    "--builder-element-radius": element.styles.borderRadius || "0",
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
  const left = `${((Number(pos.x) || 0) / viewportWidth) * 100}%`;
  const top = `${((Number(pos.y) || 0) / sectionHeight) * 100}%`;
  const width = `${((Number(pos.width) || 240) / viewportWidth) * 100}%`;
  const minHeight = `${((Number(pos.height) || 80) / sectionHeight) * 100}%`;

  return {
    position: "absolute",
    left,
    top,
    width,
    height: minHeight,
    minHeight:
      element.type === "metric" || element.type === "list"
        ? `${(getMetricMinimumHeight(element) / sectionHeight) * 100}%`
        : element.type === "reservationBlock"
          ? `${(getDirectElementMinimumSize(element).height / sectionHeight) * 100}%`
        : undefined,
    maxWidth: `calc(100% - ${left})`,
  };
};

