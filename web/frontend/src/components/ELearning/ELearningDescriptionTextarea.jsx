import { learningDescription } from "../../utils/elearningPresentation";
import { useLayoutEffect, useRef } from "react";
import "../../styles/admin/dashboard/elearning-description.css";

export default function ELearningDescriptionTextarea({ value = "", maxLength, onChange, placeholder, label }) {
  const ref = useRef(null);
  useLayoutEffect(() => {
    const textarea = ref.current;
    if (!textarea) return;
    const resize = () => {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.max(144, Math.min(320, textarea.scrollHeight + 2))}px`;
    };
    resize();
    let width = textarea.clientWidth;
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(() => {
      if (textarea.clientWidth === width) return;
      width = textarea.clientWidth;
      resize();
    });
    observer?.observe(textarea);
    return () => observer?.disconnect();
  }, [value]);
  return <textarea className="elearning-description-textarea" ref={ref} value={learningDescription(value)} maxLength={maxLength} rows={6} wrap="soft"
    placeholder={placeholder} aria-label={label} onChange={onChange}
    onPaste={() => requestAnimationFrame(() => { if (ref.current) ref.current.scrollTop = 0; })} />;
}
