import { useState } from "react";
import { defaultTheme } from "../core/PageBuilder.constants";

const websiteColorControls = [
  ["background", "Page background"],
  ["surface", "Content surface"],
  ["softSurface", "Alternate section"],
  ["text", "Main text"],
  ["muted", "Secondary text"],
  ["accent", "Brand accent"],
  ["accentDark", "Accent hover"],
  ["buttonText", "Button text"],
];

const formColorControls = [
  ["background", "Page background"],
  ["surface", "Form surface"],
  ["inputBackground", "Input background"],
  ["text", "Text"],
  ["muted", "Help text"],
  ["border", "Border"],
  ["accent", "Accent"],
  ["buttonText", "Button text"],
];

const colorFallbacks = {
  background: "#fafaf7",
  surface: "#ffffff",
  softSurface: "#f7f5ef",
  inputBackground: "#ffffff",
  text: "#1b2a4a",
  muted: "#6f7787",
  primary: "#1b2a4a",
  accent: "#852c21",
  accentDark: "#6f241b",
  border: "#d8dde6",
  buttonText: "#ffffff",
};

const getColorValue = (value, fallback = "#000000") =>
  /^#[0-9a-f]{6}$/i.test(String(value || "")) ? value : fallback;

const getThemeElementStyles = (element = {}) => {
  const baseStyles = { ...(element.styles || {}) };

  if (element.type === "heading") {
    return {
      ...baseStyles,
      color: "var(--theme-text)",
      backgroundColor: "",
    };
  }

  if (element.type === "text") {
    return {
      ...baseStyles,
      color: "var(--theme-text-soft)",
      backgroundColor: "",
    };
  }

  if (element.type === "button") {
    return {
      ...baseStyles,
      color: "var(--theme-text-inverse)",
      backgroundColor: "var(--theme-primary)",
    };
  }

  if (
    [
      "card",
      "list",
      "metric",
      "embed",
      "loginBlock",
      "registrationBlock",
      "formBlock",
      "reservationBlock",
      "responsesTable",
    ].includes(element.type)
  ) {
    return {
      ...baseStyles,
      color: baseStyles.color || "var(--theme-text)",
      backgroundColor: "var(--theme-surface)",
    };
  }

  return baseStyles;
};

const applyThemeToElement = (element = {}) => ({
  ...element,
  styles: getThemeElementStyles(element),
});

const applyThemeToSection = (section = {}, sectionIndex = 0) => ({
  ...section,
  layout: {
    ...(section.layout || {}),
    background: sectionIndex % 2 === 0 ? "var(--theme-bg)" : "var(--theme-bg-soft)",
  },
  rows: (section.rows || []).map((row) => ({
    ...row,
    columns: (row.columns || []).map((column) => ({
      ...column,
      elements: (column.elements || []).map(applyThemeToElement),
    })),
  })),
  freeElements: (section.freeElements || []).map(applyThemeToElement),
});

export default function PageBuilderThemeTab({
  project,
  updateProject,
  saveProject,
}) {
  const [savingTheme, setSavingTheme] = useState(false);

  const saveTheme = async () => {
    if (!saveProject || savingTheme) return;

    setSavingTheme(true);
    try {
      await saveProject();
    } finally {
      setSavingTheme(false);
    }
  };

  const resetWebsiteTheme = () => {
    updateProject((prev) => ({
      ...prev,
      theme: {
        ...defaultTheme,
        form: prev.theme?.form || {},
      },
    }));
  };

  const resetFormTheme = () => {
    updateProject((prev) => ({
      ...prev,
      theme: {
        ...prev.theme,
        form: {},
      },
    }));
  };

  const applyThemeToPageBlocks = () => {
    updateProject((prev) => ({
      ...prev,
      pages: (prev.pages || []).map((page) => ({
        ...page,
        sections: (page.sections || []).map(applyThemeToSection),
      })),
    }));
  };

  const updateThemeValue = (key, value) => {
    updateProject((prev) => ({
      ...prev,
      theme: {
        ...prev.theme,
        [key]: value,
      },
    }));
  };

  const updateFormThemeValue = (key, value) => {
    updateProject((prev) => ({
      ...prev,
      theme: {
        ...prev.theme,
        form: {
          ...(prev.theme?.form || {}),
          [key]: value,
        },
      },
    }));
  };

  return (
    <div className="workspace-page theme-workspace-page">
      <section className="theme-section">
        <div className="theme-section-heading">
          <div>
            <span className="workspace-kicker">Website</span>
            <h3>Website theme</h3>
            <p>Controls the published site colors, typography, buttons, header, footer, and page canvas.</p>
          </div>
          <div className="theme-section-actions">
            <button type="button" className="theme-reset-button" onClick={resetWebsiteTheme}>
              Reset website colors
            </button>
            <button type="button" className="theme-reset-button" onClick={applyThemeToPageBlocks}>
              Apply theme to page blocks
            </button>
            <button type="button" className="theme-save-button" onClick={saveTheme} disabled={savingTheme || !saveProject}>
              {savingTheme ? "Saving..." : "Save website theme"}
            </button>
          </div>
        </div>

        <div className="theme-grid">
          {websiteColorControls.map(([key, label]) => (
            <label className="theme-control" key={key}>
              {label}
              <input
                type="color"
                value={getColorValue(project.theme?.[key], colorFallbacks[key])}
                onChange={(event) => updateThemeValue(key, event.target.value)}
              />
            </label>
          ))}

          <label className="theme-control">
            Radius
            <input
              type="number"
              min="0"
              value={project.theme?.radius || 18}
              onChange={(event) => updateThemeValue("radius", Number(event.target.value))}
            />
          </label>

          <label className="theme-control">
            Font family
            <input
              value={project.theme?.fontFamily || "Inter"}
              onChange={(event) => updateThemeValue("fontFamily", event.target.value)}
            />
          </label>
        </div>
      </section>

      <section className="theme-section">
        <div className="theme-section-heading">
          <div>
            <span className="workspace-kicker">Website forms</span>
            <h3>Form appearance</h3>
            <p>Controls forms embedded on published website pages.</p>
          </div>
          <button type="button" className="theme-reset-button" onClick={resetFormTheme}>
            Use website colors
          </button>
        </div>

        <div className="theme-grid">
          {formColorControls.map(([key, label]) => (
            <label className="theme-control" key={key}>
              {label}
              <input
                type="color"
                value={getColorValue(
                  project.theme?.form?.[key],
                  getColorValue(project.theme?.[key], colorFallbacks[key])
                )}
                onChange={(event) => updateFormThemeValue(key, event.target.value)}
              />
            </label>
          ))}

          <label className="theme-control">
            Form radius
            <input
              type="number"
              min="0"
              value={project.theme?.form?.radius ?? 8}
              onChange={(event) => updateFormThemeValue("radius", Number(event.target.value))}
            />
          </label>

          <label className="theme-control">
            Field radius
            <input
              type="number"
              min="0"
              value={project.theme?.form?.fieldRadius ?? 14}
              onChange={(event) => updateFormThemeValue("fieldRadius", Number(event.target.value))}
            />
          </label>
        </div>
      </section>
    </div>
  );
}
