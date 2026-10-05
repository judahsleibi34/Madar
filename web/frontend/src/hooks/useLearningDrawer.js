import { useEffect } from "react";

// Both fixed learner drawers share keyboard handling and return focus to their opener.
export default function useLearningDrawer(open, panelRef, close) {
  useEffect(() => {
    if (!open || !panelRef.current) return undefined;
    const panel = panelRef.current;
    const opener = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    const focusable = () => [...panel.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), [tabindex="0"]')].filter(node => node.getClientRects().length);
    document.body.style.overflow = "hidden";
    (focusable()[0] || panel).focus();
    const keyboard = event => {
      if (event.key === "Escape") { event.preventDefault(); close(); }
      if (event.key === "Tab") {
        const nodes = focusable(), first = nodes[0], last = nodes.at(-1);
        if (!first) { event.preventDefault(); panel.focus(); }
        else if (event.shiftKey && (document.activeElement === first || !panel.contains(document.activeElement))) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && (document.activeElement === last || !panel.contains(document.activeElement))) { event.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener("keydown", keyboard);
    return () => { document.removeEventListener("keydown", keyboard); document.body.style.overflow = previousOverflow; if (opener?.isConnected) opener.focus(); };
  }, [open, panelRef, close]);
}
