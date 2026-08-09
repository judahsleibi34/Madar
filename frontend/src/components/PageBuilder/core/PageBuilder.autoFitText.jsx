import { useLayoutEffect, useRef } from "react";

export default function AutoFitDirectText({ as: Element, fitKey, children, ...props }) {
  const elementRef = useRef(null);

  useLayoutEffect(() => {
    const element = elementRef.current;
    const frame = element?.closest(".direct-element-frame");
    if (!element || !frame) return undefined;

    let animationFrame = null;
    let disposed = false;
    const requestFrame = window.requestAnimationFrame?.bind(window)
      || ((callback) => window.setTimeout(callback, 16));
    const cancelFrame = window.cancelAnimationFrame?.bind(window)
      || window.clearTimeout.bind(window);
    const fitText = () => {
      animationFrame = null;
      element.style.removeProperty("--builder-fitted-font-size");
      element.style.removeProperty("--builder-text-fit-scale");

      if (frame.closest("[data-responsive-layout-mode='smart']")) return;

      if (!element.clientWidth || !element.clientHeight) return;

      const maximumFontSize = Number.parseFloat(window.getComputedStyle(element).fontSize);
      if (!Number.isFinite(maximumFontSize) || maximumFontSize <= 0) return;

      const fits = () =>
        element.scrollWidth <= element.clientWidth + 1 &&
        element.scrollHeight <= element.clientHeight + 1;

      if (fits()) return;

      const applyScale = (scale) => {
        element.style.setProperty("--builder-fitted-font-size", `${maximumFontSize * scale}px`);
        element.style.setProperty("--builder-text-fit-scale", String(scale));
      };
      const declaredMinimum = Number.parseFloat(
        window.getComputedStyle(frame).getPropertyValue("--site-minimum-font-size")
      );
      const minimumFontSize = Number.isFinite(declaredMinimum) && declaredMinimum > 0
        ? declaredMinimum
        : 12;
      let lowerScale = Math.min(1, minimumFontSize / maximumFontSize);
      let upperScale = 1;

      applyScale(lowerScale);
      for (let index = 0; index < 10; index += 1) {
        const candidateScale = (lowerScale + upperScale) / 2;
        applyScale(candidateScale);
        if (fits()) lowerScale = candidateScale;
        else upperScale = candidateScale;
      }
      applyScale(lowerScale);
    };
    const scheduleFit = () => {
      if (disposed || animationFrame !== null) return;
      animationFrame = requestFrame(fitText);
    };
    const resizeObserver = typeof ResizeObserver === "undefined"
      ? null
      : new ResizeObserver(scheduleFit);

    resizeObserver?.observe(frame);
    element.addEventListener("input", scheduleFit);
    window.addEventListener("resize", scheduleFit);
    document.fonts?.addEventListener?.("loadingdone", scheduleFit);
    document.fonts?.ready?.then(scheduleFit);
    scheduleFit();

    return () => {
      disposed = true;
      if (animationFrame !== null) cancelFrame(animationFrame);
      resizeObserver?.disconnect();
      element.removeEventListener("input", scheduleFit);
      window.removeEventListener("resize", scheduleFit);
      document.fonts?.removeEventListener?.("loadingdone", scheduleFit);
    };
  }, [fitKey]);

  return <Element ref={elementRef} {...props}>{children}</Element>;
}
