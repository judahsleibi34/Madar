const globalColorControls = [
  ["background", "App background"],
  ["surface", "Surface"],
  ["softSurface", "Soft surface"],
  ["text", "Text"],
  ["muted", "Muted"],
  ["primary", "Primary"],
  ["accent", "Accent"],
  ["accentDark", "Accent dark"],
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
  background: "#f5f2ee",
  surface: "#ffffff",
  softSurface: "#fbfaf8",
  inputBackground: "#ffffff",
  text: "#1a2744",
  muted: "#6d7484",
  primary: "#1a2744",
  accent: "#8b1e18",
  accentDark: "#b32620",
  border: "#d8dde6",
  buttonText: "#ffffff",
};

const getColorValue = (value, fallback = "#000000") =>
  /^#[0-9a-f]{6}$/i.test(String(value || "")) ? value : fallback;

export default function PageBuilderThemeTab({
  project,
  updateProject,
}) {
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
          <h3>Builder Theme</h3>
        </div>

        <div className="theme-grid">
          {globalColorControls.map(([key, label]) => (
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
          <h3>Forms Theme</h3>
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
