import { useLayoutEffect } from "react";
import { useLocation, useNavigationType } from "react-router-dom";

export default function ScrollToTop() {
  const { hash, key, pathname, search } = useLocation();
  const navigationType = useNavigationType();

  useLayoutEffect(() => {
    if (navigationType === "POP") return;

    if (hash) {
      const frame = window.requestAnimationFrame(() => {
        document.getElementById(hash.slice(1))?.scrollIntoView();
      });
      return () => window.cancelAnimationFrame(frame);
    }

    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
    document.querySelectorAll(".authenticated-main, .live-store, .tenant-site-runtime").forEach((element) => {
      if (typeof element.scrollTo === "function") {
        element.scrollTo({ top: 0, left: 0, behavior: "instant" });
      } else {
        element.scrollTop = 0;
        element.scrollLeft = 0;
      }
    });
  }, [hash, key, navigationType, pathname, search]);

  return null;
}
