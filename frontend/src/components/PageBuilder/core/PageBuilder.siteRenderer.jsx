import { Fragment, forwardRef, useCallback, useLayoutEffect, useRef, useState } from "react";

import { getRowCarouselElements } from "./PageBuilder.elementLayout";
import {
  getDirectElementMinimumSize,
  getMetricMinimumHeight,
  getSectionCanvasHeight,
} from "./PageBuilder.layout";
import { getDirectElementFrameStyle } from "./PageBuilder.styles";
import {
  RESPONSIVE_ELEMENT_GAP_RATIO,
  resolveMobileReadingOrder,
  resolveDirectElementCollisionPadding,
} from "./PageBuilder.collisionPadding";
import { resolveResponsiveElementSizing } from "./PageBuilder.responsiveSizing";
import {
  getUnderTextImageRelationships,
  projectUnderTextImagePosition,
} from "./PageBuilder.underTextLayout";
import { getPageBuilderThemeVars } from "./PageBuilder.theme";
import {
  getArtboardElementPosition,
  getArtboardLogicalWidth,
  normalizeArtboardViewportMode,
} from "./PageBuilder.artboard";

const intrinsicHeightElementTypes = new Set(["heading", "text", "list"]);
const compactDividerTypes = new Set(["divider", "thinDivider"]);

const measurableElementTypes = new Set([
  "heading",
  "text",
  "list",
  "formBlock",
  "reservationBlock",
  "loginBlock",
  "registrationBlock",
]);

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
  const logicalWidth = referenceLogicalWidth;
  const zoom = Math.min(2, Math.max(0.0001, Number(presentationZoom) || 1));
  const [measuredElementHeights, setMeasuredElementHeights] = useState({});
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
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(schedule);
    observer?.observe(artboard);
    artboard.addEventListener("load", schedule, true);
    schedule();
    return () => {
      cancelled = true;
      if (animationFrame !== null) window.cancelAnimationFrame(animationFrame);
      observer?.disconnect();
      artboard.removeEventListener("load", schedule, true);
    };
  }, [activePage?.id, mode, project]);

  const sections = activePage?.sections || [];
  const underTextImageRelationshipsBySection = Object.fromEntries(sections.map((section) => {
    if (!["direct", "free"].includes(section.mode)) return [section.id, new Set()];
    const desktopEntries = (section.freeElements || []).filter(filterElement).map((element) => ({
      element,
      position: getArtboardElementPosition(element, "desktop"),
    }));
    return [section.id, getUnderTextImageRelationships(desktopEntries)];
  }));
  const resolvedDirectPositionsBySection = Object.fromEntries(sections.map((section) => {
    if (!["direct", "free"].includes(section.mode)) return [section.id, {}];
    const visibleElements = (section.freeElements || []).filter(filterElement);
    const entries = visibleElements.map((element) => {
      const underTextRelationship = underTextImageRelationshipsBySection[section.id]?.get(element.id);
      const isUnderTextImage = Boolean(underTextRelationship);
      const authoredDesktopPosition = getArtboardElementPosition(element, "desktop");
      const requestedPosition = getDirectElementPosition?.(element, section, mode)
        || getArtboardElementPosition(element, mode);
      const projectedDesktopPosition = projectUnderTextImagePosition(
        authoredDesktopPosition,
        logicalWidth
      );
      const tabletDriftLimit = logicalWidth * 0.35;
      const hasBrokenTabletVerticalPlacement = mode === "tablet"
        && Math.abs(
          Number(requestedPosition.y || 0) - Number(projectedDesktopPosition.y || 0)
        ) > tabletDriftLimit;
      const savedPosition = mode === "tablet" && isUnderTextImage
        ? projectedDesktopPosition
        : hasBrokenTabletVerticalPlacement
          ? { ...requestedPosition, y: projectedDesktopPosition.y }
          : requestedPosition;
      const measurementKey = `${activePage?.id || "page"}:${mode}:${logicalWidth}:${section.id}:${element.id}`;
      const measuredHeight = measuredElementHeights[measurementKey] || 0;
      const minimumHeight = getDirectElementMinimumSize(element).height;
      const usesMeasuredReservationHeight = element.type === "reservationBlock"
        && measuredHeight > 0;
      const usesCompactDividerFrame = compactDividerTypes.has(element.type);
      const usesFixedEditorialCardHeight = element.type === "imageButton"
        && element.imageButtonVariant === "editorialCard";
      return {
        element,
        readingOrderPosition: authoredDesktopPosition,
        flowRole: isUnderTextImage ? "underText" : "normal",
        anchorElementId: mode === "desktop"
          ? underTextRelationship?.anchorElementId || null
          : null,
        anchorOffsetY: mode === "desktop"
          ? (underTextRelationship?.offsetY || 0) * (logicalWidth / 1200)
          : 0,
        position: {
          ...savedPosition,
          height: usesFixedEditorialCardHeight
            ? 240
            : usesCompactDividerFrame
            ? minimumHeight
            : usesMeasuredReservationHeight
            ? Math.max(minimumHeight, measuredHeight)
            : Math.max(Number(savedPosition.height) || 0, measuredHeight),
        },
      };
    });
    const sizedEntries = resolveResponsiveElementSizing(entries, mode, logicalWidth);
    const orderedEntries = mode === 'mobile'
      ? resolveMobileReadingOrder(sizedEntries, RESPONSIVE_ELEMENT_GAP_RATIO)
      : sizedEntries;
    const resolvedPositions = mode === 'mobile'
      ? Object.fromEntries(orderedEntries.map((entry) => [
          entry.element.id,
          { ...entry.position },
        ]))
      : resolveDirectElementCollisionPadding(orderedEntries, RESPONSIVE_ELEMENT_GAP_RATIO);
    return [
      section.id,
      resolvedPositions,
    ];
  }));
  const resolvedSectionHeights = Object.fromEntries(sections.map((section) => {
    const baseHeight = getSectionLogicalHeight?.(section, mode) || getSectionCanvasHeight(section, mode);
    if (!['direct', 'free'].includes(section.mode)) return [section.id, baseHeight];
    const requiredHeight = (section.freeElements || []).filter(filterElement).reduce((maximum, element) => {
      const position = resolvedDirectPositionsBySection[section.id]?.[element.id]
        || getArtboardElementPosition(element, mode);
      return Math.max(
        maximum,
        (Number(position.y) || 0) + (Number(position.height) || 0) + 48
      );
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
                    const effectivePosition = resolvedDirectPositionsBySection[section.id]?.[element.id]
                      || getArtboardElementPosition(element, mode);
                    const isUnderTextImage = underTextImageRelationshipsBySection[section.id]?.has(element.id);
                    const layoutElement = isUnderTextImage && element.layer !== "behindText"
                      ? { ...element, layer: "behindText" }
                      : element;
                    const usesIntrinsicHeight = intrinsicHeightElementTypes.has(element.type);
                    const frameStyle = {
                      ...getDirectElementFrameStyle({
                        element: layoutElement,
                        position: effectivePosition,
                        viewportWidth: logicalWidth,
                        sectionHeight: logicalHeight,
                        getMetricMinimumHeight,
                        getDirectElementMinimumSize,
                        canvasScale: 1,
                      }),
                      "--site-element-logical-height": `${effectivePosition.height}px`,
                    };
                    const suppliedFrameProps = getDirectFrameProps?.(element, section, frameStyle) || {};
                    const frameProps = {
                      ...suppliedFrameProps,
                      className: `direct-element-frame direct-element-frame-${element.type} ${usesIntrinsicHeight ? "is-intrinsic-height" : ""} ${isUnderTextImage || element.layer === "behindText" ? "is-behind-text" : ""} ${suppliedFrameProps.className || ""}`.trim(),
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
                          shouldMeasure={measurableElementTypes.has(element.type) || usesIntrinsicHeight}
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
