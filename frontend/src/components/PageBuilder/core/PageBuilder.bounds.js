const finiteNumber = (value, fallback = 0) => {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
};

const nonNegative = (value, fallback = 0) =>
  Math.max(0, finiteNumber(value, fallback));

const clamp = (value, minimum, maximum) =>
  Math.min(Math.max(value, minimum), Math.max(minimum, maximum));

const stableNumber = (value) => Math.round(value * 1000) / 1000;

/**
 * Constrains an element rectangle to its immediate parent's local bounds.
 *
 * Move/normalization preserves the requested size where possible and moves the
 * rectangle inside. Resize preserves the requested origin and limits the size
 * to the space remaining to the parent's right and bottom edges. In both modes
 * an element larger than its parent is reduced to fit.
 */
export const clampElementToBounds = (
  position,
  bounds,
  {
    minWidth = 0,
    minHeight = 0,
    mode = "move",
    allowBottomOverflow = false,
  } = {}
) => {
  const boundX = finiteNumber(bounds?.x, 0);
  const boundY = finiteNumber(bounds?.y, 0);
  const boundWidth = nonNegative(bounds?.width);
  const boundHeight = nonNegative(bounds?.height);
  const boundRight = boundX + boundWidth;
  const boundBottom = boundY + boundHeight;
  const safeMinWidth = Math.min(nonNegative(minWidth), boundWidth);
  const safeMinHeight = allowBottomOverflow
    ? nonNegative(minHeight)
    : Math.min(nonNegative(minHeight), boundHeight);
  const requestedWidth = nonNegative(position?.width, safeMinWidth);
  const requestedHeight = nonNegative(position?.height, safeMinHeight);

  if (mode === "resize") {
    const x = clamp(finiteNumber(position?.x, boundX), boundX, boundRight);
    const y = allowBottomOverflow
      ? Math.max(boundY, finiteNumber(position?.y, boundY))
      : clamp(finiteNumber(position?.y, boundY), boundY, boundBottom);
    const availableWidth = Math.max(0, boundRight - x);
    const availableHeight = Math.max(0, boundBottom - y);
    const width = Math.min(
      availableWidth,
      Math.max(Math.min(safeMinWidth, availableWidth), requestedWidth)
    );
    const height = allowBottomOverflow
      ? Math.max(safeMinHeight, requestedHeight)
      : Math.min(
          availableHeight,
          Math.max(Math.min(safeMinHeight, availableHeight), requestedHeight)
        );

    return {
      ...(position || {}),
      x: stableNumber(x),
      y: stableNumber(y),
      width: stableNumber(width),
      height: stableNumber(height),
    };
  }

  const width = Math.min(boundWidth, Math.max(safeMinWidth, requestedWidth));
  const height = allowBottomOverflow
    ? Math.max(safeMinHeight, requestedHeight)
    : Math.min(boundHeight, Math.max(safeMinHeight, requestedHeight));
  const x = clamp(
    finiteNumber(position?.x, boundX),
    boundX,
    boundRight - width
  );
  const y = allowBottomOverflow
    ? Math.max(boundY, finiteNumber(position?.y, boundY))
    : clamp(
        finiteNumber(position?.y, boundY),
        boundY,
        boundBottom - height
      );

  return {
    ...(position || {}),
    x: stableNumber(x),
    y: stableNumber(y),
    width: stableNumber(width),
    height: stableNumber(height),
  };
};

const getAxisTransformScale = (renderedSize, layoutSize) => {
  const rendered = nonNegative(renderedSize);
  const layout = nonNegative(layoutSize);
  return rendered > 0 && layout > 0 ? rendered / layout : 1;
};

/**
 * Describes a canvas in the same local coordinate system used by saved element
 * positions. clientWidth/clientHeight exclude borders and include padding,
 * matching the padding-box containing block used by absolutely positioned
 * children. The rendered/layout ratio accounts for CSS transforms and zoom.
 */
export const getCanvasLocalGeometry = (
  canvas,
  { coordinateScale = 1 } = {}
) => {
  if (!canvas?.getBoundingClientRect) return null;

  const rect = canvas.getBoundingClientRect();
  const layoutWidth = nonNegative(canvas.offsetWidth, rect.width);
  const layoutHeight = nonNegative(canvas.offsetHeight, rect.height);
  const transformScaleX = getAxisTransformScale(rect.width, layoutWidth);
  const transformScaleY = getAxisTransformScale(rect.height, layoutHeight);
  const modelScale = Math.max(0.0001, finiteNumber(coordinateScale, 1));
  const clientWidth = nonNegative(
    canvas.clientWidth,
    Math.max(0, layoutWidth - nonNegative(canvas.clientLeft))
  );
  const clientHeight = nonNegative(
    canvas.clientHeight,
    Math.max(0, layoutHeight - nonNegative(canvas.clientTop))
  );

  return {
    canvas,
    rect,
    bounds: {
      x: 0,
      y: 0,
      width: stableNumber(clientWidth / modelScale),
      height: stableNumber(clientHeight / modelScale),
    },
    clientScaleX: transformScaleX * modelScale,
    clientScaleY: transformScaleY * modelScale,
    originClientX: rect.left + nonNegative(canvas.clientLeft) * transformScaleX,
    originClientY: rect.top + nonNegative(canvas.clientTop) * transformScaleY,
    scrollX: nonNegative(canvas.scrollLeft) / modelScale,
    scrollY: nonNegative(canvas.scrollTop) / modelScale,
  };
};

export const clientPointToCanvasLocal = (
  canvas,
  clientX,
  clientY,
  options
) => {
  const geometry = getCanvasLocalGeometry(canvas, options);
  if (!geometry) return null;

  return {
    x: stableNumber(
      (finiteNumber(clientX) - geometry.originClientX) / geometry.clientScaleX +
        geometry.scrollX
    ),
    y: stableNumber(
      (finiteNumber(clientY) - geometry.originClientY) / geometry.clientScaleY +
        geometry.scrollY
    ),
    bounds: geometry.bounds,
    geometry,
  };
};

export const getImmediateParentCanvasGeometry = (
  elementFrame,
  options
) => {
  const parent = elementFrame?.parentElement;
  if (!parent) return null;

  return {
    parent,
    geometry: getCanvasLocalGeometry(parent, options),
  };
};
