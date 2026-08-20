import { useEffect, useRef } from "react";

export default function PageBuilderMeasuredFrame({
  measureEnabled = false,
  measurementKey = "",
  onMeasuredHeight,
  children,
  ...frameProps
}) {
  const frameRef = useRef(null);
  const callbackRef = useRef(onMeasuredHeight);
  const animationFrameRef = useRef(null);
  const lastReportedHeightRef = useRef(0);

  useEffect(() => {
    callbackRef.current = onMeasuredHeight;
  }, [onMeasuredHeight]);

  useEffect(() => {
    if (!measureEnabled || typeof ResizeObserver === "undefined") return undefined;

    const frame = frameRef.current;
    const content = frame?.querySelector(":scope > .direct-element-content");
    if (!content) return undefined;

    let cancelled = false;
    let observer = null;
    let settleFrame = null;

    const reportMeasurement = () => {
      animationFrameRef.current = null;
      if (cancelled) return;

      const activeElement = document.activeElement;
      if (
        activeElement &&
        (content.contains(activeElement) || activeElement.closest?.(".builder-inspector"))
      ) return;

      const measuredHeight = Math.ceil(content.scrollHeight || content.getBoundingClientRect().height || 0);
      if (!measuredHeight || Math.abs(lastReportedHeightRef.current - measuredHeight) <= 1) return;

      lastReportedHeightRef.current = measuredHeight;
      callbackRef.current?.(measuredHeight);
    };

    const scheduleMeasurement = () => {
      if (cancelled || animationFrameRef.current !== null) return;
      animationFrameRef.current = window.requestAnimationFrame(reportMeasurement);
    };

    // Wait until the responsive frame has painted before observing it. This
    // prevents the old viewport and new viewport from racing each other.
    settleFrame = window.requestAnimationFrame(() => {
      settleFrame = window.requestAnimationFrame(() => {
        if (cancelled) return;
        observer = new ResizeObserver(scheduleMeasurement);
        observer.observe(content);
        document.addEventListener("focusout", scheduleMeasurement);
        scheduleMeasurement();
      });
    });

    return () => {
      cancelled = true;
      observer?.disconnect();
      document.removeEventListener("focusout", scheduleMeasurement);
      if (settleFrame !== null) window.cancelAnimationFrame(settleFrame);
      if (animationFrameRef.current !== null) {
        window.cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
      lastReportedHeightRef.current = 0;
    };
  }, [measureEnabled, measurementKey]);

  return <div ref={frameRef} {...frameProps}>{children}</div>;
}
