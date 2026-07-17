import { RotateCcw, Wand2 } from "lucide-react";
import { defaultTheme } from "../core/PageBuilder.constants";

const websiteColorControls = [
  ["background", "Site background"],
  ["surface", "Content area"],
  ["softSurface", "Alternate area"],
  ["text", "Main text"],
  ["muted", "Supporting text"],
  ["accent", "Main brand color"],
  ["accentDark", "Button hover"],
  ["buttonText", "Button text"],
];

const fontFamilyOptions = [
  "Inter",
  "Arial",
  "Verdana",
  "Tahoma",
  "Trebuchet MS",
  "Georgia",
  "Times New Roman",
  "Courier New",
];

const colorFallbacks = {
  background: "#f4f0e8",
  surface: "#fffdfa",
  softSurface: "#f8f4ed",
  inputBackground: "#f8f4ed",
  text: "#162033",
  muted: "#6f7787",
  primary: "#162033",
  accent: "#852c21",
  accentDark: "#6f241b",
  border: "#ddd6ca",
  buttonText: "#ffffff",
};

const getColorValue = (value, fallback = "#000000") =>
  /^#[0-9a-f]{6}$/i.test(String(value || "")) ? value : fallback;

const formatColorValue = (value) => String(value || "").toUpperCase();

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
  variant = "page",
}) {
  const websiteTheme = project.theme || {};
  const isSidebar = variant === "sidebar";

  const resetWebsiteTheme = () => {
    updateProject((prev) => ({
      ...prev,
      theme: {
        ...defaultTheme,
        form: prev.theme?.form || {},
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

  const renderColorControl = ({
    fallback,
    keyName,
    label,
    onChange,
    value,
  }) => {
    const currentValue = getColorValue(value, fallback);

    return (
      <label className="theme-token-control" key={keyName}>
        <span className="theme-token-label">{label}</span>
        <span className="theme-token-input">
          <span
            className="theme-token-swatch"
            style={{ "--theme-token-color": currentValue }}
            aria-hidden="true"
          />
          <span className="theme-token-value">{formatColorValue(currentValue)}</span>
          <input
            aria-label={label}
            type="color"
            value={currentValue}
            onChange={(event) => onChange(keyName, event.target.value)}
          />
        </span>
      </label>
    );
  };

  if (isSidebar) {
    return (
      <div className="theme-sidebar-editor">
        <h2>Themes</h2>
        <p className="panel-help">Tune the builder canvas and preview changes beside this panel.</p>

        <div className="page-utility-actions theme-sidebar-actions">
          <button type="button" onClick={resetWebsiteTheme}>
            <RotateCcw size={16} aria-hidden="true" />
            <span>Reset</span>
          </button>
          <button type="button" onClick={applyThemeToPageBlocks}>
            <Wand2 size={16} aria-hidden="true" />
            <span>Apply</span>
          </button>
        </div>

        <div className="section-component-palette theme-sidebar-palette">
          <span>Theme colors</span>
          <div className="theme-sidebar-grid">
            {websiteColorControls.map(([key, label]) =>
              renderColorControl({
                fallback: colorFallbacks[key],
                keyName: key,
                label,
                onChange: updateThemeValue,
                value: websiteTheme[key],
              })
            )}
          </div>

          <span>Shape & typography</span>
          <div className="theme-sidebar-grid">
            <label className="theme-number-control">
              <span className="theme-token-label">Round corners</span>
              <input
                type="number"
                min="0"
                value={websiteTheme.radius || 18}
                onChange={(event) => updateThemeValue("radius", Number(event.target.value))}
              />
            </label>

            <label className="theme-select-control">
              <span className="theme-token-label">Font family</span>
              <select
                value={websiteTheme.fontFamily || "Inter"}
                onChange={(event) => updateThemeValue("fontFamily", event.target.value)}
              >
                {fontFamilyOptions.map((fontFamily) => (
                  <option key={fontFamily} value={fontFamily}>
                    {fontFamily}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="workspace-page theme-workspace-page">
      <section className="theme-section">
        <div className="theme-section-heading">
          <div>
            <span className="workspace-kicker">{isSidebar ? "Builder themes" : "Builder style"}</span>
            <h3>Canvas look</h3>
            <p>
              {isSidebar
                ? "Edit the builder page theme while keeping the canvas visible."
                : "Choose the colors, font, buttons, and page background used by the builder canvas."}
            </p>
          </div>
          <div className="theme-section-actions">
            <button type="button" className="theme-action-button" onClick={resetWebsiteTheme}>
              <RotateCcw size={16} />
              <span>Reset</span>
            </button>
            <button type="button" className="theme-action-button" onClick={applyThemeToPageBlocks}>
              <Wand2 size={16} />
              <span>Apply to pages</span>
            </button>
          </div>
        </div>

        <div className="theme-grid">
          {websiteColorControls.map(([key, label]) =>
            renderColorControl({
              fallback: colorFallbacks[key],
              keyName: key,
              label,
              onChange: updateThemeValue,
              value: websiteTheme[key],
            })
          )}

          <label className="theme-number-control">
            <span className="theme-token-label">Round corners</span>
            <input
              type="number"
              min="0"
              value={websiteTheme.radius || 18}
              onChange={(event) => updateThemeValue("radius", Number(event.target.value))}
            />
          </label>

          <label className="theme-select-control">
            <span className="theme-token-label">Font family</span>
            <select
              value={websiteTheme.fontFamily || "Inter"}
              onChange={(event) => updateThemeValue("fontFamily", event.target.value)}
            >
              {fontFamilyOptions.map((fontFamily) => (
                <option key={fontFamily} value={fontFamily}>
                  {fontFamily}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

    </div>
  );
}
