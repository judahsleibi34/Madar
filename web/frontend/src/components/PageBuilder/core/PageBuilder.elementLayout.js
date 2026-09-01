export const normalizeElementAlignSelf = (value) => {
  if (!value || value === "auto") return undefined;
  if (value === "left") return "flex-start";
  if (value === "right") return "flex-end";
  return value;
};

export const getElementLayoutWidth = (value, alignSelf = "auto") => {
  const placement = normalizeElementAlignSelf(alignSelf);

  if (placement === "stretch") return "100%";

  if (!value || value === "auto") return undefined;
  return value;
};

export const getElementAlignControlValue = (value) =>
  normalizeElementAlignSelf(value) || "auto";

export const getComponentPositionClass = (position) => {
  const normalized = normalizeElementAlignSelf(position);
  if (position === "Left" || normalized === "flex-start") return "justify-start";
  if (position === "Center" || normalized === "center") return "justify-center";
  if (position === "Right" || normalized === "flex-end") return "justify-end";
  return "justify-center";
};

export const getCarouselWidthValue = (element) => {
  const width = element.styles?.width;
  if (!width || width === "auto") return "100%";
  return width;
};

export const getElementPlacementMargins = (value) => {
  const placement = normalizeElementAlignSelf(value);

  if (placement === "center") {
    return { marginLeft: "auto", marginRight: "auto" };
  }

  if (placement === "flex-end") {
    return { marginLeft: "auto", marginRight: "0" };
  }

  if (placement === "flex-start") {
    return { marginLeft: "0", marginRight: "auto" };
  }

  return { marginLeft: undefined, marginRight: undefined };
};

export const isDirectionalElementPlacement = (value) =>
  ["flex-start", "center", "flex-end", "left", "right"].includes(value);

export const getClosestColumnIdFromEvent = (event) => {
  const columns = Array.from(event.currentTarget.querySelectorAll("[data-column-id]"));
  if (columns.length === 0) return "";

  const point = { x: event.clientX, y: event.clientY };
  let closest = { id: "", distance: Number.POSITIVE_INFINITY };

  columns.forEach((column) => {
    const rect = column.getBoundingClientRect();
    const center = {
      x: rect.left + rect.width / 2,
      y: rect.top + rect.height / 2,
    };
    const distance = Math.hypot(point.x - center.x, point.y - center.y);

    if (distance < closest.distance) {
      closest = { id: column.dataset.columnId || "", distance };
    }
  });

  return closest.id;
};

export const getCarouselVariant = (element) => {
  if (element.carouselVariant) return element.carouselVariant;
  if (element.type === "card") return "cards";
  if (element.type === "logoSlider") return "logos";
  if (element.type === "carouselCards") return "cards";
  if (element.type === "carouselSplit") return "split";
  if (element.type === "carouselSpotlight") return "spotlight";
  if (element.type === "carouselStack") return "stack";
  if (element.type === "carouselEditorial") return "editorial";
  if (element.type === "circularGallery") return "circular";
  return "lightswind";
};

export const getRowCarouselElements = (row, carouselElementTypes) =>
  (row.columns || []).flatMap((column) =>
    (column.elements || []).filter((element) => carouselElementTypes.has(element.type))
  );
