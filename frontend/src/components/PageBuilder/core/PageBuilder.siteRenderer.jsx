import { Fragment, forwardRef, useCallback, useLayoutEffect, useMemo, useRef, useState } from "react";

import { getRowCarouselElements } from "./PageBuilder.elementLayout";
import {
  getDirectElementMinimumSize,
  getMetricMinimumHeight,
  getSectionCanvasHeight,
} from "./PageBuilder.layout";
import { getDirectElementFrameStyle } from "./PageBuilder.styles";
import { getPageBuilderThemeVars } from "./PageBuilder.theme";
import {
  getArtboardElementPosition,
  getArtboardLogicalWidth,
  normalizeArtboardViewportMode,
} from "./PageBuilder.artboard";
import { getResponsiveCapabilities, isSmartResponsiveProject } from "./PageBuilder.responsiveCapabilities";
import { resolvePageResponsiveLayout } from "./PageBuilder.responsiveLayout";

const legacyMeasurableElementTypes = new Set(["formBlock", "reservationBlock", "loginBlock", "registrationBlock"]);

const mergeRefs = (...refs) => (node) => {
  refs.forEach((ref) => {
    if (typeof ref === "function") ref(node);
    else if (ref) ref.current = node;
  });
};

function MeasuredDirectElement({
  element,
  frameProps,
  frameStyle,
  shouldMeasure,
  onLogicalHeight,
  children,
}) {
  const frameRef = useRef(null);
  const { ref: suppliedRef, ...domFrameProps } = frameProps;

  useLayoutEffect(() => {
    if (!shouldMeasure) return undefined;
    if (element.type === "reservationBlock" && element.directSizeMode === "fixed") return undefined;

    const frame = frameRef.current;
    const content = frame?.querySelector(":scope > .direct-element-content");
    if (!content) return undefined;

    let animationFrame = null;
    let cancelled = false;
    const measure = () => {
      animationFrame = null;
      if (cancelled) return;
      // offsetHeight/scrollHeight are logical CSS pixels and are not affected by
      // the camera transform. getBoundingClientRect() would be physical pixels.
      const logicalHeight = Math.ceil(Math.max(content.scrollHeight || 0, content.offsetHeight || 0));
      if (logicalHeight > 0) onLogicalHeight(element.id, logicalHeight);
    };
    const schedule = () => {
      if (cancelled || animationFrame !== null) return;
      animationFrame = window.requestAnimationFrame(measure);
    };
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(schedule);
    observer?.observe(content);
    content.addEventListener("load", schedule, true);
    schedule();

    return () => {
      cancelled = true;
      if (animationFrame !== null) window.cancelAnimationFrame(animationFrame);
      observer?.disconnect();
      content.removeEventListener("load", schedule, true);
    };
  }, [element, onLogicalHeight, shouldMeasure]);

  return (
    <div
      {...domFrameProps}
      ref={mergeRefs(frameRef, suppliedRef)}
      style={frameStyle}
    >
      {children}
    </div>
  );
}

const SiteRenderer = forwardRef(function SiteRenderer({
  project,
  activePage,
  viewportMode = "desktop",
  presentationZoom = 1,
  availablePresentationWidth,
  responsiveLayoutWidth,
  responsiveChangedElementIds = [],
  responsiveTransientRectsBySection = {},
  renderElement,
  renderSiteHeader,
  renderSiteFooter,
  carouselElementTypes = new Set(),
  className = "",
  canvasStyle = {},
  getDirectElementPosition,
  getDirectCanvasProps,
  getDirectFrameProps,
  renderDirectElementOverlay,
  renderAfterDirectElement,
  getSectionProps,
  getColumnProps,
  renderEmptyColumn,
  filterElement = () => true,
  getSectionLogicalHeight,
  onElementMeasured,
}, forwardedRef) {
  const mode = normalizeArtboardViewportMode(viewportMode);
  const referenceLogicalWidth = getArtboardLogicalWidth(mode);
  const smartResponsive = isSmartResponsiveProject(project);
  const requestedLayoutWidth = smartResponsive
    ? Math.max(1, Number(responsiveLayoutWidth) || referenceLogicalWidth)
    : referenceLogicalWidth;
  const zoom = Math.min(2, Math.max(0.0001, Number(presentationZoom) || 1));
  const [measuredElementHeights, setMeasuredElementHeights] = useState({});
  const [lastMeasuredElementIds, setLastMeasuredElementIds] = useState([]);
  const [fontStateRevision, setFontStateRevision] = useState(0);
  const [assetStateRevision, setAssetStateRevision] = useState(0);
  const measurementsBySection = useMemo(() => {
    const result = {};
    Object.entries(measuredElementHeights).forEach(([key, height]) => {
      const [pageId, keyMode, keyWidth, sectionId, elementId] = key.split(":");
      if (pageId !== String(activePage?.id || "page") || keyMode !== mode || Number(keyWidth) !== requestedLayoutWidth) return;
      if (!result[sectionId]) result[sectionId] = {};
      result[sectionId][elementId] = height;
    });
    return result;
  }, [activePage?.id, measuredElementHeights, mode, requestedLayoutWidth]);
  const resolvedLayout = useMemo(() => resolvePageResponsiveLayout({
    project,
    page: activePage,
    viewportMode: mode,
    layoutWidth: requestedLayoutWidth,
    measurements: measurementsBySection,
    changedElementIds: [...new Set([...lastMeasuredElementIds, ...responsiveChangedElementIds])],
    transientRectsBySection: responsiveTransientRectsBySection,
    fontSignature: {
      theme: project?.theme?.typography || project?.theme?.fonts || "",
      readinessRevision: fontStateRevision,
    },
    assetState: {
      projectRevision: project?.assetRevision || "",
      loadRevision: assetStateRevision,
    },
  }), [
    activePage,
    lastMeasuredElementIds,
    measurementsBySection,
    mode,
    project,
    requestedLayoutWidth,
    assetStateRevision,
    fontStateRevision,
    responsiveChangedElementIds,
    responsiveTransientRectsBySection,
  ]);
  const logicalWidth = resolvedLayout?.layoutWidth || referenceLogicalWidth;
  useLayoutEffect(() => {
    if (!lastMeasuredElementIds.length) return undefined;
    const frame = window.requestAnimationFrame(() => setLastMeasuredElementIds([]));
    return () => window.cancelAnimationFrame(frame);
  }, [lastMeasuredElementIds, resolvedLayout]);
  const physicalAvailableWidth = Math.max(
    logicalWidth * zoom,
    Number(availablePresentationWidth) || 0
  );
  const bleedLogicalWidth = physicalAvailableWidth / zoom;
  const artboardRef = useRef(null);
  const [artboardHeight, setArtboardHeight] = useState(1);

  const reportElementHeight = useCallback((elementId, logicalHeight, sectionId) => {
    const measurementKey = `${activePage?.id || "page"}:${mode}:${logicalWidth}:${sectionId}:${elementId}`;
    setMeasuredElementHeights((current) =>
      Math.abs((current[measurementKey] || 0) - logicalHeight) <= 1
        ? current
        : { ...current, [measurementKey]: logicalHeight }
    );
    setLastMeasuredElementIds((current) =>
      current.length === 1 && current[0] === elementId ? current : [elementId]
    );
    onElementMeasured?.(elementId, logicalHeight, mode, sectionId);
  }, [activePage?.id, logicalWidth, mode, onElementMeasured]);

  useLayoutEffect(() => {
    const artboard = artboardRef.current;
    if (!artboard) return undefined;
    let animationFrame = null;
    let cancelled = false;
    const measure = () => {
      animationFrame = null;
      const nextHeight = Math.ceil(Math.max(artboard.scrollHeight, artboard.offsetHeight, 1));
      setArtboardHeight((current) => Math.abs(current - nextHeight) <= 1 ? current : nextHeight);
    };
    const schedule = () => {
      if (cancelled || animationFrame !== null) return;
      animationFrame = window.requestAnimationFrame(measure);
    };
    const scheduleAssetMeasurement = () => {
      if (cancelled) return;
      setAssetStateRevision((current) => current + 1);
      schedule();
    };
    const scheduleFontMeasurement = () => {
      if (cancelled) return;
      setFontStateRevision((current) => current + 1);
      schedule();
    };
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(schedule);
    observer?.observe(artboard);
    artboard.addEventListener("load", scheduleAssetMeasurement, true);
    document.fonts?.addEventListener?.("loadingdone", scheduleFontMeasurement);
    document.fonts?.ready?.then(scheduleFontMeasurement);
    schedule();
    return () => {
      cancelled = true;
      if (animationFrame !== null) window.cancelAnimationFrame(animationFrame);
      observer?.disconnect();
      artboard.removeEventListener("load", scheduleAssetMeasurement, true);
      document.fonts?.removeEventListener?.("loadingdone", scheduleFontMeasurement);
    };
  }, [activePage?.id, mode, project]);

  const sections = activePage?.sections || [];
  const resolvedSectionHeights = Object.fromEntries(sections.map((section) => {
    const smartSection = resolvedLayout?.sections?.[section.id];
    if (smartSection) return [section.id, smartSection.rect.height];
    const baseHeight = getSectionLogicalHeight?.(section, mode) || getSectionCanvasHeight(section, mode);
    if (!['direct', 'free'].includes(section.mode)) return [section.id, baseHeight];
    const requiredHeight = (section.freeElements || []).reduce((maximum, element) => {
      const position = getDirectElementPosition?.(element, section, mode)
        || resolvedLayout?.sections?.[section.id]?.elementRects?.[element.id]
        || getArtboardElementPosition(element, mode);
      const measuredHeight = measuredElementHeights[`${activePage?.id || "page"}:${mode}:${logicalWidth}:${section.id}:${element.id}`] || 0;
      const height = Math.max(Number(position.height) || 0, measuredHeight);
      return Math.max(maximum, (Number(position.y) || 0) + height + 48);
    }, baseHeight);
    return [section.id, requiredHeight];
  }));

  const cameraStyle = {
    width: `${logicalWidth * zoom}px`,
    height: `${artboardHeight * zoom}px`,
  };
  const artboardStyle = {
    ...getPageBuilderThemeVars(project?.theme),
    ...canvasStyle,
    width: `${logicalWidth}px`,
    minHeight: "1px",
    transform: `scale(${zoom})`,
    transformOrigin: "top left",
    "--site-presentation-zoom": zoom,
    "--site-logical-width": `${logicalWidth}px`,
    "--site-bleed-logical-width": `${bleedLogicalWidth}px`,
    "--site-bleed-offset-x": `${(logicalWidth - bleedLogicalWidth) / 2}px`,
  };

  return (
    <div
      className="site-renderer-camera"
      style={cameraStyle}
      data-presentation-zoom={zoom.toFixed(4)}
      data-logical-width={logicalWidth}
      data-viewport-mode={mode}
      data-responsive-layout-mode={smartResponsive ? "smart" : "legacy"}
      data-responsive-engine-version={resolvedLayout?.engineVersion || ""}
    >
      <div
        ref={mergeRefs(artboardRef, forwardedRef)}
        className={`builder-canvas site-renderer-artboard viewport-${mode} ${className}`.trim()}
        style={artboardStyle}
      >
        {renderSiteHeader?.()}
        {sections.map((section) => {
          const isFullBleed = section.layout?.fullBleed === true || section.layout?.width === "full";
          const sectionBackground = section.layout?.background;
          const bleedBackground = isFullBleed ? (
            <div
              className="site-section-bleed-background"
              data-section-bleed-for={section.id}
              aria-hidden="true"
              style={{ backgroundColor: sectionBackground, width: `${bleedLogicalWidth}px` }}
            />
          ) : null;
          const sectionProps = getSectionProps?.(section) || {};
          const {
            renderOverlay: renderSectionOverlay,
            className: sectionClassName = "",
            style: sectionStyle = {},
            ...domSectionProps
          } = sectionProps;
          if (section.mode === "direct" || section.mode === "free") {
            const logicalHeight = resolvedSectionHeights[section.id];
            const directCanvasProps = getDirectCanvasProps?.(section) || {};
            return (
              <section
                {...domSectionProps}
                key={section.id}
                className={`site-section direct-layout-section width-${section.layout?.width || "full"} ${isFullBleed ? "has-full-bleed" : ""} ${sectionClassName}`.trim()}
                style={{ ...sectionStyle, backgroundColor: isFullBleed ? "transparent" : sectionBackground, minHeight: `${logicalHeight}px` }}
              >
                {bleedBackground}
                <div
                  {...directCanvasProps}
                  className={`direct-layout-frame ${directCanvasProps.className || ""}`.trim()}
                  data-section-id={section.id}
                  style={{ width: `${logicalWidth}px`, minHeight: `${logicalHeight}px`, ...(directCanvasProps.style || {}) }}
                >
                  {(section.freeElements || []).filter(filterElement).map((element) => {
                    const responsiveCapabilities = getResponsiveCapabilities(element);
                    const position = getDirectElementPosition?.(element, section, mode)
                      || resolvedLayout?.sections?.[section.id]?.elementRects?.[element.id]
                      || getArtboardElementPosition(element, mode);
                    const measuredHeight = measuredElementHeights[`${activePage?.id || "page"}:${mode}:${logicalWidth}:${section.id}:${element.id}`] || 0;
                    const effectivePosition = {
                      ...position,
                      height: Math.max(Number(position.height) || 0, measuredHeight),
                    };
                    const frameStyle = {
                      ...getDirectElementFrameStyle({
                        element,
                        position: effectivePosition,
                        viewportWidth: logicalWidth,
                        sectionHeight: logicalHeight,
                        getMetricMinimumHeight,
                        getDirectElementMinimumSize,
                        canvasScale: 1,
                      }),
                      "--site-element-logical-height": `${effectivePosition.height}px`,
                      "--site-minimum-font-size": `${responsiveCapabilities.minimumFontSize}px`,
                    };
                    const suppliedFrameProps = getDirectFrameProps?.(element, section, frameStyle) || {};
                    const frameProps = {
                      ...suppliedFrameProps,
                      className: `direct-element-frame direct-element-frame-${element.type} ${element.type === "reservationBlock" && element.directSizeMode === "fixed" ? "is-fixed-size" : ""} ${element.layer === "behindText" ? "is-behind-text" : ""} ${suppliedFrameProps.className || ""}`.trim(),
                      "data-builder-element-id": element.id,
                      "data-logical-x": effectivePosition.x,
                      "data-logical-y": effectivePosition.y,
                      "data-logical-width": effectivePosition.width,
                      "data-logical-height": effectivePosition.height,
                    };
                    return (
                      <Fragment key={element.id}>
                        <MeasuredDirectElement
                          element={element}
                          frameProps={frameProps}
                          frameStyle={{ ...frameStyle, ...(suppliedFrameProps.style || {}) }}
                          shouldMeasure={smartResponsive
                            ? responsiveCapabilities.canGrowY
                            : legacyMeasurableElementTypes.has(element.type)}
                          onLogicalHeight={(elementId, height) => reportElementHeight(elementId, height, section.id)}
                        >
                          <div className="direct-element-content">
                            {renderElement(element, false, section)}
                          </div>
                          {renderDirectElementOverlay?.(element, section, frameStyle)}
                        </MeasuredDirectElement>
                        {renderAfterDirectElement?.(element, section, frameStyle)}
                      </Fragment>
                    );
                  })}
                  {renderSectionOverlay?.()}
                </div>
              </section>
            );
          }

          return (
            <section
              {...domSectionProps}
              key={section.id}
              className={`site-section width-${section.layout?.width || "full"} padding-${section.layout?.paddingY || "none"} ${isFullBleed ? "has-full-bleed" : ""} ${sectionClassName}`.trim()}
              style={{ ...sectionStyle, backgroundColor: isFullBleed ? "transparent" : sectionBackground }}
            >
              {bleedBackground}
              {(section.rows || []).map((row) => (
                <div key={row.id} className={`site-row columns-${row.layout?.columns || 1} align-${row.layout?.align || "center"} gap-${row.layout?.gap || "medium"}`}>
                  {(row.columns || []).map((column) => {
                    const columnProps = getColumnProps?.(column, section) || {};
                    return (
                      <div
                        {...columnProps}
                        key={column.id}
                        data-column-id={column.id}
                        className={`site-column column-align-${column.layout?.align || "left"} ${columnProps.className || ""}`.trim()}
                      >
                        {(column.elements || []).filter(filterElement).filter((element) => !carouselElementTypes.has(element.type)).map((element) => renderElement(element, false, section))}
                        {renderEmptyColumn?.(column, section)}
                      </div>
                    );
                  })}
                  {getRowCarouselElements(row, carouselElementTypes).filter(filterElement).map((element) => renderElement(element, false, section))}
                </div>
              ))}
            </section>
          );
        })}
        {renderSiteFooter?.()}
      </div>
    </div>
  );
});

export default SiteRenderer;
