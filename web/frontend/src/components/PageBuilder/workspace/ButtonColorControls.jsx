import { useState } from "react";
import {
  getButtonContrastWarnings,
  normalizeButtonColor,
} from "../core/PageBuilder.buttonColors";

const CONTROLS = [
  ["backgroundColor", "Button background color"],
  ["textColor", "Button text color"],
  ["hoverBackgroundColor", "Button hover background color"],
  ["hoverTextColor", "Button hover text color"],
  ["borderColor", "Button border color"],
];

const PICKER_FALLBACK = "#000000";

export default function ButtonColorControls({ element, onChange }) {
  const [invalidDrafts, setInvalidDrafts] = useState({});
  const valueFor = (field) => (
    Object.hasOwn(invalidDrafts, field) ? invalidDrafts[field] : element?.[field] || ""
  );

  const setColor = (field, rawValue) => {
    const normalized = normalizeButtonColor(rawValue);
    if (normalized === null) {
      setInvalidDrafts((current) => ({ ...current, [field]: rawValue }));
      return;
    }
    setInvalidDrafts((current) => {
      const next = { ...current };
      delete next[field];
      return next;
    });
    onChange({ [field]: normalized });
  };

  const warnings = getButtonContrastWarnings(element);

  return (
    <fieldset className="button-color-controls">
      <legend>Button colors</legend>
      {CONTROLS.map(([field, label]) => {
        const currentValue = valueFor(field);
        const normalized = normalizeButtonColor(currentValue);
        const invalid = normalized === null;
        const inputId = `button-color-${element?.id || "selected"}-${field}`;
        return (
          <div className="button-color-control" key={field}>
            <label htmlFor={inputId}>{label}</label>
            <div className="button-color-inputs">
              <input
                type="color"
                aria-label={`${label} picker`}
                value={normalized || PICKER_FALLBACK}
                onChange={(event) => setColor(field, event.target.value)}
              />
              <input
                id={inputId}
                type="text"
                inputMode="text"
                autoComplete="off"
                aria-invalid={invalid ? "true" : "false"}
                aria-describedby={invalid ? `${inputId}-error` : undefined}
                placeholder="#1A2B3C"
                value={currentValue}
                onChange={(event) => setColor(field, event.target.value)}
              />
              <button type="button" onClick={() => setColor(field, "")} disabled={!currentValue}>
                Clear
              </button>
            </div>
            {invalid && <span className="button-color-error" id={`${inputId}-error`}>Use a six-digit hexadecimal color.</span>}
          </div>
        );
      })}
      {warnings.length > 0 && (
        <div className="button-contrast-warning" role="status" aria-live="polite">
          {warnings.map((warning) => <p key={warning}>{warning}</p>)}
        </div>
      )}
    </fieldset>
  );
}
