import { useState, useRef, useEffect } from "react";
import "./LanguageSwitcher.css";

const languages = [
  { code: "en", label: "EN", full: "English" },
  { code: "ar", label: "AR", full: "العربية" },
];

export default function LanguageSwitcher({ current, onChange }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const selected = languages.find((l) => l.code === current);

  return (
    <div className="lang-switcher" ref={ref}>
      <button
        className={`lang-trigger ${open ? "open" : ""}`}
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        {selected.label}
        <svg
          className={`lang-chevron ${open ? "rotated" : ""}`}
          width="12"
          height="12"
          viewBox="0 0 12 12"
          fill="none"
        >
          <path
            d="M2 4L6 8L10 4"
            stroke="#1a2744"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      <div className={`lang-dropdown ${open ? "visible" : ""}`} role="listbox">
        {languages.map((lang, i) => (
          <div
            key={lang.code}
            className={`lang-option ${current === lang.code ? "active" : ""}`}
            role="option"
            aria-selected={current === lang.code}
            onClick={() => {
              onChange(lang.code);
              setOpen(false);
            }}
            style={{
              borderBottom:
                i < languages.length - 1
                  ? "1px solid rgba(26,39,68,0.07)"
                  : "none",
            }}
          >
            {lang.full}
            {current === lang.code && <span className="lang-check">✓</span>}
          </div>
        ))}
      </div>
    </div>
  );
}