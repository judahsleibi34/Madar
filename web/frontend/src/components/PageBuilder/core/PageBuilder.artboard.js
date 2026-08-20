import { viewports } from "./PageBuilder.constants";
import { createPosition } from "./PageBuilder.factories";

export const ARTBOARD_VIEWPORT_MODES = Object.freeze(["desktop", "tablet", "mobile"]);
export const LIVE_VIEWPORT_CROSSOVERS = Object.freeze({
  mobileMax: 600,
  tabletMax: 1024,
});

export const normalizeArtboardViewportMode = (value) =>
  ARTBOARD_VIEWPORT_MODES.includes(value) ? value : "desktop";

export const getArtboardLogicalWidth = (viewportMode) =>
  viewports[normalizeArtboardViewportMode(viewportMode)] || viewports.desktop;

export const getLiveArtboardViewportMode = (viewportWidth) => {
  const width = Math.max(1, Number(viewportWidth) || viewports.desktop);
  if (width <= LIVE_VIEWPORT_CROSSOVERS.mobileMax) return "mobile";
  if (width <= LIVE_VIEWPORT_CROSSOVERS.tabletMax) return "tablet";
  return "desktop";
};

export const getFitPresentationZoom = (availableWidth, logicalWidth) => {
  const available = Math.max(1, Number(availableWidth) || 1);
  const logical = Math.max(1, Number(logicalWidth) || 1);
  return Math.min(1, available / logical);
};

export const getEditorCameraStageWidth = (logicalWidth, editorZoom) => {
  const logical = Math.max(1, Number(logicalWidth) || 1);
  const zoom = Math.max(0.0001, Number(editorZoom) || 1);
  return logical * zoom;
};

export const getLivePresentationZoom = (availableWidth, viewportMode) => {
  const available = Math.max(1, Number(availableWidth) || 1);
  const mode = normalizeArtboardViewportMode(viewportMode);
  const logicalWidth = getArtboardLogicalWidth(mode);
  return Math.min(1, available / logicalWidth);
};

export const getLiveArtboardProfile = (viewportWidth) => {
  const availableWidth = Math.max(1, Number(viewportWidth) || viewports.desktop);
  const viewportMode = getLiveArtboardViewportMode(availableWidth);
  const logicalWidth = getArtboardLogicalWidth(viewportMode);
  return {
    viewportMode,
    logicalWidth,
    presentationZoom: getLivePresentationZoom(availableWidth, viewportMode),
  };
};

export const clampEditorZoom = (value) =>
  Math.min(2, Math.max(0.1, Number(value) || 1));

export const getArtboardElementPosition = (element, viewportMode) => {
  const mode = normalizeArtboardViewportMode(viewportMode);
  const positions = element?.position || {};
  if (positions[mode]) return positions[mode];

  const fallbackOrder = mode === "mobile"
    ? ["tablet", "desktop"]
    : mode === "tablet"
      ? ["desktop", "mobile"]
      : ["tablet", "mobile"];
  const sourceMode = fallbackOrder.find((candidate) => positions[candidate]);
  if (!sourceMode) return createPosition()[mode];

  const source = positions[sourceMode];
  const ratio = getArtboardLogicalWidth(mode) / getArtboardLogicalWidth(sourceMode);
  return {
    ...source,
    x: (Number(source.x) || 0) * ratio,
    y: (Number(source.y) || 0) * ratio,
    width: (Number(source.width) || 240) * ratio,
    height: (Number(source.height) || 80) * ratio,
  };
};

export const physicalRectToLogicalRect = (rect, presentationZoom = 1, physicalOrigin = {}) => {
  const zoom = Math.max(0.0001, Number(presentationZoom) || 1);
  return {
    x: ((Number(rect?.x ?? rect?.left) || 0) - (Number(physicalOrigin?.x ?? physicalOrigin?.left) || 0)) / zoom,
    y: ((Number(rect?.y ?? rect?.top) || 0) - (Number(physicalOrigin?.y ?? physicalOrigin?.top) || 0)) / zoom,
    width: (Number(rect?.width) || 0) / zoom,
    height: (Number(rect?.height) || 0) / zoom,
  };
};

export const logicalRectToPhysicalRect = (rect, presentationZoom = 1, physicalOrigin = {}) => {
  const zoom = Math.max(0.0001, Number(presentationZoom) || 1);
  return {
    x: (Number(physicalOrigin?.x ?? physicalOrigin?.left) || 0) + (Number(rect?.x ?? rect?.left) || 0) * zoom,
    y: (Number(physicalOrigin?.y ?? physicalOrigin?.top) || 0) + (Number(rect?.y ?? rect?.top) || 0) * zoom,
    width: (Number(rect?.width) || 0) * zoom,
    height: (Number(rect?.height) || 0) * zoom,
  };
};
