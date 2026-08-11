import { useState } from "react";
import { RotateCcw, Wand2 } from "lucide-react";
import { defaultTheme } from "../core/PageBuilder.constants";
import { pageBuilderFontFamilyOptions } from "../core/PageBuilder.theme";
import {
  RESPONSIVE_LAYOUT_ENGINE_VERSION,
  RESPONSIVE_LAYOUT_MODES,
  isSmartResponsiveProject,
} from "../core/PageBuilder.responsiveCapabilities";

const websiteColorControls = [
  ["background", "Site background"],
  ["surface", "Content area"],
  ["headerBackground", "Header color"],
  ["softSurface", "Alternate area"],
  ["text", "Main text"],
  ["muted", "Supporting text"],
  ["accent", "Main brand color"],
  ["accentDark", "Button hover"],
  ["buttonText", "Button text"],
];

const colorFallbacks = {
  background: "#f4f0e8",
  surface: "#fffdfa",
  headerBackground: "#fffdfa",
  softSurface: "#f8f4ed",
  inputBackground: "#f8f4ed",
  text: "#000000",
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

const normalizeHexColor = (value, { allowShort = true } = {}) => {
  const candidate = String(value || "").trim();
  const prefixed = candidate.startsWith("#") ? candidate : `#${candidate}`;
  if (/^#[0-9a-f]{6}$/i.test(prefixed)) return prefixed.toUpperCase();
  if (allowShort && /^#[0-9a-f]{3}$/i.test(prefixed)) {
    return `#${[...prefixed.slice(1)].map((character) => character.repeat(2)).join("")}`.toUpperCase();
  }
  return "";
};

function ThemeColorControl({ fallback, keyName, label, onChange, value }) {
  const currentValue = getColorValue(value, fallback);
  const [hexDraft, setHexDraft] = useState(formatColorValue(currentValue));

  const commitHex = (candidate, options) => {
    const normalized = normalizeHexColor(candidate, options);
    if (!normalized) return false;
    setHexDraft(normalized);
    onChange(keyName, normalized);
    return true;
  };

  return (
    <label className="theme-token-control">
      <span className="theme-token-label">{label}</span>
      <span className="theme-token-input">
        <span
          className="theme-token-swatch"
          style={{ "--theme-token-color": currentValue }}
        >
          <input
            aria-label={`${label} color picker`}
            type="color"
            value={currentValue}
            onChange={(event) => {
              const nextColor = formatColorValue(event.target.value);
              setHexDraft(nextColor);
              onChange(keyName, nextColor);
            }}
          />
        </span>
        <input
          aria-label={`${label} hex`}
          className="theme-token-hex-input"
          type="text"
          inputMode="text"
          maxLength={7}
          spellCheck="false"
          value={hexDraft}
          onChange={(event) => {
            const nextDraft = event.target.value.toUpperCase();
            setHexDraft(nextDraft);
            commitHex(nextDraft, { allowShort: false });
          }}
          onBlur={() => {
            if (!commitHex(hexDraft, { allowShort: true })) {
              setHexDraft(formatColorValue(currentValue));
            }
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter") event.currentTarget.blur();
          }}
          placeholder="#RRGGBB"
        />
      </span>
    </label>
  );
}

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
    const themeNeutralStyles = { ...baseStyles };
    delete themeNeutralStyles.color;
    delete themeNeutralStyles.backgroundColor;
    return themeNeutralStyles;
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
      "document",
      "photoProofing",
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
  legacyShadowEnabled = false,
  legacyShadowComparison = null,
  onToggleLegacyShadow,
}) {
  const websiteTheme = project.theme || {};
  const isSidebar = variant === "sidebar";
  const smartResponsiveEnabled = isSmartResponsiveProject(project);

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

  const toggleSmartResponsive = () => {
    updateProject((current) => ({
      ...current,
      responsiveLayout: {
        mode: smartResponsiveEnabled ? RESPONSIVE_LAYOUT_MODES.legacy : RESPONSIVE_LAYOUT_MODES.smart,
        engineVersion: RESPONSIVE_LAYOUT_ENGINE_VERSION,
      },
    }));
  };

  const responsiveLayoutSection = (
    <section className="theme-sidebar-section theme-responsive-section" aria-labelledby="theme-responsive-heading">
      <div className="theme-sidebar-section-heading">
        <h3 id="theme-responsive-heading">Website responsive layout</h3>
      </div>
      <p className="panel-help">
        {smartResponsiveEnabled
          ? `Smart engine v${RESPONSIVE_LAYOUT_ENGINE_VERSION} is active across every page of this website.`
          : "Legacy mode preserves the three saved artboards across the website."}
      </p>
      <button
        type="button"
        className={smartResponsiveEnabled ? "danger-lite" : "primary-action"}
        onClick={toggleSmartResponsive}
      >
        {smartResponsiveEnabled ? "Use legacy responsive" : "Enable smart responsive"}
      </button>
      {!smartResponsiveEnabled && typeof onToggleLegacyShadow === "function" && (
        <button type="button" className="danger-lite" onClick={onToggleLegacyShadow}>
          {legacyShadowEnabled ? "Stop shadow comparison" : "Compare smart layout in shadow"}
        </button>
      )}
      {legacyShadowComparison && (
        <div className="responsive-shadow-report" role="status">
          <strong>Shadow comparison only</strong>
          <p className="panel-help">
            Compared {legacyShadowComparison.summary.comparedElementCount} elements;{" "}
            {legacyShadowComparison.summary.changedElementCount} differ by more than 0.5px.
            Maximum displacement: {legacyShadowComparison.summary.maximumDisplacement.toFixed(1)}px.
          </p>
          <p className="panel-help">
            Blocking smart diagnostics: {legacyShadowComparison.summary.blockingDiagnosticCount}.
          </p>
        </div>
      )}
    </section>
  );

  if (isSidebar) {
    return (
      <div className="theme-sidebar-editor">
        <h2>Themes</h2>
        <p className="panel-help">Set the shared colors, shape, and typography for your site.</p>

        <div className="page-utility-actions theme-sidebar-actions">
          <button type="button" className="theme-sidebar-reset" onClick={resetWebsiteTheme}>
            <RotateCcw size={16} aria-hidden="true" />
            <span>Reset</span>
          </button>
          <button type="button" className="theme-sidebar-apply" onClick={applyThemeToPageBlocks}>
            <Wand2 size={16} aria-hidden="true" />
            <span>Apply to pages</span>
          </button>
        </div>

        <div className="section-component-palette theme-sidebar-palette">
          <span>Site theme</span>
          <section className="theme-sidebar-section" aria-labelledby="theme-colors-heading">
            <div className="theme-sidebar-section-heading">
              <h3 id="theme-colors-heading">Theme colors</h3>
            </div>
            <div className="theme-sidebar-grid theme-sidebar-color-grid">
              {websiteColorControls.map(([key, label]) =>
                <ThemeColorControl
                  fallback={colorFallbacks[key]}
                  key={`${key}:${getColorValue(websiteTheme[key], colorFallbacks[key])}`}
                  keyName={key}
                  label={label}
                  onChange={updateThemeValue}
                  value={websiteTheme[key]}
                />
              )}
            </div>
          </section>

          <section className="theme-sidebar-section" aria-labelledby="theme-type-heading">
            <div className="theme-sidebar-section-heading">
              <h3 id="theme-type-heading">Shape & typography</h3>
            </div>
            <div className="theme-sidebar-grid theme-sidebar-type-grid">
              <label className="theme-number-control">
                <span className="theme-token-label">Corner radius</span>
                <span className="theme-number-input-wrap">
                  <input
                    aria-label="Corner radius"
                    type="number"
                    min="0"
                    value={websiteTheme.radius ?? 18}
                    onChange={(event) => updateThemeValue("radius", Number(event.target.value))}
                  />
                  <span aria-hidden="true">px</span>
                </span>
              </label>

              <label className="theme-select-control">
                <span className="theme-token-label">Font family</span>
                <select
                  aria-label="Font family"
                  value={websiteTheme.fontFamily || "Inter"}
                  onChange={(event) => updateThemeValue("fontFamily", event.target.value)}
                >
                  {pageBuilderFontFamilyOptions.map((fontFamily) => (
                    <option key={fontFamily} value={fontFamily}>
                      {fontFamily}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </section>
          {responsiveLayoutSection}
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
            <ThemeColorControl
              fallback={colorFallbacks[key]}
              key={`${key}:${getColorValue(websiteTheme[key], colorFallbacks[key])}`}
              keyName={key}
              label={label}
              onChange={updateThemeValue}
              value={websiteTheme[key]}
            />
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
              {pageBuilderFontFamilyOptions.map((fontFamily) => (
                <option key={fontFamily} value={fontFamily}>
                  {fontFamily}
                </option>
              ))}
            </select>
          </label>
        </div>
        {responsiveLayoutSection}
      </section>

    </div>
  );
}
