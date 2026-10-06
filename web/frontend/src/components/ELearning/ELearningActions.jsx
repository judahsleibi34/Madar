import { useEffect, useRef } from "react";
import { MoreVertical } from "lucide-react";

export default function ELearningActions({ label, disabled, children }) {
  const ref = useRef(null);
  useEffect(() => {
    const close = (event) => {
      if (ref.current?.open && (event.key === "Escape" || !ref.current.contains(event.target))) {
        ref.current.open = false;
        if (event.key === "Escape") ref.current.querySelector("summary")?.focus();
      }
    };
    document.addEventListener("pointerdown", close); document.addEventListener("keydown", close);
    return () => { document.removeEventListener("pointerdown", close); document.removeEventListener("keydown", close); };
  }, []);
  return <details ref={ref} className="elearning-structure-menu" onClick={(event) => { if (event.target.closest("button") || event.target.closest("a")) ref.current.open = false; }}>
    <summary aria-label={label} aria-disabled={disabled} onClick={(event) => { if (disabled) event.preventDefault(); }}><MoreVertical size={19} aria-hidden="true" /></summary>
    <div className="elearning-structure-menu-items">{children}</div>
  </details>;
}

