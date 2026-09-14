import { useLayoutEffect, useRef } from "react";

// A sibling overlay escapes the artwork's stacking context without raising it.
export default function SelectionBoundary({ frameStyle, elementId, children }) {
  const boundaryRef = useRef(null);
  useLayoutEffect(() => {
    const boundary = boundaryRef.current;
    const frame = boundary?.previousElementSibling;
    if (!frame || frame.dataset.builderElementId !== elementId) return undefined;
    const sync = () => {
      // Logical dimensions stay correct at every camera zoom level.
      if (frame.offsetWidth) boundary.style.width = `${frame.offsetWidth}px`;
      if (frame.offsetHeight) boundary.style.height = `${frame.offsetHeight}px`;
    };
    sync();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(sync);
    observer?.observe(frame);
    return () => observer?.disconnect();
  }, [elementId, frameStyle]);

  return (
    <div ref={boundaryRef} className="builder-selection-boundary"
      data-selection-for={elementId}
      style={{ ...frameStyle, zIndex: 20 }}
      onClick={(event) => event.stopPropagation()}>
      {children}
    </div>
  );
}
